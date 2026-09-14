# Minimal Harness v3 GitHub 竞品格局刷新

> 审计日期：2026-09-14
>
> 产品基线：[`v0.2.0-beta.2@15c3436`](https://github.com/denggui-ai/minimal-harness/tree/15c3436ae7318021e5cb18e3cfaa560df1af5e2e)
>
> 结论：定位成立，但竞争力来自一组窄而完整的能力组合，不来自单项功能独占

本报告更新
[2026-09-13 的 v2 历史审计](2026-09-13-github-harness-landscape-audit.md)。
旧报告发现的三个发布阻塞已经改变：v3 evidence 现已绑定验证时的源码与完整契约，仓库和
运行时 ZIP 已包含 MIT License，并且已经发布可复现的 GitHub Release。同时，GitHub 上又出现
或被检索到更直接的 completion gate 候选，因此不能沿用“轻量、离线、fail-closed 本身就是
差异化”的说法。

## 执行摘要

- **已有直接替代。** 只需要独立 completion admission 时，x-harness 和 Proofed 都能覆盖
  重要场景；需要完整 Agent 工作流时，repo-harness、Agentic Harness、Garda 和 Kratos 提供
  更广的能力。
- **Minimal Harness 仍有独立位置。** 它把任务生命周期、真实命令验收、证据完整性、完整
  contract/Git 新鲜度、完成门禁与 handoff 放进一个约 145 KB、Python 3.9+ 标准库、可复制到
  仓库的运行时中。
- **当前短板不是功能数量。** 仓库没有独立采用证据，也尚未进入主要 Agent Harness 收录清单；
  README 先前没有直接解释“为什么选择 Minimal Harness”。
- **不做功能追平。** 规划、模型调用、Agent 调度、长期记忆、GUI、daemon、数据库和 OS 沙箱
  继续留在边界之外。
- **唯一值得进入下一轮设计的窄能力缺口**是 GitHub exact-candidate verification：当前示例
  adapter 运行 `doctor` 和项目级 `run check`，但没有重新验证一个指定 task 的完整 acceptance
  并发布与 commit/contract 绑定的 receipt。

## 证据口径

候选提交在 2026-09-14 通过 GitHub API 固定。证据等级分为：

1. **本地验证**：在固定代码上运行或检查了源码与测试；
2. **源码复核**：检查固定提交的实现、schema 或测试，但本轮未执行；
3. **文档声明**：只确认固定提交的 README／技术文档如何描述能力；
4. **GitHub 信号**：星标、fork、更新时间和下载量，只表示发现或采用线索，不证明质量。

表中的星标与 fork 是审计日快照，不进入 README。没有本地执行的竞品能力不得写成已经独立
证明。一个搜索引擎缓存中的 Keepgate 仓库在本轮无法再通过 GitHub API 解析，因此没有进入
当前短名单。

## Minimal Harness 已验证基线

| 能力 | 固定证据 | 判断 |
| --- | --- | --- |
| 小运行时 | [Release](https://github.com/denggui-ai/minimal-harness/releases/tag/v0.2.0-beta.2) 中的 ZIP 为 145,005 bytes；Python 3.9+ 标准库，无模型 API／服务 | 成立；“minimal”应以依赖和部署边界表达，不以源码行数表达 |
| 单任务闭环 | [README 能力地图](https://github.com/denggui-ai/minimal-harness/blob/15c3436ae7318021e5cb18e3cfaa560df1af5e2e/README.md#capability-map) 覆盖 `task add`、`next`、`verify`／`record`、`report`、`complete`、`handoff` | 成立 |
| evidence 新鲜度 | [v3 设计](../superpowers/specs/2026-09-13-evidence-freshness-and-release-design.md)和源码测试覆盖 branch、HEAD、index、tracked/non-ignored 内容、预脏状态、契约与 submodule | 成立；任何相关漂移要求重新验证 |
| 真正运行验收 | command acceptance 由受限 runner 执行并保留原始日志；browser/manual 明确只是 observation/attestation | 成立，但不能把人工或浏览器摘要宣传为独立真实性证明 |
| 工程验证 | [验证报告](../superpowers/reports/2026-09-14-hardening-validation.md)记录 231 项 Python 测试、Node、Ruff、三系统 CI 与真实 Chromium 流程 | 成立；三名真实新用户试用仍未完成 |
| GitHub adapter | [`minimal-harness-check.yml`](https://github.com/denggui-ai/minimal-harness/blob/15c3436ae7318021e5cb18e3cfaa560df1af5e2e/integrations/github/minimal-harness-check.yml) 以最小权限运行 `doctor` 和 `run check`，可信 push 才发布 Check Run | 安全边界清楚，但不是 task exact-candidate completion receipt |

## 直接与广义替代

| 候选（固定提交） | 重合与差异 | 本轮证据 | 2026-09-14 GitHub 信号 |
| --- | --- | --- | --- |
| [x-harness@10777da](https://github.com/BrianNguyen29/x-harness/tree/10777da0c44697807a37917edbc8af618093e50b) | 最直接的轻量替代：file-first、离线、fail-closed admission、静态 Go binary、多宿主 adapter。文档说明 evidence runner 记录 Git commit/branch/dirty baseline，并有 verifier mutation guard。Minimal 的区别是把 task lifecycle、acceptance execution、contract/source freshness 和 handoff 组成默认闭环。 | 固定 README、Evidence Provenance、Verify Gate 文档；未本地执行 | 14 stars、5 forks；稳定版 1.0.0；最后 push 2026-08-13 |
| [Proofed@2f1dd54](https://github.com/liangfeng-hu/proofed/tree/2f1dd546115227982dcabb33c65cc404c589adf5) | 直接竞争“新鲜 evidence receipt”：`verify --run-tests`、current-subject binding、代码变化后 receipt 失效、GitHub Action 重新运行检查。范围比 Minimal 的任务状态与 handoff 更窄，但 GitHub exact-candidate 表达更直接。 | 固定 README 与公开 spec 声明；未本地执行 | 0 stars、0 forks；alpha；最后 push 2026-08-31 |
| [agent-execution-harness@4011872](https://github.com/lordaeternus/agent-execution-harness/tree/401187291bf9e0cf5c91eaaedcf578912411b770) | plan、typed evidence、claims、finish preflight、worker handoff、codebase/learning memory 都更广。Minimal 的优势是更小的无依赖运行时与更深的默认 Git/contract freshness；不与其记忆和调度能力竞争。 | 上轮固定提交源码复核；提交未变化 | 2 stars、0 forks；最后 push 2026-06-30 |
| [repo-harness@d5b4f22](https://github.com/Ancienttwo/repo-harness/tree/d5b4f22b981906039463403af87feedb3546c7f5) | 完整 PRD/plan/task/worktree/hook/MCP/skills/review/ship 系统，能力面和采用信号都显著更强。它是广义替代或上层系统，不是 Minimal 应追平的体量。 | 当前 README；上轮在较早提交做过 evidence/snapshot 源码复核 | 431 stars、34 forks；约 43 MB 仓库；最后 push 2026-09-13 |
| [Agentic Harness@ec36f34](https://github.com/moortekweb-art/agentic-harness/tree/ec36f341a528fe595c45f03462d2ccc61cf1db1d) | 自托管 completion gate、独立 verification、CLI 与本地 GUI，可连接多种 worker/model。它在独立审查与易用界面上更强，但也引入完整执行环境。 | 固定 README 与 Evidence Contract 文档；未本地执行 | 3 stars、0 forks；约 18 MB；最后 push 2026-08-30 |
| [Garda@2befa7a](https://github.com/Shubchynskyi/garda-agent-orchestrator/tree/2befa7aa8a0e5bc39bfb8b4c0d4bef3a2b13e7d5) | provider-neutral task workflow、mandatory gates、review、doc-impact 与 audit trail，属于治理型 Node orchestrator。Minimal 可作为更低层的验收内核，不复制其治理面。 | 上轮与本轮固定 README/源码复核 | 26 stars、0 forks；约 16 MB；最后 push 2026-08-31 |
| [Kratos@c05f999](https://github.com/thiagocorreanet/kratos-harness/tree/c05f99980a6708f2d435c284222a5926e04813f9) | deterministic、observable、spec-driven workflow 与人控交付，覆盖从规格到交付的更长链路。Minimal 不承担 SDD 上游。 | 固定 README 声明；未本地执行 | 16 stars、2 forks；最后 push 2026-09-04 |

许可证快照：x-harness、agent-execution-harness、repo-harness、Agentic Harness 和 Kratos 为
MIT；Proofed 与 Garda 为 Apache-2.0。本轮只比较公开机制，没有复制竞品实现。

## 按用户任务选择

| 用户真正需要的工作 | 更合适的类别 | Minimal 的位置 |
| --- | --- | --- |
| 判断一张 completion card／receipt 能否接受 | Standalone admission gate | x-harness 或 Proofed 是有效替代；Minimal 不是唯一选择 |
| 在本地完成 task → acceptance → evidence → completion → handoff | Minimal acceptance kernel | Minimal 的组合优势最清楚 |
| 规划、委派、记忆、多 worker、hooks、GUI 或 provider routing | Full agent orchestrator | 选择 repo-harness、Agentic Harness、Garda、Kratos 等；Minimal 只做互补内核 |
| 只验证 push／pull request | CI verifier | 使用 CI 原生验证；Minimal 的本地状态机不是必需 |

因此，公开定位不应再写成“市场上没有替代品”，而应写成：

> Minimal Harness 是一个可复制的、与 Agent 无关的本地验收与交接内核。它用同一套
> fail-closed 状态机运行命令验收，把证据绑定到完整 contract 与 Git 验证对象，并在证据仍然
> 新鲜时才允许完成。

## 最强反方意见

1. **纯 completion gate 用户会认为 x-harness 更成熟。** 它有稳定版、静态 binary、更多 adapter、
   完整威胁模型和更多 GitHub 采用信号。
2. **Git 新鲜度不是独占能力。** Proofed 已明确宣传 current-subject receipt；x-harness 也记录
   Git 与 dirty baseline。Minimal 必须强调“完整闭环中的默认强绑定”，不能把 freshness 单独
   宣传成无人具备。
3. **工程测试不等于产品采用。** 当前自动化能证明实现行为，不能证明新人能独立安装、理解
   rejection 或愿意复用。
4. **名称发现竞争激烈。** [Best of Agent Harnesses](https://github.com/RyanAlberts/best-of-Agent-Harnesses)
   已收录 100+ 项目；本轮检查其 `harnesses.json` 未找到 Minimal Harness。

## 采用与发现快照

GitHub API 在审计日显示 Minimal Harness 为公开仓库，0 stars、0 forks。维护者可见的 14 日
traffic 快照只出现 1 个 unique cloner；view 数据尚未覆盖公开后的完整日期。三个带 ZIP 的
发行版本累计显示 10 次 ZIP 下载，但 README 与发布检查会主动下载这些 ZIP，因此不能把该数字当作
独立用户数。

唯一诚实结论是：**尚无外部采用证据。** 继续使用
[首次真人试用表](../adoption-validation.md)收集三名未接触过本项目的开发者结果，不用自动化
walkthrough 替代真人反馈。

## 能力优先级与停止线

### P0：先验证采用

- 完成三名首次用户试用；保留失败、求助点、首次成功时间、对 stale evidence 的理解和复用意愿。
- README 用可复核的组合能力解释定位，并链接本报告。
- 更新 GitHub About 描述；使用[收录材料草案](../launch/2026-09-14-best-of-agent-harnesses-submission.md)
  准备进入主要清单，但外部投稿单独授权。

### P1：只设计 GitHub exact-candidate verification

若真人试用或真实 issue 证明 GitHub/CI 绑定是采用阻塞，再设计一个干净 checkout 上的单次验证
入口：重新运行指定 task 的 acceptance，生成包含 commit、contract、check 与 artifact hashes 的
版本化 receipt，再由最小权限 Action 发布。设计前不得把现有 `run check` 宣传为 task completion。

### P2：独立 review evidence 导入

只定义 provider-neutral 的 reviewer evidence schema 和验证规则。评审模型或 reviewer 由宿主、
CI 或人工运行；核心不调用模型，也不建立调度系统。

### 明确不做

- Agent 规划、模型调用或 provider router；
- DAG、多 Agent 调度或并发写入；
- 长期记忆、向量数据库或后台 daemon；
- GUI、托管服务或 OS sandbox。

在三名真人试用和真实问题单出现前，不因竞品功能更多而突破这些停止线。

## 最终判断

- 同类资源：**很多，且已有直接替代。**
- 独立竞争力：**成立，是 task/acceptance/evidence/freshness/completion/handoff 与小运行时的组合。**
- 是否继续补能力：**暂不横向扩张；P1 只保留 exact-candidate GitHub verification 的证据门槛。**
- 是否同步 GitHub：**是；README、About 与日期化研究应立即更新，Release 历史保持不变。**
