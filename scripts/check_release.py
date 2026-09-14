#!/usr/bin/env python3
"""Build a fixed-ref release and exercise it in a disposable real Git project."""

import argparse
import hashlib
import json
import os
import shlex
import stat
import subprocess
import sys
import traceback
import zipfile
from pathlib import Path, PurePosixPath

import build_release


class CheckFailure(RuntimeError):
    """A release check failed with diagnostic context already recorded."""


class Transcript:
    def __init__(self, path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("Minimal Harness release check\n", encoding="utf-8")

    def write(self, text):
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(text.rstrip("\n") + "\n")


def write_text_lf(path, text):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build and smoke-check a Minimal Harness release from a fixed Git ref."
    )
    parser.add_argument("--ref", required=True, help="Git ref to validate")
    parser.add_argument("--version", required=True, help="Release version, for example v0.2.0")
    parser.add_argument("--output-dir", required=True, type=Path, help="Diagnostic output directory")
    return parser.parse_args(argv)


def run_command(transcript, arguments, cwd, *, expected=(0,), timeout_seconds=120):
    display = " ".join(shlex.quote(str(argument)) for argument in arguments)
    transcript.write(f"$ (cwd={cwd}) {display}")
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            [str(argument) for argument in arguments],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        for label, output in (("stdout", exc.stdout), ("stderr", exc.stderr)):
            if output:
                if isinstance(output, bytes):
                    output = output.decode("utf-8", errors="replace")
                transcript.write(f"{label} before timeout:\n{output}")
        message = f"command timed out after {timeout_seconds} seconds: {display}"
        transcript.write(message)
        raise CheckFailure(message) from exc
    if completed.stdout:
        transcript.write("stdout:\n" + completed.stdout)
    if completed.stderr:
        transcript.write("stderr:\n" + completed.stderr)
    transcript.write(f"exit: {completed.returncode}")
    if completed.returncode not in expected:
        raise CheckFailure(
            f"command returned {completed.returncode}, expected {expected}: {display}"
        )
    return completed


def validate_checksum(archive, checksum):
    lines = checksum.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1:
        raise CheckFailure("checksum file must contain exactly one entry")
    fields = lines[0].split("  ", 1)
    if len(fields) != 2 or fields[1] != archive.name:
        raise CheckFailure("checksum entry does not name the generated archive")
    expected = fields[0]
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise CheckFailure("checksum entry is not a lowercase SHA-256 digest")
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected:
        raise CheckFailure(f"archive checksum mismatch: expected {expected}, got {actual}")
    return actual


def safe_extract(archive, destination):
    destination.mkdir(parents=True, exist_ok=False)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as package:
        validated = []
        targets = set()
        for member in package.infolist():
            name = PurePosixPath(member.filename)
            if (
                member.is_dir()
                or "\\" in member.filename
                or name.is_absolute()
                or not name.parts
                or name.parts[0] != ".harness"
                or any(part in ("", ".", "..") or ":" in part for part in name.parts)
            ):
                raise CheckFailure(f"unsafe archive member: {member.filename}")
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                raise CheckFailure(f"unsafe archive member type: {member.filename}")
            target = destination.joinpath(*name.parts)
            try:
                target.resolve().relative_to(destination_root)
            except ValueError as exc:
                raise CheckFailure(f"unsafe archive member: {member.filename}") from exc
            if target in targets:
                raise CheckFailure(f"duplicate archive member: {member.filename}")
            targets.add(target)
            validated.append((member, target, mode))

        for member, target, mode in validated:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(package.read(member))
            if mode & 0o111:
                target.chmod(target.stat().st_mode | 0o111)


def write_smoke_sources(project):
    (project / "src").mkdir()
    (project / "tests").mkdir()
    greeting = (
        "def greet(name):\n"
        "    return f\"Hello, {name}!\"\n"
    )
    (project / "src" / "__init__.py").write_text("", encoding="utf-8")
    write_text_lf(project / "src" / "greeting.py", greeting)
    write_text_lf(
        project / "tests" / "test_greeting.py",
        "import unittest\n\n"
        "from src.greeting import greet\n\n\n"
        "class GreetingBehaviorTest(unittest.TestCase):\n"
        "    def test_greets_a_named_person(self):\n"
        "        self.assertEqual(\"Hello, Ada!\", greet(\"Ada\"))\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    unittest.main()\n",
    )
    definition = {
        "id": "greeting-behavior",
        "title": "Verify greeting behavior",
        "acceptance": [
            {
                "id": "real-greeting-test",
                "type": "command",
                "instruction": "The greeting returns a personalized Hello message.",
                "command": ["{python}", "-m", "unittest", "discover", "-s", "tests", "-v"],
                "timeout_seconds": 60,
            }
        ],
    }
    definition_path = project / "greeting-task.json"
    write_text_lf(
        definition_path,
        json.dumps(definition, ensure_ascii=False, indent=2) + "\n",
    )
    return greeting, definition_path


def write_report(path, completed):
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_lf(path, completed.stdout)


def run_check(repo, ref, version, output_dir, transcript):
    commit = build_release.resolve_fixed_ref(repo, ref)
    transcript.write(f"fixed ref: {ref} -> {commit}")
    assets = output_dir / "assets"
    archive, checksum = build_release.build_release(repo, commit, version, assets)
    digest = validate_checksum(archive, checksum)
    transcript.write(f"checksum verified: {digest}  {archive.name}")

    source_distribution = output_dir / "source-distribution"
    safe_extract(archive, source_distribution)
    transcript.write(f"archive safely extracted: {source_distribution}")

    project = output_dir / "smoke-project"
    project.mkdir(parents=True, exist_ok=False)
    project_license = b"Synthetic release-check project license\n"
    (project / "LICENSE").write_bytes(project_license)
    run_command(transcript, ["git", "init"], project)
    run_command(transcript, ["git", "config", "user.name", "Release Check"], project)
    run_command(
        transcript,
        ["git", "config", "user.email", "release-check@example.invalid"],
        project,
    )
    run_command(transcript, ["git", "config", "core.autocrlf", "false"], project)

    source_cli = source_distribution / ".harness" / "harness.py"
    run_command(
        transcript,
        [sys.executable, source_cli, "--workspace", project, "init"],
        repo,
    )
    installed_license = project / ".harness" / "LICENSE"
    packaged_license = source_distribution / ".harness" / "LICENSE"
    if installed_license.read_bytes() != packaged_license.read_bytes():
        raise CheckFailure("installed runtime license differs from the fixed-ref release license")
    if (project / "LICENSE").read_bytes() != project_license:
        raise CheckFailure("initializer replaced the disposable project's root license")

    original_greeting, definition_path = write_smoke_sources(project)
    run_command(transcript, ["git", "add", "."], project)
    run_command(transcript, ["git", "commit", "-m", "prepare greeting smoke project"], project)

    cli = [sys.executable, project / ".harness" / "harness.py"]
    run_command(transcript, [*cli, "task", "add", "--from", definition_path], project)
    run_command(transcript, [*cli, "next"], project)
    run_command(transcript, [*cli, "verify", "greeting-behavior"], project)

    reports = output_dir / "diagnostics" / "reports"
    for format_name, filename in (
        ("text", "report.txt"),
        ("json", "report.json"),
        ("markdown", "report.md"),
    ):
        report = run_command(
            transcript,
            [*cli, "report", "greeting-behavior", "--format", format_name],
            project,
        )
        write_report(reports / filename, report)

    greeting_path = project / "src" / "greeting.py"
    write_text_lf(
        greeting_path,
        "def greet(name):\n    return f\"Goodbye, {name}!\"\n",
    )
    stale = run_command(
        transcript,
        [*cli, "complete", "greeting-behavior"],
        project,
        expected=(1,),
    )
    stale_output = stale.stdout + stale.stderr
    if "stale evidence" not in stale_output:
        raise CheckFailure("changed greeting source was not rejected as stale evidence")
    write_text_lf(
        output_dir / "diagnostics" / "stale-complete.log",
        stale_output,
    )

    write_text_lf(greeting_path, original_greeting)
    run_command(transcript, [*cli, "verify", "greeting-behavior"], project)
    run_command(transcript, [*cli, "complete", "greeting-behavior"], project)
    run_command(transcript, [*cli, "handoff"], project)

    summary = {
        "status": "passed",
        "ref": ref,
        "commit": commit,
        "version": version,
        "archive": archive.relative_to(output_dir).as_posix(),
        "checksum": digest,
        "smoke_project": project.relative_to(output_dir).as_posix(),
    }
    write_text_lf(
        output_dir / "summary.json",
        json.dumps(summary, indent=2) + "\n",
    )
    transcript.write("release check passed")
    return summary


def main(argv=None):
    args = parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    output_dir = args.output_dir.resolve()
    transcript = Transcript(output_dir / "diagnostics" / "check-release.log")
    try:
        run_check(repo, args.ref, args.version, output_dir, transcript)
    except (CheckFailure, OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        transcript.write(f"FAILED: {exc}\n{traceback.format_exc()}")
        print(f"release check failed: {exc}", file=sys.stderr)
        return 1
    print(f"Release check passed: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
