# Minimal AI Coding Harness

这是一套可复制到任意代码项目的最小 Harness。它不调用 AI，也不把“代码写完”当作“用户可用”；它把任务、单项执行、真实验证、证据门禁和跨会话交接连接成可检查的闭环。

Harness v2 只依赖 Python 3.9+ 标准库。Node.js 和 Playwright 只用于仓库自带示例及开发验收。

## 1. 安装或升级

新项目复制模板：

```bash
cp -R template/.harness /path/to/your-project/.harness
cd /path/to/your-project
```

Windows PowerShell 可使用：

```powershell
Copy-Item -Recurse template/.harness C:\path\to\project\.harness
Set-Location C:\path\to\project
py -3 .harness/harness.py doctor
```

已有 v1 状态先预览迁移：

```bash
python3 .harness/harness.py migrate --dry-run
python3 .harness/harness.py migrate
```

活动或阻塞中的 v1 任务无法证明旧 index baseline，迁移时必须显式确认断点：

```bash
python3 .harness/harness.py migrate --note "确认从当前 Git 状态重新建立 v2 baseline"
```

迁移会在 `.harness/migrations/` 保存原始 v1 配置、任务和哈希清单，不会改写历史 evidence。活动任务的 v1 passed 会降级为 `unverified`；已完成任务保留并标注为 legacy evidence。重复执行 migrate 是安全的。

## 2. 任务与配置

`.harness/tasks.json` 使用 schema v2。每个任务至少包含一个验收项：

- `command`：Harness 直接执行 argv。
- `browser`：Agent 使用真实浏览器执行。
- `manual`：人工观察或外部工具执行。

任务状态为 `pending / in_progress / blocked / done`；验收状态为 `not_run / passed / failed / unverified`。`unverified` 不等于通过。

`.harness/config.json` 同样使用 schema v2：

- `commands.setup/start/check` 必须是 argv 数组或 `null`，执行时不经过 shell。
- argv 中的 `{python}` 会安全替换为当前运行 Harness 的 Python 解释器，适合跨平台配置。
- `policy.allowed_paths` 使用分段 glob：`*` 只匹配一层，`**` 才能跨目录；模式必须是安全的 workspace 相对路径。
- `policy.require_git_for_completion` 默认为 `true`。无可信 Git baseline 时可以继续管理任务和 evidence，但不能 complete。
- `approval_required_operations` 是 Agent 与人的流程约束，不会拦截系统调用。

`allowed_paths` 也不是操作系统沙箱。Harness 只在 complete 时审计 Git 范围；需要隔离时仍应使用容器、受限账户或 Agent 平台权限。

模板中的检查命令示例：

```json
["{python}", "-m", "unittest", "discover", "-s", "tests"]
```

## 3. 固定工作循环

全局 `--workspace PATH` 必须位于子命令之前。每轮开始执行：

```bash
python3 .harness/harness.py doctor
python3 .harness/harness.py status
python3 .harness/harness.py next
```

`next` 只领取第一个 pending 任务，并冻结：

- Git branch、HEAD、工作树和 index 指纹；
- 失败阈值、允许路径、Git completion 策略和需审批操作。

预先脏的普通文件会记录类型、模式与内容指纹。若脏路径是 submodule 或其他无法用标准库完整指纹化的对象，`next` 会拒绝建立不完整 baseline；先清理该路径后再领取任务。

活动或阻塞任务存在时，`next` 拒绝选择新任务。第一版仍只支持单执行者串行运行；原子替换避免半写文件，但不提供并发事务或锁。

项目命令入口：

```bash
python3 .harness/harness.py run setup
python3 .harness/harness.py run start
python3 .harness/harness.py run check
```

长运行 `start` 会流式继承终端输出；Ctrl-C 会终止子进程并以 130 退出，不打印 traceback。

## 4. 验证与证据

命令型验收：

```bash
python3 .harness/harness.py verify
```

stdout/stderr 会按原始字节保存到日志；终端显示使用 UTF-8 replacement 解码。退出码 0 为 passed，其他退出码为 failed。

浏览器 passed 必须提供工具名和至少一个 workspace 内的非 symlink 普通文件：

```bash
python3 .harness/harness.py record TASK_ID CHECK_ID \
  --result passed \
  --summary "实际执行了什么，以及观察到什么" \
  --tool browser \
  --artifact proof/screenshot.png
```

manual 可以用非空摘要记录人工声明，附件可选。Harness 能验证声明与文件的一致性，但不能证明人或 Agent 没有撒谎。

能力不可用时记录：

```bash
python3 .harness/harness.py record TASK_ID CHECK_ID \
  --result unverified \
  --summary "当前 Agent 没有浏览器工具"
```

每次结果会新增不可覆盖的 schema v2 evidence JSON。最新 evidence JSON、命令日志和每个附件都记录大小及 SHA-256；doctor、handoff 和 complete 会验证路径、文件类型、摘要及任务/验收字段。

同一验收达到冻结的失败阈值后任务自动 blocked。人工处理后执行：

```bash
python3 .harness/harness.py unblock TASK_ID --note "处理了什么"
```

只有全部验收为 passed、证据完整且 Git 范围审计成功时才能完成：

```bash
python3 .harness/harness.py complete TASK_ID
```

任何 Git status、branch、HEAD 或 index 读取不确定都会 fail closed。

## 5. 跨会话交接

每轮结束运行：

```bash
python3 .harness/harness.py handoff
```

`.harness/HANDOFF.md` 记录 schema、snapshot 时间、当前验收及有效证据、历史失败、Git 状态、越界警告和下一条命令。工作树章节明确排除生成文件 `.harness/HANDOFF.md` 自身；证据无效时只显示错误，不展示未验证摘要为可信事实。

旧失败证据在后续记录覆盖了状态中的最新哈希后，HANDOFF 只列出路径并标记摘要未受信，不再把其文本当成可信结果展示。

适配器片段位于 `template/.harness/adapters/`。Harness 不会自动 commit、push 或修改 Git 历史。

CLI 返回码：成功 `0`，验收或流程门禁失败 `1`，配置或用法错误 `2`，用户中断 `130`。

## 可运行 Todo 示例

```bash
python3 template/.harness/harness.py --workspace examples/todo doctor
python3 template/.harness/harness.py --workspace examples/todo run check
python3 template/.harness/harness.py --workspace examples/todo run start
```

打开 `http://127.0.0.1:8000`，验证新增、勾选和刷新持久化。示例目录也可直接执行：

```bash
cd examples/todo
python3 .harness/harness.py doctor
python3 .harness/harness.py status
```

## 开发验证

```bash
python3 -m unittest discover -s tests -v
node --test examples/todo/test.mjs
ruff check --no-cache template/.harness/harness.py tests/test_harness.py
```

真实浏览器回归需要 Playwright 和可通过 CDP 访问的 Chromium：

```bash
python3 template/.harness/harness.py --workspace examples/todo run start
python3 tests/todo_browser_acceptance.py
```

仓库脚本默认启动无头 Chromium；需复用已启动的专用浏览器时，可设置 `HARNESS_CDP_URL=http://127.0.0.1:9344`。Playwright 仅是开发验收依赖，不是 Harness 运行时依赖。
