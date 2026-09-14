# Minimal Harness v2 GitHub 同类资源独立复核与蒸馏判断

> 历史快照：本报告只描述 2026-09-13 的 v2 状态。证据新鲜度、许可证和发布缺口已在
> v0.2.0-beta.2 解决；当前竞品与定位结论见
> [2026-09-14 刷新报告](2026-09-14-github-harness-landscape-refresh.md)。

> 审计日期：2026-09-13
> 被审计提交：b523ba4f92d52795f6771ce9e6e7ad7f461b81d8
> 默认定位：Minimal, dependency-free, fail-closed completion proof layer for coding agents
> 蒸馏结论：**现在不蒸馏**

## 执行摘要

截至本次快照，**未发现完全替代品**。没有一个已核验候选同时具备运行时无关、repo-local 单任务闭环、Git 分支/HEAD/index/工作树精确范围审计、证据文件完整性复验、fail-closed 完成门禁、可信 handoff，以及 Python 3.9+ 标准库级体量。

广义替代方案已经存在。lordaeternus/agent-execution-harness 覆盖的任务图、typed evidence、claims、finish preflight 和 worker handoff 最接近；Ancienttwo/repo-harness 在验证对象、contract、command 和 Git revision 绑定上更强，但也是明显更重的工程系统。

Minimal Harness 仍有独立定位，但应收窄为：

> 面向任意 coding agent 的、Python 标准库实现的 repo-local acceptance kernel；它不规划、不调用模型、不编排 Agent，只负责证明“这项工作是否真的可以结束”。

独立盲审还发现一个首轮未充分强调的真实缺口：evidence JSON、日志和附件虽然有 SHA-256 绑定，证据却没有绑定验证当时的代码快照。验证通过后若在 allowed_paths 内再修改代码，complete 会复验旧证据文件和 Git 范围，却不能证明旧证据对应当前代码。此项应作为下一轮最高优先级安全加固。

## 独立性与只读边界

- 干净任务 01a096b1-404c-71c3-8610-9a2abcdf61d8 只接收仓库路径、固定 SHA 和审计问题，没有接收首轮候选或结论；它在独立 worktree 中完成了源码、许可证和活动度取证，最终长答生成停滞。
- 为避免把停滞任务的中间判断当作完整结论，又启动了干净任务 01a096d0-ca3b-7072-8ee8-e91886d38ca3；它同样未接收首轮候选或结论，并完整输出了盲审结论。
- 两个任务均跳过 docs/research，结束核验时没有修改本地仓库或 GitHub 远端状态。
- GitHub 网页登录态被强制 2FA 提醒页阻断；审计没有点击会写入远端状态的控件，转用已登录 gh 及 GitHub 公开 raw/API 做只读核验。

内部任务 ID 只用于本地追溯，不是技术证据。下文关键判断均链接到固定提交。

## 检索方法

检索词组覆盖 coding agent harness、completion gate、task evidence、Git scope、baseline、receipt、handoff、spec-driven development、long-running agents 和 task memory；另对 allowed_paths、sha256 evidence、require_git_for_completion 等实现词做精确检索。

证据优先级：

1. 固定提交下的源码、schema 和测试；
2. 固定提交下的 README 和技术文档；
3. 固定提交下的 LICENSE 与运行时 manifest；
4. GitHub 元数据和近期活动，仅作为成熟度参考。

星标不用于判断技术质量或相似度。候选按“直接同类”和“相邻生态”分层；每个候选只给一个关系判断：替代、集成、借鉴、差异化或忽略。

## Minimal Harness v2 已核验边界

指定提交已实现 Python 3.9+ 标准库运行时、单执行者任务状态、活动/阻塞任务的 schema v2 不变量、领取时冻结 branch/HEAD/unborn/工作树/index 指纹、分段 glob 路径审计、不可覆盖 evidence/log、附件哈希复验，以及 doctor/handoff/complete 共享的 fail-closed 门禁。

固定证据：[README](https://github.com/denggui-ai/minimal-harness/blob/b523ba4f92d52795f6771ce9e6e7ad7f461b81d8/README.md)、[Git 快照与范围审计](https://github.com/denggui-ai/minimal-harness/blob/b523ba4f92d52795f6771ce9e6e7ad7f461b81d8/template/.harness/harness.py#L471-L648)、[证据创建与复验](https://github.com/denggui-ai/minimal-harness/blob/b523ba4f92d52795f6771ce9e6e7ad7f461b81d8/template/.harness/harness.py#L983-L1165)。

已确认边界：

- evidence 未保存验证时 Git/代码快照，存在证据新鲜度缺口；
- manual 是人工声明，browser 虽强制 tool 和文件 artifact，仍不能单独证明摘要真实；
- approval_required_operations 是流程约束，不是 OS sandbox；
- 单执行者、无独立 evaluator；
- 指定提交根目录没有 LICENSE，也没有正式 release；若公开分发，这是采用和贡献边界的阻塞项。

## 直接同类短名单

| 候选与固定证据 | 核心判断 | 运行时 / 成熟度 | 关系 |
|---|---|---|---|
| [agent-execution-harness@4011872](https://github.com/lordaeternus/agent-execution-harness/blob/401187291bf9e0cf5c91eaaedcf578912411b770/README.md) | 任务图、typed evidence、claims、finish preflight 和 worker handoff 完整，是最接近的广义替代。其 [scope guard](https://github.com/lordaeternus/agent-execution-harness/blob/401187291bf9e0cf5c91eaaedcf578912411b770/src/core/scope-guard.ts#L42-L82) 聚焦当前 diff/index/untracked，未覆盖 Minimal 的 branch/HEAD、已提交变化和预脏内容指纹；[finish check](https://github.com/lordaeternus/agent-execution-harness/blob/401187291bf9e0cf5c91eaaedcf578912411b770/src/core/finish-check.ts#L21-L70) 未见完成时重算附件哈希。 | Node 20 + AJV，MIT，v0.17.2 | **替代** |
| [Ancienttwo/repo-harness@b962887](https://github.com/Ancienttwo/repo-harness/blob/b9628876aae4ec7076b459e4c4cac12a90a87828/README.md) | 任务 contract、evidence ledger、hook、worktree 和 closeout 面很广；证据类型绑定 [target commit、scope、subject、contract 和 command hash](https://github.com/Ancienttwo/repo-harness/blob/b9628876aae4ec7076b459e4c4cac12a90a87828/src/core/evidence/types.ts#L20-L29)，验证执行还绑定 tree/snapshot hash。能力更强但明显更重。 | TypeScript/Bun，MIT，高活跃 | **差异化** |
| [SUNRNEHUI/agent-harness@788f78a](https://github.com/SUNRNEHUI/agent-harness/blob/788f78a67a97d2197cb5a79c573c8b9b17897394/README.md#L214-L303) | Native/Portable/Audited 三档，包含 contract、事件、capsule、workspace fingerprint、evidence digest、owner epoch 和 resume drift；但属于 Skill/管理流程层，不是独立验收内核。 | Python 3.10–3.14，[MIT](https://github.com/SUNRNEHUI/agent-harness/blob/788f78a67a97d2197cb5a79c573c8b9b17897394/LICENSE)，v10 | **差异化** |
| [huangruiteng/loopx@0cbb847](https://github.com/huangruiteng/loopx/blob/0cbb8472fd09c3a335f46236bfecb998a61924de/README.md) | 长周期控制面，保存 objective/gate/todo/scope/evidence/quota/handoff；[completion validation](https://github.com/huangruiteng/loopx/blob/0cbb8472fd09c3a335f46236bfecb998a61924de/loopx/control_plane/todos/completion_validation.py) 验证声明哈希并在失败时不写回完成。Minimal 可作为其本地验收内核。 | Python 3.11+ + Node，Apache-2.0，高活跃 | **集成** |
| [gmickel/flow-next@7eeadd7](https://github.com/gmickel/flow-next/blob/7eeadd74c2100a1fe1a30a74dee669ebf610cc68/README.md) | 持久 spec、fresh-context worker、交叉审查和 receipt 很强；但底层 [done](https://github.com/gmickel/flow-next/blob/7eeadd74c2100a1fe1a30a74dee669ebf610cc68/plugins/flow-next/scripts/flowctl.py#L35499-L35572) 允许空 evidence，强约束依赖上层工作流与 hook。 | Python 内核 + 可选组件，MIT，高活跃 | **借鉴** |
| [Repo Task Proof Loop@8536221](https://github.com/DenisSergeevitch/repo-task-proof-loop/blob/853622144588798dc1b3babc81ed9499328321bf/README.md) | spec freeze → build → evidence → fresh verify 流程清晰；但 [validate_evidence](https://github.com/DenisSergeevitch/repo-task-proof-loop/blob/853622144588798dc1b3babc81ed9499328321bf/scripts/task_loop.py#L382-L416) 主要检查 JSON 字段/状态，没有 Git baseline 和附件哈希链。 | Python / Skill，Apache-2.0，小型 | **借鉴** |
| [Agent Lifecycle Kit@2706b99](https://github.com/avksp/agent-lifecycle-kit/blob/2706b99b4ec40bdf75ee3df7ac509a339d8620f1/README.md) | reviewed spec、frozen plan、bounded execution、adapter check 和 final proof 概念接近，另有多 provider adapter；范围远大于单任务验收内核。 | Python >=3.11，Apache-2.0，无运行时依赖，新兴 | **差异化** |
| [Garda@2befa7a](https://github.com/Shubchynskyi/garda-agent-orchestrator/blob/2befa7aa8a0e5bc39bfb8b4c0d4bef3a2b13e7d5/README.md) | 治理型本地运行时，任务生命周期、mandatory gates、review 和可审计完成面完整；它是大型 Node 编排器，不是可复制的最小证明层。 | Node 24，Apache-2.0，新兴 | **差异化** |

### 直接同类能力矩阵

图例：●=代码级明确支持；◐=部分支持或依赖上层流程；—=未见同等机制。

| 候选 | 生命周期 | Git 范围/基线 | 证据绑定 | 完成门禁 | Handoff | 最小运行时 |
|---|---:|---:|---:|---:|---:|---|
| Minimal Harness v2 | ● | ● | ◐ | ● | ● | Python 3.9+ stdlib |
| agent-execution-harness | ● | ◐ | ◐ | ● | ● | Node 20 + AJV |
| repo-harness | ● | ● | ● | ● | ● | TypeScript/Bun |
| SUNRNEHUI/agent-harness | ● | ◐ | ● | ◐ | ● | Python 3.10+ / Skill |
| LoopX | ● | ◐ | ● | ● | ● | Python 3.11+ + Node |
| Flow-Next | ● | ◐ | ◐ | ◐ | ● | Python + host workflow |
| Repo Task Proof Loop | ● | — | ◐ | ◐ | ● | Python / Skill |
| Agent Lifecycle Kit | ● | ◐ | ● | ● | ● | Python 3.11+ |
| Garda | ● | ◐ | ● | ● | ● | Node 24 |

Minimal 的证据绑定标为部分支持，因为它能强绑定证据文件本身，却尚未强绑定验证时的代码快照。

## 相邻生态短名单

| 候选与固定证据 | 核心判断 | 运行时 / 许可证 | 关系 |
|---|---|---|---|
| [github/spec-kit@d848fb4](https://github.com/github/spec-kit/blob/d848fb4e18f44640ad6b42e60a280551ee90cdce/README.md) | 强在上游规格和任务生成，不提供同等级 Git/证据完整性完成门禁。 | Python/uv，MIT，成熟 | **集成** |
| [Fission-AI/OpenSpec@9d4e597](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/README.md) | proposal/spec/design/tasks/apply/archive 适合生成 acceptance；非刚性 checklist 不是运行证据。 | Node >=20.19，MIT，成熟 | **集成** |
| [gastownhall/beads@f56632a](https://github.com/gastownhall/beads/blob/f56632adcfabed7da6ed0aabe4e760066b472c46/README.md) | 持久任务状态、依赖图、claim/close 和 Dolt 历史很强；任务 audit trail 不等于产品代码 acceptance evidence。 | Go/Dolt，MIT，成熟 | **集成** |
| [anthropics/cwc-long-running-agents@ad107a9](https://github.com/anthropics/cwc-long-running-agents/blob/ad107a974bced5244f74dd283dbf2bfd3baee3a1/README.md) | 默认 FAIL、证据先读、fresh evaluator、PROGRESS + Git commit handoff 值得借鉴；[verify hook](https://github.com/anthropics/cwc-long-running-agents/blob/ad107a974bced5244f74dd283dbf2bfd3baee3a1/claude-code-config/.claude/hooks/verify-gate.sh#L5-L12) 自述仍有绕过和证据对齐缺口。 | Claude Code + Bash/Python，Apache-2.0，不维护示例 | **借鉴** |
| [GanyuanRan/Aegis@750c7c6](https://github.com/GanyuanRan/Aegis/blob/750c7c6747512239d59cf93c9b4a7f6df7f2e0e3/README.md) | baseline-first、architecture-aware、drift check 和长任务续接强，但不是通用 CLI 验收内核。 | Python，MIT，活跃 | **借鉴** |
| [fusengine/harness@db97e7f](https://github.com/fusengine/harness/blob/db97e7fc594be8b4583806b2adb2bcc8f94bbbd7/README.md) | 跨宿主 hook/策略适配、Git 操作门禁和 fresh receipt 强；[TaskCompleted](https://github.com/fusengine/harness/blob/db97e7fc594be8b4583806b2adb2bcc8f94bbbd7/src/runtime/lifecycle/task-completed.ts#L27-L43) 可拒绝无新验证的代码任务，但受宿主 hook 上限影响。 | Bun/Node，MIT，活跃 | **借鉴** |
| [moshi-labs/handoff@8e6ca3f](https://github.com/moshi-labs/handoff/blob/8e6ca3fd4059a8f81df9e93a0995cd720b5d6318/README.md) | 只解决多宿主会话转换和 digest；neutral session、narrative 降级和只新建不覆盖值得参考。 | Node >=20，指定提交未见 LICENSE | **借鉴** |
| [open-gsd/gsd-core@a0270a7](https://github.com/open-gsd/gsd-core/blob/a0270a79452f94360d7c4acda81038d51a4df7a1/README.md) | discuss/plan/execute/verify/ship 和 fresh-context 流程成熟，但主要是方法与上下文编排。 | JavaScript，MIT，成熟 | **借鉴** |
| [maxritter/pilot-shell@925fa40](https://github.com/maxritter/pilot-shell/blob/925fa406a6955fca80d4cc82734741f769bc7dc3/README.md) | 功能面广，但 [专有许可证](https://github.com/maxritter/pilot-shell/blob/925fa406a6955fca80d4cc82734741f769bc7dc3/LICENSE) 禁止再分发、派生作品和竞争用途；不复制其实现或结构。 | 付费订阅，专有许可 | **忽略** |

### 相邻生态能力矩阵

| 候选 | 生命周期 | Git 产品范围 | 验收证据绑定 | 硬完成门禁 | 跨会话 | 主要价值 |
|---|---:|---:|---:|---:|---:|---|
| Spec Kit | ● | — | — | ◐ | ◐ | 规格/任务输入 |
| OpenSpec | ● | — | — | ◐ | ◐ | 变更提案/归档 |
| Beads | ● | — | ◐ | ◐ | ● | 任务记忆/依赖图 |
| CWC long-running agents | ● | ◐ | ◐ | ◐ | ● | fresh evaluator |
| Aegis | ● | ◐ | ◐ | ◐ | ● | 架构基线/漂移 |
| fusengine/harness | ◐ | ◐ | ● | ● | ◐ | 宿主 hook/fresh receipt |
| moshi-labs/handoff | — | — | — | — | ● | 中性会话转换 |
| GSD Core | ● | ◐ | ◐ | ◐ | ● | 方法/上下文编排 |
| Pilot Shell | ● | ◐ | ◐ | ● | ● | 不进入实现输入 |

## 首轮与独立盲审 reconciliation

### 一致项

- 无完全替代品，但广义替代和更大的编排平台已存在。
- Spec Kit、OpenSpec、Beads 是上游/相邻集成层，不是 completion proof 替换。
- 应保持最小内核，不把 Agent 调用、DAG、记忆系统或 sandbox 塞进核心。
- 现在不蒸馏；现有证据不证明跨项目审计 Skill 的增益。

### 独立盲审补出的遗漏

- 补出 agent-execution-harness、SUNRNEHUI/agent-harness、agentbrain、cwc-long-running-agents、fusengine/harness 和 moshi-labs/handoff。
- 另一条独立取证补出 repo-harness、LoopX、Flow-Next 和 Repo Task Proof Loop，显著增强了直接同类样本。
- 首轮关注 evidence 文件是否可篡改；独立盲审进一步指出“证据是否对应当前代码”的新鲜度问题。回读本地源码后确认该缺口成立。
- 独立盲审强调了发布风险：Minimal 指定提交未声明 LICENSE，而 Pilot Shell 是明确专有许可。

### 冲突与裁决

| 冲突 | 裁决 |
|---|---|
| 首轮更倾向 Agent Lifecycle Kit；盲审认为 agent-execution-harness 最接近。 | 按 CLI 闭环和 handoff 广度，agent-execution-harness 是最接近的广义替代；按证据与 revision/snapshot 绑定，repo-harness 更强；两者都不是 Minimal 体量下的完全替代。 |
| 部分 README 自称 fail-closed/evidence-first，源码只检查字段或当前 diff。 | 源码优先；只有能实际阻断完成并复验关键证据的才标为硬门禁。 |
| 表中“替代”似乎与“无完全替代品”冲突。 | “替代”表示可替代部分用户场景；“完全替代品”要求八个维度及小体量约束同时满足。 |

首轮还找到 [Crewplane@bc0b5ee](https://github.com/crewplaneai/crewplane/blob/bc0b5eef57622a66e79bf70a2274016c4445c19a/README.md)（**集成**）、[Forge@be95eff](https://github.com/ForgeAILab/forge/blob/be95eff20bdf41368541f8dc3d9f60c8248c5280/README.md)（**集成**）和 [Harness Starter Kit@62437be](https://github.com/harnessworks/harness-starter-kit/blob/62437bec264b2deed83353e8209660d645e86828/README.md)（**借鉴**）。对账后将它们列为补充样本，因为与独立 fail-closed acceptance kernel 的实现重合弱于直接短名单。

## 许可证风险

| 类型 | 处理规则 |
|---|---|
| MIT / Apache-2.0 | 可研究，并在满足归属/通知要求后复用；本轮只比较机制，未复制实现。 |
| Pilot Shell 专有许可 | 不复制 prompt、源码、脚本、配置、架构结构或派生实现；不将其源代码作为产品设计基底。 |
| 无 LICENSE | 默认未获得复制、修改或分发许可，只做黑盒概念参考。Minimal 自身公开发布前也必须解决此问题。 |

## 值得借鉴的机制

1. **证据绑定验证时代码快照**：独立设计 target commit/tree/snapshot/contract/command hash；complete 要求当前快照与 passed evidence 快照一致，否则降为 unverified。
2. **只读 preflight**：提供类似 finish check 的命令，一次解释缺失证据、越界路径、Git 漂移和下一条可执行命令。
3. **fresh-context evaluator 证据类型**：Harness 不内置 Agent 调用，只定义可导入的 independent-review evidence。
4. **Native / Portable / Audited 分档**：明确哪些宿主能硬阻断、哪些只能生成文件、哪些可提供独立审查。
5. **稳定 handoff capsule**：参考 owner epoch、字符预算、neutral session 和 narrative 降级，同时继续对未验证内容显式标警。
6. **只做轻适配**：Spec Kit/OpenSpec 导入 acceptance，Beads 导入任务 ID/依赖；不复制其规划、记忆或编排语义。

## 三个必答问题

### 是否已有完全替代品？

**没有。** agent-execution-harness 是最接近的广义替代，repo-harness 的快照绑定更强，但二者都未在 Minimal 的 Python 3.9+ 标准库体量下复制其整套 Git 与完成门禁组合。

### 哪些机制值得借鉴？

最高优先级是证据新鲜度绑定；其次是只读 preflight、可导入的 fresh evaluator evidence、宿主硬/软门禁兼容矩阵，以及更稳定的 handoff capsule。

### Minimal Harness 是否仍有独立定位？

**有，但必须保持收窄。** 它的价值不是“又一个 coding-agent workflow”，而是不依赖 Agent 平台的最小、可复制、fail-closed acceptance kernel。

## 蒸馏门禁

| 条件 | 现状 | 结果 |
|---|---|---|
| 同一审计流程在至少 3 个不同项目重复使用 | 只对 Minimal Harness 做了一次景观审计 | 未满足 |
| 输入、输出、分类和证据要求稳定 | 八维矩阵可用，但直接/相邻和关系分类仍在对账中调整 | 未满足 |
| 有回归样例证明 Skill 优于普通模板 | 无 Skill-vs-template 对照 eval | 未满足 |
| 清晰区分 GitHub 调研、代码审计、产品定位触发边界 | 本次三者高度耦合，无跨项目路由证据 | 未满足 |

**单一结论：现在不蒸馏。** 保留本报告结构为可复用 Markdown 模板。未来四项条件同时满足后，再用系统 skill-creator 单独 authoring，随后用 production governor 做第二阶段质量门禁；不要把 CLI 核心逻辑重写为 prompt。

## 下一步建议

1. **P0，发布前：明确许可证。** 若计划公开使用或接受贡献，由所有者选择并确认 LICENSE；本报告不代替所有者作许可证决定。
2. **P0，安全：绑定 evidence 与验证时 Git 快照。** 先写“验证通过后在允许路径内改代码仍被 complete 接受”的失败测试，再设计 schema 和迁移。
3. **P1，可用性：增加只读 preflight。** 优先给出门禁原因和下一命令，不扩展为新编排器。
4. **P1，可信度：定义独立审查证据导入格式。** evaluator 由宿主或 CI 运行，Harness 只校验输出、评审对象和代码快照。
5. **P2，集成：只做一个单向导入 spike。** 从 Spec Kit、OpenSpec、Beads 中选一个，不引入核心运行时依赖。
6. **蒸馏：暂停。** 先用本模板在 3 个不同仓库重复审计，保留遗漏对照和评分，再决定是否进入 Skill 候选。

## 最终判断

- 完全替代品：**未发现**。
- 最接近的广义替代：**agent-execution-harness**。
- 最值得研究的证据快照绑定：**repo-harness**。
- Minimal Harness 独立定位：**成立，但必须保持最小 acceptance kernel 边界**。
- 当前蒸馏结论：**现在不蒸馏**。
