"""Initialization must preserve an existing project and its agent instructions."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE = Path(__file__).resolve().parents[1] / "template" / ".harness" / "harness_init.py"
ROOT_LICENSE = Path(__file__).resolve().parents[1] / "LICENSE"
TEMPLATE_LICENSE = Path(__file__).resolve().parents[1] / "template" / ".harness" / "LICENSE"


class InitializeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.workspace = self.root / "project"
        self.workspace.mkdir()
        for name in ("harness.py", "harness_init.py", "harness_runner.py"):
            (self.source / name).write_text("# trusted runtime: " + name, encoding="utf-8")
        (self.source / "LICENSE").write_bytes(b"fixture distribution license\n")
        if not MODULE.exists():
            self.fail("safe init is not implemented yet")
        spec = importlib.util.spec_from_file_location("harness_init", MODULE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def init(self, **kwargs):
        return self.module.initialize(self.workspace, source_dir=self.source, **kwargs)

    def contents(self):
        return {
            path.relative_to(self.workspace).as_posix(): path.read_bytes()
            for path in self.workspace.rglob("*") if path.is_file()
        }

    def test_dry_run_leaves_project_byte_for_byte_unchanged(self):
        (self.workspace / "AGENTS.md").write_bytes(b"User instructions\r\n")
        before = self.contents()
        summary = self.init(agent="codex", dry_run=True)
        self.assertEqual(before, self.contents())
        self.assertFalse((self.workspace / ".harness").exists())
        self.assertIn("AGENTS.md", summary)

    def test_initializes_empty_tasks_and_unconfigured_commands(self):
        self.init()
        harness = self.workspace / ".harness"
        config = json.loads((harness / "config.json").read_text())
        state = json.loads((harness / "tasks.json").read_text())
        self.assertEqual(state, {"schema_version": 3, "current_task_id": None, "tasks": []})
        self.assertEqual(config["commands"], {"setup": None, "start": None, "check": None})
        self.assertTrue(config["policy"]["require_git_for_completion"])
        for name in ("harness.py", "harness_init.py", "harness_runner.py"):
            self.assertEqual((harness / name).read_bytes(), (self.source / name).read_bytes())
        self.assertEqual((harness / "LICENSE").read_bytes(), b"fixture distribution license\n")
        self.assertFalse((self.workspace / "AGENTS.md").exists())

    def test_template_carries_root_license_unchanged(self):
        self.assertEqual(TEMPLATE_LICENSE.read_bytes(), ROOT_LICENSE.read_bytes())

    def test_fresh_init_does_not_replace_workspace_root_license(self):
        project_license = self.workspace / "LICENSE"
        project_license.write_bytes(b"project's own license\n")

        self.init()

        self.assertEqual(project_license.read_bytes(), b"project's own license\n")
        self.assertEqual(
            (self.workspace / ".harness" / "LICENSE").read_bytes(),
            b"fixture distribution license\n",
        )

    def test_appends_instructions_once_and_preserves_existing_bytes(self):
        instructions = self.workspace / "AGENTS.md"
        original = b"# User rules\r\nDo not rewrite these.\r\n"
        instructions.write_bytes(original)
        self.init(agent="codex")
        result = instructions.read_bytes()
        self.assertTrue(result.startswith(original))
        self.assertIn(b"HANDOFF.md", result)
        before = self.contents()
        self.init(agent="codex")
        self.assertEqual(before, self.contents())

    def test_existing_tasks_and_configuration_survive_reinitialization(self):
        self.init()
        config = self.workspace / ".harness" / "config.json"
        value = json.loads(config.read_text())
        value["project_name"] = "Personalized project"
        config.write_text(json.dumps(value), encoding="utf-8")
        state_file = self.workspace / ".harness" / "tasks.json"
        value = json.loads(state_file.read_text())
        value["tasks"] = [{"id": "preserve-my-task"}]
        state_file.write_text(json.dumps(value), encoding="utf-8")
        before = self.contents()
        self.init()
        self.assertEqual(before, self.contents())

    def test_conflicting_instructions_fail_before_any_bootstrap_write(self):
        (self.workspace / "CLAUDE.md").write_text(
            "User text\n<!-- minimal-harness:start -->\nCustom block\n"
            "<!-- minimal-harness:end -->\n", encoding="utf-8"
        )
        before = self.contents()
        with self.assertRaisesRegex(ValueError, "conflict"):
            self.init(agent="claude")
        self.assertEqual(before, self.contents())

    def test_partial_installation_is_not_overwritten(self):
        harness = self.workspace / ".harness"
        harness.mkdir()
        (harness / "tasks.json").write_bytes(b"my existing task data")
        before = self.contents()
        with self.assertRaises(ValueError):
            self.init(agent="codex")
        self.assertEqual(before, self.contents())

    def test_existing_modified_runtime_is_not_replaced(self):
        self.init()
        (self.workspace / ".harness" / "harness.py").write_bytes(b"my patched runtime")
        before = self.contents()
        with self.assertRaises(ValueError):
            self.init()
        self.assertEqual(before, self.contents())

    def test_existing_modified_license_is_not_replaced(self):
        self.init()
        (self.workspace / ".harness" / "LICENSE").write_bytes(b"user replacement\n")
        before = self.contents()
        with self.assertRaisesRegex(ValueError, "LICENSE"):
            self.init()
        self.assertEqual(before, self.contents())

    def test_symlinked_host_instructions_are_rejected_without_external_write(self):
        external = self.root / "external.md"
        external.write_bytes(b"external original")
        try:
            (self.workspace / "AGENTS.md").symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("symlink support unavailable")
        with self.assertRaises(ValueError):
            self.init(agent="generic")
        self.assertEqual(external.read_bytes(), b"external original")
        self.assertFalse((self.workspace / ".harness").exists())

    def test_symlinked_harness_directory_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        try:
            (self.workspace / ".harness").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink support unavailable")
        with self.assertRaises(ValueError):
            self.init()
        self.assertEqual(list(outside.iterdir()), [])

    def test_missing_runtime_file_fails_without_partial_install(self):
        (self.source / "harness_runner.py").unlink()
        with self.assertRaises((OSError, ValueError)):
            self.init()
        self.assertFalse((self.workspace / ".harness").exists())

    def test_missing_source_license_fails_without_partial_install(self):
        (self.source / "LICENSE").unlink()
        with self.assertRaises((OSError, ValueError)):
            self.init(agent="codex")
        self.assertEqual(self.contents(), {})
        self.assertFalse((self.workspace / ".harness").exists())

    def test_existing_install_missing_license_requires_explicit_upgrade(self):
        self.init()
        (self.workspace / ".harness" / "LICENSE").unlink()
        before = self.contents()
        with self.assertRaisesRegex(ValueError, "LICENSE"):
            self.init(agent="codex")
        self.assertEqual(before, self.contents())

    def test_crlf_managed_block_is_idempotent(self):
        instructions = self.workspace / "AGENTS.md"
        original = ("User instructions\n" + self.module.agent_instructions()).replace("\n", "\r\n")
        instructions.write_bytes(original.encode())
        self.init(agent="generic")
        self.assertEqual(instructions.read_bytes(), original.encode())
        self.init(agent="generic")
        self.assertEqual(instructions.read_bytes(), original.encode())

    def test_new_managed_block_uses_existing_crlf_style(self):
        instructions = self.workspace / "AGENTS.md"
        instructions.write_bytes(b"User instructions\r\n")
        self.init(agent="codex")
        self.assertNotIn(b"\n", instructions.read_bytes().replace(b"\r\n", b""))

    def test_missing_handoff_is_rejected_as_partial_installation(self):
        self.init()
        (self.workspace / ".harness" / "HANDOFF.md").unlink()
        before = self.contents()
        with self.assertRaises(ValueError):
            self.init(agent="codex")
        self.assertEqual(before, self.contents())

    def test_partial_write_rolls_back_owned_files_and_allows_retry(self):
        original_open = Path.open

        class InterruptedFile:
            def __init__(self, handle):
                self.handle = handle

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.handle.close()

            def fileno(self):
                return self.handle.fileno()

            def write(self, payload):
                self.handle.write(payload[:3])
                self.handle.flush()
                raise OSError("injected disk-full after a partial write")

        def partial_open(path, mode="r", *args, **kwargs):
            handle = original_open(path, mode, *args, **kwargs)
            if mode == "xb" and path.name == "config.json":
                return InterruptedFile(handle)
            return handle

        with mock.patch.object(Path, "open", partial_open):
            with self.assertRaisesRegex(OSError, "disk-full"):
                self.init(agent="codex")
        self.assertEqual(self.contents(), {})
        self.assertFalse((self.workspace / ".harness").exists())
        self.init(agent="codex")
        self.assertTrue((self.workspace / ".harness" / "tasks.json").is_file())


if __name__ == "__main__":
    unittest.main()
