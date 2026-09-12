"""Real-browser acceptance for the dependency-free todo example."""

from pathlib import Path

from playwright.sync_api import sync_playwright


SCREENSHOT = Path("/tmp/minimal-harness-todo-acceptance.png")
SCREENSHOT.unlink(missing_ok=True)


with sync_playwright() as playwright:
    browser = playwright.chromium.connect_over_cdp("http://127.0.0.1:9344")
    context = browser.contexts[0]
    page = context.new_page()
    console_errors = []
    failed_resources = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on(
        "response",
        lambda response: failed_resources.append(f"{response.status} {response.url}")
        if response.status >= 400
        else None,
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

    item.locator('input[type="checkbox"]').check()
    assert "completed" in (item.get_attribute("class") or ""), "勾选后应显示完成样式"
    assert item.locator(".todo-state").inner_text() == "已完成", "勾选后状态文字应更新"
    decoration = item.locator(".todo-text").evaluate(
        "element => getComputedStyle(element).textDecorationLine"
    )
    assert "line-through" in decoration, "勾选后计算样式应包含删除线"

    page.reload(wait_until="networkidle")
    persisted = page.locator(".todo-item", has_text="验证 Harness")
    assert persisted.count() == 1, "刷新后待办应保留"
    assert persisted.locator('input[type="checkbox"]').is_checked(), "刷新后完成状态应保留"
    assert not console_errors, f"浏览器控制台不应出现错误: {console_errors}"
    assert not failed_resources, f"页面资源不应加载失败: {failed_resources}"

    page.screenshot(path=str(SCREENSHOT), full_page=True)
    assert SCREENSHOT.is_file() and SCREENSHOT.stat().st_size > 0, "验收截图必须是非空普通文件"
    page.close()
    browser.close()

print(f"PASS: add, toggle, and reload persistence verified; screenshot={SCREENSHOT}")
