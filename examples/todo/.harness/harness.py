#!/usr/bin/env python3
"""Run the repository's canonical Harness against this example."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


example_workspace = Path(__file__).resolve().parent.parent
repository_root = Path(__file__).resolve().parents[3]
canonical_harness = repository_root / "template" / ".harness" / "harness.py"
arguments = sys.argv[1:]
has_workspace = any(argument == "--workspace" or argument.startswith("--workspace=") for argument in arguments)
command = [sys.executable, str(canonical_harness)]
if not has_workspace:
    command.extend(["--workspace", str(example_workspace)])
command.extend(arguments)
raise SystemExit(subprocess.call(command))
