"""Prepare three additive files against exact runtime pins. Never install/reload."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(bundle, connector_sha, contracts_sha, store_sha, output):
    expected = {'connector.py': connector_sha, 'contracts.json': contracts_sha, 'sidechat.py': store_sha}
    inputs = {name: (bundle/name).read_bytes() for name in expected}
    if any(hashlib.sha256(inputs[name]).hexdigest() != digest for name, digest in expected.items()):
        raise ValueError('Shared runtime changed; reconcile the fresh baseline')
    source = inputs['connector.py'].decode()
    anchor = 'def call(name,args):\n'
    if source.count(anchor) != 1 or 'notification_call' in source:
        raise ValueError('Connector hook changed or already present')
    hook = "    if name in ('list_workspace_dot_notifications', 'acknowledge_dot_dispatch_notes'):\n" \
           "        from notification_ack import call as notification_call\n" \
           "        return notification_call(ROOT/'threads.sqlite', Principal(owner(), 'dot'), name, args)\n"
    candidate = source.replace(anchor, anchor+hook)
    # Keep every old AST node, including the complete original call body.
    before, after = ast.parse(source), ast.parse(candidate)
    node = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == 'call')
    node.body = node.body[1:]
    if ast.dump(before) != ast.dump(after):
        raise ValueError('Unexpected connector edit')
    contracts = json.loads(inputs['contracts.json'])
    new = json.loads(Path(__file__).with_name('contracts.json').read_text())
    names = {'list_workspace_dot_notifications', 'acknowledge_dot_dispatch_notes'}
    if names & {t['name'] for t in contracts['tools']}:
        raise ValueError('Tools already registered; reconcile rather than duplicate')
    additions = [t for t in new['tools'] if t['name'] in names]
    if {t['name'] for t in additions} != names:
        raise ValueError('New tool definitions unavailable')
    contracts['tools'].extend(additions)
    output.mkdir(parents=True, exist_ok=False)
    (output/'connector.py').write_text(candidate)
    (output/'contracts.json').write_text(json.dumps(contracts, indent=2)+'\n')
    shutil.copy2(Path(__file__).with_name('notification_ack.py'), output/'notification_ack.py')
    return {'baseline': expected, 'candidate': {n: sha(output/n) for n in
            ('connector.py', 'contracts.json', 'notification_ack.py')},
            'existingStoreUnchanged': True, 'allOriginalToolAndEventDefinitionsPreserved': True,
            'installed': False, 'reloads': 0, 'liveWrites': 0}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    for name in ('connector', 'contracts', 'store'):
        p.add_argument('--'+name+'-sha', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.bundle, a.connector_sha, a.contracts_sha, a.store_sha, a.output)))
