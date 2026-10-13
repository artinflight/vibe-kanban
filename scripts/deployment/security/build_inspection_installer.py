"""Unprivileged local packager: immutable Git inputs and digest-pinned ELFs."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess

HEAD = '29af1c33e029bc1fe9ef9467fd51a03eb586105d'
PLAN = 'scripts/deployment/security/inspection-two-profile-install-plan.json'
PLAN_SHA = 'a17d7f29b4b47c25811e8bf3d992f09ecd5084812d666dc761fbf4afff8a5357'


def git_bytes(path):
    return subprocess.check_output(['git', 'show', HEAD + ':' + path])


def build(template, binaries):
    raw = git_bytes(PLAN)
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA:
        raise ValueError('reviewed plan mismatch')
    plan = json.loads(raw)
    sources = {path: git_bytes(path) for path in plan['code_artifact_sha256']}
    for path, expected in plan['code_artifact_sha256'].items():
        if hashlib.sha256(sources[path]).hexdigest() != expected:
            raise ValueError('source mismatch')
    compiled = {}
    for entry, file in zip(plan['files'][:2], binaries):
        data = Path(file).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('launcher mismatch')
        compiled[entry['destination']] = data
    encode = lambda value: base64.b64encode(value).decode('ascii')
    payload = {'plan': encode(raw), 'sources': {p: encode(v) for p, v in sources.items()},
               'binaries': {p: encode(v) for p, v in compiled.items()}}
    marker = 'PAYLOAD = None  # builder injects data, not executable imports'
    if template.count(marker) != 1:
        raise ValueError('template marker mismatch')
    return template.replace(marker, 'PAYLOAD = ' + repr(payload)).encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--managed-binary', required=True)
    parser.add_argument('--historical-binary', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('build as unprivileged actor, never root')
    if not os.path.ismount('/mnt/vk-storage'):
        raise SystemExit('mounted SSD required')
    out = Path(args.output)
    if not out.resolve().is_relative_to('/mnt/vk-storage'):
        raise SystemExit('output must remain on mounted SSD')
    template = Path(__file__).with_name('vk_inspection_installer.py').read_text()
    data = build(template, [args.managed_binary, args.historical_binary])
    with out.open('xb') as stream:
        stream.write(data)
    print(json.dumps({'path': str(out), 'sha256': hashlib.sha256(data).hexdigest(),
                      'reviewed_plan_head': HEAD, 'bytes': len(data), 'root_execution': False}))


if __name__ == '__main__':
    main()
