"""Create fresh paired frontends retaining hashed assets for both open-tab versions.

Never modifies either input. Same-name assets must be byte-identical; ambiguous
collisions fail closed. The caller verifies release provenance before calling.
"""
import hashlib
import os
from pathlib import Path
import shutil


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def compose(candidate, fallback, output):
    candidate, fallback, output = map(Path, (candidate, fallback, output))
    if output.exists():
        raise ValueError('Fresh frontend package required')
    for root in (candidate, fallback):
        if not (root / 'index.html').is_file() or not (root / 'assets').is_dir():
            raise ValueError('Complete frontend required')
        if any(path.is_symlink() for path in root.rglob('*')):
            raise ValueError('Frontend links are not admitted')
    merged = {}
    for root in (candidate, fallback):
        for path in (root / 'assets').rglob('*'):
            if path.is_file():
                relative = path.relative_to(root)
                value = digest(path)
                if relative in merged and merged[relative][1] != value:
                    raise ValueError('Conflicting asset pathname: '+str(relative))
                merged[relative] = (path, value)
    output.mkdir(mode=0o700)
    receipt = dict(schema=1, roots={}, retained_asset_count=len(merged))
    for variant, root in [('candidate', candidate), ('fallback', fallback)]:
        target = output / variant
        shutil.copytree(root, target)
        for relative, (path, expected) in merged.items():
            destination = target / relative
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(path, destination)
                except OSError:
                    shutil.copy2(path, destination)
            if digest(destination) != expected:
                raise ValueError('Copied asset failed verification')
        if digest(target / 'index.html') != digest(root / 'index.html'):
            raise ValueError('Frontend entrypoint changed')
        receipt['roots'][variant] = dict(path=str(target), source=str(root),
                                        index_sha256=digest(target / 'index.html'))
    return receipt
