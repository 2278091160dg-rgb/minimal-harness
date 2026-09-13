# Dual-agent initialization and GitHub delivery

## Approved scope

Provide a source-checkout installer for Codex and Claude Code, preserve existing
project state and instructions, document everyday use, and demonstrate serial
handoff in both directions. Base: `be424bd4f88b5021f36d0888fd9d14ff979b382a`.

Global constraints: Python 3.9+ standard library at runtime; config/tasks v2 and
evidence v3 remain unchanged; preserve the existing CLI and release ZIP contract.
Do not add model orchestration, concurrency, state migration, or cross-worktree
synchronization. Push a feature branch and open a PR, without merging or releasing.

## Task 1: Installer and instruction adapters

Implement `scripts/init_harness.py` and behavioral tests in
`tests/test_init_harness.py`. CLI: required `--workspace`, optional
`--agent codex|claude|both` (default both), and `--dry-run`. The workspace must
already exist. Use a fixed source manifest from `template/.harness`, never copy
arbitrary evidence, caches, logs, or a used runtime's task state.

- A fresh install copies the canonical runtime, config, tasks, bootstrap handoff,
  and the three adapters. It does not execute the installed runtime, project
  commands, Git commands, or task actions.
- Existing complete config/tasks v2 installations retain every runtime file and
  state byte. Validate required file/directory types and JSON structure using the
  trusted source runtime's validators, not code from the destination project.
  Missing runtime files, malformed state, and config/tasks v1 are errors; there
  is no implicit upgrade or repair. Runtime version is not inferred from v2 JSON.
- Merge selected root instruction files using agent-specific managed markers
  `<!-- minimal-harness:codex:start -->` / `<!-- minimal-harness:codex:end -->`
  and equivalent `claude` markers. Preserve bytes outside the managed block.
  Missing files are created, missing blocks appended, existing blocks updated.
  Re-running with identical contents is a no-op. Reject partial, duplicate,
  reversed, nested, or unexpected minimal-harness markers and non-UTF-8 inputs.
- Reject symlinked destinations and symlinked path ancestors before any write.
  Preflight the complete operation before writing; reject existing non-file
  instruction destinations and unsafe source entries as well.
- If existing state has an active or blocked task, reject changes without writing
  any file. A true no-op succeeds. Dry-run reports the plan and a blocking condition
  without mutation; use the same nonzero exit code as the real blocked operation.
- Success exit 0; active-task gate exit 1; configuration, filesystem, and input
  errors exit 2. Print clear create/update/unchanged actions and next commands.
- Do not change `doctor` or automatically generate handoff. Newly installed
  template config/tasks still need project-specific editing; say this explicitly.
- Unify the three adapters: doctor/status/read HANDOFF; resume the active task;
  next only with no active/blocked task; verify command evidence; actually perform
  browser/manual checks before record; complete only after all gates; handoff at
  stopping points. Changes after verification require fresh evidence. One writer.
  Preserve user authorization already given instead of asking twice for it.

Use test-first development for installation, preservation, idempotency, dry-run,
single-agent selection, malformed markers/state, unsafe paths, and activity gates.
Also prove the copied runtime works independently via doctor/status subprocesses.

## Task 2: Browser evidence and deterministic handoff

Add `--artifact-dir PATH` to `tests/todo_browser_acceptance.py`. Default behavior
continues to produce the existing temporary screenshot. An explicit directory
receives separate add/toggle/persist screenshots; after successful checks print
their paths. Browser assets are created before recording Harness evidence.
Keep `HARNESS_CDP_URL` support and do not add runtime dependencies.

Add deterministic subprocess coverage using isolated temporary Git projects,
Todo application files, a complete installed runtime and Todo-specific config
and tasks. One process claims and hands off a task; the next inspects the same
task without claiming another. Assert task identity, untouched prior evidence,
and lifecycle transitions. These are process tests, not claims of real agents.

## Task 3: Bilingual usage and real-agent smoke verification

Update both READMEs with source-checkout initialization, safe repeat invocation,
dry-run, project customization, Codex/Claude entry points, and four copyable
prompts (initial setup, start/resume, hand off, take over). Preserve ZIP setup,
explicitly explaining it does not contain the source installer. Explain shared
workspace, one writer, and run check versus verify. Add the new scripts/tests to
the existing validation workflow only if discovery does not already cover them.

In two isolated temporary Todo Git projects, exercise actual Codex -> Claude
and Claude -> Codex sessions serially. Sender must leave a current task with an
unverified acceptance; receiver reads state/handoff and continues that task,
performs browser acceptance, records real artifacts and completes it. Use the
user's existing login and permission configuration. If either executable cannot
connect or run, retain an explicit UNVERIFIED result rather than simulating it.
Only sanitized outcomes, reproducible steps and limitations are committed;
raw session data, credentials, runtime state and private screenshots stay local.

## Task 4: Review and GitHub delivery

Run Python unittest discovery (including release packaging), Node tests, ruff,
template/example doctor and example check, plus actual Chromium acceptance.
Run independent spec/quality review of changes and fix actionable findings.
Commit on `codex/dual-agent-init`, push that branch and create a PR against main.
Check remote CI; fix failures attributable to the change. Do not merge, tag,
publish a release, or change unrelated project data.
