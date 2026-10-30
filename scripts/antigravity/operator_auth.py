"""One explicit operator-authorized personal-account sign-in; never inference.

Prepare a dedicated browser handoff first. The executable browser hook must
forward the opaque runtime URL to that browser without recording it. This driver
does not read browser state or credentials, and never chooses an API-key method.
Keep the attempt directory private: SESSION.private.json contains native session
continuity and advertised model/mode metadata. A ready session is not activation.
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


def authenticate(runtime, expected_sha256, attempt_dir, browser_command, display,
                 *, auth_timeout=900, total_timeout=1020):
    RUNTIME, D = Path(runtime).resolve(), Path(attempt_dir).resolve()
    PIN = expected_sha256
    browser_command = Path(browser_command).resolve()
    if not browser_command.is_file() or not os.access(browser_command, os.X_OK):
        raise ValueError('An executable private browser hook is required')
    if not display.startswith(':') or not display[1:].isdigit():
        raise ValueError('A dedicated local display is required')
    with RUNTIME.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != PIN:
            raise ValueError('Runtime identity changed; nothing launched')
    D.mkdir(mode=0o700)  # Never reuse a consumed attempt.
    receipt = D / 'RESULT.safe.json'
    result = dict(schema=1, phase='starting', authenticate_calls=0, authenticate_ack=False,
                  session_created=False, prompt_calls=0, raw_output_retained=False,
                  runtime_sha256=PIN)
    fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)

    def save():
        receipt.write_text(json.dumps(result, indent=2) + '\n')

    save()
    env = {key: os.environ[key] for key in ('HOME', 'USER', 'LOGNAME', 'LANG', 'PATH',
           'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS') if key in os.environ}
    env.update(DISPLAY=display, BROWSER=str(browser_command), TMPDIR=str(D / 'tmp'))
    for name in ('tmp', 'empty-session'):
        (D / name).mkdir(mode=0o700)
    started = time.monotonic()
    child = None
    selector = selectors.DefaultSelector()
    buffer = b''
    received = 0

    def request(rid, method, params, timeout):
        nonlocal buffer, received
        child.stdin.write((json.dumps(dict(jsonrpc='2.0', id=rid, method=method, params=params)) + '\n').encode())
        child.stdin.flush()
        deadline = min(started + total_timeout, time.monotonic() + timeout)
        while time.monotonic() < deadline:
            for key, _ in selector.select(.2):
                raw = os.read(key.fd, 65536)
                if not raw:
                    selector.unregister(key.fileobj)
                    continue
                received += len(raw)
                if received > 2 * 1024**2:
                    raise ValueError('output bound')
                if key.data == 'stderr':
                    continue
                buffer += raw
                if len(buffer) > 262144:
                    raise ValueError('line bound')
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if not line.strip():
                        continue
                    message = json.loads(line)
                    if not isinstance(message, dict):
                        raise ValueError('invalid protocol')
                    if 'method' in message and 'id' in message:
                        raise ValueError('unsupported client request')
                    if message.get('id') == rid and 'method' not in message:
                        if 'error' in message:
                            code = message['error'].get('code')
                            result['request_error_code'] = code if type(code) is int else None
                            raise ValueError('ACP error')
                        return message['result']
            if child.poll() is not None:
                raise ValueError('runtime exited')
        raise TimeoutError('operator authentication deadline')

    try:
        child = subprocess.Popen([str(RUNTIME), '--uid='], cwd=D / 'empty-session', env=env,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True)
        result['owned_runtime_pid'] = child.pid
        for name in ('stdout', 'stderr'):
            selector.register(getattr(child, name), selectors.EVENT_READ, name)
        init = request(1, 'initialize', dict(protocolVersion=1, clientCapabilities={},
                       clientInfo=dict(name='vibe-kanban-operator-auth', version='1')), 20)
        methods = [m for m in init.get('authMethods', []) if m.get('id') == 'oauth-personal']
        if type(init.get('protocolVersion')) is not int or init['protocolVersion'] != 1 or len(methods) != 1 or methods[0].get('type', 'agent') != 'agent':
            raise ValueError('personal authentication not advertised')
        result.update(phase='awaiting_operator_signin', initialize_passed=True, authenticate_calls=1)
        save()
        ack = request(2, 'authenticate', {'methodId': 'oauth-personal'}, auth_timeout)
        if not isinstance(ack, dict) or ack:
            raise ValueError('unexpected authentication acknowledgment')
        result.update(authenticate_ack=True, phase='verifying_empty_session')
        save()
        session = request(3, 'session/new', dict(cwd=str(D / 'empty-session'), mcpServers=[]), 30)
        if not isinstance(session.get('sessionId'), str) or not session['sessionId']:
            raise ValueError('missing session identity')
        # Session IDs are private native continuity data, never browser/login payloads.
        private = D / 'SESSION.private.json'
        fd = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump({key: session[key] for key in ('sessionId', 'models', 'modes', 'configOptions') if key in session}, stream)
        result.update(phase='authenticated_session_ready', session_created=True,
                      config_options_present=isinstance(session.get('configOptions'), list),
                      legacy_models_present=isinstance(session.get('models'), dict),
                      legacy_modes_present=isinstance(session.get('modes'), dict))
    except Exception as error:
        result.update(phase='failed', error_type=type(error).__name__)
    finally:
        if child is not None:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=3)
            for stream in (child.stdin, child.stdout, child.stderr):
                stream.close()
        selector.close()
        result.update(owned_process_reaped=child is None or child.poll() is not None,
                      elapsed_seconds=round(time.monotonic() - started, 2),
                      UTC=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        save()
    return result



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'sha256', 'attempt-dir', 'browser-command', 'display'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    parent = Path(args.attempt_dir).resolve().parent
    mount = subprocess.check_output(['findmnt', '-n', '-o', 'TARGET', '--target', str(parent)], text=True).strip()
    if mount != '/mnt/vk-storage':
        raise ValueError('Use a fresh attempt directory on mounted secondary SSD')
    result = authenticate(args.runtime, args.sha256, args.attempt_dir, args.browser_command, args.display)
    print(json.dumps(result))
    return 0 if result['session_created'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
