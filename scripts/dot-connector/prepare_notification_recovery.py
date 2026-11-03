"""Exact-baseline preparation for the installed T66 notification-decoupling fix.

Writes a fresh candidate only. Never installs, calls an agent, or reads secrets.
The full reviewed replacement and minimal source diff are published alongside it.
"""
import argparse
import ast
import hashlib
from pathlib import Path

BASELINE = 'b1f5957c626e7a0159361343b1fbd0393765f707c06d5adbfddab10780fbb980'
CANDIDATE = 'b53fb4fb9f919a4799c16017c7fc9fd3c703e1850fbf7e66b7b9fa56535e9a4e'
CHANGED = {'Workflow.call','Workflow.finish','Runtime.chat_scope','Runtime.notifications'}


def preserved(source):
    tree=ast.parse(source)
    for node in tree.body:
        if isinstance(node,ast.ClassDef):
            node.body=[n for n in node.body if not (isinstance(n,ast.FunctionDef) and node.name+'.'+n.name in CHANGED)]
    suffix = ' Local authorised issue/chat scope is required; unavailable notifications do not block launch and delivery is reported separately.'
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.endswith(suffix):
            node.value = node.value[:-len(suffix)]
    return ast.dump(tree)


def prepare(source, output):
    raw=Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASELINE:
        raise ValueError('Installed workflow changed; reconcile before preparation')
    replacement=Path(__file__).with_name('templates').joinpath('issue_workflow.py').read_bytes()
    if hashlib.sha256(replacement).hexdigest()!=CANDIDATE:
        raise ValueError('Reviewed replacement changed')
    if preserved(raw.decode())!=preserved(replacement.decode()):
        raise ValueError('Unexpected edit outside notification separation')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'issue_workflow.py').write_bytes(replacement)
    return {'candidateSha256':CANDIDATE,'installed':False,'liveWrites':0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(prepare(a.source,a.output))
