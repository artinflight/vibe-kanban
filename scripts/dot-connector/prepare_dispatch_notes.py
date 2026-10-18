"""Prepare exact-baseline note hooks; never install, activate or dispatch work."""
import argparse
import ast
import hashlib
from pathlib import Path
import shutil


def pinned(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected: raise ValueError('Runtime baseline changed; reconcile before preparing')
    return data.decode()


def replace_once(text, old, new):
    if text.count(old) != 1: raise ValueError('Dispatch integration anchor changed')
    return text.replace(old, new)


def adapter_patch(source):
    source = replace_once(source,
        '            if name == "run_session_prompt": return {"jsonrpc":"2.0","id":msg["id"],"result":local_followup(args)}',
        '            if name == "run_session_prompt":\n'
        '                from dispatch_notes import observe\n'
        '                return {"jsonrpc":"2.0","id":msg["id"],"result":observe(name,args,local_followup(args))}')
    source = replace_once(source,
        '                return {"jsonrpc":"2.0","id":msg["id"],"result":dispatch_start(local_start,args)}',
        '                from dispatch_notes import observe\n'
        '                return {"jsonrpc":"2.0","id":msg["id"],"result":observe(name,args,dispatch_start(local_start,args))}')
    return source


def status_patch(source):
    if 'dispatch_notes.workspace_status' in source: raise ValueError('Dispatch status already integrated')
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'status')
    lines = source.splitlines(keepends=True)
    original = ''.join(lines[node.lineno-1:node.end_lineno])
    changed = replace_once(original, '    return result', '''    try:
        import dispatch_notes
        result = dict(result, dispatch_notes=dispatch_notes.workspace_status(wid))
    except Exception:
        result = dict(result, dispatch_notes={"status": "unavailable", "receipts": []})
    return result''')
    lines[node.lineno-1:node.end_lineno] = [changed]
    return ''.join(lines)


def worker_patch(source):
    if 'from dispatch_notes import recover_pending' in source: raise ValueError('Dispatch recovery already integrated')
    return replace_once(source, '                    next_scan=time.monotonic()+5', '''                    try:
                        from dispatch_notes import recover_pending
                        recover_pending()
                    except Exception:
                        print('dispatch_note_recovery_unavailable; receipts retained',file=sys.stderr,flush=True)
                    next_scan=time.monotonic()+5''')


def assert_ast_preserved(before, after, changed):
    def nodes(source):
        tree = ast.parse(source)
        for n in tree.body:
            if isinstance(n, ast.ClassDef):
                n.body = [m for m in n.body if not (isinstance(m, ast.FunctionDef) and n.name+'.'+m.name in changed)]
        return [ast.dump(n) for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name in changed)]
    if nodes(before) != nodes(after): raise ValueError('Unexpected source edit outside scoped hooks')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('adapter','status','worker'):
        p.add_argument('--'+name, type=Path, required=True)
        p.add_argument('--'+name+'-sha', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    sources = [(a.adapter, a.adapter_sha, adapter_patch, {'Adapter.handle'}, 'adapter.py'),
               (a.status, a.status_sha, status_patch, {'status'}, 'report_reconciliation.py'),
               (a.worker, a.worker_sha, worker_patch, {'main'}, 'worker.py')]
    prepared = {}
    for path, digest, patch, changed, name in sources:
        original = pinned(path,digest); result = patch(original)
        assert_ast_preserved(original,result,changed); prepared[name] = result
    a.output.mkdir(parents=True, exist_ok=False)
    for name, text in prepared.items(): (a.output/name).write_text(text)
    shutil.copy2(Path(__file__).with_name('dispatch_notes.py'), a.output/'dispatch_notes.py')
    print('Scoped candidate prepared; no live changes or agent dispatch')
