#!/usr/bin/env python3
"""Pinned finite backend child: archive or restore one existing workspace.

No service restart, SQL migration, agent dispatch, retry daemon or schedule action.
The backend retains inputs and invokes this helper under its current configuration.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import uuid

MODULES = {'driver.py', 'host.py', 'process_probe.py', 'provider_factory.py',
           'authority.py', 'catalog.py', 'controller.py', 'custody.py', 'ownership.py',
           'nightly_binding.py', 'nightly_selection.py', 'process_use.py', 'inventory.py', 'payloads.py', 'lifecycle.py', 'normal_b.py',
           'git_dependency.py', 'shared_dependency.py', 'shared_files.py'}


def version(st):
    return tuple(getattr(st, name) for name in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_uid', 'st_gid', 'st_nlink'))


def configuration(path):
    # Verify the whole Python implementation before importing a local module.
    path = Path(path)
    before = path.lstat()
    if (not path.is_absolute() or path.resolve(strict=True) != path or not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid() or before.st_nlink != 1 or before.st_mode & 0o077):
        raise ValueError('Private canonical archive configuration required')
    raw = path.read_bytes()
    value = json.loads(raw)
    if value['format'] != 'vk-workspace-archive-driver-v1':
        raise ValueError('Unknown physical driver protocol')
    folder = Path(__file__).resolve().parent
    refs = {ref['path']: ref for ref in value['source_pins']}
    for name in MODULES:
        source = folder / name
        ref = refs.get(str(source))
        info = source.lstat()
        if (ref is None or source.resolve(strict=True) != source or not stat.S_ISREG(info.st_mode)
                or info.st_uid not in (0, os.getuid()) or info.st_nlink != 1 or info.st_mode & 0o022
                or hashlib.sha256(source.read_bytes()).hexdigest() != ref['sha256']
                or version(source.lstat()) != version(info)):
            raise ValueError('Physical driver source closure changed')
    if version(path.lstat()) != version(before):
        raise ValueError('Physical driver configuration changed')
    return value, dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())


def run(path, workspace, action):
    value, reference = configuration(path)
    from contextlib import closing, redirect_stdout
    from authority import WorkspaceAuthority
    from catalog import Catalog
    from controller import Controller
    from custody import Custody
    from host import Host
    from shared_dependency import SharedGit
    from shared_files import SharedFiles
    import provider_factory
    workspace = str(uuid.UUID(workspace))
    # The sole stdout object is the backend's bounded receipt. Provider chatter
    # cannot masquerade as success or expose private diagnostics in the UI.
    with redirect_stdout(sys.stderr), Custody(value['custody_root'], workspace, exclusive=True) as custody:
        host = Host(value, custody, reference)
        host.qualify()
        authority = WorkspaceAuthority(workspace, value, host)
        # Construction reads pinned configuration; capture/connection work only
        # begins after Controller has qualified the actual serving pair.
        provider = provider_factory.create(value['nightly'],
            lambda: host.check() if authority.action is None else authority.check(workspace))
        authority.bind_dependencies(SharedGit(value['dependency_root'], value['custody_root'], provider, authority),
                                    SharedFiles(value['dependency_root'], value['custody_root'], provider, authority))
        with closing(Catalog(value['database'])) as catalog:
            return Controller(catalog, custody, provider, authority, value['staging_root']).run(action)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('action', choices=('archive', 'ensure'))
    args = parser.parse_args()
    try:
        result = run(args.config, args.workspace, args.action)
    except Exception as error:
        # No exception text/credentials/paths enter ordinary user-facing errors.
        print(json.dumps(dict(format='vk-workspace-archive-driver-result-v1', complete=False,
                              failure_type=type(error).__name__, retained=True)))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
