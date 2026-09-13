# GitHub Developer Program Readiness — 2026-09-13

## Decision

**Minimal Harness is a credible GitHub Developer Program candidate, but the application should not be submitted yet.**

GitHub states that individual developers and companies may join when they have both:

1. an integration in production or development that uses the GitHub API; and
2. an email address where GitHub users can obtain support.

Source: [GitHub Developer Program](https://docs.github.com/en/integrations/concepts/github-developer-program).

This repository now has an optional Check Runs REST API adapter in development, so the technical integration criterion is substantially met. The maintainer has authorized `2278091160@qq.com` as the public support address. Submission still waits for a public project and release.

## Current readiness snapshot

| Area | Status | Evidence / action |
| --- | --- | --- |
| Product position | Ready | Minimal, dependency-free, fail-closed completion proof layer for coding agents. |
| GitHub API integration | Ready in development | `integrations/github/publish_check.py` publishes a completed Check Run. |
| Least-privilege workflow | Ready locally | Pull requests verify with read-only contents access; Check Run publishing is isolated to trusted pushes with `checks: write`. |
| Automated regression tests | Ready locally | Success, API failure, invalid JSON, network failure, non-UTF-8 error, and redirect credential-leak cases are covered. |
| Public project | Blocked | The GitHub repository is private as of this snapshot. |
| Support channel | Ready | The maintainer authorized `2278091160@qq.com` as the public support address. |
| Release identity/privacy | Accepted | The maintainer explicitly accepted public visibility of the same address in reachable Git history. No history rewrite is required. |
| CI proof | Ready | PR #1 and the merged `main` commit passed Linux, macOS, Windows, Python 3.9/current, Node, Ruff, doctor, Todo, and real Chromium checks. |
| Release | Pending | No GitHub release exists; the MIT license is present on the private default branch. |

## Integration assessment

The adapter uses the Check Runs API, which is a meaningful product integration rather than a documentation-only GitHub mention. GitHub documents Check Runs as a GitHub App capability for reporting CI and code-analysis results. Creating a Check Run requires Checks write permission. Sources: [using the REST API for checks](https://docs.github.com/en/rest/guides/using-the-rest-api-to-interact-with-checks) and [Check Run endpoints](https://docs.github.com/en/rest/checks/runs).

The included workflow follows the relevant trust boundary: GitHub reduces forked pull-request tokens to read-only in the normal case, so untrusted PR code must not receive a write-capable token. Source: [GitHub Actions workflow permissions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#changing-the-permissions-in-a-forked-repository).

For the first release, GitHub Actions' repository-scoped `GITHUB_TOKEN` is sufficient for a trusted push job because it is an installation token issued by the GitHub Actions GitHub App. A separately registered GitHub App becomes worthwhile only if Minimal Harness later needs cross-repository installation, webhooks, re-run buttons, or a hosted service. Source: [`GITHUB_TOKEN` security model](https://docs.github.com/en/actions/concepts/security/github_token).

## Recommended application sequence

1. Make the repository public only after the owner explicitly approves the visibility change.
2. Verify the MIT license and security documentation render correctly, then create a minimal tagged release.
3. Submit the Developer Program application with the public repository, API integration description, support address, and release link.

## What not to claim

- Developer Program membership is not yet obtained.
- This readiness assessment is not an application submission.
- The optional Actions adapter is not yet a generally installable GitHub App.
- No funding, accelerator admission, marketplace listing, or endorsement is implied by Developer Program eligibility.

## Final recommendation

Email/privacy and CI gates are resolved. Defer public release and Developer Program submission until the owner explicitly authorizes changing repository visibility.
