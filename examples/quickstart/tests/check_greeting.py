"""Acceptance checks the actual CLI, including the no-argument behavior."""

import subprocess
import sys
from pathlib import Path


workspace = Path(__file__).resolve().parents[1]
for arguments, expected in [(["Ada"], "Hello, Ada!"), ([], "Hello, world!")]:
    result = subprocess.run(
        [sys.executable, str(workspace / "src" / "greet.py"), *arguments],
        capture_output=True, text=True, check=True,
    )
    if result.stdout.strip() != expected:
        raise SystemExit(f"Expected {expected!r}; observed {result.stdout.strip()!r}")
print("PASS: named and default greetings match the CLI contract")
