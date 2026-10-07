#!/usr/bin/env python3
"""Prepare, validate and atomically publish AutoSwitch releases; never restart VK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def storage(path):
    subprocess.run(['mountpoint', '-q', '/mnt/vk-storage'], check=True)
    path = path.absolute()
    if not path.resolve().is_relative_to('/mnt/vk-storage'):
        raise ValueError('Module artifacts must be on mounted /mnt/vk-storage')
    return path


def verify(release, validator):
    # This is the real backend loader, including a sandboxed no-inference probe.
    result = subprocess.run([str(validator), '--verify-release', str(release)],
                            check=True, capture_output=True, text=True, timeout=10)
    return json.loads(result.stdout)


def prepare(args):
    root = storage(args.root)
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', args.version):
        raise ValueError('Use a plain version identifier')
    root.mkdir(parents=True, exist_ok=True)
    target = root / 'releases' / args.version
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        raise ValueError('Release already exists; use a new version')
    # Pin the backend-matched loader once; never execute an update worker on the host.
    validator = root / 'validator'
    if not validator.exists():
        candidate = root / '.validator.next'
        shutil.copy2(args.worker, candidate)
        subprocess.run(['strip', str(candidate)], check=True)
        candidate.chmod(0o555)
        os.rename(candidate, validator)
        sync_directory(root)
    defaults = json.loads(subprocess.check_output([str(validator), '--defaults'], timeout=10))
    temporary = Path(tempfile.mkdtemp(prefix='.preparing-', dir=target.parent))
    try:
        shutil.copy2(args.worker, temporary / 'worker')
        # Strip the copied worker, never the shared Cargo build output.
        subprocess.run(['strip', str(temporary / 'worker')], check=True)
        models = args.models.read_text() if args.models else json.dumps(defaults['models'], indent=2) + '\n'
        instructions = args.instructions.read_text() if args.instructions else defaults['instructions']
        (temporary / 'models.json').write_text(models)
        (temporary / 'instructions.txt').write_text(instructions)
        manifest = {'protocol': 1, 'version': args.version,
                    'worker_sha256': digest(temporary / 'worker'),
                    'models_sha256': digest(temporary / 'models.json'),
                    'instructions_sha256': digest(temporary / 'instructions.txt'),
                    'classifier_model': args.classifier_model, 'classifier_effort': args.classifier_effort}
        (temporary / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        verify(temporary, validator)
        for name in ('worker', 'models.json', 'instructions.txt', 'manifest.json'):
            p = temporary / name
            p.chmod(0o555 if name == 'worker' else 0o444)
            with p.open('rb') as stream:
                os.fsync(stream.fileno())
        temporary.chmod(0o555)
        os.rename(temporary, target)
        sync_directory(target.parent)
        return verify(target, validator)
    except BaseException:
        if temporary.exists():
            temporary.chmod(0o755)
            shutil.rmtree(temporary)
        raise


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(root, version):
    root = storage(root)
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', version):
        raise ValueError('Invalid version')
    release = root / 'releases' / version
    result = verify(release, root / 'validator')
    # Same primitive is used for rollback to any existing verified version.
    temporary = root / ('.current-' + __import__('uuid').uuid4().hex)
    try:
        temporary.symlink_to(release)
        os.replace(temporary, root / 'current')
        sync_directory(root)
    finally:
        temporary.unlink(missing_ok=True)
    return result


def check_unit(unit, root, live):
    import shlex
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.service', unit):
        raise ValueError('Expected a plain service name')
    expected = str(root / 'current')
    values = subprocess.check_output(['systemctl', '--user', 'show', unit, '-p', 'Environment', '--value'], text=True)
    env = dict(item.split('=', 1) for item in shlex.split(values) if '=' in item)
    if env.get('VK_CODEX_ROUTING_MODULE') != expected:
        raise ValueError('Candidate is missing VK_CODEX_ROUTING_MODULE=' + expected)
    if live:
        pid = subprocess.check_output(['systemctl', '--user', 'show', unit, '-p', 'MainPID', '--value'], text=True).strip()
        env = dict(x.split('=', 1) for x in Path('/proc', pid, 'environ').read_text().split('\0') if '=' in x)
        if env.get('VK_CODEX_ROUTING_MODULE') != expected:
            raise ValueError('Running process did not adopt the module setting')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'publish', 'check', 'render'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--version')
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--models', type=Path)
    parser.add_argument('--instructions', type=Path)
    parser.add_argument('--classifier-model', default='gpt-5.6-luna')
    parser.add_argument('--classifier-effort', default='low')
    parser.add_argument('--unit')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = storage(args.root)
    if args.action == 'prepare':
        if not args.worker or not args.version:
            parser.error('prepare requires --worker and --version')
        result = prepare(args)
    elif args.action == 'publish':
        if not args.version:
            parser.error('publish requires --version')
        result = publish(root, args.version)
    else:
        result = verify(root / 'current', root / 'validator')
        if args.action == 'render':
            if not args.output:
                parser.error('render requires --output')
            output = storage(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            value = 'VK_CODEX_ROUTING_MODULE=' + str(root / 'current')
            if any(c in value for c in '\n\r\x00%'):
                raise ValueError('Invalid systemd path')
            output.write_text('[Service]\nEnvironment=' + json.dumps(value) + '\n')
        elif args.unit:
            check_unit(args.unit, root, args.live)
        elif args.live:
            parser.error('--live requires --unit')
    print(json.dumps({'passed': True, 'action': args.action, 'release': result,
                      'restarted': False, 'liveVerified': args.action == 'check' and args.live}))


if __name__ == '__main__':
    main()
