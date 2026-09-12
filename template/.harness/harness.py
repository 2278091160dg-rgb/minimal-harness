#!/usr/bin/env python3
"""Minimal, dependency-free harness for AI-assisted coding projects."""

from __future__ import annotations

import argparse
import copy
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


TASK_STATUSES = {"pending", "in_progress", "blocked", "done"}
CHECK_STATUSES = {"not_run", "passed", "failed", "unverified"}
CHECK_TYPES = {"command", "browser", "manual"}
SAFE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
SCHEMA_VERSION = 2


class HarnessError(Exception):
    """A configuration or usage error."""

    exit_code = 2


class GateError(HarnessError):
    """A valid operation rejected by a workflow gate."""

    exit_code = 1


class GitAuditError(HarnessError):
    """Git exists for this workspace but could not provide a trustworthy snapshot."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HarnessError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HarnessError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HarnessError(f"{path} must contain a JSON object")
    return value


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HarnessError(f"{field} must be a non-empty string")
    return value


def require_identifier(value: Any, field: str) -> str:
    identifier = require_string(value, field)
    if SAFE_ID_PATTERN.fullmatch(identifier) is None:
        raise HarnessError(
            f"{field} must be a safe identifier using 1-128 ASCII letters, digits, dot, underscore, or hyphen"
        )
    return identifier


def validate_argv(value: Any, field: str, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise HarnessError(f"{field} must be null or a non-empty array of strings")


def validate_policy(policy: Any, field: str = "policy") -> None:
    if not isinstance(policy, dict):
        raise HarnessError(f"{field} must be an object")
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise HarnessError(f"{field}.schema_version must be {SCHEMA_VERSION}")
    limit = policy.get("max_consecutive_failures")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise HarnessError(f"{field}.max_consecutive_failures must be a positive integer")
    for name in ("allowed_paths", "approval_required_operations"):
        value = policy.get(name)
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise HarnessError(f"{field}.{name} must be an array of strings")
    for pattern in policy["allowed_paths"]:
        validate_allowed_path_pattern(pattern, f"{field}.allowed_paths")
    if not isinstance(policy.get("require_git_for_completion"), bool):
        raise HarnessError(f"{field}.require_git_for_completion must be a boolean")


def validate_allowed_path_pattern(pattern: str, field: str) -> None:
    normalized = pattern.replace("\\", "/")
    if (
        normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or any(part in {"", ".", ".."} for part in normalized.split("/"))
    ):
        raise HarnessError(f"{field} contains an unsafe relative pattern: {pattern}")


def validate_config(config: Dict[str, Any]) -> None:
    if config.get("schema_version") != SCHEMA_VERSION:
        raise HarnessError(
            f"config schema_version must be {SCHEMA_VERSION}; run `python3 .harness/harness.py migrate`"
        )
    require_string(config.get("project_name"), "project_name")
    commands = config.get("commands")
    if not isinstance(commands, dict):
        raise HarnessError("commands must be an object")
    for name in ("setup", "start", "check"):
        if name not in commands:
            raise HarnessError(f"commands.{name} is required")
        validate_argv(commands[name], f"commands.{name}", optional=True)
    validate_policy(config.get("policy"))


def validate_v1_policy(policy: Any, field: str) -> None:
    if not isinstance(policy, dict):
        raise HarnessError(f"{field} must be an object")
    limit = policy.get("max_consecutive_failures")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise HarnessError(f"{field}.max_consecutive_failures must be a positive integer")
    for name in ("allowed_paths", "approval_required_operations"):
        value = policy.get(name)
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise HarnessError(f"{field}.{name} must be an array of strings")


def validate_v1_config(config: Dict[str, Any]) -> None:
    if config.get("schema_version") != 1:
        raise HarnessError("config schema_version must be 1")
    require_string(config.get("project_name"), "project_name")
    commands = config.get("commands")
    if not isinstance(commands, dict):
        raise HarnessError("commands must be an object")
    for name in ("setup", "start", "check"):
        if name not in commands:
            raise HarnessError(f"commands.{name} is required")
        validate_argv(commands[name], f"commands.{name}", optional=True)
    validate_v1_policy(config.get("policy"), "policy")


def validate_v1_tasks(state: Dict[str, Any]) -> None:
    if state.get("schema_version") != 1:
        raise HarnessError("tasks schema_version must be 1")
    tasks = state.get("tasks")
    if not isinstance(tasks, list):
        raise HarnessError("tasks must be an array")
    task_ids = set()
    active_ids = []
    blocked_ids = []
    for task in tasks:
        if not isinstance(task, dict):
            raise HarnessError("each task must be an object")
        task_id = require_identifier(task.get("id"), "task.id")
        if task_id in task_ids:
            raise HarnessError(f"duplicate task id: {task_id}")
        task_ids.add(task_id)
        require_string(task.get("title"), f"task {task_id} title")
        if task.get("status") not in TASK_STATUSES:
            raise HarnessError(f"task {task_id} has invalid status")
        if task["status"] == "in_progress":
            active_ids.append(task_id)
        if task["status"] == "blocked":
            blocked_ids.append(task_id)
        policy_baseline = task.get("policy_baseline")
        if policy_baseline is not None:
            validate_v1_policy(policy_baseline, f"task {task_id} policy_baseline")
        checks = task.get("acceptance")
        if not isinstance(checks, list) or not checks:
            raise HarnessError(f"task {task_id} acceptance must be a non-empty array")
        check_ids = set()
        for check in checks:
            if not isinstance(check, dict):
                raise HarnessError(f"task {task_id} acceptance entries must be objects")
            check_id = require_identifier(check.get("id"), f"task {task_id} acceptance.id")
            if check_id in check_ids:
                raise HarnessError(f"duplicate acceptance id in task {task_id}: {check_id}")
            check_ids.add(check_id)
            if check.get("type") not in CHECK_TYPES:
                raise HarnessError(f"acceptance {check_id} has invalid type")
            require_string(check.get("instruction"), f"acceptance {check_id} instruction")
            if check.get("status") not in CHECK_STATUSES:
                raise HarnessError(f"acceptance {check_id} has invalid status")
            failures = check.get("consecutive_failures")
            if not isinstance(failures, int) or isinstance(failures, bool) or failures < 0:
                raise HarnessError(f"acceptance {check_id} consecutive_failures must be non-negative")
            if check["type"] == "command":
                validate_argv(check.get("command"), f"acceptance {check_id} command")
            else:
                steps = check.get("steps")
                if not isinstance(steps, list) or not steps or not all(
                    isinstance(step, str) and step for step in steps
                ):
                    raise HarnessError(
                        f"acceptance {check_id} steps must be a non-empty array of strings"
                    )
        if task["status"] == "done" and any(check["status"] != "passed" for check in checks):
            raise HarnessError(f"done task {task_id} must have all acceptance checks passed")
    if len(active_ids) > 1 or len(blocked_ids) > 1:
        raise HarnessError("v1 state may contain at most one active and one blocked task")
    current = state.get("current_task_id")
    if current is not None and current not in task_ids:
        raise HarnessError("current_task_id does not reference a task")
    current_task = next((task for task in tasks if task["id"] == current), None) if current else None
    if current_task and current_task["status"] not in {"in_progress", "blocked"}:
        raise HarnessError("current_task_id must reference an in_progress or blocked task")
    if active_ids and current != active_ids[0]:
        raise HarnessError("current_task_id must reference the in_progress task")
    if blocked_ids and current != blocked_ids[0]:
        raise HarnessError("current_task_id must reference the blocked task")


def validate_git_baseline(value: Any, field: str) -> None:
    if not isinstance(value, dict):
        raise HarnessError(f"{field} must be an object")
    if value.get("version") != SCHEMA_VERSION:
        raise HarnessError(f"{field}.version must be {SCHEMA_VERSION}")
    require_string(value.get("captured_at"), f"{field}.captured_at")
    if not isinstance(value.get("available"), bool):
        raise HarnessError(f"{field}.available must be a boolean")
    paths = value.get("dirty_paths")
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise HarnessError(f"{field}.dirty_paths must be an array of strings")
    if len(paths) != len(set(paths)) or any(not safe_git_relative_path(path) for path in paths):
        raise HarnessError(f"{field}.dirty_paths must contain unique safe normalized paths")
    for name in ("worktree_fingerprints", "index_fingerprints"):
        fingerprints = value.get(name)
        if not isinstance(fingerprints, dict) or not all(
            isinstance(path, str) and isinstance(digest, str)
            for path, digest in fingerprints.items()
        ):
            raise HarnessError(f"{field}.{name} must be an object of string fingerprints")
        if set(fingerprints) != set(paths):
            raise HarnessError(f"{field}.{name} must exactly cover dirty_paths")
    if not all(valid_worktree_fingerprint(item) for item in value["worktree_fingerprints"].values()):
        raise HarnessError(f"{field}.worktree_fingerprints contains an invalid fingerprint")
    if not all(re.fullmatch(r"sha256:[0-9a-f]{64}", item) for item in value["index_fingerprints"].values()):
        raise HarnessError(f"{field}.index_fingerprints contains an invalid fingerprint")
    branch = value.get("branch")
    head = value.get("head")
    if value["available"]:
        require_string(branch, f"{field}.branch")
        if head is not None and not isinstance(head, str):
            raise HarnessError(f"{field}.head must be null or a Git object id")
        if isinstance(head, str) and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", head) is None:
            raise HarnessError(f"{field}.head must be a Git object id")
        if branch == "DETACHED" and head is None:
            raise HarnessError(f"{field} cannot be detached without HEAD")
    elif branch is not None or head is not None or paths:
        raise HarnessError(f"{field} unavailable snapshot must not contain Git state")


def safe_git_relative_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return bool(
        path
        and path == normalized
        and not normalized.startswith("/")
        and re.match(r"^[A-Za-z]:", normalized) is None
        and all(part not in {"", ".", ".."} for part in normalized.split("/"))
    )


def valid_worktree_fingerprint(value: str) -> bool:
    return bool(
        value == "missing"
        or re.fullmatch(r"file:[0-7]{3,4}:sha256:[0-9a-f]{64}", value)
        or re.fullmatch(r"symlink:sha256:[0-9a-f]{64}", value)
    )


def validate_tasks(state: Dict[str, Any]) -> None:
    if state.get("schema_version") != SCHEMA_VERSION:
        raise HarnessError(
            f"tasks schema_version must be {SCHEMA_VERSION}; run `python3 .harness/harness.py migrate`"
        )
    tasks = state.get("tasks")
    if not isinstance(tasks, list):
        raise HarnessError("tasks must be an array")
    task_ids = set()
    active_ids = []
    blocked_ids = []
    for task in tasks:
        if not isinstance(task, dict):
            raise HarnessError("each task must be an object")
        task_id = require_identifier(task.get("id"), "task.id")
        if task_id in task_ids:
            raise HarnessError(f"duplicate task id: {task_id}")
        task_ids.add(task_id)
        require_string(task.get("title"), f"task {task_id} title")
        if task.get("status") not in TASK_STATUSES:
            raise HarnessError(f"task {task_id} has invalid status")
        policy_baseline = task.get("policy_baseline")
        if policy_baseline is not None:
            validate_policy(policy_baseline, f"task {task_id} policy_baseline")
        if task["status"] == "in_progress":
            active_ids.append(task_id)
        if task["status"] == "blocked":
            blocked_ids.append(task_id)
        checks = task.get("acceptance")
        if not isinstance(checks, list) or not checks:
            raise HarnessError(f"task {task_id} acceptance must be a non-empty array")
        check_ids = set()
        for check in checks:
            if not isinstance(check, dict):
                raise HarnessError(f"task {task_id} acceptance entries must be objects")
            check_id = require_identifier(check.get("id"), f"task {task_id} acceptance.id")
            if check_id in check_ids:
                raise HarnessError(f"duplicate acceptance id in task {task_id}: {check_id}")
            check_ids.add(check_id)
            if check.get("type") not in CHECK_TYPES:
                raise HarnessError(f"acceptance {check_id} has invalid type")
            require_string(check.get("instruction"), f"acceptance {check_id} instruction")
            if check.get("status") not in CHECK_STATUSES:
                raise HarnessError(f"acceptance {check_id} has invalid status")
            failures = check.get("consecutive_failures")
            if not isinstance(failures, int) or isinstance(failures, bool) or failures < 0:
                raise HarnessError(f"acceptance {check_id} consecutive_failures must be non-negative")
            if check["status"] in {"not_run", "passed"} and failures != 0:
                raise HarnessError(f"acceptance {check_id} failure counter conflicts with its status")
            if check["status"] == "failed" and failures == 0:
                raise HarnessError(f"acceptance {check_id} failed status requires a positive failure counter")
            if check["type"] == "command":
                validate_argv(check.get("command"), f"acceptance {check_id} command")
            else:
                steps = check.get("steps")
                if not isinstance(steps, list) or not steps or not all(isinstance(step, str) and step for step in steps):
                    raise HarnessError(f"acceptance {check_id} steps must be a non-empty array of strings")
        if task["status"] == "done" and any(check["status"] != "passed" for check in checks):
            raise HarnessError(f"done task {task_id} must have all acceptance checks passed")
        if task["status"] in {"in_progress", "blocked"}:
            require_string(task.get("started_at"), f"task {task_id} started_at")
            if policy_baseline is None:
                raise HarnessError(f"task {task_id} policy_baseline is required while active")
            validate_git_baseline(task.get("git_baseline"), f"task {task_id} git_baseline")
        if task["status"] != "blocked" and (
            task.get("blocked_at") is not None or task.get("block_reason") is not None
        ):
            raise HarnessError(f"task {task_id} has stale blocking metadata")
        if task["status"] == "in_progress":
            limit = policy_baseline["max_consecutive_failures"]
            if any(
                check["status"] == "failed" and check["consecutive_failures"] >= limit
                for check in checks
            ):
                raise HarnessError(f"task {task_id} must be blocked at the frozen failure limit")
        if task["status"] == "blocked":
            require_string(task.get("blocked_at"), f"task {task_id} blocked_at")
            require_string(task.get("block_reason"), f"task {task_id} block_reason")
            limit = policy_baseline["max_consecutive_failures"]
            if not any(
                check["status"] == "failed" and check["consecutive_failures"] >= limit
                for check in checks
            ):
                raise HarnessError(f"blocked task {task_id} must have an acceptance at the failure limit")
    if len(active_ids) > 1:
        raise HarnessError("only one task may be in_progress")
    if len(blocked_ids) > 1:
        raise HarnessError("only one task may be blocked")
    current = state.get("current_task_id")
    if current is not None and current not in task_ids:
        raise HarnessError("current_task_id does not reference a task")
    current_task = next((task for task in tasks if task["id"] == current), None) if current else None
    if current_task and current_task["status"] not in {"in_progress", "blocked"}:
        raise HarnessError("current_task_id must reference an in_progress or blocked task")
    if active_ids and current != active_ids[0]:
        raise HarnessError("current_task_id must reference the in_progress task")
    if current is None and active_ids:
        raise HarnessError("current_task_id is required while a task is in_progress")
    if blocked_ids and current != blocked_ids[0]:
        raise HarnessError("current_task_id must reference the blocked task")


def load_workspace(workspace: Path) -> tuple[Path, Dict[str, Any], Dict[str, Any]]:
    workspace = workspace.resolve()
    harness_dir = workspace / ".harness"
    config = read_json(harness_dir / "config.json")
    state = read_json(harness_dir / "tasks.json")
    validate_config(config)
    validate_tasks(state)
    return harness_dir, config, state


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_write_json(path: Path, value: Dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def find_task(state: Dict[str, Any], task_id: str) -> Dict[str, Any]:
    for task in state["tasks"]:
        if task["id"] == task_id:
            return task
    raise HarnessError(f"unknown task: {task_id}")


def find_check(task: Dict[str, Any], check_id: str) -> Dict[str, Any]:
    for check in task["acceptance"]:
        if check["id"] == check_id:
            return check
    raise HarnessError(f"unknown acceptance check in task {task['id']}: {check_id}")


def effective_policy(task: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    return task.get("policy_baseline") or config["policy"]


def run_git(
    workspace: Path,
    arguments: List[str],
    operation: str,
    allowed_returncodes: Sequence[int] = (0,),
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=workspace,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise GitAuditError(f"Git {operation} failed: {exc}") from exc
    if result.returncode not in allowed_returncodes:
        detail = result.stderr.strip() or f"exit code {result.returncode}"
        raise GitAuditError(f"Git {operation} failed: {detail}")
    return result


def git_workspace_prefix(workspace: Path) -> str:
    result = run_git(workspace, ["rev-parse", "--show-prefix"], "workspace prefix")
    return result.stdout.strip().replace("\\", "/").strip("/")


def git_path_relative_to_workspace(path: str, prefix: str) -> Optional[str]:
    normalized = path.replace("\\", "/")
    if not prefix:
        return normalized
    marker = f"{prefix}/"
    if normalized.startswith(marker):
        return normalized[len(marker) :]
    return None


def git_snapshot(workspace: Path) -> Dict[str, Any]:
    try:
        probe = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=workspace,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return {
            "version": SCHEMA_VERSION,
            "captured_at": utc_now(),
            "available": False,
            "branch": None,
            "head": None,
            "dirty_paths": [],
            "worktree_fingerprints": {},
            "index_fingerprints": {},
        }
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return {
            "version": SCHEMA_VERSION,
            "captured_at": utc_now(),
            "available": False,
            "branch": None,
            "head": None,
            "dirty_paths": [],
            "worktree_fingerprints": {},
            "index_fingerprints": {},
        }
    symbolic = run_git(
        workspace,
        ["symbolic-ref", "--quiet", "--short", "HEAD"],
        "branch",
        (0, 1),
    )
    branch_name = symbolic.stdout.strip() if symbolic.returncode == 0 else "DETACHED"
    head_result = run_git(
        workspace,
        ["rev-parse", "--verify", "HEAD"],
        "HEAD",
        (0, 1, 128),
    )
    if head_result.returncode == 0:
        head_value = head_result.stdout.strip()
    elif symbolic.returncode == 0:
        metadata = run_git(
            workspace,
            ["status", "--porcelain=v2", "--branch", "-z", "--untracked-files=no", "--", "."],
            "unborn HEAD probe",
        )
        branch_fields = {}
        for entry in metadata.stdout.split("\0"):
            if entry.startswith("# branch.") and " " in entry:
                name, value = entry[2:].split(" ", 1)
                branch_fields[name] = value
        if (
            branch_fields.get("branch.oid") != "(initial)"
            or branch_fields.get("branch.head") != branch_name
        ):
            raise GitAuditError(
                "Git HEAD failed and could not prove an unborn repository: "
                + (head_result.stderr.strip() or f"exit code {head_result.returncode}")
            )
        head_value = None
    else:
        raise GitAuditError(f"Git HEAD failed: {head_result.stderr.strip()}")
    status = run_git(
        workspace,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--", "."],
        "status",
    )
    prefix = git_workspace_prefix(workspace)
    dirty_paths: List[str] = []
    entries = status.stdout.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        code = entry[:2]
        paths = [entry[3:]]
        if "R" in code or "C" in code:
            if index < len(entries) and entries[index]:
                paths.append(entries[index])
            index += 1
        for path in paths:
            relative = git_path_relative_to_workspace(path, prefix)
            if relative is not None:
                dirty_paths.append(relative)
    unique_dirty_paths = sorted(set(dirty_paths))
    return {
        "version": SCHEMA_VERSION,
        "captured_at": utc_now(),
        "available": True,
        "branch": branch_name,
        "head": head_value,
        "dirty_paths": unique_dirty_paths,
        "worktree_fingerprints": {
            path: workspace_path_fingerprint(workspace, path) for path in unique_dirty_paths
        },
        "index_fingerprints": {
            path: git_index_fingerprint(workspace, path) for path in unique_dirty_paths
        },
    }


def workspace_path_fingerprint(workspace: Path, path: str) -> str:
    candidate = workspace / path
    try:
        if candidate.is_symlink():
            target_digest = hashlib.sha256(os.fsencode(os.readlink(candidate))).hexdigest()
            return f"symlink:sha256:{target_digest}"
        if candidate.is_file():
            mode = candidate.stat().st_mode & 0o7777
            return f"file:{mode:04o}:sha256:{file_sha256(candidate)}"
        if candidate.exists():
            raise GitAuditError(f"Git cannot fingerprint non-regular dirty path: {path}")
    except OSError as exc:
        raise GitAuditError(f"Git worktree fingerprint failed for {path}: {exc}") from exc
    return "missing"


def git_index_fingerprint(workspace: Path, path: str) -> str:
    result = run_git(workspace, ["ls-files", "--stage", "-z", "--", path], "index read")
    payload = result.stdout.encode("utf-8", "surrogateescape")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def git_committed_changes(workspace: Path, baseline_head: Optional[str], current_head: Optional[str]) -> List[str]:
    if baseline_head == current_head:
        return []
    if current_head is None:
        raise GitAuditError("Git HEAD disappeared after the task started")
    prefix = git_workspace_prefix(workspace)
    if baseline_head is None:
        argv = ["git", "ls-tree", "-r", "--name-only", "-z", current_head]
        if prefix:
            argv.extend(["--", prefix])
    else:
        argv = ["git", "diff", "--name-only", "-z", baseline_head, current_head, "--", "."]
    result = run_git(workspace, argv[1:], "revision comparison")
    relative_paths = (
        git_path_relative_to_workspace(path, prefix)
        for path in result.stdout.split("\0")
        if path
    )
    return sorted(path for path in relative_paths if path is not None)


def changed_paths_since_baseline(
    workspace: Path,
    baseline: Dict[str, Any],
    current: Dict[str, Any],
) -> List[str]:
    if not baseline.get("available"):
        return []
    if not current.get("available"):
        raise GateError("Git became unavailable after the task started")
    if baseline.get("branch") != current.get("branch"):
        raise GateError(
            f"Git branch changed during task: {baseline.get('branch')} -> {current.get('branch')}"
        )
    changed = set(git_committed_changes(workspace, baseline.get("head"), current.get("head")))
    baseline_dirty = set(baseline.get("dirty_paths", []))
    changed.update(set(current.get("dirty_paths", [])) - baseline_dirty)
    for path, fingerprint in baseline.get("worktree_fingerprints", {}).items():
        if workspace_path_fingerprint(workspace, path) != fingerprint:
            changed.add(path)
    for path, fingerprint in baseline.get("index_fingerprints", {}).items():
        if git_index_fingerprint(workspace, path) != fingerprint:
            changed.add(path)
    return sorted(changed)


def path_allowed(path: str, patterns: List[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        normalized_pattern = pattern.replace("\\", "/")
        if path_segments_match(normalized.split("/"), normalized_pattern.split("/")):
            return True
    return False


def path_segments_match(path_parts: List[str], pattern_parts: List[str]) -> bool:
    if not pattern_parts:
        return not path_parts
    pattern = pattern_parts[0]
    if pattern == "**":
        return path_segments_match(path_parts, pattern_parts[1:]) or bool(
            path_parts and path_segments_match(path_parts[1:], pattern_parts)
        )
    return bool(
        path_parts
        and fnmatch.fnmatchcase(path_parts[0], pattern)
        and path_segments_match(path_parts[1:], pattern_parts[1:])
    )


def evidence_details_for_handoff(
    workspace: Path,
    harness_dir: Path,
    task: Dict[str, Any],
    check: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    reference = check.get("latest_evidence")
    if not isinstance(reference, str) or not reference:
        return None
    try:
        validate_evidence_reference(workspace, harness_dir, task, check)
        evidence_path = resolve_inside(reference, workspace, "evidence path")
        evidence = read_json(evidence_path)
    except (HarnessError, OSError) as exc:
        return {
            "valid": False,
            "error": str(exc),
            "timestamp": "Invalid",
            "summary": "Evidence invalid",
            "path": reference,
        }
    return {
        "valid": True,
        "timestamp": evidence.get("timestamp", "Unknown"),
        "summary": evidence.get("summary", "No summary"),
        "path": reference,
    }


def historical_failures_for_handoff(workspace: Path, harness_dir: Path) -> List[Dict[str, Any]]:
    failures = []
    evidence_root = harness_dir / "evidence"
    if not evidence_root.exists() and not evidence_root.is_symlink():
        return failures
    try:
        require_safe_directory(evidence_root, workspace, create=False)
    except HarnessError as exc:
        return [
            {
                "valid": False,
                "path": evidence_root.relative_to(workspace).as_posix(),
                "error": str(exc),
            }
        ]
    for evidence_path in evidence_root.glob("*/*.json"):
        try:
            if evidence_path.is_symlink() or not evidence_path.is_file():
                raise HarnessError("historical evidence must be a non-symlink regular file")
            evidence = read_json(evidence_path)
            if evidence.get("result") != "failed":
                continue
            if evidence.get("schema_version") != SCHEMA_VERSION:
                raise HarnessError("historical evidence is not schema v2")
            task_id = require_identifier(evidence.get("task_id"), "historical evidence task_id")
            check_id = require_identifier(evidence.get("check_id"), "historical evidence check_id")
            timestamp = require_string(evidence.get("timestamp"), "historical evidence timestamp")
            require_string(evidence.get("summary"), "historical evidence summary")
            method = evidence.get("method")
            if method not in CHECK_TYPES:
                raise HarnessError("historical evidence method is invalid")
            expected_provenance = {
                "command": "command-exit",
                "browser": "browser-tool",
                "manual": "manual-attestation",
            }[method]
            if evidence.get("provenance") != expected_provenance:
                raise HarnessError("historical evidence provenance is invalid")
            log_metadata = evidence.get("log")
            if log_metadata is not None:
                validate_file_metadata(
                    log_metadata, workspace, "historical evidence log", evidence_path.parent.resolve()
                )
            artifacts = evidence.get("artifacts")
            if not isinstance(artifacts, list) or not all(
                isinstance(artifact, dict) for artifact in artifacts
            ):
                raise HarnessError("historical evidence artifacts are invalid")
            for artifact in artifacts:
                validate_file_metadata(
                    artifact, workspace, "historical evidence artifact", workspace
                )
            failures.append(
                {
                    "valid": True,
                    "task_id": task_id,
                    "check_id": check_id,
                    "timestamp": timestamp,
                    "path": evidence_path.relative_to(workspace).as_posix(),
                }
            )
        except (HarnessError, OSError) as exc:
            failures.append(
                {
                    "valid": False,
                    "path": evidence_path.relative_to(workspace).as_posix(),
                    "error": str(exc),
                }
            )
    return sorted(failures, key=lambda item: item.get("timestamp", ""), reverse=True)[:20]


def render_handoff(workspace: Path, config: Dict[str, Any], state: Dict[str, Any]) -> str:
    snapshot = git_snapshot(workspace)
    current_id = state.get("current_task_id")
    current = find_task(state, current_id) if current_id else None
    completed = sorted(
        (task for task in state["tasks"] if task["status"] == "done"),
        key=lambda task: task.get("completed_at", ""),
        reverse=True,
    )[:5]
    blocked = [task for task in state["tasks"] if task["status"] == "blocked"]
    failed_checks = [
        (task, check)
        for task in state["tasks"]
        for check in task["acceptance"]
        if check["status"] == "failed"
    ]
    historical_failures = historical_failures_for_handoff(workspace, workspace / ".harness")
    unverified_checks = [
        (task, check)
        for task in state["tasks"]
        for check in task["acceptance"]
        if check["status"] == "unverified"
    ]
    lines = [
        "# Harness Handoff",
        "",
        "## Project state",
        "",
        f"- Project: {config['project_name']}",
        f"- Snapshot schema: {SCHEMA_VERSION}",
        f"- Snapshot captured: {snapshot['captured_at']}",
        f"- Generated: {utc_now()}",
        f"- Branch: {snapshot['branch'] or 'Unavailable'}",
        f"- HEAD: {snapshot['head'] or 'Unavailable'}",
        f"- Current task: {current_id or 'None'}",
        "",
        "## Current acceptance",
        "",
    ]
    if current:
        lines.append(f"### {current['id']}: {current['title']} [{current['status']}]")
        lines.append("")
        for check in current["acceptance"]:
            lines.append(f"- {check['id']} [{check['status']}] ({check['type']}): {check['instruction']}")
            details = evidence_details_for_handoff(workspace, workspace / ".harness", current, check)
            if details:
                if details["valid"]:
                    lines.append(f"  - Evidence time: {details['timestamp']}")
                    lines.append(f"  - Evidence summary: {details['summary']}")
                    lines.append(f"  - Evidence path: {details['path']}")
                else:
                    lines.append(f"  - Evidence invalid: {details['error']}")
    else:
        lines.append("None")
    lines.extend(["", "## Recently completed", ""])
    lines.extend(
        [
            f"- {task['id']}: {task['title']}"
            + (" [legacy evidence]" if task.get("legacy_evidence") is True else "")
            for task in completed
        ]
        or ["None"]
    )
    lines.extend(["", "## Failures and blockers", ""])
    failure_lines = [f"- {task['id']}: {task.get('block_reason', 'blocked')}" for task in blocked]
    failure_lines.extend(
        f"- {task['id']}/{check['id']}: failed ({check['consecutive_failures']} consecutive)"
        for task, check in failed_checks
    )
    failure_lines.extend(
        (
            "- Historical failure record (untrusted summary omitted) "
            f"{item['task_id']}/{item['check_id']} at {item['timestamp']}: {item['path']}"
            if item["valid"]
            else f"- Historical evidence invalid {item['path']}: {item['error']}"
        )
        for item in historical_failures
    )
    lines.extend(failure_lines or ["None"])
    lines.extend(["", "## Unverified", ""])
    lines.extend([f"- {task['id']}/{check['id']}: {check['instruction']}" for task, check in unverified_checks] or ["None"])
    lines.extend(["", "## Working tree (excluding generated .harness/HANDOFF.md)", ""])
    if snapshot["available"]:
        displayed_paths = [
            path for path in snapshot["dirty_paths"] if path != ".harness/HANDOFF.md"
        ]
        lines.extend([f"- {path}" for path in displayed_paths] or ["Clean"])
    else:
        lines.append("Git unavailable or workspace is not a repository.")
    if current and current.get("git_baseline", {}).get("available"):
        lines.extend(["", "### Out-of-scope warning", ""])
        try:
            changed_paths = changed_paths_since_baseline(
                workspace, current["git_baseline"], snapshot
            )
            outside = [
                path
                for path in changed_paths
                if not path_allowed(path, effective_policy(current, config)["allowed_paths"])
            ]
            if outside:
                lines.append("WARNING: These task changes are outside policy.allowed_paths:")
                lines.extend(f"- {path}" for path in outside)
            else:
                lines.append("None")
        except (GateError, GitAuditError) as exc:
            lines.append(f"WARNING: Scope audit unavailable: {exc}")
    relevant_task = current or (completed[0] if completed else None)
    baseline_dirty = (
        relevant_task.get("git_baseline", {}).get("dirty_paths", []) if relevant_task else []
    )
    lines.extend(["", "## Pre-existing changes at task start", ""])
    if baseline_dirty:
        lines.append("WARNING: These paths existed before the task and are not attributed to it unless their content changed.")
        lines.extend(f"- {path}" for path in baseline_dirty)
    else:
        lines.append("None")
    lines.extend(["", "## Next action", ""])
    if current and current["status"] == "blocked":
        lines.append(f"Run `python3 .harness/harness.py unblock {current['id']} --note \"<what changed>\"` after human intervention.")
    elif current:
        pending_command = next(
            (check for check in current["acceptance"] if check["type"] == "command" and check["status"] != "passed"),
            None,
        )
        if pending_command:
            lines.append(f"Run `python3 .harness/harness.py verify {current['id']}`.")
        else:
            pending_check = next((check for check in current["acceptance"] if check["status"] != "passed"), None)
            if pending_check:
                lines.append(f"Perform `{pending_check['id']}` and record the observed result.")
            else:
                lines.append(f"Run `python3 .harness/harness.py complete {current['id']}`.")
    elif any(task["status"] == "pending" for task in state["tasks"]):
        lines.append("Run `python3 .harness/harness.py next`.")
    else:
        lines.append("All tasks are complete.")
    lines.append("")
    return "\n".join(lines)


def refresh_handoff(workspace: Path, harness_dir: Path, config: Dict[str, Any], state: Dict[str, Any]) -> None:
    atomic_write_text(harness_dir / "HANDOFF.md", render_handoff(workspace, config, state))


def relative_path(path: Path, workspace: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_safe_directory(path: Path, workspace: Path, *, create: bool) -> Path:
    workspace = workspace.resolve()
    lexical = path if path.is_absolute() else workspace / path
    try:
        relative = lexical.relative_to(workspace)
    except ValueError as exc:
        raise HarnessError(f"directory must stay inside the workspace: {path}") from exc
    current = workspace
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise HarnessError(f"directory must not contain a symbolic link: {current}")
    if create:
        lexical.mkdir(parents=True, exist_ok=True)
    if not lexical.is_dir():
        raise HarnessError(f"required directory is not a directory: {lexical}")
    return lexical


def write_unique_bytes(path: Path, payload: bytes) -> None:
    descriptor: Optional[int] = None
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise HarnessError(f"refusing to overwrite existing evidence file: {path}") from exc
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        raise HarnessError(f"could not create evidence file {path}: {exc}") from exc


def regular_file_metadata(path: Path, workspace: Path) -> Dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise HarnessError(f"artifact must be a non-symlink regular file: {path}")
    stat_result = path.stat()
    return {
        "path": relative_path(path, workspace),
        "type": "file",
        "size": stat_result.st_size,
        "sha256": file_sha256(path),
    }


def create_evidence(
    workspace: Path,
    harness_dir: Path,
    task: Dict[str, Any],
    check: Dict[str, Any],
    result: str,
    summary: str,
    method: str,
    *,
    tool: Optional[str] = None,
    exit_code: Optional[int] = None,
    output: Optional[bytes] = None,
    artifacts: Optional[List[Dict[str, Any]]] = None,
) -> tuple[str, str]:
    timestamp = utc_now()
    file_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stem = f"{file_stamp}-{check['id']}-{uuid.uuid4().hex[:8]}"
    require_safe_directory(harness_dir, workspace, create=False)
    evidence_root = require_safe_directory(harness_dir / "evidence", workspace, create=True)
    evidence_dir = require_safe_directory(evidence_root / task["id"], workspace, create=True)
    log_metadata = None
    if output is not None:
        absolute_log_path = evidence_dir / f"{stem}.log"
        write_unique_bytes(absolute_log_path, output)
        log_metadata = regular_file_metadata(absolute_log_path, workspace)
    evidence_path = evidence_dir / f"{stem}.json"
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "evidence_id": stem,
        "task_id": task["id"],
        "check_id": check["id"],
        "timestamp": timestamp,
        "result": result,
        "method": method,
        "summary": summary,
        "tool": tool,
        "provenance": {
            "command": "command-exit",
            "browser": "browser-tool",
            "manual": "manual-attestation",
        }[method],
        "exit_code": exit_code,
        "log": log_metadata,
        "artifacts": artifacts or [],
    }
    write_unique_bytes(
        evidence_path,
        (json.dumps(evidence, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return relative_path(evidence_path, workspace), file_sha256(evidence_path)


def apply_check_result(
    state: Dict[str, Any],
    config: Dict[str, Any],
    task: Dict[str, Any],
    check: Dict[str, Any],
    result: str,
    evidence_path: str,
    evidence_sha256: str,
) -> None:
    check["status"] = result
    check["latest_evidence"] = evidence_path
    check["latest_evidence_sha256"] = evidence_sha256
    if result == "failed":
        check["consecutive_failures"] += 1
        if check["consecutive_failures"] >= effective_policy(task, config)[
            "max_consecutive_failures"
        ]:
            task["status"] = "blocked"
            task["blocked_at"] = utc_now()
            task["block_reason"] = f"acceptance {check['id']} reached the consecutive failure limit"
    elif result == "passed":
        check["consecutive_failures"] = 0


def resolve_inside(path_value: str, root: Path, description: str) -> Path:
    candidate = Path(path_value)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise HarnessError(f"{description} must stay inside {root}") from exc
    return resolved


def validate_evidence_reference(
    workspace: Path,
    harness_dir: Path,
    task: Dict[str, Any],
    check: Dict[str, Any],
) -> None:
    reference = check.get("latest_evidence")
    if reference is None:
        if task.get("legacy_evidence") is True and task.get("status") == "done":
            return
        if check["status"] == "passed":
            raise HarnessError(f"passed acceptance {task['id']}/{check['id']} requires valid evidence")
        return
    if not isinstance(reference, str) or not reference:
        raise HarnessError(f"latest evidence for {task['id']}/{check['id']} must be a path string")
    require_safe_directory(harness_dir, workspace, create=False)
    require_safe_directory(harness_dir / "evidence", workspace, create=False)
    evidence_root = require_safe_directory(
        harness_dir / "evidence" / task["id"], workspace, create=False
    ).resolve()
    reference_path = Path(reference)
    lexical_evidence_path = (
        reference_path if reference_path.is_absolute() else workspace / reference_path
    )
    if lexical_evidence_path.is_symlink():
        raise HarnessError(f"evidence file must be a non-symlink regular file: {reference}")
    evidence_path = resolve_inside(reference, workspace, "evidence path")
    try:
        evidence_path.relative_to(evidence_root)
    except ValueError as exc:
        raise HarnessError(f"evidence path for {task['id']}/{check['id']} is outside its task directory") from exc
    if not evidence_path.is_file():
        raise HarnessError(f"evidence file does not exist: {reference}")
    expected_digest = check.get("latest_evidence_sha256")
    if not isinstance(expected_digest, str) or file_sha256(evidence_path) != expected_digest:
        raise HarnessError(f"evidence digest does not match for {task['id']}/{check['id']}")
    evidence = read_json(evidence_path)
    if evidence.get("schema_version") != SCHEMA_VERSION:
        if task.get("legacy_evidence") is True and task.get("status") == "done":
            return
        raise HarnessError(f"evidence schema_version must be {SCHEMA_VERSION} for {task['id']}/{check['id']}")
    expected = {
        "task_id": task["id"],
        "check_id": check["id"],
        "result": check["status"],
        "method": check["type"],
    }
    for field, value in expected.items():
        if evidence.get(field) != value:
            raise HarnessError(f"evidence {field} does not match for {task['id']}/{check['id']}")
    if not isinstance(evidence.get("summary"), str) or not evidence["summary"].strip():
        raise HarnessError(f"evidence summary is missing for {task['id']}/{check['id']}")
    log_metadata = evidence.get("log")
    if log_metadata is not None:
        validate_file_metadata(
            log_metadata, workspace, f"evidence log for {task['id']}/{check['id']}", evidence_root
        )
    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, list) or not all(isinstance(item, dict) for item in artifacts):
        raise HarnessError(f"evidence artifacts are invalid for {task['id']}/{check['id']}")
    for artifact in artifacts:
        validate_file_metadata(
            artifact, workspace, f"evidence artifact for {task['id']}/{check['id']}", workspace
        )
    if check["type"] == "command" and check["status"] == "passed" and evidence.get("exit_code") != 0:
        raise HarnessError(f"passed command evidence must have exit_code 0 for {task['id']}/{check['id']}")
    expected_provenance = {
        "command": "command-exit",
        "browser": "browser-tool",
        "manual": "manual-attestation",
    }[check["type"]]
    if evidence.get("provenance") != expected_provenance:
        raise HarnessError(f"evidence provenance does not match for {task['id']}/{check['id']}")
    if check["type"] == "browser" and check["status"] == "passed":
        if not isinstance(evidence.get("tool"), str) or not evidence["tool"].strip():
            raise HarnessError(f"passed browser evidence requires a tool for {task['id']}/{check['id']}")
        if not artifacts:
            raise HarnessError(f"passed browser evidence requires an artifact for {task['id']}/{check['id']}")


def validate_file_metadata(
    metadata: Dict[str, Any],
    workspace: Path,
    description: str,
    required_root: Path,
) -> Path:
    if metadata.get("type") != "file" or not isinstance(metadata.get("path"), str):
        raise HarnessError(f"{description} metadata is invalid")
    candidate = Path(metadata["path"])
    lexical_path = candidate if candidate.is_absolute() else workspace / candidate
    if lexical_path.is_symlink():
        raise HarnessError(f"{description} must be a non-symlink regular file")
    path = resolve_inside(metadata["path"], workspace, description)
    try:
        path.relative_to(required_root.resolve())
    except ValueError as exc:
        raise HarnessError(f"{description} is outside its allowed directory") from exc
    if path.is_symlink() or not path.is_file():
        raise HarnessError(f"{description} must be a non-symlink regular file")
    expected_size = metadata.get("size")
    if not isinstance(expected_size, int) or isinstance(expected_size, bool) or path.stat().st_size != expected_size:
        raise HarnessError(f"{description} size does not match")
    expected_digest = metadata.get("sha256")
    if not isinstance(expected_digest, str) or file_sha256(path) != expected_digest:
        kind = "log" if "log" in description else "artifact"
        raise HarnessError(f"evidence {kind} digest does not match")
    return path


def executable_available(workspace: Path, executable: str) -> bool:
    if executable == "{python}":
        return True
    executable_path = Path(executable)
    if executable_path.is_absolute() or "/" in executable or "\\" in executable:
        candidate = executable_path if executable_path.is_absolute() else workspace / executable_path
        return candidate.is_file() and os.access(candidate, os.X_OK)
    return shutil.which(executable) is not None


def command_doctor(workspace: Path) -> int:
    harness_dir, config, state = load_workspace(workspace)
    if sys.version_info < (3, 9):
        raise HarnessError("Python 3.9 or newer is required")
    for name, argv in config["commands"].items():
        if argv is not None and not executable_available(workspace, argv[0]):
            raise HarnessError(f"commands.{name} executable not found: {argv[0]}")
    for task in state["tasks"]:
        for check in task["acceptance"]:
            if check["type"] == "command" and not executable_available(
                workspace, check["command"][0]
            ):
                raise HarnessError(
                    f"acceptance {task['id']}/{check['id']} executable not found: {check['command'][0]}"
                )
            validate_evidence_reference(workspace, harness_dir, task, check)
    print(f"OK: configuration valid ({len(state['tasks'])} tasks)")
    snapshot = git_snapshot(workspace)
    if snapshot["available"]:
        print(f"OK: Git branch={snapshot['branch']} HEAD={snapshot['head']}")
        if snapshot["dirty_paths"]:
            print(f"WARNING: working tree has {len(snapshot['dirty_paths'])} changed path(s)")
    else:
        print("WARNING: Git unavailable or workspace is not a repository")
    return 0


def command_next(workspace: Path) -> int:
    harness_dir, config, state = load_workspace(workspace)
    if state.get("current_task_id") is not None:
        raise GateError(f"task {state['current_task_id']} is already active")
    blocked = [task["id"] for task in state["tasks"] if task["status"] == "blocked"]
    if blocked:
        raise GateError(f"blocked task requires intervention: {blocked[0]}")
    task = next((item for item in state["tasks"] if item["status"] == "pending"), None)
    if task is None:
        print("No pending tasks.")
        return 0
    task["status"] = "in_progress"
    task["started_at"] = utc_now()
    task["git_baseline"] = git_snapshot(workspace)
    task["policy_baseline"] = {
        "schema_version": SCHEMA_VERSION,
        "max_consecutive_failures": config["policy"]["max_consecutive_failures"],
        "allowed_paths": list(config["policy"]["allowed_paths"]),
        "approval_required_operations": list(
            config["policy"]["approval_required_operations"]
        ),
        "require_git_for_completion": config["policy"]["require_git_for_completion"],
    }
    state["current_task_id"] = task["id"]
    atomic_write_json(harness_dir / "tasks.json", state)
    refresh_handoff(workspace, harness_dir, config, state)
    print(f"Selected {task['id']}: {task['title']}")
    return 0


def command_status(workspace: Path) -> int:
    _, config, state = load_workspace(workspace)
    print(f"Project: {config['project_name']}")
    print(f"Current task: {state.get('current_task_id') or 'None'}")
    for task in state["tasks"]:
        print(f"- {task['id']} [{task['status']}]: {task['title']}")
        for check in task["acceptance"]:
            print(f"  - {check['id']} [{check['status']}] ({check['type']})")
    return 0


def decode_command_output(output: bytes) -> str:
    return output.decode("utf-8", errors="replace")


def expand_argv(argv: List[str]) -> List[str]:
    return [sys.executable if item == "{python}" else item for item in argv]


def run_argv(argv: List[str], workspace: Path, capture: bool) -> subprocess.CompletedProcess[bytes]:
    expanded_argv = expand_argv(argv)
    try:
        if capture:
            return subprocess.run(
                expanded_argv,
                cwd=workspace,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
        process = subprocess.Popen(expanded_argv, cwd=workspace)
        try:
            return_code = process.wait()
        except KeyboardInterrupt:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
        return subprocess.CompletedProcess(expanded_argv, return_code)
    except FileNotFoundError as exc:
        raise HarnessError(f"executable not found: {argv[0]}") from exc
    except OSError as exc:
        raise HarnessError(f"could not execute {argv[0]}: {exc}") from exc


def command_run(workspace: Path, command_name: str) -> int:
    _, config, _ = load_workspace(workspace)
    argv = config["commands"][command_name]
    if argv is None:
        raise GateError(f"commands.{command_name} is not configured")
    capture = command_name != "start"
    result = run_argv(argv, workspace, capture=capture)
    if result.stdout:
        output = decode_command_output(result.stdout)
        print(output, end="" if output.endswith("\n") else "\n")
    return 0 if result.returncode == 0 else 1


def command_verify(workspace: Path, requested_task_id: Optional[str]) -> int:
    harness_dir, config, state = load_workspace(workspace)
    task_id = requested_task_id or state.get("current_task_id")
    if not task_id:
        raise GateError("no active task; run next first")
    if state.get("current_task_id") != task_id:
        raise GateError(f"task {task_id} is not the current task")
    task = find_task(state, task_id)
    if task["status"] != "in_progress":
        raise GateError(f"task {task_id} is not in_progress")
    checks = [check for check in task["acceptance"] if check["type"] == "command"]
    if not checks:
        raise GateError(f"task {task_id} has no command acceptance checks")
    for check in checks:
        result = run_argv(check["command"], workspace, capture=True)
        output = result.stdout or b""
        if output:
            displayed_output = decode_command_output(output)
            print(displayed_output, end="" if displayed_output.endswith("\n") else "\n")
        check_result = "passed" if result.returncode == 0 else "failed"
        evidence_path, evidence_sha256 = create_evidence(
            workspace,
            harness_dir,
            task,
            check,
            check_result,
            f"command exited with code {result.returncode}",
            "command",
            tool=check["command"][0],
            exit_code=result.returncode,
            output=output,
        )
        apply_check_result(state, config, task, check, check_result, evidence_path, evidence_sha256)
        atomic_write_json(harness_dir / "tasks.json", state)
        refresh_handoff(workspace, harness_dir, config, state)
        if result.returncode != 0:
            return 1
    return 0


def validate_artifacts(workspace: Path, artifacts: List[str]) -> List[Dict[str, Any]]:
    validated: List[Dict[str, Any]] = []
    workspace = workspace.resolve()
    for artifact in artifacts:
        candidate = Path(artifact)
        lexical = candidate if candidate.is_absolute() else workspace / candidate
        if lexical.is_symlink():
            raise HarnessError(f"artifact must be a non-symlink regular file: {artifact}")
        resolved = lexical.resolve()
        try:
            resolved.relative_to(workspace)
        except ValueError as exc:
            raise HarnessError(f"artifact must be inside the workspace: {artifact}") from exc
        if resolved.is_symlink() or not resolved.is_file():
            raise HarnessError(f"artifact must be a non-symlink regular file: {artifact}")
        validated.append(regular_file_metadata(resolved, workspace))
    return validated


def command_record(
    workspace: Path,
    task_id: str,
    check_id: str,
    result: str,
    summary: str,
    tool: Optional[str],
    artifacts: List[str],
) -> int:
    harness_dir, config, state = load_workspace(workspace)
    if state.get("current_task_id") != task_id:
        raise GateError(f"task {task_id} is not the current task")
    task = find_task(state, task_id)
    if task["status"] != "in_progress":
        raise GateError(f"task {task_id} is not in_progress")
    check = find_check(task, check_id)
    if check["type"] == "command":
        raise HarnessError("command acceptance must be recorded with verify")
    summary = summary.strip()
    if not summary:
        raise HarnessError("summary must not be empty")
    if check["type"] == "browser" and result == "passed":
        if not isinstance(tool, str) or not tool.strip():
            raise HarnessError("passed browser evidence requires --tool")
        if not artifacts:
            raise HarnessError("passed browser evidence requires at least one --artifact")
    validated_artifacts = validate_artifacts(workspace, artifacts)
    evidence_path, evidence_sha256 = create_evidence(
        workspace,
        harness_dir,
        task,
        check,
        result,
        summary,
        check["type"],
        tool=tool,
        artifacts=validated_artifacts,
    )
    apply_check_result(state, config, task, check, result, evidence_path, evidence_sha256)
    atomic_write_json(harness_dir / "tasks.json", state)
    refresh_handoff(workspace, harness_dir, config, state)
    print(f"Recorded {task_id}/{check_id}: {result}")
    return 0 if result == "passed" else 1


def command_complete(workspace: Path, task_id: str) -> int:
    harness_dir, config, state = load_workspace(workspace)
    if state.get("current_task_id") != task_id:
        raise GateError(f"task {task_id} is not the current task")
    task = find_task(state, task_id)
    if task["status"] != "in_progress":
        raise GateError(f"task {task_id} is not in_progress")
    not_passed = [check["id"] for check in task["acceptance"] if check["status"] != "passed"]
    if not_passed:
        raise GateError(f"acceptance checks not passed: {', '.join(not_passed)}")
    for check in task["acceptance"]:
        try:
            validate_evidence_reference(workspace, harness_dir, task, check)
        except HarnessError as exc:
            raise GateError(f"acceptance {check['id']} lacks valid evidence: {exc}") from exc
    try:
        current_snapshot = git_snapshot(workspace)
        baseline = task["git_baseline"]
        if effective_policy(task, config)["require_git_for_completion"] and not baseline["available"]:
            raise GateError("Git baseline is required for completion")
        if baseline.get("available"):
            changed_paths = changed_paths_since_baseline(workspace, baseline, current_snapshot)
            outside = sorted(
                path
                for path in changed_paths
                if not path_allowed(path, effective_policy(task, config)["allowed_paths"])
            )
            if outside:
                raise GateError(f"new changes outside allowed_paths: {', '.join(outside)}")
    except GitAuditError as exc:
        raise GateError(str(exc)) from exc
    task["status"] = "done"
    task["completed_at"] = utc_now()
    state["current_task_id"] = None
    atomic_write_json(harness_dir / "tasks.json", state)
    refresh_handoff(workspace, harness_dir, config, state)
    print(f"Completed {task_id}: {task['title']}")
    return 0


def command_unblock(workspace: Path, task_id: str, note: str) -> int:
    harness_dir, config, state = load_workspace(workspace)
    task = find_task(state, task_id)
    if task["status"] != "blocked" or state.get("current_task_id") != task_id:
        raise GateError(f"task {task_id} is not the current blocked task")
    note = note.strip()
    if not note:
        raise HarnessError("unblock note must not be empty")
    task.setdefault("unblock_history", []).append({"timestamp": utc_now(), "note": note})
    for check in task["acceptance"]:
        check["consecutive_failures"] = 0
        if check["status"] == "failed":
            check["status"] = "unverified"
            check["latest_evidence"] = None
            check["latest_evidence_sha256"] = None
    task["status"] = "in_progress"
    task.pop("blocked_at", None)
    task.pop("block_reason", None)
    atomic_write_json(harness_dir / "tasks.json", state)
    refresh_handoff(workspace, harness_dir, config, state)
    print(f"Unblocked {task_id}")
    return 0


def command_handoff(workspace: Path) -> int:
    harness_dir, config, state = load_workspace(workspace)
    refresh_handoff(workspace, harness_dir, config, state)
    print(f"Updated {harness_dir / 'HANDOFF.md'}")
    return 0


def migrated_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "max_consecutive_failures": policy["max_consecutive_failures"],
        "allowed_paths": list(policy["allowed_paths"]),
        "approval_required_operations": list(policy["approval_required_operations"]),
        "require_git_for_completion": True,
    }


def command_migrate(workspace: Path, dry_run: bool, note: Optional[str]) -> int:
    workspace = workspace.resolve()
    harness_dir = workspace / ".harness"
    source_config = read_json(harness_dir / "config.json")
    source_state = read_json(harness_dir / "tasks.json")
    versions = (source_config.get("schema_version"), source_state.get("schema_version"))
    if versions == (SCHEMA_VERSION, SCHEMA_VERSION):
        validate_config(source_config)
        validate_tasks(source_state)
        print("Harness is already schema v2.")
        return 0
    if versions != (1, 1):
        raise HarnessError("config.json and tasks.json must both be schema v1 or both be schema v2")
    validate_v1_config(source_config)
    validate_v1_tasks(source_state)
    active = next(
        (task for task in source_state.get("tasks", []) if task.get("status") in {"in_progress", "blocked"}),
        None,
    )
    clean_note = note.strip() if isinstance(note, str) else ""
    if active is not None and not clean_note:
        raise HarnessError("migrating an active or blocked v1 task requires --note")

    target_config = copy.deepcopy(source_config)
    target_config["schema_version"] = SCHEMA_VERSION
    target_config["policy"] = migrated_policy(source_config["policy"])
    target_state = copy.deepcopy(source_state)
    target_state["schema_version"] = SCHEMA_VERSION
    migration_time = utc_now()
    for task in target_state.get("tasks", []):
        status = task.get("status")
        if status in {"in_progress", "blocked"}:
            task["started_at"] = task.get("started_at") or migration_time
            task["git_baseline"] = git_snapshot(workspace)
            task["policy_baseline"] = copy.deepcopy(target_config["policy"])
            task.setdefault("migration_history", []).append(
                {"timestamp": migration_time, "from_schema": 1, "note": clean_note}
            )
        if status != "done":
            for check in task.get("acceptance", []):
                if check.get("latest_evidence") is not None:
                    check["legacy_evidence"] = {
                        "path": check.get("latest_evidence"),
                        "sha256": check.get("latest_evidence_sha256"),
                    }
                    check["latest_evidence"] = None
                    check["latest_evidence_sha256"] = None
                if check.get("status") == "passed":
                    check["status"] = "unverified"
        else:
            task["legacy_evidence"] = True
            for check in task.get("acceptance", []):
                if check.get("latest_evidence") is not None:
                    check["legacy_evidence"] = {
                        "path": check.get("latest_evidence"),
                        "sha256": check.get("latest_evidence_sha256"),
                    }
                    check["latest_evidence"] = None
                    check["latest_evidence_sha256"] = None

    validate_config(target_config)
    validate_tasks(target_state)
    legacy_evidence_files = []
    source_evidence_root = harness_dir / "evidence"
    if source_evidence_root.exists() or source_evidence_root.is_symlink():
        require_safe_directory(source_evidence_root, workspace, create=False)
        for legacy_path in sorted(source_evidence_root.rglob("*")):
            if legacy_path.is_symlink():
                raise HarnessError(f"legacy evidence must not be a symbolic link: {legacy_path}")
            if legacy_path.is_file():
                legacy_evidence_files.append(
                    {
                        "path": legacy_path.relative_to(workspace).as_posix(),
                        "size": legacy_path.stat().st_size,
                        "sha256": file_sha256(legacy_path),
                    }
                )
    if dry_run:
        print("Harness would migrate schema v1 to v2; no files changed.")
        return 0
    migration_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    migration_dir = harness_dir / "migrations" / f"v1-to-v2-{migration_stamp}"
    atomic_write_json(migration_dir / "config.v1.json", source_config)
    atomic_write_json(migration_dir / "tasks.v1.json", source_state)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "migrated_at": migration_time,
        "source_config_sha256": file_sha256(migration_dir / "config.v1.json"),
        "source_tasks_sha256": file_sha256(migration_dir / "tasks.v1.json"),
        "active_task_rebaseline_note": clean_note or None,
        "legacy_evidence_files": legacy_evidence_files,
    }
    atomic_write_json(migration_dir / "manifest.json", manifest)
    atomic_write_json(harness_dir / "config.json", target_config)
    atomic_write_json(harness_dir / "tasks.json", target_state)
    refresh_handoff(workspace, harness_dir, target_config, target_state)
    print(f"Migrated Harness schema v1 to v2; archive={migration_dir.relative_to(workspace)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor")
    subparsers.add_parser("status")
    subparsers.add_parser("next")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("command_name", choices=("setup", "start", "check"))
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("task_id", nargs="?")
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("task_id")
    record_parser.add_argument("check_id")
    record_parser.add_argument("--result", required=True, choices=("passed", "failed", "unverified"))
    record_parser.add_argument("--summary", required=True)
    record_parser.add_argument("--tool")
    record_parser.add_argument("--artifact", action="append", default=[])
    complete_parser = subparsers.add_parser("complete")
    complete_parser.add_argument("task_id")
    unblock_parser = subparsers.add_parser("unblock")
    unblock_parser.add_argument("task_id")
    unblock_parser.add_argument("--note", required=True)
    subparsers.add_parser("handoff")
    migrate_parser = subparsers.add_parser("migrate")
    migrate_parser.add_argument("--dry-run", action="store_true")
    migrate_parser.add_argument("--note")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    default_workspace = Path(__file__).resolve().parent.parent
    workspace = (args.workspace or default_workspace).resolve()
    try:
        if args.command == "doctor":
            return command_doctor(workspace)
        if args.command == "status":
            return command_status(workspace)
        if args.command == "next":
            return command_next(workspace)
        if args.command == "run":
            return command_run(workspace, args.command_name)
        if args.command == "verify":
            return command_verify(workspace, args.task_id)
        if args.command == "record":
            return command_record(
                workspace, args.task_id, args.check_id, args.result, args.summary, args.tool, args.artifact
            )
        if args.command == "complete":
            return command_complete(workspace, args.task_id)
        if args.command == "unblock":
            return command_unblock(workspace, args.task_id, args.note)
        if args.command == "handoff":
            return command_handoff(workspace)
        if args.command == "migrate":
            return command_migrate(workspace, args.dry_run, args.note)
        raise HarnessError(f"unsupported command: {args.command}")
    except HarnessError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
