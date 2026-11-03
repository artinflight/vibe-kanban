"""Prepare the installed connector health hook against a fresh exact source pin.

No install/reload, state changes, subscription credentials or arbitrary HTTP.
"""
import argparse
import ast
import hashlib
from pathlib import Path
import shutil

ANCHOR = '        return store.workspace_context(principal, workspace)'
HOOK = '''        context = store.workspace_context(principal, workspace)
        if context.get('status') == 'available':
            try:
                from delivery_health import registration_health
                context = dict(context, delivery_registration=registration_health(store, principal, context))
            except Exception:
                context = dict(context, delivery_registration={'status': 'unavailable', 'agent_prompt_dependency': False})
        return context'''


def patch(source):
    if source.count(ANCHOR) != 1:
        raise ValueError('Shared connector changed; reconcile before adoption')
    result=source.replace(ANCHOR,HOOK)
    def unchanged(text):
        tree=ast.parse(text)
        tree.body=[n for n in tree.body if not (isinstance(n,ast.FunctionDef) and n.name=='workspace_context')]
        return ast.dump(tree)
    if unchanged(source)!=unchanged(result):raise ValueError('Unexpected connector modification')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--connector',type=Path,required=True);p.add_argument('--sha256',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raw=a.connector.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=a.sha256:raise SystemExit('Live connector baseline changed')
    result=patch(raw.decode());a.output.mkdir(exist_ok=False,parents=True)
    (a.output/'connector.py').write_text(result)
    for name in ('events.py','delivery_health.py'):
        shutil.copy2(Path(__file__).with_name(name),a.output/name)
    print('Exact connector/events/health candidate prepared; no live files or states changed')
