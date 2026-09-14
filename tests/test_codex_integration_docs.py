import re
import unittest
from pathlib import Path
from typing import Optional
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
ENGLISH_GUIDE = ROOT / "docs" / "codex-integration-guide.md"
CHINESE_GUIDE = ROOT / "docs" / "codex-integration-guide.zh-CN.md"


def markdown_links(document: Path) -> list[str]:
    text = document.read_text(encoding="utf-8")
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)


def local_link_target(document: Path, raw_target: str) -> Optional[Path]:
    target = raw_target.strip().split("#", 1)[0]
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    return (document.parent / unquote(target)).resolve()


def harness_commands(document: Path) -> set[str]:
    text = document.read_text(encoding="utf-8")
    return set(re.findall(r"^python3 \.harness/harness\.py .+$", text, flags=re.MULTILINE))


class CodexIntegrationDocumentationTest(unittest.TestCase):
    def test_primary_navigation_links_to_bilingual_guides(self):
        expected_links = {
            ROOT / "README.md": "docs/codex-integration-guide.md",
            ROOT / "README.zh-CN.md": "docs/codex-integration-guide.zh-CN.md",
            ROOT / "docs" / "README.md": "codex-integration-guide.md",
            ROOT / "docs" / "README.zh-CN.md": "codex-integration-guide.zh-CN.md",
        }

        for document, target in expected_links.items():
            with self.subTest(document=document.name):
                self.assertIn(f"]({target})", document.read_text(encoding="utf-8"))

    def test_guides_share_version_sections_and_runnable_commands(self):
        english = ENGLISH_GUIDE.read_text(encoding="utf-8")
        chinese = CHINESE_GUIDE.read_text(encoding="utf-8")

        for text in (english, chinese):
            self.assertIn("v0.2.0-beta.2", text)
            self.assertIn("schema v3", text)
            self.assertIn("quickstart", text)
            self.assertIn("Todo", text)

        matching_sections = (
            ("Understand it in one sentence", "先用一句话理解它"),
            ("Is it valuable for Skill development?", "它对 Skill 开发是否有价值"),
            ("Divide responsibility with Codex Goal and Plan Mode", "与 Codex Goal 和 Plan Mode 怎么分工"),
            ("Recommended combination for a large project", "大型项目的推荐组合"),
            ("Why a large project needs a single writer", "为什么大型项目必须指定单一写入者"),
            ("Runnable walkthrough 1: command acceptance and stale evidence", "可运行演练一：命令验收与证据失效"),
            ("Runnable walkthrough 2: Todo browser evidence", "可运行演练二：Todo 浏览器证据"),
            ("Three adoption depths", "三种接入深度"),
            ("Three anti-patterns to avoid", "三个必须避免的反例"),
            ("Completion checklist", "完成检查表"),
            ("Further reading", "进一步阅读"),
        )
        for english_heading, chinese_heading in matching_sections:
            with self.subTest(section=english_heading):
                self.assertIn(f"## {english_heading}", english)
                self.assertIn(f"## {chinese_heading}", chinese)

        official_plan_mode_doc = "https://learn.chatgpt.com/guides/best-practices"
        self.assertIn(official_plan_mode_doc, english)
        self.assertIn(official_plan_mode_doc, chinese)

        expected_commands = {
            "python3 .harness/harness.py doctor",
            "python3 .harness/harness.py task add --from greeting.task.json",
            "python3 .harness/harness.py next",
            "python3 .harness/harness.py verify",
            "python3 .harness/harness.py report greeting",
            "python3 .harness/harness.py complete greeting",
            "python3 .harness/harness.py handoff",
        }
        self.assertEqual(harness_commands(ENGLISH_GUIDE), expected_commands)
        self.assertEqual(harness_commands(CHINESE_GUIDE), expected_commands)

    def test_guides_preserve_single_writer_and_reverification_boundaries(self):
        english = ENGLISH_GUIDE.read_text(encoding="utf-8")
        chinese = CHINESE_GUIDE.read_text(encoding="utf-8")

        for phrase in (
            "single executor",
            "single integration writer",
            "reverify after merge",
            "not native multi-agent orchestration",
        ):
            self.assertIn(phrase, english)
        for phrase in ("单执行者", "单一集成写入者", "合并后重验", "不是原生多智能体编排"):
            self.assertIn(phrase, chinese)

    def test_guide_local_links_and_referenced_examples_exist(self):
        documents = (
            ENGLISH_GUIDE,
            CHINESE_GUIDE,
            ROOT / "README.md",
            ROOT / "README.zh-CN.md",
            ROOT / "docs" / "README.md",
            ROOT / "docs" / "README.zh-CN.md",
        )
        for document in documents:
            with self.subTest(document=document):
                for raw_target in markdown_links(document):
                    target = local_link_target(document, raw_target)
                    if target is not None:
                        self.assertTrue(target.exists(), f"{document}: broken link {raw_target}")

        referenced_paths = (
            "examples/quickstart/greeting.task.json",
            "examples/quickstart/tests/check_greeting.py",
            "examples/todo/AGENTS.md",
            "examples/todo/test.mjs",
            "tests/test_walkthrough.py",
            "tests/run_todo_walkthrough.py",
        )
        combined = ENGLISH_GUIDE.read_text(encoding="utf-8") + CHINESE_GUIDE.read_text(
            encoding="utf-8"
        )
        for relative_path in referenced_paths:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((ROOT / relative_path).is_file())
                self.assertIn(relative_path, combined)


if __name__ == "__main__":
    unittest.main()
