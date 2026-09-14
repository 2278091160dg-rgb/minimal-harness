# Contributing

Thank you for helping improve Minimal Harness.

## Project boundary

The core is a small Python 3.9+ standard-library acceptance kernel. Changes should preserve:

- fail-closed Git and evidence checks;
- deterministic, non-shell command execution;
- no third-party runtime dependency;
- cross-platform behavior on Linux, macOS, and Windows;
- the existing CLI exit-code contract.

Optional integrations belong outside `template/.harness/` when they require a platform API or additional tooling.

## Development workflow

1. Open an issue for substantial behavior or schema changes.
2. Add a failing regression test before changing behavior.
3. Keep commits focused and explain security-sensitive tradeoffs.
4. Run the full verification set:

```bash
python3 -m unittest discover -s tests -v
node --test examples/todo/test.mjs
python3 -m pip install ruff==0.15.12
ruff check --no-cache template/.harness integrations/github/publish_check.py scripts tests examples/quickstart
python3 template/.harness/harness.py --workspace template doctor
python3 template/.harness/harness.py --workspace examples/todo doctor
python3 template/.harness/harness.py --workspace examples/todo run check
```

Browser-facing changes must also pass `python3 tests/run_todo_walkthrough.py`, which runs
real Chromium acceptance and the complete Harness task loop in a disposable project.

## Security reports

Do not open a public issue containing a vulnerability or working exploit. Follow [SECURITY.md](SECURITY.md).

By submitting a contribution, you agree that it may be distributed under the repository's MIT License.
