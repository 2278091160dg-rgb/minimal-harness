"""Independent CLI processes share state; these are not live-agent tests."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "init_harness.py"


class HandoffProcessTest(unittest.TestCase):
    def test_new_process_resumes_same_task_and_preserves_evidence(self):
        with tempfile.TemporaryDirectory(prefix="harness-handoff-") as temp:
            workspace = Path(temp).resolve() / "todo"
            workspace.mkdir()
            setup = subprocess.run(
                [sys.executable, str(INSTALLER), "--workspace", str(workspace)],
                capture_output=True, text=True,
            )
            self.assertEqual(setup.returncode, 0, setup.stderr)
            example = ROOT / "examples" / "todo"
            shutil.copytree(example / "site", workspace / "site")
            shutil.copyfile(example / "test.mjs", workspace / "test.mjs")
            for name in ("config.json", "tasks.json"):
                shutil.copyfile(example / ".harness" / name, workspace / ".harness" / name)
            state_path = workspace / ".harness" / "tasks.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["tasks"][0]["acceptance"].insert(0, {
                "id": "store-regression", "type": "command",
                "instruction": "Verify Todo storage behavior with Node tests.",
                "command": ["node", "--test", "test.mjs"],
                "status": "not_run", "consecutive_failures": 0,
                "latest_evidence": None, "latest_evidence_sha256": None,
            })
            state_path.write_text(json.dumps(state), encoding="utf-8")
            for command in (
                ["git", "init"],
                ["git", "config", "user.name", "Harness Test"],
                ["git", "config", "user.email", "harness@example.test"],
                ["git", "add", "."],
                ["git", "commit", "-m", "Todo test fixture"],
            ):
                subprocess.run(command, cwd=workspace, capture_output=True, check=True)

            def cli(*args):
                return subprocess.run(
                    [sys.executable, ".harness/harness.py", *args],
                    cwd=workspace, capture_output=True, text=True, encoding="utf-8",
                )

            for args in (("doctor",), ("status",), ("next",), ("verify",), ("handoff",)):
                result = cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
            before_state = state_path.read_bytes()
            state = json.loads(before_state)
            evidence = workspace / state["tasks"][0]["acceptance"][0]["latest_evidence"]
            before_evidence = evidence.read_bytes()
            handoff_path = workspace / ".harness" / "HANDOFF.md"
            before_handoff = handoff_path.read_bytes()

            # Every call launches a fresh interpreter with no sender memory.
            self.assertEqual(cli("doctor").returncode, 0)
            status = cli("status")
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("Current task: todo-add", status.stdout)
            self.assertIn("todo-add", before_handoff.decode("utf-8"))
            self.assertEqual(state_path.read_bytes(), before_state)
            self.assertEqual(evidence.read_bytes(), before_evidence)
            self.assertEqual(handoff_path.read_bytes(), before_handoff)
            self.assertEqual(cli("next").returncode, 1)
            self.assertEqual(cli("complete", "todo-add").returncode, 1)

            # A process test cannot attest a real browser action.
            missing = cli(
                "record", "todo-add", "add-in-browser", "--result", "unverified",
                "--summary", "No browser action is performed by this process-only test.",
            )
            self.assertEqual(missing.returncode, 1, missing.stderr)
            after = json.loads(state_path.read_bytes())
            self.assertEqual(after["current_task_id"], "todo-add")
            self.assertEqual(after["tasks"][0]["acceptance"][1]["status"], "unverified")
            self.assertEqual(after["tasks"][1]["status"], "pending")
            self.assertEqual(evidence.read_bytes(), before_evidence)


if __name__ == "__main__":
    unittest.main()
