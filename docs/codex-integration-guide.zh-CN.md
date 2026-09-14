# Codex × Minimal Harness 应用攻略：从 Skill 开发到大型项目

[English](codex-integration-guide.md) · [项目首页](../README.zh-CN.md) ·
[实战使用指南](usage-guide.zh-CN.md)

本文从用户第一次看到 Minimal Harness 时最常见的问题出发，逐步说明它是什么、何时值得用于
Skill 开发、怎样与 Codex Goal 和 Plan Mode 分工，以及大型项目如何在并行开发之后保留一条
可信的完成与交接链路。

**兼容范围：Minimal Harness v0.2.0-beta.2 · schema v3 · Codex 文档核验日期 2026-09-14**

本文中的 Goal、Plan Mode、项目、子智能体和 worktree 是 Codex 能力；Minimal Harness 不调用
模型，也不负责启动或编排这些能力。Codex 功能可能继续变化，请以文末链接的 OpenAI 官方文档
为准。

## 先用一句话理解它

Minimal Harness 是放在 Git 仓库里的轻量验收内核，可以把它理解成 AI 编程助手旁边的
“验收员、证据记录簿和跨会话交接单”。它负责：

1. 保存任务及其验收定义；
2. 运行 command 检查，记录 browser/manual 观察；
3. 把证据绑定到当前契约、源码和 Git 验证对象；
4. 在证据仍然新鲜时才允许完成任务；
5. 生成 `.harness/HANDOFF.md` 供下一次会话接续。

它不是 AI Agent、项目管理器、CI 替代品、OS 沙箱或并发协议。它只有一个刻意保持很窄的职责：
回答“这项工作现在是否有足够且仍有效的证据，可以登记完成”。

## 它对 Skill 开发是否有价值

取决于 Skill 的可验证程度，而不取决于 `SKILL.md` 有多长。

| Skill 类型 | 建议 | 原因 |
| --- | --- | --- |
| 短提示词、没有脚本或产物 | 轻量使用或暂不接入 | 维护 Harness 任务的成本可能大于收益，先写少量 eval 更重要 |
| 带脚本、文件转换或工具调用 | 推荐接入 | command 验收、日志和源码新鲜度能防止旧结果冒充当前结果 |
| 带浏览器、图片、视频或人工判断 | 推荐接入并保留附件 | Harness 能记录声明和附件元数据，但不会独立判断内容质量 |
| 需要审计、发布或自进化证据 | 作为最外层完成门 | 它能串起验证过程，但不能替代领域标准、grader 或人工评审 |

一条实用的职责链是：

```text
skill-creator → evals → production governor → Minimal Harness
     编写         行为验证          质量审计              完成与证据门禁
```

这里的 `skill-creator` 和 `production governor` 是 Skill 开发流程中的可选角色名，不是安装
Minimal Harness 的依赖。如果你的环境使用其他创作、评测或发布工具，用对应工具替换即可。

建议把 `.harness/` 放在 Skill 的**开发仓库根目录**，而不是为了通过检查而塞进可部署的运行时
Skill。Harness 的 command acceptance 可以调用现有 eval、单元测试和静态检查；语义质量仍由
grader 或人工评审负责。

## 与 Codex Goal 和 Plan Mode 怎么分工

三者不冲突，因为它们回答不同问题：

| 层级 | 回答的问题 | 合适内容 |
| --- | --- | --- |
| Codex Goal | 最终要做到什么 | 稳定的里程碑与可验证停止条件 |
| Plan Mode | 准备怎么做 | 调研、拆解、依赖、风险和验收设计 |
| Codex task | 本次具体交付什么 | 一个聚焦、可独立审查的成果 |
| Minimal Harness | 是否真的完成 | 当前源码上的检查、证据、新鲜度和完成状态 |

可以记成：**Goal 管方向，Plan Mode 管路径，Codex task 管交付，Harness 管证据。**

例如，一个 Skill 生产化 Goal 可以写成：

```text
把目标 Skill 提升到可发布状态。

停止条件：
1. 触发边界和权限规则明确；
2. 正向、反向和边界 eval 通过；
3. 版本记录和开发证据完整；
4. Minimal Harness 中本轮任务全部完成；
5. 最终质量审计通过。
```

不要在 Goal、计划文档和 Harness 中各维护一份详细状态。Goal 只保留稳定终点，计划允许变化，
Harness 是完成事实来源。如果 Goal 看起来已经完成，但 Harness 的任务仍是 `in_progress`、
`blocked` 或证据过期，以 Harness 报告为准。

## 大型项目的推荐组合

大型项目需要把编排与验收分开：

```text
Codex Project
├── Goal：版本或里程碑
├── Plan Mode：架构、拆解和依赖
├── Task A → Worktree A → 项目测试/CI → PR
├── Task B → Worktree B → 项目测试/CI → PR
├── Task C → Worktree C → 项目测试/CI → PR
└── Integration writer → 合并 → Harness 重验 → 发布
```

推荐规则：

- 一个项目保存共享代码、文档和长期指令；
- 一个里程碑使用一个稳定 Goal；
- 一个具体成果使用一个 Codex task；
- 可以独立修改的成果使用独立 worktree；
- 子智能体优先承担代码库探索、测试缺口、安全审查和日志总结；
- 同时写公共接口、数据库 schema 或共享配置的任务应串行或明确所有权；
- PR 和问题跟踪器记录协作进度，CI 检查每次提交；
- 最终集成工作区重新运行 Harness，并决定是否完成里程碑。

Codex 的长期项目规则应放在仓库的 `AGENTS.md` 或已提交文档中。Harness `init --agent codex`
会添加受管理的 Harness 工作流区块；项目自己的架构、测试和权限规则可以继续保留在区块之外。

## 为什么大型项目必须指定单一写入者

Minimal Harness 当前是**单执行者**工具，不是原生多智能体编排，也不是 worktree 状态合并器。
大型项目采用并行 Codex task 时，应指定一个 **单一集成写入者**：只有集成工作区负责推进共享
`.harness/tasks.json`、证据、attempt 和 handoff 状态。

功能 worktree 运行项目自己的局部测试并提交 PR，不把各自的 Harness 状态当作最终完成授权。
原因是多个 worktree 同时更新同一套 Harness 文件会产生状态和合并冲突；更重要的是，功能分支
上的证据不能证明最终组合后的源码正确。

因此完成顺序固定为：

```text
功能实现与局部测试
→ PR 审查和合并
→ 集成工作区更新到最终组合源码
→ Harness 合并后重验
→ report ready
→ complete
→ 完成里程碑 Goal
```

这里的“合并后重验”也可以记成英文检查词 `reverify after merge`。它是推荐的集成模式，不表示
Harness 会替你创建 worktree、合并分支或操作 Codex Goal。

## 可运行演练一：命令验收与证据失效

从 v0.2.0-beta.2 源码检出根目录开始，只在可丢弃目录中演练。示例定义见
[`examples/quickstart/greeting.task.json`](../examples/quickstart/greeting.task.json)，检查脚本见
[`examples/quickstart/tests/check_greeting.py`](../examples/quickstart/tests/check_greeting.py)。

```bash
mkdir ../harness-demo
cp -R examples/quickstart/src examples/quickstart/tests examples/quickstart/greeting.task.json ../harness-demo/
python3 template/.harness/harness.py --workspace ../harness-demo init --agent codex
cd ../harness-demo
git init
```

然后运行完整闭环：

```bash
python3 .harness/harness.py doctor
python3 .harness/harness.py task add --from greeting.task.json
python3 .harness/harness.py next
python3 .harness/harness.py verify
python3 .harness/harness.py report greeting
python3 .harness/harness.py complete greeting
python3 .harness/harness.py handoff
```

预期看到 command 检查通过、ready 报告、`Completed greeting` 和更新后的 handoff。仓库中的
[`tests/test_walkthrough.py`](../tests/test_walkthrough.py)会自动验证这个闭环。

要理解新鲜度门禁，可以在 `verify` 通过后、`complete` 前修改 `src/greet.py`。此时
`report greeting` 会返回 1，并提示源码快照过期。恢复代码并重新 `verify` 后才能完成。这个行为
不是时间戳检查，而是对当前内容、契约和 Git 验证对象的绑定。

## 可运行演练二：Todo 浏览器证据

Todo 示例包含真实网页、Node 测试和 Agent 指令：

- [`examples/todo/AGENTS.md`](../examples/todo/AGENTS.md)
- [`examples/todo/test.mjs`](../examples/todo/test.mjs)
- [`tests/run_todo_walkthrough.py`](../tests/run_todo_walkthrough.py)

安装 Playwright 和 Chromium 的开发环境可以从仓库根目录运行：

```bash
python3 tests/run_todo_walkthrough.py
```

演练会创建临时项目，运行 Todo 检查，启动本地服务器，执行真实 Chromium 验收，记录附件，
并确认所有 Harness 任务完成。它证明的是示例的工程闭环；browser/manual 记录仍属于操作者声明，
Harness 不会从截图像素中独立推断声明真假。

## 三种接入深度

| 接入方式 | 适用情况 | 使用内容 |
| --- | --- | --- |
| 轻量 | 一次性或低风险修改 | Plan Mode、项目测试、必要时一条 Harness command acceptance |
| 标准 | Skill、功能或跨会话任务 | Goal、独立 Codex task、Harness verify/report/complete/handoff |
| 大型项目 | 多成果、多 worktree、多人或多 Agent | 项目规则、任务/PR、CI、单一集成写入者和最终 Harness 重验 |

不要为了“流程完整”机械地添加层级。验收必须针对真实风险；无法自动判断的质量要求应明确交给
grader 或人工观察，而不是写一个永远通过的 command。

## 三个必须避免的反例

1. **多个 worktree 同时写 `.harness/`**：这违反单执行者边界，状态冲突也难以解释。
2. **功能分支分别通过后直接发布**：组合源码从未被验证，必须合并后重验。
3. **Goal 显示完成就跳过 Harness**：Goal 是推进目标，不是独立证据或完成授权。

还要避免把 `run check` 当作任务验收。它是项目辅助命令；只有任务 acceptance 产生的当前证据
才能进入完成门。

## 完成检查表

- Goal 有明确、可验证的停止条件；
- Plan Mode 已拆清依赖、验收和危险操作；
- 每个 Codex task 只有一个聚焦成果；
- 并行 worktree 没有争抢共享写入范围；
- 只有单一集成写入者修改最终 Harness 状态；
- 最终合并源码已经重新运行 acceptance；
- `report` 显示 ready，随后 `complete` 成功；
- `handoff` 已生成供下一次会话读取的当前摘要。

## 进一步阅读

- [第一次使用](../START-HERE.zh-CN.md)
- [实战使用指南](usage-guide.zh-CN.md)
- [完整 CLI 参考](cli-reference.zh-CN.md)
- [Codex Goal：Follow a goal](https://learn.chatgpt.com/use-cases/follow-goals)
- [Codex 最佳实践与 Plan Mode](https://learn.chatgpt.com/guides/best-practices)
- [Codex 项目和聊天](https://learn.chatgpt.com/zh-Hans/docs/projects)
- [Codex AGENTS.md](https://learn.chatgpt.com/zh-Hans/docs/agent-configuration/agents-md)
- [Codex 子智能体](https://learn.chatgpt.com/zh-Hans/docs/agent-configuration/subagents)
- [Codex Git worktree](https://learn.chatgpt.com/zh-Hans/docs/environments/git-worktrees)
