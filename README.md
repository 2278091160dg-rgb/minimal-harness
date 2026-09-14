# Minimal Harness

[![CI](https://github.com/2278091160dg-rgb/minimal-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/2278091160dg-rgb/minimal-harness/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/2278091160dg-rgb/minimal-harness)](https://github.com/2278091160dg-rgb/minimal-harness/releases)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A small, local acceptance and handoff tool for coding agents. Define what must work,
run the checks, retain evidence, and complete a task only while that evidence still
matches the current source and acceptance definition.

**Python 3.9+ standard library · Git · one writer · no model API or service**

[简体中文](README.zh-CN.md) · [Documentation](docs/README.md) ·
[First-time trial sheet](docs/adoption-validation.md)

## Choose the right version

| Version | Use it for | Scope |
| --- | --- | --- |
| [v0.2.0-beta.1](https://github.com/2278091160dg-rgb/minimal-harness/releases/tag/v0.2.0-beta.1) | Published schema v3 beta | Includes `init`, `task add/revise`, `report`, and source/contract freshness. Its ZIP does **not** contain a runtime `LICENSE` or the unreleased Git/runner hardening in this source revision. |
| Current source/PR | Evaluating this unreleased hardening revision | Fresh `init` and explicit upgrades copy `harness.py`, `harness_init.py`, `harness_runner.py`, and `.harness/LICENSE`. Source examples and the release checker are included. |
| [v0.1.1](https://github.com/2278091160dg-rgb/minimal-harness/releases/tag/v0.1.1) | Older stable workflow | Schema v2; no `init`, `task add/revise`, or `report`. Do not use the v3 command guide with it. |

This documentation describes schema v3. Use beta.1 to try its published behavior; use
the current source checkout when evaluating fixes in this PR.

## Install the published beta ZIP

These commands download the two real beta.1 assets, verify the archive, extract it into
a staging directory, and initialize an **existing** project. They never unpack over the
project's `.harness/` directory. Change only the final project path.

macOS or Linux:

```bash
(
set -eu
mh_version=v0.2.0-beta.1
mh_base="https://github.com/2278091160dg-rgb/minimal-harness/releases/download/$mh_version"
mh_stage="$(mktemp -d)"
curl -fL "$mh_base/minimal-harness-$mh_version.zip" -o "$mh_stage/minimal-harness-$mh_version.zip"
curl -fL "$mh_base/SHA256SUMS.txt" -o "$mh_stage/SHA256SUMS.txt"
if command -v sha256sum >/dev/null 2>&1; then
  (cd "$mh_stage" && sha256sum -c SHA256SUMS.txt)
else
  (cd "$mh_stage" && shasum -a 256 -c SHA256SUMS.txt)
fi
mkdir "$mh_stage/runtime"
python3 -m zipfile -e "$mh_stage/minimal-harness-$mh_version.zip" "$mh_stage/runtime"
python3 "$mh_stage/runtime/.harness/harness.py" --workspace /absolute/path/to/project init --agent codex
)
```

PowerShell:

```powershell
$ErrorActionPreference = "Stop"
$Version = "v0.2.0-beta.1"
$Base = "https://github.com/2278091160dg-rgb/minimal-harness/releases/download/$Version"
$Stage = Join-Path ([IO.Path]::GetTempPath()) ("minimal-harness-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Stage | Out-Null
$Zip = Join-Path $Stage "minimal-harness-$Version.zip"
$Sums = Join-Path $Stage "SHA256SUMS.txt"
Invoke-WebRequest "$Base/minimal-harness-$Version.zip" -OutFile $Zip
Invoke-WebRequest "$Base/SHA256SUMS.txt" -OutFile $Sums
$Expected = ((Get-Content $Sums | Where-Object { $_ -match "minimal-harness-$([regex]::Escape($Version))\.zip" }) -split '\s+')[0].ToLowerInvariant()
$Actual = (Get-FileHash $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Actual -ne $Expected) { throw "SHA-256 mismatch: expected $Expected, observed $Actual" }
$Runtime = Join-Path $Stage "runtime"
Expand-Archive -Path $Zip -DestinationPath $Runtime
py -3 "$Runtime/.harness/harness.py" --workspace "C:\path\to\project" init --agent codex
if ($LASTEXITCODE -ne 0) { throw "Minimal Harness init failed with exit $LASTEXITCODE" }
```

The verified beta.1 digest is
`f57b733a8eb4e62a05a0bf6ebcf66fc7972b9ec91dec47e1697252d5a1a81567`.
The downloaded `SHA256SUMS.txt` remains the file to check. The beta ZIP contains a staged
`.harness/` tree, not the examples and not `.harness/LICENSE`.

Use `--agent claude` for `CLAUDE.md`, `--agent generic` for generic `AGENTS.md`, or omit
`--agent` to install only the runtime. `init --dry-run` previews changes. Existing
instructions are preserved and a managed block is appended once. Partial installs,
symlinks, conflicting blocks, and a different installed runtime fail closed. `init`
does not upgrade state, initialize Git, or install dependencies.

## Try a complete source example

From a current source checkout, create a disposable project:

```bash
mkdir ../harness-demo
cp -R examples/quickstart/src examples/quickstart/tests examples/quickstart/greeting.task.json ../harness-demo/
python3 template/.harness/harness.py --workspace ../harness-demo init --agent codex
cd ../harness-demo
git init
python3 .harness/harness.py doctor
python3 .harness/harness.py task add --from greeting.task.json
python3 .harness/harness.py next
python3 .harness/harness.py verify
python3 .harness/harness.py report greeting
python3 .harness/harness.py complete greeting
python3 .harness/harness.py handoff
```

Expect `PASS: named and default greetings match the CLI contract`, a ready report,
`Completed greeting`, and an updated `.harness/HANDOFF.md`. Git does not need an initial
commit for this disposable example. The quickstart and Todo fixtures are source-only.

PowerShell preparation, followed by the same `doctor` through `handoff` commands with
`py -3`:

```powershell
New-Item -ItemType Directory ..\harness-demo | Out-Null
Copy-Item -Recurse examples\quickstart\src, examples\quickstart\tests, examples\quickstart\greeting.task.json ..\harness-demo\
py -3 template/.harness/harness.py --workspace ../harness-demo init --agent codex
Set-Location ..\harness-demo
git init
```

## Capability map

| Capability | Purpose | Command | Output or evidence | Boundary |
| --- | --- | --- | --- | --- |
| Initialize and connect an agent | Install runtime and optionally append instructions | `harness.py --workspace PATH init [--agent codex\|claude\|generic] [--dry-run]` | Runtime/config/task/handoff files; optional managed block | `--workspace` precedes the command; no upgrade, Git history, dependencies, or overwrite. |
| Add a task | Convert definition-only JSON into pending state | `task add --from SPEC.json` | Task state and refreshed handoff | `--from` is required; relative paths follow the caller's current directory. Runtime/evidence fields are rejected. |
| Select work | Freeze Git, policy, and acceptance baselines | `next` | First pending task becomes `in_progress` | One current task; a blocker stops selection. |
| Revise requirements | Deliberately replace a pending or active definition | `task revise ID --from SPEC.json --note TEXT` | Revision history and invalidated evidence | Same ID; unblock first; original Git/policy starting point remains frozen. |
| Run project helpers | Run configured setup, server, or project check | `run setup\|start\|check` | Setup/check logs under `.harness/attempts/runs/` | Not task acceptance. `start` stays attached; child commands may modify the workspace. |
| Command acceptance | Run all command checks for the current task | `verify [ID]` | Logs, attempts, evidence, state and handoff | Current `in_progress` task only. No browser/manual result. Drift makes the run unverified. |
| Browser acceptance | Record actions actually performed with a browser tool | `record ID CHECK --result ... --summary ... --tool TOOL --artifact FILE` | Attestation plus artifact metadata | A pass requires a real, non-symlink workspace artifact and tool. Harness does not launch a browser or prove the observation. Repeat `--artifact` for several files. |
| Manual acceptance | Record an observed manual result | `record ID CHECK --result ... --summary ... [--artifact FILE]` | Attestation and optional artifacts | Non-empty observation required; tool and attachments optional. |
| Freshness | Bind evidence to source, acceptance, branch, HEAD and index | `doctor`; `report ID`; `complete ID` | Stale warning or rejection | mtime alone is ignored; external services, ignored dependencies and environment changes are outside the guarantee. |
| Git scope | Audit changes against frozen `allowed_paths` | `report ID`; `complete ID` | Ready/issues and next command | Git required by default. Audit is a completion gate, not an OS sandbox. |
| Report and complete | Read-only preflight, then close a ready task | `report ID [--format text\|json\|markdown]`; `complete ID` | Stdout report; final state and handoff | A done-task report is historical, exits 1, and cannot authorize another completion. |
| Unblock | Resume after addressing repeated failures | `unblock ID --note TEXT` | Unblock history, reset counters, handoff | Current blocked task only; does not make a check pass. |
| Handoff | Regenerate cross-session summary | `handoff` | `.harness/HANDOFF.md` | Local write only; no upload or session creation. |
| Migration | Archive and convert v1/v2 state to v3 | `migrate [--dry-run] [--note TEXT]` | Migration archive, state, handoff | Active/blocked requires a note; unfinished old passes become unverified. |
| Optional GitHub | Publish a separate Check Run for trusted pushes | Copy `integrations/github/` adapter | GitHub Check Run | Requires credentials and `checks: write`; `run check` remains non-acceptance. |

## Configure before `next`

Edit `.harness/config.json` before selecting a task:

- `commands.setup/start/check` are `null` or non-empty argv arrays. No shell is used;
  `{python}` expands to the interpreter running Harness.
- `policy.allowed_paths` defaults to `src/**`, `tests/**`, and `.harness/**`. Add explicit
  patterns for root application files. `*` matches one segment; `**` crosses folders.
- `max_consecutive_failures` defaults to three. The policy freezes at `next`.
- `require_git_for_completion` defaults to `true`. Setting it to `false` permits
  completion when Git is unavailable; when Git is available, the captured Git identity
  remains part of source freshness.
- `approval_required_operations` are workflow instructions, not syscall interception.

A task input contains definitions only:

```json
{
  "id": "greeting",
  "title": "Greet a named user and support the default name",
  "acceptance": [{
    "id": "greeting-cli",
    "type": "command",
    "instruction": "The CLI greets Ada by name and world by default.",
    "command": ["{python}", "tests/check_greeting.py"],
    "timeout_seconds": 30
  }]
}
```

Command checks require `command`; browser/manual checks require non-empty `steps`. IDs
use 1–128 ASCII letters, digits, dots, underscores, or hyphens and begin with a letter
or digit. Do not hand-edit generated status, counters, baselines, or hashes.

## Evidence and recovery

`verify` invalidates previous command passes before the batch. Each command defaults to
300 seconds and 10 MiB of raw output; a positive finite `timeout_seconds` can override
time. Timeout and output-limit failures retain a bounded partial log. Interruption returns
130 and leaves acceptance unverified. `run check` creates no task acceptance.

For browser acceptance, perform every step with the browser tool and save a real artifact
under `.harness/artifacts/`. Only then record what was actually observed:

```bash
python3 .harness/harness.py record TASK_ID CHECK_ID --result passed \
  --summary "Opened the page, submitted Ada, and observed Hello, Ada!" \
  --tool playwright --artifact .harness/artifacts/greeting.png
```

Use `--result unverified` when the tool or observation is unavailable; it exits 1 and
completion stays closed. Browser/manual records are operator attestations. Harness checks
file existence and digest but does not independently prove the statement.

At `report` and `complete`, evidence must still match the contract and source snapshot.
The snapshot covers Git branch, HEAD, index, tracked and non-ignored files, plus clean,
initialized submodules recursively. Staging, committing, switching branches, editing
source, or revising acceptance after verification requires another verification. Dirty
or uninitialized submodules and hidden index flags fail closed. Harness-generated state,
attempts, evidence, reports, handoff, migrations, artifacts, legacy logs and runtime
`__pycache__` are excluded from application-source scope.

Task states are `pending / in_progress / blocked / done`; check states are
`not_run / passed / failed / unverified`. Unverified never means passed. Exit codes:
`0` success/ready, `1` failed acceptance or unmet/stale gate, `2` invalid usage/config or
damaged evidence, and `130` interruption.

## Upgrade explicitly to this unreleased revision

Back up the installed `.harness/` and stage the current source checkout away from the
project. Replace only these four runtime files; preserve configuration, tasks, evidence,
attempts, artifacts, handoff history, and agent instructions:

```bash
mh_source=/absolute/path/to/current/minimal-harness-checkout
mh_project=/absolute/path/to/project
mh_backup="$(mktemp -d)"
cp -R "$mh_project/.harness" "$mh_backup/.harness"
cp "$mh_source/template/.harness/harness.py" "$mh_project/.harness/harness.py"
cp "$mh_source/template/.harness/harness_init.py" "$mh_project/.harness/harness_init.py"
cp "$mh_source/template/.harness/harness_runner.py" "$mh_project/.harness/harness_runner.py"
cp "$mh_source/template/.harness/LICENSE" "$mh_project/.harness/LICENSE"
python3 "$mh_project/.harness/harness.py" --workspace "$mh_project" migrate --dry-run --note "Acknowledge the current acceptance definition for v3"
python3 "$mh_project/.harness/harness.py" --workspace "$mh_project" migrate --note "Acknowledge the current acceptance definition for v3"
```

PowerShell performs the same four-file replacement and keeps its backup outside the
project:

```powershell
$ErrorActionPreference = "Stop"
$Source = "C:\path\to\current\minimal-harness-checkout"
$Project = "C:\path\to\project"
$Backup = Join-Path ([IO.Path]::GetTempPath()) ("minimal-harness-backup-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Backup | Out-Null
Copy-Item -Recurse (Join-Path $Project ".harness") (Join-Path $Backup ".harness")
Copy-Item -Force (Join-Path $Source "template\.harness\harness.py") (Join-Path $Project ".harness\harness.py")
Copy-Item -Force (Join-Path $Source "template\.harness\harness_init.py") (Join-Path $Project ".harness\harness_init.py")
Copy-Item -Force (Join-Path $Source "template\.harness\harness_runner.py") (Join-Path $Project ".harness\harness_runner.py")
Copy-Item -Force (Join-Path $Source "template\.harness\LICENSE") (Join-Path $Project ".harness\LICENSE")
py -3 (Join-Path $Project ".harness\harness.py") --workspace $Project migrate --dry-run --note "Acknowledge the current acceptance definition for v3"
if ($LASTEXITCODE -ne 0) { throw "Minimal Harness migration preview failed with exit $LASTEXITCODE" }
py -3 (Join-Path $Project ".harness\harness.py") --workspace $Project migrate --note "Acknowledge the current acceptance definition for v3"
if ($LASTEXITCODE -ne 0) { throw "Minimal Harness migration failed with exit $LASTEXITCODE" }
```

The runtime license does not alter the project's root license. The published beta.1 ZIP
cannot supply `.harness/LICENSE`; obtain all four files from the same current revision.
For an older ref without `template/.harness/LICENSE`, use that same ref's root `LICENSE`
only if intentionally staying on that ref.

Migration archives v1/v2 state first. Unfinished old passes must reverify; completed old
tasks remain historical. v2 Git/policy baselines and blockers survive. Active/blocked v1
tasks get new baselines while retaining their old baselines in history. Repeating the
migration on v3 reports that it is already v3.

## Trust and optional GitHub adapter

Minimal Harness is not an OS sandbox, authorization service, signature system,
concurrency protocol, or independent anti-forgery service. A process able to rewrite the
repository and Harness state can bypass it. One writer is supported. The runtime never
calls a model, sends telemetry, commits, pushes, publishes, or uploads evidence.

After configuring `commands.check`, the optional example copies
`integrations/github/minimal-harness-check.yml` to `.github/workflows/` and keeps
`integrations/github/publish_check.py` at the same project path. It publishes only for a
trusted `push` with `checks: write`; pull requests run local checks without publication.
It requires `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, and a full `GITHUB_SHA`.

## Continue reading

- [Practical usage guide](docs/usage-guide.md)
- [Complete CLI reference](docs/cli-reference.md)
- [Documentation index](docs/README.md)
- [First-time human trial sheet](docs/adoption-validation.md) — pending real users
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [MIT License](LICENSE)
