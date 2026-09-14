import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "first-use-macos.md"
HARNESS = ROOT / "template" / ".harness" / "harness.py"


def run_command(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("PYTHONDONTWRITEBYTECODE", None)
    return subprocess.run(
        arguments,
        cwd=cwd,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class FirstUseDocumentationTest(unittest.TestCase):
    def test_documented_python_template_does_not_stale_its_own_evidence(self):
        guide = GUIDE.read_text(encoding="utf-8")
        json_blocks = re.findall(r"```json\n(.*?)```", guide, flags=re.DOTALL)
        self.assertEqual(len(json_blocks), 2)
        task = json.loads(json_blocks[0])

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            (workspace / "test_sample.py").write_text(
                "import unittest\n\n"
                "class SampleTest(unittest.TestCase):\n"
                "    def test_example(self):\n"
                "        self.assertEqual(1 + 1, 2)\n",
                encoding="utf-8",
            )
            task_path = workspace / "first-task.json"
            task_path.write_text(json.dumps(task), encoding="utf-8")

            git_result = run_command(["git", "init"], workspace)
            self.assertEqual(git_result.returncode, 0, git_result.stdout)

            steps = (
                ([sys.executable, str(HARNESS), "--workspace", str(workspace), "init"], 0),
                ([sys.executable, ".harness/harness.py", "doctor"], 0),
                (
                    [
                        sys.executable,
                        ".harness/harness.py",
                        "task",
                        "add",
                        "--from",
                        str(task_path),
                    ],
                    0,
                ),
                ([sys.executable, ".harness/harness.py", "next"], 0),
                ([sys.executable, ".harness/harness.py", "verify", "first-check"], 0),
                ([sys.executable, ".harness/harness.py", "report", "first-check"], 0),
            )
            for arguments, expected_status in steps:
                with self.subTest(command=arguments[-1]):
                    result = run_command(arguments, workspace)
                    self.assertEqual(result.returncode, expected_status, result.stdout)


if __name__ == "__main__":
    unittest.main()
