# Minimal Harness

为 AI 编程提供本地验收与跨会话交接：先定义什么必须成立，再运行检查、保存证据，
只有证据仍对应当前代码和验收标准时，才允许登记完成。

**Python 3.9+ 标准库 · Git · 单执行者 · 不调用模型或云服务**

[English README](README.md) · [真实新用户验证记录](docs/adoption-validation.md)

## 下载与版本

[GitHub Releases](https://github.com/2278091160dg-rgb/minimal-harness/releases) 提供
运行时 ZIP 和 `SHA256SUMS.txt`。本文介绍 schema v3 开发版本；已发布的 v0.1.1 尚无
`init`、`task add/revise` 和 `report`，体验 v3 请使用下方源码流程。已有项目应按本文
迁移步骤升级，保留自己的配置、任务与历史证据。

## 完整体验一次

克隆仓库并创建一个可丢弃的示例项目；如果已经下载，从仓库根目录的 `mkdir` 开始：

```bash
git clone https://github.com/2278091160dg-rgb/minimal-harness.git
cd minimal-harness
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

验收实际调用问候程序，检查有名字和没有名字两种输入。预期能看到检查通过、报告允许
完成，以及交接文件记录任务完成。示例不要求先创建 Git 提交。

可以在 `verify` 之后、`complete` 之前，把 `src/greet.py` 的 `Hello` 改为 `Hi`。
旧验收应被报告判定过期，不能完成。恢复正确行为后，重新运行 `verify`。

PowerShell 的目录准备命令如下，后续使用 `py -3` 执行同一套命令：

```powershell
New-Item -ItemType Directory ..\harness-demo
Copy-Item -Recurse examples\quickstart\src, examples\quickstart\tests, examples\quickstart\greeting.task.json ..\harness-demo\
py -3 template/.harness/harness.py --workspace ../harness-demo init --agent codex
Set-Location ..\harness-demo
git init
```

`--agent codex` 向 `AGENTS.md` 追加带标记的工作流；`claude` 使用 `CLAUDE.md`；
`generic` 使用通用 `AGENTS.md`。省略该选项时只安装运行时。`init --dry-run` 只预览。
初始化不会覆盖已有任务、配置、不同版本的代码或冲突的指令区块，也不会执行升级。

## 接入自己的项目

全局 `--workspace` 必须放在子命令之前：

```bash
python3 template/.harness/harness.py --workspace /path/to/project init --agent codex
```

在领取任务之前调整 `.harness/config.json`：

- `policy.allowed_paths` 默认允许 `src/**`、`tests/**`、`.harness/**`。根据实际项目设置
  修改范围；根目录的应用文件需要单独纳入。
- `commands.setup/start/check` 可以保持 `null`，或填写命令的 argv 数组。命令不经过 shell。
  `{python}` 自动使用启动 Harness 的 Python 解释器。
- `*` 仅匹配一层目录，`**` 可以跨目录。默认要求 Git 才能完成任务。
- 初始化不创建 Git 仓库、不提交代码，也不自动安装依赖。

任务规格只填写定义，不填写状态、失败次数或证据哈希：

```json
{
  "id": "greeting",
  "title": "有名字时问候指定用户，没有名字时使用默认值",
  "acceptance": [{
    "id": "greeting-cli",
    "type": "command",
    "instruction": "两种输入都产生预期的命令行输出。",
    "command": ["{python}", "tests/check_greeting.py"],
    "timeout_seconds": 30
  }]
}
```

用 `task add --from SPEC.json` 添加任务，再用 `next` 领取。开始后验收定义和编辑策略
会冻结。需要改变要求时，显式修订并留下原因：

```bash
python3 .harness/harness.py task revise greeting --from .harness/specs/revised.task.json --note "说明需求为何变化"
```

规格中的任务 ID 必须一致。修订保留任务原来的 Git 和策略起点，旧证据失效。已完成任务
不能修订；阻塞任务需要先通过 `unblock ID --note TEXT` 处理。不要手改运行态或哈希。
Harness 检查你定义的验收，不能自动判断验收是否充分。

新的修订规格建议保存到允许的路径，例如 `.harness/specs/`。在冻结范围以外新增或修改
规格文件也属于越界改动；修订验收不会扩大文件编辑权限。

## 验证、报告与恢复

| 命令 | 作用 |
| --- | --- |
| `verify [ID]` | 执行当前任务的命令验收并保存证据 |
| `run check` | 运行项目检查，不会产生任务验收证据 |
| `run setup` / `run start` | 项目辅助命令；start 保持长驻服务行为 |
| `report ID --format text\|json\|markdown` | 只读查看证据来源、过期原因、缺失项和下一步 |
| `complete ID` | 使用与 report 相同的审计逻辑检查是否可完成 |
| `handoff` | 更新跨会话交接文件 |

每项命令验收默认最多 300 秒、日志最多 10 MiB，正数 `timeout_seconds` 可以覆盖时间。
超时或日志超限会结束验证进程并保存已有日志。新验证开始前旧通过资格即失效；中断后
保持未验证，不能借用以前的成功结果。连续失败达到配置阈值后阻塞，默认阈值为 3。

命令验证前后代码内容与验收定义必须一致，完成时会再次计算摘要。证据也绑定 Git 分支、
HEAD 和暂存区身份；验证后暂存改动或创建提交，需要重新验证。固定排除运行状态、
证据、迁移档案、验证尝试、旧版 `.harness/logs/`、交接、报告、`.harness/artifacts/` 和运行时的
`.harness/__pycache__/`。检查 Git 跟踪文件及未忽略的新文件；即使整个 `.harness/`
被忽略，其中的源码和配置仍属于输入。不要把产品代码放到保留的输出目录。仅修改文件
时间不会让证据过期。已初始化且干净的 Git 子模块递归纳入；子模块有未提交改动、未
初始化或隐藏索引标记时，验证会停止并解释原因。

任务状态仍是 `pending / in_progress / blocked / done`，验收状态仍是
`not_run / passed / failed / unverified`。`unverified` 不算通过。
退出码：成功或就绪 `0`、验收/门禁未满足或证据过期 `1`、配置/用法错误或证据损坏 `2`、
用户中断 `130`。
已完成任务的报告是历史说明，不能授权另一项任务完成。

新会话先运行 `doctor`、`status`，再阅读 `.harness/HANDOFF.md`。报告只写到标准输出，
不会自动发送评论、上传附件或发布结果。

## 浏览器与人工验收

浏览器规格使用 `type: "browser"`、验收说明和非空 `steps` 数组。实际执行这些操作，
把截图保存到 `.harness/artifacts/`，然后记录观察结果：

```bash
python3 .harness/harness.py record TASK_ID CHECK_ID --result passed \
  --summary "描述实际操作和观察结果" \
  --tool playwright --artifact .harness/artifacts/screenshot.png
```

浏览器通过必须提供工具名称和工作区内真实存在、非符号链接的附件。人工验收要求非空
观察说明，附件可选。两者均属于**记录时的声明**：文件完整性与代码绑定不代表程序能够
独立证明截图或文字真实。工具不可用时记录 `unverified` 和原因。

Todo 示例包含新增、勾选和刷新持久化。开发验收需要可选的 Playwright：

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
python3 tests/run_todo_walkthrough.py
```

脚本创建临时 Git 项目、启动自己的本地服务器和无头浏览器，执行真实操作及 record、
report、complete、handoff 全流程，最后停止服务器并打印证据目录。端口 8000 需要空闲；
仓库自带示例的任务状态保持不变。

若使用自行启动的服务，可运行 `tests/todo_browser_acceptance.py --workspace PATH
--record`；不加 `--record` 只做浏览器回归。这个底层脚本可用 `HARNESS_CDP_URL`
连接专用 Chromium，临时演练脚本始终使用独立无头浏览器。Playwright 不属于运行时依赖。

## 从 v1 / v2 升级

先备份，再只替换 `template/.harness/` 中的 `harness.py`、`harness_init.py`、
`harness_runner.py` 三个代码文件，保留自己的配置、任务和证据。随后预览并显式迁移：

```bash
python3 .harness/harness.py migrate --dry-run
python3 .harness/harness.py migrate --note "确认以当前验收定义进入 v3"
```

迁移归档旧状态并保留历史证据。旧证据不能追溯获得代码与验收绑定，未完成任务需要
重验。v2 的原 Git/策略起点、阻塞状态和失败计数保留；旧完成任务明确标为历史记录。
v1 活跃任务若缺少可用起点，需要说明后重新建立起点。重复迁移安全，不会静默升级。

## 能力边界与开发检查

它适用于合作的开发者和 Agent。允许路径在完成时审计，审批操作配置只是流程要求，
不拦截系统调用。拥有代码和状态写权限的人可以绕过它。Git 忽略的依赖、外部服务、
环境变化以及验收定义质量，都不在源码摘要的保证范围内。

只支持单执行者，不提供多 Agent 并发事务。运行时不调用模型、不收集遥测、不提交或
推送 Git，也不发布内容。

`integrations/github/` 保留独立、可选的 GitHub Check Run 适配器。配置 `commands.check`
后，把 `minimal-harness-check.yml` 复制到项目的 `.github/workflows/`，把
`publish_check.py` 复制到项目的 `integrations/github/`。它只对可信 `push`
事件使用 `checks: write`，需要 `GITHUB_TOKEN`、`GITHUB_REPOSITORY` 和完整的
`GITHUB_SHA`。发布项目检查结果不会把 `run check` 自动变成任务验收证据。

```bash
python3 -m unittest discover -s tests -v
node --test examples/todo/test.mjs
ruff check --no-cache template/.harness integrations/github/publish_check.py scripts tests examples/quickstart
python3 template/.harness/harness.py --workspace template doctor
python3 template/.harness/harness.py --workspace examples/todo doctor
```

CI 保留 Linux/macOS/Windows 覆盖和真实 Chromium 验收。真实新用户试用另行记录，
自动化演练和 Agent 审查不能代替人类采用证据。

## 安全、贡献与许可证

安全问题请先阅读 [SECURITY.md](SECURITY.md)，贡献流程见
[CONTRIBUTING.md](CONTRIBUTING.md)。项目沿用 [MIT License](LICENSE)。
