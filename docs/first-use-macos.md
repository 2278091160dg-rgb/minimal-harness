# macOS: a 15-minute first successful run

[简体中文](first-use-macos.zh-CN.md) · [Choose another system](../START-HERE.md)

This page is written for Minimal Harness `v0.2.0-beta.2`. Open Terminal on macOS and
copy only the current code block. Do not run these commands in a production project or
read the full README before the trial.

## 1. Check whether this computer is ready

Run:

```bash
python3 --version
git --version
```

Continue only if you see Python `3.9` or newer and a Git version line. If you see
`command not found`, an older Python version, or another error, stop and send the exact
text to the person who invited you. This page does not install system dependencies.

Then run:

```bash
test ! -e "$HOME/minimal-harness-first-use-source" && echo "source path ready"
test ! -e "$HOME/harness-demo" && echo "demo path ready"
```

You must see both `source path ready` and `demo path ready`. If either is missing, stop.
Do not delete an existing directory. Record your start time now.

## 2. Create a disposable demo

Paste the whole block into Terminal:

```bash
cd "$HOME"
git clone --branch v0.2.0-beta.2 --depth 1 https://github.com/2278091160dg-rgb/minimal-harness.git minimal-harness-first-use-source
mkdir harness-demo
cp -R minimal-harness-first-use-source/examples/quickstart/src minimal-harness-first-use-source/examples/quickstart/tests minimal-harness-first-use-source/examples/quickstart/greeting.task.json harness-demo/
python3 minimal-harness-first-use-source/template/.harness/harness.py --workspace "$HOME/harness-demo" init --agent generic
cd "$HOME/harness-demo"
git init
```

The last output should confirm Git initialization. Stop and retain the last 20 terminal
lines if any command reports an error.

## 3. Reach the first acceptance pass

Run these commands in order:

```bash
python3 .harness/harness.py doctor
python3 .harness/harness.py task add --from greeting.task.json
python3 .harness/harness.py next
python3 .harness/harness.py verify greeting
```

Find this line:

```text
PASS: named and default greetings match the CLI contract
```

Stop if you do not see `PASS`. If you see it, do not run `complete` yet.

## 4. Observe one change

Run these two commands. The second may return a nonzero status; that is the observation
for this step, so do not close Terminal.

```bash
python3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hello', 'Hi'), encoding='utf-8')"
python3 .harness/harness.py report greeting
```

Pause and answer in your own words: **It already passed. Why can it not complete now?**

Do not search for the answer or ask an AI to explain it. Record your own answer first.

## 5. Restore and complete

```bash
python3 -c "from pathlib import Path; p=Path('src/greet.py'); p.write_text(p.read_text(encoding='utf-8').replace('Hi', 'Hello'), encoding='utf-8')"
python3 .harness/harness.py verify greeting
python3 .harness/harness.py report greeting
python3 .harness/harness.py complete greeting
python3 .harness/harness.py handoff
sed -n '1,160p' .harness/HANDOFF.md
```

You should again see `PASS`, a report containing `ready`, and `Completed greeting`.
After reading the handoff, write one sentence: **What should a new session do first?**
Record the finish time. Stage 1 is complete.

## 6. Optional: use a copy of your own project

Use only a disposable copy of an existing Git project that already has a working test
command. That command should leave `git status` unchanged after it runs. Enter the copied
project in Terminal. Run `pwd` and `git status` to confirm that you are in the copy and Git
is available.

From the copied project root, paste this installation block:

```bash
(
set -eu
mh_project="$PWD"
mh_version=v0.2.0-beta.2
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
python3 "$mh_stage/runtime/.harness/harness.py" --workspace "$mh_project" init --agent generic
)
python3 .harness/harness.py doctor
```

Create a task file:

```bash
touch first-task.json
open -e first-task.json
```

For a Python project normally tested with `python3 -m unittest discover`, paste:

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

Save and close TextEdit, then run:

```bash
python3 .harness/harness.py task add --from first-task.json
python3 .harness/harness.py next
python3 .harness/harness.py verify first-check
python3 .harness/harness.py report first-check
python3 .harness/harness.py complete first-check
python3 .harness/harness.py handoff
```

If the project uses another test system, has no existing test command, or any step fails,
stop and record why. Do not edit `.harness/` state files to make it pass.

## 7. Send these six answers to the inviter

1. macOS version, `python3 --version`, `git --version`, and the English page used.
2. Time from the start until the fixed demo completed.
3. The first unclear or blocked step, with the last 20 terminal lines.
4. Your own explanation of why completion was refused after a pass.
5. Whether you tried a project copy, the result, and whether you needed help.
6. Whether you would use it again in a real project, in your own words.

Do not send secrets, private source code, or screenshots without consent.
