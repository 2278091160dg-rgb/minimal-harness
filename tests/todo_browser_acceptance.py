"""Real-browser acceptance for the dependency-free todo example."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[1] / "examples" / "todo")
parser.add_argument("--record", action="store_true", help="record each real browser observation and complete the three tasks")
args = parser.parse_args()
workspace = args.workspace.resolve()
artifacts = workspace / ".harness" / "artifacts"
if artifacts.is_symlink():
    raise SystemExit("Artifact directory must not be a symbolic link")
artifacts.mkdir(parents=True, exist_ok=True)
SCREENSHOT = artifacts / "todo-final.png"


def harness(*arguments):
    result = subprocess.run(
        [sys.executable, str(workspace / ".harness" / "harness.py"), *arguments],
        cwd=workspace, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    print(result.stdout, end="")


def begin(task_id):
    if not args.record:
        return
    state = json.loads((workspace / ".harness" / "tasks.json").read_text(encoding="utf-8"))
    if state["current_task_id"] is None:
        harness("next")
        state = json.loads((workspace / ".harness" / "tasks.json").read_text(encoding="utf-8"))
    if state["current_task_id"] != task_id:
        raise RuntimeError(f"Expected {task_id}; use a fresh Todo copy for the complete walkthrough")


def finish(page, task_id, check_id, summary):
    if not args.record:
        return
    screenshot = artifacts / f"{task_id}.png"
    page.screenshot(path=str(screenshot), full_page=True)
    assert screenshot.is_file() and screenshot.stat().st_size > 0
    harness("record", task_id, check_id, "--result", "passed", "--summary", summary,
            "--tool", "playwright", "--artifact", screenshot.relative_to(workspace).as_posix())
    harness("report", task_id)
    harness("complete", task_id)
    harness("handoff")


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

    begin("todo-add")
    page.get_by_label("待办内容").fill("验证 Harness")
    page.get_by_role("button", name="新增待办").click()
    item = page.locator(".todo-item", has_text="验证 Harness")
    assert item.count() == 1, "新增后应出现唯一一条待办"
    assert not item.locator('input[type="checkbox"]').is_checked(), "新待办应为未完成"

    finish(page, "todo-add", "add-in-browser", "Entered text and clicked Add; observed one unchecked matching item.")
    begin("todo-toggle")
    item.locator('input[type="checkbox"]').check()
    assert "completed" in (item.get_attribute("class") or ""), "勾选后应显示完成样式"
    assert item.locator(".todo-state").inner_text() == "已完成", "勾选后状态文字应更新"
    decoration = item.locator(".todo-text").evaluate(
        "element => getComputedStyle(element).textDecorationLine"
    )
    assert "line-through" in decoration, "勾选后计算样式应包含删除线"

    finish(page, "todo-toggle", "toggle-in-browser", "Checked the item; observed completed status and computed line-through style.")
    begin("todo-persist")
    page.reload(wait_until="networkidle")
    persisted = page.locator(".todo-item", has_text="验证 Harness")
    assert persisted.count() == 1, "刷新后待办应保留"
    assert persisted.locator('input[type="checkbox"]').is_checked(), "刷新后完成状态应保留"
    assert not console_errors, f"浏览器控制台不应出现错误: {console_errors}"
    assert not failed_resources, f"页面资源不应加载失败: {failed_resources}"
    assert not failed_requests, f"页面请求不应在网络层失败: {failed_requests}"

    finish(page, "todo-persist", "persist-in-browser", "Reloaded the page; observed preserved content and checked completion state.")
    page.screenshot(path=str(SCREENSHOT), full_page=True)
    assert SCREENSHOT.is_file() and SCREENSHOT.stat().st_size > 0, "验收截图必须是非空普通文件"
    page.close()
    browser.close()

print(f"PASS: add, toggle, and reload persistence verified; screenshot={SCREENSHOT}")
