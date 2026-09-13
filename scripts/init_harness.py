#!/usr/bin/env python3
"""Install the pristine Minimal Harness template into an existing workspace."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


MANIFEST = (
    Path("harness.py"),
    Path("config.json"),
    Path("tasks.json"),
    Path("HANDOFF.md"),
    Path("adapters/AGENTS.md.snippet"),
    Path("adapters/CLAUDE.md.snippet"),
    Path("adapters/GENERIC.md"),
)
AGENT_FILES = {
    "codex": (Path("AGENTS.md"), Path("adapters/AGENTS.md.snippet")),
    "claude": (Path("CLAUDE.md"), Path("adapters/CLAUDE.md.snippet")),
}


class InitError(Exception):
    """A configuration, filesystem, or input error."""

    exit_code = 2


class ActivityGateError(InitError):
    """An otherwise valid change blocked by current task activity."""

    exit_code = 1


@dataclass(frozen=True)
class PlannedFile:
    relative: Path
    destination: Path
    action: str
    content: Optional[bytes]
    source_mode: Optional[int] = None


def lexical_absolute(path: Path) -> Path:
    """Make a path absolute while preserving dots and symbolic-link components."""

    return path if path.is_absolute() else Path.cwd() / path


def path_exists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def require_no_symlink_ancestors(path: Path, description: str) -> Path:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        if part == "..":
            current = current.parent
            continue
        current = current / part
        if current.is_symlink():
            raise InitError(f"{description} path must not contain a symlink: {current}")
    return current


def require_real_directory(path: Path, description: str) -> None:
    if path.is_symlink():
        raise InitError(f"{description} must not be a symlink: {path}")
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise InitError(f"{description} must already exist: {path}") from exc
    if not stat.S_ISDIR(mode):
        raise InitError(f"{description} must be a directory: {path}")


def require_regular_file(path: Path, description: str) -> os.stat_result:
    if path.is_symlink():
        raise InitError(f"{description} must not be a symlink: {path}")
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise InitError(f"missing {description}: {path}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise InitError(f"{description} must be a regular file: {path}")
    return metadata


def preflight_internal_ancestors(workspace: Path, relative: Path) -> None:
    current = workspace
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise InitError(f"destination path ancestor must not be a symlink: {current}")
        if path_exists(current) and not stat.S_ISDIR(current.lstat().st_mode):
            raise InitError(f"destination path ancestor must be a directory: {current}")


def preflight_destination_file(workspace: Path, relative: Path) -> Path:
    preflight_internal_ancestors(workspace, relative)
    destination = workspace / relative
    if destination.is_symlink():
        raise InitError(f"destination must not be a symlink: {destination}")
    if path_exists(destination) and not stat.S_ISREG(destination.lstat().st_mode):
        raise InitError(f"destination must be a regular file: {destination}")
    return destination


def trusted_runtime_module(runtime_path: Path):
    spec = importlib.util.spec_from_file_location("_minimal_harness_trusted_runtime", runtime_path)
    if spec is None or spec.loader is None:
        raise InitError(f"could not load trusted runtime validators: {runtime_path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def read_json_object(path: Path) -> Dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise InitError(f"existing state must be UTF-8: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InitError(f"invalid JSON in existing state {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InitError(f"existing state must contain a JSON object: {path}")
    return value


def validate_existing_state(workspace: Path, trusted_runtime) -> Dict[str, object]:
    config_path = workspace / ".harness" / "config.json"
    tasks_path = workspace / ".harness" / "tasks.json"
    config = read_json_object(config_path)
    tasks = read_json_object(tasks_path)
    if config.get("schema_version") != 2 or tasks.get("schema_version") != 2:
        raise InitError("existing config/tasks schema_version must be 2; no automatic upgrade or repair is performed")
    try:
        trusted_runtime.validate_config(config)
        trusted_runtime.validate_tasks(tasks)
    except trusted_runtime.HarnessError as exc:
        raise InitError(f"invalid existing harness state: {exc}") from exc
    except Exception as exc:
        raise InitError(
            f"invalid existing harness state: trusted validator rejected malformed data ({type(exc).__name__})"
        ) from exc
    return tasks


def normalize_snippet(snippet: bytes, newline: bytes, source: Path) -> bytes:
    try:
        text = snippet.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InitError(f"source adapter is not UTF-8: {source}") from exc
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    return newline.join(line.encode("utf-8") for line in normalized.split("\n"))


def managed_instruction_content(existing: bytes, snippet: bytes, agent: str, destination: Path, source: Path) -> bytes:
    bom = b"\xef\xbb\xbf"
    payload = existing[len(bom) :] if existing.startswith(bom) else existing
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InitError(f"instruction file must be UTF-8: {destination}") from exc

    start_text = f"<!-- minimal-harness:{agent}:start -->"
    end_text = f"<!-- minimal-harness:{agent}:end -->"
    start = start_text.encode("ascii")
    end = end_text.encode("ascii")
    start_count = text.count(start_text)
    end_count = text.count(end_text)

    without_expected = text.replace(start_text, "").replace(end_text, "")
    if "minimal-harness:" in without_expected:
        raise InitError(f"unexpected minimal-harness marker in {destination}")
    if start_count != end_count or start_count not in {0, 1}:
        raise InitError(f"partial or duplicate minimal-harness marker block in {destination}")

    newline = b"\r\n" if b"\r\n" in payload else b"\n"
    block = start + newline + normalize_snippet(snippet, newline, source) + newline + end
    if start_count == 1:
        start_index = existing.find(start)
        end_index = existing.find(end)
        if start_index > end_index:
            raise InitError(f"reversed minimal-harness markers in {destination}")
        return existing[:start_index] + block + existing[end_index + len(end) :]

    if not payload:
        separator = b""
    elif existing.endswith(newline + newline):
        separator = b""
    elif existing.endswith(newline):
        separator = newline
    else:
        separator = newline + newline
    return existing + separator + block + newline


def validate_source_manifest(source_root: Path) -> Tuple[Dict[Path, bytes], Dict[Path, int]]:
    require_real_directory(source_root.parent, "source template parent")
    require_real_directory(source_root, "source template directory")
    require_real_directory(source_root / "adapters", "source adapters directory")
    contents: Dict[Path, bytes] = {}
    modes: Dict[Path, int] = {}
    for relative in MANIFEST:
        source = source_root / relative
        metadata = require_regular_file(source, "source manifest entry")
        contents[relative] = source.read_bytes()
        modes[relative] = stat.S_IMODE(metadata.st_mode)
    return contents, modes


def build_plan(
    workspace: Path,
    source_root: Path,
    source_contents: Dict[Path, bytes],
    source_modes: Dict[Path, int],
    agents: Sequence[str],
) -> Tuple[List[PlannedFile], Optional[Dict[str, object]], bool]:
    harness_relative = Path(".harness")
    harness_path = workspace / harness_relative
    if harness_path.is_symlink():
        raise InitError(f"destination path ancestor must not be a symlink: {harness_path}")
    fresh = not path_exists(harness_path)
    if not fresh and not stat.S_ISDIR(harness_path.lstat().st_mode):
        raise InitError(f"existing .harness must be a directory: {harness_path}")

    destinations = {
        relative: preflight_destination_file(workspace, harness_relative / relative)
        for relative in MANIFEST
    }
    plan: List[PlannedFile] = []
    for relative in MANIFEST:
        destination_relative = harness_relative / relative
        destination = destinations[relative]
        if fresh:
            plan.append(
                PlannedFile(destination_relative, destination, "CREATE", source_contents[relative], source_modes[relative])
            )
        else:
            require_regular_file(destination, "existing runtime file")
            plan.append(PlannedFile(destination_relative, destination, "UNCHANGED", None))

    tasks: Optional[Dict[str, object]] = None
    if not fresh:
        trusted_runtime = trusted_runtime_module(source_root / "harness.py")
        tasks = validate_existing_state(workspace, trusted_runtime)

    for agent in agents:
        root_relative, snippet_relative = AGENT_FILES[agent]
        destination = preflight_destination_file(workspace, root_relative)
        exists = path_exists(destination)
        existing = destination.read_bytes() if exists else b""
        updated = managed_instruction_content(
            existing,
            source_contents[snippet_relative],
            agent,
            destination,
            source_root / snippet_relative,
        )
        action = "CREATE" if not exists else ("UNCHANGED" if updated == existing else "UPDATE")
        plan.append(PlannedFile(root_relative, destination, action, updated if action != "UNCHANGED" else None))
    return plan, tasks, fresh


def active_task_id(tasks: Optional[Dict[str, object]]) -> Optional[str]:
    if tasks is None:
        return None
    current = tasks.get("current_task_id")
    if not isinstance(current, str):
        return None
    for task in tasks.get("tasks", []):
        if isinstance(task, dict) and task.get("id") == current and task.get("status") in {"in_progress", "blocked"}:
            return current
    return None


def print_plan(plan: Sequence[PlannedFile], dry_run: bool) -> None:
    prefix = "DRY-RUN " if dry_run else ""
    for item in plan:
        print(f"{prefix}{item.action} {item.relative.as_posix()}")


def apply_plan(plan: Sequence[PlannedFile]) -> None:
    for item in plan:
        if item.action == "UNCHANGED":
            continue
        item.destination.parent.mkdir(parents=True, exist_ok=True)
        assert item.content is not None
        if path_exists(item.destination):
            mode = stat.S_IMODE(item.destination.lstat().st_mode)
        elif item.source_mode is not None:
            mode = item.source_mode
        else:
            previous_umask = os.umask(0)
            os.umask(previous_umask)
            mode = 0o666 & ~previous_umask
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{item.destination.name}.",
            dir=item.destination.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(item.content)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(mode)
            os.replace(temporary, item.destination)
        finally:
            if path_exists(temporary):
                temporary.unlink()


def selected_agents(agent: str) -> Tuple[str, ...]:
    return ("codex", "claude") if agent == "both" else (agent,)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--agent", choices=("codex", "claude", "both"), default="both")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = lexical_absolute(args.workspace)
    source_root = Path(__file__).resolve().parents[1] / "template" / ".harness"
    try:
        workspace = require_no_symlink_ancestors(workspace, "workspace")
        require_real_directory(workspace, "workspace")
        source_contents, source_modes = validate_source_manifest(source_root)
        plan, tasks, fresh = build_plan(
            workspace,
            source_root,
            source_contents,
            source_modes,
            selected_agents(args.agent),
        )
        print_plan(plan, args.dry_run)
        changes = any(item.action != "UNCHANGED" for item in plan)
        current_task = active_task_id(tasks)
        if changes and current_task is not None:
            raise ActivityGateError(
                f"active or blocked task {current_task} prevents instruction changes; finish it or resolve the blocker first"
            )
        if not args.dry_run:
            apply_plan(plan)
        if fresh:
            print("The installed config.json and tasks.json require project-specific editing before use.")
        print("Next: python3 .harness/harness.py doctor")
        print("Then: python3 .harness/harness.py status and read .harness/HANDOFF.md")
        return 0
    except InitError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    except OSError as exc:
        print(f"ERROR: filesystem operation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
