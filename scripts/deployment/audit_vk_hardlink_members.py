"""Read authenticated retained member inventories; never extract or delete archives."""
import argparse
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import time

from vk_prep_common import digest, save, storage


def audit(inventory_path, audit_root):
    inventory = json.loads(inventory_path.read_text())
    complete = json.loads((audit_root / 'chain-audit.json').read_text())
    if not complete['passed']:
        raise ValueError('Prior full stream audit did not pass')
    rows, totals, links = [], Counter(), []
    for original in inventory['archive_files']:
        folder = audit_root / Path(original['local']).name.removesuffix('.tar.zst')
        receipt = json.loads((folder / 'result.json').read_text())
        members = folder / 'members.jsonl.gz'
        bound = complete['archive_results'][original['local']]
        if (not receipt['passed'] or receipt['sha256'] != original['sha256']
                or bound['sha256'] != original['sha256']
                or receipt['member_inventory_sha256'] != digest(members)
                or digest(Path(original['receipt'])) != bound['descriptor_sha256']):
            raise ValueError('Retained inventory/descriptor binding changed')
        st = Path(original['local']).stat()
        identity = [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]
        if identity != bound['local_identity']:
            raise ValueError('Original archive identity changed since full stream audit')
        counts = Counter()
        with gzip.open(members, 'rt') as stream:
            for line in stream:
                row = json.loads(line)
                counts[row['type']] += 1
                if row['type'] == '1':
                    links.append({'archive': original['local'], **row})
        totals.update(counts)
        rows.append({'archive': original['local'], 'archive_sha256': original['sha256'],
                     'inventory': str(members), 'inventory_sha256': digest(members),
                     'member_types': dict(counts), 'archive_identity_unchanged': True})
    checked = {row['archive'] for row in rows}
    heads = []
    for head in inventory['backup_chain_heads']:
        if not set(head['chain']).issubset(checked):
            raise ValueError('Head requires uninspected archive')
        descriptor = json.loads(Path(head['descriptor']).read_text())
        archive = str(Path(descriptor['folder']) / descriptor['archive'])
        if archive != head['chain'][0]:
            raise ValueError('Current head no longer matches audited chain')
        heads.append({'descriptor': head['descriptor'], 'archives': len(head['chain']),
                      'guarded_restore_parent': str(Path(descriptor['folder']).parent.parent.resolve())})
    return {'at': time.time(), 'passed': True, 'inventory_sha256': digest(inventory_path),
            'prior_stream_audit_sha256': digest(audit_root / 'chain-audit.json'),
            'archives': rows, 'heads': heads, 'member_types': dict(totals),
            'hardlinks': links, 'hardlink_count': len(links),
            'specific_persisted_hardlink_case_applicable': bool(links),
            'actual_data_loss_established': False, 'full_filesystem_restore_performed': False,
            'archive_payloads_reread': False, 'originals_modified': False,
            'limit': 'Hardlink presence would need chronological follow-up; no hardlinks rules out this specific case only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', required=True, type=Path)
    parser.add_argument('--audit-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = storage(args.output)
    if output.exists():
        raise ValueError('Keep earlier audit evidence; use a new output')
    result = audit(args.inventory, args.audit_root)
    fs = os.statvfs(output.parent)
    result['free_bytes_at_audit'] = fs.f_bavail * fs.f_frsize
    save(output, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'archives'}, indent=2))


if __name__ == '__main__':
    main()
