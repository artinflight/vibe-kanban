"""Explicit current-absence proof for failed ENOENT journal enrollment.

This never edits a raw journal report or grants baseline/fence acceptance. A
consumer authenticates the certificate separately, reconciles the entire changed
namespace, and continues probing these exact parents until its final fence.
"""
import errno
import hashlib
import os
from pathlib import Path
import re
import stat

from vk_typed_recovery import canonical, checksum

FORMAT = 'vk-vanished-enrollment-current-absence-v1'
ANCESTOR_FORMAT = 'vk-vanished-enrollment-watched-ancestor-v2'


def start_ticks(pid):
    return int((Path('/proc') / str(pid) / 'stat').read_text().rsplit(') ', 1)[1].split()[19])


def probe(observer, paths, *, ancestors=False):
    """Read the actual same-process kernel subscriptions; no source body read."""
    pid, fd = observer['PID'], observer['fd']
    if start_ticks(pid) != observer['start_ticks']:
        raise ValueError('observer process identity changed')
    path = Path('/proc') / str(pid) / 'fd' / str(fd)
    if os.readlink(path) != 'anon_inode:inotify':
        raise ValueError('observer descriptor is not inotify')
    identity = path.stat()
    parents = []
    for target in paths:
        try:
            Path(target).lstat()
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise
        else:
            raise ValueError('failed enrollment target has reappeared')
        parent = Path(target).parent
        if ancestors:
            while True:
                try:
                    parent.lstat()
                    break
                except FileNotFoundError:
                    parent = parent.parent
        st = parent.lstat()
        if not stat.S_ISDIR(st.st_mode) or parent.resolve() != parent:
            raise ValueError('failed enrollment parent is not the canonical directory')
        parents.append((target, parent, st))
    wanted = {(st.st_ino, (os.major(st.st_dev) << 20) | os.minor(st.st_dev)) for _, _, st in parents}
    watches = []; fdinfo_hash = hashlib.sha256()
    with (path.parent.parent / 'fdinfo' / str(fd)).open('rb') as stream:
        for line in stream:
            fdinfo_hash.update(line)
            if line.startswith(b'inotify wd:'):
                # Keep ignored_mask distinct, without retaining the whole
                # 100k-watch table in a small validation process's memory.
                fields = dict(re.findall(r'(?:^|\s)(wd|ino|sdev|mask):([0-9a-f]+)(?=\s|$)', line.decode('ascii')))
                if set(fields) != {'wd', 'ino', 'sdev', 'mask'}:
                    raise ValueError('unreadable kernel watch fields')
                w = {k: int(v, 16) for k, v in fields.items()}
                if (w['ino'], w['sdev']) in wanted:
                    watches.append(w)
    rows = []
    for target, parent, st in parents:
        latest = parent.lstat()
        if (latest.st_dev, latest.st_ino) != (st.st_dev, st.st_ino):
            raise ValueError('parent changed during kernel probe')
        kernel_dev = (os.major(st.st_dev) << 20) | os.minor(st.st_dev)
        subscriptions = [w for w in watches if w['ino'] == st.st_ino and w['sdev'] == kernel_dev]
        if len(subscriptions) != 1 or subscriptions[0]['mask'] & 0x180 != 0x180:
            raise ValueError('parent does not cover creation and move-in')
        row = {'path': target, 'parent_device': st.st_dev, 'parent_inode': st.st_ino,
               'watch': subscriptions[0], 'absence_errno': errno.ENOENT}
        if ancestors:
            row['watched_ancestor'] = str(parent)
            row['absent_child'] = str(parent / Path(target).relative_to(parent).parts[0])
            # Recheck the first missing component after reading fdinfo. A watch
            # on the ancestor protects recreation, not hidden intermediate links.
            try:
                Path(row['absent_child']).lstat()
            except FileNotFoundError:
                pass
            else:
                raise ValueError('missing ancestor child reappeared during probe')
        rows.append(row)
    if start_ticks(pid) != observer['start_ticks']:
        raise ValueError('observer changed during kernel probe')
    return {'observer': observer, 'fd_device': identity.st_dev, 'fd_inode': identity.st_ino,
            'fdinfo_sha256': fdinfo_hash.hexdigest(), 'rows': rows}


def related(path, target):
    return path == target or path.startswith(target.rstrip('/') + '/')


def seal(*, observer, initial, before, after, kernel, plan_sha256, required_sources,
         subtree_names):
    """Seal only absent enrollment targets, never all changed paths or history."""
    errors = before.get('errors')
    if (initial.get('ready') is not True or initial.get('errors') != []
            or not isinstance(errors, list) or not errors
            or before.get('ready') is not False or after.get('ready') is not False
            or after.get('errors') != errors
            or any(set(e) != {'watch_failed', 'errno'} or e['errno'] != errno.ENOENT for e in errors)):
        raise ValueError('raw error list is not exact resolvable ENOENT enrollment')
    paths = [e['watch_failed'] for e in errors]
    if len(paths) != len(set(paths)):
        raise ValueError('repeated enrollment failure needs a new disposition')
    for report in (initial, before, after):
        if (report.get('instance') != initial['instance'] or not initial['instance']
                or report.get('scope_sha256') != initial['scope_sha256']
                or type(report.get('sequence')) is not int):
            raise ValueError('journal identity/sequence changed')
    if not 0 <= initial['sequence'] <= before['sequence'] <= after['sequence']:
        raise ValueError('journal sequence regressed')
    if kernel['observer'] != observer or [r['path'] for r in kernel['rows']] != paths:
        raise ValueError('kernel witnesses differ from ordered raw failures')
    for target, row in zip(paths, kernel['rows']):
        if (target in required_sources or not any(related(target, root) for root in required_sources)
                or row['absence_errno'] != errno.ENOENT or row['watch']['mask'] & 0x180 != 0x180
                or not before.get('events', {}).get(target, 0) & 0x600):
            raise ValueError('required root, unwitnessed absence, or missing deletion event')
        if any(subtree_names(target)):
            raise ValueError('selected map still contains the vanished subtree')
        if any(related(path, target) for path in after.get('changed', [])):
            raise ValueError('target changed during absence bracket')
    return {'format': FORMAT, 'observer': observer, 'plan_sha256': plan_sha256,
            'required_sources_sha256': checksum(sorted(required_sources)),
            'initial_raw': initial, 'before_raw': before, 'after_raw': after,
            'kernel': kernel, 'closed_sequence': after['sequence'],
            'disposition': 'CURRENT_SUBTREE_ABSENT_PARENT_STILL_WATCHED',
            'unobserved_transient_history_recovered': False,
            'all_changed_paths_reconciled': False, 'raw_journal_ready': False,
            'full_current_set_accepted': False, 'writer_fence_verified': False}


def check_continuing(certificate, expected_sha256, *, plan_sha256, required_sources,
                     watched, current_kernel):
    """Fail closed on new errors, reappearance, drift or lost parent coverage.

    `watched` must be an unmodified raw report queried since closed_sequence;
    current_kernel comes from a fresh probe bracketed by the caller's reports.
    """
    c = certificate
    if (checksum(c) != expected_sha256 or c.get('format') != FORMAT
            or c.get('plan_sha256') != plan_sha256
            or c.get('required_sources_sha256') != checksum(sorted(required_sources))):
        raise ValueError('unauthenticated enrollment closure/scope')
    raw = c['after_raw']
    if (watched.get('instance') != raw['instance'] or watched.get('scope_sha256') != raw['scope_sha256']
            or watched.get('errors') != raw['errors'] or watched.get('ready') is not False
            or type(watched.get('sequence')) is not int or watched['sequence'] < c['closed_sequence']):
        raise ValueError('raw journal continuity or exact errors changed')
    old, new = c['kernel'], current_kernel
    if any(old[k] != new[k] for k in ('observer', 'fd_device', 'fd_inode', 'rows')):
        raise ValueError('observer/parent/kernel subscription changed')
    paths = [e['watch_failed'] for e in raw['errors']]
    if any(related(path, target) for path in watched.get('changed', []) for target in paths):
        raise ValueError('failed subtree changed; closure needs reconciliation')
    return {'enrollment_gaps_conditionally_resolved': len(paths), 'raw': watched,
            'full_current_set_accepted': False, 'writer_fence_verified': False}


class VanishedEnrollmentCoverage:
    """Consumer-owned authenticated adapter; keeps the raw unready report.

    The caller pins the certificate outside the descriptor and supplies its real
    journal reader. The default kernel reader performs current host probes.
    This does not reconcile unrelated changed paths or grant a writer fence.
    """
    def __init__(self, certificate, expected_sha256, journal_reader, kernel_reader=probe):
        import json
        self.certificate = json.loads(canonical(certificate))
        self.expected_sha256 = expected_sha256
        self.journal_reader, self.kernel_reader = journal_reader, kernel_reader
        if checksum(self.certificate) != expected_sha256:
            raise ValueError('unauthenticated enrollment certificate')

    def current(self, *, plan_sha256, required_sources):
        c = self.certificate
        watched = self.journal_reader(c['closed_sequence'])
        paths = [e['watch_failed'] for e in c['after_raw']['errors']]
        kernel = self.kernel_reader(c['observer'], paths)
        check_continuing(c, self.expected_sha256, plan_sha256=plan_sha256,
                         required_sources=required_sources, watched=watched, current_kernel=kernel)
        drained = self.journal_reader(watched['sequence'])
        check_continuing(c, self.expected_sha256, plan_sha256=plan_sha256,
                         required_sources=required_sources, watched=drained, current_kernel=kernel)
        if drained['sequence'] < watched['sequence']:
            raise ValueError('sequence regressed during current kernel bracket')
        return watched, drained

    def validate_anchor(self, anchor, *, plan_sha256, required_sources):
        c = self.certificate
        raw = c['after_raw']
        if (anchor.get('enrollment_resolution_sha256') != self.expected_sha256
                or anchor.get('errors') != raw['errors']
                or anchor.get('instance') != raw['instance']
                or anchor.get('scope_sha256') != raw['scope_sha256']
                or anchor['end'] < c['closed_sequence']
                or anchor['start'] < c['initial_raw']['sequence']):
            raise ValueError('journal anchor differs from authenticated enrollment coverage')
        watched, drained = self.current(plan_sha256=plan_sha256, required_sources=required_sources)
        if drained['sequence'] < anchor['end']:
            raise ValueError('current observer is behind the descriptor')
        return [e['watch_failed'] for e in raw['errors']]


def enrollment_paths(errors):
    """Only exact ENOENT enroll/re-enroll errors can have absence witnesses."""
    paths = []
    if not isinstance(errors, list) or not errors:
        raise ValueError('nonempty raw enrollment errors required')
    for error in errors:
        fields = set(error) - {'errno'}
        if (error.get('errno') != errno.ENOENT or len(fields) != 1
                or not fields <= {'watch_failed', 'watch_reenrollment_stat_failed'}):
            raise ValueError('unknown or non-ENOENT enrollment error')
        path = error[next(iter(fields))]
        if not isinstance(path, str) or not path.startswith('/') or str(Path(path)) != path or '..' in Path(path).parts:
            raise ValueError('canonical enrollment path required')
        paths.append(path)
    if len(paths) != len(set(paths)):
        raise ValueError('duplicate enrollment errors require separate reconciliation')
    return paths


def seal_ancestors(*, observer, initial, before, after, kernel, plan_sha256,
                   required_sources, subtree_names):
    """Versioned current-absence disposition; historical gaps remain unaccepted.

    Missing intermediate parents require the first absent child of an actually
    watched surviving ancestor. The caller checks the selected map for that
    WHOLE absent child, not just the deepest failed path. No error is removed.
    """
    paths = enrollment_paths(before.get('errors'))
    initial_ready = initial.get('ready') is True or (
        initial.get('format') == 'T17-open-gap-current-observation-v2'
        and initial.get('observation_ready') is True and initial.get('ready') is False)
    if (not initial_ready or initial.get('errors') != []
            or before.get('ready') is not False or after.get('ready') is not False
            or after.get('errors') != before['errors']
            or any(r.get('pending_directory_moves', 0) != 0 for r in (before, after))):
        raise ValueError('initial coverage or exact current error bracket differs')
    for report in (initial, before, after):
        if (not initial.get('instance') or report.get('instance') != initial['instance']
                or report.get('scope_sha256') != initial['scope_sha256']
                or type(report.get('sequence')) is not int):
            raise ValueError('observer epoch or scope differs')
    if not 0 <= initial['sequence'] <= before['sequence'] <= after['sequence']:
        raise ValueError('observer sequence regressed')
    if kernel['observer'] != observer or [r['path'] for r in kernel['rows']] != paths:
        raise ValueError('kernel witnesses differ from ordered raw failures')
    absent = set()
    for target, row in zip(paths, kernel['rows']):
        ancestor, child = row['watched_ancestor'], row['absent_child']
        if (not related(target, child) or str(Path(child).parent) != ancestor
                or not any(related(child, root) and child != root for root in required_sources)
                or any(related(root, child) for root in required_sources)
                or row['absence_errno'] != errno.ENOENT or row['watch']['mask'] & 0x180 != 0x180
                or not before.get('events', {}).get(child, 0) & 0x600):
            raise ValueError('required root, unwatched ancestor or missing child deletion event')
        absent.add(child)
    for child in absent:
        if any(subtree_names(child)):
            raise ValueError('selected map still contains the absent child subtree')
        if any(related(path, child) for path in after.get('changed', [])):
            raise ValueError('absent child changed during bracket')
    return {'format': ANCESTOR_FORMAT, 'observer': observer,
            'plan_sha256': plan_sha256, 'required_sources_sha256': checksum(sorted(required_sources)),
            'initial_raw': initial, 'before_raw': before, 'after_raw': after,
            'kernel': kernel, 'absent_subtrees': sorted(absent), 'closed_sequence': after['sequence'],
            'disposition': 'CURRENT_SUBTREES_ABSENT_ANCESTOR_STILL_WATCHED',
            'unobserved_transient_history_recovered': False, 'historical_gap_closed': False,
            'all_changed_paths_reconciled': False, 'raw_journal_ready': False,
            'full_current_set_accepted': False, 'writer_fence_verified': False}


def check_ancestors(certificate, expected_sha256, *, plan_sha256, required_sources,
                    watched, current_kernel):
    c = certificate
    if (checksum(c) != expected_sha256 or c.get('format') != ANCESTOR_FORMAT
            or c.get('plan_sha256') != plan_sha256
            or c.get('required_sources_sha256') != checksum(sorted(required_sources))):
        raise ValueError('unauthenticated ancestor absence closure')
    raw = c['after_raw']
    if (watched.get('instance') != raw['instance'] or watched.get('scope_sha256') != raw['scope_sha256']
            or watched.get('errors') != raw['errors'] or watched.get('ready') is not False
            or watched.get('pending_directory_moves', 0) != 0
            or type(watched.get('sequence')) is not int or watched['sequence'] < c['closed_sequence']):
        raise ValueError('current journal continuity/errors changed')
    old = c['kernel']
    if any(old[k] != current_kernel[k] for k in ('observer', 'fd_device', 'fd_inode', 'rows')):
        raise ValueError('observer/ancestor/kernel subscription changed')
    if any(related(path, child) for path in watched.get('changed', []) for child in c['absent_subtrees']):
        raise ValueError('absent subtree changed; current map reconciliation required')
    return {'enrollment_gaps_conditionally_resolved': len(raw['errors']), 'raw': watched,
            'historical_gap_closed': False, 'full_current_set_accepted': False,
            'writer_fence_verified': False}


class WatchedAncestorCoverage(VanishedEnrollmentCoverage):
    """Typed-reader adapter for v2; preserves the raw unready observer report."""
    def current(self, *, plan_sha256, required_sources):
        c = self.certificate
        watched = self.journal_reader(c['closed_sequence'])
        paths = enrollment_paths(c['after_raw']['errors'])
        kernel = self.kernel_reader(c['observer'], paths, ancestors=True)
        args = dict(plan_sha256=plan_sha256, required_sources=required_sources, current_kernel=kernel)
        check_ancestors(c, self.expected_sha256, watched=watched, **args)
        drained = self.journal_reader(watched['sequence'])
        check_ancestors(c, self.expected_sha256, watched=drained, **args)
        if drained['sequence'] < watched['sequence']:
            raise ValueError('sequence regressed during ancestor bracket')
        return watched, drained

    def validate_anchor(self, anchor, *, plan_sha256, required_sources):
        c = self.certificate; raw = c['after_raw']
        if (anchor.get('enrollment_resolution_sha256') != self.expected_sha256
                or anchor.get('errors') != raw['errors']
                or anchor.get('instance') != raw['instance']
                or anchor.get('scope_sha256') != raw['scope_sha256']
                or anchor['end'] < c['closed_sequence']
                or anchor['start'] < c['initial_raw']['sequence']):
            raise ValueError('journal anchor differs from authenticated ancestor coverage')
        _, drained = self.current(plan_sha256=plan_sha256, required_sources=required_sources)
        if drained['sequence'] < anchor['end']:
            raise ValueError('current observer is behind descriptor')
        return enrollment_paths(raw['errors'])
