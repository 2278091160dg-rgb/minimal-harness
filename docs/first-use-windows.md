# Windows: a 15-minute first successful run

[简体中文](first-use-windows.zh-CN.md) · [Choose another system](../START-HERE.md)

This page is written for Minimal Harness `v0.2.0-beta.2`. Open PowerShell on Windows
10 or 11. Do not use Command Prompt, Git Bash, or WSL. Copy only the current code block.
Do not run these commands in a production project or read the full README first.

## 1. Check whether this computer is ready

Run:

```powershell
py -3 --version
git --version
```

Continue only if you see Python `3.9` or newer and a Git version line. If a command is not
recognized, Python is older, or another error appears, stop and send the exact text to the
person who invited you. This page does not install system dependencies.

Then run:

```powershell
Test-Path "$HOME\minimal-harness-first-use-source"
Test-Path "$HOME\harness-demo"
```

You must see two `False` values. If either value is `True`, stop. Do not delete an existing
directory. Record your start time now.

## 2. Create a disposable demo

Paste the whole block into PowerShell:

```powershell
Set-Location $HOME
git clone --branch v0.2.0-beta.2 --depth 1 https://github.com/denggui-ai/minimal-harness.git minimal-harness-first-use-source
New-Item -ItemType Directory -Path "$HOME\harness-demo" | Out-Null
Copy-Item -Recurse -Path "$HOME\minimal-harness-first-use-source\examples\quickstart\src","$HOME\minimal-harness-first-use-source\examples\quickstart\tests","$HOME\minimal-harness-first-use-source\examples\quickstart\greeting.task.json" -Destination "$HOME\harness-demo"
py -3 "$HOME\minimal-harness-first-use-source\template\.harness\harness.py" --workspace "$HOME\harness-demo" init --agent generic
Set-Location "$HOME\harness-demo"
git init
```

The last output should confirm Git initialization. Stop and retain the last 20 PowerShell
lines if any command reports an error.

## 3. Reach the first acceptance pass

Run these commands in order:

```powershell
py -3 .harness\harness.py doctor
py -3 .harness\harness.py task add --from greeting.task.json
py -3 .harness\harness.py next
py -3 .harness\harness.py verify greeting
```

Find this line:

```text
PASS: named and default greetings match the CLI contract
```

Stop if you do not see `PASS`. If you see it, do not run `complete` yet.

## 4. Observe one change

Run these two commands. The second may return a nonzero status; that is the observation
for this step, so do not close PowerShell.

```powershell
py -3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hello', 'Hi'), encoding='utf-8')"
py -3 .harness\harness.py report greeting
```

Pause and answer in your own words: **It already passed. Why can it not complete now?**

Do not search for the answer or ask an AI to explain it. Record your own answer first.

## 5. Restore and complete

```powershell
py -3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hi', 'Hello'), encoding='utf-8')"
py -3 .harness\harness.py verify greeting
py -3 .harness\harness.py report greeting
py -3 .harness\harness.py complete greeting
py -3 .harness\harness.py handoff
Get-Content .harness\HANDOFF.md
```

You should again see `PASS`, a report containing `ready`, and `Completed greeting`.
After reading the handoff, write one sentence: **What should a new session do first?**
Record the finish time. Stage 1 is complete.

## 6. Optional: use a copy of your own project

Use only a disposable copy of an existing Git project that already has a working test
command. That command should leave `git status` unchanged after it runs. Enter the copied
project in PowerShell. Run `Get-Location` and `git status` to confirm that you are in the
copy and Git is available.

From the copied project root, paste this installation block:

```powershell
$ErrorActionPreference = "Stop"
$Project = (Get-Location).Path
$Version = "v0.2.0-beta.2"
$Base = "https://github.com/denggui-ai/minimal-harness/releases/download/$Version"
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
py -3 "$Runtime\.harness\harness.py" --workspace $Project init --agent generic
if ($LASTEXITCODE -ne 0) { throw "Minimal Harness init failed with exit $LASTEXITCODE" }
py -3 .harness\harness.py doctor
```

Run `notepad first-task.json`. For a Python project normally tested with
`py -3 -m unittest discover`, paste:

```json
{
  "id": "first-check",
  "title": "Existing Python tests stay green",
  "acceptance": [{
    "id": "project-tests",
    "type": "command",
    "instruction": "Run the existing Python unittest suite.",
    "command": ["{python}", "-B", "-m", "unittest", "discover"],
    "timeout_seconds": 300
  }]
}
```

For a Node project normally tested with `npm test`, paste instead:

```json
{
  "id": "first-check",
  "title": "Existing Node tests stay green",
  "acceptance": [{
    "id": "project-tests",
    "type": "command",
    "instruction": "Run the existing npm test suite.",
    "command": ["npm", "test"],
    "timeout_seconds": 300
  }]
}
```

Save and close Notepad, then run:

```powershell
py -3 .harness\harness.py task add --from first-task.json
py -3 .harness\harness.py next
py -3 .harness\harness.py verify first-check
py -3 .harness\harness.py report first-check
py -3 .harness\harness.py complete first-check
py -3 .harness\harness.py handoff
```

If the project uses another test system, has no existing test command, or any step fails,
stop and record why. Do not edit `.harness/` state files to make it pass.

## 7. Send these six answers to the inviter

1. Windows version, `py -3 --version`, `git --version`, and the English page used.
2. Time from the start until the fixed demo completed.
3. The first unclear or blocked step, with the last 20 PowerShell lines.
4. Your own explanation of why completion was refused after a pass.
5. Whether you tried a project copy, the result, and whether you needed help.
6. Whether you would use it again in a real project, in your own words.

Do not send secrets, private source code, or screenshots without consent.
