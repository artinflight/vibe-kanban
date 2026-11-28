"""Read-only history overlays for an isolated reader rehearsal.

Missing original captures may be supplied from independently hash-verified
recovery copies. Never hide an existing capture or omit neighbouring files.
The caller must pin the recovery bytes and run in a private mount namespace.
"""
from pathlib import Path
import stat


def _relative(value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or len(path.parts) != 4:
        raise ValueError('Expected a contained session process path')
    if path.parts[2] != 'processes' or path.suffix != '.jsonl':
        raise ValueError('Expected an original execution capture')
    return path


def _regular(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Expected a regular source file')


def history_mounts(source_root, target_root, packed, selected, recovered):
    root = Path(source_root)
    selected = {_relative(p) for p in selected}
    recovered = {_relative(p): Path(v) for p, v in recovered.items()}
    if selected & recovered.keys():
        raise ValueError('Recovery and packed selections overlap')
    groups = {p.parent for p in recovered}
    for relative in packed:
        path = Path(relative)
        _relative(path / 'check.jsonl')
        groups.add(path)
    if any(str(p.parent) not in packed for p in selected):
        raise ValueError('Selected packed capture has no directory overlay')
    mounts = []
    for relative in sorted(groups):
        directory = root / relative
        current = root
        for part in relative.parts:
            current = current / part
            if not stat.S_ISDIR(current.lstat().st_mode):
                raise ValueError('Source parent is not an ordinary directory')
        target = str(Path(target_root) / relative)
        mounts += ['--tmpfs', target]
        pack_dir = Path(packed[str(relative)]) if str(relative) in packed else None
        for child in sorted(directory.iterdir()):
            if not (stat.S_ISREG(child.lstat().st_mode) or stat.S_ISDIR(child.lstat().st_mode)):
                raise ValueError('Unexpected source directory member')
            rel = relative / child.name
            if rel in recovered:
                raise ValueError('Recovery destination already exists')
            source = child
            if rel in selected:
                source = pack_dir / child.name
                _regular(source)
            if pack_dir and child.name == '.log-packs':
                raise ValueError('Existing packs must not be shadowed')
            mounts += ['--ro-bind', str(source), target + '/' + child.name]
        for rel in selected:
            if rel.parent == relative and not (root / rel).exists():
                raise ValueError('Selected original capture is missing')
        if pack_dir:
            packs = pack_dir / '.log-packs'
            if not stat.S_ISDIR(packs.lstat().st_mode):
                raise ValueError('Pack directory is not an ordinary directory')
            mounts += ['--ro-bind', str(packs), target + '/.log-packs']
        for rel, source in sorted(recovered.items()):
            if rel.parent == relative:
                _regular(source)
                mounts += ['--ro-bind', str(source), str(Path(target_root) / rel)]
    return mounts
