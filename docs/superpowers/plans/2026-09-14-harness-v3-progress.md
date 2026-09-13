# Progress — 2026-09-14-harness-v3.md

Base: 0899ded. Branch: codex/harness-v3.

## Preflight interfaces

| Tasks | Interface or shared file | Resolution |
| --- | --- | --- |
| Core / runner | bounded execution result and durable log | API fixed in plan; runner file has independent owner |
| Core / init | CLI parser delegates initializer | Core owns parser; root owns initializer; no overlapping edits |
| Core / documentation | task/report CLI and schema | CLI contract fixed in plan; root verifies examples after integration |
| Core | snapshots, attempts, migration | Generated-only exclusions; source/config remain inputs; legacy passes never promoted |
| Runner | runtime bound vs development server | Bound verify; preserve long-lived run start |
| Onboarding | empty bootstrap vs ready acceptance | Empty tasks and unconfigured project commands; no fake passed task |

## Decisions

- Work on a new local branch in the shared checkout; no automatic commits or remote writes.
- Separate files for bounded execution and initialization retain a copyable stdlib runtime.
- First-time human user validation is an explicit pending follow-up, not replaced by agent simulation.

## Execution

- Baseline: Python 84/84 passed; Node 3/3 passed.
- Core: schema3, attempts, migrations, task maintenance and shared auditor implemented.
  Evidence binds current content and the full frozen contract; verification revokes old
  command passes before spawning a new command. Reports and completion share one auditor.
- Init: 14 tests passed after independent review fixed partial-write rollback, CRLF,
  missing-HANDOFF preflight and CLI agent enum. Scoped re-review approved.
- Installed-runtime walkthrough: 3/3 passed, including stale-source rejection/recovery.
- Runner: timeout/output bounds, exclusive raw logs and process-tree cleanup implemented.
  Windows uses a gated stdlib launcher: user argv is released only after Job assignment.
  Windows native API execution remains a CI check, not a local test claim.
- Real Chromium: all three Todo tasks completed with screenshot/evidence/report/handoff
  in a disposable repo. The helper prints its local proof directory; temporary evidence
  is retained locally and is not part of the distributable repository.
- Independent core review closed both P2 findings: ignored Harness inputs are mandatory,
  and clean initialized submodules are snapshotted recursively. Generated runtime bytecode
  does not cause mtime-only drift. Scope-only rejection now recommends Git inspection.
- Independent runner review closed unbounded handshake, silent short-write truncation,
  output-reader startup cleanup and handshake construction cleanup findings. Final scoped
  review passed; all reported P1/P2 findings are closed.

## Final verification

Executed on macOS after the final runtime changes:

- Python 3.14: `PYTHONDONTWRITEBYTECODE=1 python3 -W error::ResourceWarning -m unittest discover -s tests -q`
  — 157 tests passed in 48.163 seconds.
- Python 3.9: same command with `/usr/bin/python3`
  — 157 tests passed in 45.294 seconds. The bytecode regression explicitly disables Apple's
  global cache prefix in its child process so it tests the intended local cache directory.
- Node: `node --test examples/todo/test.mjs` — 3 tests passed.
- Ruff: `ruff check --no-cache template/.harness tests examples/quickstart` — passed.
- `git diff --check` — passed.
- Template and Todo `doctor` — valid; expected warnings for this uncommitted checkout.
- Todo `run check` — passed without generating task acceptance.
- Installed-runtime tests cover ready and stale reports in text, JSON and Markdown.
- Real Chromium: add, toggle and reload persistence passed, including recording, reporting,
  completion and handoff; the temporary server was stopped afterward.

Linux/Windows CI jobs have been retained but not executed in this local session. Actual
Windows Job API behavior remains a platform validation boundary. First-time human adoption
is pending; no external participants were contacted. These results describe the initial
local implementation on `codex/harness-v3`, before integration and GitHub CI.

## Acceptance coverage

| Approved requirement | Retained check |
| --- | --- |
| Stale code, changed/deleted acceptance, mid-run drift | `tests/test_harness_v3.py` |
| Rerun invalidation, interruption, spawn failure, damaged evidence | v3 and existing Harness suites |
| Timeout, byte limit, raw log integrity, process cleanup | `tests/test_runner.py` plus core integration |
| Long-lived development server | Existing Harness compatibility tests |
| v1/v2 migration, active/blocked state and original baselines | v3 and existing migration regressions |
| Safe init, host instructions, dry run and idempotency | `tests/test_init.py` |
| Copied-runtime first use, stale-pass rejection and recovery | `tests/test_walkthrough.py` |
| Real browser add/toggle/persistence and recorded completion | `tests/run_todo_walkthrough.py` |
| Linux/macOS/Windows coverage | Retained CI matrix; remote jobs not run locally |
| First-time human adoption | `docs/adoption-validation.md`; pending real participants |
