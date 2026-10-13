"""Unprivileged exact-profile adapter; no deletion, cutover or live adoption.

Existing CandidateController backup/fence/promote/fallback gates remain with the
owning controller. Only its consumer inspection is added at the held boundary.
"""
import hashlib
import os
from pathlib import Path
import subprocess

import vk_retirement_preflight as boundary

PROFILE = 'historical-archive-v1'
PATH = Path('/mnt/vk-storage/vk-combined-preparation-20261007/backups/checkpoint-/db5bb16b095241319a79e02e5fc8cdf6/checkpoint--db5bb16b095241319a79e02e5fc8cdf6.tar.zst')
IDENTITY = {'dev': 2065, 'ino': 7340415, 'size': 23441521918,
            'mtime_ns': 1791409456129506845, 'ctime_ns': 1791409456129506845,
            'nlink': 1, 'uid': 1000, 'gid': 1000, 'mode': 0o100600}
SHA256 = 'e994567edaacc75d8aa9a3497b8384a8dbacec462854a3f7f8c5760e1a9a0ce4'
BACKUP = '27e8d486516ab818eee8376178badc9df3a5ddb6f42c6639c8021e5c7b893a2f'
COMMAND = ('/usr/bin/sudo', '-n', '--', '/usr/local/sbin/vk-historical-archive-inspect-v1')


def manifest_for(lease_identity, *, source_sha256, root_binding, release_id, guard_held=False):
    return {'scope_id': PROFILE, 'release_id': release_id, 'source_sha256': source_sha256,
            'root_binding': root_binding, 'backup_manifest_sha256': BACKUP, 'lease': dict(lease_identity),
            'targets': [{'name': PATH.name, 'identity': dict(IDENTITY), 'sha256': SHA256, 'guard_held': guard_held}]}


def validate_manifest(manifest):
    boundary.require(manifest['scope_id'] == PROFILE and manifest['backup_manifest_sha256'] == BACKUP
                     and len(manifest['targets']) == 1)
    target = manifest['targets'][0]
    boundary.require(set(target) == {'name', 'identity', 'sha256', 'guard_held'}
                     and target['name'] == PATH.name and target['identity'] == IDENTITY
                     and target['sha256'] == SHA256 and type(target['guard_held']) is bool)


def open_target(flags):
    # Constant path only; every parent and leaf no-follow, no enumeration.
    parent = os.open('/', os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for name in PATH.parts[1:-1]:
            child = os.open(name, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            os.close(parent)
            parent = child
        return os.open(PATH.name, flags | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
    finally:
        os.close(parent)


def metadata(fd):
    return {key: getattr(os.fstat(fd), 'st_' + key) for key in IDENTITY}


def hash_archive(_scope_path, manifest):
    validate_manifest(manifest)
    # Ordinary file-owner permissions; NOATIME preserves historical metadata.
    with os.fdopen(open_target(os.O_RDONLY | os.O_NONBLOCK | os.O_NOATIME), 'rb') as stream:
        boundary.require(metadata(stream.fileno()) == IDENTITY)
        checksum = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
        boundary.require(checksum.hexdigest() == SHA256 and metadata(stream.fileno()) == IDENTITY)
    verify_metadata(_scope_path, manifest)


def verify_metadata(_scope_path, manifest):
    validate_manifest(manifest)
    fd = open_target(os.O_PATH)
    try:
        boundary.require(metadata(fd) == IDENTITY)
    finally:
        os.close(fd)


def launch_checker():
    return subprocess.Popen(COMMAND, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'}, close_fds=True)


def validate_receipt(receipt, request, installation):
    boundary.require(set(installation) == {'code_sha256', 'policy_sha256', 'library_sha256'}
                     and receipt.get('profile') == PROFILE
                     and receipt.get('library_sha256') == installation['library_sha256'])
    boundary.validate_receipt(receipt, request, {key: installation[key] for key in ('code_sha256', 'policy_sha256')})


def at_archive_boundary(**kwargs):
    # Handler selection is fixed source, never root request fields or a command.
    boundary.require('_handlers' not in kwargs)
    validate_manifest(kwargs['manifest'])
    return boundary.at_held_boundary(**kwargs, _handlers=(hash_archive, verify_metadata, launch_checker, validate_receipt))
