"""Run the opt-in real ACP adapter test in a bounded disposable filesystem.

Requires explicit account authorization. The caller supplies the already-compiled
unit test, pinned hashes, a previously advertised model ID, and the existing
personal credential file. Only the native runtime reads that credential through
a read-only bind mount; this runner never reads, copies or logs its contents.
The test sends at most two prompts (write approval/denial, native resume with cancellation), never enables Vibe,
and refuses a consumed output directory. Keep all results private.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess


def verified(path, expected):
    path = Path(path).resolve(strict=True)
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
            raise ValueError('Executable identity changed; nothing launched')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('test-executable', 'test-sha256', 'runtime', 'runtime-sha256',
                'harness-sha256', 'credential-file', 'model', 'output', 'build-lock'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    # Hold the existing compiler ownership boundary while executing its artifact.
    lock = Path(args.build_lock).open('rb')
    fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
    binary = verified(args.test_executable, args.test_sha256)
    runtime = verified(args.runtime, args.runtime_sha256)
    harness = verified(runtime.parent / 'localharness_external', args.harness_sha256)
    credential = Path(args.credential_file).resolve(strict=True)
    if not credential.is_file():
        raise ValueError('Existing personal-account credential file required')
    output = Path(args.output).resolve()
    mount = subprocess.check_output(['findmnt', '-n', '-o', 'TARGET', '--target', str(output.parent)], text=True).strip()
    if mount != '/mnt/vk-storage':
        raise ValueError('Mounted secondary SSD required')
    output.mkdir(mode=0o700)
    native_home = output / 'native-home'
    token_mount = native_home / 'antigravity-acp' / 'acp_token.json'
    token_mount.parent.mkdir(mode=0o700, parents=True)
    token_mount.touch(mode=0o600)  # Empty placeholder; never a credential copy.
    command = ['/usr/bin/bwrap', '--die-with-parent', '--unshare-all', '--share-net', '--new-session']
    for item in ('/usr', '/lib', '/lib64', '/etc/ld.so.cache', '/etc/ssl/certs',
                 '/etc/resolv.conf', '/etc/hosts', '/etc/passwd', '/etc/alternatives',
                 '/sys/devices/system/cpu/possible', '/sys/devices/system/cpu/present'):
        command += ['--ro-bind', item, item]
    command += ['--symlink', 'usr/bin', '/bin', '--tmpfs', '/home/mcp', '--tmpfs', '/tmp',
                '--tmpfs', '/run', '--proc', '/proc', '--dev', '/dev',
                '--ro-bind', str(binary), str(binary), '--ro-bind', str(runtime), str(runtime),
                '--ro-bind', str(harness), str(harness),
                '--bind', str(output), str(output), '--ro-bind', str(credential), str(token_mount),
                '--clearenv']
    environment = dict(HOME='/home/mcp', USER='mcp', LOGNAME='mcp', LANG='C.UTF-8',
                       PATH='/usr/bin:/bin', GEMINI_HOME=str(native_home), BROWSER='/bin/false',
                       VK_AG_NATIVE_TEST_ROOT=str(output), VK_AG_NATIVE_RUNTIME=str(runtime),
                       VK_AG_NATIVE_RUNTIME_SHA256=args.runtime_sha256, VK_AG_NATIVE_MODEL=args.model)
    for key, value in environment.items():
        command += ['--setenv', key, value]
    command += ['--chdir', str(output), str(binary), '--exact',
                'executors::acp::supervised::native_acceptance::antigravity_native_write_approval_denial_resume_and_cancel',
                '--ignored', '--test-threads=1']
    result = dict(schema=1, max_prompt_calls=2, runtime_sha256=args.runtime_sha256,
                  test_sha256=args.test_sha256, harness_sha256=args.harness_sha256, credential_read_by_runner=False,
                  original_credential_read_only=True, production_changed=False)
    child = None
    try:
        with (output / 'test.private.log').open('xb') as log:
            os.chmod(log.name, 0o600)
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                result['exit_code'] = child.wait(timeout=300)
            except subprocess.TimeoutExpired:
                result['timed_out'] = True
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)
        result['owned_process_reaped'] = child is None or child.poll() is not None
        path = output / 'RUNNER.safe.json'
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
            json.dump(result, stream, indent=2)
        print(json.dumps(result))
    return 0 if result.get('exit_code') == 0 else 2


if __name__ == '__main__':
    raise SystemExit(main())
