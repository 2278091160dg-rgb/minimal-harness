# Harness Handoff

This is a schema v2 bootstrap file. It does not contain a Git snapshot yet.

Run:

```bash
python3 .harness/harness.py doctor
python3 .harness/harness.py status
python3 .harness/harness.py handoff
```

After `handoff`, this file becomes the generated cross-session view of task, evidence, Git, and next-action state. Its working-tree section explicitly excludes `.harness/HANDOFF.md` itself.
