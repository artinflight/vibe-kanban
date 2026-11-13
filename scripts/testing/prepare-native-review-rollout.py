"""Read-only live-policy proposal. Emits field edits, never writes live settings.

No credentials, grants, permissions or service configuration are copied or changed.
Apply through the supported APIs only after exact-action authorization.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tomllib


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def prepare(native, profiles):
    edits = []
    def edit(path, previous, value):
        if previous != value:
            edits.append({'keyPath': path, 'before': previous, 'after': value})
    edit('approvals_reviewer', native.get('approvals_reviewer'), 'auto_review')
    edit('approval_policy', native.get('approval_policy'), 'on-request')
    sandbox = 'read-only' if native.get('sandbox_mode') == 'read-only' else 'workspace-write'
    edit('sandbox_mode', native.get('sandbox_mode'), sandbox)
    edit('features.guardian_approval', native.get('features', {}).get('guardian_approval'), True)
    edit('features.write_stdin_approval', native.get('features', {}).get('write_stdin_approval'), True)
    def segment(value):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
    apps = native.get('apps', {})
    defaults = apps.get('_default', {})
    edit('apps._default.approvals_reviewer', defaults.get('approvals_reviewer'), 'auto_review')
    for name, app in apps.items():
        if name == '_default': continue
        app_path = 'apps.' + segment(name)
        edit(app_path + '.approvals_reviewer', app.get('approvals_reviewer'), 'auto_review')
        for account, link in app.get('links', {}).items():
            edit(app_path + '.links.' + segment(account) + '.approvals_reviewer',
                 link.get('approvals_reviewer'), 'auto_review')
    variants = []
    for name, value in profiles.get('executors', {}).get('CODEX', {}).items():
        if not isinstance(value, dict) or not isinstance(value.get('CODEX'), dict): continue
        profile = value['CODEX']
        sandbox = 'read-only' if profile.get('sandbox') == 'read-only' or profile.get('plan') else 'workspace-write'
        changes = {}
        for key, after in [('sandbox', sandbox), ('ask_for_approval', 'on-request')]:
            if profile.get(key) != after: changes[key] = {'before': profile.get(key), 'after': after}
        # A reviewer-specific CLI argument can supersede native persisted config.
        for index, argument in enumerate(profile.get('additional_params') or []):
            normalized = argument.removeprefix('--config=')
            key, separator, before = normalized.partition('=')
            if separator and key.strip().endswith('approvals_reviewer'):
                after = key + '="auto_review"'
                if argument.startswith('--config='): after = '--config=' + after
                if argument != after:
                    changes['additional_params[' + str(index) + ']'] = {'before': argument, 'after': after}
        if changes: variants.append({'variant': name, 'changes': changes})
    return {'nativeEdits': edits, 'codexProfileEdits': variants,
            'otherExecutorFamilies': 'unchanged; no native Codex reviewer API',
            'nativeApprovalModesAndAppToolEnablement': 'preserved',
            'applicationPerformed': False, 'authorizationRequired': True,
            'activation': 'new processes and resumed sessions at natural boundaries; never interrupt active work',
            'rollback': 'restore only listed before values through supported APIs, preserving later unrelated changes'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-config', type=Path, required=True)
    parser.add_argument('--profiles', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if any(args.output.resolve().is_relative_to(path.resolve().parent) for path in [args.native_config, args.profiles]):
        raise ValueError('proposal output must be outside live configuration directories')
    native = tomllib.loads(args.native_config.read_text())
    profiles = json.loads(args.profiles.read_text())
    proposal = prepare(native, profiles)
    proposal['preconditions'] = {'nativeConfigSha256': digest(args.native_config), 'profilesSha256': digest(args.profiles)}
    args.output.write_text(json.dumps(proposal, indent=2) + '\n')
    args.output.chmod(0o600)
    print('Prepared', len(proposal['nativeEdits']), 'native setting edits and', len(proposal['codexProfileEdits']), 'profile edits; no live writes.')


if __name__ == '__main__': main()
