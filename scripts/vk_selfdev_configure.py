#!/usr/bin/env python3
import argparse
import json
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path("/home/mcp/.local/share/vibe-kanban/db.v2.sqlite")
BACKUP_ROOT = Path("/home/mcp/backups")
VK_REPO_PATH = "/home/mcp/_vibe_kanban_repo"
VK_REPO_NAME = "_vibe_kanban_repo"
VK_REPO_DISPLAY = "vibe-kanban"
LEGACY_PROJECT_NAME = "vibe-kanban"
NEW_PROJECT_NAME = "VK Dev"
DEFAULT_BRANCH = "staging"
SETUP_SCRIPT = "bash /home/mcp/_vibe_kanban_repo/scripts/vk_selfdev_guard.sh"
DEV_SERVER_SCRIPT = "pnpm run preview:light"
UI_PREFERENCES_ID = "00000000-0000-0000-0000-000000000001"
VK_DEV_ABBREVIATION = "VK"
VK_DEV_COLOR = "170 45% 82%"

STATUS_TEMPLATE = [
    {"id": "todo", "name": "To do", "color": "220 70% 52%", "hidden": False, "sort_order": 0},
    {"id": "in_progress", "name": "In progress", "color": "42 90% 55%", "hidden": False, "sort_order": 1},
    {"id": "status_onhold", "name": "On Hold", "color": "220 70% 52%", "hidden": False, "sort_order": 2},
    {"id": "status_longrunning", "name": "Long Running", "color": "220 70% 52%", "hidden": False, "sort_order": 3},
    {"id": "in_review", "name": "In review", "color": "280 55% 58%", "hidden": False, "sort_order": 4},
    {"id": "cancelled", "name": "Cancelled", "color": "0 0% 55%", "hidden": True, "sort_order": 5},
    {"id": "status_tomerge", "name": "To merge", "color": "220 70% 52%", "hidden": False, "sort_order": 6},
    {"id": "in_staging", "name": "In Staging", "color": "196 72% 47%", "hidden": False, "sort_order": 7},
    {"id": "status_hotfixpath", "name": "Hotfix Path", "color": "220 70% 52%", "hidden": False, "sort_order": 8},
    {"id": "done", "name": "Done", "color": "145 55% 42%", "hidden": False, "sort_order": 9},
]


def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def uuid_blob(value: str) -> bytes:
    return uuid.UUID(value).bytes


def blob_uuid(value: bytes | None) -> str | None:
    if value is None:
        return None
    return str(uuid.UUID(bytes=value))


def dict_rows(rows):
    out = []
    for row in rows:
        item = {}
        for key in row.keys():
            value = row[key]
            if key.endswith("id") and isinstance(value, bytes) and len(value) == 16:
                item[key] = blob_uuid(value)
            else:
                item[key] = value
        out.append(item)
    return out


def fetch_one(conn, query, params=()):
    row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def find_repo(conn):
    return fetch_one(
        conn,
        "select * from repos where path = ? or name = ? order by updated_at desc limit 1",
        (VK_REPO_PATH, VK_REPO_NAME),
    )


def find_project(conn, name):
    return fetch_one(conn, "select * from projects where name = ? order by updated_at desc limit 1", (name,))


def scratch_payload(repo_id: str) -> str:
    return json.dumps(
        {
            "type": "PROJECT_REPO_DEFAULTS",
            "data": {
                "repos": [{"repo_id": repo_id, "target_branch": DEFAULT_BRANCH}],
                "statuses": STATUS_TEMPLATE,
            },
        },
        separators=(",", ":"),
    )


def ui_preferences_payload(existing_payload: str | None, project_id: str) -> str:
    if existing_payload:
        try:
            payload = json.loads(existing_payload)
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}

    data = payload.setdefault("data", {})
    payload["type"] = "UI_PREFERENCES"

    current_order = data.get("local_project_order")
    if not isinstance(current_order, list):
        current_order = []

    data["local_project_order"] = [
        project_id,
        *[item for item in current_order if item != project_id],
    ]

    customizations = data.get("local_project_customizations")
    if not isinstance(customizations, dict):
        customizations = {}
    customizations[project_id] = {
        "abbreviation": VK_DEV_ABBREVIATION,
        "color": VK_DEV_COLOR,
    }
    data["local_project_customizations"] = customizations

    return json.dumps(payload, separators=(",", ":"))


def backup_rows(conn, backup_dir: Path):
    backup_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(DB_PATH, backup_dir / "db.v2.sqlite")

    conn.row_factory = sqlite3.Row
    repo = find_repo(conn)
    repo_id = repo["id"] if repo else None

    projects = conn.execute(
        "select * from projects where name in (?, ?) or default_agent_working_dir = ? order by name",
        (LEGACY_PROJECT_NAME, NEW_PROJECT_NAME, VK_REPO_PATH),
    ).fetchall()
    project_ids = [row["id"] for row in projects]

    project_repos = []
    scratches = []
    if project_ids:
        placeholders = ",".join("?" for _ in project_ids)
        project_repos = conn.execute(
            f"select * from project_repos where project_id in ({placeholders})", project_ids
        ).fetchall()
        scratches = conn.execute(
            f"""
            select * from scratch
             where id in ({placeholders})
                or id = ?
                or lower(payload) like '%vibe-kanban%'
                or lower(payload) like '%_vibe_kanban_repo%'
            """,
            [*project_ids, uuid_blob(UI_PREFERENCES_ID)],
        ).fetchall()

    rows = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(DB_PATH),
        "repo": dict_rows([repo]) if repo else [],
        "projects": dict_rows(projects),
        "project_repos": dict_rows(project_repos),
        "scratch": dict_rows(scratches),
    }
    (backup_dir / "vk-selfdev-rows.json").write_text(json.dumps(rows, indent=2) + "\n")
    return rows


def configure(conn, mode: str):
    repo = find_repo(conn)
    if not repo:
        repo_id = uuid.uuid4()
        conn.execute(
            """
            insert into repos (
              id, path, name, display_name, setup_script, cleanup_script, copy_files,
              parallel_setup_script, dev_server_script, default_target_branch,
              default_working_dir, archive_script
            ) values (?, ?, ?, ?, ?, null, null, 0, ?, ?, null, null)
            """,
            (repo_id.bytes, VK_REPO_PATH, VK_REPO_NAME, VK_REPO_DISPLAY, SETUP_SCRIPT, DEV_SERVER_SCRIPT, DEFAULT_BRANCH),
        )
        repo = find_repo(conn)
    else:
        conn.execute(
            """
            update repos
               set display_name = ?,
                   setup_script = ?,
                   parallel_setup_script = 0,
                   dev_server_script = ?,
                   default_target_branch = ?,
                   updated_at = datetime('now', 'subsec')
             where id = ?
            """,
            (VK_REPO_DISPLAY, SETUP_SCRIPT, DEV_SERVER_SCRIPT, DEFAULT_BRANCH, repo["id"]),
        )

    repo_id = blob_uuid(repo["id"])

    if mode == "repair":
        project = find_project(conn, LEGACY_PROJECT_NAME)
        if not project:
            raise RuntimeError("repair mode requested, but legacy vibe-kanban project was not found")
        project_id = blob_uuid(project["id"])
        conn.execute(
            """
            update projects
               set archived = 0,
                   default_agent_working_dir = ?,
                   updated_at = datetime('now', 'subsec')
             where id = ?
            """,
            (VK_REPO_PATH, project["id"]),
        )
    else:
        project = find_project(conn, NEW_PROJECT_NAME)
        if project:
            project_id = blob_uuid(project["id"])
            conn.execute(
                """
                update projects
                   set archived = 0,
                       default_agent_working_dir = ?,
                       updated_at = datetime('now', 'subsec')
                 where id = ?
                """,
                (VK_REPO_PATH, project["id"]),
            )
        else:
            project_uuid = uuid.uuid4()
            project_id = str(project_uuid)
            conn.execute(
                """
                insert into projects (id, name, remote_project_id, default_agent_working_dir, archived)
                values (?, ?, null, ?, 0)
                """,
                (project_uuid.bytes, NEW_PROJECT_NAME, VK_REPO_PATH),
            )

    project_blob = uuid_blob(project_id)
    repo_blob = uuid_blob(repo_id)

    conn.execute(
        "delete from project_repos where project_id = ? and repo_id = ?",
        (project_blob, repo_blob),
    )
    conn.execute(
        "insert into project_repos (id, project_id, repo_id) values (?, ?, ?)",
        (uuid.uuid4().bytes, project_blob, repo_blob),
    )
    conn.execute(
        """
        insert into scratch (id, scratch_type, payload)
        values (?, 'PROJECT_REPO_DEFAULTS', ?)
        on conflict(id, scratch_type) do update
            set payload = excluded.payload,
                updated_at = datetime('now', 'subsec')
        """,
        (project_blob, scratch_payload(repo_id)),
    )
    ui_preferences = conn.execute(
        "select payload from scratch where id = ? and scratch_type = 'UI_PREFERENCES'",
        (uuid_blob(UI_PREFERENCES_ID),),
    ).fetchone()
    conn.execute(
        """
        insert into scratch (id, scratch_type, payload)
        values (?, 'UI_PREFERENCES', ?)
        on conflict(id, scratch_type) do update
            set payload = excluded.payload,
                updated_at = datetime('now', 'subsec')
        """,
        (
            uuid_blob(UI_PREFERENCES_ID),
            ui_preferences_payload(
                ui_preferences["payload"] if ui_preferences else None,
                project_id,
            ),
        ),
    )

    return {
        "mode": mode,
        "project_id": project_id,
        "project_name": LEGACY_PROJECT_NAME if mode == "repair" else NEW_PROJECT_NAME,
        "repo_id": repo_id,
        "repo_path": VK_REPO_PATH,
        "default_branch": DEFAULT_BRANCH,
        "setup_script": SETUP_SCRIPT,
        "dev_server_script": DEV_SERVER_SCRIPT,
    }


def snapshot(conn):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        select lower(hex(p.id)) project_id, p.name project_name, p.archived,
               p.default_agent_working_dir,
               lower(hex(r.id)) repo_id, r.path repo_path, r.default_target_branch,
               r.setup_script, r.dev_server_script
          from projects p
          left join project_repos pr on pr.project_id = p.id
          left join repos r on r.id = pr.repo_id
         where p.name in (?, ?)
         order by p.name
        """,
        (LEGACY_PROJECT_NAME, NEW_PROJECT_NAME),
    ).fetchall()
    return [dict(row) for row in rows]


def main():
    global DB_PATH

    parser = argparse.ArgumentParser(description="Configure a clean VK self-development project.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--backup-root", type=Path, default=BACKUP_ROOT)
    parser.add_argument("--mode", choices=("new", "repair"), default="new")
    parser.add_argument("--apply", action="store_true", help="Actually write changes. Default is dry-run.")
    args = parser.parse_args()

    if args.db != DB_PATH:
        DB_PATH = args.db

    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")

    backup_dir = args.backup_root / f"vk-selfdev-config-{utc_ts()}"
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    backup = backup_rows(conn, backup_dir)
    result = {"backup_dir": str(backup_dir), "before": snapshot(conn), "backup": backup}

    if args.apply:
        with conn:
            applied = configure(conn, args.mode)
        result["applied"] = applied
        result["after"] = snapshot(conn)
    else:
        result["dry_run"] = True
        result["would_apply"] = {
            "mode": args.mode,
            "project_name": LEGACY_PROJECT_NAME if args.mode == "repair" else NEW_PROJECT_NAME,
            "repo_path": VK_REPO_PATH,
            "default_branch": DEFAULT_BRANCH,
            "setup_script": SETUP_SCRIPT,
            "dev_server_script": DEV_SERVER_SCRIPT,
        }

    (backup_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "backup"}, indent=2))


if __name__ == "__main__":
    main()
