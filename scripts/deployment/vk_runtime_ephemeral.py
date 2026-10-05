"""Narrow allowance for journal-proven deletion of Codex launcher scratch files."""
from pathlib import Path
import re

HOMES = ('/home/mcp/.codex', '/home/mcp/.local/share/vibe-kanban-green-codex-home')
MEMBERS = {'', '.lock', 'apply_patch', 'applypatch', 'codex-execve-wrapper', 'codex-linux-sandbox'}


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
    backup.validate_archive_warnings = lambda log, watched, plan, online: original(
        log, watched, warning_plan(log, plan), online)
