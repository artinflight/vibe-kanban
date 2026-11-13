#!/usr/bin/env python3
"""Pin the real scanner in a disposable builder; no repository data is published."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request

VERSION = '8.30.1'
ARCHIVE_SHA256 = '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb'


def prepare(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / 'gitleaks'
    if target.exists():
        raise ValueError('Use a fresh scanner output')
    url = f'https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/gitleaks_{VERSION}_linux_x64.tar.gz'
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = response.read(32 * 1024 * 1024 + 1)
    if len(payload) > 32 * 1024 * 1024 or hashlib.sha256(payload).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Scanner archive length/hash mismatch')
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
        members = [x for x in archive if x.name == 'gitleaks' and x.isfile()]
        if len(members) != 1:
            raise ValueError('Expected one regular scanner member')
        data = archive.extractfile(members[0]).read()
    with target.open('xb') as file:
        file.write(data)
    target.chmod(0o755)
    actual = subprocess.check_output([str(target), 'version'], text=True).strip()
    if actual != VERSION:
        raise ValueError('Scanner version mismatch')
    proof = {'version': VERSION, 'archive_sha256': ARCHIVE_SHA256,
             'binary_sha256': hashlib.sha256(data).hexdigest(),
             'binary_bytes': len(data), 'source_url': url}
    (root / 'scanner-source.json').write_text(json.dumps(proof, indent=2) + '\n')
    return target


if __name__ == '__main__':
    prepare(os.environ['VK_SCANNER_OUTPUT'])
