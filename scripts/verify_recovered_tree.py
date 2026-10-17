#!/usr/bin/env python3
"""Read-only content/metadata audit. Never extracts, places, removes or starts code.

The caller supplies an authenticated manifest and its independently recorded
SHA-256. A journal records names/events, not previous content: even complete
coverage cannot prove preservation of all post-backup edits.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat


def safe_relative(raw):
    path = PurePosixPath(raw)
    if not isinstance(raw, str) or not raw or path.is_absolute() or any(
        part in ('', '.', '..') for part in raw.split('/')
    ):
        raise ValueError('manifest path must be a normalized relative path')
    return path


def no_link_path(root, raw):
    parts = safe_relative(raw).parts
    path = root
    for part in parts[:-1]:
        path = path / part
        mode = path.lstat().st_mode
        if not stat.S_ISDIR(mode):
            raise ValueError('non-directory or link in parent path')
    return path / parts[-1]


def file_hash(path):
    # O_NONBLOCK prevents a raced-in FIFO from hanging the audit.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('not a regular file')
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
        after = os.fstat(source.fileno())
        current = path.lstat()
        identity = lambda row: (row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns, row.st_ctime_ns)
        if identity(before) != identity(after) or identity(after) != identity(current):
            raise ValueError('file changed during audit')
        return digest


def verify_entry(root, row):
    raw = row['path']
    path = no_link_path(root, raw)
    meta = path.lstat()
    actual_type = ('file' if stat.S_ISREG(meta.st_mode) else
                   'directory' if stat.S_ISDIR(meta.st_mode) else
                   'symlink' if stat.S_ISLNK(meta.st_mode) else 'special')
    expected_type = row.get('type')
    if expected_type not in ('file', 'directory', 'symlink', 'hardlink'):
        return {'path': raw, 'status': 'unverified', 'reason': 'missing supported type evidence'}
    if actual_type != ('file' if expected_type == 'hardlink' else expected_type):
        return {'path': raw, 'status': 'mismatch', 'reason': 'type', 'actual': actual_type}
    if 'mode' not in row:
        return {'path': raw, 'status': 'unverified', 'reason': 'missing mode evidence'}
    if stat.S_IMODE(meta.st_mode) != row['mode']:
        return {'path': raw, 'status': 'mismatch', 'reason': 'mode', 'actual': stat.S_IMODE(meta.st_mode)}
    if expected_type in ('file', 'hardlink'):
        if 'sha256' not in row:
            return {'path': raw, 'status': 'unverified', 'reason': 'missing content hash'}
        actual = file_hash(path)
        if actual != row['sha256']:
            return {'path': raw, 'status': 'mismatch', 'reason': 'content', 'actual_sha256': actual,
                    'meaning': 'baseline differs; newer surviving edit or loss requires separate evidence'}
        if expected_type == 'hardlink':
            target = no_link_path(root, row['target'])
            target_meta = target.lstat()
            if not stat.S_ISREG(target_meta.st_mode) or (meta.st_dev, meta.st_ino) != (target_meta.st_dev, target_meta.st_ino):
                return {'path': raw, 'status': 'mismatch', 'reason': 'hardlink identity'}
    elif expected_type == 'symlink':
        if 'target' not in row:
            return {'path': raw, 'status': 'unverified', 'reason': 'missing link target evidence'}
        if os.readlink(path) != row['target']:
            return {'path': raw, 'status': 'mismatch', 'reason': 'link target'}
    return {'path': raw, 'status': 'verified'}


def audit(root, entries, journal, observed_names=(), coverage=None):
    root = Path(root).resolve(strict=True)
    if not entries:
        raise ValueError('empty manifest cannot establish recovery coverage')
    names = [row['path'] for row in entries]
    name_set = set(names)
    if len(set(names)) != len(names):
        raise ValueError('duplicate manifest paths')
    for name in names:
        safe_relative(name)
    findings, counts = [], {key: 0 for key in ('verified', 'missing', 'mismatch', 'unverified', 'error')}
    for row in entries:
        try:
            result = verify_entry(root, row)
        except FileNotFoundError:
            result = {'path': row['path'], 'status': 'missing'}
        except (OSError, ValueError, KeyError) as error:
            result = {'path': row['path'], 'status': 'error', 'reason': str(error)}
        counts[result['status']] += 1
        if result['status'] != 'verified':
            findings.append(result)
    uncovered = []
    for name in observed_names:
        safe_relative(name)
        if name not in name_set:
            uncovered.append({'path': name, 'current_exists': os.path.lexists(root / name),
                              'status': 'unverified', 'reason': 'no authenticated baseline metadata'})
    coverage = coverage or {}
    journal_complete = (journal.get('ready') is True and coverage.get('instance')
                        and journal.get('instance') == coverage.get('instance')
                        and coverage.get('scope_sha256')
                        and journal.get('scope_sha256') == coverage.get('scope_sha256')
                        and isinstance(coverage.get('sequence_start'), int)
                        and isinstance(journal.get('sequence'), int)
                        and journal['sequence'] >= coverage['sequence_start']
                        and journal.get('errors') == [])
    return {
        'scope': 'supplied manifest entries only', 'counts': counts, 'findings': findings,
        'uncovered_names': uncovered,
        'baseline_verified': all(counts[k] == 0 for k in counts if k != 'verified') and not uncovered,
        'journal_coverage_verified': bool(journal_complete),
        'journal_errors': journal.get('errors', ['coverage evidence missing']),
        'post_backup_content_preservation_verified': False,
        'new_file_preservation_verified': False,
        'uncertainty': ['Events do not retain prior bytes of modified files.',
                        'Unobserved new names and edits during journal gaps remain unresolved.'],
        'zero_loss_proven': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--journal', required=True, type=Path)
    args = parser.parse_args()
    raw = args.manifest.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != args.manifest_sha256:
        parser.error('manifest SHA-256 does not match independently recorded expected value')
    manifest = json.loads(raw)
    if manifest.get('version') != 1:
        parser.error('unsupported manifest version')
    result = audit(args.root, manifest['entries'], json.loads(args.journal.read_text()), manifest.get('observed_names', []), manifest.get('journal_coverage'))
    result['manifest_sha256'] = digest
    print(json.dumps(result, indent=2))
    return 0 if result['baseline_verified'] and result['journal_coverage_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
