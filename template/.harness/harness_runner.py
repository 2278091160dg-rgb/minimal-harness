#!/usr/bin/env python3
"""Run verification commands with bounded time and output."""

from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Union


PathLike = Union[str, os.PathLike]
_CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)


_WINDOWS_LAUNCHER = r"""
import json
import os
import subprocess
import sys


def send_status(value):
    sys.stdout.buffer.write(json.dumps(value, ensure_ascii=True).encode("ascii") + b"\n")
    sys.stdout.buffer.flush()


payload = sys.stdin.buffer.readline()
if not payload:
    send_status({"ok": False, "error": "missing payload"})
    raise SystemExit(2)
try:
    argv = json.loads(payload.decode("utf-8"))
    if not isinstance(argv, list) or not argv or not all(
        isinstance(item, str) and item for item in argv
    ):
        raise ValueError("invalid argv")
except (UnicodeError, ValueError) as exc:
    send_status({"ok": False, "error": str(exc)})
    raise SystemExit(2)
try:
    child = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        bufsize=0,
    )
except OSError as exc:
    send_status({
        "ok": False,
        "errno": exc.errno,
        "strerror": exc.strerror or str(exc),
        "filename": exc.filename,
    })
    raise SystemExit(126)
send_status({"ok": True})
while True:
    chunk = child.stdout.read(64 * 1024)
    if not chunk:
        break
    os.write(sys.stdout.fileno(), chunk)
child.stdout.close()
raise SystemExit(child.wait())
"""


@dataclass(frozen=True)
class RunResult:
    returncode: int
    reason: str
    bytes_written: int
    truncated: bool


class _StartupTimeout(Exception):
    pass


class _WindowsJob:
    """Small Job Object wrapper that fails closed when assignment is unavailable."""

    def __init__(self, process: subprocess.Popen):
        self._handle = None
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]

        class BASIC_LIMITS(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class EXTENDED_LIMITS(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMITS),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
        ]
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            error = ctypes.get_last_error()
            raise OSError(error or 1, "CreateJobObjectW failed")
        limits = EXTENDED_LIMITS()
        limits.BasicLimitInformation.LimitFlags = 0x00002000
        try:
            configured = kernel32.SetInformationJobObject(
                handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            )
            assigned = configured and kernel32.AssignProcessToJobObject(
                handle, process._handle
            )
        except BaseException:
            kernel32.CloseHandle(handle)
            raise
        if not assigned:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(handle)
            raise OSError(error or 1, "AssignProcessToJobObject failed")
        self._handle = handle
        self._kernel32 = kernel32

    def terminate(self, returncode: int) -> bool:
        if self._handle is None:
            return False
        return bool(self._kernel32.TerminateJobObject(self._handle, returncode))

    def close(self) -> None:
        if self._handle is not None:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


def _validate(
    argv: Sequence[str], timeout_seconds: float, max_output_bytes: int
) -> None:
    if (
        isinstance(argv, (str, bytes))
        or not isinstance(argv, Sequence)
        or not argv
        or any(not isinstance(item, str) or not item for item in argv)
    ):
        raise ValueError("argv must be a non-empty sequence of non-empty strings")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("timeout_seconds must be a positive finite number")
    if (
        isinstance(max_output_bytes, bool)
        or not isinstance(max_output_bytes, int)
        or max_output_bytes <= 0
    ):
        raise ValueError("max_output_bytes must be a positive integer")


def _terminate_tree(
    process: subprocess.Popen, job: Optional[_WindowsJob], returncode: int
) -> None:
    if os.name == "nt":
        if job is None or not job.terminate(returncode):
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=2,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    time.sleep(0.1)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _stop_waiting_launcher(process: subprocess.Popen) -> None:
    try:
        process.stdin.close()
    except OSError:
        pass
    try:
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    finally:
        process.stdout.close()


def _close_windows_startup_resources(
    process: subprocess.Popen,
    job: _WindowsJob,
    handshake: Optional[threading.Thread],
) -> None:
    failure = None
    for resource in (job, process.stdout, process.stdin):
        try:
            if resource is not None:
                resource.close()
        except BaseException as exc:
            if failure is None:
                failure = exc
    try:
        if handshake is not None and handshake.ident is not None:
            handshake.join(timeout=2)
    except BaseException as exc:
        if failure is None:
            failure = exc
    if failure is not None:
        raise failure


def _start_windows_process(
    argv: Sequence[str], workspace: Path, deadline: float
) -> tuple[subprocess.Popen, _WindowsJob]:
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", _WINDOWS_LAUNCHER],
        cwd=str(workspace),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        creationflags=_CREATE_NEW_PROCESS_GROUP,
    )
    try:
        job = _WindowsJob(process)
    except BaseException:
        _stop_waiting_launcher(process)
        raise
    handshake = None
    try:
        handshake_done = threading.Event()
        handshake_result = []

        def exchange_payload() -> None:
            try:
                payload = json.dumps(list(argv), ensure_ascii=True).encode("utf-8") + b"\n"
                view = memoryview(payload)
                while view:
                    written = process.stdin.write(view)
                    if (
                        not isinstance(written, int)
                        or written <= 0
                        or written > len(view)
                    ):
                        raise OSError("Windows launcher payload write made no progress")
                    view = view[written:]
                process.stdin.flush()
                process.stdin.close()
                status_line = process.stdout.readline(65_537)
                if len(status_line) > 65_536 or not status_line.endswith(b"\n"):
                    raise OSError("invalid or oversized Windows launcher response")
                handshake_result.append(json.loads(status_line.decode("ascii")))
            except BaseException as exc:
                handshake_result.append(exc)
            finally:
                handshake_done.set()

        handshake = threading.Thread(
            target=exchange_payload, name="harness-windows-launch", daemon=True
        )
        handshake.start()
        remaining = max(0.0, deadline - time.monotonic())
        if not handshake_done.wait(remaining):
            raise _StartupTimeout()
        handshake.join()
        status = handshake_result[0]
        if isinstance(status, BaseException):
            raise status
        if status != {"ok": True}:
            if "errno" in status:
                raise OSError(
                    status["errno"], status.get("strerror"), status.get("filename")
                )
            raise OSError(status.get("error", "Windows launcher failed"))
    except BaseException:
        try:
            if process.poll() is None:
                _terminate_tree(process, job, 125)
        finally:
            _close_windows_startup_resources(process, job, handshake)
        raise
    return process, job


def _close_process_resources(
    process: subprocess.Popen, reader: threading.Thread, job: Optional[_WindowsJob]
) -> None:
    reader.join(timeout=2)
    failure = None
    try:
        if job is not None:
            job.close()
    except BaseException as exc:
        failure = exc
    try:
        if process.stdout is not None:
            process.stdout.close()
    except BaseException as exc:
        if failure is None:
            failure = exc
    reader.join(timeout=2)
    if failure is not None:
        raise failure


def run_bounded(
    argv: Sequence[str],
    workspace: PathLike,
    log_path: PathLike,
    *,
    timeout_seconds: float = 300,
    max_output_bytes: int = 10_485_760,
) -> RunResult:
    """Run argv without a shell and record at most max_output_bytes bytes."""
    _validate(argv, timeout_seconds, max_output_bytes)
    try:
        workspace_path = Path(workspace)
        output_path = Path(log_path)
    except TypeError as exc:
        raise ValueError("workspace and log_path must be filesystem paths") from exc
    bytes_written = 0
    truncated = False
    limit_reached = threading.Event()
    reader_done = threading.Event()
    reader_errors = []
    process: Optional[subprocess.Popen] = None
    job: Optional[_WindowsJob] = None

    with output_path.open("xb", buffering=0) as log_file:
        started = time.monotonic()
        if os.name == "nt":
            deadline = started + timeout_seconds
            try:
                process, job = _start_windows_process(argv, workspace_path, deadline)
            except _StartupTimeout:
                return RunResult(124, "timeout", 0, False)
        else:
            process = subprocess.Popen(
                list(argv),
                cwd=str(workspace_path),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
                start_new_session=True,
            )
            try:
                job = _WindowsJob(process)
            except BaseException:
                _terminate_tree(process, None, 125)
                process.stdout.close()
                raise

        def drain_output() -> None:
            nonlocal bytes_written, truncated
            try:
                while True:
                    chunk = process.stdout.read1(64 * 1024)
                    if not chunk:
                        break
                    remaining = max_output_bytes - bytes_written
                    if remaining:
                        pending = memoryview(chunk)[:remaining]
                        while pending:
                            written = log_file.write(pending)
                            if (
                                not isinstance(written, int)
                                or written <= 0
                                or written > len(pending)
                            ):
                                raise OSError("log write made no progress")
                            bytes_written += written
                            pending = pending[written:]
                    if len(chunk) > remaining:
                        truncated = True
                        limit_reached.set()
            except BaseException as exc:
                reader_errors.append(exc)
            finally:
                reader_done.set()

        try:
            reader = threading.Thread(
                target=drain_output, name="harness-output", daemon=True
            )
            reader.start()
        except BaseException as exc:
            try:
                _terminate_tree(process, job, 130 if isinstance(exc, KeyboardInterrupt) else 125)
            finally:
                try:
                    if job is not None:
                        job.close()
                finally:
                    process.stdout.close()
            if isinstance(exc, KeyboardInterrupt):
                return RunResult(130, "interrupted", 0, False)
            raise
        reason = "exit"
        synthetic_returncode = None
        try:
            while True:
                if reader_errors:
                    raise reader_errors[0]
                if limit_reached.is_set():
                    reason = "output_limit"
                    synthetic_returncode = 125
                    break
                if time.monotonic() >= started + timeout_seconds:
                    reason = "timeout"
                    synthetic_returncode = 124
                    break
                if process.poll() is not None and reader_done.is_set():
                    break
                # Condition.wait cleanup can mask KeyboardInterrupt on Windows.
                time.sleep(0.01)
        except KeyboardInterrupt:
            reason = "interrupted"
            synthetic_returncode = 130
        except BaseException:
            try:
                _terminate_tree(process, job, 125)
            finally:
                _close_process_resources(process, reader, job)
            raise

        try:
            if synthetic_returncode is not None:
                _terminate_tree(process, job, synthetic_returncode)
            else:
                process.wait()
        finally:
            _close_process_resources(process, reader, job)
        if reader_errors:
            raise reader_errors[0]

    return RunResult(
        process.returncode if synthetic_returncode is None else synthetic_returncode,
        reason,
        bytes_written,
        truncated,
    )
