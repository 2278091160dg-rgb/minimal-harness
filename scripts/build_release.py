#!/usr/bin/env python3
"""Build versioned Minimal Harness release assets from a fixed Git ref."""

import argparse
import datetime
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
    ".harness/LICENSE",
    ".harness/harness.py",
    ".harness/config.json",
    ".harness/tasks.json",
}
V3_RUNTIME_FILES = {".harness/harness_init.py", ".harness/harness_runner.py"}
FORBIDDEN_PARTS = {
    "__pycache__", "evidence", "logs", "migrations", "attempts", "artifacts", "reports",
}
GIT_TIMEOUT_SECONDS = 120


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


def git_output(repo, *arguments, timeout_seconds=GIT_TIMEOUT_SECONDS):
    command = ["git", "-C", str(repo), *arguments]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or b"").decode("utf-8", errors="replace").strip()
        error = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        context = "; ".join(
            item
            for item in (
                f"stdout: {output}" if output else "",
                f"stderr: {error}" if error else "",
            )
            if item
        )
        suffix = f"; {context}" if context else ""
        raise RuntimeError(
            f"git {' '.join(arguments)} timed out after {timeout_seconds} seconds{suffix}"
        ) from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(arguments)} failed: {detail or 'unknown Git error'}")
    return completed.stdout


def fixed_ref_files(repo, ref):
    listing = git_output(
        repo,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        ref,
        "--",
        "template/.harness",
    )
    files = {}
    for record in listing.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, _object_id = metadata.split(b" ", 2)
        if object_type != b"blob" or mode not in (b"100644", b"100755"):
            raise ValueError(
                "release template must contain only regular files: "
                + raw_path.decode("utf-8", errors="replace")
            )
        try:
            source_path = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("release template paths must be UTF-8") from exc
        prefix = "template/.harness/"
        if not source_path.startswith(prefix):
            raise ValueError(f"unexpected release template path: {source_path}")
        archive_path = ".harness/" + source_path[len(prefix):]
        payload = git_output(repo, "show", f"{ref}:{source_path}").replace(b"\r\n", b"\n")
        files[archive_path] = (payload, mode == b"100755")

    if ".harness/LICENSE" not in files:
        try:
            license_payload = git_output(repo, "show", f"{ref}:LICENSE")
        except RuntimeError as exc:
            raise ValueError(
                "fixed Git ref has no template/.harness/LICENSE or root LICENSE"
            ) from exc
        files[".harness/LICENSE"] = (license_payload.replace(b"\r\n", b"\n"), False)
    return files


def resolve_fixed_ref(repo, ref):
    raw_commit = git_output(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    try:
        commit = raw_commit.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise ValueError(f"Git ref did not resolve to an ASCII object id: {ref}") from exc
    if len(commit) not in (40, 64) or any(character not in "0123456789abcdef" for character in commit):
        raise ValueError(f"Git ref did not resolve to a commit: {ref}")
    return commit


def fixed_ref_timestamp(repo, ref):
    raw_timestamp = git_output(repo, "show", "-s", "--format=%ct", f"{ref}^{{commit}}")
    try:
        timestamp = int(raw_timestamp.strip())
    except ValueError as exc:
        raise ValueError(f"fixed Git ref has an invalid commit timestamp: {ref}") from exc
    value = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
    if value.year < 1980:
        return (1980, 1, 1, 0, 0, 0)
    if value.year > 2107:
        return (2107, 12, 31, 23, 59, 58)
    return (value.year, value.month, value.day, value.hour, value.minute, value.second)


def deterministic_archive(files, timestamp):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as package:
        for name in sorted(files):
            payload, executable = files[name]
            info = zipfile.ZipInfo(name, date_time=timestamp)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = ((0o100755 if executable else 0o100644) << 16)
            package.writestr(info, payload)
    return output.getvalue()


def build_release(repo, ref, version, output_dir):
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ValueError(f"invalid version: {version!r}")

    commit = resolve_fixed_ref(repo, ref)
    files = fixed_ref_files(repo, commit)
    archive_payload = deterministic_archive(files, fixed_ref_timestamp(repo, commit))
    validate_archive(archive_payload)
    archive_path = output_dir / f"minimal-harness-{version}.zip"
    checksum_path = output_dir / "SHA256SUMS.txt"
    digest = hashlib.sha256(archive_payload).hexdigest()
    checksum_payload = f"{digest}  {archive_path.name}\n".encode("utf-8")

    atomic_write(archive_path, archive_payload)
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
