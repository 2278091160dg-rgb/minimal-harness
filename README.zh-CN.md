# Minimal Harness

[English](README.md) | [简体中文](README.zh-CN.md)

[![CI](https://github.com/2278091160dg-rgb/minimal-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/2278091160dg-rgb/minimal-harness/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/2278091160dg-rgb/minimal-harness)](https://github.com/2278091160dg-rgb/minimal-harness/releases/latest)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**面向编码 Agent 的最小、零运行时依赖、fail-closed 完成证明层。**

Minimal Harness 是一套可放进任意代码仓库的验收内核，Codex、Claude Code、
GitHub Copilot 等编码 Agent 都能调用。它把任务状态、真实验证、防篡改证据、
Git 范围、完成门禁和跨会话交接连接成可检查的闭环。

它不调用 AI，也不把“代码写完”当作“任务已经完成”。

## 30 秒安装

### macOS 和 Linux

```bash
curl -fLO https://github.com/2278091160dg-rgb/minimal-harness/releases/download/v0.1.1/minimal-harness-v0.1.1.zip
python3 -m zipfile -e minimal-harness-v0.1.1.zip .
python3 .harness/harness.py doctor
```

### Windows PowerShell

```powershell
Invoke-WebRequest https://github.com/2278091160dg-rgb/minimal-harness/releases/download/v0.1.1/minimal-harness-v0.1.1.zip -OutFile minimal-harness-v0.1.1.zip
py -3 -m zipfile -e minimal-harness-v0.1.1.zip .
py -3 .harness/harness.py doctor
```

压缩包会直接解出 `.harness/`。根据项目编辑
`.harness/config.json` 和 `.harness/tasks.json`，然后进入下方工作流。
Release 同时提供 `SHA256SUMS.txt` 供下载校验。

## 能力清单

| 能力 | 能确认什么 |
| --- | --- |
| Agent 中立、仓库本地运行 | 不同编码 Agent 可以调用同一份纳入版本管理的工作流。 |
| 确定性任务生命周期 | 任务按明确规则经过 `pending`、`in_progress`、`blocked`、`done`。 |
| 严格 v1 → v2 迁移 | 活动中的旧任务重建 baseline，不静默继承不完整状态。 |
| Git 范围审计 | 对 branch、HEAD、index、工作树、tracked/ignored 文件和允许路径执行 fail-closed 检查。 |
| 证据绑定 | evidence JSON、日志和附件记录大小、SHA-256 及 Git verification subject。 |
| 三类验收 | command 由 Harness 执行；browser 通过需要工具和附件；manual 明确标为人工声明。 |
| Fail-closed 完成门禁 | Git 或证据缺失、过期、篡改、无法确认时拒绝 `complete`。 |
| 可验证交接 | `HANDOFF.md` 记录当前任务、可信证据、警告和下一条命令。 |
| 可移植运行时 | 核心只依赖 Python 3.9+ 标准库，支持 Linux、macOS 和 Windows。 |
| 可选 GitHub 汇报 | 独立适配器可把可信结果发布为 GitHub Check Run。 |

## 最小工作流

```bash
# 1. 检查仓库并领取一个任务。
python3 .harness/harness.py doctor
python3 .harness/harness.py status
python3 .harness/harness.py next

# 2. 完成工作后运行 command 验收。
python3 .harness/harness.py verify

# 3. 需要时记录 browser 或 manual 验收。
python3 .harness/harness.py record TASK_ID CHECK_ID \
  --result passed \
  --summary "实际执行了什么，以及观察到什么" \
  --tool browser \
  --artifact proof/screenshot.png

# 4. 所有门禁通过后才能完成。
python3 .harness/harness.py complete TASK_ID

# 5. 为下一会话生成交接。
python3 .harness/harness.py handoff
```

第一分钟的实际输出类似：

```text
$ python3 .harness/harness.py doctor
OK: configuration valid (1 tasks)
OK: Git branch=main HEAD=<commit>

$ python3 .harness/harness.py next
Selected T1: <任务标题>

$ python3 .harness/harness.py status
Project: <项目名>
Current task: T1
- T1 [in_progress]: <任务标题>
```

## 为什么不只是 CI？

CI 回答某个版本上的命令是否通过。Minimal Harness 还把结果绑定到任务生命周期、
任务开始时的 Git 状态、允许路径、附件、证据新鲜度和最终完成决定，并在不同
Agent 会话之间保留可信交接。

Minimal Harness 是独立 CLI 验收内核，**不是**：

- Codex Skill 或 Agent 编排器；
- 操作系统沙箱或权限系统；
- 自动 commit 或 push 的服务；
- 对人工声明真实性的密码学证明。

执行不可信代码时仍需使用容器、虚拟机、受限账户或平台权限。

## 配置与任务模型

`.harness/config.json` 和 `.harness/tasks.json` 使用 schema v2。

- `commands.setup/start/check` 必须是 argv 数组或 `null`，执行时不经过 shell。
- `{python}` 会安全替换为当前运行 Harness 的 Python 解释器。
- `policy.allowed_paths` 使用路径分段 glob：`*` 只匹配一层，`**` 才跨目录。
- `policy.require_git_for_completion` 默认为 `true`。
- `approval_required_operations` 记录 Agent 与人的流程边界，不拦截系统调用。

验收类型：

- `command`：由 Harness 直接执行。
- `browser`：使用真实浏览器；passed 必须提供 `--tool` 和至少一个非
  symlink 普通文件附件。
- `manual`：明确标注为人工或外部工具声明，附件可选。

返回码为：成功 `0`，验收或流程门禁失败 `1`，配置或用法错误 `2`，
用户中断 `130`。

## 从 v1 迁移

先预览再修改状态：

```bash
python3 .harness/harness.py migrate --dry-run
python3 .harness/harness.py migrate
```

活动或阻塞中的 v1 任务无法证明旧 index baseline，必须显式确认新断点：

```bash
python3 .harness/harness.py migrate \
  --note "确认从当前 Git 状态重新开始"
```

迁移会在 `.harness/migrations/` 保存原始 v1 文件和哈希，不改写历史
evidence。未完成任务的 v1 passed 会降为 `unverified`；已完成任务保持
可读并标为 legacy evidence。重复迁移是安全的。

## Git baseline 与范围

`next` 只领取第一个 pending 任务，并冻结：

- branch、HEAD、unborn 状态、工作树和 index 指纹；
- tracked/ignored 文件清单与 Git 标志指纹；
- 允许路径、失败阈值、审批和 Git completion 策略。

存在活动或阻塞任务时，不能领取新任务。既有脏普通文件会被指纹化，后续修改
无法隐藏在旧脏状态中。无法完整指纹化的脏对象（包括不安全的 submodule 状态）
会阻止建立不完整 baseline。

所有 Git 子命令都检查返回码。仓库一旦被识别，status、branch、HEAD、index、
tracked/ignored 文件或 submodule 的读取不确定都会阻塞完成。

## 证据与新鲜度

```bash
# 执行活动任务的全部 command 验收。
python3 .harness/harness.py verify

# 能力不可用时如实记录，而不是伪造 passed。
python3 .harness/harness.py record TASK_ID CHECK_ID \
  --result unverified \
  --summary "当前 Agent 会话没有浏览器工具"
```

每次结果都会创建不可覆盖的 schema v3 evidence JSON。命令输出按原始字节
保存，终端用 UTF-8 replacement 解码。evidence JSON、日志和附件都记录路径、
类型、大小和 SHA-256。

passed evidence 还会保存验收时的 Git verification subject。之后相关文件、
index、branch、HEAD、ignored 文件、submodule 或 Git 历史变化都会使证据
过期，必须重新执行 `verify` 或 `record`。

新鲜度只排除 Harness 生成的可变状态：`tasks.json`、`evidence/**`、
`logs/**`、`HANDOFF.md` 和 `migrations/**`。运行时、配置、适配器和
项目文件仍在审计范围内。

任务达到失败阈值并 blocked 后，人工处理可以重置当前门禁，同时保留历史证据：

```bash
python3 .harness/harness.py unblock TASK_ID --note "处理了什么"
```

## 跨会话交接

```bash
python3 .harness/harness.py handoff
```

`.harness/HANDOFF.md` 记录 schema、snapshot 时间、当前验收、有效证据、
历史失败、Git 状态、范围警告和下一条命令。无效证据只显示错误，不会把摘要
展示为可信结果；生成的 HANDOFF 文件会在工作树章节排除自身。

Agent 指令文件适配片段位于 `template/.harness/adapters/`。

## 可运行 Todo 示例

```bash
python3 template/.harness/harness.py --workspace examples/todo doctor
python3 template/.harness/harness.py --workspace examples/todo run check
python3 template/.harness/harness.py --workspace examples/todo run start
```

打开 `http://127.0.0.1:8000`，验证新增、勾选和刷新持久化。也可在示例目录
直接运行：

```bash
cd examples/todo
python3 .harness/harness.py doctor
python3 .harness/harness.py status
```

## 可选 GitHub Check Run

`integrations/github/` 提供标准库适配器和示例 workflow。它在普通 CI 中运行
doctor/check，仅在可信的 `push` 事件中使用 `checks: write` 发布 Check Run：

```bash
mkdir -p .github/workflows
cp integrations/github/minimal-harness-check.yml .github/workflows/
```

适配器要求 `GITHUB_TOKEN`、`GITHUB_REPOSITORY` 和完整 `GITHUB_SHA`，
并拒绝跨主机重定向，避免转发 Authorization。参见官方
[Check Runs REST API](https://docs.github.com/en/rest/checks/runs) 和
[GitHub Actions fork 权限边界](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#changing-the-permissions-in-a-forked-repository)。

## 开发验证

```bash
python3 -m unittest discover -s tests -v
node --test examples/todo/test.mjs
python3 -m pip install ruff==0.15.12
ruff check --no-cache template/.harness/harness.py integrations/github/publish_check.py scripts tests
python3 template/.harness/harness.py --workspace template doctor
python3 template/.harness/harness.py --workspace examples/todo doctor
python3 template/.harness/harness.py --workspace examples/todo run check
```

真实浏览器回归需要 Playwright 和 Chromium，但它们只是开发验收依赖，不是
Harness 运行时依赖。

```bash
python3 template/.harness/harness.py --workspace examples/todo run start
python3 tests/todo_browser_acceptance.py
```

设置 `HARNESS_CDP_URL=http://127.0.0.1:9344` 可以复用专用的 CDP 浏览器。

## 安全、贡献与许可证

报告漏洞前请阅读 [SECURITY.md](SECURITY.md)，提交行为或 schema 变更前请阅读
[CONTRIBUTING.md](CONTRIBUTING.md)。

Minimal Harness 采用 [MIT License](LICENSE)。
