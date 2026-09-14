"""Conservative, dependency-free installation into an existing project."""

import json
import os
import tempfile
from pathlib import Path
from typing import Optional


RUNTIME_FILES = ("harness.py", "harness_init.py", "harness_runner.py")
DISTRIBUTION_FILES = (*RUNTIME_FILES, "LICENSE")
START_MARKER = "<!-- minimal-harness:start -->"
END_MARKER = "<!-- minimal-harness:end -->"


def agent_instructions() -> str:
    return (
        START_MARKER + "\n"
        "## Minimal Harness workflow\n\n"
        "At session start run `python3 .harness/harness.py doctor` and "
        "`python3 .harness/harness.py status`, then read `.harness/HANDOFF.md`.\n"
        "Keep one task active. Define tasks with `task add --from SPEC.json`; "
        "use `task revise ID --from SPEC.json --note TEXT` for explicit changes. "
        "Do not edit runtime status or evidence fields by hand.\n"
        "Use `next` to select work, `verify` for command acceptance, and `record` "
        "for browser/manual observations. `run check` alone is not task evidence. "
        "Save browser artifacts in `.harness/artifacts/`.\n"
        "Run `report ID` to inspect readiness and evidence, and `complete ID` "
        "only after every acceptance passes against the current code and definition. "
        "An unavailable tool means `unverified`; browser/manual records are attestations.\n"
        "Respect configured allowed paths and approval operations. Stop at the "
        "configured failure limit; do not bypass a blocked task. "
        "Run `handoff` before ending the session.\n"
        + END_MARKER + "\n"
    )


def _read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected a non-symlink regular file: {path}")
    return path.read_bytes()


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _instruction_update(path: Path) -> tuple[Optional[bytes], bytes]:
    original = _read_regular(path) if path.exists() or path.is_symlink() else None
    content = (original or b"").decode("utf-8")
    block = agent_instructions()
    if START_MARKER in content or END_MARKER in content:
        if content.count(START_MARKER) != 1 or content.count(END_MARKER) != 1:
            raise ValueError(f"conflicting Harness instruction markers in {path.name}")
        begin = content.index(START_MARKER)
        end = content.index(END_MARKER) + len(END_MARKER)
        if content[begin:end].replace("\r\n", "\n") != block.rstrip("\n"):
            raise ValueError(f"conflicting Harness instruction block in {path.name}; review it manually")
        return original, original
    newline = "\r\n" if "\r\n" in content else "\n"
    separator = (newline * 2).encode() if original else b""
    return original, (original or b"") + separator + block.replace("\n", newline).encode("utf-8")


def _create_file(path: Path, payload: bytes, created: list) -> None:
    with path.open("xb") as output:
        identity = os.fstat(output.fileno())
        created.append((path, identity.st_dev, identity.st_ino))
        output.write(payload)


def _replace_instructions(path: Path, original: bytes, payload: bytes) -> None:
    # Only the explicit managed-block append changes an existing file.
    if _read_regular(path) != original:
        raise ValueError(f"instructions changed while initializing: {path.name}")
    mode = path.stat().st_mode & 0o777
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        if _read_regular(path) != original:
            raise ValueError(f"instructions changed while initializing: {path.name}")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def initialize(
    workspace: Path,
    *,
    agent: Optional[str] = None,
    dry_run: bool = False,
    source_dir: Path,
) -> str:
    """Preflight every conflict before writing; never replace an installed runtime."""
    if agent not in (None, "codex", "claude", "generic"):
        raise ValueError("agent must be codex, claude, or generic")
    workspace = Path(workspace).resolve()
    source_dir = Path(source_dir).resolve()
    if not workspace.is_dir():
        raise ValueError("workspace must be an existing directory")
    harness = workspace / ".harness"
    if harness.is_symlink() or (harness.exists() and not harness.is_dir()):
        raise ValueError(".harness must be a real directory inside the workspace")

    distribution = {name: _read_regular(source_dir / name) for name in DISTRIBUTION_FILES}
    writes = {}
    installed = harness.exists() and any(harness.iterdir())
    if installed:
        required = (*DISTRIBUTION_FILES, "config.json", "tasks.json", "HANDOFF.md")
        for name in required:
            if not (harness / name).is_file() or (harness / name).is_symlink():
                raise ValueError(f"partial or conflicting installation: .harness/{name}; no files changed")
        for name, payload in distribution.items():
            if _read_regular(harness / name) != payload:
                raise ValueError(f"conflicting installed runtime: {name}; use an explicit upgrade")
        for name in ("config.json", "tasks.json"):
            value = json.loads(_read_regular(harness / name).decode("utf-8"))
            if not isinstance(value, dict) or value.get("schema_version") != 3:
                raise ValueError(f"{name} requires explicit migration; init never upgrades state")
    else:
        config = {
            "schema_version": 3,
            "project_name": workspace.name,
            "commands": {"setup": None, "start": None, "check": None},
            "policy": {
                "schema_version": 3,
                "max_consecutive_failures": 3,
                "allowed_paths": ["src/**", "tests/**", ".harness/**"],
                "approval_required_operations": [
                    "install or remove dependencies", "delete or move user files",
                    "write to external services", "git commit, push, reset, or history changes",
                ],
                "require_git_for_completion": True,
            },
        }
        writes = {harness / name: payload for name, payload in distribution.items()}
        writes[harness / "config.json"] = _json_bytes(config)
        writes[harness / "tasks.json"] = _json_bytes(
            {"schema_version": 3, "current_task_id": None, "tasks": []}
        )
        writes[harness / "HANDOFF.md"] = (
            "# Harness Handoff\n\nNo tasks have been added.\n\n"
            "Run `python3 .harness/harness.py doctor`, then add an acceptance definition "
            "with `python3 .harness/harness.py task add --from SPEC.json`.\n"
        ).encode("utf-8")

    host_path = workspace / ("CLAUDE.md" if agent == "claude" else "AGENTS.md")
    host_original = host_payload = None
    if agent is not None:
        host_original, host_payload = _instruction_update(host_path)
    changes = [str(path.relative_to(workspace)) for path in writes]
    if host_payload is not None and host_payload != host_original:
        changes.append(host_path.name + " (append managed instructions)")
    if dry_run:
        return "Dry run; no files changed.\n" + "\n".join(changes or ["Already initialized."])

    created = []
    new_directory = not harness.exists()
    try:
        if writes:
            harness.mkdir(exist_ok=True)
        for path, payload in writes.items():
            _create_file(path, payload, created)
        if host_payload is not None and host_payload != host_original:
            if host_original is None:
                _create_file(host_path, host_payload, created)
            else:
                _replace_instructions(host_path, host_original, host_payload)
    except BaseException:
        for path, device, inode in reversed(created):
            if path.is_file() and not path.is_symlink():
                identity = path.stat()
                if (identity.st_dev, identity.st_ino) == (device, inode):
                    path.unlink()
        if new_directory and harness.is_dir() and not any(harness.iterdir()):
            harness.rmdir()
        raise
    return (
        ("Initialized" if not installed else "Already initialized") + f": {workspace}\n"
        + "\n".join(changes)
        + "\nNext: python3 .harness/harness.py doctor\n"
        "Add your task: python3 .harness/harness.py task add --from SPEC.json\n"
        "Set policy.allowed_paths to your project's intended edit scope before running next."
    )
