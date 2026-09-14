# Minimal Harness hardening and bilingual documentation

User-approved implementation plan, 2026-09-14. Base: `28dc64d`.

Goal: fix Git scope and Windows interruption defects, ship the license with the
runtime, validate real release assets, and provide complete English/Chinese user
documentation. Deliver a GitHub PR with passing CI; do not merge or publish.

Global constraints: Python 3.9+ standard library runtime; schema v3 and existing
CLI/JSON/state contracts; one writer; no CLI localization. Published versions are
v0.1.1 stable and v0.2.0-beta.1 prerelease. Current work is unreleased. Human trials
remain pending; prepare bilingual materials without contacting participants.

## Task 1: Runtime correctness

Owner files: `template/.harness/harness.py`, `template/.harness/harness_runner.py`,
`tests/test_harness.py`, `tests/test_harness_v3.py`, `tests/test_main_integration.py`,
`tests/test_runner.py`. Other workers own initializer, packaging, CI and docs.

- Add failing behavioral regressions before changing production code. Existing
  reproducible defect: clean tracked protected.txt, next, update-index with
  --assume-unchanged or --skip-worktree, modify protected.txt outside allowed_paths,
  verify/report/complete incorrectly all succeed.
- Reject hidden index flags at the Git snapshot entrypoint for the current
  workspace. Report affected paths and recovery commands; never change flags
  automatically. Reuse this validation for nested submodules. Respect nested
  workspaces: unrelated sibling paths must not prevent this workspace's audit.
- Cover flags before next, during verification, after a pass, re-verification,
  both flags together, and recovery after clearing flags and reverting forbidden
  changes. Retain initialized-submodule and source freshness protections.
- Replace the main runner loop's Event.wait(0.01) with short sleep so an interrupt
  cannot be masked by Condition lock cleanup. Preserve returncode 130, bounded
  raw logs, cleanup, timeout/output limits, and long-running run start.
- Test interrupt behavior and real process cleanup. Avoid Timer-only scheduling
  assumptions where readiness can be observed. Keep native Windows coverage;
  local POSIX validation does not establish Windows success.
- Preserve the existing distinction between direct Git audit errors and a shared
  report/complete not-ready decision. Do not introduce new CLI/schema fields.
- Run the affected tests, retain red/green evidence in the task report, self-review.
  Do not commit: the coordinator serializes commits after reviewing all workers.

## Task 2: Licensed distribution and release verification

Owner files: `template/.harness/LICENSE`, `template/.harness/harness_init.py`,
`scripts/build_release.py`, `scripts/check_release.py` (new), `.github/workflows/ci.yml`,
`tests/test_init.py`, `tests/test_release_package.py`, and a new release smoke test
module if needed. Do not edit runtime core/runner, README or other documentation.

- Add failing tests first. Carry the root MIT license, unchanged, in the template
  and in fresh init's .harness/LICENSE. Keep repeat init conservative and atomic;
  no user configuration, tasks, evidence, instructions or root LICENSE overwrite.
- Upgrade is explicit: users copy the three modules plus LICENSE. Tell the docs
  worker about concrete compatibility choices. A source distribution missing its
  license must fail before partially installing.
- Build from a fixed Git ref, including the license from that ref. For historical
  refs without template/.harness/LICENSE, obtain the same ref's root LICENSE;
  never substitute the current checkout. Preserve historical runtime module shape,
  generated-output rejection, normalized line endings and checksum generation.
- Add a real release check helper accepting --ref, --version, --output-dir.
  Build/archive and validate checksum, safely extract its own generated archive,
  initialize a disposable Git project, use an actual greeting behavior acceptance,
  verify, report in all formats, complete, handoff. Prove license installation and
  stale-source rejection/recovery. Test the helper against real committed runtime
  content, not stub print-only packaging fixtures. Keep meaningful failure logs.
- CI runs that helper from the checked-out SHA on its existing OS/Python matrix;
  upload diagnostic outputs on failure, without secrets or user project content.
  Keep permissions read-only; no release publication workflow.
- Coordinate helper CLI and evidence locations with the coordinator. Run scoped
  regressions and self-review; record red/green results. Do not commit.

## Task 3: Bilingual user documentation

Owner files: README.md, README.zh-CN.md; docs/README.md and docs/README.zh-CN.md;
docs/usage-guide.md and docs/usage-guide.zh-CN.md; docs/cli-reference.md and
docs/cli-reference.zh-CN.md; docs/adoption-validation.md and .zh-CN.md;
CONTRIBUTING.md and CONTRIBUTING.zh-CN.md; SECURITY.md and SECURITY.zh-CN.md.
Do not edit other existing plans, runtime, tests, examples, workflows or scripts.

- Keep both READMEs as useful entrypoints with matching language navigation and
  a capability matrix (capability, purpose, command, output/evidence, boundary).
  Cover init/agent integration, task add/revise, command/browser/manual acceptance,
  freshness, Git scope, report/complete, unblock, handoff, migration, optional GitHub.
- Supply full bilingual command references for every parser command/option:
  --workspace ordering/default, prerequisites/task states, writes vs read-only,
  output, failure recovery, exit codes. Reflect real implementation: e.g. run check
  creates no task acceptance, record browser passes need tool + real artifact,
  artifacts repeat, verify requires current in_progress task, task add reads an
  explicit definition file; no invented commands or automatic browser execution.
- Supply four executable-use-case guides: regression bugfix, browser screenshot
  acceptance, revise requirements + reverify, interrupted/blocked/session recovery.
  Include minimal command/browser/manual definitions, allowed_paths configuration,
  exact commands and observed expected outcomes. Examples must be self-contained
  or point to supplied source fixtures, not nonexistent files. Browser observations
  are actual actions by the user's browser tool, never fabricated placeholders.
- Add copyable ZIP installation routes for macOS/Linux and PowerShell, including
  downloading ZIP/checksums, checking hash, staging extraction and init. Use real
  beta.1 asset URLs. Source/PR checkout includes unreleased fixes; beta.1 ZIP does
  not include them. Stable v0.1.1 lacks v3 commands. Make version scope explicit.
- Upgrade instructions preserve state and copy the three Python modules plus the
  runtime LICENSE for this unreleased revision; don't imply beta.1 contains LICENSE.
- Complete bilingual index, human-trial materials, contribution/security guidance.
  Preserve exact factual claims, commands and support address; don't imply trials
  took place. Keep the MIT legal text English and do not translate internal history.
- Review language parity, links and command correctness. Human prose does not need
  tests that grep its contents. Coordinator will run documented workflows. Do not
  commit. Report files changed, validation and concerns to the coordinator.

## Integration and delivery

Coordinator records task progress in the plan-scoped SDD workspace, arranges
independent reviews, fixes findings, and commits focused changes sequentially.
Run Python unit tests with ResourceWarning strictness, Node tests, Ruff, doctor,
Todo check and real Chromium. Run real release smoke from committed HEAD. Check
all bilingual links and scenarios. Push codex/hardening-bilingual-docs, create PR,
wait for CI on the latest PR commit, and resolve failures without weakening tests.
No merge, tag or new release. Report remaining human-validation limitation.
