#!/usr/bin/env python3
"""Offline Responses fixture for the installed Codex goal engine.

Runs a real app-server with isolated caller-supplied CODEX_HOME, no credentials,
no external model requests, and deterministic multi-turn progress or refinement.
Used by the ignored native_goal_runtime integration test, never production.
"""
import http.server
import json
import os
import shlex
from pathlib import Path
import subprocess
import sys
import threading
import time

scenario = os.environ.get('VK_GOAL_TEST_SCENARIO', 'progress')
turn = 0
recovery_stage = 0


class Provider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        global turn, recovery_stage
        request_body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
        turn += 1
        if scenario.startswith('capacity') and turn == 1:
            Path(os.environ['CODEX_HOME'], 'capacity-tools.json').write_text(
                json.dumps(json.loads(request_body).get('tools', []), indent=2))
        if scenario == 'capacity-containment' and turn == 3:
            Path(os.environ['CODEX_HOME'], 'capacity-delegation-reply.json').write_text(request_body)
        if scenario.startswith('capacity') and turn >= (3 if scenario == 'capacity-containment' else 2):
            # First deliver a durable checkpoint; then leave a native goal
            # actively awaiting a model response for 30 seconds.
            # Tests must interrupt it externally, not wait for a convenient turn.
            Path(os.environ['CODEX_HOME'], 'capacity-request-active').write_text(str(turn))
            time.sleep(30)
        if scenario == 'stop':
            time.sleep(0.05)
        requirements = {str(n): f'Verify parity requirement {n}' for n in range(8)}
        if scenario == 'capacity-containment' and turn == 1:
            probe = '''import json, socket, subprocess, time
from pathlib import Path
results = {"workspace_write": True}
for family, target, name in [(socket.AF_INET, ("127.0.0.1", 9), "tcp"), (socket.AF_UNIX, "/run/user/1000/bus", "systemd_bus")]:
    try:
        s = socket.socket(family); s.settimeout(1); s.connect(target)
        results[name] = "unexpected access"
    except OSError as error:
        results[name] = error.errno
try:
    Path.cwd().parent.joinpath("outside-work-proof").write_text("unexpected")
    results["outside_write"] = "unexpected access"
except OSError as error:
    results["outside_write"] = error.errno
heartbeat = Path("contained-child-heartbeat")
heartbeat.unlink(missing_ok=True)
child = "import signal,time,itertools; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); p=Path('contained-child-heartbeat'); [(p.write_text(str(time.time())),time.sleep(.1)) for _ in itertools.repeat(None)]"
subprocess.Popen(["python3", "-c", child], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(100):
    if heartbeat.exists(): break
    time.sleep(.01)
results["child_started"] = heartbeat.exists()
Path("native-containment.json").write_text(json.dumps(results))
print(json.dumps(results))'''
            item = dict(type='function_call', id='containment', call_id='containment',
                        name='exec_command', arguments=json.dumps(dict(
                            cmd='python3 -c ' + shlex.quote(probe), login=False,
                            yield_time_ms=1000, max_output_tokens=1000)))
        elif scenario == 'capacity-containment' and turn == 2:
            # Negative admission probe: depth zero must reject without starting
            # any sub-agent. All Responses are this offline fixture.
            item = dict(type='function_call', id='delegation', call_id='delegation',
                        name='spawn_agent',
                        arguments=json.dumps(dict(message='Offline denied-launch probe')))
        elif scenario == 'tool' and turn <= 16:
            stage = (turn - 1) // 2
            if turn % 2:
                checkpoint = dict(requirements=requirements if turn == 1 else {},
                                  completed={str(stage): f'Integration validation {stage}'},
                                  disposition='continue', reason='')
                item = dict(type='function_call', id=f'checkpoint{stage}', call_id=f'checkpoint{stage}',
                            name='vk_goal_checkpoint', arguments=json.dumps(checkpoint))
            else:
                item = dict(type='message', id=f'msg{turn}', role='assistant',
                            content=[dict(type='output_text', text=f'Stage {stage} complete.')], phase='final_answer')
        elif scenario == 'tool' and turn == 17:
            item = dict(type='function_call', id='finish', call_id='finish',
                        name='update_goal', arguments=json.dumps(dict(status='complete')))
        elif scenario == 'recover':
            # Steering can cause multiple model requests within one native turn.
            # Recover only after VK actually delivers its recovery instruction.
            if recovery_stage or 'AUTOMATIC RECOVERY 1/3' in request_body:
                recovery_stage += 1
            if recovery_stage <= 7:
                stage = recovery_stage
                checkpoint = dict(requirements=requirements if turn == 1 else {},
                                  completed={str(stage): f'Integration validation {stage}'},
                                  disposition='continue', reason='')
                if stage == 1:
                    checkpoint['recovery_plan'] = '1: requirement 0 is already sufficient; implement missing parity requirement 1 and verify its integration instead of polishing 0'
                text = f'Recovery fixture stage {stage}.\n<vk_goal_checkpoint>{json.dumps(checkpoint)}</vk_goal_checkpoint>'
                item = dict(type='message', id=f'msg{turn}', role='assistant',
                            content=[dict(type='output_text', text=text)], phase='final_answer')
            elif recovery_stage == 8:
                item = dict(type='function_call', id='finish', call_id='finish',
                            name='update_goal', arguments=json.dumps(dict(status='complete')))
            else:
                item = dict(type='message', id=f'msg{turn}', role='assistant',
                            content=[dict(type='output_text', text='Recovered and verified all eight requirements.')], phase='final_answer')
        elif turn <= 8 or scenario in ('loop', 'stop'):
            stage = min(turn - 1, 7) if scenario not in ('loop', 'stop') else 0
            checkpoint = dict(requirements=requirements if turn == 1 else {},
                              completed={str(stage): f'Integration validation {stage}'},
                              disposition='continue', reason='')
            if scenario == 'needs_input':
                checkpoint.update(disposition='needs_input', reason='Choose API compatibility policy')
            text = f'Stage {stage} validated.\n<vk_goal_checkpoint>{json.dumps(checkpoint)}</vk_goal_checkpoint>'
            item = dict(type='message', id=f'msg{turn}', role='assistant',
                        content=[dict(type='output_text', text=text)], phase='final_answer')
        elif turn == 9:
            item = dict(type='function_call', id='finish', call_id='finish',
                        name='update_goal', arguments=json.dumps(dict(status='complete')))
        else:
            item = dict(type='message', id=f'msg{turn}', role='assistant',
                        content=[dict(type='output_text', text='All eight requirements are verified.')],
                        phase='final_answer')
        events = [dict(type='response.created', response=dict(id=f'resp{turn}')),
                  dict(type='response.output_item.done', item=item),
                  dict(type='response.completed', response=dict(id=f'resp{turn}', output=[],
                      usage=dict(input_tokens=10, output_tokens=10, total_tokens=20)))]
        data = ''.join(f'event: {event["type"]}\ndata: {json.dumps(event)}\n\n' for event in events).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    if not os.environ.get('CODEX_HOME') or 'vk-continuation' not in os.environ['CODEX_HOME']:
        raise SystemExit('Use a disposable CODEX_HOME under the vk-continuation task directory')
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    overrides = {
        'model_provider': 'fixture', 'model': 'fixture',
        'model_providers.fixture.name': 'Offline goal fixture',
        'model_providers.fixture.base_url': f'http://127.0.0.1:{server.server_port}/v1',
        'model_providers.fixture.wire_api': 'responses',
        'model_providers.fixture.requires_openai_auth': False,
        'features.goals': True,
    }
    argv = [os.environ.get('VK_GOAL_TEST_CODEX', 'codex'), 'app-server']
    for key, value in overrides.items():
        argv.extend(['-c', f'{key}={json.dumps(value)}'])
    # Exercise the actual executor's process-level policy arguments too.
    forwarded = sys.argv[1:]
    if forwarded[:1] == ['app-server']:
        forwarded = forwarded[1:]
    argv.extend(forwarded)
    try:
        result = subprocess.run(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
        sys.exit(result.returncode)
    finally:
        server.shutdown()
