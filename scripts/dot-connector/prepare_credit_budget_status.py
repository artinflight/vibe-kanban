"""Add a private CU-only budget readback to the existing reconciliation tool.

No new tool/schema, adapter, service setting, ledger or backend change. The
workspace binding is supplied only when preparing private installed source.
"""
import argparse
import hashlib
from pathlib import Path
import uuid

ORIGINAL = '''def status(api, args, store=None):
    if set(args) != {"workspace_id"}:
        raise ValueError("Exactly one workspace_id required")
    return (store or Store()).status(workspace_id(args["workspace_id"]))
'''


def patched(source, cu_workspace_id):
    scope = str(uuid.UUID(cu_workspace_id))
    if uuid.UUID(scope).int == 0:
        raise ValueError('A non-nil private CU workspace binding is required')
    if source.count(ORIGINAL) != 1:
        raise ValueError('Status baseline changed; reconcile rather than overwrite')
    replacement = '''def status(api, args, store=None):
    if set(args) != {"workspace_id"}:
        raise ValueError("Exactly one workspace_id required")
    wid = workspace_id(args["workspace_id"])
    result = (store or Store()).status(wid)
    if wid == SCOPE:
        import credit_budget
        result = dict(result, credit_budget=credit_budget.read_credit_budget())
    return result
'''.replace('SCOPE', repr(scope))
    candidate = source.replace(ORIGINAL, replacement)
    compile(candidate, 'budget-status-candidate.py', 'exec')
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reconciliation', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--cu-workspace-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.reconciliation.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.expected_sha256:
        parser.error('Installed baseline changed; coordinate with its owner')
    candidate = patched(raw.decode(), args.cu_workspace_id)
    args.output.mkdir(exist_ok=False, parents=True)
    (args.output / 'report_reconciliation.py').write_text(candidate)
    print('Prepared CU-only status overlay; private binding omitted from output; no live change.')


if __name__ == '__main__':
    main()
