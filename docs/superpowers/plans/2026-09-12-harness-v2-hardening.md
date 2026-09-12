# Minimal Harness v2 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every uncertain Git, state, and evidence condition fail closed while retaining a Python 3.9+ standard-library runtime.

**Architecture:** Upgrade configuration and task state to schema v2, capture complete Git worktree/index baselines, bind evidence payloads to digests, and make HANDOFF a validated derived view. A strict explicit migration preserves v1 source files and records any unavoidable provenance discontinuity.

**Tech Stack:** Python 3.9+ standard library, Git CLI, Node.js tests, optional Playwright browser acceptance.

**Spec:** User-approved Minimal Harness v2 hardening plan derived from the independent audit of HEAD `4a94b08aac4dcb0c86fa6ccbca9d8c735b872df4`.

## Global Constraints

- No third-party Harness runtime dependencies.
- Keep the existing public commands and exit-code contract; add only `migrate`.
- Do not add locking, multi-Agent merging, automatic Git history changes, or an OS sandbox.
- Use strict schema v2 migration; never silently trust incomplete v1 baselines or evidence.

---

### Task 1: Strict v2 state and migration

**Files:** `template/.harness/harness.py`, template/example JSON, `tests/test_harness.py`

- [ ] Add failing tests for v2 schema validation, impossible blocked states, missing lifecycle baselines, migration dry-run/idempotency, active-task acknowledgement, and legacy evidence handling.
- [ ] Implement schema v2 validators and explicit `migrate [--dry-run] [--note TEXT]`.
- [ ] Preserve immutable v1 source snapshots and a migration manifest; rebaseline acknowledged active tasks and downgrade active legacy passed checks to `unverified`.
- [ ] Run targeted and full Python tests.
- [ ] Commit `fix: add strict harness v2 state migration`.

### Task 2: Fail-closed Git scope audit

**Files:** `template/.harness/harness.py`, `tests/test_harness.py`

- [ ] Add failing tests for Git command failure, index/worktree divergence, branch/HEAD changes, unborn repositories, nested workspaces, and segment-aware allowed paths.
- [ ] Capture worktree and index fingerprints and reject every uncertain Git operation during completion.
- [ ] Replace path matching with segment-aware `*`/`**` semantics and reject unsafe patterns.
- [ ] Run targeted and full Python tests.
- [ ] Commit `fix: make git scope audit fail closed`.

### Task 3: Evidence integrity

**Files:** `template/.harness/harness.py`, `tests/test_harness.py`

- [ ] Add failing tests for symlink roots, directory artifacts, missing browser provenance, mutated artifacts/logs, and collision-safe evidence creation.
- [ ] Emit evidence schema v2 with regular-file type, size, and SHA-256 metadata for logs and artifacts.
- [ ] Validate full evidence payloads from doctor, complete, and handoff without rewriting historical files.
- [ ] Run targeted and full Python tests.
- [ ] Commit `fix: bind evidence logs and artifacts`.

### Task 4: Handoff and subprocess reliability

**Files:** `template/.harness/harness.py`, shipped HANDOFF files, `tests/test_harness.py`

- [ ] Add failing tests for HANDOFF self-staleness, invalid evidence display, invalid byte output, workspace-relative executables, and SIGINT.
- [ ] Exclude generated HANDOFF from its displayed snapshot, expose snapshot/schema metadata, and render invalid evidence as warnings.
- [ ] Capture command output as bytes, preserve raw log bytes, decode terminal output safely, and return 130 on interruption.
- [ ] Replace shipped snapshots with bootstrap HANDOFF documents.
- [ ] Run targeted and full Python tests.
- [ ] Commit `fix: harden handoff and command execution`.

### Task 5: Documentation, example, and release gates

**Files:** `README.md`, browser acceptance, CI workflow, template/example configs and tasks

- [ ] Update README for migration, schema v2, path semantics, Git-required completion, provenance boundaries, and platform-neutral commands.
- [ ] Extend browser acceptance with computed-style, failed-resource, and screenshot-file assertions.
- [ ] Add Linux/macOS/Windows CI for Python 3.9 and current Python plus Node LTS tests.
- [ ] Run Python, Node, Ruff, doctor, example checks, and real-browser acceptance.
- [ ] Request independent code review, fix all Critical/Important findings, and repeat verification.
- [ ] Commit `test: add adversarial and cross-platform coverage`.
