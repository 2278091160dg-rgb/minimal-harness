"""Exercise the release helper against a committed copy of the real runtime."""

import json
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = REPOSITORY_ROOT / "scripts" / "check_release.py"


def load_check_module():
    scripts = str(REPOSITORY_ROOT / "scripts")
    sys.path.insert(0, scripts)
    try:
        spec = importlib.util.spec_from_file_location("check_release_for_test", CHECK_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(scripts)


class ReleaseSmokeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "real-runtime-fixture"
        self.repo.mkdir()
        (self.repo / "scripts").mkdir()
        shutil.copy2(REPOSITORY_ROOT / "LICENSE", self.repo / "LICENSE")
        shutil.copy2(REPOSITORY_ROOT / "scripts" / "build_release.py", self.repo / "scripts")
        if CHECK_SCRIPT.exists():
            shutil.copy2(CHECK_SCRIPT, self.repo / "scripts")
        shutil.copytree(
            REPOSITORY_ROOT / "template" / ".harness",
            self.repo / "template" / ".harness",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        self.git("init")
        self.git("config", "user.name", "Release Smoke Test")
        self.git("config", "user.email", "release-smoke@example.invalid")
        self.git("add", "LICENSE", "scripts", "template")
        self.git("commit", "-m", "commit real runtime fixture")

    def git(self, *arguments):
        return subprocess.run(
            ["git", "-C", str(self.repo), *arguments],
            check=True,
            capture_output=True,
        )

    def run_helper(self, output_name="release-check", version="v9.8.7"):
        return self.run_helper_with_output(self.repo / output_name, self.repo, version)

    def run_helper_with_output(self, output_path, cwd, version="v9.8.7"):
        return subprocess.run(
            [
                sys.executable,
                str(self.repo / "scripts" / "check_release.py"),
                "--ref",
                "HEAD",
                "--version",
                version,
                "--output-dir",
                str(output_path),
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
        )

    def test_real_release_completes_behavior_loop_and_retains_evidence(self):
        root_license = self.repo / "LICENSE"
        root_license.write_bytes(
            root_license.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        )
        result = self.run_helper()

        output = self.repo / "release-check"
        diagnostic = output / "diagnostics" / "check-release.log"
        self.assertEqual(
            0,
            result.returncode,
            result.stdout + result.stderr + (diagnostic.read_text() if diagnostic.exists() else ""),
        )
        archive = output / "assets" / "minimal-harness-v9.8.7.zip"
        checksum = output / "assets" / "SHA256SUMS.txt"
        self.assertTrue(archive.is_file())
        self.assertTrue(checksum.is_file())
        expected_license = (self.repo / "LICENSE").read_bytes().replace(b"\r\n", b"\n")
        with zipfile.ZipFile(archive) as package:
            self.assertEqual(
                package.read(".harness/LICENSE"),
                expected_license,
            )

        installed = output / "smoke-project" / ".harness"
        self.assertEqual(
            (installed / "LICENSE").read_bytes(),
            expected_license,
        )
        tasks = json.loads((installed / "tasks.json").read_text(encoding="utf-8"))
        self.assertEqual("done", tasks["tasks"][0]["status"])
        self.assertEqual("passed", tasks["tasks"][0]["acceptance"][0]["status"])
        self.assertIn("greeting behavior", (installed / "HANDOFF.md").read_text(encoding="utf-8"))

        reports = output / "diagnostics" / "reports"
        self.assertTrue(json.loads((reports / "report.json").read_text(encoding="utf-8"))["ready"])
        self.assertIn("— ready", (reports / "report.txt").read_text(encoding="utf-8"))
        self.assertIn("— ready", (reports / "report.md").read_text(encoding="utf-8"))
        stale = (output / "diagnostics" / "stale-complete.log").read_text(encoding="utf-8")
        self.assertIn("stale evidence", stale)
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual("passed", summary["status"])
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.decode().strip(), summary["commit"])

    def test_failure_keeps_diagnostic_log_without_partial_smoke_project(self):
        result = self.run_helper(output_name="invalid-check", version="not-a-version")

        self.assertNotEqual(0, result.returncode)
        output = self.repo / "invalid-check"
        log = output / "diagnostics" / "check-release.log"
        self.assertTrue(log.is_file())
        self.assertIn("invalid version", log.read_text(encoding="utf-8").lower())
        self.assertFalse((output / "smoke-project").exists())

    def test_child_command_timeout_fails_quickly_and_is_logged(self):
        module = load_check_module()
        transcript = module.Transcript(Path(self.temporary.name) / "timeout.log")
        started = time.monotonic()

        with self.assertRaisesRegex(module.CheckFailure, "timed out"):
            module.run_command(
                transcript,
                [sys.executable, "-c", "import time; time.sleep(2)"],
                self.repo,
                timeout_seconds=0.05,
            )

        self.assertLess(time.monotonic() - started, 1.0)
        self.assertIn("timed out", transcript.path.read_text(encoding="utf-8"))

    def test_safe_extract_rejects_cross_platform_escape_names(self):
        module = load_check_module()
        for index, unsafe_name in enumerate(
            (".harness/..\\outside.txt", ".harness/C:outside.txt")
        ):
            with self.subTest(name=unsafe_name):
                archive = Path(self.temporary.name) / f"unsafe-{index}.zip"
                with zipfile.ZipFile(archive, "w") as package:
                    package.writestr(unsafe_name, b"must not extract")
                destination = Path(self.temporary.name) / f"extract-{index}"

                with self.assertRaisesRegex(module.CheckFailure, "unsafe"):
                    module.safe_extract(archive, destination)

                self.assertEqual([], list(destination.rglob("*")))

    def test_output_path_is_absolute_when_resolve_preserves_a_relative_path(self):
        module = load_check_module()
        with mock.patch.object(module.Path, "resolve", lambda path: path):
            output = module.absolute_output_path(Path("missing-relative-output"))

        self.assertTrue(output.is_absolute(), output)

    def test_relative_output_dir_completes_from_a_non_repository_cwd(self):
        caller = Path(self.temporary.name) / "non-repository-caller"
        caller.mkdir()

        result = self.run_helper_with_output("relative-release-check", caller)

        output = caller / "relative-release-check"
        diagnostic = output / "diagnostics" / "check-release.log"
        self.assertEqual(
            0,
            result.returncode,
            result.stdout + result.stderr + (diagnostic.read_text() if diagnostic.exists() else ""),
        )
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual("passed", summary["status"])
        self.assertEqual("smoke-project", summary["smoke_project"])


if __name__ == "__main__":
    unittest.main()
