# Dual-agent initialization verification — 2026-09-13

## What was exercised

The source-checkout initializer was tested against independent temporary
projects. The Todo fixtures contained the complete installed runtime, application
files, project-specific config/tasks, both managed instruction blocks and a local
Git baseline. They did not depend on the example's repository-local wrapper.

Config/tasks remain schema v2; the unchanged core emits schema v3 evidence.
The existing release ZIP remains a runtime-only archive. The new initializer
is run from a source checkout and is not advertised as part of that archive.

## Deterministic and browser checks

Final local results on the reviewed implementation:

| Validation | Result |
| --- | --- |
| Full Python suite, Python 3.14.6 | PASS — 148 tests, including release-package regressions |
| Installer compatibility, Python 3.9.6 | PASS — 21 tests |
| Todo Node suite | PASS — 3 tests |
| Ruff 0.15.12 and Git whitespace checks | PASS |
| Template and Todo doctor | PASS |
| Actual Chromium add, toggle and persistence | PASS |
| Independent specification and code review | PASS — both reported defects fixed and regression-tested |

The local HTTP integration tests ran with localhost listening permitted. Live
model calls are excluded from CI; their separate status is recorded below.

- Installer cases cover both/single-agent installation, byte-preserving repeat
  invocation and block replacement, UTF-8 BOM/CRLF, dry-run without destination
  or source-cache writes, malformed JSON/markers, incomplete installations,
  unsafe file types, symlink ancestors (including `symlink/..`), and active or
  blocked task gates. The destination runtime is not executed by the installer.
- Independent CLI processes share the same task ID, handoff and prior evidence.
  A second claim and completion without browser acceptance are refused. The
  process-only test records the missing browser action as `unverified`.
- Actual local Chromium exercised Todo add, toggle and refresh persistence. The
  default temporary screenshot behavior passed. `--artifact-dir` produced
  separate, nonempty `add.png`, `toggle.png` and `persist.png` files showing the
  three observed states. All screenshots are created before recording evidence.
- The existing CI matrix discovers the new tests. The Chromium job additionally
  exercises the explicit artifact directory and checks all three output files.

Reproduction from the source checkout:

```bash
python3 -m unittest discover -s tests -v
node --test examples/todo/test.mjs
ruff check --no-cache template/.harness/harness.py integrations/github/publish_check.py scripts tests
python3 template/.harness/harness.py --workspace template doctor
python3 template/.harness/harness.py --workspace examples/todo doctor
python3 template/.harness/harness.py --workspace examples/todo run check
```

For browser checks, start the example server in one terminal, then run the
following in another. Playwright/Chromium are development dependencies only.

```bash
python3 template/.harness/harness.py --workspace examples/todo run start
```

```bash
python3 tests/todo_browser_acceptance.py
python3 tests/todo_browser_acceptance.py --artifact-dir "examples/todo/proof"
```

## Actual agent sessions: partial verification

| Check | Result | Observed outcome |
| --- | --- | --- |
| Codex CLI sender, version 0.144.1 | UNVERIFIED | The configured model was rejected with API 400 requiring a newer Codex version, before any task operations. No CLI upgrade or model substitution was performed. |
| Codex App native agent sender | PASS | An independent live agent loaded the installed project instructions, ran doctor/status, read handoff, claimed `todo-add`, and generated a handoff. Task remained `in_progress`; browser acceptance remained `not_run`. |
| Claude Code receiver, version 2.1.270 | UNVERIFIED | The actual CLI invocation returned `ConnectionRefused` after about 179 seconds, before executing task operations. Its configured local API forwarding endpoint had no listener. |
| Complete Codex → Claude handoff | UNVERIFIED | Sender succeeded through Codex App; Claude could not connect. The original active task and unperformed browser acceptance were preserved. |
| Complete Claude → Codex handoff | UNVERIFIED | Not advanced after confirming the shared Claude connection prerequisite was unavailable. The reverse fixture remained pending; the receiver was not started. |

The Codex App session is a real model-driven agent session, not a renamed shell
process. It verifies the sender role only. Neither the deterministic process
test nor the standalone Chromium test establishes successful cross-product
handoff. No cross-product direction is claimed as passed.

The attempts used the existing login/provider configuration. Claude's provider
destination and credentials were not changed to bypass the unavailable local
service. Raw session output, credentials, account details, temporary project
state and host-specific endpoint details are not included in this report.

## Rerunning the live handoff checks

Use a compatible Codex CLI or the Codex App and a working configured Claude Code
connection. For each direction, prepare a separate temporary Todo Git project
with the source initializer, copy the Todo application/config/tasks and browser
runner into it, and establish the Git baseline before claiming work.

1. Open the sender in that project. Read its installed instructions, run
   doctor/status, claim the first task and hand off with browser acceptance
   still unperformed.
2. Stop the sender. Serve that fixture's own `site` directory on local port 8000.
3. Open the receiver in the exact same project. Read doctor/status/handoff and
   resume `todo-add` without invoking `next`.
4. Run the copied browser runner with `--artifact-dir proof`. After successful
   browser checks and creation of all screenshots, record `add-in-browser`
   with `--tool playwright --artifact proof/add.png` and an observed summary.
5. Complete `todo-add`, regenerate handoff, and confirm the other tasks remain
   pending. If a tool or gate fails, preserve an honest non-passing state.
6. Repeat with the agent roles reversed in the second fresh fixture.

Only a successful run of both directions can change the cross-product statuses
above to PASS. A working connection is an environment prerequisite, not a reason
to weaken the Harness completion gate.
