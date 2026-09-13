"""Real-browser acceptance for the dependency-free todo example."""

import argparse
import os
import tempfile
from pathlib import Path


DEFAULT_SCREENSHOT = Path(tempfile.gettempdir()) / "minimal-harness-todo-acceptance.png"


def run_browser(artifact_dir):
    from playwright.sync_api import sync_playwright

    screenshot = artifact_dir / "persist.png" if artifact_dir is not None else DEFAULT_SCREENSHOT
    outputs = (
        [artifact_dir / name for name in ("add.png", "toggle.png", "persist.png")]
        if artifact_dir is not None else [screenshot]
    )
    for output in outputs:
        output.unlink(missing_ok=True)

    with sync_playwright() as playwright:
        cdp_url = os.environ.get("HARNESS_CDP_URL")
        browser = (
            playwright.chromium.connect_over_cdp(cdp_url)
            if cdp_url
            else playwright.chromium.launch(headless=True)
        )
        context = browser.contexts[0] if cdp_url else browser.new_context()
        page = context.new_page()
        console_errors = []
        failed_resources = []
        failed_requests = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on(
            "response",
            lambda response: failed_resources.append(f"{response.status} {response.url}")
            if response.status >= 400
            else None,
        )
        page.on(
            "requestfailed",
            lambda request: failed_requests.append(
                f"{request.method} {request.url}: {request.failure or 'unknown failure'}"
            ),
        )
        cdp_session = context.new_cdp_session(page)
        cdp_session.send("Network.clearBrowserCache")

        page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")

        page.get_by_label("待办内容").fill("验证 Harness")
        page.get_by_role("button", name="新增待办").click()
        item = page.locator(".todo-item", has_text="验证 Harness")
        assert item.count() == 1, "新增后应出现唯一一条待办"
        assert not item.locator('input[type="checkbox"]').is_checked(), "新待办应为未完成"

        if artifact_dir is not None:
            page.screenshot(path=str(artifact_dir / "add.png"), full_page=True)

        item.locator('input[type="checkbox"]').check()
        assert "completed" in (item.get_attribute("class") or ""), "勾选后应显示完成样式"
        assert item.locator(".todo-state").inner_text() == "已完成", "勾选后状态文字应更新"
        decoration = item.locator(".todo-text").evaluate(
            "element => getComputedStyle(element).textDecorationLine"
        )
        assert "line-through" in decoration, "勾选后计算样式应包含删除线"

        if artifact_dir is not None:
            page.screenshot(path=str(artifact_dir / "toggle.png"), full_page=True)

        page.reload(wait_until="networkidle")
        persisted = page.locator(".todo-item", has_text="验证 Harness")
        assert persisted.count() == 1, "刷新后待办应保留"
        assert persisted.locator('input[type="checkbox"]').is_checked(), "刷新后完成状态应保留"
        assert not console_errors, f"浏览器控制台不应出现错误: {console_errors}"
        assert not failed_resources, f"页面资源不应加载失败: {failed_resources}"
        assert not failed_requests, f"页面请求不应在网络层失败: {failed_requests}"

        page.screenshot(path=str(screenshot), full_page=True)
        assert screenshot.is_file() and screenshot.stat().st_size > 0, "验收截图必须是非空普通文件"
        page.close()
        browser.close()

    for output in outputs:
        assert output.is_file() and output.stat().st_size > 0, f"missing browser artifact: {output}"
    print(f"PASS: add, toggle, and reload persistence verified; screenshot={screenshot}")
    if artifact_dir is not None:
        for output in outputs:
            print(f"ARTIFACT: {output}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir", type=Path,
        help="Save add.png, toggle.png and persist.png inside this directory.",
    )
    args = parser.parse_args(argv)
    artifact_dir = args.artifact_dir
    if artifact_dir is not None:
        try:
            artifact_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            parser.error(f"cannot create artifact directory: {exc}")
    run_browser(artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
