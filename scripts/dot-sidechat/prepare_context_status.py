"""Exact-baseline additive status/shim preparation; no installation or restart."""
import ast
import hashlib
from pathlib import Path


def prepare(source, expected_sha256):
    if hashlib.sha256(source).hexdigest() != expected_sha256:
        raise ValueError('Status baseline changed; reconcile before preparing')
    tree = ast.parse(source)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'status']
    if len(nodes) != 1:
        raise ValueError('Expected one status function')
    node = nodes[0]
    lines = source.decode().splitlines(keepends=True)
    original = ''.join(lines[node.lineno-1:node.end_lineno])
    if original.count('    return result') != 1 or 'sidechat_context' in original:
        raise ValueError('Status return anchor changed')
    replacement = original.replace('    return result', '''    # Additive private history lookup. Original delivery/CU readbacks retain their meaning.
    try:
        import sidechat_connector
        sidechat_context = sidechat_connector.workspace_context(wid)
    except Exception:
        sidechat_context = {"status": "unavailable", "workspace_id": wid}
    result = dict(result, sidechat=sidechat_context)
    return result''')
    lines[node.lineno-1:node.end_lineno] = [replacement]
    candidate = ''.join(lines).encode()
    before = [ast.dump(n) for n in tree.body if n is not node]
    after = [ast.dump(n) for n in ast.parse(candidate).body
             if not (isinstance(n, ast.FunctionDef) and n.name == 'status')]
    if before != after:
        raise ValueError('Unexpected change outside status')
    return candidate


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_bytes(prepare(Path(args.source).read_bytes(), args.sha256))
