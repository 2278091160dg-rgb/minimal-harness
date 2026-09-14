$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$TrialRoot = Join-Path $env:RUNNER_TEMP ("minimal-harness-first-use-" + [guid]::NewGuid())
$Source = Join-Path $TrialRoot "minimal-harness-first-use-source"
$Demo = Join-Path $TrialRoot "harness-demo"

New-Item -ItemType Directory -Path $TrialRoot | Out-Null
git clone --branch v0.2.0-beta.2 --depth 1 https://github.com/2278091160dg-rgb/minimal-harness.git $Source
if ($LASTEXITCODE -ne 0) { throw "Unable to clone the fixed release tag" }

New-Item -ItemType Directory -Path $Demo | Out-Null
Copy-Item -Recurse -Path "$Source\examples\quickstart\src","$Source\examples\quickstart\tests","$Source\examples\quickstart\greeting.task.json" -Destination $Demo
py -3 "$Source\template\.harness\harness.py" --workspace $Demo init --agent generic
if ($LASTEXITCODE -ne 0) { throw "Minimal Harness init failed" }

Set-Location $Demo
git init
if ($LASTEXITCODE -ne 0) { throw "git init failed" }

py -3 .harness\harness.py doctor
if ($LASTEXITCODE -ne 0) { throw "doctor failed" }
py -3 .harness\harness.py task add --from greeting.task.json
if ($LASTEXITCODE -ne 0) { throw "task add failed" }
py -3 .harness\harness.py next
if ($LASTEXITCODE -ne 0) { throw "next failed" }
$VerifyOutput = py -3 .harness\harness.py verify greeting 2>&1
$VerifyOutput | Write-Output
if ($LASTEXITCODE -ne 0) { throw "initial verification failed" }
if (($VerifyOutput -join "`n") -notmatch "PASS: named and default greetings match the CLI contract") {
    throw "expected PASS marker is missing"
}

py -3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hello', 'Hi'), encoding='utf-8')"
if ($LASTEXITCODE -ne 0) { throw "unable to change demo source" }
$StaleOutput = py -3 .harness\harness.py report greeting 2>&1
$StaleStatus = $LASTEXITCODE
$StaleOutput | Write-Output
if ($StaleStatus -ne 1) { throw "stale report returned $StaleStatus instead of 1" }
if (($StaleOutput -join "`n") -notmatch "stale evidence") { throw "stale diagnostic is missing" }

py -3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hi', 'Hello'), encoding='utf-8')"
if ($LASTEXITCODE -ne 0) { throw "unable to restore demo source" }
py -3 .harness\harness.py verify greeting
if ($LASTEXITCODE -ne 0) { throw "verification after restore failed" }
py -3 .harness\harness.py report greeting
if ($LASTEXITCODE -ne 0) { throw "ready report failed" }
py -3 .harness\harness.py complete greeting
if ($LASTEXITCODE -ne 0) { throw "completion failed" }
py -3 .harness\harness.py handoff
if ($LASTEXITCODE -ne 0) { throw "handoff failed" }
if (-not (Test-Path .harness\HANDOFF.md -PathType Leaf)) { throw "handoff file is missing" }

$Project = Join-Path $TrialRoot "release-project"
New-Item -ItemType Directory -Path $Project | Out-Null
Set-Location $Project
git init
if ($LASTEXITCODE -ne 0) { throw "release project git init failed" }

$Version = "v0.2.0-beta.2"
$Base = "https://github.com/2278091160dg-rgb/minimal-harness/releases/download/$Version"
$Stage = Join-Path $TrialRoot "release-stage"
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
if ($LASTEXITCODE -ne 0) { throw "release init failed" }
py -3 .harness\harness.py doctor
if ($LASTEXITCODE -ne 0) { throw "release doctor failed" }

Write-Output "DOC_WINDOWS_FLOW_OK stale_status=$StaleStatus"
