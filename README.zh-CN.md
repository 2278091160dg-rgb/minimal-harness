# Minimal Harness

[![CI](https://github.com/2278091160dg-rgb/minimal-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/2278091160dg-rgb/minimal-harness/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/2278091160dg-rgb/minimal-harness)](https://github.com/2278091160dg-rgb/minimal-harness/releases)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个面向 AI 编程的轻量本地验收与跨会话交接工具。先定义必须成立的行为，再运行检查、
保留证据；只有证据仍对应当前源码和验收定义时，任务才能登记完成。

**Python 3.9+ 标准库 · Git · 单执行者 · 不调用模型或云服务**

[English](README.md) · [文档索引](docs/README.zh-CN.md) ·
[首次真人试用表](docs/adoption-validation.zh-CN.md)

## 选择正确版本

| 版本 | 适用场景 | 范围 |
| --- | --- | --- |
| [v0.2.0-beta.1](https://github.com/2278091160dg-rgb/minimal-harness/releases/tag/v0.2.0-beta.1) | 已发布 schema v3 测试版 | 包含 `init`、`task add/revise`、`report` 与源码/契约新鲜度绑定。它的 ZIP **没有**运行时 `LICENSE`，也没有当前源码中尚未发布的 Git/runner 加固。 |
| 当前源码/PR | 评估本次未发布加固修订 | 全新 `init` 与显式升级会复制 `harness.py`、`harness_init.py`、`harness_runner.py` 和 `.harness/LICENSE`；还包含源码示例与发布检查器。 |
| [v0.1.1](https://github.com/2278091160dg-rgb/minimal-harness/releases/tag/v0.1.1) | 较早的稳定流程 | schema v2；没有 `init`、`task add/revise` 或 `report`。不要把 v3 命令手册用于它。 |

本文档描述 schema v3。要体验已发布行为可下载 beta.1；要评估本 PR 修复，请使用当前源码检出。

## 安装已发布 beta ZIP

下面命令会下载两个真实 beta.1 资源、核验压缩包、解压到临时分段目录，然后初始化一个
**已经存在**的项目。它们不会把压缩包直接覆盖到项目 `.harness/`。只需修改最后的项目路径。

macOS 或 Linux：

```bash
(
set -eu
mh_version=v0.2.0-beta.1
mh_base="https://github.com/2278091160dg-rgb/minimal-harness/releases/download/$mh_version"
mh_stage="$(mktemp -d)"
curl -fL "$mh_base/minimal-harness-$mh_version.zip" -o "$mh_stage/minimal-harness-$mh_version.zip"
curl -fL "$mh_base/SHA256SUMS.txt" -o "$mh_stage/SHA256SUMS.txt"
if command -v sha256sum >/dev/null 2>&1; then
  (cd "$mh_stage" && sha256sum -c SHA256SUMS.txt)
else
  (cd "$mh_stage" && shasum -a 256 -c SHA256SUMS.txt)
fi
mkdir "$mh_stage/runtime"
python3 -m zipfile -e "$mh_stage/minimal-harness-$mh_version.zip" "$mh_stage/runtime"
python3 "$mh_stage/runtime/.harness/harness.py" --workspace /项目/绝对路径 init --agent codex
)
```

PowerShell：

```powershell
$ErrorActionPreference = "Stop"
$Version = "v0.2.0-beta.1"
$Base = "https://github.com/2278091160dg-rgb/minimal-harness/releases/download/$Version"
$Stage = Join-Path ([IO.Path]::GetTempPath()) ("minimal-harness-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Stage | Out-Null
$Zip = Join-Path $Stage "minimal-harness-$Version.zip"
$Sums = Join-Path $Stage "SHA256SUMS.txt"
Invoke-WebRequest "$Base/minimal-harness-$Version.zip" -OutFile $Zip
Invoke-WebRequest "$Base/SHA256SUMS.txt" -OutFile $Sums
$Expected = ((Get-Content $Sums | Where-Object { $_ -match "minimal-harness-$([regex]::Escape($Version))\.zip" }) -split '\s+')[0].ToLowerInvariant()
$Actual = (Get-FileHash $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Actual -ne $Expected) { throw "SHA-256 mismatch: expected $Expected, observed $Actual" }
$Runtime = Join-Path $Stage "runtime"
Expand-Archive -Path $Zip -DestinationPath $Runtime
py -3 "$Runtime/.harness/harness.py" --workspace "C:\项目\绝对路径" init --agent codex
if ($LASTEXITCODE -ne 0) { throw "Minimal Harness init failed with exit $LASTEXITCODE" }
```

已核验的 beta.1 摘要为
`f57b733a8eb4e62a05a0bf6ebcf66fc7972b9ec91dec47e1697252d5a1a81567`；
仍应以刚下载的 `SHA256SUMS.txt` 为核验依据。beta ZIP 内是分段用 `.harness/` 树，
不含示例，也不含 `.harness/LICENSE`。

`--agent claude` 向 `CLAUDE.md` 追加托管区块，`--agent generic` 使用通用
`AGENTS.md`，省略 `--agent` 则只安装运行时。`init --dry-run` 仅预览。已有指令会保留，
托管区块只追加一次。局部安装、符号链接、冲突区块或不同运行时代码都会保守拒绝。
`init` 不升级状态、不初始化 Git，也不安装依赖。

## 完整体验源码示例

从当前源码检出根目录创建一个可丢弃项目：

```bash
mkdir ../harness-demo
cp -R examples/quickstart/src examples/quickstart/tests examples/quickstart/greeting.task.json ../harness-demo/
python3 template/.harness/harness.py --workspace ../harness-demo init --agent codex
cd ../harness-demo
git init
python3 .harness/harness.py doctor
python3 .harness/harness.py task add --from greeting.task.json
python3 .harness/harness.py next
python3 .harness/harness.py verify
python3 .harness/harness.py report greeting
python3 .harness/harness.py complete greeting
python3 .harness/harness.py handoff
```

预期看到 `PASS: named and default greetings match the CLI contract`、ready 报告、
`Completed greeting`，以及更新后的 `.harness/HANDOFF.md`。这个一次性示例不要求先有
Git 提交。quickstart 和 Todo 夹具只存在于源码仓库。

PowerShell 的准备步骤如下；随后用 `py -3` 执行同一组 `doctor` 到 `handoff` 命令：

```powershell
New-Item -ItemType Directory ..\harness-demo | Out-Null
Copy-Item -Recurse examples\quickstart\src, examples\quickstart\tests, examples\quickstart\greeting.task.json ..\harness-demo\
py -3 template/.harness/harness.py --workspace ../harness-demo init --agent codex
Set-Location ..\harness-demo
git init
```

## 能力地图

| 能力 | 目的 | 命令 | 输出或证据 | 边界 |
| --- | --- | --- | --- | --- |
| 初始化与 Agent 接入 | 安装运行时并可选追加指令 | `harness.py --workspace PATH init [--agent codex\|claude\|generic] [--dry-run]` | 运行时、配置、任务、交接；可选托管区块 | `--workspace` 在子命令前；不升级、不建 Git 历史、不装依赖、不覆盖。 |
| 添加任务 | 把纯定义 JSON 转为 pending 状态 | `task add --from SPEC.json` | 任务状态和刷新交接 | 必须有 `--from`；相对路径以调用者当前目录解析；拒绝运行态/证据字段。 |
| 领取工作 | 冻结 Git、策略与验收基线 | `next` | 第一个 pending 变为 `in_progress` | 只能有一个当前任务；blocked 会阻止继续领取。 |
| 修订需求 | 显式替换 pending 或 active 定义 | `task revise ID --from SPEC.json --note TEXT` | 修订历史与失效的旧证据 | ID 一致；blocked 先解阻；原 Git/策略起点不变。 |
| 项目辅助命令 | 运行配置的安装、服务或项目检查 | `run setup\|start\|check` | setup/check 日志位于 `.harness/attempts/runs/` | 不是任务验收；`start` 保持前台；子命令可能修改项目。 |
| 命令验收 | 运行当前任务全部 command 检查 | `verify [ID]` | 日志、attempt、证据、状态、交接 | 仅当前 `in_progress`；不生成 browser/manual 结果；漂移会记 unverified。 |
| 浏览器验收 | 记录浏览器工具实际执行的动作 | `record ID CHECK --result ... --summary ... --tool TOOL --artifact FILE` | 声明证据和附件元数据 | passed 必须有真实、非符号链接的项目内附件和工具名；不自动开浏览器或证明观察；多个附件重复 `--artifact`。 |
| 人工验收 | 记录实际人工观察 | `record ID CHECK --result ... --summary ... [--artifact FILE]` | 声明与可选附件 | 观察不能为空；工具和附件可省略。 |
| 新鲜度 | 绑定源码、验收、分支、HEAD 与 index | `doctor`；`report ID`；`complete ID` | 过期警告或拒绝 | 只改 mtime 不会过期；外部服务、忽略依赖、环境变化不在保证内。 |
| Git 范围 | 按冻结的 `allowed_paths` 审计改动 | `report ID`；`complete ID` | ready/issues 和下一命令 | 默认完成需要 Git；审计是完成门，不是 OS 沙箱。 |
| 报告与完成 | 只读预检，然后关闭 ready 任务 | `report ID [--format text\|json\|markdown]`；`complete ID` | stdout 报告；最终状态与交接 | done 报告仅是历史视图，返回 1，不能再次授权完成。 |
| 解阻 | 处理连续失败原因后恢复 | `unblock ID --note TEXT` | 解阻历史、重置计数、交接 | 只能处理当前 blocked 任务；不会把检查变成通过。 |
| 交接 | 重新生成跨会话摘要 | `handoff` | `.harness/HANDOFF.md` | 只写本地，不上传、不创建会话。 |
| 迁移 | 归档并把 v1/v2 转为 v3 | `migrate [--dry-run] [--note TEXT]` | 迁移归档、状态、交接 | active/blocked 必须写 note；未完成任务的旧通过会变 unverified。 |
| 可选 GitHub | 对可信 push 发布独立 Check Run | 复制 `integrations/github/` 适配器 | GitHub Check Run | 需要凭证与 `checks: write`；`run check` 仍不是任务证据。 |

## 在 `next` 前配置

先编辑 `.harness/config.json`：

- `commands.setup/start/check` 是 `null` 或非空 argv 数组，不经过 shell；`{python}`
  替换为启动 Harness 的解释器。
- `policy.allowed_paths` 默认 `src/**`、`tests/**`、`.harness/**`。根目录应用文件要
  显式加入。`*` 匹配一层，`**` 跨目录。
- `max_consecutive_failures` 默认三次，策略在 `next` 时冻结。
- `require_git_for_completion` 默认 `true`。设为 `false` 只是允许 Git 不可用时完成；只要
  Git 实际可用，捕获的 Git 身份仍属于源码新鲜度绑定。
- `approval_required_operations` 是工作流指令，不拦截系统调用。

任务输入只含定义：

```json
{
  "id": "greeting",
  "title": "有名字时问候指定用户，没有名字时使用默认值",
  "acceptance": [{
    "id": "greeting-cli",
    "type": "command",
    "instruction": "有参数时问候 Ada，无参数时问候 world。",
    "command": ["{python}", "tests/check_greeting.py"],
    "timeout_seconds": 30
  }]
}
```

command 必须有 `command`；browser/manual 必须有非空 `steps`。ID 长 1–128 个 ASCII
字母、数字、点、下划线或连字符，首字符是字母或数字。不要手改生成的状态、计数、基线或哈希。

## 证据与恢复

`verify` 会在批次开始前使旧 command 通过结果失效。每条命令默认上限为 300 秒和
10 MiB 原始输出；正的有限 `timeout_seconds` 可调整时间。超时和超量会保留受限的部分日志。
中断返回 130，并保持 unverified。`run check` 不创建任务验收。

browser 验收必须先用浏览器工具执行每一步，把真实附件放入 `.harness/artifacts/`，再如实
记录实际观察：

```bash
python3 .harness/harness.py record TASK_ID CHECK_ID --result passed \
  --summary "打开页面、提交 Ada，实际看到 Hello, Ada!" \
  --tool playwright --artifact .harness/artifacts/greeting.png
```

工具或观察不可用时用 `--result unverified`；命令返回 1，完成门保持关闭。browser/manual
记录是操作者声明。Harness 核验文件存在与摘要，但不会独立证明陈述真假。

`report` 和 `complete` 时，证据仍须匹配契约与源码快照。快照包含 Git 分支、HEAD、index、
已跟踪与未忽略文件，以及递归初始化且干净的 submodule。验收后暂存、提交、切换分支、修改源码
或修订验收，都必须重验。脏或未初始化 submodule 与隐藏 index 标志会保守失败。Harness 生成的
状态、attempt、evidence、report、handoff、migration、artifact、旧 logs 与运行时
`__pycache__` 不计入应用源码范围。

任务状态为 `pending / in_progress / blocked / done`；检查状态为
`not_run / passed / failed / unverified`，unverified 绝不等于通过。退出码：`0` 成功/ready；
`1` 检查失败或门禁未满足/过期；`2` 用法、配置或证据损坏；`130` 中断。

## 显式升级到当前未发布修订

先备份已安装的 `.harness/`，并把当前源码检出放在项目之外的分段路径。只替换以下四个运行时
文件；保留配置、任务、证据、attempt、artifact、handoff 历史与 Agent 指令：

```bash
mh_source=/当前/minimal-harness/源码绝对路径
mh_project=/项目/绝对路径
mh_backup="$(mktemp -d)"
cp -R "$mh_project/.harness" "$mh_backup/.harness"
cp "$mh_source/template/.harness/harness.py" "$mh_project/.harness/harness.py"
cp "$mh_source/template/.harness/harness_init.py" "$mh_project/.harness/harness_init.py"
cp "$mh_source/template/.harness/harness_runner.py" "$mh_project/.harness/harness_runner.py"
cp "$mh_source/template/.harness/LICENSE" "$mh_project/.harness/LICENSE"
python3 "$mh_project/.harness/harness.py" --workspace "$mh_project" migrate --dry-run --note "确认 v3 当前验收定义"
python3 "$mh_project/.harness/harness.py" --workspace "$mh_project" migrate --note "确认 v3 当前验收定义"
```

PowerShell 同样只替换四个文件，并把备份放在项目外：

```powershell
$ErrorActionPreference = "Stop"
$Source = "C:\当前\minimal-harness\源码路径"
$Project = "C:\项目\绝对路径"
$Backup = Join-Path ([IO.Path]::GetTempPath()) ("minimal-harness-backup-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Backup | Out-Null
Copy-Item -Recurse (Join-Path $Project ".harness") (Join-Path $Backup ".harness")
Copy-Item -Force (Join-Path $Source "template\.harness\harness.py") (Join-Path $Project ".harness\harness.py")
Copy-Item -Force (Join-Path $Source "template\.harness\harness_init.py") (Join-Path $Project ".harness\harness_init.py")
Copy-Item -Force (Join-Path $Source "template\.harness\harness_runner.py") (Join-Path $Project ".harness\harness_runner.py")
Copy-Item -Force (Join-Path $Source "template\.harness\LICENSE") (Join-Path $Project ".harness\LICENSE")
py -3 (Join-Path $Project ".harness\harness.py") --workspace $Project migrate --dry-run --note "确认 v3 当前验收定义"
if ($LASTEXITCODE -ne 0) { throw "Minimal Harness migration preview failed with exit $LASTEXITCODE" }
py -3 (Join-Path $Project ".harness\harness.py") --workspace $Project migrate --note "确认 v3 当前验收定义"
if ($LASTEXITCODE -ne 0) { throw "Minimal Harness migration failed with exit $LASTEXITCODE" }
```

运行时 LICENSE 不修改用户项目根许可证。已发布 beta.1 ZIP 不能提供 `.harness/LICENSE`；四个
文件须来自同一当前修订。如果刻意停留在没有 `template/.harness/LICENSE` 的旧 ref，只能使用
同一 ref 的根 `LICENSE`。

迁移先归档 v1/v2 状态。未完成任务的旧通过必须重验；已完成旧任务只作历史记录。v2 Git/策略
基线与阻塞计数保留。active/blocked v1 任务会获新基线，同时把旧基线存入历史。对 v3 重复迁移
只会报告已经是 v3。

## 信任边界与可选 GitHub 适配器

Minimal Harness 不是 OS 沙箱、授权系统、签名服务、并发协议或独立防伪服务。能重写仓库和
Harness 状态的进程可以绕过它。只支持单执行者。运行时不调用模型、不发遥测、不提交、不推送、
不发布，也不上传证据。

配置 `commands.check` 后，可把 `integrations/github/minimal-harness-check.yml` 复制到
`.github/workflows/`，并把 `integrations/github/publish_check.py` 保持在项目同名路径。
示例仅对可信 `push` 以 `checks: write` 发布；pull request 只跑本地检查。它需要
`GITHUB_TOKEN`、`GITHUB_REPOSITORY` 和完整 `GITHUB_SHA`。

## 继续阅读

- [实战使用指南](docs/usage-guide.zh-CN.md)
- [完整 CLI 参考](docs/cli-reference.zh-CN.md)
- [文档索引](docs/README.zh-CN.md)
- [首次真人试用表](docs/adoption-validation.zh-CN.md)——仍等待真实用户
- [贡献指南](CONTRIBUTING.zh-CN.md)
- [安全策略](SECURITY.zh-CN.md)
- [MIT License（英文法律文本）](LICENSE)
