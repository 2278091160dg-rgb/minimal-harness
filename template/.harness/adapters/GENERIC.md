# Minimal Harness instructions

Before changing code:

1. Run `python3 .harness/harness.py doctor`.
2. Run `python3 .harness/harness.py status` and read `.harness/HANDOFF.md`.
3. Resume a task that is `in_progress`. If it is `blocked`, report the blocker and obtain the needed intervention, then use `unblock` before mutating the project. Run `python3 .harness/harness.py next` only when status shows no active or blocked task.
4. Work on only the current task and only inside `policy.allowed_paths`.

Keep one writer in the shared workspace. Use `verify` for command checks. Actually perform browser and manual checks before using `record`; code inspection or an unavailable tool is not proof. Run `complete` only after every acceptance item and policy gate passes. Changes made after verification require fresh evidence.

Respect operations listed in `policy.approval_required_operations`, while preserving authorization the user already granted instead of asking twice. After three consecutive failures on one check, leave the task blocked with its logs intact. At every stopping or transfer point, run `python3 .harness/harness.py handoff` before another writer takes over.
