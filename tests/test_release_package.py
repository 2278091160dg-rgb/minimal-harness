import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPOSITORY_ROOT / "scripts" / "build_release.py"


def load_build_module():
    spec = importlib.util.spec_from_file_location("build_release_for_test", BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleasePackageTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.repo = Path(self.temp_dir.name) / "repo"
        self.repo.mkdir()
        self.run_git("init")
        self.run_git("config", "user.name", "Release Test")
        self.run_git("config", "user.email", "release@example.invalid")
        self.run_git("config", "core.autocrlf", "true")

        harness_dir = self.repo / "template" / ".harness"
        harness_dir.mkdir(parents=True)
        (self.repo / "LICENSE").write_bytes(b"root license from committed ref\r\n")
        (harness_dir / "LICENSE").write_bytes(b"template license from committed ref\r\n")
        (harness_dir / "harness.py").write_bytes(b"print('committed')\r\n")
        (harness_dir / "harness_init.py").write_bytes(b"# initializer\r\n")
        (harness_dir / "harness_runner.py").write_bytes(b"# bounded runner\r\n")
        (harness_dir / "config.json").write_text('{"schema_version": 3}\n', encoding="utf-8")
        (harness_dir / "tasks.json").write_text('{"schema_version": 3, "tasks": []}\n', encoding="utf-8")
        self.run_git("add", "LICENSE", "template/.harness")
        self.run_git("commit", "-m", "add harness template")

    def run_git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            capture_output=True,
        )

    def run_builder(self, version="v1.2.3", output_name="dist", ref="HEAD"):
        output_dir = self.repo / output_name
        result = subprocess.run(
            [
                sys.executable,
                str(BUILD_SCRIPT),
                "--repo",
                str(self.repo),
                "--ref",
                ref,
                "--version",
                version,
                "--output-dir",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
        )
        return result, output_dir

    def commit_legacy_template(self, schema):
        harness_dir = self.repo / "template" / ".harness"
        (harness_dir / "config.json").write_text(
            json.dumps({"schema_version": schema}) + "\n", encoding="utf-8"
        )
        (harness_dir / "tasks.json").write_text(
            json.dumps({"schema_version": schema, "tasks": []}) + "\n", encoding="utf-8"
        )
        self.run_git(
            "rm",
            "template/.harness/harness_init.py",
            "template/.harness/harness_runner.py",
            "template/.harness/LICENSE",
        )
        self.run_git("add", "template/.harness")
        self.run_git("commit", "-m", f"legacy schema {schema} template")

    def test_builds_fixed_ref_archive_and_matching_checksum(self):
        harness_dir = self.repo / "template" / ".harness"
        (harness_dir / "harness.py").write_text("print('dirty')\n", encoding="utf-8")
        (harness_dir / "LICENSE").write_text("dirty checkout license\n", encoding="utf-8")
        (harness_dir / "evidence").mkdir()
        (harness_dir / "evidence" / "untracked.json").write_text("secret\n", encoding="utf-8")

        result, output_dir = self.run_builder()

        self.assertEqual(result.returncode, 0, result.stderr)
        archive = output_dir / "minimal-harness-v1.2.3.zip"
        checksum = output_dir / "SHA256SUMS.txt"
        self.assertTrue(archive.is_file())
        self.assertTrue(checksum.is_file())

        with zipfile.ZipFile(archive) as package:
            file_names = {name for name in package.namelist() if not name.endswith("/")}
            self.assertEqual(
                file_names,
                {
                    ".harness/LICENSE",
                    ".harness/config.json",
                    ".harness/tasks.json",
                    ".harness/harness.py",
                    ".harness/harness_init.py",
                    ".harness/harness_runner.py",
                },
            )
            for name in ("harness.py", "harness_init.py", "harness_runner.py"):
                self.assertEqual(
                    package.read(f".harness/{name}"),
                    self.run_git("show", f"HEAD:template/.harness/{name}").stdout,
                )
                self.assertNotIn(b"\r\n", package.read(f".harness/{name}"))
            self.assertEqual(
                package.read(".harness/LICENSE"),
                b"template license from committed ref\n",
            )

        expected_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual(
            checksum.read_text(encoding="utf-8"),
            f"{expected_digest}  {archive.name}\n",
        )

    def test_missing_runtime_or_state_file_is_rejected_before_assets_are_written(self):
        baseline = self.run_git("rev-parse", "HEAD").stdout.decode("ascii").strip()
        required = ("harness.py", "harness_init.py", "harness_runner.py", "config.json", "tasks.json")
        for name in required:
            with self.subTest(missing=name):
                try:
                    self.run_git("rm", f"template/.harness/{name}")
                    self.run_git("commit", "-m", f"remove {name}")

                    result, output_dir = self.run_builder(output_name=f"missing-{name}")

                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn(f".harness/{name}", result.stderr)
                    self.assertFalse(output_dir.exists())
                finally:
                    self.run_git("reset", "--hard", baseline)

    def test_missing_all_fixed_ref_license_sources_is_rejected_before_assets_are_written(self):
        self.run_git("rm", "LICENSE", "template/.harness/LICENSE")
        self.run_git("commit", "-m", "remove every license source")

        result, output_dir = self.run_builder()

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("license", result.stderr.lower())
        self.assertFalse(output_dir.exists())

    def test_committed_generated_outputs_are_rejected_before_assets_are_written(self):
        baseline = self.run_git("rev-parse", "HEAD").stdout.decode("ascii").strip()
        generated_directories = ("attempts", "artifacts", "reports", "evidence", "logs", "migrations", "__pycache__")
        for name in generated_directories:
            with self.subTest(generated=name):
                try:
                    generated = self.repo / "template" / ".harness" / name / "private.txt"
                    generated.parent.mkdir()
                    generated.write_text("private run output\n", encoding="utf-8")
                    self.run_git("add", str(generated))
                    self.run_git("commit", "-m", f"accidentally retain {name}")

                    result, output_dir = self.run_builder(output_name=f"generated-{name}")

                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("forbidden path", result.stderr)
                    self.assertIn(f".harness/{name}/private.txt", result.stderr)
                    self.assertFalse(output_dir.exists())
                finally:
                    self.run_git("reset", "--hard", baseline)

    def test_rejects_unsafe_version_without_writing_assets(self):
        result, output_dir = self.run_builder("../v1.2.3")

        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid version", result.stderr.lower())
        self.assertFalse(output_dir.exists())

    def test_git_timeout_is_bounded_and_preserves_command_output(self):
        module = load_build_module()
        timeout = subprocess.TimeoutExpired(
            cmd=["git", "status"],
            timeout=0.05,
            output=b"partial stdout",
            stderr=b"partial stderr",
        )
        with mock.patch.object(module.subprocess, "run", side_effect=timeout):
            with self.assertRaisesRegex(RuntimeError, "timed out.*partial stderr"):
                module.git_output(self.repo, "status", timeout_seconds=0.05)

    def test_legacy_fixed_refs_rebuild_without_v3_runtime_modules(self):
        baseline = self.run_git("rev-parse", "HEAD").stdout.decode("ascii").strip()
        for schema in (1, 2):
            with self.subTest(schema=schema):
                try:
                    self.commit_legacy_template(schema)
                    legacy_tag = f"v0.1.{schema}"
                    self.run_git("tag", legacy_tag)
                finally:
                    self.run_git("reset", "--hard", baseline)

                # HEAD contains v3; rebuilding the old tag must inspect the old config.
                result, output_dir = self.run_builder(
                    version=legacy_tag, output_name=f"legacy-{schema}", ref=legacy_tag
                )

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                with zipfile.ZipFile(output_dir / f"minimal-harness-{legacy_tag}.zip") as package:
                    self.assertEqual(
                        {name for name in package.namelist() if not name.endswith("/")},
                        {
                            ".harness/LICENSE",
                            ".harness/harness.py",
                            ".harness/config.json",
                            ".harness/tasks.json",
                        },
                    )
                    self.assertEqual(schema, json.loads(package.read(".harness/config.json"))["schema_version"])
                    self.assertEqual(
                        self.run_git("show", f"{legacy_tag}:template/.harness/harness.py").stdout,
                        package.read(".harness/harness.py"),
                    )
                    self.assertEqual(
                        b"root license from committed ref\n",
                        package.read(".harness/LICENSE"),
                    )

    def test_legacy_license_fallback_uses_fixed_ref_and_is_timezone_deterministic(self):
        self.commit_legacy_template(2)
        fixed_ref = self.run_git("rev-parse", "HEAD").stdout.decode("ascii").strip()
        (self.repo / "LICENSE").write_bytes(b"dirty current checkout license\n")

        with mock.patch.dict(os.environ, {"TZ": "UTC"}):
            first, first_dir = self.run_builder(output_name="first", ref=fixed_ref)
        with mock.patch.dict(os.environ, {"TZ": "Pacific/Honolulu"}):
            second, second_dir = self.run_builder(output_name="second", ref=fixed_ref)

        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        first_archive = first_dir / "minimal-harness-v1.2.3.zip"
        second_archive = second_dir / "minimal-harness-v1.2.3.zip"
        self.assertEqual(first_archive.read_bytes(), second_archive.read_bytes())
        with zipfile.ZipFile(first_archive) as package:
            self.assertEqual(
                package.read(".harness/LICENSE"),
                b"root license from committed ref\n",
            )

    def test_legacy_archive_still_rejects_new_generated_directories(self):
        self.commit_legacy_template(2)
        baseline = self.run_git("rev-parse", "HEAD").stdout.decode("ascii").strip()
        for name in ("attempts", "artifacts", "reports"):
            with self.subTest(generated=name):
                try:
                    generated = self.repo / "template" / ".harness" / name / "private.txt"
                    generated.parent.mkdir()
                    generated.write_text("private run output\n", encoding="utf-8")
                    self.run_git("add", str(generated))
                    self.run_git("commit", "-m", f"accidentally retain {name}")

                    result, output_dir = self.run_builder(output_name=f"legacy-generated-{name}")

                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("forbidden path", result.stderr)
                    self.assertIn(f".harness/{name}/private.txt", result.stderr)
                    self.assertFalse(output_dir.exists())
                finally:
                    self.run_git("reset", "--hard", baseline)


if __name__ == "__main__":
    unittest.main()
