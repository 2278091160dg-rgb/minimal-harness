"""Regressions for combining released freshness guarantees with schema v3."""
import hashlib
import json
import subprocess
import sys
import unittest

import test_harness as fixtures
import test_harness_v3 as fixtures_v3


class MainIntegrationTest(unittest.TestCase):
    setUp = fixtures.HarnessCliTest.setUp
    tearDown = fixtures.HarnessCliTest.tearDown
    write_json = fixtures.HarnessCliTest.write_json
    read_tasks = fixtures.HarnessCliTest.read_tasks
    run_cli = fixtures.HarnessCliTest.run_cli
    initialize_git_repository = fixtures.HarnessCliTest.initialize_git_repository

    add_clean_submodule = fixtures_v3.HarnessV3Test.add_clean_submodule

    def ready(self):
        self.assertEqual(0, self.run_cli("next").returncode)
        result = self.run_cli("verify")
        self.assertEqual(0, result.returncode, result.stderr)

    def set_index_flags(self, flags, path="protected.txt", cwd=None):
        for flag in flags:
            subprocess.run(["git", "update-index", flag, "--", path],
                           cwd=cwd or self.workspace, check=True, capture_output=True)

    def clear_index_flags(self, path="protected.txt", cwd=None):
        self.set_index_flags(("--no-assume-unchanged", "--no-skip-worktree"), path, cwd)

    def assert_hidden_flags_rejected(self, result, returncode, path="protected.txt"):
        self.assertEqual(returncode, result.returncode, result.stdout + result.stderr)
        diagnostic = result.stdout + result.stderr
        self.assertIn("hidden index flags", diagnostic)
        self.assertIn(path, diagnostic)
        self.assertIn("--no-assume-unchanged", diagnostic)
        self.assertIn("--no-skip-worktree", diagnostic)

    def test_hidden_index_flags_before_next_reject_clean_tracked_files(self):
        (self.workspace / "protected.txt").write_text("original\n")
        self.initialize_git_repository()
        for flags in (("--assume-unchanged",), ("--skip-worktree",),
                      ("--assume-unchanged", "--skip-worktree")):
            with self.subTest(flags=flags):
                self.set_index_flags(flags)
                before = (self.harness_dir / "tasks.json").read_bytes()
                self.assert_hidden_flags_rejected(self.run_cli("next"), 2)
                self.assertEqual(before, (self.harness_dir / "tasks.json").read_bytes())
                self.clear_index_flags()
        self.assertEqual(0, self.run_cli("next").returncode)

    def test_hidden_index_flags_cannot_hide_out_of_scope_changes_before_verification(self):
        source = self.workspace / "protected.txt"
        source.write_text("original\n")
        self.initialize_git_repository()
        self.assertEqual(0, self.run_cli("next").returncode)
        for flags in (("--assume-unchanged",), ("--skip-worktree",),
                      ("--assume-unchanged", "--skip-worktree")):
            with self.subTest(flags=flags):
                self.set_index_flags(flags)
                source.write_text("forbidden change\n")
                self.assert_hidden_flags_rejected(self.run_cli("verify"), 2)
                report = self.run_cli("report", "task-1", "--format", "json")
                self.assert_hidden_flags_rejected(report, 1)
                self.assertFalse(json.loads(report.stdout)["ready"])
                self.assert_hidden_flags_rejected(self.run_cli("complete", "task-1"), 1)
                self.clear_index_flags()
                self.assertEqual(0, self.run_cli("verify").returncode)
                rejected = self.run_cli("complete", "task-1")
                self.assertEqual(1, rejected.returncode, rejected.stderr)
                self.assertIn("outside allowed_paths", rejected.stderr)
                source.write_text("original\n")
        self.assertEqual(0, self.run_cli("verify").returncode)
        self.assertEqual(0, self.run_cli("complete", "task-1").returncode)

    def test_hidden_index_flags_after_pass_block_reports_and_reverification_until_recovery(self):
        source = self.workspace / "protected.txt"
        source.write_text("original\n")
        self.initialize_git_repository()
        self.ready()
        for flags in (("--assume-unchanged",), ("--skip-worktree",),
                      ("--assume-unchanged", "--skip-worktree")):
            with self.subTest(flags=flags):
                self.set_index_flags(flags)
                before_flags = subprocess.run(["git", "ls-files", "-v", "-z"],
                                              cwd=self.workspace, capture_output=True, check=True).stdout
                before_state = (self.harness_dir / "tasks.json").read_bytes()
                for format_name in ("json", "text", "markdown"):
                    self.assert_hidden_flags_rejected(
                        self.run_cli("report", "task-1", "--format", format_name), 1)
                self.assertEqual(before_state, (self.harness_dir / "tasks.json").read_bytes())
                self.assert_hidden_flags_rejected(self.run_cli("complete", "task-1"), 1)
                self.assertEqual(before_flags, subprocess.run(["git", "ls-files", "-v", "-z"],
                                 cwd=self.workspace, capture_output=True, check=True).stdout)
                source.write_text("forbidden change\n")
                self.assert_hidden_flags_rejected(self.run_cli("verify"), 2)
                self.assertNotEqual("passed", self.read_tasks()["tasks"][0]["acceptance"][0]["status"])
                self.clear_index_flags()
                source.write_text("original\n")
                self.assertEqual(0, self.run_cli("verify").returncode)
                self.assertEqual(0, self.run_cli("report", "task-1", "--format", "json").returncode)
        self.assertEqual(0, self.run_cli("complete", "task-1").returncode)

    def test_hidden_index_flags_created_during_verification_cannot_pass(self):
        (self.workspace / "protected.txt").write_text("original\n")
        command = [sys.executable, "-c", "import subprocess; subprocess.run(['git', 'update-index', '--skip-worktree', 'protected.txt'], check=True)"]
        self.write_json("tasks.json", fixtures.base_tasks(command=command))
        self.initialize_git_repository()
        self.assertEqual(0, self.run_cli("next").returncode)
        self.assert_hidden_flags_rejected(self.run_cli("verify"), 2)
        self.assertNotEqual("passed", self.read_tasks()["tasks"][0]["acceptance"][0]["status"])
        self.assert_hidden_flags_rejected(self.run_cli("complete", "task-1"), 1)

    def test_nested_workspace_ignores_sibling_flags_but_rejects_its_own_flags(self):
        root = self.workspace
        nested = root / "packages" / "nested"
        harness = nested / ".harness"
        harness.mkdir(parents=True)
        (harness / "config.json").write_text(json.dumps(fixtures.base_config()))
        (harness / "tasks.json").write_text(json.dumps(fixtures.base_tasks()))
        (nested / "protected.txt").write_text("nested source\n")
        (root / "sibling.txt").write_text("unrelated source\n")
        self.initialize_git_repository()
        self.set_index_flags(("--assume-unchanged", "--skip-worktree"), "sibling.txt")
        (root / "sibling.txt").write_text("unrelated hidden change\n")
        self.workspace, self.harness_dir = nested, harness
        self.ready()
        for flags in (("--assume-unchanged",), ("--skip-worktree",)):
            with self.subTest(flags=flags):
                self.set_index_flags(flags)
                self.assert_hidden_flags_rejected(self.run_cli("verify"), 2)
                self.clear_index_flags()
                self.assertEqual(0, self.run_cli("verify").returncode)
        self.assertEqual(0, self.run_cli("complete", "task-1").returncode)

    def test_submodule_hidden_flags_report_paths_and_manual_recovery(self):
        library = self.add_clean_submodule()
        self.ready()
        for flags in (("--assume-unchanged",), ("--skip-worktree",),
                      ("--assume-unchanged", "--skip-worktree")):
            with self.subTest(flags=flags):
                self.set_index_flags(flags, "library.txt", library)
                report = self.run_cli("report", "task-1", "--format", "json")
                self.assert_hidden_flags_rejected(report, 1, "library.txt")
                self.assertIn("vendor/library", report.stdout)
                self.assert_hidden_flags_rejected(self.run_cli("verify"), 2, "library.txt")
                self.clear_index_flags("library.txt", library)
                self.assertEqual(0, self.run_cli("verify").returncode)
        self.assertEqual(0, self.run_cli("complete", "task-1").returncode)

    def test_staging_same_worktree_bytes_invalidates_until_reverification(self):
        source = self.workspace / "src" / "feature.py"
        source.parent.mkdir()
        source.write_text("value = 1\n", encoding="utf-8")
        self.initialize_git_repository()
        source.write_text("value = 2\n", encoding="utf-8")
        self.ready()
        subprocess.run(["git", "add", "src/feature.py"], cwd=self.workspace, check=True)

        rejected = self.run_cli("complete", "task-1")
        self.assertEqual(1, rejected.returncode, rejected.stderr)
        self.assertIn("stale evidence", rejected.stderr)
        self.assertIn("src/feature.py", rejected.stderr)
        self.assertEqual(0, self.run_cli("verify").returncode)
        self.assertEqual(0, self.run_cli("complete", "task-1").returncode)

    def test_empty_commit_invalidates_until_reverification_without_scope_regression(self):
        self.initialize_git_repository()
        self.ready()
        subprocess.run(["git", "commit", "--allow-empty", "-m", "new head"],
                       cwd=self.workspace, check=True, capture_output=True)
        rejected = self.run_cli("complete", "task-1")
        self.assertEqual(1, rejected.returncode)
        self.assertIn("HEAD changed", rejected.stderr)
        self.assertEqual(0, self.run_cli("verify").returncode)
        self.assertEqual(0, self.run_cli("complete", "task-1").returncode)

    def test_reports_escape_untrusted_instruction_and_summary(self):
        payload = "Observed\n- FORGED *[link]*\x1b[31m\x85 end"
        tasks = fixtures.base_tasks(check_type="manual")
        tasks["tasks"][0]["acceptance"][0]["instruction"] = payload
        self.write_json("tasks.json", tasks)
        self.assertEqual(0, self.run_cli("next").returncode)
        recorded = self.run_cli("record", "task-1", "check-1", "--result", "passed", "--summary", payload)
        self.assertEqual(0, recorded.returncode, recorded.stderr)
        text = self.run_cli("report", "task-1", "--format", "text")
        markdown = self.run_cli("report", "task-1", "--format", "markdown")
        data = self.run_cli("report", "task-1", "--format", "json")
        for output in (text, markdown, data):
            self.assertEqual(0, output.returncode, output.stderr)
            self.assertNotIn("\x1b", output.stdout)
            self.assertNotIn("\x85", output.stdout)
            self.assertNotIn("\n- FORGED", output.stdout)
        self.assertIn(r"Observed\n- FORGED *[link]*\x1b[31m", text.stdout)
        self.assertIn(r"Observed\\n- FORGED \*\[link\]\*\\x1b\[31m", markdown.stdout)
        parsed = json.loads(data.stdout)
        self.assertEqual(payload, parsed["checks"][0]["instruction"])
        self.assertEqual(payload, parsed["checks"][0]["summary"])

    def test_corrupt_evidence_has_same_exit_code_in_every_report_and_complete(self):
        self.ready()
        check = self.read_tasks()["tasks"][0]["acceptance"][0]
        (self.workspace / check["latest_evidence"]).write_text("{}\n", encoding="utf-8")
        for output_format in ("text", "json", "markdown"):
            report = self.run_cli("report", "task-1", "--format", output_format)
            self.assertEqual(2, report.returncode, report.stderr)
            if output_format == "json":
                self.assertFalse(json.loads(report.stdout)["ready"])
                self.assertEqual(2, json.loads(report.stdout)["exit_code"])
        self.assertEqual(2, self.run_cli("complete", "task-1").returncode)

    def test_migrate_released_v2_state_with_v3_subject_evidence_preserves_history(self):
        self.initialize_git_repository()
        self.ready()
        tasks = self.read_tasks()
        task = tasks["tasks"][0]
        baseline = task["git_baseline"]
        check = task["acceptance"][0]
        path = self.workspace / check["latest_evidence"]
        evidence = json.loads(path.read_text(encoding="utf-8"))
        for key in ("source_snapshot", "source_after", "contract_fingerprint", "attempt", "run_reason"):
            evidence.pop(key, None)
        evidence["verification_subject"] = fixtures.legacy_verification_subject()
        path.write_text(json.dumps(evidence), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        check["latest_evidence_sha256"] = digest
        task.pop("contract_baseline")
        tasks["schema_version"] = 2
        config = fixtures.base_config()
        config["schema_version"] = config["policy"]["schema_version"] = 2
        self.write_json("config.json", config)
        self.write_json("tasks.json", tasks)

        migrated = self.run_cli("migrate", "--note", "preserve released evidence history")
        self.assertEqual(0, migrated.returncode, migrated.stderr)
        current = self.read_tasks()["tasks"][0]
        self.assertEqual(baseline, current["git_baseline"])
        self.assertEqual("unverified", current["acceptance"][0]["status"])
        self.assertIsNone(current["acceptance"][0]["latest_evidence"])
        self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(1, self.run_cli("complete", "task-1").returncode)
        self.assertEqual(0, self.run_cli("verify").returncode)
        self.assertEqual(0, self.run_cli("complete", "task-1").returncode)


    def test_released_browser_failure_history_remains_readable(self):
        self.write_json("tasks.json", fixtures.base_tasks(check_type="browser"))
        self.assertEqual(0, self.run_cli("next").returncode)
        failed = self.run_cli("record", "task-1", "check-1", "--result", "failed", "--summary", "observed failure")
        self.assertEqual(1, failed.returncode, failed.stderr)
        tasks = self.read_tasks()
        check = tasks["tasks"][0]["acceptance"][0]
        path = self.workspace / check["latest_evidence"]
        evidence = json.loads(path.read_text(encoding="utf-8"))
        evidence.pop("source_snapshot")
        evidence["provenance"] = "browser-tool"
        for version in (2, 3):
            with self.subTest(schema=version):
                evidence["schema_version"] = version
                path.write_text(json.dumps(evidence), encoding="utf-8")
                check["latest_evidence_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                self.write_json("tasks.json", tasks)
                self.assertEqual(0, self.run_cli("doctor").returncode)
                handoff = self.run_cli("handoff")
                self.assertEqual(0, handoff.returncode, handoff.stderr)
                text = (self.harness_dir / "HANDOFF.md").read_text(encoding="utf-8")
                self.assertIn("Historical failure record", text)
                self.assertNotIn("Historical evidence invalid", text)


    def test_clean_submodule_commit_and_staged_gitlink_can_be_reverified(self):
        config = fixtures.base_config()
        config["policy"]["allowed_paths"].append("vendor/**")
        self.write_json("config.json", config)
        library = self.add_clean_submodule()
        self.ready()
        (library / "library.txt").write_text("Updated clean library\n", encoding="utf-8")
        subprocess.run(["git", "add", "library.txt"], cwd=library, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.test",
                        "commit", "-m", "library update"], cwd=library, check=True, capture_output=True)
        self.assertEqual(1, self.run_cli("complete", "task-1").returncode)
        verified = self.run_cli("verify")
        self.assertEqual(0, verified.returncode, verified.stderr)
        subprocess.run(["git", "add", "vendor/library"], cwd=self.workspace, check=True)
        self.assertEqual(1, self.run_cli("complete", "task-1").returncode)
        verified = self.run_cli("verify")
        self.assertEqual(0, verified.returncode, verified.stderr)
        completed = self.run_cli("complete", "task-1")
        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == "__main__":
    unittest.main()
