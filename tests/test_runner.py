import ctypes
import errno
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = PROJECT_ROOT / "template" / ".harness" / "harness_runner.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("harness_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class BoundedRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_runner()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_python(self, source, name="command.log", **kwargs):
        log_path = self.workspace / name
        result = self.runner.run_bounded(
            [sys.executable, "-c", source], self.workspace, log_path, **kwargs
        )
        return result, log_path

    def assert_process_gone(self, pid):
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotIn(str(pid), result.stdout)
            return
        deadline = time.monotonic() + 2
        while True:
            try:
                os.kill(pid, 0)
            except OSError as exc:
                if exc.errno == errno.ESRCH:
                    return
                raise
            if time.monotonic() >= deadline:
                self.fail(f"descendant process {pid} survived runner cleanup")
            time.sleep(0.02)

    def assert_handshake_setup_failure_is_cleaned(self, attribute, replacement, message):
        marker = self.workspace / f"{attribute}-must-not-exist"
        processes = []
        jobs = []
        real_popen = subprocess.Popen

        class TrackingJob:
            def __init__(self, process):
                self.process = process
                self.closed = False
                jobs.append(self)

            def terminate(self, _returncode):
                if self.process.poll() is None:
                    self.process.kill()
                return True

            def close(self):
                self.closed = True

        def start_real_helper(*args, **kwargs):
            kwargs.pop("creationflags", None)
            process = real_popen(*args, start_new_session=True, **kwargs)
            processes.append(process)
            return process

        try:
            with (
                mock.patch.object(
                    self.runner.subprocess, "Popen", side_effect=start_real_helper
                ),
                mock.patch.object(self.runner, "_WindowsJob", TrackingJob),
                mock.patch.object(self.runner.threading, attribute, replacement),
            ):
                with self.assertRaisesRegex(RuntimeError, message):
                    self.runner._start_windows_process(
                        [
                            sys.executable,
                            "-c",
                            f"from pathlib import Path; Path({str(marker)!r}).touch()",
                        ],
                        self.workspace,
                        time.monotonic() + 1,
                    )

            self.assertFalse(marker.exists())
            self.assertIsNotNone(processes[0].poll())
            self.assertTrue(processes[0].stdin.closed)
            self.assertTrue(processes[0].stdout.closed)
            self.assertTrue(jobs[0].closed)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if not process.stdin.closed:
                    process.stdin.close()
                if not process.stdout.closed:
                    process.stdout.close()

    def test_records_combined_output_and_nonzero_exit(self):
        # Preserve mixed line endings byte-for-byte on every platform.
        source = (
            "import os, sys; os.write(sys.stdout.fileno(), b'out\\r\\n'); "
            "os.write(sys.stderr.fileno(), b'err\\n'); sys.exit(7)"
        )

        result, log_path = self.run_python(source)

        self.assertEqual(7, result.returncode)
        self.assertEqual("exit", result.reason)
        self.assertEqual(b"out\r\nerr\n", log_path.read_bytes())
        self.assertEqual(9, result.bytes_written)
        self.assertFalse(result.truncated)

    def test_preserves_invalid_utf8_as_raw_bytes(self):
        result, log_path = self.run_python(
            "import os, sys; os.write(sys.stdout.fileno(), b'\\xff\\xfe\\x00ok')"
        )

        self.assertEqual(0, result.returncode)
        self.assertEqual(b"\xff\xfe\x00ok", log_path.read_bytes())
        self.assertEqual(5, result.bytes_written)
        self.assertFalse(result.truncated)

    def test_stops_at_output_limit_without_buffering_the_remainder(self):
        result, log_path = self.run_python(
            "import os, sys; data=b'x'*65536; [(os.write(sys.stdout.fileno(), data)) for _ in range(256)]",
            max_output_bytes=100_003,
        )

        self.assertEqual(125, result.returncode)
        self.assertEqual("output_limit", result.reason)
        self.assertEqual(100_003, result.bytes_written)
        self.assertEqual(100_003, log_path.stat().st_size)
        self.assertTrue(result.truncated)

    @unittest.skipUnless(sys.platform == "darwin", "Darwin zombie process-group behavior")
    def test_cleanup_reaps_exited_leader_before_retrying_group_signal(self):
        process = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
        try:
            # Darwin removes an exited leader from its group before wait() reaps
            # it. Observe that boundary without poll(), which would reap it.
            deadline = time.monotonic() + 5
            while True:
                try:
                    os.getpgid(process.pid)
                except ProcessLookupError:
                    break
                self.assertLess(time.monotonic(), deadline, "child never exited")
                time.sleep(0.01)
            self.assertIsNone(process.returncode)
            self.runner._terminate_tree(process, None, 125)
            self.assertEqual(0, process.returncode)
            self.assert_process_gone(process.pid)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()

    @unittest.skipUnless(os.name == "posix", "POSIX process-group permissions")
    def test_cleanup_does_not_hide_permission_error_for_live_process(self):
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
        )
        try:
            with mock.patch.object(self.runner.os, "killpg", side_effect=PermissionError("denied")):
                with self.assertRaisesRegex(PermissionError, "denied"):
                    self.runner._terminate_tree(process, None, 125)
            self.assertIsNone(process.poll())
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()

    def test_exact_output_limit_is_not_reported_as_truncated(self):
        result, log_path = self.run_python(
            "import os, sys; os.write(sys.stdout.fileno(), b'12345')",
            max_output_bytes=5,
        )

        self.assertEqual(0, result.returncode)
        self.assertEqual("exit", result.reason)
        self.assertEqual(b"12345", log_path.read_bytes())
        self.assertEqual(5, result.bytes_written)
        self.assertFalse(result.truncated)

    def test_timeout_returns_promptly_and_retains_partial_output(self):
        started = time.monotonic()
        result, log_path = self.run_python(
            "import os, time; os.write(1, b'started\\n'); time.sleep(30)",
            timeout_seconds=0.2,
        )

        self.assertEqual(124, result.returncode)
        self.assertEqual("timeout", result.reason)
        self.assertEqual(b"started\n", log_path.read_bytes())
        self.assertEqual(8, result.bytes_written)
        self.assertFalse(result.truncated)
        self.assertLess(time.monotonic() - started, 3)

    @unittest.skipUnless(hasattr(signal, "SIGINT"), "SIGINT is unavailable")
    def test_keyboard_interrupt_returns_130_and_cleans_ready_process_tree(self):
        self.assert_ready_interrupt_cleanup()

    @unittest.skipUnless(hasattr(signal, "SIGINT"), "SIGINT is unavailable")
    def test_interrupt_does_not_enter_condition_wait_cleanup_on_main_thread(self):
        # Emulate the observed Python 3.9 Windows Condition cleanup failure at
        # the blocking boundary, while retaining real output and process cleanup.
        real_wait = threading.Event.wait

        def wait_with_interrupt_cleanup_failure(event, timeout=None):
            if threading.current_thread() is threading.main_thread() and timeout == 0.01:
                try:
                    raise KeyboardInterrupt
                except KeyboardInterrupt as exc:
                    raise RuntimeError("release unlocked lock") from exc
            return real_wait(event, timeout)

        with mock.patch.object(threading.Event, "wait", wait_with_interrupt_cleanup_failure):
            self.assert_ready_interrupt_cleanup()

    def assert_ready_interrupt_cleanup(self):
        pid_path = self.workspace / "interrupt-pids.json"
        log_path = self.workspace / "interrupt.log"
        stop = threading.Event()
        sent = []

        def interrupt_when_ready():
            deadline = time.monotonic() + 10
            while not stop.is_set() and time.monotonic() < deadline:
                if pid_path.exists() and log_path.exists() and log_path.read_bytes() == b"before interrupt\xff\n":
                    sent.append(True)
                    signal.raise_signal(signal.SIGINT)
                    return
                time.sleep(0.01)

        watcher = threading.Thread(target=interrupt_when_ready, daemon=True)
        watcher.start()
        source = (
            "import json, os, pathlib, subprocess, sys, time; "
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
            f"pathlib.Path({str(pid_path)!r}).write_text(json.dumps([os.getpid(), child.pid])); "
            "os.write(1, b'before interrupt\\xff\\n'); time.sleep(30)"
        )
        try:
            result, log_path = self.run_python(source, name="interrupt.log", timeout_seconds=15)
        finally:
            stop.set()
            watcher.join(timeout=2)
        self.assertTrue(sent, "child never became ready for interrupt")
        self.assertEqual(130, result.returncode)
        self.assertEqual("interrupted", result.reason)
        self.assertEqual(b"before interrupt\xff\n", log_path.read_bytes())
        self.assertEqual(18, result.bytes_written)
        self.assertFalse(result.truncated)
        for pid in json.loads(pid_path.read_text()):
            self.assert_process_gone(pid)

    def test_timeout_kills_descendant_that_keeps_output_pipe_open(self):
        pid_path = self.workspace / "descendant.pid"
        child_source = (
            "import os, pathlib, subprocess, sys; "
            "grandchild=\"import os, signal, time; \" "
            "+ (\"signal.signal(signal.SIGTERM, signal.SIG_IGN); \" if os.name != 'nt' else \"\") "
            "+ \"time.sleep(30)\"; "
            "p=subprocess.Popen([sys.executable, '-c', grandchild]); "
            f"pathlib.Path({str(pid_path)!r}).write_text(str(p.pid), encoding='ascii')"
        )

        result, _ = self.run_python(child_source, timeout_seconds=0.3)

        self.assertEqual("timeout", result.reason)
        self.assertTrue(pid_path.exists())
        self.assert_process_gone(int(pid_path.read_text(encoding="ascii")))

    def test_existing_log_is_never_overwritten(self):
        log_path = self.workspace / "command.log"
        log_path.write_bytes(b"keep me")

        with self.assertRaises(FileExistsError):
            self.runner.run_bounded(
                [sys.executable, "-c", "print('replacement')"], self.workspace, log_path
            )

        self.assertEqual(b"keep me", log_path.read_bytes())

    def test_missing_executable_raises_oserror(self):
        with self.assertRaises(OSError):
            self.runner.run_bounded(
                [str(self.workspace / "missing-program")],
                self.workspace,
                self.workspace / "command.log",
            )

    def test_rejects_invalid_parameters_before_creating_log(self):
        invalid_calls = [
            ([], 1, 1),
            ([sys.executable, ""], 1, 1),
            ([sys.executable], 0, 1),
            ([sys.executable], True, 1),
            ([sys.executable], 1, 0),
            ([sys.executable], 1, True),
        ]

        for index, (argv, timeout, output_limit) in enumerate(invalid_calls):
            log_path = self.workspace / f"invalid-{index}.log"
            with self.subTest(argv=argv, timeout=timeout, output_limit=output_limit):
                with self.assertRaises(ValueError):
                    self.runner.run_bounded(
                        argv,
                        self.workspace,
                        log_path,
                        timeout_seconds=timeout,
                        max_output_bytes=output_limit,
                    )
                self.assertFalse(log_path.exists())

    def test_rejects_non_path_workspace_and_log_path(self):
        cases = [
            (None, self.workspace / "command.log"),
            (self.workspace, None),
        ]

        for workspace, log_path in cases:
            with self.subTest(workspace=workspace, log_path=log_path):
                with self.assertRaises(ValueError):
                    self.runner.run_bounded(
                        [sys.executable, "-c", "pass"], workspace, log_path
                    )

    def test_reader_error_terminates_process_and_closes_owned_resources(self):
        class BrokenLog:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def write(self, _data):
                raise OSError("injected log failure")

        real_job = self.runner._WindowsJob
        jobs = []

        class TrackingJob:
            def __init__(self, process):
                self.job = real_job(process)
                self.closed = False
                self.was_assigned = self.job._handle is not None
                jobs.append(self)

            def terminate(self, _returncode):
                # Exercise the native taskkill fallback without skipping Job assignment.
                return False

            def close(self):
                self.job.close()
                self.closed = True

        processes = []
        cleanup_processes = []
        real_popen = subprocess.Popen

        def start_real_process(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            if args[0][0] == "taskkill":
                cleanup_processes.append((list(args[0]), process))
            else:
                processes.append(process)
            return process

        pid_path = self.workspace / "reader-error-child.pid"
        with (
            mock.patch.object(self.runner.Path, "open", return_value=BrokenLog()),
            mock.patch.object(self.runner.subprocess, "Popen", side_effect=start_real_process),
            mock.patch.object(self.runner, "_WindowsJob", TrackingJob),
        ):
            with self.assertRaisesRegex(OSError, "injected log failure"):
                self.runner.run_bounded(
                    [
                        sys.executable,
                        "-c",
                        "import os, pathlib, sys, time; "
                        f"pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid()), encoding='ascii'); "
                        "os.write(sys.stdout.fileno(), b'x'); time.sleep(30)",
                    ],
                    self.workspace,
                    self.workspace / "ignored.log",
                )

        self.assertEqual(1, len(processes))
        self.assertIsNotNone(processes[0].poll())
        self.assertTrue(processes[0].stdout.closed)
        self.assertEqual(1, len(jobs))
        self.assertTrue(jobs[0].closed)
        self.assertIsNone(jobs[0].job._handle)
        self.assert_process_gone(int(pid_path.read_text(encoding="ascii")))
        if os.name == "nt":
            self.assertTrue(jobs[0].was_assigned)
            self.assertEqual(
                [sys.executable, "-I", "-c", self.runner._WINDOWS_LAUNCHER],
                processes[0].args,
            )
            self.assertEqual(1, len(cleanup_processes))
            argv, cleanup_process = cleanup_processes[0]
            self.assertEqual(["taskkill", "/PID", str(processes[0].pid), "/T", "/F"], argv)
            self.assertIsNotNone(cleanup_process.poll())
        else:
            self.assertEqual([], cleanup_processes)

    def test_job_setup_error_terminates_process_and_closes_stdout(self):
        processes = []
        real_popen = subprocess.Popen

        def start_real_process(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process

        with (
            mock.patch.object(self.runner.subprocess, "Popen", side_effect=start_real_process),
            mock.patch.object(
                self.runner, "_WindowsJob", side_effect=OSError("injected job setup failure")
            ),
        ):
            with self.assertRaisesRegex(OSError, "injected job setup failure"):
                self.run_python("import time; time.sleep(30)")

        self.assertEqual(1, len(processes))
        self.assertIsNotNone(processes[0].poll())
        self.assertTrue(processes[0].stdout.closed)

    def test_windows_taskkill_fallback_is_bounded(self):
        class NoJob:
            def terminate(self, _returncode):
                return False

        class Process:
            pid = 4242

            def __init__(self):
                self.killed = False
                self.waits = 0

            def wait(self, timeout=None):
                self.waits += 1
                if self.waits == 1:
                    raise subprocess.TimeoutExpired("target", timeout)
                return 0

            def kill(self):
                self.killed = True

        taskkill_timeouts = []

        def hanging_taskkill(*_args, timeout, **_kwargs):
            taskkill_timeouts.append(timeout)
            raise subprocess.TimeoutExpired("taskkill", timeout)

        process = Process()
        with (
            mock.patch.object(self.runner.os, "name", "nt"),
            mock.patch.object(self.runner.subprocess, "run", side_effect=hanging_taskkill),
        ):
            self.runner._terminate_tree(process, NoJob(), 124)

        self.assertEqual([2], taskkill_timeouts)
        self.assertTrue(process.killed)

    def test_windows_job_configuration_error_closes_created_handle(self):
        class Function:
            def __init__(self, implementation):
                self.implementation = implementation

            def __call__(self, *args):
                return self.implementation(*args)

        closed_handles = []
        kernel32 = type("Kernel32", (), {})()
        kernel32.CreateJobObjectW = Function(lambda *_args: 99)
        kernel32.SetInformationJobObject = Function(
            lambda *_args: (_ for _ in ()).throw(OSError("injected configuration failure"))
        )
        kernel32.AssignProcessToJobObject = Function(lambda *_args: 1)
        kernel32.TerminateJobObject = Function(lambda *_args: 1)
        kernel32.CloseHandle = Function(lambda handle: closed_handles.append(handle))
        process = type("Process", (), {"_handle": 101})()

        with (
            mock.patch.object(self.runner.os, "name", "nt"),
            mock.patch.object(ctypes, "WinDLL", return_value=kernel32, create=True),
        ):
            with self.assertRaisesRegex(OSError, "injected configuration failure"):
                self.runner._WindowsJob(process)

        self.assertEqual([99], closed_handles)

    def test_windows_job_reports_failed_termination_for_fallback(self):
        job = self.runner._WindowsJob.__new__(self.runner._WindowsJob)
        job._handle = 99
        job._kernel32 = type(
            "Kernel32", (), {"TerminateJobObject": staticmethod(lambda *_args: 0)}
        )()

        self.assertFalse(job.terminate(124))

    def test_stdout_close_error_does_not_skip_job_close(self):
        class Reader:
            def join(self, timeout=None):
                return None

        class Output:
            def close(self):
                raise OSError("injected stdout close failure")

        class Job:
            closed = False

            def close(self):
                self.closed = True

        process = type("Process", (), {"stdout": Output()})()
        job = Job()

        with self.assertRaisesRegex(OSError, "injected stdout close failure"):
            self.runner._close_process_resources(process, Reader(), job)

        self.assertTrue(job.closed)

    def test_launcher_waits_for_json_payload_and_preserves_raw_output(self):
        child_source = (
            "import os, sys; os.write(sys.stdout.fileno(), b'\\xffraw'); sys.exit(7)"
        )
        process = subprocess.Popen(
            [sys.executable, "-I", "-c", self.runner._WINDOWS_LAUNCHER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        output, stderr = process.communicate(
            json.dumps([sys.executable, "-c", child_source]).encode("utf-8") + b"\n",
            timeout=3,
        )

        status, raw_output = output.split(b"\n", 1)
        self.assertEqual({"ok": True}, json.loads(status.decode("utf-8")))
        self.assertEqual(b"\xffraw", raw_output)
        self.assertEqual(b"", stderr)
        self.assertEqual(7, process.returncode)

    def test_launcher_without_payload_never_executes_user_command(self):
        marker = self.workspace / "must-not-exist"
        process = subprocess.Popen(
            [sys.executable, "-I", "-c", self.runner._WINDOWS_LAUNCHER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "HARNESS_TEST_MARKER": str(marker)},
        )

        output, stderr = process.communicate(b"", timeout=3)

        self.assertNotEqual(0, process.returncode)
        self.assertFalse(marker.exists())
        self.assertEqual(b"", stderr)
        self.assertEqual({"ok": False, "error": "missing payload"}, json.loads(output))

    def test_windows_job_failure_sends_no_launcher_payload(self):
        class Input:
            def __init__(self):
                self.payload = b""
                self.closed = False

            def write(self, data):
                self.payload += data

            def flush(self):
                return None

            def close(self):
                self.closed = True

        class Output:
            closed = False

            def close(self):
                self.closed = True

        class Launcher:
            pid = 2026
            returncode = 2

            def __init__(self):
                self.stdin = Input()
                self.stdout = Output()
                self.killed = False

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                self.killed = True

        launcher = Launcher()
        with (
            mock.patch.object(self.runner.subprocess, "Popen", return_value=launcher),
            mock.patch.object(
                self.runner, "_WindowsJob", side_effect=OSError("job assignment failed")
            ),
        ):
            with self.assertRaisesRegex(OSError, "job assignment failed"):
                self.runner._start_windows_process(
                    [sys.executable, "-c", "raise RuntimeError('must not execute')"],
                    self.workspace,
                    time.monotonic() + 1,
                )

        self.assertEqual(b"", launcher.stdin.payload)
        self.assertTrue(launcher.stdin.closed)
        self.assertTrue(launcher.stdout.closed)

    def test_windows_handshake_write_and_ack_obey_run_deadline(self):
        real_popen = subprocess.Popen

        for drains_payload in (True, False):
            processes = []
            jobs = []
            results = []
            errors = []

            class Job:
                def __init__(self, process):
                    self.process = process
                    self.closed = False
                    jobs.append(self)

                def terminate(self, _returncode):
                    if self.process.poll() is None:
                        self.process.kill()
                    return True

                def close(self):
                    self.closed = True

            def start_stalled_launcher(*_args, **_kwargs):
                prefix = "import sys; sys.stdin.buffer.readline(); " if drains_payload else ""
                process = real_popen(
                    [sys.executable, "-c", prefix + "import time; time.sleep(30)"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                processes.append(process)
                return process

            def invoke():
                try:
                    results.append(
                        self.runner.run_bounded(
                            [sys.executable, "x" * 200_000],
                            self.workspace,
                            self.workspace / f"stall-{drains_payload}.log",
                            timeout_seconds=0.05,
                        )
                    )
                except BaseException as exc:
                    errors.append(exc)

            with (
                mock.patch.object(self.runner.os, "name", "nt"),
                mock.patch.object(
                    self.runner,
                    "Path",
                    side_effect=lambda value: value if isinstance(value, Path) else Path(value),
                ),
                mock.patch.object(
                    self.runner.subprocess, "Popen", side_effect=start_stalled_launcher
                ),
                mock.patch.object(self.runner, "_WindowsJob", Job),
            ):
                worker = threading.Thread(target=invoke)
                worker.start()
                worker.join(timeout=0.3)
                completed_within_bound = not worker.is_alive()
                if worker.is_alive() and processes[0].poll() is None:
                    processes[0].kill()
                worker.join(timeout=2)

            with self.subTest(drains_payload=drains_payload):
                self.assertTrue(completed_within_bound)
                self.assertEqual([], errors)
                self.assertEqual("timeout", results[0].reason)
                self.assertEqual(124, results[0].returncode)
                self.assertEqual(b"", (self.workspace / f"stall-{drains_payload}.log").read_bytes())
                self.assertTrue(jobs[0].closed)
                self.assertTrue(processes[0].stdin.closed)
                self.assertTrue(processes[0].stdout.closed)

    def test_windows_handshake_event_creation_failure_is_cleaned(self):
        def fail_event():
            raise RuntimeError("cannot create handshake event")

        self.assert_handshake_setup_failure_is_cleaned(
            "Event", fail_event, "cannot create handshake event"
        )

    def test_windows_handshake_thread_creation_failure_is_cleaned(self):
        def fail_thread(**_kwargs):
            raise RuntimeError("cannot create handshake thread")

        self.assert_handshake_setup_failure_is_cleaned(
            "Thread", fail_thread, "cannot create handshake thread"
        )

    def test_windows_handshake_thread_start_failure_is_cleaned(self):
        class FailingStartThread:
            ident = None

            def __init__(self, **_kwargs):
                return None

            def start(self):
                raise RuntimeError("cannot start handshake thread")

            def join(self, timeout=None):
                return None

        self.assert_handshake_setup_failure_is_cleaned(
            "Thread", FailingStartThread, "cannot start handshake thread"
        )

    def test_short_raw_writes_are_retried_without_losing_bytes(self):
        class ShortLog:
            def __init__(self):
                self.data = bytearray()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def write(self, data):
                count = min(2, len(data))
                self.data.extend(data[:count])
                return count

        log = ShortLog()
        with mock.patch.object(self.runner.Path, "open", return_value=log):
            result = self.runner.run_bounded(
                [sys.executable, "-c", "import os; os.write(1, b'abcde')"],
                self.workspace,
                self.workspace / "ignored.log",
            )

        self.assertEqual(b"abcde", bytes(log.data))
        self.assertEqual(5, result.bytes_written)
        self.assertEqual("exit", result.reason)
        self.assertFalse(result.truncated)

    def test_reader_thread_start_failure_cleans_up_spawned_process(self):
        class FailingThread:
            def __init__(self, **_kwargs):
                return None

            def start(self):
                raise RuntimeError("cannot start new thread")

            def join(self, timeout=None):
                return None

        processes = []
        real_popen = subprocess.Popen
        real_thread = threading.Thread
        thread_names = []

        def create_thread(**kwargs):
            thread_names.append(kwargs.get("name"))
            if kwargs.get("name") == "harness-output":
                return FailingThread(**kwargs)
            return real_thread(**kwargs)

        def start_real_process(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process

        try:
            with (
                mock.patch.object(
                    self.runner.subprocess, "Popen", side_effect=start_real_process
                ),
                mock.patch.object(self.runner.threading, "Thread", side_effect=create_thread),
            ):
                with self.assertRaisesRegex(RuntimeError, "cannot start new thread"):
                    self.run_python("import time; time.sleep(30)")

            self.assertIn("harness-output", thread_names)
            if os.name == "nt":
                self.assertEqual(["harness-windows-launch", "harness-output"], thread_names)
            self.assertEqual(1, len(processes))
            self.assertIsNotNone(processes[0].poll())
            self.assertTrue(processes[0].stdout.closed)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if not process.stdout.closed:
                    process.stdout.close()

    def test_reader_thread_creation_failure_cleans_up_spawned_process(self):
        class FailingThread:
            def __init__(self, **_kwargs):
                raise RuntimeError("cannot create new thread")

        processes = []
        real_popen = subprocess.Popen
        real_thread = threading.Thread
        thread_names = []

        def create_thread(**kwargs):
            thread_names.append(kwargs.get("name"))
            if kwargs.get("name") == "harness-output":
                return FailingThread(**kwargs)
            return real_thread(**kwargs)

        def start_real_process(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process

        try:
            with (
                mock.patch.object(
                    self.runner.subprocess, "Popen", side_effect=start_real_process
                ),
                mock.patch.object(self.runner.threading, "Thread", side_effect=create_thread),
            ):
                with self.assertRaisesRegex(RuntimeError, "cannot create new thread"):
                    self.run_python(
                        "import time; time.sleep(30)", name="thread-create.log"
                    )

            self.assertIn("harness-output", thread_names)
            if os.name == "nt":
                self.assertEqual(["harness-windows-launch", "harness-output"], thread_names)
            self.assertEqual(1, len(processes))
            self.assertIsNotNone(processes[0].poll())
            self.assertTrue(processes[0].stdout.closed)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if not process.stdout.closed:
                    process.stdout.close()


if __name__ == "__main__":
    unittest.main()
