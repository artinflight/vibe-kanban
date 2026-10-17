"""Prepare an additive budget-reader overlay against a pinned adapter; never install."""
import argparse
import hashlib
from pathlib import Path
import shutil


def patched(source):
    if 'import credit_budget' in source:
        raise ValueError('Budget reader already integrated; reconcile the owner baseline')
    replacements = [
        ('"serverInfo":{"name":"vibe-dot-connector","version":"1.4"}',
         '"serverInfo":{"name":"vibe-dot-connector","version":"1.5"}'),
        ('import stop_control\n', 'import stop_control\nimport credit_budget\n'),
        (' + stop_control.TOOLS', ' + credit_budget.TOOLS + stop_control.TOOLS'),
        ('            if name in stop_control.HANDLERS:',
         '            if name == "get_credit_budget":\n'
         '                if not isinstance(params.get("arguments", {}), dict): raise ValueError("Arguments must be an object")\n'
         '                return {"jsonrpc":"2.0","id":msg["id"],"result":credit_budget.call(sys.modules[__name__],args)}\n'
         '            if name in stop_control.HANDLERS:'),
        ('No deletion/admin tools.',
         'get_credit_budget reads observational CU account-wide data only; stale or unknown evidence grants no launch permission and no stop enforcement. No deletion/admin tools.'),
    ]
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError('Adapter changed; reconcile exact budget-reader anchors')
        source = source.replace(before, after)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.adapter.read_bytes()
    if hashlib.sha256(source).hexdigest() != args.expected_sha256:
        parser.error('Adapter baseline changed; coordinate before overwriting anything')
    candidate = patched(source.decode())
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'adapter.py').write_text(candidate)
    shutil.copyfile(Path(__file__).with_name('credit_budget.py'), args.output / 'credit_budget.py')
    print('Prepared budget overlay only; no live source, service or private state changed.')


if __name__ == '__main__':
    main()
