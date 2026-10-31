#!/usr/bin/env python3
"""Recheck retained October 7 evidence without importing any placement program.

The original retained manifest authenticates the private-recovery receipt locally;
its earlier Desktop verification is historical evidence, not refreshed here.
No archive is extracted and no live path is written. Output goes to stdout.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
INCIDENT = Path('/mnt/vk-storage/vk-combined-release-20261007/incident-2316')
spec = importlib.util.spec_from_file_location('recovery_audit', REPO / 'scripts/verify_recovered_tree.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main():
    evidence = json.loads((INCIDENT / 'evidence-manifest.json').read_text())
    source = INCIDENT / 'private-recovery-result.json'
    raw = source.read_bytes()
    expected = evidence['files'][source.name]
    if len(raw) != expected['bytes'] or hashlib.sha256(raw).hexdigest() != expected['sha256']:
        raise ValueError('retained private recovery receipt does not match retained incident manifest')
    receipt = json.loads(raw)
    if receipt.get('passed') is not True:
        raise ValueError('no accepted private recovery receipt')
    entries = [{'path': name, 'type': 'file', **row} for name, row in receipt['files'].items()]
    # The receipt contains no authenticated directory/link metadata. Those names
    # are therefore reported as uncovered, even when they currently exist.
    missing_baseline = json.loads((INCIDENT / 'missing-baseline-paths.json').read_text())
    journal = json.loads((INCIDENT / 'journal-after.json').read_text())
    result = module.audit(Path('/'), entries, journal, missing_baseline)
    result['incident_receipt_sha256'] = expected['sha256']
    result['archive_authentication'] = 'retained authenticated stream receipts; no fresh B stream read in this audit'
    result['receipt_has_authenticated_link_directory_metadata'] = False
    result['journal_binding'] = 'no complete capture-to-incident bound coverage; gaps retained'
    result['survivor_difference_policy'] = 'Report differences; never replace newer surviving content.'
    print(json.dumps(result, indent=2))
    return 0 if result['baseline_verified'] and result['journal_coverage_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
