#!/usr/bin/env python3
"""Build versioned Minimal Harness release assets from a fixed Git ref."""

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


VERSION_PATTERN = re.compile(
    r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?"
)
REQUIRED_FILES = {
    ".harness/harness.py",
    ".harness/config.json",
    ".harness/tasks.json",
}
V3_RUNTIME_FILES = {".harness/harness_init.py", ".harness/harness_runner.py"}
FORBIDDEN_PARTS = {
    "__pycache__", "evidence", "logs", "migrations", "attempts", "artifacts", "reports",
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a .harness ZIP and SHA256SUMS.txt from a Git ref."
    )
    parser.add_argument("--version", required=True, help="Release version, for example v0.1.1")
    parser.add_argument("--ref", default="HEAD", help="Git ref to archive (default: HEAD)")
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent of this script)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist"),
        help="Asset output directory (default: dist)",
    )
    return parser.parse_args(argv)


def validate_archive(payload):
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as package:
            file_names = [name for name in package.namelist() if not name.endswith("/")]
            missing = REQUIRED_FILES.difference(file_names)
            if missing:
                raise ValueError("archive is missing required files: " + ", ".join(sorted(missing)))
            config = json.loads(package.read(".harness/config.json"))
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Git produced an invalid ZIP archive: {exc}") from exc

    if not isinstance(config, dict):
        raise ValueError("archive config must be a JSON object")
    schema = config.get("schema_version", 1)
    if type(schema) is not int or schema not in (1, 2, 3):
        raise ValueError(f"archive config has unsupported schema_version: {schema!r}")
    if schema == 3:
        missing = V3_RUNTIME_FILES.difference(file_names)
        if missing:
            raise ValueError("archive is missing required files: " + ", ".join(sorted(missing)))
    for name in file_names:
        path = Path(name)
        if not name.startswith(".harness/") or FORBIDDEN_PARTS.intersection(path.parts):
            raise ValueError(f"archive contains forbidden path: {name}")


def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def build_release(repo, ref, version, output_dir):
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError(f"invalid version: {version!r}")

    command = [
        "git",
        "-c",
        "core.autocrlf=false",
        "-c",
        "core.eol=lf",
        "-C",
        str(repo),
        "archive",
        "--format=zip",
        "--prefix=.harness/",
        f"{ref}:template/.harness",
    ]
    completed = subprocess.run(command, capture_output=True)
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git archive failed: {detail or 'unknown Git error'}")

    validate_archive(completed.stdout)
    archive_path = output_dir / f"minimal-harness-{version}.zip"
    checksum_path = output_dir / "SHA256SUMS.txt"
    digest = hashlib.sha256(completed.stdout).hexdigest()
    checksum_payload = f"{digest}  {archive_path.name}\n".encode("utf-8")

    atomic_write(archive_path, completed.stdout)
    atomic_write(checksum_path, checksum_payload)
    return archive_path, checksum_path


def main(argv=None):
    args = parse_args(argv)
    try:
        archive_path, checksum_path = build_release(
            args.repo.resolve(), args.ref, args.version, args.output_dir.resolve()
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(archive_path)
    print(checksum_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
