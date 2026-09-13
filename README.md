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

## Runnable Todo example

```bash
python3 template/.harness/harness.py --workspace examples/todo doctor
python3 template/.harness/harness.py --workspace examples/todo run check
python3 template/.harness/harness.py --workspace examples/todo run start
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
python3 template/.harness/harness.py --workspace template doctor
python3 template/.harness/harness.py --workspace examples/todo doctor
python3 template/.harness/harness.py --workspace examples/todo run check
```

Real browser regression uses Playwright and Chromium for development acceptance
only; they are not Harness runtime dependencies.

```bash
python3 template/.harness/harness.py --workspace examples/todo run start
python3 tests/todo_browser_acceptance.py
```

Set `HARNESS_CDP_URL=http://127.0.0.1:9344` to reuse a dedicated
CDP-accessible browser.

## Security, contributing, and license

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability and
[CONTRIBUTING.md](CONTRIBUTING.md) before proposing behavior or schema changes.

Minimal Harness is released under the [MIT License](LICENSE).
