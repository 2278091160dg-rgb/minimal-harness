#!/usr/bin/env python3
"""Publish a completed Minimal Harness result through the GitHub Checks API."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Sequence
from urllib.parse import urlsplit


API_VERSION = "2022-11-28"
MAX_SUMMARY_CHARACTERS = 65535
MAX_RESPONSE_BYTES = 65536
REPOSITORY_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*\Z"
)
SHA_PATTERN = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


class PublisherError(Exception):
    exit_code = 2


class GitHubAPIError(PublisherError):
    exit_code = 1


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise PublisherError(f"{name} is required")
    return value


def validate_api_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise PublisherError("GITHUB_API_URL must not contain credentials, query, or fragment")
    if parsed.scheme == "https" and parsed.hostname:
        return value.rstrip("/")
    if parsed.scheme == "http" and parsed.hostname:
        if parsed.hostname == "localhost":
            return value.rstrip("/")
        try:
            if ipaddress.ip_address(parsed.hostname).is_loopback:
                return value.rstrip("/")
        except ValueError:
            pass
    raise PublisherError("GITHUB_API_URL must use HTTPS, except for a loopback test server")


def read_summary(path_value: str) -> str:
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        raise PublisherError("summary must be a non-symlink regular file")
    try:
        summary = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PublisherError(f"could not read UTF-8 summary: {exc}") from exc
    if not summary.strip():
        raise PublisherError("summary must not be empty")
    if len(summary) > MAX_SUMMARY_CHARACTERS:
        raise PublisherError(
            f"summary must be at most {MAX_SUMMARY_CHARACTERS} characters"
        )
    return summary


def build_payload(
    sha: str,
    conclusion: str,
    title: str,
    summary: str,
) -> bytes:
    payload = {
        "name": "Minimal Harness",
        "head_sha": sha,
        "status": "completed",
        "conclusion": conclusion,
        "output": {"title": title, "summary": summary},
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def publish_check(
    *,
    api_url: str,
    repository: str,
    token: str,
    payload: bytes,
) -> Dict[str, object]:
    url = f"{api_url}/repos/{repository}/check-runs"
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "minimal-harness-check-publisher",
            "X-GitHub-Api-Version": API_VERSION,
        },
    )
    opener = urllib.request.build_opener(NoRedirectHandler())
    try:
        with opener.open(request, timeout=20) as response:
            response_body = response.read(MAX_RESPONSE_BYTES + 1)
            status = response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read(MAX_RESPONSE_BYTES + 1).decode("utf-8", errors="replace").strip()
        raise GitHubAPIError(f"GitHub API returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GitHubAPIError(f"GitHub API request failed: {exc}") from exc
    if status != 201:
        detail = response_body.decode("utf-8", errors="replace").strip()
        raise GitHubAPIError(f"GitHub API returned HTTP {status}: {detail}")
    if len(response_body) > MAX_RESPONSE_BYTES:
        raise GitHubAPIError("GitHub API response exceeded the size limit")
    try:
        value = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GitHubAPIError("GitHub API returned an invalid JSON response") from exc
    if not isinstance(value, dict) or not isinstance(value.get("id"), int):
        raise GitHubAPIError("GitHub API response is missing the check run id")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--conclusion",
        required=True,
        choices=("success", "failure", "neutral", "cancelled", "timed_out", "action_required"),
    )
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary-file", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        token = required_environment("GITHUB_TOKEN")
        repository = required_environment("GITHUB_REPOSITORY")
        sha = required_environment("GITHUB_SHA")
        if REPOSITORY_PATTERN.fullmatch(repository) is None:
            raise PublisherError("GITHUB_REPOSITORY must be owner/repository")
        if SHA_PATTERN.fullmatch(sha) is None:
            raise PublisherError("GITHUB_SHA must be a full Git object id")
        title = args.title.strip()
        if not title or len(title) > 255:
            raise PublisherError("title must contain 1-255 characters")
        summary = read_summary(args.summary_file)
        api_url = validate_api_url(os.environ.get("GITHUB_API_URL", "https://api.github.com"))
        response = publish_check(
            api_url=api_url,
            repository=repository,
            token=token,
            payload=build_payload(sha, args.conclusion, title, summary),
        )
        destination = response.get("html_url") or f"check run {response['id']}"
        print(f"Published Minimal Harness check: {destination}")
        return 0
    except PublisherError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
