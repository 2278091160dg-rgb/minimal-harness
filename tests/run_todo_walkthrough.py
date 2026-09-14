"""Run real Chromium acceptance and the full Harness loop in a disposable Todo repo."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


repo = Path(__file__).resolve().parents[1]
example = repo / "examples" / "todo"
workspace = Path(tempfile.mkdtemp(prefix="harness-v3-browser-"))
shutil.copytree(example / "site", workspace / "site")
shutil.copy2(example / "test.mjs", workspace / "test.mjs")
environment = dict(os.environ)
environment.pop("HARNESS_CDP_URL", None)


def run(command):
    result = subprocess.run(command, cwd=workspace, env=environment, capture_output=True,
                            text=True, encoding="utf-8", timeout=120)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


run([sys.executable, str(repo / "template/.harness/harness.py"), "--workspace", str(workspace), "init"])
shutil.copy2(example / ".harness/config.json", workspace / ".harness/config.json")
run(["git", "init", "-q"])
definitions = workspace / ".harness/specs"
definitions.mkdir()
for task in json.loads((example / ".harness/tasks.json").read_text(encoding="utf-8"))["tasks"]:
    definition = {"id": task["id"], "title": task["title"], "acceptance": [
        {key: check[key] for key in ("id", "type", "instruction", "steps", "command", "timeout_seconds") if key in check}
        for check in task["acceptance"]
    ]}
    spec = definitions / f"{task['id']}.json"
    spec.write_text(json.dumps(definition, ensure_ascii=False), encoding="utf-8")
    run([sys.executable, ".harness/harness.py", "task", "add", "--from", str(spec)])

artifacts = workspace / ".harness/artifacts"
artifacts.mkdir()
with (artifacts / "server.log").open("wb") as server_log:
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8000", "--bind", "127.0.0.1",
         "--directory", str(workspace / "site")], stdout=server_log, stderr=subprocess.STDOUT,
    )
    try:
        expected_page = (workspace / "site/index.html").read_bytes()
        for _ in range(50):
            if server.poll() is not None:
                raise RuntimeError("Owned server failed; port 8000 may be busy. " +
                                   (artifacts / "server.log").read_text(encoding="utf-8"))
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000", timeout=1) as response:
                    if response.read() != expected_page:
                        raise RuntimeError("Port 8000 serves a different project; it was not modified")
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.1)
        else:
            raise RuntimeError("Demo server did not become ready")
        output = run([sys.executable, str(repo / "tests/todo_browser_acceptance.py"),
                      "--workspace", str(workspace), "--record"])
        print(output)
        state = json.loads((workspace / ".harness/tasks.json").read_text(encoding="utf-8"))
        if not all(task["status"] == "done" for task in state["tasks"]):
            raise RuntimeError("Browser checks did not complete every Harness task")
        print(f"BROWSER_PROOF_DIRECTORY={workspace}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
