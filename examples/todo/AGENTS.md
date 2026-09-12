# Todo example Agent instructions

Before changing this example:

1. Run `python3 .harness/harness.py doctor`.
2. Run `python3 .harness/harness.py status` and read `.harness/HANDOFF.md`.
3. If there is no active task, run `python3 .harness/harness.py next`.
4. Work on only the current task and only inside `policy.allowed_paths`.

Use `python3 .harness/harness.py run check` for the project check. Start the page with `python3 .harness/harness.py run start`. Browser acceptance must follow the steps in the current task and be recorded with `record`; code inspection alone is not evidence, and `unverified` is not a passing result.

Stop and ask the user before any operation listed in `policy.approval_required_operations`. After three consecutive failures on one check, leave the task blocked with its evidence intact. End every work round with `python3 .harness/harness.py handoff`.
