"""Create and verify a NEW portable Desktop-backed recovery tool package.

Does not touch sealed packages, install services, retire archives or restore live data.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from vk_archive_store import install_locators, reference
from vk_prep_common import digest, save, storage


def build(root, inventory_path, *, require_clean=True):
    source = Path(__file__).resolve().parent
    repo = source.parents[1]
    root = storage(root)
    if root.exists():
        raise ValueError('Use a new recovery package; never rewrite existing evidence')
    if require_clean and subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain']).strip():
        raise ValueError('Commit operational source before packaging')
    inventory = json.loads(Path(inventory_path).read_text())
    descriptors = []
    for row in inventory['archive_files']:
        result = json.loads(Path(row['receipt']).read_text())
        ref = reference(result)
        if (str(Path(ref['folder']) / ref['archive']) != row['local']
                or ref['sha256'] != row['sha256'] or ref.get('bytes') != row['bytes']
                or ref.get('desktop_directory', '').rstrip('/') + '/' + ref['archive'] != row['remote']):
            raise ValueError('Inventory/retained descriptor disagree')
        descriptors.append(result)
    install_locators(descriptors)
    root.mkdir(mode=0o700)
    tools = root / 'tools'; tools.mkdir(mode=0o700)
    bound = []
    for path in source.glob('*.py'):
        target = tools / path.name
        shutil.copy2(path, target)
        bound.append(target)
    for index, result in enumerate(descriptors):
        path = root / 'descriptors' / (str(index) + '.json')
        save(path, result); bound.append(path)
    heads = []
    for index, row in enumerate(inventory['backup_chain_heads']):
        result = json.loads(Path(row['descriptor']).read_text())
        if reference(result) not in [reference(d) for d in descriptors]:
            raise ValueError('Current head is outside the retained descriptor inventory')
        path = root / 'heads' / (str(index) + '.json')
        save(path, result); bound.append(path)
        heads.append({'name': str(index), 'original': row['descriptor'], 'descriptor': str(path.relative_to(root))})
    save(root / 'inventory.json', inventory); bound.append(root / 'inventory.json')
    receipt = {'schema': 1, 'source_commit': subprocess.check_output(
        ['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
        'production_modified': False, 'archives_retired': 0, 'cutover_authorized': False,
        'heads': heads, 'inventory_sha256': digest(inventory_path),
        'sha256': {str(path.relative_to(root)): digest(path) for path in bound}}
    save(root / 'recovery-package.json', receipt)
    return verify(root)


def verify(root):
    root = storage(root)
    receipt = json.loads((root / 'recovery-package.json').read_text())
    required = ['vk_archive_store.py', 'vk_rolling_backup.py', 'vk_recovery_package.py',
                'vk_prepare.py', 'vk_operational_package.py', 'vk_direct_capture.py',
                'vk_archive_stream.py', 'vk_desktop_transport.py']
    for name in required:
        if 'tools/' + name not in receipt['sha256']:
            raise ValueError('Missing required recovery tool: ' + name)
    for raw, checksum in receipt['sha256'].items():
        path = root / raw
        if (Path(raw).is_absolute() or '..' in Path(raw).parts or path.is_symlink()
                or not path.resolve().is_relative_to(root) or digest(path) != checksum):
            raise ValueError('Recovery package changed: ' + raw)
    install_locators([json.loads((root / raw).read_text()) for raw in receipt['sha256']
                      if raw.startswith('descriptors/')])
    return {'passed': True, 'source_commit': receipt['source_commit'],
            'files_verified': len(receipt['sha256']), 'heads': receipt['heads'],
            'cutover_authorized': False, 'archives_retired': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('backup_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    result = build(args.root, args.inventory) if args.inventory else verify(args.root)
    if args.backup_args:
        if Path(__file__).resolve() != args.root.resolve() / 'tools/vk_recovery_package.py':
            raise ValueError('Run the bound package entrypoint, not an external checkout')
        import vk_rolling_backup
        sys.argv = [str(Path(vk_rolling_backup.__file__)), *args.backup_args[1:]] if args.backup_args[0] == '--' else [str(Path(vk_rolling_backup.__file__)), *args.backup_args]
        vk_rolling_backup.main()
    else:
        print(json.dumps(result))


if __name__ == '__main__':
    main()
