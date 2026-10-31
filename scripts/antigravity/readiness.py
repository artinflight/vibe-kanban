"""Check the official ACP runtime without authentication or inference.

Only protocol metadata is retained. Raw stdout, stderr, session IDs and error
messages are never written to the receipt. This is readiness, not end-to-end
executor acceptance, and a successful empty session does not enable Vibe.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

AUTH_METHODS = {'oauth-personal', 'oauth-business', 'gemini-api-key', 'agent-platform'}


def probe(runtime, expected_sha256, workdir, output, *, request_timeout=20, total_timeout=45):
    runtime, workdir, output = Path(runtime).resolve(), Path(workdir).resolve(), Path(output)
    with runtime.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != expected_sha256:
            raise ValueError('Runtime hash mismatch; nothing launched')
    if not workdir.is_dir():
        raise ValueError('An existing dedicated scratch directory is required')
    result = dict(schema=1, runtime_sha256=expected_sha256, initialize_passed=False,
                  authenticate_calls=0, prompt_calls=0, session_created=False,
                  credential_files_read_by_probe=False, outcome='probe_incomplete')
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as receipt:
        json.dump(result, receipt)
    env = {key: os.environ[key] for key in (
        'HOME', 'USER', 'LOGNAME', 'LANG', 'PATH', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS'
    ) if key in os.environ}
    env.update(TMPDIR=str(workdir), BROWSER='/bin/false')
    child, buffer, received = None, b'', 0
    selector, started = selectors.DefaultSelector(), time.monotonic()

    def request(request_id, method, params):
        nonlocal buffer, received
        child.stdin.write((json.dumps(dict(jsonrpc='2.0', id=request_id, method=method, params=params)) + '\n').encode())
        child.stdin.flush()
        deadline = min(started + total_timeout, time.monotonic() + request_timeout)
        while time.monotonic() < deadline:
            for key, _ in selector.select(.05):
                raw = os.read(key.fd, 65536)
                if not raw:
                    selector.unregister(key.fileobj)
                    continue
                received += len(raw)
                if received > 2 * 1024**2:
                    raise ValueError('Output bound exceeded')
                if key.data == 'stderr':
                    continue
                buffer += raw
                if len(buffer) > 262144:
                    raise ValueError('Line bound exceeded')
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if not line.strip():
                        continue
                    message = json.loads(line)
                    if not isinstance(message, dict):
                        raise ValueError('Invalid protocol object')
                    if message.get('id') == request_id and 'method' not in message:
                        return message
                    if 'method' in message and 'id' in message:
                        raise ValueError('Unexpected client request; no tool performed')
            if child.poll() is not None:
                raise ValueError('Runtime exited')
        raise TimeoutError('Readiness deadline')

    try:
        child = subprocess.Popen([str(runtime), '--uid='], cwd=workdir, env=env,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, start_new_session=True)
        for name in ('stdout', 'stderr'):
            selector.register(getattr(child, name), selectors.EVENT_READ, name)
        initialized = request(1, 'initialize', dict(protocolVersion=1, clientCapabilities={},
                              clientInfo=dict(name='vibe-kanban-acp-readiness', version='1')))
        if 'error' in initialized:
            result['outcome'] = 'initialize_rejected'
            code = initialized['error'].get('code')
            if type(code) is int:
                result['initialize_error_code'] = code
        else:
            value = initialized['result']
            if type(value.get('protocolVersion')) is not int or value['protocolVersion'] != 1:
                raise ValueError('Unsupported protocol')
            result.update(initialize_passed=True, protocol_version=1,
                          auth_methods=[method['id'] for method in value.get('authMethods', [])
                                        if method.get('id') in AUTH_METHODS],
                          load_session_advertised=value.get('agentCapabilities', {}).get('loadSession') is True)
            session = request(2, 'session/new', dict(cwd=str(workdir), mcpServers=[]))
            if 'error' in session:
                code = session['error'].get('code')
                if type(code) is int:
                    result['session_error_code'] = code
                # ACP's standard AUTH_REQUIRED code; no provider error text retained.
                result['authentication_required'] = code == -32000
            else:
                value = session['result']
                result.update(session_created=isinstance(value.get('sessionId'), str) and bool(value['sessionId']),
                              legacy_models_present=isinstance(value.get('models'), dict),
                              config_options_present=isinstance(value.get('configOptions'), list))
            result['outcome'] = ('session_ready_without_inference' if result['session_created'] else
                                 'authentication_required' if result.get('authentication_required') else 'session_unavailable')
    except Exception as error:
        result.update(outcome='probe_failed', error_type=type(error).__name__)
    finally:
        if child is not None:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=3)
            for pipe in (child.stdin, child.stdout, child.stderr):
                pipe.close()
        selector.close()
        result.update(owned_process_reaped=child is None or child.poll() is not None,
                      UTC=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      elapsed_seconds=round(time.monotonic() - started, 2))
        output.write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'sha256', 'workdir', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = probe(args.runtime, args.sha256, args.workdir, args.output)
    print(json.dumps(result))
    return 0 if result['session_created'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
