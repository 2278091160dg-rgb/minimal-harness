import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "integrations" / "github" / "publish_check.py"


class RecordingHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.server.requests.append(
            {
                "path": self.path,
                "headers": dict(self.headers),
                "body": self.rfile.read(length),
            }
        )
        self.send_response(self.server.response_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.server.response_body)

    def do_GET(self):
        self.server.get_requests.append(self.path)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"id": 99}')

    def log_message(self, _format, *_args):
        return


class GitHubIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp_dir.name)
        self.summary = self.directory / "summary.md"
        self.summary.write_text("Harness checks passed.\n", encoding="utf-8")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        self.server.requests = []
        self.server.get_requests = []
        self.server.response_status = 201
        self.server.response_body = b'{"id": 42, "html_url": "https://example.test/check/42"}'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp_dir.cleanup()

    def run_publisher(self, *args, env_overrides=None):
        env = {
            **os.environ,
            "GITHUB_TOKEN": "test-token",
            "GITHUB_REPOSITORY": "owner/project",
            "GITHUB_SHA": "a" * 40,
            "GITHUB_API_URL": f"http://127.0.0.1:{self.server.server_port}",
        }
        if env_overrides:
            env.update(env_overrides)
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--conclusion",
                "success",
                "--title",
                "Minimal Harness passed",
                "--summary-file",
                str(self.summary),
                *args,
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            env=env,
        )

    def test_publishes_completed_check_run(self):
        result = self.run_publisher()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, len(self.server.requests))
        request = self.server.requests[0]
        self.assertEqual("/repos/owner/project/check-runs", request["path"])
        self.assertEqual("Bearer test-token", request["headers"]["Authorization"])
        self.assertEqual("application/vnd.github+json", request["headers"]["Accept"])
        payload = json.loads(request["body"])
        self.assertEqual("Minimal Harness", payload["name"])
        self.assertEqual("a" * 40, payload["head_sha"])
        self.assertEqual("completed", payload["status"])
        self.assertEqual("success", payload["conclusion"])
        self.assertEqual("Minimal Harness passed", payload["output"]["title"])
        self.assertEqual("Harness checks passed.\n", payload["output"]["summary"])
        self.assertIn("check/42", result.stdout)

    def test_missing_environment_is_usage_error_without_network_request(self):
        for name in ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "GITHUB_SHA"):
            with self.subTest(name=name):
                result = self.run_publisher(env_overrides={name: ""})
                self.assertEqual(2, result.returncode)
                self.assertIn(name, result.stderr)
        self.assertEqual([], self.server.requests)

    def test_rejects_invalid_summary_file(self):
        result = self.run_publisher("--summary-file", str(self.directory))

        self.assertEqual(2, result.returncode)
        self.assertIn("regular file", result.stderr)
        self.assertEqual([], self.server.requests)

    def test_github_error_is_failure_and_token_is_not_exposed(self):
        self.server.response_status = 403
        self.server.response_body = b'{"message":"permission denied"}'

        result = self.run_publisher()

        self.assertEqual(1, result.returncode)
        self.assertIn("permission denied", result.stderr)
        self.assertNotIn("test-token", result.stderr)

    def test_non_utf8_github_error_is_safely_decoded(self):
        self.server.response_status = 500
        self.server.response_body = b"server failed: \xff"

        result = self.run_publisher()

        self.assertEqual(1, result.returncode)
        self.assertIn("server failed", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_json_success_response_is_failure(self):
        self.server.response_body = b"not-json"

        result = self.run_publisher()

        self.assertEqual(1, result.returncode)
        self.assertIn("invalid JSON", result.stderr)

    def test_network_failure_is_reported_without_traceback(self):
        result = self.run_publisher(
            env_overrides={"GITHUB_API_URL": "http://127.0.0.1:1"}
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("request failed", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_redirect_is_rejected_without_forwarding_authorization(self):
        self.server.response_status = 302
        self.server.response_body = b"redirect"
        self.server.redirect_target = f"http://127.0.0.1:{self.server.server_port}/token-leak"

        original_do_post = RecordingHandler.do_POST

        def redirecting_do_post(handler):
            length = int(handler.headers.get("Content-Length", "0"))
            handler.server.requests.append(
                {
                    "path": handler.path,
                    "headers": dict(handler.headers),
                    "body": handler.rfile.read(length),
                }
            )
            handler.send_response(302)
            handler.send_header("Location", handler.server.redirect_target)
            handler.end_headers()

        RecordingHandler.do_POST = redirecting_do_post
        self.addCleanup(setattr, RecordingHandler, "do_POST", original_do_post)

        result = self.run_publisher()

        self.assertEqual(1, result.returncode)
        self.assertIn("HTTP 302", result.stderr)
        self.assertEqual([], self.server.get_requests)


if __name__ == "__main__":
    unittest.main()
