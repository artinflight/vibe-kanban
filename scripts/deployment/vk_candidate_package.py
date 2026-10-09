"""Bind a NEW offline candidate tool package; never authorize an operational release.

The reviewed PR229 package builder stays unchanged. Add its required review
receipt and candidate contracts to this newly built package before publishing
its receipt. Empty inventories are allowed only as explicitly labelled fixtures.
No archive transfer, service, route, credential change or cleanup is performed.
"""
import hashlib
import json
from pathlib import Path
import shutil

import vk_recovery_package
from vk_candidate_direct_b import PR229, source_pins
from vk_candidate_generation import require
from vk_prep_common import digest, save

MODULES = ('vk_candidate_generation.py', 'vk_candidate_direct_b.py', 'vk_candidate_scaffold.py',
           'vk_candidate_scope.py', 'vk_candidate_scope_plan.py', 'vk_candidate_package.py',
           'vk_candidate_owner.py')
REVIEW = 'receipts/direct-stream-20261008.json'
# Exact retained verifier package, created before preparation-lifetime tooling.
# Its original six-module contract is valid only with both immutable receipts.
RECORDED_VERIFIERS = {
    '01af7c36f1ba969fa4457278b8fd0978fe76c2b1': (
        '7741c433dbb255741e425ed3d11f982ed7e448d92cb37a0629051f1ea48bbf4c',
        'e7856e60d87478f75f7ecac9999135f5e4a64fff2f76260b655ce77e6eda425d'),
}


def build(root, inventory_path, *, fixture_only=False):
    inventory = json.loads(Path(inventory_path).read_text())
    require(bool(inventory['archive_files']) or fixture_only,
            'empty archive inventory is only a tool-binding fixture')
    pins = source_pins()
    vk_recovery_package.build(root, inventory_path)
    root = Path(root)
    source = Path(__file__).parent
    target = root / 'tools' / REVIEW
    target.parent.mkdir()
    shutil.copy2(source / REVIEW, target)
    recovery_path = root / 'recovery-package.json'
    recovery = json.loads(recovery_path.read_text())
    recovery['sha256']['tools/' + REVIEW] = digest(target)
    save(recovery_path, recovery)
    contract = {'schema': 1, 'source_commit': recovery['source_commit'],
                'reviewed_direct_b_head': PR229, 'reviewed_source_sha256': pins,
                'fixture_only': fixture_only, 'operational_acceptance': False,
                'combined_backend_binary_bound': False, 'cutover_authorized': False,
                'recovery_package_sha256': digest(recovery_path),
                'required_modules': {name: recovery['sha256']['tools/' + name] for name in MODULES},
                'review_receipt_sha256': digest(target)}
    save(root / 'candidate-tool-binding.json', contract)
    return verify(root)


def verify(root, *, expected_source=None):
    root = Path(root)
    result = vk_recovery_package.verify(root)
    contract = json.loads((root / 'candidate-tool-binding.json').read_text())
    required_modules = set(MODULES)
    if expected_source is not None:
        require(result['source_commit'] == expected_source, 'recorded package source differs')
        if expected_source in RECORDED_VERIFIERS:
            contract_sha, recovery_sha = RECORDED_VERIFIERS[expected_source]
            require(digest(root / 'candidate-tool-binding.json') == contract_sha
                    and digest(root / 'recovery-package.json') == recovery_sha,
                    'recorded verifier receipts differ')
            required_modules.remove('vk_candidate_owner.py')
    require(contract['source_commit'] == result['source_commit']
            and contract['reviewed_direct_b_head'] == PR229
            and contract['recovery_package_sha256'] == digest(root / 'recovery-package.json')
            and contract['operational_acceptance'] is False
            and contract['combined_backend_binary_bound'] is False
            and contract['cutover_authorized'] is False,
            'candidate package binding differs or claims operational acceptance')
    require(set(contract['required_modules']) == required_modules, 'candidate package omitted required contracts')
    for name, checksum in contract['required_modules'].items():
        require(digest(root / 'tools' / name) == checksum, 'candidate contract changed: ' + name)
    review_path = root / 'tools' / REVIEW
    require(digest(review_path) == contract['review_receipt_sha256'], 'candidate review receipt changed')
    pins = json.loads(review_path.read_text())['source_sha256']
    require(pins == contract['reviewed_source_sha256'] and len(pins) == 8,
            'packaged reviewed source inventory differs')
    for raw, checksum in pins.items():
        require(raw.startswith('scripts/deployment/') and '..' not in Path(raw).parts,
                'unsafe packaged reviewed source selector')
        require(hashlib.sha256((root / 'tools' / Path(raw).name).read_bytes()).hexdigest() == checksum,
                'packaged direct-B source changed')
    return {**result, 'candidate_modules_verified': len(required_modules),
            'reviewed_source_files_verified': len(pins), 'fixture_only': contract['fixture_only'],
            'combined_backend_binary_bound': False, 'operational_acceptance': False}
