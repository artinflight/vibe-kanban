#!/usr/bin/env python3
"""Discover and optionally verify routing models. No inference without --verify.
Writes only sanitized evidence; use an output path outside source/worktree roots.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import threading
import shlex
import subprocess
import time
import tomllib

MODELS = ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-6-luna", "gpt-6-sol", "gpt-6.1-sol", "gpt-6-astra"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--verify', action='store_true', help='One short inference turn per model (maximum seven).')
    parser.add_argument('--models', nargs='+', default=MODELS, help='Exact IDs; new releases need no code changes.')
    args = parser.parse_args()
    if len(args.models) > 7 or len(set(args.models)) != len(args.models):
        parser.error('Use at most seven distinct model IDs per bounded probe')
    home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).resolve()
    launcher = os.environ.get('VK_CODEX_BASE_COMMAND', 'codex')
    config = tomllib.loads((home / 'config.toml').read_text()) if (home / 'config.toml').exists() else {}
    p = subprocess.Popen(shlex.split(launcher) + ['app-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    lines = queue.Queue()
    def pump():
        for line in p.stdout:
            lines.put(line)
        lines.put(None)
    threading.Thread(target=pump, daemon=True).start()
    seq = 0

    def read(deadline):
        try:
            line = lines.get(timeout=max(0.01, deadline - time.monotonic()))
        except queue.Empty:
            raise TimeoutError('app-server timeout') from None
        if line is None:
            raise RuntimeError('app-server closed')
        return json.loads(line)

    def rpc(method, params):
        nonlocal seq
        seq += 1
        p.stdin.write(json.dumps({'id': seq, 'method': method, 'params': params}) + '\n')
        p.stdin.flush()
        deadline = time.monotonic() + 30
        while True:
            d = read(deadline)
            if d.get('id') == seq:
                if 'error' in d:
                    raise RuntimeError('RPC rejected: ' + method)
                return d['result']

    evidence = {'version': 1, 'observed_at': int(time.time()), 'codex_home': str(home), 'launcher': launcher, 'models': []}
    try:
        init = rpc('initialize', {'clientInfo': {'name': 'vk_routing_probe', 'version': '1'}})
        evidence['runtime'] = init['userAgent']
        account = rpc('account/read', {})['account'] or {}
        if account.get('type') != 'chatgpt' or not account.get('email'):
            raise RuntimeError('Automatic routing verification requires a signed-in Work/Codex account')
        # Match Rust runtime identity without storing an email or credential.
        identity = account.get('type', '') + ':' + account.get('email', '')
        evidence['account_fingerprint'] = hashlib.sha256(identity.encode()).hexdigest()
        native = {}
        cursor = None
        while True:
            page = rpc('model/list', {'includeHidden': True, 'cursor': cursor})
            native.update({m['id']: m for m in page['data']})
            cursor = page.get('nextCursor')
            if not cursor:
                break
        for model in args.models:
            m = native.get(model)
            efforts = [x['reasoningEffort'] for x in m['supportedReasoningEfforts']] if m else []
            effort = 'high' if model == 'gpt-6-astra' else 'medium'
            row = {'id': model, 'discovered': m is not None, 'supported_efforts': efforts,
                   'verified_efforts': [], 'verified_at': None}
            evidence['models'].append(row)
            if args.verify:
                overrides = {'features.multi_agent': False}
                for name in config.get('mcp_servers', {}):
                    overrides['mcp_servers.' + name + '.enabled'] = False
                overrides['model_reasoning_effort'] = effort
                try:
                    thread = rpc('thread/start', {'model': model, 'cwd': str(Path(args.output).parent.resolve()),
                        'ephemeral': True, 'approvalPolicy': 'never', 'sandbox': 'read-only',
                        'serviceTier': None, 'config': overrides,
                        'developerInstructions': 'For this verification, use no tools. Return exactly ROUTING_OK.'})
                    if (thread['model'] != model or thread.get('modelProvider') != 'openai'
                            or thread.get('reasoningEffort') != effort
                            or thread.get('serviceTier') not in (None, 'default')):
                        raise RuntimeError('resolved model mismatch')
                    started = rpc('turn/start', {'threadId': thread['thread']['id'], 'model': model, 'effort': effort,
                        'input': [{'type': 'text', 'text': 'Return exactly ROUTING_OK.', 'text_elements': []}]})
                    end = time.monotonic() + 90
                    ok_text = False
                    while True:
                        event = read(end)
                        params = event.get('params', {})
                        if params.get('threadId') != thread['thread']['id']:
                            continue
                        if event.get('method') == 'model/rerouted':
                            raise RuntimeError('provider rerouted requested model')
                        if event.get('method') == 'item/completed':
                            item = params.get('item', {})
                            if item.get('type') == 'agentMessage' and 'ROUTING_OK' in item.get('text', ''):
                                ok_text = True
                        if event.get('method') == 'turn/completed' and params['turn']['id'] == started['turn']['id']:
                            if params['turn']['status'] != 'completed' or not ok_text:
                                raise RuntimeError('inference failed: ' + str((params['turn'].get('error') or {}).get('message', 'no success marker'))[:400])
                            break
                    row['verified_efforts'] = [effort]
                    row['verified_at'] = int(time.time())
                except (RuntimeError, TimeoutError) as error:
                    row['failure'] = str(error)
                    # No billed retry. Stop a timed-out request before another model.
                    if isinstance(error, TimeoutError):
                        break
            print(model, 'discovered=' + str(row['discovered']), 'verified=' + str(row['verified_efforts']), flush=True)
    finally:
        import signal
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=10)
        Path(args.output).write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    main()
