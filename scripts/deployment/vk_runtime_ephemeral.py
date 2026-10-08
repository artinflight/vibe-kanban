"""Narrow allowance for journal-proven deletion of Codex launcher scratch files."""
from pathlib import Path
import os
import re
import stat

HOMES = ('/home/mcp/.codex', '/home/mcp/.local/share/vibe-kanban-green-codex-home')
MEMBERS = {'', '.lock', 'apply_patch', 'applypatch', 'codex-execve-wrapper', 'codex-linux-sandbox'}
THREAD = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def released_runtime_file(path, plan):
    """Classify exact runtime names, not whole directories or session data.

    Codex regenerates shell snapshots and deletes them on drop. Writer lock
    files hold OS locks, not history, and are created on acquire/deleted on drop.
    The caller still requires an observed deletion and absence in online mode.
    """
    for home in HOMES:
        home = Path(home)
        patterns = {'shell_snapshots': THREAD + r'\.[0-9]{1,20}\.sh',
                    'thread-writer-locks': THREAD + r'\.lock'}
        for directory, pattern in patterns.items():
            root = home / directory
            if path.parent != root or not re.fullmatch(pattern, path.name):
                continue
            if (any(p.is_symlink() for p in path.parents) or not root.is_dir()
                    or root.stat().st_uid != os.getuid()
                    or str(path) != str(path.absolute()) or '..' in path.parts):
                raise ValueError('Unsafe runtime-file parent: ' + str(path))
            required = [*plan['sources'], *plan.get('critical_sqlite', []),
                        *plan.get('sqlite_snapshots', [])]
            if str(path) in required:
                raise ValueError('Explicitly required runtime file disappeared: ' + str(path))
            return any(home.is_relative_to(Path(source).resolve()) for source in plan['sources'])
    return False


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
        if released_runtime_file(path, plan):
            roots.append(str(path))
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
