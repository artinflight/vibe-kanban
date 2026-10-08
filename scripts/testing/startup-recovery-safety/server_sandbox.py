#!/usr/bin/env python3
"""Real-server regressions, with host workspaces and managers masked by namespaces."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[3]

# Executed inside the private PID, filesystem, manager and network namespaces.
RUNNER = r'''
import hashlib,json,os, pathlib,subprocess,sys,time,urllib.request
base=pathlib.Path('/run/fixture')
def snapshot():
    result={}
    for scope in ('assets','workspaces','external'):
        for path in sorted((base/scope).rglob('*')):
            meta=path.lstat()
            result[str(path.relative_to(base))]=(meta.st_mode,meta.st_mtime_ns,
                os.readlink(path) if path.is_symlink() else
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'directory')
    return result
before=snapshot()
args=json.loads(sys.argv[1])
child=subprocess.Popen(['/run/test-server',*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
    if sys.argv[2]=='serve':
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if child.poll() is not None:
                raise AssertionError('correct startup exited: '+child.stderr.read().decode())
            try:
                with urllib.request.urlopen('http://127.0.0.1:39001/api/info',timeout=.2) as response:
                    data=json.load(response)
                assert data.get('success') is True
                break
            except OSError:
                time.sleep(.05)
        else:
            raise AssertionError('correctly identified startup never served /api/info')
        # All untracked/shared-shaped sentinels must survive normal startup too.
        after=snapshot()
        for key,value in before.items():
            if key.startswith(('workspaces/','external/')):
                assert after.get(key)==value, key
    else:
        stdout,stderr=child.communicate(timeout=5)
        expected=sys.argv[2]=='inspect'
        assert (child.returncode==0)==expected, (args,child.returncode,stderr.decode())
        assert snapshot()==before, 'inspection/rejected startup changed private state'
        if expected and '--build-info' in args:
            assert json.loads(stdout)['automaticWorkspaceDeletion'] is False
finally:
    if child.poll() is None:
        child.kill()
    child.wait(timeout=5)
print('passed',json.dumps(args),sys.argv[2])
'''


def pin(database, root, actual_database, actual_root):
    db = actual_database.stat(); workspace = actual_root.stat()
    return (f'vk-runtime-identity-v1\ndatabase={database}\ndatabase_id={db.st_dev}:{db.st_ino}\n'
            f'workspace_root={root}\nworkspace_root_id={workspace.st_dev}:{workspace.st_ino}\n')


def run_case(binary, label, arguments, outcome):
    with tempfile.TemporaryDirectory(prefix='server-safety-', dir=os.environ.get('VK_SAFETY_TEST_ROOT')) as raw:
        fixture = Path(raw)
        for name in ('assets', 'home', 'workspaces/untracked/repo', 'external'):
            (fixture / name).mkdir(parents=True, exist_ok=True)
        (fixture / 'workspaces/untracked/repo/edit').write_bytes(b'newer surviving work')
        (fixture / 'workspaces/untracked/repo/edit').chmod(0o640)
        (fixture / 'workspaces/untracked/repo/.git').write_text('gitdir: /run/fixture/external/registration\n')
        (fixture / 'external/registration').write_bytes(b'protected registration')
        (fixture / 'workspaces/link').symlink_to('/run/fixture/external', target_is_directory=True)
        config = json.loads((REPO / 'scripts/testing/startup-recovery-safety/private-config.json').read_text())
        config['workspace_dir'] = '/run/fixture/workspaces'
        (fixture / 'assets/config.json').write_text(json.dumps(config))
        database = fixture / 'assets/db.v2.sqlite'
        with sqlite3.connect(database) as connection:
            connection.execute('CREATE TABLE private_fixture_seed (id INTEGER)')
        embedded_assets = str(REPO / 'dev_assets')
        expected_db = embedded_assets + '/db.v2.sqlite'
        receipt = pin(expected_db, '/run/fixture/workspaces', database, fixture / 'workspaces')
        if label == 'empty-receipt': receipt = ''
        if label == 'wrong-database': receipt = receipt.replace(expected_db, '/run/fixture/legacy/db.v2.sqlite')
        if label == 'wrong-root': receipt = receipt.replace('workspace_root=/run/fixture/workspaces', 'workspace_root=/run/fixture/other')
        if label == 'mismatched-object': receipt = receipt.replace('database_id=', 'database_id=999:')
        if label == 'empty-database': database.write_bytes(b'')
        (fixture / 'identity').write_text(receipt)
        command = [shutil.which('bwrap'), '--unshare-all', '--new-session', '--die-with-parent',
                   '--ro-bind', '/', '/', '--tmpfs', '/home', '--tmpfs', '/mnt', '--tmpfs', '/run',
                   '--proc', '/proc', '--dev', '/dev', '--bind', str(fixture), '/run/fixture',
                   '--ro-bind', str(binary), '/run/test-server', '--bind', str(fixture / 'assets'), embedded_assets,
                   '--clearenv', '--setenv', 'HOME', '/run/fixture/home', '--setenv', 'PATH', '/usr/bin:/bin',
                   '--setenv', 'BACKEND_PORT', '39001', '--setenv', 'PREVIEW_PROXY_PORT', '39002',
                   '--setenv', 'RUST_LOG', 'error', '--setenv', 'VK_DISABLE_PR_MONITOR', '1',
                   '--setenv', 'DISABLE_ATTACHMENT_CLEANUP', '1']
        if label != 'missing-receipt':
            command += ['--setenv', 'VK_RUNTIME_IDENTITY_FILE', '/run/fixture/identity']
        command += ['--chdir', '/run/fixture', '/usr/bin/python3', '-c', RUNNER, json.dumps(arguments), outcome]
        result = subprocess.run(command, capture_output=True, text=True, timeout=25)
        if result.returncode:
            raise AssertionError(f'{label}: {result.stdout}\n{result.stderr}')
        print(label, result.stdout.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    if not shutil.which('bwrap'):
        parser.error('bubblewrap is required; no host-execution fallback')
    binary = args.binary.resolve(strict=True)
    for arguments in (['--vk-build-info'], ['--help', '--vk-build-info'], ['--build-info', 'extra'], ['--']):
        run_case(binary, 'unknown-invocation', arguments, 'reject')
    for arguments in (['--help'], ['--version'], ['--build-info']):
        run_case(binary, 'missing-receipt', arguments, 'inspect')
    for label in ('missing-receipt', 'empty-receipt', 'wrong-database', 'wrong-root', 'mismatched-object', 'empty-database'):
        run_case(binary, label, [], 'reject')
    run_case(binary, 'correct-identity', [], 'serve')


if __name__ == '__main__':
    main()
