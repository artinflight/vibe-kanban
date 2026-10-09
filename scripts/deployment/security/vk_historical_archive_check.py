"""Exact historical profile, root metadata-only. No live installation.

Only a fixed root-owned audited module is loaded. No caller-selected imports,
paths, command arguments, artifact bytes, deletion or controller execution.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time

CODE = '/usr/local/libexec/vk-historical-archive-inspection-v1.py'
LIBRARY = '/usr/local/libexec/vk-process-inspection-v1.py'
POLICY = '/etc/vibe-kanban/historical-archive-inspection-v1.json'
PROFILE = 'historical-archive-v1'
CONTROL_PATH = '/mnt/vk-storage/vk-process-inspection-managed-v1'
UUID = '26e4cac1-f2cf-485b-b1bc-d1be197a747e'
TARGET = {
    'path': '/mnt/vk-storage/vk-combined-preparation-20261007/backups/checkpoint-/db5bb16b095241319a79e02e5fc8cdf6/checkpoint--db5bb16b095241319a79e02e5fc8cdf6.tar.zst',
    'identity': {'dev': 2065, 'ino': 7340415, 'size': 23441521918,
                 'mtime_ns': 1791409456129506845, 'ctime_ns': 1791409456129506845,
                 'nlink': 1, 'uid': 1000, 'gid': 1000, 'mode': 0o100600},
    'sha256': 'e994567edaacc75d8aa9a3497b8384a8dbacec462854a3f7f8c5760e1a9a0ce4',
}
BACKUP = '27e8d486516ab818eee8376178badc9df3a5ddb6f42c6639c8021e5c7b893a2f'
APPROVAL = 'Sentinel_3c972054e9688191900e38417fd55e00'


def bootstrap_trust(path):
    # Fixed installed code paths only, before loading any shared module.
    item = Path(path)
    for parent in [*list(item.parents)[::-1], item]:
        info = parent.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or not (
            stat.S_ISREG(info.st_mode) and info.st_nlink == 1 if parent == item
            else stat.S_ISDIR(info.st_mode)
        ):
            raise ValueError('inspection blocked')


def load_common():
    bootstrap_trust(CODE)
    bootstrap_trust(LIBRARY)
    spec = importlib.util.spec_from_file_location('_vk_audited_proc_v1', LIBRARY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_profile(common, policy, request):
    common.validate_request(request)
    common.require(type(policy) is dict and set(policy) == {
        'abi', 'profile', 'caller_uid', 'control_scope', 'target',
        'backup_manifest_sha256', 'approval_reference'})
    common.require(type(policy['abi']) is int and policy['abi'] == 1
                   and policy['profile'] == PROFILE and type(policy['caller_uid']) is int
                   and policy['caller_uid'] == 1000
                   and common.canonical(policy['target']) == common.canonical(TARGET)
                   and policy['backup_manifest_sha256'] == BACKUP
                   and policy['approval_reference'] == APPROVAL)
    control = policy['control_scope']
    common.validate_policy({'abi': 1, 'caller_uid': 1000, 'scopes': {PROFILE: control}})
    common.require(control['path'] == CONTROL_PATH and control['filesystem_uuid'] == UUID)
    manifest = request['manifest']
    common.require(manifest['scope_id'] == PROFILE and manifest['backup_manifest_sha256'] == BACKUP)
    common.require(len(manifest['targets']) == 1)
    target = manifest['targets'][0]
    common.require(target['name'] == Path(TARGET['path']).name
                   and target['identity'] == TARGET['identity'] and target['sha256'] == TARGET['sha256'])


def inspect_target(common, policy):
    # Policy was compared to immutable exact constants, not caller paths.
    fd = common.open_path(policy['target']['path'])
    try:
        info = os.fstat(fd)
        common.require(common.identity(info) == policy['target']['identity']
                       and stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        return {(info.st_dev, info.st_ino)}
    finally:
        os.close(fd)  # no own target reference during scan


def check(common, policy, request):
    validate_profile(common, policy, request)
    common.visibility()
    control_policy = {'abi': 1, 'caller_uid': 1000, 'scopes': {PROFILE: policy['control_scope']}}
    scope = common.open_scope(control_policy, request['manifest'])
    try:
        common.live_owner(scope, request, policy['caller_uid'])
        targets = inspect_target(common, policy)
        scanned_at, scanned_mono = time.time_ns(), time.monotonic_ns()
        guards = common.target_guards(request)
        visibility = common.scan_consumers(targets, owner_pid=request['owner_pid'], guards=guards)
        common.require(common.target_guards(request) == guards)
        common.visibility()
        common.live_owner(scope, request, policy['caller_uid'])
        common.require(inspect_target(common, policy) == targets)
        current = common.open_scope(control_policy, request['manifest'])
        try:
            common.require((os.fstat(current).st_dev, os.fstat(current).st_ino) ==
                           (os.fstat(scope).st_dev, os.fstat(scope).st_ino))
        finally:
            os.close(current)
        return {'abi': 1, 'profile': PROFILE, 'nonce': request['nonce'],
                'owner_pid': request['owner_pid'], 'owner_start': request['owner_start'],
                'inspection_manifest_sha256': common.digest(request['manifest']),
                'scan_started_ns': scanned_at, 'issued_ns': time.time_ns(),
                'scan_started_mono_ns': scanned_mono, 'issued_mono_ns': time.monotonic_ns(),
                'euid': 0, 'consumer_clearance_passed': True, 'visibility': visibility,
                'target_metadata_verified': True, 'target_content_hashes_verified_by_root': False,
                'action_authorized': False, 'deletion_performed': False, 'production_changed': False}
    finally:
        os.close(scope)


def main():
    try:
        if not (len(sys.argv) == 1 and sys.flags.isolated and sys.flags.no_site
                and sys.flags.dont_write_bytecode and os.geteuid() == 0 and __file__ == CODE):
            raise ValueError('inspection blocked')
        common = load_common()
        common.trusted_path(os.path.realpath('/usr/bin/python3'))
        common.trusted_path(POLICY)
        with open(POLICY, 'rb') as stream:
            raw_policy = stream.read(common.MAX_JSON + 1)
        result = check(common, common.parse_json(raw_policy), common.read_json_fd(0))
        for key, path in (('code_sha256', CODE), ('library_sha256', LIBRARY)):
            with open(path, 'rb') as stream:
                raw = stream.read(common.MAX_JSON + 1)
            common.require(len(raw) <= common.MAX_JSON)
            result[key] = hashlib.sha256(raw).hexdigest()
        result['policy_sha256'] = hashlib.sha256(raw_policy).hexdigest()
        print(common.encode_receipt(result))
        return 0
    except Exception:
        print('{"consumer_clearance_passed":false,"reason":"inspection blocked"}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
