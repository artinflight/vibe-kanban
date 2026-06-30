#!/usr/bin/env python3
"""Small live smoke for the local Vibe Kanban deployment.

This script is intentionally read-only. It checks invariants that have regressed
in previous local deploys without restarting the service or mutating the DB.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_URL = os.environ.get("VK_SMOKE_BASE_URL", "https://vibe.local").rstrip("/")
TIMEOUT = float(os.environ.get("VK_SMOKE_TIMEOUT", "5"))
PASTE_PLUGIN_SOURCE = Path("packages/ui/src/components/PasteMarkdownPlugin.tsx")


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def request(path: str) -> tuple[int, Any, bytes]:
    url = f"{BASE_URL}{path}"
    request_obj = urllib.request.Request(url, headers={"Accept": "application/json"})
    context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(request_obj, timeout=TIMEOUT, context=context) as response:
            body = response.read()
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return response.status, json.loads(body.decode("utf-8")), body
            return response.status, None, body
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            parsed = json.loads(body.decode("utf-8"))
        except Exception:
            parsed = None
        return exc.code, parsed, body


def ok(name: str, detail: str) -> Check:
    return Check(name, True, detail)


def fail(name: str, detail: str) -> Check:
    return Check(name, False, detail)


def unwrap_api_data(data: Any) -> Any:
    if isinstance(data, dict) and data.get("success") is True and "data" in data:
        return data["data"]
    return data


def check_info() -> Check:
    status, data, _ = request("/api/info")
    data = unwrap_api_data(data)
    if status != 200 or not isinstance(data, dict):
        return fail("api info", f"expected JSON 200, got {status}")

    shared_api_base = data.get("shared_api_base")
    login_status = data.get("login_status")
    if isinstance(login_status, dict):
        login_status = login_status.get("status")
    if shared_api_base is not None:
        return fail("api info", f"shared_api_base is {shared_api_base!r}, expected null")
    if login_status != "loggedin":
        return fail("api info", f"login_status is {login_status!r}, expected loggedin")
    return ok("api info", "local-only install is logged in with no shared API base")


def check_projects() -> Check:
    status, data, _ = request("/api/projects")
    data = unwrap_api_data(data)
    if status != 200 or not isinstance(data, list):
        return fail("projects", f"expected JSON list 200, got {status}")

    active_names = [project.get("name") for project in data if not project.get("archived")]
    archived_names = [project.get("name") for project in data if project.get("archived")]
    vk_dev_count = active_names.count("VK Dev")
    if vk_dev_count != 1:
        return fail("projects", f"active VK Dev count is {vk_dev_count}, expected 1")
    if "vibe-kanban" in active_names:
        return fail("projects", "archived vibe-kanban history is active again")
    return ok(
        "projects",
        f"active VK Dev present once; archived projects visible in API: {len(archived_names)}",
    )


def check_index() -> Check:
    status, _, body = request("/")
    if status != 200:
        return fail("frontend", f"expected index 200, got {status}")
    if b"/assets/index-" not in body:
        return fail("frontend", "index did not reference a built asset")
    return ok("frontend", "index loaded and references built assets")


def check_paste_plugin_source() -> Check:
    if not PASTE_PLUGIN_SOURCE.exists():
        return fail("paste source", f"{PASTE_PLUGIN_SOURCE} is missing")
    source = PASTE_PLUGIN_SOURCE.read_text()
    required = [
        "COMMAND_PRIORITY_HIGH",
        "LINE_BREAK_PATTERN.test(plainText)",
        "selection.insertRawText(plainText)",
        "htmlText && !shouldInsertMultilineRaw",
    ]
    missing = [token for token in required if token not in source]
    if missing:
        return fail("paste source", f"missing {', '.join(missing)}")
    if "COMMAND_PRIORITY_LOW" in source:
        return fail("paste source", "paste handler still uses COMMAND_PRIORITY_LOW")
    return ok("paste source", "multiline rich paste guard runs at high priority")


def main() -> int:
    checks = [
        check_info(),
        check_projects(),
        check_index(),
        check_paste_plugin_source(),
    ]
    for check in checks:
        prefix = "PASS" if check.passed else "FAIL"
        print(f"{prefix} {check.name}: {check.detail}")

    failed = [check for check in checks if not check.passed]
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
