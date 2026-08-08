#!/usr/bin/env python3
"""Read-only live smoke checks for local Vibe Kanban hotfix deploys."""

from __future__ import annotations

import json
import ssl
import subprocess
import sys
import urllib.request


BASE_URL = "https://vibe.local"
EXPECTED_RELEASE = (
    "/home/mcp/.local/share/vibe-kanban/frontend-dist/releases/"
    "20260626Tmultiline-rich-paste"
)
EXPECTED_ASSET = "/assets/index-DXMultilinePaste.js"
EXPECTED_ACTIVE = [
    "matchSubs",
    "BBinvoice",
    "DeNest",
    "ScrollCap",
    "oharaFIT",
    "outsource",
    "Iniandi",
    "CodexUsage",
    "VL",
    "LifeOS",
    "Operations",
    "OSTP",
    "programming",
    "ops-playbook",
    "intake-shield",
    "foxtrot-lima",
    "caspian-app",
    "hyroxready-app",
    "VK Sub-Agent Monitor",
]
EXPECTED_ARCHIVED = [
    "PostStoryboard",
    "mealPlan",
    "Monitor",
    "Monitor local",
    "virtualCard",
    "Champions Nutrition",
    "caspian-ova-dashboard",
    "vibe-kanban",
    "vibe-kanban-orchestrator",
]
EXPECTED_STATUS_NAMES = [
    "To do",
    "In progress",
    "On Hold",
    "Long Running",
    "In review",
    "Cancelled",
    "To merge",
    "In Staging",
    "Hotfix Path",
    "Done",
]
DEFAULT_COLUMN_PROJECTS = {
    "CodexUsage": "3e9a9fda-2bd6-414f-ba93-a4a7913fede0",
    "Monitor local": "0f7e902f-3f4f-4a7d-a72e-97e7e235e23a",
    "LifeOS": "855db5fd-7e2f-4217-a853-21e7cc9252a4",
    "Operations": "48c03c77-4207-48c1-86ed-686262c1116a",
}
ASSET_TOKENS = [
    "status_hotfixpath",
    "Long Running",
    "Hotfix Path",
    "Archived projects",
    "Archive",
    "Unarchive",
    "mobile-archived-projects",
    "Rename",
    "Copy code",
    "queued",
    "insertRawText",
    "u&&!d?!1",
    "if(d){f.insertRawText(c);return}",
    "vk-executor-config-selection",
    "branchNameMatchesSearch",
    "VK turn complete",
    "VK turn failed",
    "Notification.permission",
    "requestPermission",
    "vk-workspace-",
    "Enable browser notifications",
    "Chrome notification permission still needs to be enabled",
    "Chrome notification permission is enabled",
    "Chrome notification permission is blocked",
    "Send test notification",
    "VK test notification",
    "Browser notifications are working",
    "serviceWorker",
    "showNotification",
    "vk-notifications-sw.js",
]


ctx = ssl._create_unverified_context()
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    suffix = f" :: {detail}" if detail else ""
    print(f"{status} {name}{suffix}")
    if not ok:
        failures.append(f"{name}{suffix}")


def get_text(path: str) -> str:
    with urllib.request.urlopen(f"{BASE_URL}{path}", context=ctx, timeout=10) as resp:
        return resp.read().decode("utf-8", "replace")


def get_json(path: str):
    return json.loads(get_text(path))


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def main() -> int:
    release = command(
        "readlink", "-f", "/home/mcp/.local/share/vibe-kanban/frontend-dist/current"
    )
    check("frontend release", release == EXPECTED_RELEASE, release)

    pid = command("systemctl", "--user", "show", "vibe-kanban.service", "-p", "MainPID", "--value")
    check("backend process still running", pid.isdigit() and pid != "0", f"pid={pid}")

    html = get_text("/")
    check("html references expected asset", EXPECTED_ASSET in html, EXPECTED_ASSET)
    asset = get_text(EXPECTED_ASSET)
    for token in ASSET_TOKENS:
        check(f"asset contains {token}", token in asset)

    projects = get_json("/api/projects")["data"]
    active = [project["name"] for project in projects if not project["archived"]]
    archived = [project["name"] for project in projects if project["archived"]]
    check("active project order", active == EXPECTED_ACTIVE, " | ".join(active))
    check("archived project order", archived == EXPECTED_ARCHIVED, " | ".join(archived))

    for project_name, project_id in DEFAULT_COLUMN_PROJECTS.items():
        data = get_json(f"/v1/fallback/project_statuses?project_id={project_id}")
        statuses = data.get("project_statuses", data)
        names = [status["name"] for status in statuses]
        check(f"default columns {project_name}", names == EXPECTED_STATUS_NAMES, ", ".join(names))

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
