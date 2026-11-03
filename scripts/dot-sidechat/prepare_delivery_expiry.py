"""Prepare a complete source candidate for non-expiring Dot delivery; never install.

Zero means no automatic delivery deadline. Explicit unsubscribe/revocation,
verified callback identity, scope, overlap and owner checks stay authoritative.
Browser authentication, signing-key rotation and outbox leases are not changed.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil

def replace_method(source, cls, name, transform):
    parent = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == cls)
    node = next(n for n in parent.body if isinstance(n, ast.FunctionDef) and n.name == name)
    lines = source.splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = [transform(''.join(lines[node.lineno - 1:node.end_lineno]))]
    return ''.join(lines)


def replace(source, old, new, count=1):
    if source.count(old) != count:
        raise ValueError('Delivery source changed; review exact owner baseline')
    return source.replace(old, new)


def patched_store(source):
    def bind(body):
        body = replace(body, 'ttl=3600', 'ttl=0')
        body = replace(body, 'not 60 <= ttl <= 86400', 'not (ttl == 0 or 60 <= ttl <= 86400)')
        return replace(body, 'self.clock() + ttl', '0 if ttl == 0 else self.clock() + ttl')
    result = replace_method(source, 'Store', 'bind', bind)
    return replace_method(result, 'Store', 'claim', lambda body:
                          replace(body, 'b.active=1 AND b.expires>?',
                                  'b.active=1 AND (b.expires=0 OR b.expires>?)'))


def patched_events(source):
    source = replace(source, 'params.get("ttlMs", 86400000)', 'params.get("ttlMs", 0)')
    source = replace(source, 'not 60000 <= ttl <= 604800000', 'not (ttl == 0 or 60000 <= ttl <= 604800000)')
    source = replace(source, 'Finite subscription lifetime of 1 minute to 7 days required',
                     'Legacy ttlMs must be zero or 1 minute to 7 days; delivery remains active until revoked')
    source = replace(source, 'expires=self.clock()+ttl/1000',
                     'expires=0  # Legacy ttlMs is accepted for compatibility, never a delivery deadline.')
    source = replace(source, '        # Renew before the actual deadline; do not extend finite authority.\n        renew_before = expires - min(3600, ttl / 1000 / 5)\n', '')
    source = replace(source, '__import__("datetime").datetime.fromtimestamp(renew_before,__import__("datetime").timezone.utc).isoformat()', 'None')
    source = replace(source, 'active=1 AND expires>?', 'active=1 AND (expires=0 OR expires>?)', count=2)
    return replace(source, 'ttl=max(60,min(86400,int(sub["expires"]-self.clock())))',
                   'ttl=0 if sub["expires"] == 0 else max(60,min(86400,int(sub["expires"]-self.clock())))')


def patched_scope(source):
    source = replace(source, 'active=1 AND expires>?', 'active=1 AND (expires=0 OR expires>?)')
    return replace(source, "ttl=max(60, min(86400, int(selected['expires'] - store.clock())))",
                   "ttl=0 if selected['expires'] == 0 else max(60, min(86400, int(selected['expires'] - store.clock())))")


def patched_rollout(source):
    return replace(source, 'active=1 AND expires>?', 'active=1 AND (expires=0 OR expires>?)')


def patched_health(source):
    source = replace(source, "r['active'] and r['expires'] > now", "r['active'] and (r['expires'] == 0 or r['expires'] > now)")
    source = replace(source, "expires_at=iso(row['expires']), renewal_due=row['expires'] - now <= 3600,",
                     "expires_at=None if row['expires'] == 0 else iso(row['expires']),\n                    lifetime='until_revoked' if row['expires'] == 0 else 'finite',\n                    renewal_due=row['expires'] != 0 and row['expires'] - now <= 3600,")
    source = replace(source, "next_step='The platform must renew this existing registration before expiry; status reads never renew it.'",
                     "next_step=('No renewal required; explicit unsubscribe/revocation remains authoritative.' if row['expires'] == 0 else\n                               'The platform must renew this existing registration before expiry; status reads never renew it.')")
    return replace(source, "r['active'] and r['expires'] <= now", "r['active'] and r['expires'] != 0 and r['expires'] <= now")


PATCHES = {'sidechat.py': patched_store, 'events.py': patched_events,
           'scope_migration.py': patched_scope, 'scope_rollout.py': patched_rollout,
           'delivery_health.py': patched_health}


def prepare(source, expected, output):
    source, output = Path(source).resolve(strict=True), Path(output)
    if set(expected) != set(PATCHES):
        raise ValueError('Exact five-module baseline required')
    raw = {name: (source / name).read_bytes() for name in PATCHES}
    actual = {name: hashlib.sha256(value).hexdigest() for name, value in raw.items()}
    if actual != expected:
        raise ValueError('Installed source changed; reconcile before preparation')
    patched = {name: patch(raw[name].decode()) for name, patch in PATCHES.items()}
    for value in patched.values():
        ast.parse(value)
    output.mkdir(parents=True, exist_ok=False)
    for path in source.iterdir():
        if path.is_file() and path.suffix in ('.py', '.json'):
            shutil.copyfile(path, output / path.name)
    for name, value in patched.items():
        (output / name).write_text(value)
    package_baseline = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
                        if p.is_file() and p.suffix in ('.py', '.json')}
    package_candidate = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                         for name in package_baseline}
    return {'baseline_sha256': actual, 'package_baseline_sha256': package_baseline,
            'package_candidate_sha256': package_candidate,
            'candidate_sha256': {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in PATCHES},
            'changed_modules': sorted(PATCHES), 'schema_changes': 0,
            'live_files_modified': 0, 'subscriptions_modified': 0,
            'installed': False, 'requires_action_time_confirmation': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, json.loads(args.baseline.read_text()), args.output)))


if __name__ == '__main__':
    main()
