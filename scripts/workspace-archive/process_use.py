"""Read-only process-use protection for owned workspace payload paths.

This supplements, never replaces, the kernel custody protocol implemented by the
qualified serving binaries. No process is stopped and no descriptor contents,
command arguments or environment secrets are read or recorded.
"""
import os
from pathlib import Path

from catalog import Conflict


def birth(directory):
    fields = (directory / 'stat').read_text().rsplit(')', 1)[1].split()
    return fields[19]


def in_roots(value, roots):
    if value.endswith(' (deleted)'):
        value = value[:-10]
    if not value.startswith('/'):
        return False
    p = Path(value)
    return any(p == r or r in p.parents for r in roots)


def check(roots, *, identities=(), proc=Path('/proc')):
    """Protect same-owner cwd/exe/open/mapped files, including deleted names.

    Only this exact helper is exempt. Backend/agent/backup processes receive no
    blanket exemption. A process that exits during inspection is harmless; a
    live same-owner process that cannot be inspected remains an explicit hold.
    Manifest inode identities also detect aliases in another mount namespace.
    """
    roots, identities = tuple(Path(r) for r in roots), set(tuple(v) for v in identities)
    if any(not p.is_absolute() or '..' in p.parts for p in roots):
        raise ValueError('Exact absolute process-protection roots required')
    for directory in proc.iterdir():
        if not directory.name.isdecimal() or int(directory.name) == os.getpid():
            continue
        try:
            if directory.stat().st_uid != os.getuid():
                continue
            before = birth(directory)
            references = [directory / 'cwd', directory / 'exe']
            references.extend((directory / 'fd').iterdir())
            for reference in references:
                try:
                    named = os.readlink(reference)
                    st = reference.stat()
                except FileNotFoundError:
                    continue
                if in_roots(named, roots) or (st.st_dev, st.st_ino) in identities:
                    raise Conflict('Workspace payload is referenced by a live process')
            # Linux maps carries device/inode without needing privileged
            # /proc/pid/map_files access. Ignore anonymous and kernel mappings.
            for row in (directory / 'maps').read_text().splitlines():
                fields = row.split(None, 5)
                if len(fields) < 5:
                    raise Conflict('Unresolved process map ownership')
                major, minor = (int(v, 16) for v in fields[3].split(':'))
                key = (os.makedev(major, minor), int(fields[4]))
                if key in identities or len(fields) == 6 and in_roots(fields[5], roots):
                    raise Conflict('Workspace payload is mapped by a live process')
            if birth(directory) != before:
                raise Conflict('Process identity changed during ownership inspection')
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError as error:
            if directory.exists():
                raise Conflict('Live same-owner process ownership could not be inspected') from error
