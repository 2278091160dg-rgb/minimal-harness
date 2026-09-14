# CLI 完整参考

[English](cli-reference.md) · [README](../README.zh-CN.md) ·
[实战指南](usage-guide.zh-CN.md) · [文档索引](README.zh-CN.md)

本文覆盖 schema v3 的全部 parser 接口。CLI 在中英文流程中都输出英文；没有语言或 locale 选项。

## 调用与路径规则

```text
python3 PATH/TO/.harness/harness.py [--workspace PATH] COMMAND [COMMAND OPTIONS]
```

- `--workspace PATH` 是唯一全局选项，必须出现在 `COMMAND` 前。
- 省略时，工作区是脚本文件所在目录的上级目录。对已安装的
  `PROJECT/.harness/harness.py`，结果就是 `PROJECT`，与 shell 当前目录无关。
- 除 `init` 正在创建安装外，工作区应包含 `.harness/config.json` 和
  `.harness/tasks.json`。
- `task add/revise --from` 的相对路径以 shell 当前目录解析；`record --artifact`
  的相对路径以工作区解析；配置的 argv 以工作区作为当前目录执行。
- argv 中 `{python}` 替换为启动 Harness 的解释器；命令不经过 shell。
- 顶层和各级子 parser 都支持 `-h`/`--help`，没有 `--version`。

PowerShell 的顺序相同，通常把 `python3` 换成 `py -3`。

## 状态与退出码

任务状态是 `pending / in_progress / blocked / done`；检查状态是
`not_run / passed / failed / unverified`。只有 `passed` 满足完成条件。最多一个当前任务，
其状态是 `in_progress` 或 `blocked`。

| 退出码 | 含义 |
| --- | --- |
| `0` | 操作成功、报告 ready，或有效查询没有 pending 工作。 |
| `1` | 命令/检查失败、流程门未满足或已过期、记录了非 pass，或 `doctor` 发现已通过证据过期。 |
| `2` | CLI 用法、配置/schema/路径错误，执行准备失败，或证据损坏/不一致；`argparse` 用法错误也返回 2。 |
| `130` | 用户中断；被中断的验证不会保留通过状态。 |

正常结果写 stdout，错误写 stderr。子进程非零码在 Harness 层归一为 1，原码仍写入 command 证据。

## 读写表

| 命令 | Harness 自己的写入 | 其他可能影响 |
| --- | --- | --- |
| `init --dry-run`、`doctor`、`status`、`report`、`migrate --dry-run` | 无 | 读取文件与 Git。 |
| `init` | 全新 `.harness/` 运行时/配置/任务/交接/许可证；可选托管指令 | 不初始化 Git、不装依赖。 |
| `task add`、`task revise`、`next`、`record`、`complete`、`unblock` | `.harness/tasks.json`、所需证据、交接 | 除显式读取附件外无额外影响。 |
| `verify` | 任务状态、attempt、日志、证据、交接 | 验收子命令可凭 OS 权限修改任意位置；Harness 审计漂移，不主动拦截。 |
| `run setup`、`run check` | `.harness/attempts/runs/` 下的受限日志 | 配置子命令可能修改项目或外部系统。 |
| `run start` | 不写 Harness 日志 | 前台子命令可能修改状态，并运行到自行退出或被中断。 |
| `handoff` | `.harness/HANDOFF.md` | 无。 |
| `migrate` | 迁移归档、配置、任务、交接 | 不改应用源码。 |

“只读”只描述 Harness 自有文件。Git 读取禁用 optional lock；配置子命令仍保留自己的能力。

## 定义与配置前提

除 `init` 外都需要已安装工作区。常规流程需要 schema v3 配置和任务版本一致；`migrate`
还接受一致的 v1 或 v2。

`task add/revise --from` 显式读取 UTF-8 JSON 对象，顶层只能有 `id`、`title`、非空
`acceptance`，不能有生成的状态、计数、证据、基线或未知字段。每条检查包含：

- 通用：`id`、`type`、非空 `instruction`；
- command：非空字符串数组 `command`，可选正有限数 `timeout_seconds`（默认 300）；
- browser/manual：非空字符串数组 `steps`。

ID 长 1–128 个 ASCII 字母、数字、`.`、`_`、`-`，并以字母或数字开头。配置必须包含
`commands.setup/start/check`，值为 `null` 或非空字符串数组；策略必须有正失败阈值、安全相对
`allowed_paths`、操作指令数组和布尔 Git 要求。

## `init`

```text
python3 template/.harness/harness.py [--workspace PATH] init
    [--agent {codex,claude,generic}] [--dry-run]
```

从模板或分段 ZIP 调用时实际上必须写 `--workspace`，否则默认工作区会是模板/分段目录。
目标目录须已存在。`--agent codex`/`generic` 目标是 `AGENTS.md`；`claude` 目标是
`CLAUDE.md`；省略则不写宿主指令。`--dry-run` 预检并列出变化。

当前未发布源码在写入前一次性预检同一来源目录中的 `harness.py`、`harness_init.py`、
`harness_runner.py` 和 `LICENSE`。全新安装把这四个文件放入 `.harness/`，并创建配置、
空任务与交接，不改变项目根许可证。已发布 beta.1 的历史 ZIP/运行时只有三个 Python 模块，
没有运行时许可证。

重复 init 验证整套运行时和状态，也可以补上一个缺失的托管指令区块，但不升级。当前源码遇到
旧 v3 安装缺 `.harness/LICENSE`、运行时字节不同、局部安装、符号链接、冲突/残缺托管区块时，
会要求显式升级。

成功会输出 dry-run 清单、`Initialized: PATH` 或 `Already initialized: PATH` 以及后续建议。
退出 2 表示未成功初始化；预检应在写前失败，并回滚本次操作新建的文件。应把来源放到项目外，
修正报告的冲突，或执行显式升级。

## `task`

`task` 是必选命令组，自身没有选项，后面必须且只能接 `add` 或 `revise`。只调用 `task`
属于用法错误并返回 2。

## `task add`

```text
python3 .harness/harness.py task add --from DEFINITION.json
```

`--from` 必填，不从 stdin 或 `.harness/tasks.json` 推断；相对路径按调用者当前目录解析。
在任意有效流程状态下都可添加唯一 pending 任务，包括另一个任务 active 时。Harness 生成运行态
字段，写任务状态、刷新交接，输出 `Task add: ID`。

重复 ID、字段错误、不安全 ID、检查定义错误、文件缺失/不可读都返回 2，且不添加任务。修正后重试。

## `task revise`

```text
python3 .harness/harness.py task revise TASK_ID --from DEFINITION.json --note TEXT
```

三个参数均必填；定义 ID 必须等于 `TASK_ID`，`--note` 去空白后非空。任务必须是
`pending` 或 `in_progress`。修订保存旧定义与验收状态，替换标题/检查，把所有新检查设为
`unverified`，冻结新契约，刷新交接并输出 `Task revise: ID`。

任务领取时的 Git/策略基线仍保留，因此不会扩大允许范围。done 或当前 blocked 返回 1；后者先
`unblock`。定义/ID/note 错误返回 2。active 任务每次修订后都要重验。

## `doctor`

```text
python3 .harness/harness.py doctor
```

只读。检查 schema、配置、任务/证据结构、配置命令与验收命令的可执行文件、Python 3.9+、
证据文件元数据，以及 active/blocked 已通过检查的当前 Git/源码新鲜度。输出配置/任务数、Git
身份或不可用警告、脏路径数和相关 warning。

退出 0 表示结构有效且 active passed 证据未过期；退出 1 表示结构有效但证据过期，应查看报告并
重验；退出 2 表示配置、可执行文件、证据、文件系统或 Git 检查不可信，先修复明确故障。
没有 Git 通常只在这里 warning，但冻结策略要求 Git 时仍不能完成。

## `status`

```text
python3 .harness/harness.py status
```

只读。需要有效 v3 状态，输出项目名、当前任务以及所有任务/检查的状态和类型。不审计新鲜度或
ready。状态可加载时返回 0，结构错误返回 2；完成问题使用 `report ID`。

## `next`

```text
python3 .harness/harness.py next
```

选择第一个 pending 任务，改为 `in_progress`，记录开始时间和 Git 基线，冻结当前策略与验收
契约，设为当前任务，刷新交接并输出 `Selected ID: TITLE`。

已有当前任务或任何 blocked 任务时返回 1，应恢复/解阻。没有 pending 时输出
`No pending tasks.`，返回 0 且不改状态。领取时可没有首个 Git 提交，但默认策略下缺失 Git
基线不能完成。策略与任务定义应在此命令前配置好。

## `run`

```text
python3 .harness/harness.py run {setup,start,check}
```

位置参数必填，直接对应 `commands.setup`、`.start`、`.check`。配置为 `null` 时返回 1 并输出
`commands.NAME is not configured`；可执行文件不可启动或配置错误返回 2。

`setup`/`check` 使用受限 runner，显示捕获输出，并在 `.harness/attempts/runs/` 写日志；
默认 300 秒、10 MiB。正常零退出返回 0；非零、超时、超量返回 1；中断返回 130。
`start` 不限时并保持前台，正常零退出为 0，非零为 1，Ctrl-C 为 130。

三者都不记录任务验收，`run check` 也不例外。需要授权完成时，要定义 command 验收并运行
`verify`。子进程不在沙箱中；运行前审阅 argv，产生的变化由操作者处理。

## `verify`

```text
python3 .harness/harness.py verify [TASK_ID]
```

省略 ID 使用 `current_task_id`；显式 ID 必须与当前任务一致。任务必须是 `in_progress`，契约
当前未变，并且至少有一条 command。browser/manual 会被忽略，须用 `record`。

启动子进程前，Harness 先让批次中旧 command passed 失效。按定义顺序为每条命令捕获源码/
契约、写 running attempt，以其超时和 10 MiB 上限执行并显示日志，再审计源码/任务状态，写
attempt、证据、状态和交接。遇到第一条非 pass 即停止。命令都从工作区运行且不经过 shell。

全部 command 在一致快照上通过时返回 0。子进程失败、超时、超量或发现漂移返回 1；中断 130；
状态、证据/路径损坏、可执行文件缺失或执行准备错误返回 2。某检查达到冻结的连续失败阈值会
阻塞任务。修好后重跑；blocked 时先 `unblock`。command passed 不能推断 browser/manual passed。

## `record`

```text
python3 .harness/harness.py record TASK_ID CHECK_ID
    --result {passed,failed,unverified}
    --summary TEXT
    [--tool TOOL]
    [--artifact FILE ...]
```

ID、检查 ID、`--result`、`--summary` 必填。任务须是当前 `in_progress`，检查须为 browser
或 manual，契约未变。summary 去空白后非空。`--artifact` 可重复；每个路径须是项目内已有、
非符号链接的普通文件。相对路径按工作区解析。Harness 记录元数据/摘要，不复制文件。

browser passed 还必须有非空 `--tool` 与至少一个附件；browser 的 failed/unverified 和所有
manual 可省略两者。只有实际执行并观察定义步骤后才能记 passed。Harness 保存操作者声明，
不启动浏览器，也不证明陈述真假。

命令写证据、任务状态、交接，输出 `Recorded TASK/CHECK: RESULT`。passed 返回 0 并重置该检查
失败计数；failed 返回 1、计数加一，到阈值后 blocked；unverified 返回 1 且不算通过。
command 类型、路径/附件、选项或空字段错误返回 2。应修正实际观察/附件或如实记录非 pass。

## `report`

```text
python3 .harness/harness.py report TASK_ID [--format {text,json,markdown}]
```

ID 必填，格式默认 `text`。命令只读，与 `complete` 共用审计器，展示各检查、来源、证据路径、
summary、附件、问题、ready 和下一命令。JSON 还包含 schema、任务状态、`historical`、检查详情、
`integrity_errors`、Git 策略标志及结果退出码。输出到 stdout；不上传，也不创建报告文件。

ready 返回 0；普通未满足门禁或过期证据返回 1；证据完整性损坏返回 2。done 任务仅作历史报告，
返回 1，没有再次完成权限。跟随 `next_command`：源码/契约漂移需重验；范围或 Git 身份问题通常
先看 `git status --short` 或 `doctor`。

## `complete`

```text
python3 .harness/harness.py complete TASK_ID
```

任务必须是当前 `in_progress`；全部检查都有完整、当前 passed 证据；验收契约与源码快照一致；
领取后改动都在冻结的 `allowed_paths` 内；冻结策略要求 Git 时 Git 可用。即使策略允许无 Git
完成，只要 Git 实际可用，其当前身份仍属于源码新鲜度绑定。

成功后任务变 `done`，记录完成时间，清空当前任务，刷新交接，输出 `Completed ID: TITLE` 并
返回 0；不会提交或上传。门禁未满足/过期返回 1，证据/配置/完整性错误返回 2。用 `report ID`
查看同一审计；若源码、index、HEAD、分支或契约改变，修正后重验。

## `unblock`

```text
python3 .harness/harness.py unblock TASK_ID --note TEXT
```

两参数必填。任务须是当前 blocked，note 去空白后非空。成功会追加解阻历史，重置所有检查失败
计数，把 failed 检查改为 unverified 并清除证据引用，任务回到 `in_progress`，刷新交接，
输出 `Unblocked ID`，返回 0。

任务/状态错误返回 1；note 缺失/空或状态损坏返回 2。解阻不修行为、不让验收通过；先处理原因，
再 `verify` 或 `record`。

## `handoff`

```text
python3 .harness/harness.py handoff
```

根据当前配置、任务、Git、证据、失败、新鲜度和下一动作重新生成 `.harness/HANDOFF.md`，
输出更新路径并返回 0。不创建 Agent 会话，也不上传。状态/证据/Git 检查错误返回 2；修复后重试。
下一会话改文件前先运行 `doctor`、`status` 并阅读 handoff。

## `migrate`

```text
python3 .harness/harness.py migrate [--dry-run] [--note TEXT]
```

接受 config/tasks 同为 v1、v2 或 v3。`--dry-run` 校验并描述 v1/v2 转换而不写入。
完全 inactive 时 `--note` 可省；存在 `in_progress` 或 `blocked` 时必须提供非空 note，确认当前
验收定义。

真实 v1/v2 迁移在 `.harness/migrations/` 写带时间戳的原 config/tasks 与 manifest，转换
配置/任务并刷新交接。未完成任务的 passed 证据只保留作 legacy 历史，检查变 unverified；done
保留为历史。v2 Git/策略基线和阻塞计数保留；active/blocked v1 任务获新基线，旧基线存入
`legacy_baselines`。

成功或已经 v3 返回 0。schema 不匹配、旧状态无效、legacy 证据不安全、缺必需 note 或文件错误
返回 2。不会静默升级。先备份状态、复制目标运行时、dry-run，再迁移并重验未完成任务。

## 可选 GitHub 适配器不属于此 parser

不存在 `github`、`publish`、`commit`、`push` 或自动打开浏览器的子命令。独立的
`integrations/github/` 示例运行 `doctor` 和 `run check`，再由另一个脚本使用 GitHub 环境变量
为可信 push 发布 Check Run。该发布不是本地任务验收证据。
