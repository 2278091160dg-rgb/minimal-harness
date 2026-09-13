# GitHub Download Growth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task, `superpowers:test-driven-development` for the release builder, and `superpowers:verification-before-completion` before commits, publication, or completion claims.

**Goal:** Publish a trustworthy, measurable `v0.1.1` download path and make the repository understandable to global developers in under one minute.

**Architecture:** Keep the Harness runtime and CLI unchanged. Improve the repository conversion surface with an English canonical README, a synchronized Chinese README, reproducible release assets built from a fixed Git ref, concise bilingual launch copy, and GitHub-native traffic measurements.

**Tech Stack:** Markdown, Python 3.9+ standard library, Git CLI, GitHub Releases/API, `unittest`.

**Spec:** The user-approved “Minimal Harness GitHub 下载增长优化计划”; supporting landscape evidence is in `docs/research/2026-09-13-github-harness-landscape-audit.md`.

## Global Constraints

- Do not change the existing CLI, schemas, return codes, or Python 3.9+ runtime dependency boundary.
- Keep MIT licensing and the existing `v0.1.0` release intact.
- Do not publish to package registries, create a website, resume the Developer Program application, or post externally.
- Treat English as canonical and keep the Chinese README behaviorally synchronized.
- The 30-day north-star is 30 ZIP download events above the maintainer-verification baseline, corroborated with GitHub traffic data.

---

### Task 1: Add a tested fixed-ref release builder

**Files:**

- Create: `scripts/build_release.py`
- Create: `tests/test_release_package.py`

- [ ] Write tests proving the builder archives only Git-tracked `template/.harness/` content from the requested ref under a `.harness/` root.
- [ ] Prove untracked runtime state and dirty working-tree changes are excluded.
- [ ] Prove the generated checksum matches the ZIP bytes and invalid versions fail without partial assets.
- [ ] Run the focused tests and observe the expected red failure before implementation.
- [ ] Implement the smallest Python standard-library wrapper around `git archive` plus SHA-256 generation.
- [ ] Run focused and full Python tests.
- [ ] Commit as `build: add reproducible harness release assets`.

### Task 2: Rebuild the repository landing page

**Files:**

- Modify: `README.md`
- Create: `README.zh-CN.md`

- [ ] Make English the canonical README and add reciprocal language links.
- [ ] Put badges, positioning, audience, 30-second install, capability list, minimal workflow, trust boundary, and “Why not just CI?” before the detailed reference.
- [ ] Preserve all existing migration, configuration, evidence, handoff, example, development, GitHub Check Run, security, and licensing content.
- [ ] Add identical `v0.1.1` macOS/Linux and PowerShell download instructions to both languages.
- [ ] Verify every local and release link and compare version/command strings across both files.
- [ ] Commit as `docs: add bilingual download-first readme`.

### Task 3: Prepare the release and launch materials

**Files:**

- Create: `docs/launch/2026-09-13-v0.1.1-launch-kit.md`

- [ ] Add English and Chinese short descriptions, medium posts, the CI distinction, three concrete use cases, direct links, MIT/runtime claims, and the security boundary.
- [ ] Add the exact bilingual GitHub Release body and a no-posting notice.
- [ ] Build `dist/minimal-harness-v0.1.1.zip` and `dist/SHA256SUMS.txt` from the fixed release commit.
- [ ] Inspect archive contents, verify the checksum, and smoke-test extraction in a fresh Git repository.
- [ ] Commit documentation as `docs: prepare v0.1.1 launch kit`; keep generated `dist/` artifacts untracked.

### Task 4: Publish and verify GitHub state

**Repository:** `2278091160dg-rgb/minimal-harness`

- [ ] Run the complete local verification matrix and review the full diff.
- [ ] Push `codex/github-download-growth`, open a PR, and require green CI before merge.
- [ ] Merge to `main`, tag the verified merge as `v0.1.1`, and create a new release without modifying `v0.1.0`.
- [ ] Upload the ZIP and checksum, then download and smoke-test the public assets.
- [ ] Set the approved description, latest-release homepage, and ten approved topics.
- [ ] Confirm the Releases API exposes both assets and record the ZIP download baseline after the single maintainer smoke test.

### Task 5: Schedule measurement checkpoints

- [ ] Create local, quiet checkpoints for days 7, 14, and 30 after publication.
- [ ] At each checkpoint read ZIP `download_count`, unique views, unique clones, referrers, and stars.
- [ ] Report only meaningful changes or a due checkpoint; do not add repository telemetry.
- [ ] Diagnose low traffic as distribution, high traffic/low downloads as landing-page conversion, and downloads without usage feedback as onboarding.

## Definition of Done

- The public repository has the approved metadata and bilingual download-first landing page.
- `v0.1.1` contains a working `.harness/` ZIP and matching SHA-256 file built from a fixed Git ref.
- Fresh extraction passes `doctor` and `status`; all existing local and CI gates stay green.
- External posts remain drafts only.
- A documented baseline and three time-bounded measurement checkpoints exist for the 30-download experiment.
