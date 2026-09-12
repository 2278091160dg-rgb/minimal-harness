# Harness Handoff

This is the schema v2 bootstrap for the Todo example. It does not contain a Git snapshot yet.

Run from `examples/todo`:

```bash
python3 .harness/harness.py doctor
python3 .harness/harness.py status
python3 .harness/harness.py handoff
```

After `handoff`, this file becomes the generated cross-session view of task, evidence, Git, and next-action state. Its working-tree section explicitly excludes `.harness/HANDOFF.md` itself.
