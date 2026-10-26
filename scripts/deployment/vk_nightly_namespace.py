"""One explicit bootstrap namespace audit; never used for ordinary deltas.

Stream Linux metadata into the caller's bounded SQLite control index. Bodies
are not opened or hashed. Watcher windows and subsequent changed-name replay
are independently required: completion here is NOT a recoverable baseline.
Source aliases are preserved plus their explicitly addressed resolved targets.
Discovered symlinks are recorded without following them. Transient child errors
remain an explicit replay queue; no incomplete traversal becomes accepted.
Missing required roots need their exact exception in the already-bound plan.
"""
import os
from pathlib import Path
import stat

from vk_nightly_file_version import attributes, fingerprint
from vk_nightly_qualification import encode_observation
from vk_nightly_tracking import source_bindings
from vk_rolling_backup import Exclusions


def observe(path):
    path = Path(path)
    before = path.lstat()
    kind = ('directory' if stat.S_ISDIR(before.st_mode) else
            'file' if stat.S_ISREG(before.st_mode) else
            'symlink' if stat.S_ISLNK(before.st_mode) else 'special')
    value = dict(kind=kind, identity=fingerprint(before), mode=stat.S_IMODE(before.st_mode),
                 uid=before.st_uid, gid=before.st_gid, mtime_ns=before.st_mtime_ns,
                 bytes=before.st_size, xattrs=attributes(path))
    if kind == 'symlink':
        value['target'] = os.readlink(path)
    if kind == 'special':
        value['special_type'] = stat.S_IFMT(before.st_mode)
        value['requires_explicit_disposition'] = True
    if fingerprint(path.lstat()) != fingerprint(before):
        raise ValueError('namespace metadata changed during observation: ' + str(path))
    return value


def audit(plan, database, *, checkpoint, maximum_paths, on_progress=lambda _: None):
    """The caller owns the finite SQLite budget, exclusive lease and admission.

    A failed audit leaves partial observations. A completed audit is a window,
    not an atomic snapshot or a claim about the original capture epoch. Do not
    resume by skipping partially enumerated directories after a reader gap.
    """
    if type(maximum_paths) is not int or maximum_paths < 1:
        raise ValueError('finite namespace control bound required')
    if database.execute("select 1 from sqlite_master where name='namespace'").fetchone():
        raise ValueError('preserve previous namespace audit; do not overwrite or silently replay')
    bindings = source_bindings(plan)
    exclusions = Exclusions(plan)
    exceptions = {entry['path'] for entry in plan.get('absent_source_exceptions', [])
                  if entry.get('current') == 'absent'}
    state = dict(observed_paths=0, regular_files=0, directories=0, symlinks=0, specials=0, pending_errors=0,
                 source_payload_bytes_read=0, backup_payload_bytes_copied=0,
                 complete=False, baseline_accepted=False, absent_source_exceptions=[])
    database.execute('create table namespace(name text primary key,row blob not null) without rowid')
    database.execute('create table namespace_errors(name text primary key,error blob not null) without rowid')
    database.commit()

    def guard():
        checkpoint()
        exclusions.validate()

    def failed(path, error):
        name = str(path).lstrip('/')
        if database.execute('select 1 from namespace_errors where name=?', (name,)).fetchone():
            return
        if state['observed_paths'] + state['pending_errors'] >= maximum_paths:
            raise ValueError('namespace exceeds admitted path budget; preserve partial metadata')
        database.execute('insert into namespace_errors values(?,?)', (name, encode_observation(dict(
            reason=type(error).__name__ + ': ' + str(error), errno=getattr(error, 'errno', None),
            requires_journal_replay_or_explicit_disposition=True))))
        state['pending_errors'] += 1

    def add(path):
        if exclusions(path):
            return
        name = str(path).lstrip('/')
        if database.execute('select 1 from namespace where name=?', (name,)).fetchone():
            return
        if state['observed_paths'] + state['pending_errors'] >= maximum_paths:
            raise ValueError('namespace exceeds admitted path budget; preserve partial metadata')
        try:
            value = observe(path)
        except (OSError, ValueError) as error:
            failed(path, error)
            return
        database.execute('insert into namespace values(?,?)', (name, encode_observation(value)))
        state['observed_paths'] += 1
        key = {'file': 'regular_files', 'directory': 'directories', 'symlink': 'symlinks', 'special': 'specials'}
        state[key[value['kind']]] += 1
        if state['observed_paths'] % 256 == 0:
            database.commit()
            guard()
            on_progress(dict(state, last_path=str(path)))

    # Resolve only declared roots, then collapse overlaps. No global Python set
    # of member paths; the disk index deduplicates and preserves all metadata.
    targets = set()
    for raw, binding in bindings.items():
        checkpoint()
        if binding is None:
            if raw not in exceptions:
                raise ValueError('required source unavailable: ' + raw)
            state['absent_source_exceptions'].append(raw)
            continue
        if Path(raw).is_symlink():
            add(Path(raw))
        targets.add(binding['resolved'])
    roots = []
    for raw in sorted(targets):
        if not any(Path(raw).is_relative_to(root) for root in roots):
            roots.append(raw)
    for raw in roots:
        guard()
        root = Path(raw)
        if exclusions(root):
            continue
        add(root)
        if not root.is_dir():
            continue
        for directory, dirs, files in os.walk(root, followlinks=False,
                                             onerror=lambda error: failed(error.filename, error)):
            # Recheck the visited directory; a concurrent replacement is not a
            # reason to follow a link into an undeclared tree.
            try:
                if not stat.S_ISDIR(Path(directory).lstat().st_mode):
                    raise ValueError('directory changed during namespace audit: ' + directory)
            except (OSError, ValueError) as error:
                failed(directory, error)
                dirs[:] = []
                continue
            dirs[:] = [name for name in dirs if not exclusions(Path(directory) / name)]
            for name in dirs + files:
                add(Path(directory) / name)
    database.commit()
    guard()
    if source_bindings(plan) != bindings:
        raise ValueError('required source binding changed during namespace audit')
    state['traversal_finished'] = True
    state['complete'] = state['pending_errors'] == 0
    on_progress(state)
    return state
