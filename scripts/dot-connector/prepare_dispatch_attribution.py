"""Exact-pin, additive caller-attribution candidate; never install or reload."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
from prepare_dispatch_notes import pinned, replace_once, assert_ast_preserved


READ_ANCHOR = "                message['dispatch_note']={'workspace_id':dispatch_workspace,'execution_id':dispatch_execution}\n"
READ_HOOK = "                from dispatch_attribution import presentation\n" \
            "                message['dispatch_note'].update(presentation(self, principal, message))\n"


def adapter_patch(source):
    old = 'from dispatch_notes import observe\n'
    if source.count(old) != 2:
        raise ValueError('Installed hooks changed; reconcile before preparation')
    changed = source.replace(old, 'from dispatch_notes import observe, current_caller\n')
    for call in ('local_followup(args)', 'dispatch_start(local_start,args)'):
        changed = replace_once(changed, 'observe(name,args,'+call+')',
                               'observe(name,args,'+call+',caller=current_caller())')
    # Prove the complete old AST survives after removing only these additions.
    tree = ast.parse(changed)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'dispatch_notes':
            node.names = [n for n in node.names if n.name != 'current_caller']
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'observe':
            node.keywords = [k for k in node.keywords if k.arg != 'caller']
    if ast.dump(ast.parse(source)) != ast.dump(tree):
        raise ValueError('Unexpected adapter modification')
    return changed


def store_patch(source):
    if READ_HOOK in source:
        raise ValueError('Presentation already integrated; reconcile')
    result = replace_once(source, READ_ANCHOR, READ_ANCHOR+READ_HOOK)
    assert_ast_preserved(source, result, {'Store.read'})
    if result.replace(READ_HOOK, '', 1) != source:
        raise ValueError('Unexpected shared Store modification')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('adapter', 'store'):
        p.add_argument('--'+name, type=Path, required=True)
        p.add_argument('--'+name+'-sha', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    adapter = adapter_patch(pinned(a.adapter, a.adapter_sha))
    store = store_patch(pinned(a.store, a.store_sha))
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output/'adapter.py').write_text(adapter)
    (a.output/'sidechat.py').write_text(store)
    shutil.copy2(Path(__file__).with_name('dispatch_notes.py'), a.output/'dispatch_notes.py')
    shutil.copy2(Path(__file__).resolve().parents[1]/'dot-sidechat/dispatch_attribution.py', a.output/'dispatch_attribution.py')
    print(json.dumps({'prepared': True, 'installed': False, 'liveWrites': 0,
        'candidateHashes': {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in a.output.iterdir()}}))
