# Minimal AI Coding Harness

A small, local acceptance and handoff tool for coding agents. Define what must work,
run the checks, keep evidence, and only complete a task while that evidence matches
both the current source and the agreed acceptance definition.

**Python 3.9+ standard library · Git · one writer · no model API or service**

[中文说明](docs/README.zh-CN.md) · [First-time user validation](docs/adoption-validation.md)

## Try a complete task

Clone this repository and create a disposable project (if already downloaded, start
from the repository root at `mkdir`):

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

The check invokes the actual greeting CLI with and without a name. Expect both behaviors
to pass, a ready report, and a completed task recorded in `.harness/HANDOFF.md`.
Git does not need an initial commit for this example. To see stale-evidence rejection,
change `Hello` to `Hi` in `src/greet.py` **after verify and before complete**: the report
and completion must reject the old result. Restore the behavior and run `verify` again.

PowerShell setup (then run the same `doctor` → `handoff` commands using `py -3`):

```powershell
New-Item -ItemType Directory ..\harness-demo
Copy-Item -Recurse examples\quickstart\src, examples\quickstart\tests, examples\quickstart\greeting.task.json ..\harness-demo\
py -3 template/.harness/harness.py --workspace ../harness-demo init --agent codex
Set-Location ..\harness-demo
git init
```

Use `--agent claude` for `CLAUDE.md`, `--agent generic` for generic `AGENTS.md` guidance,
or omit `--agent` to install only the runtime. `init --dry-run` previews the changes.
Existing instructions are preserved and a managed block is appended once. Conflicting
blocks, partial installs, symlink targets, and different installed runtimes are rejected.
`init` does not upgrade an existing installation or overwrite its tasks/configuration.

## Use it in your project

Initialize from this checkout with the global `--workspace PATH` **before** the command:

```bash
python3 template/.harness/harness.py --workspace /path/to/project init --agent codex
```

Before selecting a task, configure `.harness/config.json`:

- Set `policy.allowed_paths` to the files this task may change. Defaults are `src/**`,
  `tests/**`, and `.harness/**`; root-level application files need explicit patterns.
- Set optional `commands.setup/start/check` to argv arrays, or leave them `null`.
- `{python}` in argv resolves to the interpreter running Harness. No command uses a shell.
- `*` matches one path segment; `**` crosses directories. Git is required for completion
  by default. Initialization neither creates a Git repository nor changes its history.

Write a **definition-only** JSON file, without status, counters, or evidence hashes:

```json
{
  "id": "greeting",
  "title": "Greet a named user and support the default name",
  "acceptance": [{
    "id": "greeting-cli",
    "type": "command",
    "instruction": "Named and default greetings match the expected CLI output.",
    "command": ["{python}", "tests/check_greeting.py"],
    "timeout_seconds": 30
  }]
}
```

`task add --from SPEC.json` generates runtime fields. Start with `next`. After selection,
the acceptance definition and edit policy are frozen. To change the requirement explicitly:

```bash
python3 .harness/harness.py task revise greeting --from .harness/specs/revised.task.json --note "Explain the requirement change"
```

Revision requires the same task ID, preserves the task's Git/policy starting point and
invalidates previous evidence. Completed tasks cannot be revised. Blocked tasks require
`unblock ID --note TEXT` first; revision cannot bypass a blocker. Do not hand-edit runtime
status or hash fields. A passing command is only as useful as the behavior it checks:
Harness does not decide whether your acceptance criteria are sufficient.

Keep new revision specifications inside an allowed path such as `.harness/specs/`.
Creating or editing a specification outside the frozen edit scope is still an out-of-scope
change; `task revise` does not expand permission to edit other files.

## Checks, reports, and recovery

- **`verify [ID]`** runs command acceptance and records evidence. Default limit: 300 seconds
  per command and 10 MiB of raw log bytes; positive `timeout_seconds` can override time.
  Timeout and output-limit failures retain the bounded partial log. Interruptions leave
  the check unverified, even if an earlier attempt passed.
- **`run check`** runs the configured project check but **does not record task acceptance**.
  `run setup` and `run start` are project helpers; `start` remains long-running.
- **`report ID --format text|json|markdown`** is a read-only completion preflight. It shows
  each check, evidence source, blockers/staleness and the next command. It shares the
  completion auditor with `complete`; output is stdout, with no automatic uploads.
- **`complete ID`** requires passing current checks, intact evidence, unchanged acceptance
  definitions and source content, and a successful Git scope audit.
- **`handoff`** writes the generated session summary. Start a new session with `doctor`,
  `status`, and `.harness/HANDOFF.md`. Follow the configured failure threshold; defaults
  block a task after three consecutive failures of one check.

For command verification, source and acceptance digests must match before and after the
run. Completion recalculates them. Generated runtime state, evidence, attempts, migration
archives, managed `.harness/artifacts/`, reports, HANDOFF and the runtime's
`.harness/__pycache__/` are fixed exclusions. Git-tracked and non-ignored files are checked;
Harness code and configuration are checked even when `.harness/` is ignored. Do not store
application code in these reserved output locations. Modification time alone does not
invalidate a result. Initialized, clean Git submodules are included recursively; dirty or
uninitialized submodules and hidden index flags stop verification with a diagnostic.

Task states remain `pending / in_progress / blocked / done`; check states remain
`not_run / passed / failed / unverified`. Unverified never means passed. CLI exit codes:
`0` success/ready, `1` failed acceptance or unmet gate, `2` invalid configuration/usage,
`130` user interruption. A report on a finished task describes historical completion;
it cannot authorize a new completion.

## Browser and manual acceptance

A browser definition uses `type: "browser"`, an instruction, and a non-empty `steps` array.
Perform the actual actions with your browser tool and save artifacts under the reserved
`.harness/artifacts/` directory. Then record the observation:

```bash
python3 .harness/harness.py record TASK_ID CHECK_ID --result passed \
  --summary "Describe the actions and observed result" \
  --tool playwright --artifact .harness/artifacts/screenshot.png
```

A browser pass requires a tool name and a real, non-symlink workspace artifact. Manual
checks accept a non-empty observation; attachments are optional. Both are **attestations
at recording time**, not independent proof that a screenshot or human statement is true.
Unavailable tools must be recorded as `unverified` with an explanation.

The Todo example exercises add, toggle, and persistence with real Chromium. This helper
creates a disposable Git project, starts its own local server, and runs the complete loop:

```bash
# From this repository. Optional developer dependency; not a Harness runtime dependency.
python3 -m pip install playwright
python3 -m playwright install chromium
python3 tests/run_todo_walkthrough.py
```

The helper prints the directory containing screenshots, evidence and the final handoff,
then stops its server. Port 8000 must be free. The shipped example stays unchanged.
For a server you started yourself, `tests/todo_browser_acceptance.py --workspace PATH
--record` records into that workspace; omit `--record` for browser-only regression.
That lower-level script accepts `HARNESS_CDP_URL` for a dedicated Chromium instance;
the disposable helper always starts an isolated headless browser.

## Upgrade from v1 or v2

Back up your installation, then replace only `harness.py`, `harness_init.py`, and
`harness_runner.py` from `template/.harness/`. Keep your configuration, tasks and evidence.
Preview and explicitly migrate:

```bash
python3 .harness/harness.py migrate --dry-run
python3 .harness/harness.py migrate --note "Acknowledge the current acceptance definition for v3"
```

Migration archives the old state and preserves historical evidence. Old passing evidence
cannot acquire source/contract bindings retroactively: unfinished tasks must reverify.
Existing v2 Git/policy baselines and blocking counters survive; completed legacy tasks
are labeled historical, not v3 verified. A v1 task lacking a usable baseline requires an
explicit note before rebaselining. Repeated migration is safe; there is no silent upgrade.

## Trust and scope

This is a local workflow tool for a cooperating agent and developer. It is not an OS
sandbox or independent anti-forgery service. Allowed paths are audited at completion;
approval-operation settings are workflow instructions, not syscall interception. A caller
with write access to the runtime and state can bypass it. Ignored dependencies, external
services, environment changes and the quality of the acceptance definition are outside
source-fingerprint guarantees. Evidence does not automatically prove those stayed fixed.

One writer is supported; there is no multi-agent transaction or concurrent ownership
protocol. The runtime never calls a model, sends telemetry, commits, pushes or publishes.

## Development checks

```bash
python3 -m unittest discover -s tests -v
node --test examples/todo/test.mjs
ruff check --no-cache template/.harness tests
python3 template/.harness/harness.py --workspace template doctor
python3 template/.harness/harness.py --workspace examples/todo doctor
```

CI retains Linux/macOS/Windows Python coverage and a real Chromium acceptance job. Human
adoption validation is tracked separately; automated tests do not replace first-time users.
