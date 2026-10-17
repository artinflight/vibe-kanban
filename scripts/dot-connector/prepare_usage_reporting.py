"""Prepare connector reporting against exact hashes, without live installation."""
import argparse
import hashlib
from pathlib import Path
import shutil
import uuid


def adapter(source):
    if 'import usage_reporting' in source:
        raise ValueError('Reporting already integrated; reconcile installed baseline')
    replacements = [
        ('import credit_budget\n', 'import credit_budget\nimport usage_reporting\n'),
        (' + credit_budget.TOOLS', ' + usage_reporting.TOOLS + credit_budget.TOOLS'),
        ('"serverInfo":{"name":"vibe-dot-connector","version":"1.5"}',
         '"serverInfo":{"name":"vibe-dot-connector","version":"1.6"}'),
        ('            if name == "get_credit_budget":',
         '            if name in {"get_usage_report", "get_usage_summary"}:\n'
         '                if not isinstance(params.get("arguments", {}), dict): raise ValueError("Arguments must be an object")\n'
         '                return {"jsonrpc":"2.0","id":msg["id"],"result":usage_reporting.call(sys.modules[__name__],name,args)}\n'
         '            if name == "get_credit_budget":'),
        ('No deletion/admin tools.',
         'get_usage_report and get_usage_summary read CU reporting only, with independent coverage and freshness; never infer credits from tokens. No deletion/admin tools.'),
    ]
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError('Adapter changed; reconcile exact reporting anchors')
        source = source.replace(before, after)
    compile(source, 'usage-adapter-candidate.py', 'exec')
    return source


def status(source, cu_workspace_id):
    scope = str(uuid.UUID(cu_workspace_id))
    if uuid.UUID(scope).int == 0:
        raise ValueError('Private non-nil CU scope required')
    before = '''def status(api, args, store=None):
    if set(args) != {"workspace_id"}:
        raise ValueError("Exactly one workspace_id required")
    wid = workspace_id(args["workspace_id"])
    result = (store or Store()).status(wid)
    if wid == SCOPE:
        import credit_budget
        result = dict(result, credit_budget=credit_budget.read_credit_budget())
    return result
'''.replace('SCOPE', repr(scope))
    after = before.replace('        import credit_budget\n',
                           '        import credit_budget\n        import usage_reporting\n')
    after = after.replace('credit_budget.read_credit_budget())',
                          'credit_budget.read_credit_budget(),\n'
                          '                      usage_report=usage_reporting.read_summary())')
    if source.count(before) != 1:
        raise ValueError('Existing CU status baseline changed; reconcile rather than overwrite')
    result = source.replace(before, after)
    compile(result, 'usage-status-candidate.py', 'exec')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--adapter-sha256', required=True)
    parser.add_argument('--status-sha256', required=True)
    parser.add_argument('--cu-workspace-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sources = {}
    for name, expected in [('adapter.py', args.adapter_sha256),
                           ('report_reconciliation.py', args.status_sha256)]:
        raw = (args.installed / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            parser.error('Installed source changed; coordinate with release owner')
        sources[name] = raw.decode()
    output = {'adapter.py': adapter(sources['adapter.py']),
              'report_reconciliation.py': status(sources['report_reconciliation.py'], args.cu_workspace_id)}
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in output.items():
        (args.output / name).write_text(value)
    shutil.copyfile(Path(__file__).with_name('usage_reporting.py'), args.output / 'usage_reporting.py')
    print('Prepared additive reporting source only; private binding omitted; no live changes.')


if __name__ == '__main__':
    main()
