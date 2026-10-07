"""Narrow allowance for journal-proven deletion of Codex launcher scratch files."""
from pathlib import Path
import os
import re
import stat

HOMES = ('/home/mcp/.codex', '/home/mcp/.local/share/vibe-kanban-green-codex-home')
MEMBERS = {'', '.lock', 'apply_patch', 'applypatch', 'codex-execve-wrapper', 'codex-linux-sandbox'}


def runtime_socket_warning(line, plan):
    """Only the known, present Codex updater IPC endpoint has no archive payload."""
    match = re.fullmatch(r'tar: (.+?): socket ignored', line)
    if not match:
        return None
    path = Path('/' + match.group(1).lstrip('/'))
    allowed = {Path(home) / 'app-server-daemon/daemon-updater.sock' for home in HOMES}
    if (path not in allowed or str(path) != '/' + match.group(1).lstrip('/')
            or path.is_symlink() or any(p.is_symlink() for p in path.parents)
            or not any(path.is_relative_to(Path(root).resolve()) for root in plan['sources'])):
        raise ValueError('Unrecognized runtime socket warning: ' + str(path))
    info = path.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError('Runtime endpoint is not an owned socket: ' + str(path))
    return str(path)


def warning_plan(log, plan):
    roots = []
    for line in log.splitlines():
        match = re.fullmatch(r'tar: (.+?): (?:Warning: )?Cannot stat: No such file or directory', line)
        if not match:
            continue
        path = Path('/' + match.group(1).lstrip('/'))
        for home in HOMES:
            root = Path(home) / 'tmp/arg0'
            if not path.is_relative_to(root):
                continue
            parts = path.relative_to(root).parts
            if (len(parts) not in (1, 2) or not re.fullmatch(r'codex-arg0[A-Za-z0-9]{6}', parts[0])
                    or (parts[1] if len(parts) == 2 else '') not in MEMBERS):
                raise ValueError('Unknown Codex scratch member: ' + str(path))
            if any(root.is_relative_to(Path(source).resolve()) for source in plan['sources']):
                roots.append(str(root / parts[0]))
    return {**plan, 'online_ephemeral_roots': [*plan.get('online_ephemeral_roots', []), *roots]}


def install(backup):
    original = backup.validate_archive_warnings
    def validate(log, watched, plan, online):
        sockets, remaining = [], []
        for line in log.splitlines():
            endpoint = runtime_socket_warning(line, plan)
            if endpoint is None:
                remaining.append(line)
            else:
                sockets.append(endpoint)
        remaining = '\n'.join(remaining)
        return original(remaining, watched, warning_plan(remaining, plan), online) + sockets
    backup.validate_archive_warnings = validate
