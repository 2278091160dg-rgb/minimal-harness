# Minimal AI Coding Harness

这是一套可以复制进任意代码项目的最小 Harness。它不替你调用 AI，也不假装“代码写完”就是“用户可用”；它只负责把任务、执行、真实验证、证据和下一轮交接连成一个可检查的闭环。

## 1. 写清楚怎样才算完成

复制模板并编辑任务：

```bash
cp -R template/.harness /path/to/your-project/.harness
cd /path/to/your-project
```

在 `.harness/tasks.json` 中把大需求拆成有序小任务。每个任务至少有一个验收项：

- `command`：Harness 可以直接执行的命令。
- `browser`：需要 Agent 的浏览器工具执行。
- `manual`：需要人工观察或外部工具执行。

任务只有 `pending / in_progress / blocked / done` 四种状态；验收只有 `not_run / passed / failed / unverified` 四种状态。`unverified` 不等于通过。

## 2. 固定启动和检查入口

编辑 `.harness/config.json`：

- `commands.setup/start/check` 是参数数组，Harness 使用 `subprocess` 直接执行，不经过 shell。
- 不需要的命令写成 `null`；复杂命令请放进项目自己的包装脚本，再把脚本作为一个参数数组入口。
- `allowed_paths` 声明 Agent 可修改的范围。
- `approval_required_operations` 声明必须先询问你的操作。

这两项是流程约束和完成门禁，不是操作系统沙箱：Harness 会在 `complete` 时审计 Git 变更范围，但不会拦截 Agent 在执行过程中读写文件或执行命令。需要安全隔离时，仍应使用容器、受限账户或 Agent 平台自身的权限机制。

首次运行：

```bash
python3 .harness/harness.py doctor
python3 .harness/harness.py status
python3 .harness/harness.py run setup
python3 .harness/harness.py run start
python3 .harness/harness.py run check
```

全局 `--workspace PATH` 选项放在子命令之前，可从模板仓库操作其他目录。

## 3. 每轮只推进一个任务

固定循环：

```bash
python3 .harness/harness.py doctor
python3 .harness/harness.py status
python3 .harness/harness.py next
```

`next` 只会选择一个任务。已有进行中或阻塞任务时，它拒绝继续。把 `adapters/AGENTS.md.snippet`、`CLAUDE.md.snippet` 或 `GENERIC.md` 的内容加入项目对应的 Agent 说明文件，让新会话遵循同一顺序。

领取任务时，Harness 会同时冻结本任务使用的失败阈值和允许路径；任务进行中修改 `config.json` 不能放宽当前任务的自动门禁。`approval_required_operations` 仍是给 Agent 和人的流程约束，Harness 本身不会拦截系统调用。

第一版只支持单执行者串行运行。不要让多个进程或 Agent 同时执行会修改状态的命令（如 `next`、`verify`、`record`、`complete`、`unblock`）；原子替换可以避免半写文件，但不提供并发事务或锁。

同一验收连续失败三次后任务自动阻塞。人工处理环境或需求问题后执行：

```bash
python3 .harness/harness.py unblock TASK_ID --note "处理了什么"
```

## 4. 用真实结果决定是否通过

命令型验收：

```bash
python3 .harness/harness.py verify
```

浏览器或人工验收：

```bash
python3 .harness/harness.py record TASK_ID CHECK_ID \
  --result passed \
  --summary "实际执行了什么，以及观察到什么" \
  --tool browser \
  --artifact proof/screenshot.png
```

`--artifact` 可重复使用，但每个文件必须真实存在于项目目录内。没有浏览器能力时必须记录：

```bash
python3 .harness/harness.py record TASK_ID CHECK_ID \
  --result unverified \
  --summary "当前 Agent 没有浏览器工具"
```

每次结果都会在 `.harness/evidence/` 新增不可覆盖的 JSON；命令输出另存日志，任务状态保存最新证据的 SHA-256，用于发现缺失或意外篡改。它是本地一致性检查，不是对同一台机器上有写权限者的密码学信任边界。只有全部验收为 `passed` 时才能执行：

```bash
python3 .harness/harness.py complete TASK_ID
```

## 5. 留下下一轮能接手的记录

每轮结束运行：

```bash
python3 .harness/harness.py handoff
```

`.harness/HANDOFF.md` 会记录当前任务、证据状态、阻塞、Git 分支与 HEAD、工作区变更及下一条命令。Harness 不会自动 commit、push 或修改 Git 历史。

没有 Git 仓库时，`doctor` 与交接文件会明确警告，Harness 仍可管理任务和证据，但无法可靠审计代码变更范围；若要依赖 `allowed_paths` 完成门禁，应先在项目中建立 Git 基线。

CLI 返回码：成功为 `0`，验收或流程门禁失败为 `1`，配置或用法错误为 `2`。

## 可运行待办示例

先检查并运行自动测试：

```bash
python3 template/.harness/harness.py --workspace examples/todo doctor
python3 template/.harness/harness.py --workspace examples/todo run check
```

启动页面：

```bash
python3 template/.harness/harness.py --workspace examples/todo run start
```

访问 `http://127.0.0.1:8000`，再用 `next`、浏览器操作、`record` 和 `complete` 依次验证新增、勾选及刷新持久化。示例需要 Node.js 运行 JavaScript 单元测试，但 Harness 本身只需要 Python 3.9+ 标准库。

示例目录也带有自己的 `.harness/harness.py` 入口，因此进入目录后可直接运行：

```bash
cd examples/todo
python3 .harness/harness.py doctor
python3 .harness/harness.py status
```

## 开发检查

```bash
python3 -m unittest discover -s tests -v
node --test examples/todo/test.mjs
```

真实浏览器回归需要 Playwright 和一个可通过 CDP 访问的 Chromium。先在一个终端启动示例，再在仓库根目录运行浏览器脚本：

```bash
python3 template/.harness/harness.py --workspace examples/todo run start
python3 tests/todo_browser_acceptance.py
```

本仓库的浏览器脚本连接 `http://127.0.0.1:9344`，这是开发环境的专用浏览器桥接端口；它不是 Harness 运行时依赖。其他环境可以用自己的浏览器工具逐步执行 `tasks.json` 中的操作，并通过 `record` 写入观察结果。
