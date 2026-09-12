import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "template" / ".harness" / "harness.py"


def base_config():
    return {
        "schema_version": 2,
        "project_name": "Test project",
        "commands": {"setup": None, "start": None, "check": [sys.executable, "-c", "print('ok')"]},
        "policy": {
            "schema_version": 2,
            "max_consecutive_failures": 3,
            "allowed_paths": ["src/**", "tests/**", ".harness/**"],
            "approval_required_operations": ["delete files", "git commit or push"],
            "require_git_for_completion": False,
        },
    }


def base_tasks(check_type="command", command=None):
    acceptance = {
        "id": "check-1",
        "type": check_type,
        "instruction": "Prove the behavior",
        "status": "not_run",
        "consecutive_failures": 0,
        "latest_evidence": None,
    }
    if check_type == "command":
        acceptance["command"] = command or [sys.executable, "-c", "print('verified')"]
    else:
        acceptance["steps"] = ["Perform the action", "Observe the result"]
    return {
        "schema_version": 2,
        "current_task_id": None,
        "tasks": [
            {
                "id": "task-1",
                "title": "First task",
                "status": "pending",
                "acceptance": [acceptance],
            },
            {
                "id": "task-2",
                "title": "Second task",
                "status": "pending",
                "acceptance": [
                    {
                        "id": "check-2",
                        "type": "manual",
                        "instruction": "Inspect it",
                        "steps": ["Inspect the result"],
                        "status": "not_run",
                        "consecutive_failures": 0,
                        "latest_evidence": None,
                    }
                ],
            },
        ],
    }


def v2_config():
    value = base_config()
    value["policy"]["require_git_for_completion"] = True
    return value


def v2_tasks(check_type="command", command=None):
    return base_tasks(check_type=check_type, command=command)


def v1_config():
    value = base_config()
    value["schema_version"] = 1
    value["policy"].pop("require_git_for_completion")
    value["policy"].pop("schema_version")
    return value


def v1_tasks(check_type="command", command=None):
    value = base_tasks(check_type=check_type, command=command)
    value["schema_version"] = 1
    return value


def unavailable_git_baseline():
    return {
        "version": 2,
        "captured_at": "2026-09-12T00:00:00Z",
        "available": False,
        "branch": None,
        "head": None,
        "dirty_paths": [],
        "worktree_fingerprints": {},
        "index_fingerprints": {},
    }


class HarnessCliTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.harness_dir = self.workspace / ".harness"
        self.harness_dir.mkdir()
        self.write_json("config.json", base_config())
        self.write_json("tasks.json", base_tasks())

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_json(self, name, value):
        (self.harness_dir / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def read_tasks(self):
        return json.loads((self.harness_dir / "tasks.json").read_text(encoding="utf-8"))

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace", str(self.workspace), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def initialize_git_repository(self):
        commands = [
            ["git", "init"],
            ["git", "config", "user.email", "harness@example.test"],
            ["git", "config", "user.name", "Harness Test"],
            ["git", "add", "."],
            ["git", "commit", "-m", "initial"],
        ]
        for command in commands:
            subprocess.run(command, cwd=self.workspace, check=True, capture_output=True, text=True)

    def test_doctor_accepts_valid_configuration(self):
        result = self.run_cli("doctor")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("configuration valid", result.stdout)

    def test_doctor_rejects_unknown_schema(self):
        config = base_config()
        config["schema_version"] = 99
        self.write_json("config.json", config)

        result = self.run_cli("doctor")

        self.assertEqual(2, result.returncode)
        self.assertIn("schema_version", result.stderr)

    def test_v2_doctor_rejects_active_task_without_frozen_baselines(self):
        self.write_json("config.json", v2_config())
        tasks = v2_tasks(check_type="manual")
        tasks["current_task_id"] = "task-1"
        tasks["tasks"][0]["status"] = "in_progress"
        tasks["tasks"][0]["started_at"] = "2026-09-12T00:00:00Z"
        tasks["tasks"][0]["policy_baseline"] = dict(v2_config()["policy"])
        self.write_json("tasks.json", tasks)

        result = self.run_cli("doctor")

        self.assertEqual(2, result.returncode)
        self.assertIn("git_baseline", result.stderr)

    def test_v2_doctor_rejects_impossible_blocked_state(self):
        self.write_json("config.json", v2_config())
        tasks = v2_tasks(check_type="manual")
        task = tasks["tasks"][0]
        tasks["current_task_id"] = "task-1"
        task["status"] = "blocked"
        task["started_at"] = "2026-09-12T00:00:00Z"
        task["blocked_at"] = "2026-09-12T00:01:00Z"
        task["block_reason"] = "forged"
        task["git_baseline"] = {
            "version": 2,
            "captured_at": "2026-09-12T00:00:00Z",
            "available": False,
            "branch": None,
            "head": None,
            "dirty_paths": [],
            "worktree_fingerprints": {},
            "index_fingerprints": {},
        }
        task["policy_baseline"] = dict(v2_config()["policy"])
        self.write_json("tasks.json", tasks)

        result = self.run_cli("doctor")

        self.assertEqual(2, result.returncode)
        self.assertIn("failure limit", result.stderr)

    def test_migrate_dry_run_is_read_only_then_upgrades_pending_v1_state(self):
        self.write_json("config.json", v1_config())
        self.write_json("tasks.json", v1_tasks())
        before_config = (self.harness_dir / "config.json").read_bytes()
        before_tasks = (self.harness_dir / "tasks.json").read_bytes()

        dry_run = self.run_cli("migrate", "--dry-run")

        self.assertEqual(0, dry_run.returncode, dry_run.stderr)
        self.assertIn("would migrate", dry_run.stdout)
        self.assertEqual(before_config, (self.harness_dir / "config.json").read_bytes())
        self.assertEqual(before_tasks, (self.harness_dir / "tasks.json").read_bytes())

        migrated = self.run_cli("migrate")

        self.assertEqual(0, migrated.returncode, migrated.stderr)
        self.assertEqual(2, json.loads((self.harness_dir / "config.json").read_text())["schema_version"])
        self.assertEqual(2, self.read_tasks()["schema_version"])
        self.assertTrue(list((self.harness_dir / "migrations").glob("*/manifest.json")))
        repeated = self.run_cli("migrate")
        self.assertEqual(0, repeated.returncode, repeated.stderr)
        self.assertIn("already schema v2", repeated.stdout)

    def test_migrate_active_v1_state_requires_note_and_rebaselines(self):
        self.write_json("config.json", v1_config())
        tasks = v1_tasks(check_type="manual")
        tasks["current_task_id"] = "task-1"
        tasks["tasks"][0]["status"] = "in_progress"
        tasks["tasks"][0]["started_at"] = "2026-09-12T00:00:00Z"
        self.write_json("tasks.json", tasks)

        rejected = self.run_cli("migrate")
        accepted = self.run_cli("migrate", "--note", "acknowledge v1 baseline discontinuity")

        self.assertEqual(2, rejected.returncode)
        self.assertIn("--note", rejected.stderr)
        self.assertEqual(0, accepted.returncode, accepted.stderr)
        task = self.read_tasks()["tasks"][0]
        self.assertEqual(2, task["git_baseline"]["version"])
        self.assertEqual(2, task["policy_baseline"]["schema_version"])
        self.assertEqual("acknowledge v1 baseline discontinuity", task["migration_history"][-1]["note"])

    def test_doctor_rejects_task_id_that_can_escape_evidence_directory(self):
        tasks = base_tasks(check_type="manual")
        tasks["tasks"][0]["id"] = "../../../escape"
        self.write_json("tasks.json", tasks)

        result = self.run_cli("doctor")

        self.assertEqual(2, result.returncode)
        self.assertIn("safe identifier", result.stderr)

    def test_doctor_rejects_unsafe_acceptance_id(self):
        tasks = base_tasks(check_type="manual")
        tasks["tasks"][0]["acceptance"][0]["id"] = "folder/check"
        self.write_json("tasks.json", tasks)

        result = self.run_cli("doctor")

        self.assertEqual(2, result.returncode)
        self.assertIn("safe identifier", result.stderr)

    def test_doctor_rejects_current_task_that_is_not_active_or_blocked(self):
        tasks = base_tasks()
        tasks["current_task_id"] = "task-1"
        self.write_json("tasks.json", tasks)

        result = self.run_cli("doctor")

        self.assertEqual(2, result.returncode)
        self.assertIn("current_task_id", result.stderr)

    def test_doctor_rejects_done_task_with_unpassed_acceptance(self):
        tasks = base_tasks(check_type="manual")
        tasks["tasks"][0]["status"] = "done"
        tasks["tasks"][0]["completed_at"] = "2026-01-01T00:00:00Z"
        self.write_json("tasks.json", tasks)

        result = self.run_cli("doctor")

        self.assertEqual(2, result.returncode)
        self.assertIn("done task", result.stderr)

    def test_doctor_rejects_blocked_task_that_cannot_be_unblocked(self):
        tasks = base_tasks(check_type="manual")
        task = tasks["tasks"][0]
        task["status"] = "blocked"
        task["started_at"] = "2026-09-12T00:00:00Z"
        task["blocked_at"] = "2026-09-12T00:01:00Z"
        task["block_reason"] = "failure limit"
        task["policy_baseline"] = dict(base_config()["policy"])
        task["git_baseline"] = unavailable_git_baseline()
        task["acceptance"][0]["status"] = "failed"
        task["acceptance"][0]["consecutive_failures"] = 3
        self.write_json("tasks.json", tasks)

        result = self.run_cli("doctor")

        self.assertEqual(2, result.returncode)
        self.assertIn("blocked task", result.stderr)

    def test_doctor_warns_instead_of_crashing_when_git_is_not_installed(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace", str(self.workspace), "doctor"],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "PATH": ""},
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Git unavailable", result.stdout)

    def test_next_sets_only_the_first_pending_task_in_progress(self):
        result = self.run_cli("next")

        self.assertEqual(0, result.returncode, result.stderr)
        tasks = self.read_tasks()
        self.assertEqual("task-1", tasks["current_task_id"])
        self.assertEqual(["in_progress", "pending"], [task["status"] for task in tasks["tasks"]])
        self.assertTrue((self.harness_dir / "HANDOFF.md").exists())

        second = self.run_cli("next")
        self.assertEqual(1, second.returncode)
        self.assertIn("already active", second.stderr)

    def test_status_reports_current_task_and_acceptance(self):
        self.assertEqual(0, self.run_cli("next").returncode)

        result = self.run_cli("status")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("task-1", result.stdout)
        self.assertIn("check-1", result.stdout)
        self.assertIn("not_run", result.stdout)

    def test_run_executes_configured_command_without_a_shell(self):
        result = self.run_cli("run", "check")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_run_reports_missing_executable_as_configuration_error(self):
        config = base_config()
        config["commands"]["check"] = ["definitely-not-a-real-harness-command"]
        self.write_json("config.json", config)

        result = self.run_cli("run", "check")

        self.assertEqual(2, result.returncode)
        self.assertIn("executable not found", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_doctor_rejects_existing_but_non_executable_command_path(self):
        command_path = self.workspace / "tools" / "check"
        command_path.parent.mkdir()
        command_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        command_path.chmod(0o644)
        config = base_config()
        config["commands"]["check"] = ["./tools/check"]
        self.write_json("config.json", config)

        result = self.run_cli("doctor")

        self.assertEqual(2, result.returncode)
        self.assertIn("executable not found", result.stderr)

    def test_doctor_rejects_missing_acceptance_command_executable(self):
        tasks = base_tasks(command=["definitely-not-a-real-acceptance-command"])
        self.write_json("tasks.json", tasks)

        result = self.run_cli("doctor")

        self.assertEqual(2, result.returncode)
        self.assertIn("acceptance task-1/check-1 executable not found", result.stderr)

    def test_run_start_streams_output_before_long_running_process_exits(self):
        config = base_config()
        config["commands"]["start"] = [
            sys.executable,
            "-u",
            "-c",
            "import time; print('ready', flush=True); time.sleep(1)",
        ]
        self.write_json("config.json", config)
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT), "--workspace", str(self.workspace), "run", "start"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        lines = queue.Queue()
        reader = threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True)
        reader.start()
        try:
            try:
                first_line = lines.get(timeout=0.4)
            except queue.Empty:
                self.fail("start output was buffered until the process exited")
            self.assertEqual("ready", first_line.strip())
            self.assertIsNone(process.poll(), "start process should still be running when output is streamed")
        finally:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=3)

    def test_verify_passes_command_check_and_writes_evidence_and_log(self):
        self.assertEqual(0, self.run_cli("next").returncode)

        result = self.run_cli("verify")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("verified", result.stdout)
        tasks = self.read_tasks()
        check = tasks["tasks"][0]["acceptance"][0]
        self.assertEqual("passed", check["status"])
        evidence_path = self.workspace / check["latest_evidence"]
        self.assertTrue(evidence_path.exists())
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(0, evidence["exit_code"])
        self.assertEqual("command", evidence["method"])
        self.assertEqual("passed", evidence["result"])
        self.assertEqual(2, evidence["schema_version"])
        self.assertEqual("file", evidence["log"]["type"])
        log_path = self.workspace / evidence["log"]["path"]
        self.assertIn("verified", log_path.read_text(encoding="utf-8"))
        self.assertEqual(evidence["log"]["sha256"], hashlib.sha256(log_path.read_bytes()).hexdigest())

    def test_third_consecutive_command_failure_blocks_task_and_preserves_evidence(self):
        tasks = base_tasks(command=[sys.executable, "-c", "print('broken'); raise SystemExit(7)"])
        self.write_json("tasks.json", tasks)
        self.assertEqual(0, self.run_cli("next").returncode)

        results = [self.run_cli("verify") for _ in range(3)]

        self.assertEqual([1, 1, 1], [result.returncode for result in results])
        tasks = self.read_tasks()
        task = tasks["tasks"][0]
        check = task["acceptance"][0]
        self.assertEqual("blocked", task["status"])
        self.assertEqual("task-1", tasks["current_task_id"])
        self.assertEqual(3, check["consecutive_failures"])
        evidence_files = list((self.harness_dir / "evidence" / "task-1").glob("*.json"))
        self.assertEqual(3, len(evidence_files))
        self.assertEqual(1, self.run_cli("next").returncode)

    def test_record_browser_result_requires_real_in_workspace_artifact(self):
        self.write_json("tasks.json", base_tasks(check_type="browser"))
        self.assertEqual(0, self.run_cli("next").returncode)
        outside = Path(self.temp_dir.name).parent / "outside-harness-proof.txt"
        outside.write_text("proof", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))

        rejected = self.run_cli(
            "record", "task-1", "check-1", "--result", "passed", "--summary", "clicked",
            "--tool", "browser",
            "--artifact", str(outside),
        )

        self.assertEqual(2, rejected.returncode)
        self.assertIn("inside the workspace", rejected.stderr)
        self.assertFalse((self.harness_dir / "evidence").exists())

        screenshot = self.workspace / "proof" / "todo.png"
        screenshot.parent.mkdir()
        screenshot.write_bytes(b"image evidence")
        accepted = self.run_cli(
            "record", "task-1", "check-1", "--result", "passed", "--summary", "button added item",
            "--tool", "browser", "--artifact", "proof/todo.png",
        )
        self.assertEqual(0, accepted.returncode, accepted.stderr)
        check = self.read_tasks()["tasks"][0]["acceptance"][0]
        evidence = json.loads((self.workspace / check["latest_evidence"]).read_text(encoding="utf-8"))
        self.assertEqual("proof/todo.png", evidence["artifacts"][0]["path"])
        self.assertEqual("file", evidence["artifacts"][0]["type"])

    def test_record_browser_pass_requires_tool_and_artifact(self):
        self.write_json("tasks.json", base_tasks(check_type="browser"))
        self.assertEqual(0, self.run_cli("next").returncode)
        proof = self.workspace / "proof.png"
        proof.write_bytes(b"proof")

        without_tool = self.run_cli(
            "record", "task-1", "check-1", "--result", "passed", "--summary", "observed",
            "--artifact", "proof.png",
        )
        without_artifact = self.run_cli(
            "record", "task-1", "check-1", "--result", "passed", "--summary", "observed",
            "--tool", "browser",
        )

        self.assertEqual(2, without_tool.returncode)
        self.assertIn("tool", without_tool.stderr)
        self.assertEqual(2, without_artifact.returncode)
        self.assertIn("artifact", without_artifact.stderr)
        self.assertFalse((self.harness_dir / "evidence").exists())

    def test_record_rejects_directory_artifact(self):
        self.write_json("tasks.json", base_tasks(check_type="browser"))
        self.assertEqual(0, self.run_cli("next").returncode)
        (self.workspace / "proof-dir").mkdir()

        result = self.run_cli(
            "record", "task-1", "check-1", "--result", "passed", "--summary", "observed",
            "--tool", "browser", "--artifact", "proof-dir",
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("regular file", result.stderr)

    def test_record_rejects_symlink_artifact_even_when_target_is_inside_workspace(self):
        self.write_json("tasks.json", base_tasks(check_type="browser"))
        self.assertEqual(0, self.run_cli("next").returncode)
        target = self.workspace / "proof-target.png"
        target.write_bytes(b"proof")
        (self.workspace / "proof-link.png").symlink_to(target)

        result = self.run_cli(
            "record", "task-1", "check-1", "--result", "passed", "--summary", "observed",
            "--tool", "browser", "--artifact", "proof-link.png",
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("non-symlink", result.stderr)

    def test_complete_rejects_tampered_artifact_payload(self):
        self.write_json("tasks.json", base_tasks(check_type="browser"))
        self.assertEqual(0, self.run_cli("next").returncode)
        proof = self.workspace / "proof.png"
        proof.write_bytes(b"original proof")
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "observed",
                "--tool", "browser", "--artifact", "proof.png",
            ).returncode,
        )
        proof.write_bytes(b"tampered proof")

        result = self.run_cli("complete", "task-1")

        self.assertEqual(1, result.returncode)
        self.assertIn("artifact digest", result.stderr)

    def test_complete_rejects_tampered_command_log(self):
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(0, self.run_cli("verify").returncode)
        check = self.read_tasks()["tasks"][0]["acceptance"][0]
        evidence = json.loads((self.workspace / check["latest_evidence"]).read_text())
        (self.workspace / evidence["log"]["path"]).write_text("tampered\n", encoding="utf-8")

        result = self.run_cli("complete", "task-1")

        self.assertEqual(1, result.returncode)
        self.assertIn("log digest", result.stderr)

    def test_record_rejects_symlinked_evidence_root_before_external_write(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.assertEqual(0, self.run_cli("next").returncode)
        external = Path(self.temp_dir.name).parent / f"external-evidence-{os.getpid()}"
        external.mkdir(exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(external, ignore_errors=True))
        (self.harness_dir / "evidence").symlink_to(external, target_is_directory=True)

        result = self.run_cli(
            "record", "task-1", "check-1", "--result", "passed", "--summary", "observed",
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("symbolic link", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual([], list(external.rglob("*")))

    def test_unverified_result_prevents_completion(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.assertEqual(0, self.run_cli("next").returncode)
        recorded = self.run_cli(
            "record", "task-1", "check-1", "--result", "unverified", "--summary", "browser unavailable",
        )
        self.assertEqual(1, recorded.returncode)

        completed = self.run_cli("complete", "task-1")

        self.assertEqual(1, completed.returncode)
        self.assertIn("not passed", completed.stderr)
        self.assertEqual("in_progress", self.read_tasks()["tasks"][0]["status"])

    def test_complete_rejects_forged_passed_state_without_evidence(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.assertEqual(0, self.run_cli("next").returncode)
        tasks = self.read_tasks()
        check = tasks["tasks"][0]["acceptance"][0]
        check["status"] = "passed"
        check["latest_evidence"] = None
        self.write_json("tasks.json", tasks)

        result = self.run_cli("complete", "task-1")

        self.assertEqual(1, result.returncode)
        self.assertIn("valid evidence", result.stderr)
        self.assertEqual("in_progress", self.read_tasks()["tasks"][0]["status"])

    def test_deleted_evidence_fails_doctor_and_completion(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "verified",
            ).returncode,
        )
        tasks = self.read_tasks()
        check = tasks["tasks"][0]["acceptance"][0]
        (self.workspace / check["latest_evidence"]).unlink()

        doctor = self.run_cli("doctor")
        completed = self.run_cli("complete", "task-1")

        self.assertEqual(2, doctor.returncode)
        self.assertIn("evidence file does not exist", doctor.stderr)
        self.assertEqual(1, completed.returncode)
        self.assertIn("valid evidence", completed.stderr)

    def test_tampered_evidence_fails_integrity_check(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "verified",
            ).returncode,
        )
        tasks = self.read_tasks()
        check = tasks["tasks"][0]["acceptance"][0]
        evidence_path = self.workspace / check["latest_evidence"]
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["summary"] = "changed after verification"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

        result = self.run_cli("complete", "task-1")

        self.assertEqual(1, result.returncode)
        self.assertIn("digest does not match", result.stderr)

    def test_unblock_resets_counter_but_preserves_failure_evidence(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.assertEqual(0, self.run_cli("next").returncode)
        for attempt in range(3):
            result = self.run_cli(
                "record", "task-1", "check-1", "--result", "failed", "--summary", f"attempt {attempt + 1}",
            )
            self.assertEqual(1, result.returncode)

        result = self.run_cli("unblock", "task-1", "--note", "human fixed the environment")

        self.assertEqual(0, result.returncode, result.stderr)
        task = self.read_tasks()["tasks"][0]
        self.assertEqual("in_progress", task["status"])
        self.assertEqual(0, task["acceptance"][0]["consecutive_failures"])
        self.assertEqual("human fixed the environment", task["unblock_history"][-1]["note"])
        self.assertEqual(3, len(list((self.harness_dir / "evidence" / "task-1").glob("*.json"))))

    def test_complete_marks_fully_verified_task_done(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "observed expected result",
            ).returncode,
        )

        result = self.run_cli("complete", "task-1")

        self.assertEqual(0, result.returncode, result.stderr)
        tasks = self.read_tasks()
        self.assertIsNone(tasks["current_task_id"])
        self.assertEqual("done", tasks["tasks"][0]["status"])
        handoff = (self.harness_dir / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("task-1", handoff)
        self.assertIn("python3 .harness/harness.py next", handoff)

    def test_handoff_includes_latest_evidence_summary_time_and_path(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record",
                "task-1",
                "check-1",
                "--result",
                "passed",
                "--summary",
                "observed the expected browser state",
            ).returncode,
        )
        check = self.read_tasks()["tasks"][0]["acceptance"][0]

        handoff = (self.harness_dir / "HANDOFF.md").read_text(encoding="utf-8")

        self.assertIn("observed the expected browser state", handoff)
        self.assertIn(check["latest_evidence"], handoff)
        self.assertIn("Evidence time:", handoff)

    def test_handoff_preserves_historical_failure_after_later_pass(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            1,
            self.run_cli(
                "record",
                "task-1",
                "check-1",
                "--result",
                "failed",
                "--summary",
                "button did not respond",
            ).returncode,
        )
        self.assertEqual(
            0,
            self.run_cli(
                "record",
                "task-1",
                "check-1",
                "--result",
                "passed",
                "--summary",
                "button works after the fix",
            ).returncode,
        )

        handoff = (self.harness_dir / "HANDOFF.md").read_text(encoding="utf-8")

        self.assertIn("button did not respond", handoff)
        self.assertIn("Historical failure", handoff)

    def test_complete_rejects_new_git_changes_outside_allowed_paths(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.initialize_git_repository()
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "verified",
            ).returncode,
        )
        (self.workspace / "outside.txt").write_text("unexpected", encoding="utf-8")

        result = self.run_cli("complete", "task-1")

        self.assertEqual(1, result.returncode)
        self.assertIn("outside allowed_paths", result.stderr)
        self.assertIn("outside.txt", result.stderr)

    def test_complete_fails_closed_when_git_status_fails(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.initialize_git_repository()
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "verified",
            ).returncode,
        )
        (self.workspace / "outside.txt").write_text("unexpected", encoding="utf-8")
        (self.workspace / ".git" / "index").write_bytes(b"corrupt-index")

        result = self.run_cli("complete", "task-1")

        self.assertEqual(1, result.returncode)
        self.assertIn("git status failed", result.stderr.lower())
        self.assertEqual("in_progress", self.read_tasks()["tasks"][0]["status"])

    def test_complete_detects_staged_change_hidden_behind_preexisting_dirty_worktree(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        outside = self.workspace / "outside.txt"
        outside.write_text("committed base", encoding="utf-8")
        self.initialize_git_repository()
        outside.write_text("preexisting worktree", encoding="utf-8")
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "verified",
            ).returncode,
        )
        outside.write_text("task staged content", encoding="utf-8")
        subprocess.run(["git", "add", "outside.txt"], cwd=self.workspace, check=True)
        outside.write_text("preexisting worktree", encoding="utf-8")

        result = self.run_cli("complete", "task-1")

        self.assertEqual(1, result.returncode)
        self.assertIn("outside.txt", result.stderr)

    def test_allowed_paths_single_star_does_not_cross_directory_separator(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        config = base_config()
        config["policy"]["allowed_paths"] = ["src/*", ".harness/**"]
        self.write_json("config.json", config)
        self.initialize_git_repository()
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "verified",
            ).returncode,
        )
        nested = self.workspace / "src" / "deep" / "unexpected.txt"
        nested.parent.mkdir(parents=True)
        nested.write_text("unexpected", encoding="utf-8")

        result = self.run_cli("complete", "task-1")

        self.assertEqual(1, result.returncode)
        self.assertIn("src/deep/unexpected.txt", result.stderr)

    def test_doctor_rejects_unsafe_allowed_path_patterns(self):
        for pattern in ("../outside/**", "/absolute/**", "src//file"):
            with self.subTest(pattern=pattern):
                config = base_config()
                config["policy"]["allowed_paths"] = [pattern]
                self.write_json("config.json", config)

                result = self.run_cli("doctor")

                self.assertEqual(2, result.returncode)
                self.assertIn("allowed_paths", result.stderr)

    def test_handoff_marks_new_out_of_scope_git_changes(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.initialize_git_repository()
        self.assertEqual(0, self.run_cli("next").returncode)
        (self.workspace / "outside.txt").write_text("unexpected", encoding="utf-8")

        result = self.run_cli("handoff")

        self.assertEqual(0, result.returncode, result.stderr)
        handoff = (self.harness_dir / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("Out-of-scope warning", handoff)
        self.assertIn("outside.txt", handoff)

    def test_complete_rejects_committed_git_changes_outside_allowed_paths(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        config = base_config()
        config["policy"]["allowed_paths"] = [".harness/**"]
        self.write_json("config.json", config)
        self.initialize_git_repository()
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "verified",
            ).returncode,
        )
        (self.workspace / "outside.txt").write_text("unexpected", encoding="utf-8")
        subprocess.run(["git", "add", "outside.txt"], cwd=self.workspace, check=True)
        subprocess.run(
            ["git", "commit", "-m", "out of scope"],
            cwd=self.workspace,
            check=True,
            text=True,
            capture_output=True,
        )

        result = self.run_cli("complete", "task-1")

        self.assertEqual(1, result.returncode)
        self.assertIn("outside allowed_paths", result.stderr)
        self.assertIn("outside.txt", result.stderr)

    def test_complete_uses_allowed_paths_from_task_start(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.initialize_git_repository()
        self.assertEqual(0, self.run_cli("next").returncode)
        (self.workspace / "outside.txt").write_text("unexpected", encoding="utf-8")
        config = base_config()
        config["policy"]["allowed_paths"] = ["**"]
        self.write_json("config.json", config)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "verified",
            ).returncode,
        )

        result = self.run_cli("complete", "task-1")

        self.assertEqual(1, result.returncode)
        self.assertIn("outside.txt", result.stderr)

    def test_complete_allows_committed_changes_inside_allowed_paths(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.initialize_git_repository()
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "verified",
            ).returncode,
        )
        source = self.workspace / "src" / "feature.txt"
        source.parent.mkdir()
        source.write_text("allowed", encoding="utf-8")
        subprocess.run(["git", "add", "src/feature.txt"], cwd=self.workspace, check=True)
        subprocess.run(
            ["git", "commit", "-m", "allowed change"],
            cwd=self.workspace,
            check=True,
            text=True,
            capture_output=True,
        )

        result = self.run_cli("complete", "task-1")

        self.assertEqual(0, result.returncode, result.stderr)

    def test_complete_rejects_further_edits_to_preexisting_out_of_scope_path(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.initialize_git_repository()
        preexisting = self.workspace / "preexisting.txt"
        preexisting.write_text("before task", encoding="utf-8")
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "verified",
            ).returncode,
        )
        preexisting.write_text("changed during task", encoding="utf-8")

        result = self.run_cli("complete", "task-1")

        self.assertEqual(1, result.returncode)
        self.assertIn("preexisting.txt", result.stderr)

    def test_later_failure_replaces_previous_passed_result(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "worked once",
            ).returncode,
        )

        failed = self.run_cli(
            "record", "task-1", "check-1", "--result", "failed", "--summary", "regressed",
        )

        self.assertEqual(1, failed.returncode)
        check = self.read_tasks()["tasks"][0]["acceptance"][0]
        self.assertEqual("failed", check["status"])
        self.assertEqual(1, check["consecutive_failures"])
        self.assertEqual(1, self.run_cli("complete", "task-1").returncode)

    def test_preexisting_dirty_path_is_reported_but_does_not_block_completion(self):
        self.write_json("tasks.json", base_tasks(check_type="manual"))
        self.initialize_git_repository()
        (self.workspace / "preexisting.txt").write_text("already here", encoding="utf-8")
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assertEqual(
            0,
            self.run_cli(
                "record", "task-1", "check-1", "--result", "passed", "--summary", "verified",
            ).returncode,
        )

        completed = self.run_cli("complete", "task-1")

        self.assertEqual(0, completed.returncode, completed.stderr)
        handoff = (self.harness_dir / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("preexisting.txt", handoff)
        self.assertIn("Pre-existing changes at task start", handoff)

    def test_doctor_and_handoff_report_git_identity(self):
        self.initialize_git_repository()
        expected_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.workspace, check=True, text=True, capture_output=True
        ).stdout.strip()

        doctor = self.run_cli("doctor")
        handoff = self.run_cli("handoff")

        self.assertEqual(0, doctor.returncode, doctor.stderr)
        self.assertIn(expected_head, doctor.stdout)
        self.assertEqual(0, handoff.returncode, handoff.stderr)
        handoff_text = (self.harness_dir / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn(expected_head, handoff_text)
        self.assertIn("Branch:", handoff_text)

    def test_nested_workspace_git_audit_ignores_parent_repository_changes(self):
        nested = self.workspace / "packages" / "nested-project"
        nested_harness = nested / ".harness"
        nested_harness.mkdir(parents=True)
        (nested_harness / "config.json").write_text(
            json.dumps(base_config(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        nested_tasks = base_tasks(check_type="manual")
        (nested_harness / "tasks.json").write_text(
            json.dumps(nested_tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self.initialize_git_repository()

        def run_nested(*args):
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--workspace", str(nested), *args],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, run_nested("next").returncode)
        (self.workspace / "parent-only.txt").write_text("outside nested project", encoding="utf-8")
        self.assertEqual(
            0,
            run_nested(
                "record",
                "task-1",
                "check-1",
                "--result",
                "passed",
                "--summary",
                "verified",
            ).returncode,
        )

        completed = run_nested("complete", "task-1")

        self.assertEqual(0, completed.returncode, completed.stderr)
        handoff = (nested_harness / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("- .harness/tasks.json", handoff)
        self.assertNotIn("packages/nested-project", handoff)
        self.assertNotIn("parent-only.txt", handoff)

    def test_shipped_template_and_todo_example_pass_doctor(self):
        for workspace in (PROJECT_ROOT / "template", PROJECT_ROOT / "examples" / "todo"):
            with self.subTest(workspace=workspace):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--workspace", str(workspace), "doctor"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)

    def test_todo_example_survives_cold_start_and_runs_its_check(self):
        example_copy = self.workspace / "todo-example"
        shutil.copytree(PROJECT_ROOT / "examples" / "todo", example_copy)

        first_process = subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace", str(example_copy), "status"],
            text=True,
            capture_output=True,
            check=False,
        )
        second_process = subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace", str(example_copy), "run", "check"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, first_process.returncode, first_process.stderr)
        self.assertIn("todo-add", first_process.stdout)
        self.assertIn("todo-toggle", first_process.stdout)
        self.assertIn("todo-persist", first_process.stdout)
        self.assertEqual(0, second_process.returncode, second_process.stderr)
        self.assertIn("pass 3", second_process.stdout)

    def test_todo_handoff_next_command_works_from_example_directory(self):
        repository_copy = self.workspace / "repository"
        example_copy = repository_copy / "examples" / "todo"
        shutil.copytree(PROJECT_ROOT / "template", repository_copy / "template")
        shutil.copytree(PROJECT_ROOT / "examples" / "todo", example_copy)

        result = subprocess.run(
            [sys.executable, ".harness/harness.py", "next"],
            cwd=example_copy,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        tasks = json.loads((example_copy / ".harness" / "tasks.json").read_text(encoding="utf-8"))
        self.assertEqual("todo-add", tasks["current_task_id"])


if __name__ == "__main__":
    unittest.main()
