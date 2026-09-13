"""Exercise the public quickstart against a copied, independently installed runtime."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "template" / ".harness" / "harness.py"


class FirstUseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "demo"
        shutil.copytree(ROOT / "examples" / "quickstart", self.workspace,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.env = dict(os.environ)
        self.env.pop("PYTHONDONTWRITEBYTECODE", None)
        initialized = subprocess.run(
            [sys.executable, str(CANONICAL), "--workspace", str(self.workspace),
             "init", "--agent", "codex"],
            capture_output=True, text=True, encoding="utf-8", env=self.env,
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        subprocess.run(["git", "init", "-q"], cwd=self.workspace, check=True, capture_output=True)

    def cli(self, *args, expected=0):
        result = subprocess.run(
            [sys.executable, ".harness/harness.py", *args], cwd=self.workspace,
            capture_output=True, text=True, encoding="utf-8", env=self.env,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_installed_runtime_completes_the_documented_quickstart(self):
        self.cli("doctor")
        self.cli("task", "add", "--from", "greeting.task.json")
        self.cli("next")
        self.cli("verify")
        report = json.loads(self.cli("report", "greeting", "--format", "json").stdout)
        self.assertTrue(report["ready"])
        self.assertEqual(report["checks"][0]["provenance"], "command-exit")
        evidence = self.workspace / report["checks"][0]["evidence_path"]
        self.assertTrue(evidence.is_file())
        for output_format in ("text", "markdown"):
            rendered = self.cli("report", "greeting", "--format", output_format).stdout
            self.assertIn("— ready", rendered)
            self.assertIn("command-exit", rendered)
        self.cli("complete", "greeting")
        self.cli("handoff")
        state = json.loads((self.workspace / ".harness/tasks.json").read_text())
        self.assertEqual(state["tasks"][0]["status"], "done")
        self.assertIn("greeting", (self.workspace / ".harness/HANDOFF.md").read_text())

    def test_real_behavior_regression_invalidates_evidence_then_recovers(self):
        self.cli("task", "add", "--from", "greeting.task.json")
        self.cli("next")
        self.cli("verify")
        source = self.workspace / "src/greet.py"
        original = source.read_text()
        source.write_text(original.replace("Hello", "Hi"), encoding="utf-8")
        stale = json.loads(self.cli("report", "greeting", "--format", "json", expected=1).stdout)
        self.assertFalse(stale["ready"])
        for output_format in ("text", "markdown"):
            rendered = self.cli("report", "greeting", "--format", output_format, expected=1).stdout
            self.assertIn("— not ready", rendered)
            self.assertIn("source snapshot is stale", rendered)
        self.cli("complete", "greeting", expected=1)
        self.cli("verify", expected=1)
        source.write_text(original, encoding="utf-8")
        self.cli("verify")
        self.cli("complete", "greeting")

    def test_browser_attestation_and_command_share_a_managed_artifact_snapshot(self):
        definition = json.loads((self.workspace / "greeting.task.json").read_text())
        definition["acceptance"].append({
            "id": "visual", "type": "browser", "instruction": "Observe the rendered greeting",
            "steps": ["Open the page", "Check the greeting text"],
        })
        (self.workspace / "greeting.task.json").write_text(json.dumps(definition), encoding="utf-8")
        self.cli("task", "add", "--from", "greeting.task.json")
        self.cli("next")
        self.cli("verify")
        artifacts = self.workspace / ".harness/artifacts"
        artifacts.mkdir()
        # This checks the attestation transport only. Real Chromium is a separate check.
        (artifacts / "observation.txt").write_text("Fixture observation", encoding="utf-8")
        self.cli("record", "greeting", "visual", "--result", "passed", "--summary",
                 "Fixture: observed the expected greeting", "--tool", "test-observer",
                 "--artifact", ".harness/artifacts/observation.txt")
        report = json.loads(self.cli("report", "greeting", "--format", "json").stdout)
        self.assertTrue(report["ready"])
        self.assertIn("attestation", report["checks"][1]["provenance"])
        self.cli("complete", "greeting")


if __name__ == "__main__":
    unittest.main()
