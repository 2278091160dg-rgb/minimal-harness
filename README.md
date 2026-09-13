# Minimal Harness

[English](README.md) | [简体中文](README.zh-CN.md)

[![CI](https://github.com/2278091160dg-rgb/minimal-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/2278091160dg-rgb/minimal-harness/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/2278091160dg-rgb/minimal-harness)](https://github.com/2278091160dg-rgb/minimal-harness/releases/latest)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Minimal, dependency-free, fail-closed completion proof layer for coding agents.**

Minimal Harness is a repository-local acceptance kernel for Codex, Claude Code,
GitHub Copilot, and other coding agents. It connects task state, real
verification, tamper-evident evidence, Git scope, completion gates, and
cross-session handoff in one inspectable workflow.

It does not call an AI model and does not assume that “the code was written”
means “the task is complete.”

## 30-second install

### macOS and Linux

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

The archive expands directly to `.harness/`. Edit `.harness/config.json`
and `.harness/tasks.json` for your project, then begin the workflow below.
The release also includes `SHA256SUMS.txt` for download verification.

The release ZIP is the portable runtime package. It does **not** include the
source-checkout initializer described next.

## Initialize another project from a source checkout

From a clone of this repository, initialize an existing project directory:

```bash
python3 scripts/init_harness.py --workspace "/absolute/path/to/project"
```

`--workspace` is required and must name an existing directory. The default
installs instruction blocks for both supported agents. Select one explicitly
when needed:

```bash
python3 scripts/init_harness.py --workspace "/absolute/path/to/project" --agent codex
python3 scripts/init_harness.py --workspace "/absolute/path/to/project" --agent claude
python3 scripts/init_harness.py --workspace "/absolute/path/to/project" --agent both
```

A fresh installation copies the canonical `.harness/` template and adds a
managed block to the selected root instruction files: `AGENTS.md` for Codex and
`CLAUDE.md` for Claude Code. The initializer does not run project commands,
select a task, or generate project-specific configuration. Before running
`next`, edit the installed `.harness/config.json` and `.harness/tasks.json` with
the real project commands, allowed paths, tasks, and acceptance checks.

Preview the exact file actions without writing anything:

```bash
python3 scripts/init_harness.py --workspace "/absolute/path/to/project" --agent both --dry-run
```

Re-running the same command is safe. For an existing complete schema-v2
installation, runtime files and task state are preserved byte for byte; only
the selected managed instruction blocks can be added or updated. An identical
run reports a no-op and succeeds. If a task is `in_progress` or `blocked`, an
invocation that would change files refuses to write; a blocked dry-run also
returns exit code `1`. Complete the active task before changing the managed
blocks.

The initializer fails closed on incomplete installations, v1 or malformed
config/task state, malformed managed markers, symlinked destinations or path
ancestors, and unexpected destination file types. It performs no automatic
migration or repair. Use the explicit [v1 migration](#migrating-from-v1)
workflow for an existing runtime instead.

Codex reads the generated `AGENTS.md` block; see the official
[Codex AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
Claude Code reads the generated `CLAUDE.md` block; see the official
[Claude Code memory documentation](https://code.claude.com/docs/en/memory).
Open either agent in the initialized project root so it operates on the same
working tree and `.harness/` state.

### Start Claude Code with your normal launcher

After initializing and configuring the project, start the standard Claude Code
CLI in its root, then paste the start/resume or takeover prompt below:

```bash
cd "/absolute/path/to/project"
claude
```

This is the standard entry point for subscription users too; follow the
[official Claude Code quickstart](https://code.claude.com/docs/en/quickstart)
for installation and login. Harness does not select a provider, manage login
credentials, or launch the model itself.

If your machine uses a custom shell function such as `claude-sub` to select a
separate local profile, use that function instead of `claude` when starting the
session. It is a local convention, not a Harness command or an installation
requirement. Keep `--agent claude`, `CLAUDE.md`, and every Harness command the
same. Do not copy local aliases, account settings or credentials into the shared
repository. Verification reports should identify the actual launcher used and
separate its connection failures from Harness acceptance failures.

## What it can prove

| Capability | What it establishes |
| --- | --- |
| Agent-neutral, repository-local operation | The same checked-in workflow can be called by different coding agents. |
| Deterministic task lifecycle | Tasks move through `pending`, `in_progress`, `blocked`, and `done` under explicit rules. |
| Strict v1 → v2 migration | Active legacy tasks receive a new baseline instead of silently inheriting incomplete state. |
| Git-bound scope audit | Branch, HEAD, index, worktree, tracked/ignored files, and allowed paths are checked fail closed. |
| Bound evidence | Evidence JSON, logs, and artifacts carry size and SHA-256 metadata plus a Git verification subject. |
| Three acceptance modes | Commands are executed directly; browser results require a tool and artifact; manual results remain labeled attestations. |
| Fail-closed completion | Missing, stale, tampered, or uncertain Git/evidence state blocks `complete`. |
| Verifiable handoff | `HANDOFF.md` reports current task state, trusted evidence, warnings, and the next command. |
| Portable runtime | The core uses only the Python 3.9+ standard library on Linux, macOS, and Windows. |
| Optional GitHub reporting | A separate adapter can publish trusted results as a GitHub Check Run. |

## Minimal workflow

```bash
# 1. Inspect the repository and select one task.
python3 .harness/harness.py doctor
python3 .harness/harness.py status
python3 .harness/harness.py next

# 2. Do the work, then run command acceptance checks.
python3 .harness/harness.py verify

# 3. Record browser or manual acceptance when required.
python3 .harness/harness.py record TASK_ID CHECK_ID \
  --result passed \
  --summary "What was executed and observed" \
  --tool browser \
  --artifact proof/screenshot.png

# 4. Complete only after every gate passes.
python3 .harness/harness.py complete TASK_ID

# 5. Generate the next-session handoff.
python3 .harness/harness.py handoff
```

A typical first minute looks like this:

```text
$ python3 .harness/harness.py doctor
OK: configuration valid (1 tasks)
OK: Git branch=main HEAD=<commit>

$ python3 .harness/harness.py next
Selected T1: <task title>

$ python3 .harness/harness.py status
Project: <project name>
Current task: T1
- T1 [in_progress]: <task title>
```

## Why not just CI?

CI answers whether commands passed for a revision. Minimal Harness additionally
binds those results to a task lifecycle, the task's starting Git state, allowed
paths, artifacts, evidence freshness, and the final completion decision. It
also preserves a trustworthy handoff between agent sessions.

Minimal Harness is an independent CLI acceptance kernel. It is **not**:

- a Codex Skill or agent orchestrator;
- an operating-system sandbox or permission system;
- a service that automatically commits or pushes changes;
- cryptographic proof that a human manual statement is truthful.

Use a container, virtual machine, restricted account, or platform permissions
when executing untrusted code.

## Configuration and task model

`.harness/config.json` and `.harness/tasks.json` use schema v2.

- `commands.setup/start/check` must be argv arrays or `null`; no shell is
  inserted.
- `{python}` safely expands to the interpreter running Harness.
- `policy.allowed_paths` uses path-segment glob semantics: `*` matches one
  segment and `**` may cross directories.
- `policy.require_git_for_completion` defaults to `true`.
- `approval_required_operations` documents agent/human process boundaries;
  it does not intercept operating-system calls.

Acceptance types:

- `command`: executed directly by Harness.
- `browser`: executed with a real browser; a passed result requires
  `--tool` and at least one regular, non-symlink artifact.
- `manual`: a clearly labeled human or external-tool attestation; an
  attachment is optional.

Harness exit codes are `0` for success, `1` for an acceptance or workflow
gate, `2` for configuration/usage errors, and `130` for user interruption.

## Migrating from v1

Preview before changing state:

```bash
python3 .harness/harness.py migrate --dry-run
python3 .harness/harness.py migrate
```

An active or blocked v1 task needs an explicit checkpoint note because the old
index baseline cannot be proven:

```bash
python3 .harness/harness.py migrate \
  --note "Confirmed restart from the current Git state"
```

Migration snapshots the original v1 files and their hashes under
`.harness/migrations/`. It does not rewrite historical evidence. Passed v1
checks on unfinished tasks become `unverified`; completed tasks remain
readable and are labeled as legacy evidence. Re-running migration is safe.

## Git baseline and scope

`next` selects only the first pending task and freezes:

- branch, HEAD, unborn state, worktree and index fingerprints;
- tracked and ignored file fingerprints, including Git flags;
- the allowed-path, failure-threshold, approval, and Git-completion policies.

An active or blocked task prevents selecting another task. Existing dirty
regular files are fingerprinted so later edits cannot hide behind old dirt.
Unfingerprintable dirty objects, including unsafe submodule states, prevent an
incomplete baseline from being created.

Every Git subprocess is checked. Once a repository is recognized, uncertainty
reading status, branch, HEAD, index, tracked/ignored files, or submodules
blocks completion.

## Evidence and freshness

```bash
# Run all command checks for the active task.
python3 .harness/harness.py verify

# Record an unavailable capability without pretending it passed.
python3 .harness/harness.py record TASK_ID CHECK_ID \
  --result unverified \
  --summary "This agent session has no browser tool"
```

Each result creates a non-overwriting schema v3 evidence JSON file. Command
output is stored as raw bytes; terminal display uses UTF-8 replacement
decoding. Evidence JSON, logs, and artifacts record path, type, size, and
SHA-256.

Passed evidence also stores the Git verification subject at the moment of
verification. A later relevant file, index, branch, HEAD, ignored-file,
submodule, or Git-history change makes that evidence stale and requires
`verify` or `record` again.

Freshness ignores only Harness-generated mutable state:
`tasks.json`, `evidence/**`, `logs/**`, `HANDOFF.md`, and
`migrations/**`. The runtime, config, adapters, and project files are still
covered.

After the configured failure threshold blocks a task, a person can reset the
current gate while retaining historical evidence:

```bash
python3 .harness/harness.py unblock TASK_ID --note "What was resolved"
```

## Cross-session handoff

```bash
python3 .harness/harness.py handoff
```

`.harness/HANDOFF.md` records the schema, snapshot time, active acceptance
state, validated evidence, historical failures, Git state, scope warnings, and
the next command. Invalid evidence is shown as an error, never as a trusted
summary. The generated handoff file excludes itself from its worktree section.

Adapter snippets for agent instruction files live in
`template/.harness/adapters/`.

Codex and Claude Code may share one workspace and Git branch, but only one
agent should write at a time. Stop the sender before the receiver starts. The
receiver must resume `current_task_id`; it must not run `next` while a task is
`in_progress` or `blocked`. This is a serial handoff protocol, not concurrent
agent orchestration or cross-worktree synchronization.

`run check` and `verify` serve different purposes:

- `python3 .harness/harness.py run check` runs the configured project check for
  quick feedback but does not create acceptance evidence.
- `python3 .harness/harness.py verify` executes the current task's `command`
  acceptance checks and writes evidence used by the completion gate.
- `browser` and `manual` acceptance must be performed in the named tool or by a
  person, actually observed, and then recorded. A command result cannot stand
  in for that observation.

These four prompts are ready to copy into either agent.

### 1. Initial setup

```text
Initialize Minimal Harness in this existing project for both Codex and Claude Code. Use the source-checkout initializer with --agent both --dry-run first, review its plan, then run it for real. Edit the installed .harness/config.json and .harness/tasks.json for this project before running next. Run doctor and status, but do not claim a task until the configuration and acceptance checks are concrete.
```

### 2. Start or resume work

```text
Work in this project using Minimal Harness. Run doctor and status, then read .harness/HANDOFF.md if it exists. If current_task_id is in_progress, resume that exact task and do not run next. If it is blocked, report the blocker and do not change project files; resume mutating work only after the cause is addressed and python3 .harness/harness.py unblock TASK_ID --note "What was resolved" succeeds. If there is no active or blocked task, run next once. Stay within the frozen allowed paths, use run check for quick feedback, and use verify for command acceptance evidence.
```

### 3. Hand off

```text
Prepare a serial handoff to the other agent in this same workspace and Git branch. Stop making project changes, leave the current task active if any acceptance remains unverified, and run python3 .harness/harness.py handoff. Report the current task ID, completed work, remaining acceptance, evidence or artifacts already recorded, and the exact next action. Do not run next or mark an unobserved check passed.
```

### 4. Take over

```text
Take over this Minimal Harness task in the same workspace and Git branch. Run doctor and status, then read .harness/HANDOFF.md. If current_task_id is blocked, report the blocker and do not change project files; resume mutating work only after intervention and a successful python3 .harness/harness.py unblock TASK_ID --note "What was resolved". Otherwise resume current_task_id without running next. Inspect existing evidence, complete the remaining implementation and real acceptance actions, create all browser/manual proof artifacts before recording their evidence, rerun stale command evidence with verify, and complete only if every gate passes. Generate a fresh handoff when stopping.
```

## Runnable Todo example

```bash
python3 template/.harness/harness.py --workspace "examples/todo" doctor
python3 template/.harness/harness.py --workspace "examples/todo" run check
python3 template/.harness/harness.py --workspace "examples/todo" run start
```

Open `http://127.0.0.1:8000`, then test adding, completing, and refreshing a
todo. You can also run Harness from inside the example:

```bash
cd examples/todo
python3 .harness/harness.py doctor
python3 .harness/harness.py status
```

## Optional GitHub Check Run

`integrations/github/` contains a standard-library adapter and example
workflow. It runs doctor/check in ordinary CI and publishes a Check Run only
for trusted `push` events with `checks: write`:

```bash
mkdir -p .github/workflows
cp integrations/github/minimal-harness-check.yml .github/workflows/
```

The adapter requires `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, and a full
`GITHUB_SHA`. It rejects cross-host redirects rather than forwarding
Authorization. See the official [Check Runs REST API](https://docs.github.com/en/rest/checks/runs)
and [GitHub Actions fork permission boundary](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#changing-the-permissions-in-a-forked-repository).

## Development

```bash
python3 -m unittest discover -s tests -v
node --test examples/todo/test.mjs
python3 -m pip install ruff==0.15.12
ruff check --no-cache template/.harness/harness.py integrations/github/publish_check.py scripts tests
python3 template/.harness/harness.py --workspace "template" doctor
python3 template/.harness/harness.py --workspace "examples/todo" doctor
python3 template/.harness/harness.py --workspace "examples/todo" run check
```

Real browser regression uses Playwright and Chromium for development acceptance
only; they are not Harness runtime dependencies.

```bash
python3 template/.harness/harness.py --workspace "examples/todo" run start

# Default: save the final screenshot in the system temporary directory.
python3 tests/todo_browser_acceptance.py

# Or keep all three proof files inside the task workspace.
python3 tests/todo_browser_acceptance.py --artifact-dir "examples/todo/proof"
```

Without `--artifact-dir`, the final screenshot remains
`minimal-harness-todo-acceptance.png` in the system temporary directory. With
`--artifact-dir`, browser acceptance saves `add.png`, `toggle.png`, and
`persist.png`. An artifact passed to Harness `record` must be inside the task
workspace. Create every proof file first, then record those artifacts; creating
or changing project-relevant proof after recording can make the evidence stale.

Set `HARNESS_CDP_URL=http://127.0.0.1:9344` to reuse a dedicated
CDP-accessible browser.

## Security, contributing, and license

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability and
[CONTRIBUTING.md](CONTRIBUTING.md) before proposing behavior or schema changes.

Minimal Harness is released under the [MIT License](LICENSE).
