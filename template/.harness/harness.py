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
    if not isinstance(policy.get("require_git_for_completion"), bool):
        raise HarnessError(f"{field}.require_git_for_completion must be a boolean")


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


def validate_git_baseline(value: Any, field: str) -> None:
    if not isinstance(value, dict):
        raise HarnessError(f"{field} must be an object")
    if value.get("version") != SCHEMA_VERSION:
        raise HarnessError(f"{field}.version must be {SCHEMA_VERSION}")
    require_string(value.get("captured_at"), f"{field}.captured_at")
    if not isinstance(value.get("available"), bool):
        raise HarnessError(f"{field}.available must be a boolean")
    for name in ("dirty_paths",):
        paths = value.get(name)
        if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
            raise HarnessError(f"{field}.{name} must be an array of strings")
    for name in ("worktree_fingerprints", "index_fingerprints"):
        fingerprints = value.get(name)
        if not isinstance(fingerprints, dict) or not all(
            isinstance(path, str) and isinstance(digest, str)
            for path, digest in fingerprints.items()
        ):
            raise HarnessError(f"{field}.{name} must be an object of string fingerprints")


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


def git_workspace_prefix(workspace: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--show-prefix"],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
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
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=workspace, text=True, capture_output=True, check=False
    )
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=workspace, text=True, capture_output=True, check=False
    )
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", "."],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )
    prefix = git_workspace_prefix(workspace)
    dirty_paths: List[str] = []
    entries = status.stdout.split("\0") if status.returncode == 0 else []
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
        "branch": branch.stdout.strip() or "DETACHED",
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "dirty_paths": unique_dirty_paths,
        "worktree_fingerprints": {
            path: workspace_path_fingerprint(workspace, path) for path in unique_dirty_paths
        },
        "index_fingerprints": {path: "legacy-unimplemented" for path in unique_dirty_paths},
    }


def workspace_path_fingerprint(workspace: Path, path: str) -> str:
    candidate = workspace / path
    try:
        if candidate.is_symlink():
            return f"symlink:{os.readlink(candidate)}"
        if candidate.is_file():
            return f"sha256:{file_sha256(candidate)}"
        if candidate.exists():
            return "other"
    except OSError as exc:
        return f"error:{exc.errno}"
    return "missing"


def git_committed_changes(workspace: Path, baseline_head: Optional[str], current_head: Optional[str]) -> List[str]:
    if baseline_head == current_head or current_head is None:
        return []
    prefix = git_workspace_prefix(workspace)
    if baseline_head is None:
        argv = ["git", "ls-tree", "-r", "--name-only", "-z", current_head]
        if prefix:
            argv.extend(["--", prefix])
    else:
        argv = ["git", "diff", "--name-only", "-z", baseline_head, current_head, "--", "."]
    result = subprocess.run(argv, cwd=workspace, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise GateError(f"could not compare Git revisions: {result.stderr.strip()}")
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
    return sorted(changed)


def path_allowed(path: str, patterns: List[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        normalized_pattern = pattern.replace("\\", "/")
        if fnmatch.fnmatchcase(normalized, normalized_pattern):
            return True
        if normalized_pattern.endswith("/**") and normalized == normalized_pattern[:-3]:
            return True
    return False


def evidence_details_for_handoff(workspace: Path, check: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    reference = check.get("latest_evidence")
    if not isinstance(reference, str) or not reference:
        return None
    try:
        evidence_path = resolve_inside(reference, workspace, "evidence path")
        evidence = read_json(evidence_path)
    except (HarnessError, OSError):
        return {"timestamp": "Invalid", "summary": "Evidence could not be read", "path": reference}
    return {
        "timestamp": evidence.get("timestamp", "Unknown"),
        "summary": evidence.get("summary", "No summary"),
        "path": reference,
    }


def historical_failures_for_handoff(harness_dir: Path) -> List[Dict[str, Any]]:
    failures = []
    evidence_root = harness_dir / "evidence"
    if not evidence_root.is_dir():
        return failures
    for evidence_path in evidence_root.glob("*/*.json"):
        try:
            evidence = read_json(evidence_path)
        except HarnessError:
            continue
        if evidence.get("result") != "failed":
            continue
        failures.append(
            {
                "task_id": evidence.get("task_id", "Unknown task"),
                "check_id": evidence.get("check_id", "Unknown check"),
                "timestamp": evidence.get("timestamp", "Unknown time"),
                "summary": evidence.get("summary", "No summary"),
            }
        )
    return sorted(failures, key=lambda item: item["timestamp"], reverse=True)[:20]


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
    historical_failures = historical_failures_for_handoff(workspace / ".harness")
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
            details = evidence_details_for_handoff(workspace, check)
            if details:
                lines.append(f"  - Evidence time: {details['timestamp']}")
                lines.append(f"  - Evidence summary: {details['summary']}")
                lines.append(f"  - Evidence path: {details['path']}")
    else:
        lines.append("None")
    lines.extend(["", "## Recently completed", ""])
    lines.extend([f"- {task['id']}: {task['title']}" for task in completed] or ["None"])
    lines.extend(["", "## Failures and blockers", ""])
    failure_lines = [f"- {task['id']}: {task.get('block_reason', 'blocked')}" for task in blocked]
    failure_lines.extend(
        f"- {task['id']}/{check['id']}: failed ({check['consecutive_failures']} consecutive)"
        for task, check in failed_checks
    )
    failure_lines.extend(
        f"- Historical failure {item['task_id']}/{item['check_id']} at {item['timestamp']}: {item['summary']}"
        for item in historical_failures
    )
    lines.extend(failure_lines or ["None"])
    lines.extend(["", "## Unverified", ""])
    lines.extend([f"- {task['id']}/{check['id']}: {check['instruction']}" for task, check in unverified_checks] or ["None"])
    lines.extend(["", "## Working tree", ""])
    if snapshot["available"]:
        lines.extend([f"- {path}" for path in snapshot["dirty_paths"]] or ["Clean"])
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
        except GateError as exc:
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
    output: Optional[str] = None,
    artifacts: Optional[List[str]] = None,
) -> tuple[str, str]:
    timestamp = utc_now()
    file_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stem = f"{file_stamp}-{check['id']}-{uuid.uuid4().hex[:8]}"
    evidence_root = (harness_dir / "evidence").resolve()
    evidence_dir = (evidence_root / task["id"]).resolve()
    try:
        evidence_dir.relative_to(evidence_root)
    except ValueError as exc:
        raise HarnessError(f"task id escapes evidence directory: {task['id']}") from exc
    evidence_dir.mkdir(parents=True, exist_ok=True)
    log_path = None
    if output is not None:
        absolute_log_path = evidence_dir / f"{stem}.log"
        absolute_log_path.write_text(output, encoding="utf-8")
        log_path = relative_path(absolute_log_path, workspace)
    evidence_path = evidence_dir / f"{stem}.json"
    evidence = {
        "evidence_id": stem,
        "task_id": task["id"],
        "check_id": check["id"],
        "timestamp": timestamp,
        "result": result,
        "method": method,
        "summary": summary,
        "tool": tool,
        "exit_code": exit_code,
        "log_path": log_path,
        "artifacts": artifacts or [],
    }
    atomic_write_json(evidence_path, evidence)
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
        if check["status"] == "passed":
            raise HarnessError(f"passed acceptance {task['id']}/{check['id']} requires valid evidence")
        return
    if not isinstance(reference, str) or not reference:
        raise HarnessError(f"latest evidence for {task['id']}/{check['id']} must be a path string")
    evidence_root = (harness_dir / "evidence" / task["id"]).resolve()
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
    log_reference = evidence.get("log_path")
    if log_reference is not None:
        if not isinstance(log_reference, str):
            raise HarnessError(f"evidence log path is invalid for {task['id']}/{check['id']}")
        log_path = resolve_inside(log_reference, workspace, "evidence log path")
        try:
            log_path.relative_to(evidence_root)
        except ValueError as exc:
            raise HarnessError(f"evidence log is outside its task directory for {task['id']}/{check['id']}") from exc
        if not log_path.is_file():
            raise HarnessError(f"evidence log does not exist: {log_reference}")
    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts):
        raise HarnessError(f"evidence artifacts are invalid for {task['id']}/{check['id']}")
    for artifact in artifacts:
        artifact_path = resolve_inside(artifact, workspace, "artifact path")
        if not artifact_path.exists():
            raise HarnessError(f"evidence artifact does not exist: {artifact}")
    if check["type"] == "command" and check["status"] == "passed" and evidence.get("exit_code") != 0:
        raise HarnessError(f"passed command evidence must have exit_code 0 for {task['id']}/{check['id']}")


def executable_available(workspace: Path, executable: str) -> bool:
    executable_path = Path(executable)
    if executable_path.is_absolute() or executable_path.parent != Path("."):
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


def run_argv(argv: List[str], workspace: Path, capture: bool) -> subprocess.CompletedProcess[str]:
    try:
        if capture:
            return subprocess.run(
                argv,
                cwd=workspace,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
        return subprocess.run(argv, cwd=workspace, text=True, check=False)
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
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
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
        output = result.stdout or ""
        if output:
            print(output, end="" if output.endswith("\n") else "\n")
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


def validate_artifacts(workspace: Path, artifacts: List[str]) -> List[str]:
    validated = []
    workspace = workspace.resolve()
    for artifact in artifacts:
        candidate = Path(artifact)
        resolved = (candidate if candidate.is_absolute() else workspace / candidate).resolve()
        try:
            relative = resolved.relative_to(workspace)
        except ValueError as exc:
            raise HarnessError(f"artifact must be inside the workspace: {artifact}") from exc
        if not resolved.exists():
            raise HarnessError(f"artifact does not exist: {artifact}")
        validated.append(relative.as_posix())
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
    active = next(
        (task for task in source_state.get("tasks", []) if task.get("status") in {"in_progress", "blocked"}),
        None,
    )
    clean_note = note.strip() if isinstance(note, str) else ""
    if active is not None and not clean_note:
        raise HarnessError("migrating an active or blocked v1 task requires --note")
    if dry_run:
        print("Harness would migrate schema v1 to v2; no files changed.")
        return 0

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
            for check in task.get("acceptance", []):
                if check.get("status") == "passed":
                    check["legacy_evidence"] = {
                        "path": check.get("latest_evidence"),
                        "sha256": check.get("latest_evidence_sha256"),
                    }
                    check["status"] = "unverified"
                    check["latest_evidence"] = None
                    check["latest_evidence_sha256"] = None
        elif status == "done":
            task["legacy_evidence"] = True

    validate_config(target_config)
    validate_tasks(target_state)
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


if __name__ == "__main__":
    raise SystemExit(main())
