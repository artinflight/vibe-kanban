"""Refresh only isolated reader metadata. The authoritative database is read-only."""
import json
import pathlib
import sqlite3
import sys
import uuid


def prepare(primary, replica, root, process_id):
    key = uuid.UUID(process_id).bytes
    if pathlib.Path(primary).resolve() == pathlib.Path(replica).resolve():
        raise ValueError("Reader DB must be separate")
    if not pathlib.Path(replica).resolve().is_relative_to(pathlib.Path(root).resolve()):
        raise ValueError("Reader DB must be inside the isolated root")
    live = sqlite3.connect(pathlib.Path(primary).resolve().as_uri() + "?mode=ro", uri=True)
    live.row_factory = sqlite3.Row
    live.execute("BEGIN")
    process = live.execute("SELECT * FROM execution_processes WHERE id=?", (key,)).fetchone()
    if not process or process["status"] != "completed" or process["dropped"]:
        live.close()
        return False
    action = json.loads(process["executor_action"])
    if action.get("typ", {}).get("executor_config", {}).get("executor") != "CODEX":
        live.close()
        return False
    session = live.execute("SELECT * FROM sessions WHERE id=?", (process["session_id"],)).fetchone()
    workspace = live.execute("SELECT * FROM workspaces WHERE id=?", (session["workspace_id"],)).fetchone()
    if not workspace:
        live.close()
        return False
    rows = [("workspaces", dict(workspace)), ("sessions", dict(session)),
            ("execution_processes", dict(process))]
    live.close()
    # Never give this auxiliary server a real workspace or agent working directory.
    rows[0][1]["container_ref"] = str(pathlib.Path(root) / "workspaces" / str(uuid.UUID(bytes=workspace["id"])))
    rows[1][1]["agent_working_dir"] = None
    with sqlite3.connect(replica, timeout=3) as copy:
        copy.execute("PRAGMA foreign_keys=ON")
        for table, row in rows:
            columns = list(row)
            names = ",".join('"' + name + '"' for name in columns)
            updates = ",".join('"' + name + '"=excluded."' + name + '"' for name in columns if name != "id")
            copy.execute(f'INSERT INTO "{table}" ({names}) VALUES ({",".join("?" for _ in columns)}) '
                         f'ON CONFLICT(id) DO UPDATE SET {updates}', list(row.values()))
    return True


if __name__ == "__main__":
    print("ready" if prepare(*sys.argv[1:]) else "primary")
