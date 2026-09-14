# CLI reference

[简体中文](cli-reference.zh-CN.md) · [README](../README.md) ·
[Practical guide](usage-guide.md) · [Documentation index](README.md)

This is the complete parser surface for schema v3. The CLI emits English text in both
language workflows; it has no locale or translation option.

## Invocation and path rules

```text
python3 PATH/TO/.harness/harness.py [--workspace PATH] COMMAND [COMMAND OPTIONS]
```

- `--workspace PATH` is the only global option and must appear before `COMMAND`.
- If omitted, the workspace is the script file's parent directory's parent. For an
  installed `PROJECT/.harness/harness.py`, that is `PROJECT`, regardless of the shell's
  current directory.
- The workspace must resolve to the project that contains `.harness/config.json` and
  `.harness/tasks.json`, except while `init` is creating them.
- Relative paths passed to `task add/revise --from` follow the shell's current directory.
  Relative `record --artifact` paths follow the workspace. Configured argv runs with the
  workspace as its current directory.
- `{python}` in configured argv expands to the interpreter running Harness. Commands are
  argv arrays and run without a shell.
- `-h` and `--help` are available on the top-level parser and each subparser. There is no
  `--version` option.

PowerShell uses the same ordering, normally with `py -3` instead of `python3`.

## Common state and exit codes

Task states are `pending`, `in_progress`, `blocked`, and `done`. Check states are
`not_run`, `passed`, `failed`, and `unverified`. Only `passed` can satisfy completion.
One task may be current; it is either `in_progress` or `blocked`.

| Exit | Meaning |
| --- | --- |
| `0` | Operation succeeded, report is ready, or a valid query has no pending work. |
| `1` | A command/check failed, a valid workflow gate was unmet or stale, a non-pass was recorded, or `doctor` found stale passed evidence. |
| `2` | Invalid CLI usage, configuration/schema/path error, execution setup error, or damaged/inconsistent evidence. `argparse` usage errors also return 2. |
| `130` | User interruption. An interrupted verification does not retain a pass. |

Harness writes ordinary results to stdout and errors to stderr. A child process's
nonzero code is normalized to Harness exit 1; it is preserved inside command evidence.

## Read/write map

| Command | Harness-owned writes | Other possible effects |
| --- | --- | --- |
| `init --dry-run`, `doctor`, `status`, `report`, `migrate --dry-run` | None | Read files and Git state. |
| `init` | Fresh `.harness/` runtime/config/tasks/handoff/license; optional managed instructions | Never initializes Git or installs dependencies. |
| `task add`, `task revise`, `next`, `record`, `complete`, `unblock` | `.harness/tasks.json`, evidence where applicable, and handoff | None beyond explicit Harness state/artifact reads. |
| `verify` | Task state, attempts, logs, evidence, handoff | Acceptance commands can modify any location their OS permissions allow; drift is audited, not prevented. |
| `run setup`, `run check` | Bounded logs under `.harness/attempts/runs/` | Configured child can modify the workspace or external systems. |
| `run start` | No Harness log | Attached child can modify state and stays running until it exits or is interrupted. |
| `handoff` | `.harness/HANDOFF.md` | None. |
| `migrate` | Migration archive, config, tasks, handoff | No application-source changes. |

"Read-only" describes Harness-owned files. Reading Git may invoke Git with optional locks
disabled. A configured child command keeps its own capabilities.

## Definition and configuration prerequisites

All commands except `init` require an installed workspace. Normal workflow commands
require matching schema v3 config and tasks. `migrate` additionally accepts matching v1
or v2 config/tasks.

`task add/revise --from` reads an explicit UTF-8 JSON object with exactly `id`, `title`,
and non-empty `acceptance`. It must not contain generated status, counters, evidence,
baselines, or unknown fields. Each check contains:

- common: `id`, `type`, and non-empty `instruction`;
- command: non-empty string-array `command`, optional positive finite
  `timeout_seconds` (default 300);
- browser/manual: non-empty string-array `steps`.

IDs contain 1–128 ASCII letters, digits, `.`, `_`, or `-`, beginning with a letter or
digit. Config requires `commands.setup/start/check` keys whose values are `null` or
non-empty string arrays, plus a schema v3 policy with a positive failure limit, safe
relative `allowed_paths`, an operation-instruction array, and a boolean Git requirement.

## `init`

```text
python3 template/.harness/harness.py [--workspace PATH] init
    [--agent {codex,claude,generic}] [--dry-run]
```

`--workspace` is practically required when invoking a template or staged ZIP, because
its default would be the template/staging parent. The target directory must already
exist. `--agent codex` or `generic` targets `AGENTS.md`; `claude` targets `CLAUDE.md`.
Omitting it installs no host instructions. `--dry-run` preflights and lists changes.

Current unreleased source preflights `harness.py`, `harness_init.py`,
`harness_runner.py`, and `LICENSE` from one source directory before any write. A fresh
install creates those four files under `.harness/` plus config, empty tasks, and handoff.
It never changes the project root license. Published beta.1 behaves the same except that
its historical ZIP/runtime has only the three Python modules and no runtime license.

Repeat init validates the complete installed runtime and state, and can append one
missing managed instruction block. It does not upgrade. Current source treats an old v3
install without `.harness/LICENSE`, a different runtime byte, a partial install, a
symlink target, or a conflicting/partial managed block as an explicit-upgrade error.

Success prints a dry-run list, `Initialized: PATH`, or `Already initialized: PATH`, then
next-step guidance. Exit 2 means no successful initialization; preflight is designed to
fail before writes and rolls back files created by the failed operation. Stage source
outside the project, fix the reported conflict, or follow the explicit upgrade procedure.

## `task`

`task` is a required command group with no options of its own. It must be followed by
exactly one nested command, `add` or `revise`; invoking `task` alone is a usage error and
returns 2.

## `task add`

```text
python3 .harness/harness.py task add --from DEFINITION.json
```

`--from` is required and is never inferred from stdin or `.harness/tasks.json`. A relative
path follows the caller's current directory. Any valid workflow state may add a unique
pending task, including while another task is active. Harness creates runtime fields,
writes task state, refreshes handoff, and prints `Task add: ID`.

Duplicate IDs, malformed/unknown fields, unsafe IDs, invalid check definitions, or a
missing/unreadable file exit 2 without adding the task. Correct the definition and retry.

## `task revise`

```text
python3 .harness/harness.py task revise TASK_ID --from DEFINITION.json --note TEXT
```

All three arguments are required. The definition ID must equal `TASK_ID`; `--note` must
be non-empty. The task must be `pending` or `in_progress`. Revision stores the previous
definition and acceptance state, replaces title/checks, makes every replacement check
`unverified`, freezes the new contract, refreshes handoff, and prints `Task revise: ID`.

It retains the selected task's Git and policy baselines and therefore does not expand
allowed edit scope. A done task or the current blocked task exits 1; unblock the latter
first. Definition/ID/note errors exit 2. Reverify the active task after every revision.

## `doctor`

```text
python3 .harness/harness.py doctor
```

Read-only. Validates schema, configuration, task/evidence structure, required configured
and acceptance executables, Python 3.9+, evidence file metadata, and current Git/source
freshness for passed checks on active/blocked tasks. It prints configuration/task count,
Git identity or an unavailable warning, dirty-path count, and relevant warnings.

Exit 0 means structural checks passed and no active passed evidence is stale. Exit 1
means otherwise-valid evidence is stale; run the report and required verification again.
Exit 2 means configuration, executable, evidence, filesystem, or Git inspection is not
trustworthy; correct the named fault before continuing. No Git repository is normally a
warning here, though completion still rejects it when the frozen policy requires Git.

## `status`

```text
python3 .harness/harness.py status
```

Read-only. Requires valid schema v3 state and prints project name, current task, then
every task and check with status/type. It does not audit freshness or readiness. Exit 0
means the state could be loaded; structural errors exit 2. Use `report ID` for completion
questions.

## `next`

```text
python3 .harness/harness.py next
```

Selects the first pending task, changes it to `in_progress`, captures start time and Git
baseline, freezes the current policy and acceptance contract, makes it current, refreshes
handoff, and prints `Selected ID: TITLE`.

An existing current task or any blocked task exits 1; resume or unblock it. With no
pending task, prints `No pending tasks.` and exits 0 without changing state. Git need not
have a commit to select work, but a missing Git baseline prevents completion under the
default policy. Configure policy and task definitions before selection because their
baselines freeze here.

## `run`

```text
python3 .harness/harness.py run {setup,start,check}
```

The positional choice is required and maps directly to `commands.setup`, `.start`, or
`.check`. A `null` command exits 1 with `commands.NAME is not configured`. Missing or
unlaunchable executables/config errors exit 2.

`setup` and `check` run with the bounded runner, display captured output, and write a log
under `.harness/attempts/runs/`. The default limits are 300 seconds and 10 MiB. Successful
normal exit returns 0; nonzero, timeout, or output limit returns 1; interruption returns
130. `start` is unbounded and attached to the terminal; normal zero exit returns 0,
nonzero returns 1, and Ctrl-C returns 130.

None of these records a task acceptance check, even `run check`. Configure a command
acceptance and use `verify` when the result must authorize completion. Child effects are
not sandboxed; review argv before running and recover any child-created changes yourself.

## `verify`

```text
python3 .harness/harness.py verify [TASK_ID]
```

Omitting `TASK_ID` uses `current_task_id`; a supplied ID must equal it. The task must be
`in_progress`, have a current unchanged contract, and contain at least one command check.
Browser/manual checks are ignored by this command and must use `record`.

Before launching a child, Harness invalidates prior command passes for the batch. For
each command in definition order it captures the source/contract, writes a running
attempt, executes with its timeout and 10-MiB raw-output limit, displays the log, audits
source and task state again, and writes attempt/evidence/status/handoff. It stops at the
first non-pass. All commands run from the workspace without a shell.

Exit 0 means every command check passed against consistent current snapshots. A child
failure, timeout, output limit, or detected drift exits 1; interruption exits 130; an
invalid state, damaged evidence/path, unavailable executable, or execution setup error
exits 2. A check reaching the frozen consecutive-failure limit blocks the task. Fix the
behavior and rerun; use `unblock` first after it becomes blocked. Do not infer browser or
manual success from a command pass.

## `record`

```text
python3 .harness/harness.py record TASK_ID CHECK_ID
    --result {passed,failed,unverified}
    --summary TEXT
    [--tool TOOL]
    [--artifact FILE ...]
```

`TASK_ID`, `CHECK_ID`, `--result`, and `--summary` are required. The task must be the
current `in_progress` task, the check must be browser or manual, and the contract must be
current. `--summary` must remain non-empty after trimming. `--artifact` is repeatable;
each path must name an existing non-symlink regular file inside the workspace. Relative
artifact paths follow the workspace. Harness records metadata/digest; it does not copy
the file.

A passed browser check additionally requires non-empty `--tool` and at least one
artifact. Failed/unverified browser records and all manual records may omit both. Only
record `passed` after actually performing and observing the definition's steps. Harness
stores an operator attestation; it does not launch a browser or prove the statement.

The command writes evidence, task state, and handoff, then prints
`Recorded TASK/CHECK: RESULT`. `passed` exits 0 and resets that check's failure counter.
`failed` exits 1 and increments it, blocking at the threshold. `unverified` exits 1 and
does not count as passed. Invalid command checks, paths/artifacts, options, or empty fields
exit 2. Correct the observation/artifact or use an honest non-pass; never fabricate one.

## `report`

```text
python3 .harness/harness.py report TASK_ID [--format {text,json,markdown}]
```

`TASK_ID` is required. `--format` defaults to `text`. The command is read-only: it uses
the same completion auditor as `complete`, showing each check, provenance, evidence path,
summary, artifacts, issues, readiness, and next command. JSON additionally exposes
`schema_version`, task status, `historical`, per-check details, `integrity_errors`, the
Git-binding policy flag, and the resulting exit code. Output goes to stdout; nothing is
uploaded and no report file is created.

Ready exits 0. Ordinary unmet gates or stale evidence exit 1. Evidence integrity damage
exits 2. A done task is reported as historical, exits 1, and has no completion authority.
Follow `next_command`; source/contract drift requires new verification, while scope or Git
identity problems usually require inspecting `git status --short` or `doctor`.

## `complete`

```text
python3 .harness/harness.py complete TASK_ID
```

The named task must be current and `in_progress`, every check must be passed with intact
and current evidence, the acceptance contract/source snapshot must match, and Git changes
since selection must stay within frozen `allowed_paths`. Git is required when the frozen
policy says so. When Git is available, its current identity remains part of source
freshness even if the policy permits completion without Git.

Success marks the task `done`, records completion time, clears current task, refreshes
handoff, prints `Completed ID: TITLE`, and exits 0. It never commits or uploads. An unmet
or stale gate exits 1; evidence/config/integrity faults exit 2. Run `report ID` for the
same detailed audit, repair the stated issue, and reverify if source, index, HEAD, branch,
or contract changed.

## `unblock`

```text
python3 .harness/harness.py unblock TASK_ID --note TEXT
```

Both arguments are required. The task must be the current blocked task and the note must
remain non-empty after trimming. Success appends unblock history, resets all check failure
counters, converts failed checks to unverified and clears their evidence references,
returns the task to `in_progress`, refreshes handoff, prints `Unblocked ID`, and exits 0.

Wrong task/state exits 1; empty/missing note or invalid state exits 2. Unblock does not
fix behavior or pass acceptance. Address the cause first, then run `verify` or `record`.

## `handoff`

```text
python3 .harness/harness.py handoff
```

Regenerates `.harness/HANDOFF.md` from current config, task, Git, evidence, failure,
freshness, and next-action state. It prints the updated path and exits 0. It does not
start a new agent session or upload anything. Invalid state/evidence/Git inspection exits
2; fix the named issue and retry. At the next session, run `doctor`, `status`, and read the
handoff before changing files.

## `migrate`

```text
python3 .harness/harness.py migrate [--dry-run] [--note TEXT]
```

Accepts matching config/tasks schema v1, v2, or v3. `--dry-run` validates and describes a
v1/v2 conversion without writes. `--note` is optional for an entirely inactive state but
required and non-empty when any task is `in_progress` or `blocked`; it acknowledges that
task's current acceptance definition.

Real v1/v2 migration writes timestamped original config/tasks plus a manifest under
`.harness/migrations/`, converts config/tasks, and refreshes handoff. Unfinished passing
evidence is retained only as legacy history and checks become unverified. Done tasks stay
historical. v2 Git/policy baselines and blocking counters remain. Active/blocked v1 tasks
receive new baselines and retain old baselines in `legacy_baselines`.

Success or an already-v3 state exits 0. Mismatched schemas, invalid old state, unsafe
legacy evidence, missing required note, or filesystem errors exit 2. There is no silent
upgrade. Copy the intended runtime files first, back up state, run dry-run, then migrate
and reverify unfinished tasks.

## Optional GitHub adapter is outside this parser

There are no `github`, `publish`, `commit`, `push`, or browser-launch subcommands. The
separate `integrations/github/` example runs `doctor` and `run check`, then publishes a
Check Run for trusted pushes using a distinct script and GitHub environment variables.
That publication is not local task acceptance evidence.
