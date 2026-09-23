#!/usr/bin/env python3
"""Versioned MCP deployment settings; never restart services or enable goals.

render: prepare a candidate's two drop-ins without changing services.
install: atomically install both drop-ins and daemon-reload, never restart.
check: verify effective next-start settings for the nominated candidate.
live-check: additionally verify process environments, routed backend and CU.
lock-check: configuration check plus actual controller lock availability.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import urllib.request

PROFILE = Path(__file__).parent / 'deployment/mcp-capacity.json'

def unit_name(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.service', value):
        raise ValueError('Expected a plain systemd service name')
    return value

def absolute(value):
    p = Path(value)
    if not p.is_absolute() or any(c in str(p) for c in '\n\r\x00%'):
        raise ValueError('Expected an absolute path without systemd expansion')
    return p

def plan(profile, unit, server):
    if profile.get('version') != 1:
        raise ValueError('Unsupported capacity deployment profile')
    unit_name(unit)
    cu = unit_name(profile['cuUnit'])
    if cu == unit:
        raise ValueError('CU and VK must be different services')
    server = absolute(server)
    guard = server.parent / 'vk-capacity-guard'
    for key in ('stateDir', 'tokenFile', 'codexHome', 'database', 'gatewayRoute'):
        absolute(profile[key])
    roots = profile['buildRoots']
    if not isinstance(roots, list) or not 1 <= len(roots) <= 8:
        raise ValueError('Specify one to eight approved build directories')
    for root in roots:
        absolute(root)
    if profile['gatewayOrigin'] != 'http://127.0.0.1:4720' or profile['modelProvider'] != 'openai':
        raise ValueError('MCP production requires the stable gateway and OpenAI provider')
    vk_env = {
        'CODEX_HOME': profile['codexHome'],
        'VK_USE_SYSTEMD_RUN': '1',
        'VK_CAPACITY_STATE_DIR': profile['stateDir'],
        'VK_CAPACITY_GUARD': str(guard),
        'VK_CAPACITY_TOKEN_FILE': profile['tokenFile'],
        'VK_CAPACITY_MODEL_PROVIDER': profile['modelProvider'],
        'VK_CAPACITY_BUILD_ROOTS': json.dumps(roots, separators=(',', ':')),
    }
    cu_env = {
        'CU_VK_ORIGIN': profile['gatewayOrigin'],
        'CU_VK_TOKEN_FILE': profile['tokenFile'],
        'CU_CODEX_HOME': profile['codexHome'],
        'CU_VK_DATABASE': profile['database'],
    }
    def text(dependencies, env):
        # Entire KEY=VALUE is quoted; JSON quotes/backslashes survive systemd.
        return '[Unit]\n' + dependencies + '\n[Service]\n' + ''.join(
            'Environment=' + json.dumps(k + '=' + v) + '\n' for k, v in env.items())
    return {
        unit: {'environment': vk_env, 'text': text('Wants=' + cu + '\n', vk_env)},
        cu: {'environment': cu_env, 'text': text('PartOf=' + unit + '\nAfter=' + unit + '\n', cu_env)},
    }

def prerequisites(profile, server):
    for path in (Path(server), Path(server).parent / 'vk-capacity-guard'):
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError('Missing executable deployment artifact: ' + str(path))
    token = Path(profile['tokenFile'])
    if token.stat().st_uid != os.getuid() or token.stat().st_mode & 0o077 or len(token.read_text().strip()) < 32:
        raise ValueError('Capacity token must be existing, private and owned by the service user')
    protected = [Path(profile[k]).resolve() for k in ('stateDir', 'codexHome')]
    protected += [(Path(server).parent / 'vk-capacity-guard').resolve(), token.resolve()]
    for root in profile['buildRoots']:
        p = Path(root).resolve()
        if not p.is_dir() or any(p == x or p in x.parents or x in p.parents for x in protected):
            raise ValueError('Missing or unsafe build directory: ' + root)
    for key in ('stateDir', 'codexHome'):
        if not Path(profile[key]).is_dir():
            raise ValueError('Missing ' + key)
    if not os.access(profile['stateDir'], os.W_OK) or not Path(profile['database']).is_file():
        raise ValueError('Controller must be writable and VK database must exist')

def prop(unit, key):
    return subprocess.check_output(['systemctl', '--user', 'show', unit, '-p', key, '--value'], text=True).strip()

def environment(unit):
    return dict(item.split('=', 1) for item in shlex.split(prop(unit, 'Environment')))

def compare(expected, actual):
    for key, value in expected.items():
        found = actual.get(key)
        if key == 'VK_CAPACITY_BUILD_ROOTS':
            try:
                if json.loads(found) == json.loads(value):
                    continue
            except (TypeError, ValueError):
                pass
        if found != value:
            raise ValueError('Missing or mismatched setting: ' + key)

def check(profile, unit, server, planned, live=False):
    for name, spec in planned.items():
        if prop(name, 'LoadState') != 'loaded':
            raise ValueError('Service is not loaded: ' + name)
        compare(spec['environment'], environment(name))
        if live:
            pid = prop(name, 'MainPID')
            if pid == '0' or prop(name, 'FreezerState') == 'frozen':
                raise ValueError('Service is not running: ' + name)
            running = dict(x.split('=', 1) for x in Path('/proc', pid, 'environ').read_text().split('\0') if '=' in x)
            compare(spec['environment'], running)
    cu = profile['cuUnit']
    if cu not in prop(unit, 'Wants').split() or any(unit not in prop(cu, k).split() for k in ('PartOf', 'After')):
        raise ValueError('Missing coordinated VK/CU service dependency')
    # Verify the candidate command as well as environment; a guard from another
    # release must not satisfy readiness for this server.
    if 'path=' + str(Path(server)) + ' ;' not in prop(unit, 'ExecStart'):
        raise ValueError('Service ExecStart does not match the nominated server')
    if live:
        if Path('/proc', prop(unit, 'MainPID'), 'exe').resolve() != Path(server).resolve():
            raise ValueError('Running backend differs from nominated server')
        route = json.loads(Path(profile['gatewayRoute']).read_text())
        if route.get('port') != int(environment(unit)['BACKEND_PORT']):
            raise ValueError('Gateway does not route to the nominated backend')
        req = urllib.request.Request('http://127.0.0.1:4177/api/capacity/control', headers={'Tailscale-User-Login': 'seamus@artinflight.ca'})
        with urllib.request.urlopen(req, timeout=10) as response:
            state = json.load(response)
        if not state['connected'] or not state['capacity']['background']['reconciled']:
            raise ValueError('CU has not connected and reconciled with VK')

def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.next')
    with open(temporary, 'w') as stream:
        os.chmod(temporary, 0o600)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def install(profile, unit, server, planned, root):
    # Check service identity before overwriting any configuration. An operator
    # must create the nominated candidate unit as part of normal deployment.
    for name in planned:
        if prop(name, 'LoadState') != 'loaded':
            raise ValueError('Service is not loaded: ' + name)
    if 'path=' + str(server) + ' ;' not in prop(unit, 'ExecStart'):
        raise ValueError('Service ExecStart does not match the nominated server')
    before = {u: prop(u, 'MainPID') for u in planned}
    previous = {}
    try:
        for name, item in planned.items():
            path = root / (name + '.d/capacity.conf')
            previous[path] = path.read_text() if path.exists() else None
            atomic(path, item['text'])
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
        check(profile, unit, server, planned)
        if before != {u: prop(u, 'MainPID') for u in planned}:
            raise ValueError('A service changed process during configuration installation')
    except Exception:
        # Restore both previous drop-ins on a failed installation. No service
        # start/stop/restart is performed, including on this recovery path.
        for path, text in previous.items():
            if text is None:
                path.unlink(missing_ok=True)
            else:
                atomic(path, text)
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['render', 'install', 'check', 'live-check', 'lock-check'])
    p.add_argument('--profile', type=Path, default=PROFILE)
    p.add_argument('--unit', required=True)
    p.add_argument('--server', required=True, type=Path)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    profile = json.loads(args.profile.read_text())
    planned = plan(profile, args.unit, args.server)
    if args.action == 'render':
        if not args.output:
            p.error('render requires --output on mounted /mnt/vk-storage')
        if not args.output.resolve().is_relative_to('/mnt/vk-storage'):
            p.error('render output must be on /mnt/vk-storage')
        subprocess.run(['mountpoint', '-q', '/mnt/vk-storage'], check=True)
        for name, spec in planned.items():
            atomic(args.output / (name + '.d/capacity.conf'), spec['text'])
    else:
        subprocess.run(['mountpoint', '-q', '/mnt/vk-storage'], check=True)
        prerequisites(profile, args.server)
        if args.action == 'install':
            install(profile, args.unit, args.server, planned, Path.home() / '.config/systemd/user')
        check(profile, args.unit, args.server, planned, args.action == 'live-check')
        if args.action == 'lock-check':
            spec = importlib.util.spec_from_file_location('capacity_lock', Path(__file__).with_name('vk-capacity-lock.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.check_available(profile['stateDir'])
    print(json.dumps({'passed': True, 'action': args.action, 'unit': args.unit,
                      'server': str(args.server), 'liveVerified': args.action == 'live-check',
                      'servicesRestarted': False, 'goalsEnabled': False}))

if __name__ == '__main__':
    main()
