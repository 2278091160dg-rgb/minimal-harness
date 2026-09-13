# Evidence Freshness and Release Implementation Plan

> **For Codex:** Use `superpowers:executing-plans`, `superpowers:test-driven-development`, and `superpowers:verification-before-completion`. Keep the runtime Python 3.9+ standard-library-only. Do not publish or submit account forms before the final release preflight.

**Goal:** Bind passed evidence to the Git state it verified, then prepare and publish an MIT-licensed first release with an optional GitHub Check Run adapter.

**Architecture:** Keep config/tasks/baselines at schema v2 and introduce evidence schema v3. Capture a filtered Git verification subject after each acceptance action, validate it through one shared path from doctor/handoff/complete, and treat stale evidence as a workflow gate rather than state corruption. Keep GitHub API publishing outside the copied `.harness` runtime.

**Tech stack:** Python 3.9+ standard library, `unittest`, Git CLI, GitHub Actions, Node LTS for the Todo example, Playwright only for browser acceptance.

---

## Task 1: Characterize stale evidence with failing tests

**Files:**

- Modify: `tests/test_harness.py`
- Reference: `template/.harness/harness.py`

1. Add helpers that create a passed command/manual/browser evidence record and then mutate the workspace.
2. Add failing tests proving `complete` rejects changes made after verification for unstaged, staged, committed, renamed, deleted, pre-dirty, branch, and unborn-repository cases.
3. Add failing tests proving generated `tasks.json`, evidence, log, HANDOFF, and migration files do not self-invalidate.
4. Add failing tests proving edits to `.harness/config.json` and `.harness/harness.py` do invalidate evidence.
5. Run the focused tests and confirm failure is specifically caused by missing freshness validation.

Command:

```bash
python3 -m unittest -v \
  tests.test_harness.HarnessTests.test_complete_rejects_code_changed_after_pass \
  tests.test_harness.HarnessTests.test_generated_harness_state_does_not_stale_evidence
```

## Task 2: Add evidence v3 verification subjects

**Files:**

- Modify: `template/.harness/harness.py`
- Modify: `tests/test_harness.py`

1. Add `EVIDENCE_SCHEMA_VERSION = 3` without changing `SCHEMA_VERSION = 2`.
2. Refactor `git_snapshot` and committed-change comparison to accept the exact Harness-generated path exclusions while preserving nested-workspace behavior and fail-closed return-code checks.
3. Capture `verification_subject` after command execution or artifact validation and before evidence/state writes.
4. Store no machine-absolute path in evidence.
5. Extend evidence structural validation for the new subject fields.
6. Run the focused evidence creation and Git adversarial tests.
7. Commit: `fix: bind evidence to verification git state`.

## Task 3: Enforce freshness consistently

**Files:**

- Modify: `template/.harness/harness.py`
- Modify: `tests/test_harness.py`

1. Add a distinct stale-evidence gate error so stale evidence maps to exit 1 while malformed/tampered evidence remains exit 2.
2. Make the shared evidence validator compare v3 verification subjects with the current filtered Git snapshot.
3. Make `complete` reject stale passed evidence without mutating `tasks.json`.
4. Make `doctor` report stale active evidence as a gate failure without mutating state.
5. Make `handoff` label stale evidence and omit its summary from trusted results.
6. Confirm v2 passed evidence on unfinished tasks requires re-verification, while completed legacy state remains readable.
7. Confirm frozen `require_git_for_completion: false` permits completion with an explicit not-Git-bound warning.
8. Run all focused doctor/handoff/complete and legacy tests.
9. Commit: `fix: fail closed on stale completion evidence`.

## Task 4: Update documentation and release files

**Files:**

- Create: `LICENSE`
- Create: `SECURITY.md`
- Create: `CONTRIBUTING.md`
- Modify: `README.md`
- Modify: `template/.harness/HANDOFF.md` if generated documentation changes

1. Add the canonical MIT license with `Copyright (c) 2026 denggui`.
2. Document evidence v3, re-verification semantics, generated-state exclusions, the Git opt-out warning, security boundary, and responsible disclosure route.
3. Document contribution checks and compatibility expectations.
4. Describe the tool as an acceptance kernel, not a Codex Skill or sandbox.
5. Regenerate/verify the shipped handoff bootstrap if needed.
6. Run both shipped `doctor` commands and Markdown/path checks.
7. Commit: `docs: prepare minimal harness for MIT release`.

## Task 5: Build the optional GitHub Check Run adapter with TDD

**Files:**

- Create: `integrations/github/publish_check.py`
- Create: `integrations/github/minimal-harness-check.yml`
- Create: `tests/test_github_integration.py`
- Modify: `README.md`

1. Write failing tests using a local mock HTTP server for a successful Check Run request, GitHub error response, missing token/repository/SHA, invalid summary input, and non-UTF-8 HTTP error payload.
2. Implement a standard-library REST client using `urllib.request` and explicit GitHub headers.
3. Accept conclusion and trusted summary-file inputs; never scrape untrusted evidence summaries.
4. Add an example workflow with least-privilege permissions and a safe fork-PR boundary.
5. Run adapter tests and the full Python suite.
6. Commit: `feat: add optional github check run adapter`.

## Task 6: Full verification and independent review

**Files:**

- Review all changed files

1. Run Python unit tests on the current Python.
2. Run Python 3.9 tests when a local interpreter is available; otherwise rely on the existing CI matrix and report that limitation.
3. Run Node tests and Ruff.
4. Run template and Todo doctors plus Todo `run check`.
5. Start the Todo server and execute real Chromium acceptance, including screenshot validation.
6. Use `superpowers:requesting-code-review` for an independent read-only review.
7. Apply valid review findings with regression tests, then repeat the entire verification set.
8. Commit any review fixes separately.

Commands:

```bash
python3 -m unittest discover -s tests -v
node --test examples/todo/test.mjs
ruff check --no-cache template/.harness/harness.py integrations/github/publish_check.py tests
python3 template/.harness/harness.py --workspace template doctor
python3 template/.harness/harness.py --workspace examples/todo doctor
python3 template/.harness/harness.py --workspace examples/todo run check
```

## Task 7: Release preflight and GitHub publication

**Files/state:**

- Git history and repository metadata
- GitHub repository `2278091160dg-rgb/minimal-harness`

1. Inspect the complete reachable Git history for credentials, private data, machine paths, generated artifacts, and unintended large files.
2. Confirm the worktree is clean and commits contain only intended changes.
3. Push `codex/evidence-freshness-release` and require green three-platform CI.
4. Merge to `main` without rewriting history and verify `origin/main`.
5. Set the repository description and topics.
6. Change visibility from private to public only after steps 1-5 pass.
7. Create tag and GitHub Release `v0.1.0` with concise release notes.
8. Re-run public clone smoke tests.

Stop instead of publishing if secret scanning is uncertain, CI is not green, repository ownership is ambiguous, or GitHub rejects a required protection/visibility operation.

## Task 8: Developer Program readiness report

**Files:**

- Create: `docs/research/2026-09-13-github-developer-program-readiness.md`

1. Record the fixed commit/release links proving the GitHub API integration exists.
2. Map current state to the official Developer Program requirements.
3. List the one remaining owner-supplied field: a support email authorized for publication.
4. Do not submit the application or publish an inferred email address.
5. Record GitHub Accelerator/Fund readiness separately; do not claim an application window is open without current official evidence.
6. Commit: `docs: assess github developer program readiness`.

## Definition of Done

- Passed evidence cannot survive a later relevant Git change when Git completion is required.
- Generated Harness state does not self-invalidate evidence.
- Evidence v2 remains immutable and has explicit legacy behavior.
- Full local verification and independent review pass.
- MIT and release documentation are present.
- The optional GitHub adapter is tested and isolated from the core runtime.
- Public release occurs only after clean-history and CI gates.
- Developer Program submission remains blocked only on an explicitly authorized support address.
