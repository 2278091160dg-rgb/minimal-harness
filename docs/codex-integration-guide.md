# Codex × Minimal Harness: From Skill Development to Large Projects

[简体中文](codex-integration-guide.zh-CN.md) · [Project home](../README.md) ·
[Usage guide](usage-guide.md)

This guide follows the questions users typically ask when they first encounter Minimal
Harness: what it is, when it helps with Skill development, how it relates to Codex Goal
and Plan Mode, and how a large project can preserve a trustworthy completion and handoff
chain after parallel development.

**Compatibility: Minimal Harness v0.2.0-beta.2 · schema v3 · Codex docs checked 2026-09-14**

Goal, Plan Mode, projects, subagents, and worktrees are Codex capabilities. Minimal
Harness does not call models or start and orchestrate those capabilities. Codex may
continue to change, so follow the official OpenAI documentation linked at the end.

## Understand it in one sentence

Minimal Harness is a small acceptance kernel kept inside a Git repository. Think of it
as a coding agent's acceptance reviewer, evidence log, and cross-session handoff sheet.
It can:

1. retain tasks and their acceptance definitions;
2. run command checks and record browser or manual observations;
3. bind evidence to the current contract, source, and Git verification subject;
4. complete work only while that evidence remains current; and
5. generate `.harness/HANDOFF.md` for the next session.

It is not an AI agent, project manager, CI replacement, operating-system sandbox, or
concurrency protocol. Its deliberately narrow job is to answer: “Does this work have
enough current evidence to be registered as complete?”

## Is it valuable for Skill development?

That depends on how verifiable the Skill is, not on the length of `SKILL.md`.

| Skill type | Recommendation | Why |
| --- | --- | --- |
| Short instructions with no scripts or artifacts | Use lightly or wait | Maintaining Harness tasks may cost more than it saves; start with a few evals |
| Scripts, file transforms, or tool calls | Recommended | Command acceptance, logs, and freshness prevent old results from representing current work |
| Browser, image, video, or human judgment | Recommended with artifacts | Harness records attestations and artifact metadata but does not judge semantic quality |
| Audit, release, or self-evolution evidence | Use as the outer completion gate | It connects the validation steps but does not replace domain standards, graders, or review |

A practical responsibility chain is:

```text
skill-creator → evals → production governor → Minimal Harness
    author        behavior proof       quality audit          completion and evidence gate
```

`skill-creator` and `production governor` are optional role names in a Skill-development
workflow, not Minimal Harness dependencies. Substitute the authoring, evaluation, and
release tools used by your environment.

Keep `.harness/` at the **development repository root** instead of adding it to a
deployable runtime Skill merely to satisfy a checker. Command acceptance can run existing
evals, unit tests, and static checks. A grader or human reviewer still owns semantic
quality.

## Divide responsibility with Codex Goal and Plan Mode

The layers do not conflict because they answer different questions:

| Layer | Question | Appropriate content |
| --- | --- | --- |
| Codex Goal | What must ultimately be true? | A stable milestone and verifiable stopping conditions |
| Plan Mode | How should we approach it? | Research, decomposition, dependencies, risks, and acceptance design |
| Codex task | What will this run deliver? | One focused, independently reviewable outcome |
| Minimal Harness | Is it actually complete? | Checks, evidence, freshness, and completion state for the current source |

The short version is: **Goal owns direction, Plan Mode owns the route, a Codex task owns
one deliverable, and Harness owns evidence.**

For example, a Skill production-readiness Goal can say:

```text
Bring the target Skill to a releasable state.

Stopping conditions:
1. Trigger boundaries and permission rules are explicit.
2. Positive, negative, and boundary evals pass.
3. Version history and development evidence are complete.
4. All Minimal Harness tasks for this iteration are complete.
5. The final quality audit passes.
```

Do not maintain a detailed status list in the Goal, plan document, and Harness at the
same time. Keep the stable destination in Goal, let the plan evolve, and use Harness as
the completion source of truth. If Goal looks complete while the Harness task remains
`in_progress`, `blocked`, or stale, follow the Harness report.

## Recommended combination for a large project

Large projects should separate orchestration from acceptance:

```text
Codex Project
├── Goal: release or milestone
├── Plan Mode: architecture, decomposition, and dependencies
├── Task A → Worktree A → project tests/CI → PR
├── Task B → Worktree B → project tests/CI → PR
├── Task C → Worktree C → project tests/CI → PR
└── Integration writer → merge → Harness reverify → release
```

Recommended rules:

- use one project for shared code, documentation, and durable instructions;
- use one stable Goal for a milestone;
- open one Codex task for each concrete outcome;
- isolate independently writable outcomes in worktrees;
- use subagents first for codebase exploration, test gaps, security review, and log summaries;
- serialize or assign explicit ownership for shared APIs, database schemas, and common configuration;
- track collaboration in PRs and issues, and check each revision in CI; and
- run the final Harness gate again in the integration workspace.

Keep durable Codex project rules in the repository's `AGENTS.md` or committed docs.
`init --agent codex` appends a managed Harness workflow block. Your architecture, test,
and permission rules remain outside that managed block.

## Why a large project needs a single writer

Minimal Harness is currently a **single executor** tool. It is **not native multi-agent orchestration**
and it does not merge worktree state. When Codex tasks run in parallel,
designate a **single integration writer**. Only the integration workspace advances the
shared `.harness/tasks.json`, evidence, attempt, and handoff state.

Feature worktrees run their own project tests and submit PRs. Their individual Harness
state must not authorize final completion. Concurrent writes to the same Harness files
create ambiguous state and merge conflicts; more importantly, evidence from one feature
branch does not prove the final combined source.

Use this completion order:

```text
feature implementation and local tests
→ PR review and merge
→ update the integration workspace to the combined source
→ reverify after merge with Harness
→ report ready
→ complete
→ complete the milestone Goal
```

This is a recommended integration pattern. It does not mean Harness creates worktrees,
merges branches, or operates Codex Goal for you.

## Runnable walkthrough 1: command acceptance and stale evidence

Start at the root of a v0.2.0-beta.2 source checkout and use only a disposable directory.
The definition is in
[`examples/quickstart/greeting.task.json`](../examples/quickstart/greeting.task.json), and
the check is in
[`examples/quickstart/tests/check_greeting.py`](../examples/quickstart/tests/check_greeting.py).

```bash
mkdir ../harness-demo
cp -R examples/quickstart/src examples/quickstart/tests examples/quickstart/greeting.task.json ../harness-demo/
python3 template/.harness/harness.py --workspace ../harness-demo init --agent codex
cd ../harness-demo
git init
```

Run the complete loop:

```bash
python3 .harness/harness.py doctor
python3 .harness/harness.py task add --from greeting.task.json
python3 .harness/harness.py next
python3 .harness/harness.py verify
python3 .harness/harness.py report greeting
python3 .harness/harness.py complete greeting
python3 .harness/harness.py handoff
```

Expect the command acceptance to pass, a ready report, `Completed greeting`, and an
updated handoff. [`tests/test_walkthrough.py`](../tests/test_walkthrough.py) exercises
this loop automatically.

To see the freshness gate, edit `src/greet.py` after `verify` passes but before
`complete`. `report greeting` then exits 1 and reports a stale source snapshot. Restore
the source and run `verify` again before completing. This binds evidence to current
content, contract, and Git subject rather than to a timestamp.

## Runnable walkthrough 2: Todo browser evidence

The Todo example includes a real page, Node tests, and agent instructions:

- [`examples/todo/AGENTS.md`](../examples/todo/AGENTS.md)
- [`examples/todo/test.mjs`](../examples/todo/test.mjs)
- [`tests/run_todo_walkthrough.py`](../tests/run_todo_walkthrough.py)

In a development environment with Playwright and Chromium installed, run from the
repository root:

```bash
python3 tests/run_todo_walkthrough.py
```

The walkthrough creates a temporary project, runs the Todo checks, starts a local server,
performs real Chromium acceptance, records artifacts, and confirms every Harness task is
complete. It proves the example's engineering loop. Browser and manual records remain
operator attestations; Harness does not independently infer their truth from image pixels.

## Three adoption depths

| Depth | Use when | Include |
| --- | --- | --- |
| Light | One-off or low-risk change | Plan Mode, project tests, and optionally one Harness command acceptance |
| Standard | Skill, feature, or cross-session task | Goal, focused Codex task, and Harness verify/report/complete/handoff |
| Large project | Multiple deliverables, worktrees, people, or agents | Project rules, tasks/PRs, CI, a single integration writer, and final Harness reverification |

Do not add layers only to make a workflow look complete. Acceptance should target real
risks. Requirements that cannot be evaluated automatically belong to a grader or an
honest human observation, not to an always-passing command.

## Three anti-patterns to avoid

1. **Multiple worktrees write `.harness/` concurrently.** This violates the single-executor boundary and creates ambiguous state.
2. **Feature branches pass independently and ship without an integration run.** The combined source was never verified; reverify after merge.
3. **Goal appears complete, so Harness is skipped.** Goal drives progress; it is not independent evidence or completion authorization.

Also avoid treating `run check` as task acceptance. It is a project helper command. Only
current evidence produced for task acceptance can enter the completion gate.

## Completion checklist

- Goal has explicit, verifiable stopping conditions.
- Plan Mode has resolved dependencies, acceptance, and risky operations.
- Each Codex task owns one focused outcome.
- Parallel worktrees do not compete for shared writable scope.
- Only the single integration writer changes final Harness state.
- Acceptance has run again against the final combined source.
- `report` says ready and `complete` succeeds.
- `handoff` contains the current summary for the next session.

## Further reading

- [Start here](../START-HERE.md)
- [Usage guide](usage-guide.md)
- [CLI reference](cli-reference.md)
- [Codex Goal: Follow a goal](https://learn.chatgpt.com/use-cases/follow-goals)
- [Codex best practices and Plan Mode](https://learn.chatgpt.com/guides/best-practices)
- [Codex projects and chats](https://learn.chatgpt.com/zh-Hans/docs/projects)
- [Codex AGENTS.md](https://learn.chatgpt.com/zh-Hans/docs/agent-configuration/agents-md)
- [Codex subagents](https://learn.chatgpt.com/zh-Hans/docs/agent-configuration/subagents)
- [Codex Git worktrees](https://learn.chatgpt.com/zh-Hans/docs/environments/git-worktrees)
