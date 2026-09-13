"""The browser runner must validate its CLI without importing Playwright."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "todo_browser_acceptance.py"


class BrowserCliTest(unittest.TestCase):
    def run_without_site_packages(self, *args):
        return subprocess.run(
            [sys.executable, "-S", str(SCRIPT), *args],
            capture_output=True, text=True, timeout=15,
        )

    def test_help_does_not_require_browser_dependencies(self):
        result = self.run_without_site_packages("--help")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_file_as_artifact_directory_is_rejected_before_browser_start(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "keep.txt"
            destination.write_bytes(b"user content")
            result = self.run_without_site_packages("--artifact-dir", str(destination))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(destination.read_bytes(), b"user content")
            self.assertEqual(list(Path(temp).iterdir()), [destination])


if __name__ == "__main__":
    unittest.main()
