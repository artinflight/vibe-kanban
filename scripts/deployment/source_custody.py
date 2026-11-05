"""Verify published source custody, or reconstruct inert incident sources.

No command is executed, no source is installed, and no private binding is
printed. Reconstruction verifies every original hash before creating output.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def verified_files(root, catalog):
    root = Path(root).resolve()
    files = []
    for item in catalog['files']:
        relative = item.get('path', item.get('template'))
        if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Literal relative source path required')
        path = (root / relative).resolve()
        if path == root or not path.is_relative_to(root):
            raise ValueError('Source path escapes catalog root')
        raw = path.read_bytes()
        expected = item.get('public_sha256', item.get('template_sha256'))
        if sha256(raw) != expected:
            raise ValueError('Published source hash mismatch: ' + relative)
        files.append((relative, raw, item))
    if not files or len({row[0] for row in files}) != len(files):
        raise ValueError('Empty or duplicate source inventory')
    return files


def restored_files(files, bindings):
    if not isinstance(bindings, dict) or not all(
        isinstance(key, str) and re.fullmatch(r'(INCIDENT_UUID|PRIVATE_BINDING)_[0-9A-F]{16}', key)
        and isinstance(value, str) and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value)
        for key, value in bindings.items()
    ):
        raise ValueError('Invalid private binding map')
    result = []
    for relative, raw, item in files:
        for key, value in bindings.items():
            raw = raw.replace(key.encode(), value.encode())
        expected = item.get('original_sha256', item.get('deployed_sha256'))
        if sha256(raw) != expected:
            raise ValueError('Original source could not be reconstructed: ' + relative)
        result.append((relative, raw))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--catalog', required=True, type=Path)
    parser.add_argument('--bindings', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    files = verified_files(args.root, json.loads(args.catalog.read_text()))
    if args.output:
        ssd = Path('/mnt/vk-storage')
        output = args.output.resolve()
        if not os.path.ismount(ssd) or not output.is_relative_to(ssd) or output.exists():
            raise ValueError('Fresh directory on mounted /mnt/vk-storage required')
        bindings = json.loads(args.bindings.read_text()) if args.bindings else {}
        restored = restored_files(files, bindings)
        output.mkdir(mode=0o700)
        for relative, raw in restored:
            # Keep .txt suffixes inert. Never make reconstructed files executable.
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
                stream.write(raw)
    elif args.bindings:
        restored_files(files, json.loads(args.bindings.read_text()))
    print(json.dumps(dict(verified_sources=len(files), original_hashes_verified=bool(args.bindings or args.output),
                         reconstructed=bool(args.output), installed=False)))


if __name__ == '__main__':
    main()
