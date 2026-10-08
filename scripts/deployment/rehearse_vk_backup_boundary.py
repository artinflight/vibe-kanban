#!/usr/bin/env python3
"""Exercise a rolling backup through existing handover primitives in private VK units."""

import argparse
import importlib
import json
import os
from pathlib import Path
import secrets
import shlex
import socket
import sqlite3
import subprocess
import sys
import time
import uuid

from vk_change_journal import Journal
from vk_prep_common import digest, save, storage
from vk_rolling_backup import capture, mirror_desktop, restore_chain
from vk_archive_store import configure_transport
from vk_desktop_transport import DesktopTransport


def require(condition, message):
    if not condition:
        raise ValueError(message)


def desktop_restore(result, root, destination, *, hostname=None, host_key_alias=None,
                    low_peak=False):
    """Retrieve authenticated metadata; compressed payloads stay on Desktop."""
    downloaded = root / 'desktop-metadata'
    downloaded.mkdir()
    receipt = result['metadata_receipt']
    name = receipt['name']
    require(Path(name).name == name and name not in ('', '.', '..'), 'Unsafe metadata name')
    transport = DesktopTransport(root / 'metadata-transport', hostname=hostname,
                                 host_key_alias=host_key_alias)
    subprocess.run(['scp', *transport.options,
                    'desktop:' + receipt['desktop_directory'] + '/' + name,
                    str(downloaded)], check=True, timeout=120)
    require(digest(downloaded / name) == receipt['sha256'],
            'Desktop recovery metadata download changed')
    descriptor = json.loads((downloaded / name).read_text())
    restored = restore_chain(descriptor, destination, desktop_only=True,
                             retire_verified_snapshots=low_peak)
    return descriptor, restored


def ports():
    reservations, result = [], []
    try:
        for _ in range(2):
            while True:
                first = socket.socket()
                first.bind(("127.0.0.1", 0))
                port = first.getsockname()[1]
                second = socket.socket()
                try:
                    second.bind(("127.0.0.1", port + 1))
                except (OSError, OverflowError):
                    first.close()
                    second.close()
                    continue
                reservations.extend([first, second])
                result.append(port)
                break
        return result
    finally:
        for connection in reservations:
            connection.close()


def launch_command(runtime, release, port, standby):
    args = ["/home/mcp/.local/bin/bwrap", "--die-with-parent", "--new-session", "--unshare-pid",
            "--unshare-ipc", "--unshare-uts", "--tmpfs", "/", "--ro-bind", "/usr", "/usr",
            "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64", "--ro-bind", "/etc", "/etc",
            "--proc", "/proc", "--dev", "/dev", "--bind", str(runtime), "/green",
            "--bind", str(runtime / "tmp"), "/tmp", "--ro-bind", str(release), "/release",
            "--chdir", "/green", "--clearenv"]
    environment = {"HOME": "/green/home", "XDG_DATA_HOME": "/green/xdg", "XDG_CONFIG_HOME": "/green/config",
                   "XDG_CACHE_HOME": "/green/cache", "CODEX_HOME": "/green/codex-home", "TMPDIR": "/tmp",
                   "PATH": "/usr/bin:/bin", "HOST": "127.0.0.1", "PORT": str(port), "BACKEND_PORT": str(port),
                   "PREVIEW_PROXY_PORT": str(port + 1), "VK_FRONTEND_DIST_DIR": "/release/frontend",
                   "VK_ALLOWED_ORIGINS": "http://127.0.0.1:" + str(port), "VK_DISABLE_AUTH": "1",
                   "DISABLE_ATTACHMENT_CLEANUP": "1", "DISABLE_WORKTREE_CLEANUP": "1",
                   "DISABLE_STATUS_WORKTREE_CLEANUP": "1", "VK_DISABLE_PR_MONITOR": "1",
                   "VK_USE_SYSTEMD_RUN": "0", "VK_CODEX_BASE_COMMAND": "/bin/false", "BROWSER": "/bin/true",
                   "RUST_LOG": "info", "VK_CAPACITY_STATE_DIR": "/green/capacity-controller",
                   "VK_CAPACITY_GUARD": "/release/vk-capacity-guard", "VK_CAPACITY_TOKEN_FILE": "/green/capacity.token",
                   "VK_CAPACITY_MODEL_PROVIDER": "fixture", "VK_CAPACITY_BUILD_ROOTS": '["/green/capacity-build"]',
                   "VK_CAPACITY_START_PAUSED": "1" if standby else "0"}
    for name, value in environment.items():
        args.extend(["--setenv", name, value])
    return args


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--handover-directory", required=True, type=Path)
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--desktop-directory", required=True)
    parser.add_argument('--desktop-hostname')
    parser.add_argument('--desktop-host-key-alias')
    parser.add_argument('--low-peak-restore', action='store_true')
    args = parser.parse_args()
    configure_transport(args.desktop_hostname, args.desktop_host_key_alias)
    os.umask(0o077)
    root = storage(args.root) / ("handover-" + uuid.uuid4().hex)
    root.mkdir(parents=True)
    legacy, release = args.handover_directory.resolve(), args.release.resolve()
    sys.path.insert(0, str(legacy))
    handover = importlib.import_module("ownership_handover")
    runtime = root / "runtime"
    for name in ("home", "xdg/vibe-kanban", "config", "cache/utils/attachments", "codex-home", "tmp",
                 "worktrees", "capacity-controller", "capacity-build"):
        (runtime / name).mkdir(parents=True)
    config_file = runtime / "xdg/vibe-kanban/config.json"
    initial = json.loads((legacy / "runtime/xdg/vibe-kanban/config.json").read_text())
    initial.update(analytics_enabled=False, relay_enabled=False, workspace_dir="/green/worktrees",
                   host_nickname="Private preparation rehearsal")
    initial["github"] = {key: None for key in initial["github"]}
    initial["notifications"].update(sound_enabled=False, push_enabled=False)
    save(config_file, initial)
    save(config_file.with_name("profiles.json"), {"executors": {}})
    (runtime / "capacity.token").write_text(secrets.token_hex(32) + "\n")
    history = runtime / "codex-home/rollout-original.jsonl"
    history.write_text('{"thread":"original-fixture","turn":1}\n')
    dirty = runtime / "worktrees/uncommitted.txt"
    dirty.write_text("original uncommitted work")
    attachment = runtime / "cache/utils/attachments/preserved.bin"
    attachment.write_bytes(b"preserved attachment fixture")
    attachment.chmod(0o640)
    native_db = runtime / "codex-home/goal-fixture.sqlite"
    with sqlite3.connect(native_db) as db:
        db.execute("CREATE TABLE goals (thread TEXT, checkpoint TEXT)")
        db.execute("INSERT INTO goals VALUES ('original-fixture', 'before snapshot')")
    suffix = uuid.uuid4().hex[:12]
    units = {role: "vk-prep-rehearsal-" + suffix + "-" + role + ".service"
             for role in ("incumbent", "candidate")}
    incumbent_port, candidate_port = ports()
    configuration = {**units, "incumbent_policy": "ownership-release-pause",
                     "incumbent_port": incumbent_port, "candidate_port": candidate_port,
                     "incumbent_color": "green", "candidate_color": "blue",
                     "capacity_token": str(runtime / "capacity.token"),
                     "capacity_root": str(runtime / "capacity-controller"),
                     "database": str(runtime / "xdg/vibe-kanban/db.v2.sqlite"),
                     "incumbent_defaults": str(legacy / "source/crates/executors/default_profiles.json"),
                     "route": str(root / "route.json"), "receipt_directory": str(root),
                     "frontend_pointer": str(root / "frontend"), "candidate_frontend": str(release / "frontend")}
    (root / "frontend").symlink_to(release / "frontend")
    handover.route(configuration, "incumbent")
    real_ctl = handover.ctl

    def private_ctl(action, unit):
        require(unit in units.values(), "Refusing action on a non-rehearsal service")
        return real_ctl(action, unit)

    handover.ctl = private_ctl
    journal = None
    definitions = []
    result = {"passed": False, "production_modified": False, "cutover_authorized": False,
              "root": str(root), "units": units, "cases": [],
              "server_sha256": digest(release / "server"),
              "handover_sha256": digest(legacy / "ownership_handover.py"),
              "tool_sha256": {name: digest(Path(__file__).with_name(name)) for name in
                              ("vk_rolling_backup.py", "vk_change_journal.py", "vk_prep_common.py",
                               "rehearse_vk_backup_boundary.py")}}
    try:
        for role in ("incumbent", "candidate"):
            port = configuration[role + "_port"]
            command = launch_command(runtime, release, port, role == "candidate")
            isolation = subprocess.check_output(command + ["/bin/sh", "-c",
                "test ! -e /home/mcp && test ! -e /mnt/vk-storage && test ! -e /run/user/1000/bus && echo isolated"], text=True)
            require(isolation.strip() == "isolated", "Private runtime isolation failed")
            definition = Path.home() / ".config/systemd/user" / units[role]
            require(not definition.exists(), "Private service name already exists")
            definition.write_text("[Service]\nType=exec\nRestart=no\nKillMode=control-group\nExecStart=" +
                                  shlex.join(command + ["/release/server"]) + "\n")
            definitions.append(definition)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        private_ctl("start", units["incumbent"])
        handover.wait_api(incumbent_port, time.monotonic() + 30)
        pid = handover.prop(units["incumbent"], "MainPID")

        def message(port, name):
            handover.api(port, "saved-chat-messages/" + name,
                         {"id": name, "title": name, "content": "preserve " + name, "position": 1}, "PUT")

        message(incumbent_port, "before-checkpoint")
        plan = {"sources": [str(runtime)], "sqlite_snapshots": [configuration["database"], str(native_db)],
                "excluded_rebuildable_directories": [str(runtime / "tmp")]}
        journal = Journal(plan)
        journal.tree(runtime)
        journal.ready = True
        mirror = lambda path: mirror_desktop(path, args.desktop_directory)
        parent = capture(plan, root / "backups", journal.report, mirror, publish=mirror)
        message(incumbent_port, "after-checkpoint")
        dirty.write_text("work continued after the online snapshot")
        with history.open("a") as output:
            output.write('{"thread":"original-fixture","turn":2}\n')
        with sqlite3.connect(native_db) as db:
            db.execute("UPDATE goals SET checkpoint='latest goal and model choice'")

        def fence():
            require(handover.prop(units["incumbent"], "MainPID") == pid, "Original process changed")
            require(handover.prop(units["incumbent"], "FreezerState") == "frozen", "Writer is not paused")
            require(handover.prop(units["candidate"], "MainPID") == "0", "Candidate has started too early")
            receipt = json.loads((root / "incumbent-released.json").read_text())
            require(receipt["owned"] is False and receipt["pid"] == pid, "Missing ownership release receipt")
            return {"verified": True, "incumbent_pid": pid, "candidate_stopped": True,
                    "released": True, "process_start": Path("/proc", pid, "stat").read_text().rpartition(") ")[2].split()[19]}

        def rejected_boundary():
            return capture(plan, root / "backups", journal.report,
                           lambda archive: {"desktop_verified": False, "sha256": digest(archive)},
                           parent, mirror, verify_fence=fence)

        try:
            handover.switch(configuration, rejected_boundary, lambda role: None)
        except ValueError as error:
            require("delivery is unverified" in str(error), "Unexpected backup failure: " + str(error))
        else:
            raise ValueError("Unverified backup failed to abort handover")
        require(handover.prop(units["incumbent"], "MainPID") == pid, "Backup abort replaced original process")
        require(handover.ownership(configuration, "incumbent")["owned"], "Ownership not recovered")
        result["cases"].append("Failed backup returns the same original process without database restoration")
        boundary_result = None

        def boundary():
            nonlocal boundary_result
            boundary_result = capture(plan, root / "backups", journal.report, mirror, parent, mirror, verify_fence=fence)
            return boundary_result

        before, timings = handover.switch(configuration, boundary, lambda role: None)
        require(json.loads((root / "route.json").read_text())["mode"] == "blue", "Private route did not switch")
        require(any(row["id"] == "after-checkpoint" for row in handover.api(candidate_port, "saved-chat-messages")),
                "Final catch-up lost a saved message")
        result["cases"].append("Verified rolling boundary is accepted by the existing handover with latest data")
        message(candidate_port, "new-work-on-candidate")
        settings = handover.api(candidate_port, "info")["config"]
        settings["theme"] = "DARK"
        handover.api(candidate_port, "config", settings, "PUT")
        profiles = json.loads(handover.api(candidate_port, "profiles")["content"])
        profiles["executors"]["CODEX"]["DEFAULT"]["CODEX"]["model"] = "gpt-6.1-sol"
        handover.api(candidate_port, "profiles", profiles, "PUT")
        handover.recovery(configuration, before, lambda role: None)
        require(handover.prop(units["incumbent"], "MainPID") == pid, "Cutback replaced original process")
        require(any(row["id"] == "new-work-on-candidate" for row in handover.api(incumbent_port, "saved-chat-messages")),
                "Cutback lost new saved message")
        require(handover.api(incumbent_port, "info")["config"]["theme"] == "DARK", "Cutback lost settings")
        actual_profiles = json.loads(handover.api(incumbent_port, "profiles")["content"])
        require(actual_profiles["executors"]["CODEX"]["DEFAULT"]["CODEX"]["model"] == "gpt-6.1-sol",
                "Cutback lost model choice")
        result["cases"].append("Same-process cutback preserves writes and model/settings changes made after handover")
        handover.recovery(configuration, before, lambda role: None)
        result["cases"].append("Repeated recovery preserves the released candidate and current owner")
        descriptor, restored = desktop_restore(
            boundary_result, root, root / 'backups/isolated-restoration',
            hostname=args.desktop_hostname, host_key_alias=args.desktop_host_key_alias,
            low_peak=args.low_peak_restore)
        require(descriptor["handover_acceptance_pending"] and not descriptor["frozen_boundary_verified"],
                "Desktop restore metadata must not claim handover acceptance")
        restored_runtime = Path(restored["destination"]) / "files" / str(runtime).lstrip("/")
        for original in (history, dirty, attachment):
            require(digest(original) == digest(restored_runtime / original.relative_to(runtime)), "Restored fixture mismatch")
        with sqlite3.connect(restored_runtime / "xdg/vibe-kanban/db.v2.sqlite") as db:
            require(db.execute("SELECT count(*) FROM saved_chat_messages WHERE id='after-checkpoint'").fetchone()[0] == 1,
                    "Final archive lacks post-snapshot saved message")
        with sqlite3.connect(restored_runtime / "codex-home/goal-fixture.sqlite") as db:
            require(db.execute("SELECT checkpoint FROM goals").fetchone()[0] == "latest goal and model choice",
                    "Final archive lacks latest goal fixture")
        result.update(passed=True, timings=timings, restoration=restored,
                      boundary_result=str(Path(boundary_result["folder"]) / "result.json"),
                      desktop_directory=args.desktop_directory,
                      scope="Real VK binaries, private data and routes, actual Desktop transfer; no CU polling or native model execution")
    finally:
        if journal is not None:
            journal.close()
        for definition in reversed(definitions):
            unit = definition.name
            subprocess.run(["journalctl", "--user", "-u", unit, "--no-pager", "-n", "120"],
                           stdout=(root / (unit + ".log")).open("w"), check=False)
            if handover.prop(unit, "FreezerState") == "frozen":
                private_ctl("thaw", unit)
            private_ctl("stop", unit)
            definition.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        save(root / "result.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
