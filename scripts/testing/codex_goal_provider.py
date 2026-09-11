#!/usr/bin/env python3
"""Offline Responses fixture for the installed Codex goal engine.

Runs a real app-server with isolated caller-supplied CODEX_HOME, no credentials,
no external model requests, and deterministic multi-turn progress or refinement.
Used by the ignored native_goal_runtime integration test, never production.
"""
import http.server
import json
import os
import subprocess
import sys
import threading
import time

scenario = os.environ.get('VK_GOAL_TEST_SCENARIO', 'progress')
turn = 0


class Provider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        global turn
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        turn += 1
        if scenario == 'stop':
            time.sleep(0.05)
        requirements = {str(n): f'Verify parity requirement {n}' for n in range(8)}
        if scenario == 'tool' and turn <= 16:
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
    try:
        result = subprocess.run(argv, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
        sys.exit(result.returncode)
    finally:
        server.shutdown()
