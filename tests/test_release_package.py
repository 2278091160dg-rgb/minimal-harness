import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPOSITORY_ROOT / "scripts" / "build_release.py"


class ReleasePackageTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.repo = Path(self.temp_dir.name) / "repo"
        self.repo.mkdir()
        self.run_git("init")
        self.run_git("config", "user.name", "Release Test")
        self.run_git("config", "user.email", "release@example.invalid")

        harness_dir = self.repo / "template" / ".harness"
        harness_dir.mkdir(parents=True)
        (harness_dir / "harness.py").write_text("print('committed')\n", encoding="utf-8")
        (harness_dir / "config.json").write_text("{}\n", encoding="utf-8")
        self.run_git("add", "template/.harness")
        self.run_git("commit", "-m", "add harness template")

    def run_git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            capture_output=True,
        )

    def run_builder(self, version="v1.2.3"):
        output_dir = self.repo / "dist"
        result = subprocess.run(
            [
                sys.executable,
                str(BUILD_SCRIPT),
                "--repo",
                str(self.repo),
                "--ref",
                "HEAD",
                "--version",
                version,
                "--output-dir",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
        )
        return result, output_dir

    def test_builds_fixed_ref_archive_and_matching_checksum(self):
        harness_dir = self.repo / "template" / ".harness"
        (harness_dir / "harness.py").write_text("print('dirty')\n", encoding="utf-8")
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
                {".harness/config.json", ".harness/harness.py"},
            )
            self.assertEqual(
                package.read(".harness/harness.py"),
                self.run_git(
                    "show", "HEAD:template/.harness/harness.py"
                ).stdout,
            )

        expected_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual(
            checksum.read_text(encoding="utf-8"),
            f"{expected_digest}  {archive.name}\n",
        )

    def test_rejects_unsafe_version_without_writing_assets(self):
        result, output_dir = self.run_builder("../v1.2.3")

        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid version", result.stderr.lower())
        self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
