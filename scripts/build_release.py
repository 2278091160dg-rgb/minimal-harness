#!/usr/bin/env python3
"""Build versioned Minimal Harness release assets from a fixed Git ref."""

import argparse
import hashlib
import io
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
FORBIDDEN_PARTS = {"__pycache__", "evidence", "logs", "migrations"}


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
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Git produced an invalid ZIP archive: {exc}") from exc

    if ".harness/harness.py" not in file_names:
        raise ValueError("archive is missing .harness/harness.py")
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
