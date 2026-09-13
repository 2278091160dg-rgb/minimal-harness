# Evidence Freshness and Release Design

Date: 2026-09-13
Status: approved direction, implementation pending

## Objective

Close the remaining fail-open between a passed acceptance check and later code changes, then prepare Minimal Harness for an MIT-licensed public release and an optional GitHub API integration.

The product remains a dependency-free Python 3.9+ acceptance kernel. It does not become a prompt-only Codex Skill, an agent orchestrator, or a GitHub-only tool.

## Decisions

### Evidence schema versioning

Evidence receives its own `EVIDENCE_SCHEMA_VERSION = 3`. Configuration, task state, policy, and Git baseline remain schema v2.

Rejected alternatives:

- Adding optional freshness fields to evidence v2 would silently change the meaning of an existing immutable format.
- Upgrading every state document to v3 would require unrelated task/config migration and enlarge the failure surface.

Existing evidence files are never rewritten. For unfinished tasks, a passed v2 evidence reference is not fresh enough for completion and must be replaced by a new verification. Evidence retained by already completed legacy tasks remains readable and is explicitly labelled legacy.

### Completion semantics

Freshness failures are read-only observations. `doctor`, `handoff`, and `complete` never silently edit task or acceptance status.

- `complete` rejects stale passed evidence with exit code 1.
- `doctor` reports stale evidence as a gate failure with exit code 1.
- `handoff` emits a warning and omits the stale summary from trusted results.
- A malformed or hash-tampered evidence document remains a configuration/integrity error with exit code 2.
- Re-running `verify` or `record` is the only way to replace the current evidence reference.

When the frozen task policy has `require_git_for_completion: false`, completion may proceed without Git freshness proof. Evidence and handoff output must state that the result is not Git-bound by policy. The default remains `true`.

## Freshness subject

Every v3 evidence document records a `verification_subject` v2 captured after the acceptance action finishes and its artifacts are validated, but before Harness writes evidence or task state.

The subject records:

- subject schema and capture time;
- Git availability;
- repository-relative workspace prefix, without embedding an absolute machine path;
- branch, HEAD, and unborn state;
- dirty worktree fingerprints;
- staged index blob/stage fingerprints.
- complete tracked-file fingerprints, including paths hidden by `assume-unchanged` or `skip-worktree`;
- complete ignored-file fingerprints;
- non-ignored submodule status.

The snapshot excludes only Harness-generated mutable state:

- `.harness/tasks.json`;
- `.harness/evidence/**`;
- `.harness/logs/**`;
- `.harness/HANDOFF.md`;
- `.harness/migrations/**`.

It does not exclude `.harness/harness.py`, `.harness/config.json`, adapters, ordinary project files, or user-supplied artifacts outside generated state. Changing the verifier or its policy after a pass therefore makes the evidence stale.

Freshness validation compares the recorded subject with a new fail-closed Git snapshot. It directly compares HEAD even when the final tree is unchanged, and detects branch changes, committed changes, additions, modifications, deletions, renames, staged changes, unstaged changes, ignored changes, index-suppressed changes, dirty submodules, file type changes, and changes to files that were already dirty when verification ran.

The earlier verification subject v1 remains structurally readable. It cannot prove the complete tracked/ignored manifest, so active passed evidence using subject v1 is stale and requires re-verification; completed evidence using subject v1 is retained and labelled legacy. Displayed Git paths escape terminal controls and Markdown structure without changing the raw paths used for comparison.

Harness-generated state cannot invalidate the evidence that created it, avoiding a self-referential hash cycle.

## Validation flow

```text
acceptance action succeeds
        |
artifact/log validation
        |
capture Git verification subject
        |
write immutable evidence v3 + update task reference
        |
doctor / handoff / complete
        |
re-hash evidence, log and artifacts
        |
compare current Git subject with verification subject
        |
trusted / stale / malformed
```

The same validator serves all three consumers so they cannot disagree about freshness. Error messages list changed paths when Git can determine them, but never present an unverified acceptance summary as trusted.

## Compatibility and migration

No task/config migration command is required for this change.

- New `verify` and `record` operations emit evidence v3.
- Active v2 passed evidence fails the freshness gate and gives a re-verification command.
- Failed and unverified historical evidence remains inspectable.
- Completed v1/v2 legacy records remain completed; `doctor` labels them instead of retroactively reopening history.
- Repeated verification creates a new evidence file using existing unique-create semantics.

## GitHub integration boundary

The GitHub integration is optional and lives outside the runtime template core. It reads Harness output and uses GitHub's API to publish a check result for a commit or pull request.

Its first release supports:

- running `doctor` and the configured project check in CI;
- publishing a concise pass/fail/blocked Check Run through the GitHub REST API;
- reporting trusted evidence paths and hashes without embedding untrusted summaries;
- least-privilege workflow permissions (`contents: read`, `checks: write` only where publication is trusted).

Forked pull requests do not receive a write-capable token. The publisher is tested with a local mock HTTP server; tests never mutate a real repository.

The integration does not move GitHub API code into `.harness/harness.py` and does not add a runtime dependency.

## License and release

The project uses the MIT License because its primary distribution model is copying a small template into other repositories. The license holder is recorded as `denggui` for 2026 unless the owner requests a different legal attribution before release.

Release readiness includes:

- root `LICENSE`;
- concise English project description and repository topics;
- `SECURITY.md` and `CONTRIBUTING.md`;
- documented security boundary and non-goals;
- green Python, Node, lint, doctor, Todo, and browser acceptance checks;
- a clean public-history inspection before changing repository visibility;
- an initial semantic version tag and GitHub release only after all gates pass.

Publishing the repository and creating a GitHub release are external visibility changes. They happen only after the implementation and release preflight are complete. Applying to the GitHub Developer Program is a later account action because the official application also needs a support email; no email address is inferred or published automatically.

## Skill boundary

No Codex Skill is created in this project. The CLI remains the product. The landscape-audit workflow remains a Markdown template until it has been repeated on three distinct projects with comparative regression evidence.

## Testing strategy

Implementation follows test-driven development. Regression coverage must include:

- code changed after a command/browser/manual pass;
- staged, unstaged, committed, renamed, deleted, and pre-dirty changes after verification;
- branch switching and unborn repositories;
- generated Harness state not self-invalidating evidence;
- modified `.harness/config.json` or `.harness/harness.py` invalidating evidence;
- active v2 evidence requiring re-verification;
- completed legacy evidence remaining readable;
- `require_git_for_completion: false` warning without a Git gate;
- consistent doctor, handoff, and complete results;
- malformed subject versus stale subject exit-code separation;
- mocked GitHub Check Run requests, permission failures, invalid JSON, non-UTF-8 output, and network failures.

## Acceptance criteria

- Any unapproved code change after passed evidence blocks completion when Git is required.
- Evidence files, logs, artifacts, and verification subjects are all validated from one code path.
- Existing v1/v2 evidence is never rewritten.
- Python 3.9+ standard-library runtime remains intact.
- The optional GitHub adapter has no effect on local CLI users.
- All repository test and lint gates pass on supported platforms.
- The repository is not made public and no program application is submitted until release preflight and support-contact requirements are satisfied.
