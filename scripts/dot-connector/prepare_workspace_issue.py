"""Prepare an exact-baseline start preflight; never installs or restarts anything."""
import ast
import hashlib
from pathlib import Path


def prepare(source, expected_sha256):
    if hashlib.sha256(source).hexdigest() != expected_sha256:
        raise ValueError('Connector baseline changed; reconcile the live owner first')
    text = source.decode()
    anchors = [
        ('    if set(args)-allowed: raise ValueError("Unknown workspace argument")',
         '    if set(args)-allowed: raise ValueError("Unknown workspace argument")\n'
         '    from workspace_issue_context import require_issue_context\n'
         '    require_issue_context(args, http_get)'),
        ('schema["required"]=list(set(schema.get("required",[])+["prompt"]))',
         'schema["required"]=list(set(schema.get("required",[])+["prompt","project_id","issue_id"]))'),
        ('When linking issue_id, project_id is required.',
         'Both project_id and issue_id are required and verified before starting. Create/select the issue in Vibe first so Dot Chat is available.'),
    ]
    for old, new in anchors:
        if text.count(old) != 1:
            raise ValueError('Connector start/schema anchor changed')
        text = text.replace(old, new)
    before, after = ast.parse(source), ast.parse(text)
    def unchanged(tree):
        nodes = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == 'local_start':
                continue
            if isinstance(node, ast.ClassDef) and node.name == 'Adapter':
                node.body = [n for n in node.body if not (isinstance(n, ast.FunctionDef) and n.name == 'handle')]
            nodes.append(ast.dump(node))
        return nodes
    if unchanged(before) != unchanged(after):
        raise ValueError('Unexpected edit outside workspace start/discovery')
    return text.encode()


if __name__ == '__main__':
    import argparse
    import shutil
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    candidate = prepare(args.adapter.read_bytes(), args.sha256)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'adapter.py').write_bytes(candidate)
    shutil.copyfile(Path(__file__).with_name('workspace_issue_context.py'), args.output/'workspace_issue_context.py')
    print('Prepared issue-context guard only; no live changes')
