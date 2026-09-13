import codecs
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "init_harness.py"
TEMPLATE = PROJECT_ROOT / "template" / ".harness"
MANIFEST = (
    "harness.py",
    "config.json",
    "tasks.json",
    "HANDOFF.md",
    "adapters/AGENTS.md.snippet",
    "adapters/CLAUDE.md.snippet",
    "adapters/GENERIC.md",
)


class InitHarnessCliTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.temp_root = Path(self.temp_dir.name).resolve()
        self.workspace = self.temp_root / "workspace"
        self.workspace.mkdir()

    def run_init(self, *args, workspace=None, script=SCRIPT):
        return subprocess.run(
            [
                sys.executable,
                str(script),
                "--workspace",
                str(workspace or self.workspace),
                *args,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def install(self, *args):
        result = self.run_init(*args)
        self.assertEqual(0, result.returncode, result.stderr)
        return result

    def read_tasks(self):
        return json.loads((self.workspace / ".harness" / "tasks.json").read_text(encoding="utf-8"))

    def write_tasks(self, value):
        (self.workspace / ".harness" / "tasks.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def set_current_task(self, status):
        tasks = self.read_tasks()
        config = json.loads((self.workspace / ".harness" / "config.json").read_text(encoding="utf-8"))
        task = tasks["tasks"][0]
        task["status"] = status
        task["started_at"] = "2026-09-13T00:00:00Z"
        task["policy_baseline"] = copy.deepcopy(config["policy"])
        task["git_baseline"] = {
            "version": 2,
            "captured_at": "2026-09-13T00:00:00Z",
            "available": False,
            "branch": None,
            "head": None,
            "dirty_paths": [],
            "worktree_fingerprints": {},
            "index_fingerprints": {},
        }
        tasks["current_task_id"] = task["id"]
        if status == "blocked":
            check = task["acceptance"][0]
            check["status"] = "failed"
            check["consecutive_failures"] = config["policy"]["max_consecutive_failures"]
            task["blocked_at"] = "2026-09-13T00:01:00Z"
            task["block_reason"] = "acceptance failed repeatedly"
        self.write_tasks(tasks)

    def snapshot_tree(self):
        return {
            path.relative_to(self.workspace).as_posix(): path.read_bytes()
            for path in self.workspace.rglob("*")
            if path.is_file() and not path.is_symlink()
        }

    def test_fresh_install_copies_fixed_manifest_and_merges_both_instruction_files(self):
        (self.workspace / "AGENTS.md").write_bytes("用户规则\r\n".encode("utf-8"))

        result = self.run_init()

        self.assertEqual(0, result.returncode, result.stderr)
        installed = self.workspace / ".harness"
        self.assertEqual(set(MANIFEST), {
            path.relative_to(installed).as_posix()
            for path in installed.rglob("*")
            if path.is_file()
        })
        for relative in MANIFEST:
            self.assertEqual((TEMPLATE / relative).read_bytes(), (installed / relative).read_bytes())
        agents = (self.workspace / "AGENTS.md").read_text(encoding="utf-8")
        claude = (self.workspace / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(agents.startswith("用户规则\n"))
        self.assertIn("<!-- minimal-harness:codex:start -->", agents)
        self.assertIn((TEMPLATE / "adapters/AGENTS.md.snippet").read_text(encoding="utf-8").strip(), agents)
        self.assertIn("<!-- minimal-harness:claude:start -->", claude)
        self.assertIn((TEMPLATE / "adapters/CLAUDE.md.snippet").read_text(encoding="utf-8").strip(), claude)
        self.assertIn("project-specific editing", result.stdout)
        self.assertIn("python3 .harness/harness.py doctor", result.stdout)

    def test_copied_runtime_passes_doctor_and_status_as_an_independent_subprocess(self):
        self.install()
        runtime = self.workspace / ".harness" / "harness.py"

        doctor = subprocess.run(
            [sys.executable, str(runtime), "--workspace", str(self.workspace), "doctor"],
            capture_output=True,
            text=True,
            check=False,
        )
        status = subprocess.run(
            [sys.executable, str(runtime), "--workspace", str(self.workspace), "status"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, doctor.returncode, doctor.stderr)
        self.assertIn("configuration valid", doctor.stdout)
        self.assertEqual(0, status.returncode, status.stderr)
        self.assertIn("Current task: None", status.stdout)

    def test_rerun_is_a_byte_preserving_no_op(self):
        self.install()
        before = self.snapshot_tree()

        result = self.run_init()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot_tree())
        self.assertIn("UNCHANGED .harness/harness.py", result.stdout)
        self.assertIn("UNCHANGED AGENTS.md", result.stdout)
        self.assertIn("UNCHANGED CLAUDE.md", result.stdout)

    def test_dry_run_reports_fresh_plan_without_writing(self):
        result = self.run_init("--dry-run")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({}, self.snapshot_tree())
        self.assertIn("DRY-RUN", result.stdout)
        self.assertIn("CREATE .harness/harness.py", result.stdout)
        self.assertIn("CREATE AGENTS.md", result.stdout)

    def test_single_agent_selection_only_merges_that_root_file(self):
        existing_claude = b"keep claude untouched\n"
        (self.workspace / "CLAUDE.md").write_bytes(existing_claude)

        result = self.run_init("--agent", "codex")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.workspace / "AGENTS.md").is_file())
        self.assertEqual(existing_claude, (self.workspace / "CLAUDE.md").read_bytes())
        self.assertTrue((self.workspace / ".harness" / "adapters" / "CLAUDE.md.snippet").is_file())
        self.assertNotIn("CLAUDE.md\n", result.stdout)

    def test_existing_install_retains_runtime_and_state_bytes_and_does_not_execute_destination_code(self):
        self.install()
        execution_marker = self.workspace / "destination-executed"
        destination_runtime = self.workspace / ".harness" / "harness.py"
        destination_runtime.write_text(
            f"from pathlib import Path\nPath({str(execution_marker)!r}).write_text('bad')\n",
            encoding="utf-8",
        )
        tasks_path = self.workspace / ".harness" / "tasks.json"
        tasks_path.write_bytes(tasks_path.read_bytes().replace(b"  \"tasks\"", b"    \"tasks\""))
        agents_path = self.workspace / "AGENTS.md"
        agents_path.write_text(
            agents_path.read_text(encoding="utf-8").replace("## Minimal Harness workflow", "outdated"),
            encoding="utf-8",
        )
        runtime_before = {
            relative: (self.workspace / ".harness" / relative).read_bytes()
            for relative in MANIFEST
        }

        result = self.run_init("--agent", "codex")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(runtime_before, {
            relative: (self.workspace / ".harness" / relative).read_bytes()
            for relative in MANIFEST
        })
        self.assertFalse(execution_marker.exists())
        self.assertIn("UPDATE AGENTS.md", result.stdout)

    def test_utf8_bom_crlf_and_bytes_outside_an_updated_block_are_preserved(self):
        prefix = codecs.BOM_UTF8 + "用户规则\r\n\r\n".encode("utf-8")
        suffix = b"\r\nTail bytes\r\n"
        old = (
            b"<!-- minimal-harness:codex:start -->\r\n"
            b"old managed text\r\n"
            b"<!-- minimal-harness:codex:end -->"
        )
        (self.workspace / "AGENTS.md").write_bytes(prefix + old + suffix)

        result = self.run_init("--agent", "codex")

        self.assertEqual(0, result.returncode, result.stderr)
        updated = (self.workspace / "AGENTS.md").read_bytes()
        self.assertTrue(updated.startswith(prefix))
        self.assertTrue(updated.endswith(suffix))
        self.assertIn(b"<!-- minimal-harness:codex:start -->\r\n", updated)
        self.assertNotIn(b"\n", updated.replace(b"\r\n", b""))

    def test_malformed_or_unexpected_markers_reject_the_whole_fresh_operation(self):
        start = "<!-- minimal-harness:codex:start -->"
        end = "<!-- minimal-harness:codex:end -->"
        cases = {
            "partial": f"text\n{start}\n",
            "duplicate": f"{start}\na\n{end}\n{start}\nb\n{end}\n",
            "reversed": f"{end}\ntext\n{start}\n",
            "nested": f"{start}\na\n{start}\nb\n{end}\n{end}\n",
            "unexpected": "<!-- minimal-harness:claude:start -->\n",
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                case_workspace = self.temp_root / name
                case_workspace.mkdir()
                agents = case_workspace / "AGENTS.md"
                agents.write_text(content, encoding="utf-8")
                before = agents.read_bytes()

                result = self.run_init("--agent", "codex", workspace=case_workspace)

                self.assertEqual(2, result.returncode)
                self.assertIn("marker", result.stderr.lower())
                self.assertEqual(before, agents.read_bytes())
                self.assertFalse((case_workspace / ".harness").exists())

    def test_non_utf8_instruction_file_rejects_before_any_write(self):
        agents = self.workspace / "AGENTS.md"
        agents.write_bytes(b"invalid: \xff\xfe")

        result = self.run_init("--agent", "codex")

        self.assertEqual(2, result.returncode)
        self.assertIn("utf-8", result.stderr.lower())
        self.assertEqual(b"invalid: \xff\xfe", agents.read_bytes())
        self.assertFalse((self.workspace / ".harness").exists())

    def test_missing_runtime_file_or_malformed_existing_state_rejects_without_instruction_writes(self):
        self.install()
        for name, mutate in (
            ("missing", lambda root: (root / ".harness" / "HANDOFF.md").unlink()),
            ("malformed", lambda root: (root / ".harness" / "tasks.json").write_text("{bad", encoding="utf-8")),
        ):
            with self.subTest(name=name):
                case_workspace = self.temp_root / f"existing-{name}"
                shutil.copytree(self.workspace, case_workspace)
                mutate(case_workspace)
                (case_workspace / "AGENTS.md").unlink()
                before = self._tree_bytes(case_workspace)

                result = self.run_init("--agent", "codex", workspace=case_workspace)

                self.assertEqual(2, result.returncode)
                self.assertEqual(before, self._tree_bytes(case_workspace))
                self.assertFalse((case_workspace / "AGENTS.md").exists())

    def test_existing_v1_state_is_rejected_without_upgrade(self):
        self.install()
        tasks = self.read_tasks()
        tasks["schema_version"] = 1
        self.write_tasks(tasks)
        before = self.snapshot_tree()

        result = self.run_init()

        self.assertEqual(2, result.returncode)
        self.assertIn("schema_version", result.stderr)
        self.assertIn("no automatic upgrade", result.stderr.lower())
        self.assertEqual(before, self.snapshot_tree())

    def test_non_file_instruction_destination_rejects_before_any_write(self):
        (self.workspace / "AGENTS.md").mkdir()

        result = self.run_init("--agent", "codex")

        self.assertEqual(2, result.returncode)
        self.assertIn("regular file", result.stderr.lower())
        self.assertFalse((self.workspace / ".harness").exists())

    def test_symlinked_destination_and_internal_ancestor_are_rejected_before_writes(self):
        outside = self.temp_root / "outside"
        outside.mkdir()
        outside_file = outside / "instructions"
        outside_file.write_text("outside\n", encoding="utf-8")
        try:
            (self.workspace / "AGENTS.md").symlink_to(outside_file)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")

        result = self.run_init("--agent", "codex")

        self.assertEqual(2, result.returncode)
        self.assertIn("symlink", result.stderr.lower())
        self.assertEqual("outside\n", outside_file.read_text(encoding="utf-8"))
        self.assertFalse((self.workspace / ".harness").exists())

        (self.workspace / "AGENTS.md").unlink()
        harness = self.workspace / ".harness"
        harness.mkdir()
        (harness / "adapters").symlink_to(outside, target_is_directory=True)
        result = self.run_init("--agent", "codex")
        self.assertEqual(2, result.returncode)
        self.assertIn("symlink", result.stderr.lower())
        self.assertFalse((self.workspace / "AGENTS.md").exists())

    def test_symlinked_workspace_itself_is_rejected(self):
        workspace_link = self.temp_root / "workspace-link"
        try:
            workspace_link.symlink_to(self.workspace, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")

        result = self.run_init("--agent", "codex", workspace=workspace_link)

        self.assertEqual(2, result.returncode)
        self.assertIn("symlink", result.stderr.lower())
        self.assertEqual({}, self.snapshot_tree())

    def test_symlinked_lexical_workspace_ancestor_is_rejected(self):
        real_parent = self.temp_root / "real-parent"
        real_parent.mkdir()
        real_workspace = real_parent / "project"
        real_workspace.mkdir()
        linked_parent = self.temp_root / "linked-parent"
        try:
            linked_parent.symlink_to(real_parent, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")

        result = self.run_init("--agent", "codex", workspace=linked_parent / "project")

        self.assertEqual(2, result.returncode)
        self.assertIn("symlink", result.stderr.lower())
        self.assertEqual({}, self._tree_bytes(real_workspace))

    def test_symlink_before_parent_traversal_is_rejected_in_real_and_dry_run_modes(self):
        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run):
                case_root = self.temp_root / f"dotdot-{dry_run}"
                direct_workspace = case_root / "workspace"
                resolved_workspace = case_root / "outside" / "workspace"
                child = case_root / "outside" / "child"
                direct_workspace.mkdir(parents=True)
                resolved_workspace.mkdir(parents=True)
                child.mkdir()
                alias = case_root / "alias"
                try:
                    alias.symlink_to(child, target_is_directory=True)
                except (OSError, NotImplementedError) as exc:
                    self.skipTest(f"symlinks unavailable: {exc}")
                requested = alias / ".." / "workspace"
                args = ("--agent", "codex", "--dry-run") if dry_run else ("--agent", "codex")

                result = self.run_init(*args, workspace=requested)

                self.assertEqual(2, result.returncode)
                self.assertIn("symlink", result.stderr.lower())
                self.assertEqual({}, self._tree_bytes(direct_workspace))
                self.assertEqual({}, self._tree_bytes(resolved_workspace))

    def test_unsafe_source_entry_and_extra_source_state_are_not_installed(self):
        staged_repo = self.temp_root / "staged-repo"
        (staged_repo / "scripts").mkdir(parents=True)
        shutil.copy2(SCRIPT, staged_repo / "scripts" / "init_harness.py")
        shutil.copytree(TEMPLATE, staged_repo / "template" / ".harness")
        staged_template = staged_repo / "template" / ".harness"
        (staged_template / "evidence").mkdir()
        (staged_template / "evidence" / "private.json").write_text("secret", encoding="utf-8")
        safe_workspace = self.temp_root / "safe-source-workspace"
        safe_workspace.mkdir()

        safe = self.run_init(workspace=safe_workspace, script=staged_repo / "scripts" / "init_harness.py")

        self.assertEqual(0, safe.returncode, safe.stderr)
        self.assertFalse((safe_workspace / ".harness" / "evidence").exists())

        unsafe_workspace = self.temp_root / "unsafe-source-workspace"
        unsafe_workspace.mkdir()
        source_file = staged_template / "adapters" / "GENERIC.md"
        source_file.unlink()
        source_file.symlink_to(staged_template / "HANDOFF.md")

        unsafe = self.run_init(workspace=unsafe_workspace, script=staged_repo / "scripts" / "init_harness.py")

        self.assertEqual(2, unsafe.returncode)
        self.assertIn("source", unsafe.stderr.lower())
        self.assertIn("symlink", unsafe.stderr.lower())
        self.assertEqual({}, self._tree_bytes(unsafe_workspace))

    def test_existing_install_and_dry_run_do_not_create_source_bytecode_cache(self):
        staged_repo = self.temp_root / "bytecode-repo"
        (staged_repo / "scripts").mkdir(parents=True)
        shutil.copy2(SCRIPT, staged_repo / "scripts" / "init_harness.py")
        shutil.copytree(TEMPLATE, staged_repo / "template" / ".harness")
        shutil.rmtree(staged_repo / "template" / ".harness" / "__pycache__", ignore_errors=True)
        case_workspace = self.temp_root / "bytecode-workspace"
        case_workspace.mkdir()
        staged_script = staged_repo / "scripts" / "init_harness.py"
        first = self.run_init(workspace=case_workspace, script=staged_script)
        self.assertEqual(0, first.returncode, first.stderr)

        result = self.run_init("--dry-run", workspace=case_workspace, script=staged_script)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((staged_repo / "template" / ".harness" / "__pycache__").exists())

    def test_malformed_typed_state_is_exit_two_without_writes_or_traceback(self):
        cases = {
            "current-list": lambda tasks: tasks.__setitem__("current_task_id", []),
            "current-dict": lambda tasks: tasks.__setitem__("current_task_id", {}),
            "status-list": lambda tasks: tasks["tasks"][0].__setitem__("status", []),
            "status-dict": lambda tasks: tasks["tasks"][0].__setitem__("status", {}),
        }
        for name, mutate in cases.items():
            for dry_run in (False, True):
                with self.subTest(name=name, dry_run=dry_run):
                    case_workspace = self.temp_root / f"typed-{name}-{dry_run}"
                    case_workspace.mkdir()
                    installed = self.run_init(workspace=case_workspace)
                    self.assertEqual(0, installed.returncode, installed.stderr)
                    tasks_path = case_workspace / ".harness" / "tasks.json"
                    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
                    mutate(tasks)
                    tasks_path.write_text(
                        json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    before = self._tree_bytes(case_workspace)
                    args = ("--dry-run",) if dry_run else ()

                    result = self.run_init(*args, workspace=case_workspace)

                    self.assertEqual(2, result.returncode)
                    self.assertIn("invalid existing harness state", result.stderr.lower())
                    self.assertNotIn("traceback", result.stderr.lower())
                    self.assertEqual(before, self._tree_bytes(case_workspace))

    def test_active_or_blocked_state_allows_exact_no_op_but_gates_real_and_dry_run_changes(self):
        for status in ("in_progress", "blocked"):
            with self.subTest(status=status):
                case_workspace = self.temp_root / status
                case_workspace.mkdir()
                first = self.run_init(workspace=case_workspace)
                self.assertEqual(0, first.returncode, first.stderr)
                original_workspace = self.workspace
                self.workspace = case_workspace
                try:
                    self.set_current_task(status)
                finally:
                    self.workspace = original_workspace

                noop_before = self._tree_bytes(case_workspace)
                noop = self.run_init(workspace=case_workspace)
                self.assertEqual(0, noop.returncode, noop.stderr)
                self.assertEqual(noop_before, self._tree_bytes(case_workspace))

                agents = case_workspace / "AGENTS.md"
                agents.write_text(
                    agents.read_text(encoding="utf-8").replace("## Minimal Harness workflow", "stale block"),
                    encoding="utf-8",
                )
                changed_before = self._tree_bytes(case_workspace)

                blocked = self.run_init("--agent", "codex", workspace=case_workspace)
                dry_run = self.run_init("--agent", "codex", "--dry-run", workspace=case_workspace)

                self.assertEqual(1, blocked.returncode)
                self.assertEqual(1, dry_run.returncode)
                self.assertIn("active or blocked", blocked.stderr.lower())
                self.assertIn("UPDATE AGENTS.md", dry_run.stdout)
                self.assertEqual(changed_before, self._tree_bytes(case_workspace))

    def test_missing_workspace_is_an_input_error(self):
        missing = self.temp_root / "missing-workspace"

        result = self.run_init(workspace=missing)

        self.assertEqual(2, result.returncode)
        self.assertIn("already exist", result.stderr.lower())
        self.assertFalse(missing.exists())

    @staticmethod
    def _tree_bytes(root):
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()
        }


if __name__ == "__main__":
    unittest.main()
