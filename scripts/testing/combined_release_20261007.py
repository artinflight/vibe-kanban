"""Bind the repaired release to real frontend assets; never activate services."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

SOURCE = Path('/mnt/vk-storage/vk-combined-release-20261007/source')
REVISION = '5ec5722455d9b12ae8a9b00b371351ad12a685ef'
ROOT = SOURCE.parent / 'final-package'
BUNDLE = Path('/mnt/vk-storage/vk-scheduled-first-run-20261006/bundle-' + REVISION)
FRONTEND = Path('/mnt/vk-storage/vk-first-run-gates-20261006/frontend-86f62b2/frontend-build.json')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(name, value):
    with (ROOT / name).open('x') as stream:
        json.dump(value, stream, indent=2)


def package():
    assert os.path.ismount('/mnt/vk-storage')
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip() == REVISION
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=SOURCE)
    build = json.loads(FRONTEND.read_text())
    manifest = json.loads((BUNDLE / 'manifest.json').read_text())
    assert manifest['sourceCommit'] == REVISION
    inputs = ['packages', 'shared', 'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml']
    assert not subprocess.check_output(['git', 'diff', build['sourceCommit'], REVISION, '--', *inputs], cwd=SOURCE)
    assets = {name: Path(build['dist']) / name for name in build['assets']}
    assert all(sha(path) == build['assets'][name] for name, path in assets.items())
    assert '/assets/' in assets['index.html'].read_text()
    assert len(assets) > 100 and len(assets['index.html'].read_bytes()) > 500
    required = sum(p.stat().st_size for p in assets.values()) + sum(r['bytes'] for r in manifest['artifacts'].values())
    fs = os.statvfs('/mnt/vk-storage')
    assert fs.f_bavail * fs.f_frsize > required + 8 * 1024**3
    ROOT.mkdir(mode=0o700)
    bindings = {}
    for kind in ('candidate', 'rollback'):
        release = ROOT / kind
        release.mkdir()
        for name in (kind + '/server', 'vk-capacity-guard'):
            original = BUNDLE / name
            assert sha(original) == manifest['artifacts'][name]['sha256']
            target = release / original.name
            shutil.copy2(original, target)
            assert sha(target) == sha(original)
            bindings[str(target.relative_to(ROOT))] = sha(target)
        for name, original in assets.items():
            target = release / 'frontend' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
            assert sha(target) == build['assets'][name]
            bindings[str(target.relative_to(ROOT))] = sha(target)
    save('manifest.json', {'source': REVISION, 'tree': manifest['sourceTree'],
        'frontend_source': build['sourceCommit'], 'frontend_build_receipt': sha(FRONTEND),
        'frontend_inputs_unchanged': True, 'frontend_assets': len(assets),
        'files': bindings, 'production_changed': False, 'cutover_ready': False,
        'rollback': 'compile-disabled v2 reader; same latest data, never old snapshot',
        'remaining': ['matching routing module', 'full handover rehearsal', 'fresh final capture and idle checks']})
    print(json.dumps({'package': str(ROOT), 'bound_files': len(bindings), 'production_changed': False}))


if __name__ == '__main__':
    assert sys.argv[1:] == ['package']
    package()
