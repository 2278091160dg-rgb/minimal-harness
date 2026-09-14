# Practical usage guide

[简体中文](usage-guide.zh-CN.md) · [README](../README.md) ·
[CLI reference](cli-reference.md) · [Documentation index](README.md)

These four cases use v0.2.0-beta.2 and schema v3. Run them from that source tag; the
`examples/quickstart` and `examples/todo` fixtures are not in the published runtime ZIP.
The v0.2.0-beta.2 runtime includes Git/runner hardening and installs `.harness/LICENSE`.

In installed projects, run `python3 .harness/harness.py ...` from the project root.
When invoking the template from elsewhere, put the global `--workspace PATH` before the
subcommand. Without `--workspace`, Harness uses the script's parent directory's parent,
not the shell's current directory. A relative `--from` path is instead resolved from the
shell's current directory.

## Case 1: catch and fix a command-line regression

This uses the supplied greeting fixture and the default allowed paths. From the source
repository root:

```bash
mkdir ../harness-regression-demo
cp -R examples/quickstart/src examples/quickstart/tests examples/quickstart/greeting.task.json ../harness-regression-demo/
python3 template/.harness/harness.py --workspace ../harness-regression-demo init --agent codex
cd ../harness-regression-demo
git init
python3 .harness/harness.py doctor
python3 .harness/harness.py task add --from greeting.task.json
python3 .harness/harness.py next
```

The generated policy already contains the needed scope:

```json
"allowed_paths": ["src/**", "tests/**", ".harness/**"]
```

The source fixture supplies this definition:

```json
{
  "id": "greeting",
  "title": "Greet a named user and support the default name",
  "acceptance": [{
    "id": "greeting-cli",
    "type": "command",
    "instruction": "The CLI greets Ada by name and greets world when no name is given.",
    "command": ["{python}", "tests/check_greeting.py"],
    "timeout_seconds": 30
  }]
}
```

Introduce a regression in the disposable copy and run acceptance:

```bash
python3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hello', 'Hi'), encoding='utf-8')"
python3 .harness/harness.py verify greeting
```

The check prints an `Expected 'Hello, Ada!'` mismatch. `verify` exits 1, the check is
`failed`, and no completion is authorized. `run check`, if configured, would still be a
project helper and could not replace this acceptance result.

Fix the behavior and rerun:

```bash
python3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hi', 'Hello'), encoding='utf-8')"
python3 .harness/harness.py verify greeting
python3 .harness/harness.py report greeting --format text
python3 .harness/harness.py complete greeting
python3 .harness/harness.py handoff
```

Expected outcomes are the fixture's `PASS: named and default greetings match the CLI
contract`, `greeting [in_progress] — ready`, and `Completed greeting`. `verify` writes a
bounded log, attempt record, evidence, task state, and handoff. `report` is read-only.

To see freshness enforcement, edit `src/greet.py` after a passing `verify` but before
`complete`. `report greeting` and `complete greeting` exit 1 with stale-source detail.
Restore the behavior and run `verify greeting` again.

## Case 2: browser screenshot acceptance

The source repository includes a complete disposable Todo walkthrough. It starts an
owned local server, drives real Chromium through Playwright, checks add/toggle/reload
persistence, writes real screenshots, records each observation, completes all three
tasks, and prints its proof directory:

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
python3 tests/run_todo_walkthrough.py
```

Port 8000 must be free. Success ends with `PASS: add, toggle, and reload persistence
verified` and `BROWSER_PROOF_DIRECTORY=...`. Treat those statements as valid for that run
only because the helper actually performed the browser actions and asserted the results.
The source files merely being present, a screenshot existing, or this guide describing an
outcome is not proof that a browser trial happened.

For a user-controlled browser run, create a disposable project from the supplied Todo
fixture. From the source repository root, copy the application, initialize empty state,
and install the supplied command/policy configuration. This manual route also requires
Node.js for `run check` and a browser tool that can save a screenshot into the workspace:

```bash
mkdir ../harness-todo-manual
cp -R examples/todo/site examples/todo/test.mjs ../harness-todo-manual/
python3 template/.harness/harness.py --workspace ../harness-todo-manual init --agent codex
cp examples/todo/.harness/config.json ../harness-todo-manual/.harness/config.json
cd ../harness-todo-manual
git init
mkdir -p .harness/specs .harness/artifacts
python3 .harness/harness.py doctor
```

Save this minimal definition as `.harness/specs/todo-add.json`:

```json
{
  "id": "todo-add",
  "title": "Add an unchecked Todo item",
  "acceptance": [{
    "id": "add-in-browser",
    "type": "browser",
    "instruction": "Adding a Todo shows one matching unchecked item.",
    "steps": [
      "Open http://127.0.0.1:8000.",
      "Enter 验证 Harness and click 新增待办.",
      "Observe one matching item and confirm its checkbox is unchecked."
    ]
  }]
}
```

Use the Todo policy so application changes are in scope:

```json
"allowed_paths": ["site/**", "test.mjs", "proof/**", ".harness/**"]
```

Add it, select it, and start the configured server in terminal 1:

```bash
python3 .harness/harness.py task add --from .harness/specs/todo-add.json
python3 .harness/harness.py next
python3 .harness/harness.py run check
python3 .harness/harness.py run start
```

`run check` executes the Node tests but creates no task acceptance. `run start` remains
attached until stopped. In terminal 2, use the browser tool to perform the exact steps.
Save its actual screenshot as `.harness/artifacts/todo-add.png`. Confirm it is a regular,
non-empty file inside the workspace. Only after observing the stated result, record it:

```bash
python3 .harness/harness.py record todo-add add-in-browser --result passed \
  --summary "Entered 验证 Harness, clicked 新增待办, and observed one matching unchecked item." \
  --tool playwright \
  --artifact .harness/artifacts/todo-add.png
python3 .harness/harness.py report todo-add
python3 .harness/harness.py complete todo-add
```

A successful record prints `Recorded todo-add/add-in-browser: passed`. If no browser
tool or valid screenshot is available, record the real limitation instead:

```bash
python3 .harness/harness.py record todo-add add-in-browser --result unverified \
  --summary "Browser tool was unavailable; the acceptance steps were not performed."
```

That command exits 1 and completion stays closed. A browser pass additionally requires
`--tool` and at least one `--artifact`; repeat `--artifact FILE` for multiple captures.
Harness binds the observation and artifact digests to the current source but does not
independently decide whether the observation is truthful.

## Case 3: revise requirements and reverify

Use a fresh greeting demo, then add, select, and verify the supplied definition as in
Case 1. Before completing it, create `.harness/specs/greeting-v2.task.json` with this
complete replacement definition:

```bash
mkdir -p .harness/specs
```

```json
{
  "id": "greeting",
  "title": "Also greet Grace exactly",
  "acceptance": [{
    "id": "grace-cli",
    "type": "command",
    "instruction": "greet('Grace') returns exactly Hello, Grace!",
    "command": [
      "{python}",
      "-B",
      "-c",
      "from src.greet import greet; assert greet('Grace') == 'Hello, Grace!'"
    ],
    "timeout_seconds": 30
  }]
}
```

`.harness/specs/**` is covered by the default `.harness/**` allowed path. Revise and
inspect the invalidated result:

```bash
python3 .harness/harness.py task revise greeting \
  --from .harness/specs/greeting-v2.task.json \
  --note "Acceptance now names Grace explicitly"
python3 .harness/harness.py status
python3 .harness/harness.py report greeting
```

Revision prints `Task revise: greeting`. Status shows `grace-cli [unverified]`; report
exits 1 and recommends verification. Revision preserves the task's starting Git and
policy baselines, records the old definition in revision history, and does not expand
`allowed_paths`.

Run the replacement check and finish:

```bash
python3 .harness/harness.py verify greeting
python3 .harness/harness.py report greeting --format json
python3 .harness/harness.py complete greeting
```

The inline command exits 0, the JSON report has `"ready": true` and `"exit_code": 0`,
and completion succeeds. The definition ID must match `greeting`. A completed task cannot
be revised. A blocked task must be unblocked before revision; revision cannot bypass its
failure threshold.

## Case 4: interrupted, blocked, and new-session recovery

This case supplies both command and manual acceptance. In a fresh initialized Git project,
create the directories and `src/ready.txt` containing `not-ready`:

```bash
mkdir -p src .harness/specs
python3 -c "from pathlib import Path; Path('src/ready.txt').write_text('not-ready\n', encoding='utf-8')"
```

Save this definition as
`.harness/specs/recovery.task.json`:

```json
{
  "id": "recovery",
  "title": "Recover a readiness marker and inspect it",
  "acceptance": [
    {
      "id": "ready-command",
      "type": "command",
      "instruction": "src/ready.txt contains exactly ready.",
      "command": [
        "{python}",
        "-c",
        "from pathlib import Path; assert Path('src/ready.txt').read_text(encoding='utf-8').strip() == 'ready'"
      ],
      "timeout_seconds": 30
    },
    {
      "id": "ready-manual",
      "type": "manual",
      "instruction": "A person opens src/ready.txt and observes the word ready.",
      "steps": ["Open src/ready.txt.", "Observe that its complete trimmed content is ready."]
    }
  ]
}
```

The default `allowed_paths` covers `src/**` and `.harness/**`. Add and select the task:

```bash
python3 .harness/harness.py task add --from .harness/specs/recovery.task.json
python3 .harness/harness.py next
```

To exercise interruption separately, temporarily revise the command to a long-running
one such as `["{python}", "-c", "import time; print('started', flush=True); time.sleep(300)"]`,
run `verify recovery`, and press Ctrl-C while it is running, before its timeout.
`verify` displays captured output after the child stops, so do not wait for `started`
to appear in the terminal. Harness exits 130; the check is unverified and cannot
complete. Restore the definition with `task revise ... --note ...` before continuing.

With `src/ready.txt` still containing `not-ready`, run the actual definition three times:

```bash
python3 .harness/harness.py verify recovery
python3 .harness/harness.py verify recovery
python3 .harness/harness.py verify recovery
python3 .harness/harness.py status
python3 .harness/harness.py handoff
```

Each verification exits 1. With the default threshold, the third failure makes the task
`blocked`; `next`, another `verify`, revision, and completion are rejected. The failures
and recovery command appear in `.harness/HANDOFF.md`.

Fix the file, explain what changed, and rerun acceptance:

```bash
python3 -c "from pathlib import Path; Path('src/ready.txt').write_text('ready\n', encoding='utf-8')"
python3 .harness/harness.py unblock recovery --note "Corrected the readiness marker after reviewing the repeated failures"
python3 .harness/harness.py verify recovery
```

Now open `src/ready.txt` yourself. Only if you actually observe `ready`, record the manual
result; no attachment or tool is required for a manual check:

```bash
python3 .harness/harness.py record recovery ready-manual --result passed \
  --summary "Opened src/ready.txt and observed that its complete trimmed content is ready."
python3 .harness/harness.py report recovery
python3 .harness/harness.py complete recovery
python3 .harness/harness.py handoff
```

`unblock` resets failure counters and turns failed checks unverified; it does not pass
them. The subsequent command verification and actual manual observation provide the two
required passes.

At the start of a new agent or terminal session, run:

```bash
python3 .harness/harness.py doctor
python3 .harness/harness.py status
sed -n '1,240p' .harness/HANDOFF.md
```

On PowerShell, replace the last line with `Get-Content .harness/HANDOFF.md`. `doctor` is
read-only and returns 1 if otherwise-valid passed evidence has gone stale; `status` is
read-only. `handoff` is the explicit write that regenerates the session summary.

If `doctor`, `report`, or `complete` reports an `assume-unchanged` or `skip-worktree`
index flag, inspect the affected path first:

```bash
git ls-files -v -- path/to/affected-file
```

Only as a deliberate user choice, make that path visible to normal Git inspection again:

```bash
git update-index --no-assume-unchanged -- path/to/affected-file
git update-index --no-skip-worktree -- path/to/affected-file
git status --short
git diff -- path/to/affected-file
```

Review the newly revealed change. Restore a forbidden change or start a suitably scoped
task for it, then reverify the current task. Do not erase the task baseline or broaden its
frozen policy mid-task to hide the problem.

## What the evidence does and does not establish

Command evidence establishes the observed process exit and bounded log against one
consistent source and acceptance snapshot. Browser and manual evidence establish an
operator attestation plus validated artifact metadata. Source examples and automated
quickstart/Todo runs are useful engineering evidence; they do not prove that first-time
human adoption trials happened. Those remain tracked as pending in
[the trial sheet](adoption-validation.md).
