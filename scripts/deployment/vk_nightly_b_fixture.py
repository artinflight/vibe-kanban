"""Injected into an unprivileged existing WSL process: SYNTHETIC B fixtures only.

CONFIG and reviewed nightly module are supplied by the SSH acceptance harness.
No CLI, installation, schedule, production input or root operation.
"""
import base64
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

from vk_nightly_generation import NightlyStore, advance_verified_capture, encoded


WINDOWS_READBACK = '''
import hashlib,json,os,pathlib,sys
request=json.load(sys.stdin)
assert os.stat('B:/').st_dev==request['volume_device'], 'B volume substituted'
p=pathlib.Path(request['folder']);raw=(p/'manifest.json').read_bytes()
m=json.loads(raw)
assert hashlib.sha256(raw).hexdigest()==request['manifest_sha256']
assert m['scope_sha256']==request['scope'] and m['generation']==p.name
for h in {r['sha256'] for r in m['entries'].values() if r['kind']=='file'}:
 f=p/'objects'/h
 with f.open('rb') as stream:
  before=os.fstat(stream.fileno());digest=hashlib.sha256()
  for b in iter(lambda:stream.read(1048576),b''):digest.update(b)
  after=os.fstat(stream.fileno())
 assert digest.hexdigest()==h and (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
print(json.dumps({'physical_b_verified':True,'generation':m['generation'],
 'scope_sha256':m['scope_sha256'],'manifest_sha256':hashlib.sha256(raw).hexdigest()}))
'''


class CapturedFixtureProvider:
    """Exact proofs/payloads from real authenticated DirectBProvider on MCP.

    This is an acceptance transport adapter, not a production capture reader.
    Full original B archive checks complete upstream; no receipt is invented.
    """
    def verify(self, capture_id):
        return CONFIG['captures'][capture_id]['proof']

    @contextmanager
    def file_members(self, capture_id, selected):
        capture = CONFIG['captures'][capture_id]

        def members():
            for key in sorted(selected):
                raw = base64.b64decode(capture['payloads'][key], validate=True)
                row = capture['proof']['entries'][key]
                assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
                yield key, io.BytesIO(raw)
        yield members()


def mount_binding():
    assert os.getuid() == 1000, 'fixture must run without root'
    mount = subprocess.check_output(['findmnt', '-n', '-T', '/mnt/b', '-o', 'SOURCE,FSTYPE'], text=True).split()
    assert mount == ['B:\\', '9p'], 'existing B drvfs mount required'
    return Path('/mnt/b')


def physical_readback(folder, manifest):
    win_path = 'B:/' + str(folder.relative_to('/mnt/b'))
    request = {'folder': win_path, 'volume_device': CONFIG['volume_device'],
               'manifest_sha256': hashlib.sha256(encoded(manifest)).hexdigest(), 'scope': CONFIG['scope']}
    result = subprocess.run(['/mnt/c/Python310/python.exe', '-B', '-c', WINDOWS_READBACK],
                            input=json.dumps(request), capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('independent native Windows B readback failed: ' + result.stderr[:1000])
    return json.loads(result.stdout)


def open_store(case):
    root = Path(CONFIG['wsl_root']) / case
    return NightlyStore(root, CONFIG['scope'], mount_binding, independent_readback=physical_readback)


def run_case(case):
    root = Path(CONFIG['wsl_root']) / case
    root.mkdir()  # Fresh case only; never reuse/re-enroll existing directories.
    store = open_store(case)
    store.enroll_empty()
    provider = CapturedFixtureProvider()
    first = advance_verified_capture(store, provider, 'first', reserve_bytes=1024**2)
    current = store.current()
    assert current['generation'] == first['generation']
    unchanged = current['entries']['home/state/unchanged']['sha256']
    inode = (root / first['generation'] / 'objects' / unchanged).stat().st_ino
    progress = {'first': first, 'unchanged_inode': inode, 'case': case}
    with (root / 'fixture-progress.json').open('x') as out:
        json.dump(progress, out);out.flush();os.fsync(out.fileno())
    # Evidence is OUTSIDE store so the strict store inventory remains valid.
    (root / 'fixture-progress.json').rename(Path(CONFIG['wsl_root']) / (case + '-progress.json'))
    real_replace, real_unlink = os.replace, os.unlink

    def replace(source, target, **kwargs):
        if case == 'before-publication' and Path(target) == root / 'current.json':
            os._exit(73)
        return real_replace(source, target, **kwargs)

    def retention(generation):
        # Called only AFTER pointer replacement and root-directory fsync.
        if case == 'after-publication':
            os._exit(74)
        return original_retention(generation)

    def unlink(path, **kwargs):
        real_unlink(path, **kwargs)
        if case == 'during-retention' and kwargs.get('dir_fd') is not None:
            os._exit(75)  # Actual process death after one exact old-object unlink.

    original_retention = store._retire_previous_held
    with patch('os.replace', replace), patch('os.unlink', unlink), \
            patch.object(store, '_retire_previous_held', retention):
        second = advance_verified_capture(store, provider, 'second', reserve_bytes=1024**2,
                                          retention_adopted=True)
    final = store.current()
    store.verify(final)
    assert final['parent'] is None
    assert not (root / first['generation']).exists()
    assert (root / second['generation'] / 'objects' / unchanged).stat().st_ino == inode
    assert 'home/state/deleted' not in final['entries']
    assert len(store.inventory()) == 1
    print(json.dumps({'case': case, 'second': second, 'unchanged_inode_preserved': True,
                      'prior_generation_removed': True, 'self_contained': True}))


def reconcile_case(case):
    """Read-only fixture diagnosis after an actual interrupted process exits."""
    store = open_store(case)
    current = store.current()
    store.verify(current)
    root = store.root
    names = sorted(p.name for p in root.iterdir())
    blocked = None
    # Prechecks MUST reject overlaps before consuming anything or creating files.
    if case != 'success':
        try:
            store.advance([], [], expected_previous=current['generation'], reserve_bytes=1024**2)
        except (ValueError, FileNotFoundError) as error:
            blocked = str(error)
        else:
            raise AssertionError('interrupted overlap unexpectedly accepted another capture')
    return {'current_verified': True, 'current_generation': current['generation'],
            'parent': current['parent'], 'capture_blocker': blocked, 'retained_names': names,
            'reconciliation': ('none' if case == 'success' else
                'Preserve current and interrupted fixture artifacts. Diagnose the exact old/partial '
                'generation before separately reviewed reconciliation; do not repeat capture, '
                'delete unknown paths, or restore earlier data.')}


if CONFIG['action'] == 'run':
    run_case(CONFIG['case'])
else:
    print(json.dumps(reconcile_case(CONFIG['case'])))
