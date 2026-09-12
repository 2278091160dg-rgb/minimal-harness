# Minimal Harness instructions

Before changing code:

1. Run `python3 .harness/harness.py doctor`.
2. Run `python3 .harness/harness.py status` and read `.harness/HANDOFF.md`.
3. If there is no active task, run `python3 .harness/harness.py next`.
4. Work on only the current task and only inside `policy.allowed_paths`.

Use `verify` for command checks. Use `record` for browser or manual checks. Never mark a task complete from code inspection alone. `unverified` is not a passing result.

Stop and ask the user before any operation listed in `policy.approval_required_operations`. After three consecutive failures on one check, leave the task blocked with its logs intact. End every work round by running `python3 .harness/harness.py handoff`.
