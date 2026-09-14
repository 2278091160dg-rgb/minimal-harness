# Hardening and bilingual documentation validation

Engineering validation for the [approved plan](../plans/2026-09-14-hardening-bilingual-docs.md).
Initial implementation evaluated at `1bd5bc11da761c3629cf42d087906bc4f49e0578`, based on
`28dc64d1a013983373079301afce922d117dc4bf`.

## Local results

| Check | Result |
| --- | --- |
| Full Python 3.9 suite, ResourceWarning treated as error | 229 passed |
| Full Python 3.14 suite, ResourceWarning treated as error | 229 passed |
| Todo Node tests and configured `run check` | 3 passed in each invocation |
| Ruff | Passed |
| `doctor` for the template and Todo example | Passed |
| Real Chromium Todo walkthrough | Add, toggle and reload persistence passed; all three tasks completed with real screenshot evidence |
| Fixed-commit ZIP lifecycle | Build, checksum, extract, init, verify, all report formats, stale-source rejection, reverify, complete and handoff passed |
| English and Chinese README workflows | Both source examples and real beta.1 download/checksum/install/lifecycle examples passed |
| English and Chinese usage-guide definitions | Regression/revision, browser-unavailable rejection and blocked recovery flows passed |
| User-documentation links and structure | 14 pages, 83 relative links checked; tables, fences and task JSON checked |

The checked development ZIP, labeled `v0.0.0-ci` solely for validation, has SHA-256
`380dd354bd9d5e43a195d5f220bf57afc400ef412e36114d93a5e11b57911c7c`.
It is a local test artifact, not a published version. Its source commit is recorded
above; changes outside the runtime do not silently replace its source.

The real published beta.1 ZIP was independently downloaded through both README
installation routes and matched its published checksum. It does not contain the
new runtime license or this branch's hardening fixes.

## Regression and review evidence

- Hidden Git flags: failing cases were established before the fix. Coverage now
  includes both flags, their combination, pre-selection and post-verification
  mutation, mutation during a check, repeat verification, nested workspaces,
  submodules and explicit recovery without automatic flag clearing.
- Interruption: the former condition-lock failure was reproduced before changing
  the polling primitive. Real child/descendant cleanup, return code 130 and raw
  partial-log preservation remain covered. Full validation additionally exposed
  a Darwin exited-but-unreaped process-group race; a real failing regression now
  covers reap-and-retry, while genuine permission errors remain errors.
- Distribution: scoped review caught and resolved CRLF fixture handling,
  diagnostics skipped after earlier CI failure, and unbounded Git reads. The
  historical-license and archive tests read committed objects and retain old
  runtime module layouts.
- Documentation: independent review checked parser behavior, bilingual parity,
  version claims and recovery steps. The interruption guide was corrected to
  account for captured output being displayed only after the child stops.

All three component reviews approved the final scoped changes after corrections.
An independent whole-branch review of `28dc64d..1bd5bc1` also approved the integrated
implementation with no remaining actionable findings.

## Hosted CI follow-up: relative output directories

The first hosted run passed all unit tests, including native Windows interruption
coverage. Its standalone release check exposed a Windows Python 3.9 path issue:
resolving a nonexistent relative output directory could leave it relative, so
changing the child working directory duplicated that path. The uploaded synthetic
diagnostic artifact retained the exact failed command and working directory.
See the [failed release-check job](https://github.com/2278091160dg-rgb/minimal-harness/actions/runs/34797935444/job/103834569490)
and the matching [CPython pathlib issue](https://github.com/python/cpython/issues/82852).

The follow-up converts the output path to an absolute path with `os.path.abspath`
before resolving it. Two regressions cover the old resolution behavior and a real
CLI invocation from outside the repository using a relative output directory. The
latter still exercises the complete build/install/acceptance/handoff lifecycle.
The OS/Python matrix, interruption assertions and release checks remain enabled.
The follow-up passed independent review, Ruff and complete strict ResourceWarning
suites: **231 tests passed on Python 3.9 and 231 on Python 3.14**. Hosted results
for the corrected revision are attached to the PR's latest commit.

## Reproduce

Run from a source checkout with Python 3.9+ and Node installed:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -W error::ResourceWarning -m unittest discover -s tests -v
node --test examples/todo/test.mjs
ruff check --no-cache template/.harness integrations/github/publish_check.py scripts tests examples/quickstart
python3 template/.harness/harness.py --workspace template doctor
python3 template/.harness/harness.py --workspace examples/todo doctor
python3 template/.harness/harness.py --workspace examples/todo run check
python3 scripts/check_release.py --ref 1bd5bc11da761c3629cf42d087906bc4f49e0578 --version v0.0.0-ci --output-dir /tmp/harness-release-validation
python3 tests/run_todo_walkthrough.py
```

Use a fresh release-check output directory. Chromium validation additionally needs
the development-only Playwright package and Chromium installed, with port 8000
available. See the [contributor guide](../../../CONTRIBUTING.md).

## Limits and hosted validation

PowerShell installation commands were reviewed but not executed on the local
macOS host. Hosted CI executes the Python suite and real release lifecycle on
Linux, macOS and Windows, with Python 3.9 and the current Python version, plus
Chromium on Linux. The PR's latest-commit check results are the authority for
those hosted runs; local macOS results do not establish native Windows success.

Three first-time human participants are still required. Automated command/browser
workflows and engineering inspection do not substitute for those trials. The
[English](../../adoption-validation.md) and [Chinese](../../adoption-validation.zh-CN.md)
trial worksheets remain pending. This work creates a PR only; it does not merge
the branch, tag a version or publish a release.
