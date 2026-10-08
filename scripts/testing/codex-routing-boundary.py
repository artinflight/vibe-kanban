#!/usr/bin/env python3
"""Explicit two-turn paid acceptance: Luna -> Sol with a process restart and dirty file."""
import argparse
import json
import os
from pathlib import Path
import queue
import shlex
import signal
import subprocess
import threading
import time
import tomllib


class Rpc:
    def __init__(self):
        self.p = subprocess.Popen(shlex.split(os.environ.get('VK_CODEX_BASE_COMMAND', 'codex')) + ['app-server'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        self.lines = queue.Queue()
        self.seq = 0
        def pump():
            for line in self.p.stdout:
                self.lines.put(json.loads(line))
        threading.Thread(target=pump, daemon=True).start()
        self.call('initialize', {'clientInfo': {'name': 'vk_boundary_acceptance', 'version': '1'}})

    def read(self, deadline):
        return self.lines.get(timeout=max(.01, deadline-time.monotonic()))

    def call(self, method, params):
        self.seq += 1
        self.p.stdin.write(json.dumps({'id': self.seq, 'method': method, 'params': params})+'\n')
        self.p.stdin.flush()
        end = time.monotonic()+30
        while True:
            event = self.read(end)
            if event.get('id') == self.seq:
                if 'error' in event:
                    raise RuntimeError('RPC failed: '+method)
                return event['result']

    def turn(self, thread, prompt):
        result = self.call('turn/start', {'threadId': thread, 'input': [{'type':'text','text':prompt,'text_elements':[]}]})
        end = time.monotonic()+120
        while True:
            event = self.read(end)
            p = event.get('params',{})
            if event.get('method') == 'turn/completed' and p.get('turn',{}).get('id') == result['turn']['id']:
                assert p['turn']['status'] == 'completed', 'Turn failed'
                return result['turn']['id']

    def close(self):
        os.killpg(self.p.pid, signal.SIGTERM)
        self.p.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', required=True)
    args = parser.parse_args()
    work = Path(args.workdir).resolve()
    work.mkdir(parents=True, exist_ok=False)
    subprocess.run(['git','init','-q',str(work)],check=True)
    (work/'dirty.txt').write_text('baseline\n')
    subprocess.run(['git','-C',str(work),'add','dirty.txt'],check=True)
    subprocess.run(['git','-C',str(work),'-c','user.name=Routing acceptance','-c','user.email=routing@example.invalid','commit','-qm','fixture baseline'],check=True)
    (work/'dirty.txt').write_text('operator uncommitted work\n')
    home=Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
    config=tomllib.loads((home/'config.toml').read_text())
    overrides={'features.multi_agent':False,'model_reasoning_effort':'medium'}
    for name in config.get('mcp_servers',{}):overrides['mcp_servers.'+name+'.enabled']=False
    params={'cwd':str(work),'model':'gpt-6-luna','approvalPolicy':'never','sandbox':'workspace-write',
            'serviceTier':None,'config':overrides,'developerInstructions':'Only edit files inside the working directory. Never commit or reset Git. Preserve dirty.txt exactly. No network, no delegation.'}
    evidence={'tests':[]}
    rpc=Rpc()
    try:
        result=rpc.call('thread/start',params)
        assert result['model']=='gpt-6-luna' and result['reasoningEffort']=='medium'
        thread=result['thread']['id']
        rpc.turn(thread,'Write checkpoint.txt containing routing_state_721. Remember the passphrase glacier spoon for the next turn. Then stop; the next turn completes the task.')
        assert (work/'checkpoint.txt').read_text().strip()=='routing_state_721'
        evidence['tests'].append('Luna medium wrote checkpoint')
    finally:rpc.close()
    rpc=Rpc()
    try:
        result=rpc.call('thread/resume',{**params,'threadId':thread,'model':'gpt-6.1-sol'})
        assert result['thread']['id']==thread and result['model']=='gpt-6.1-sol' and result['reasoningEffort']=='medium' and result.get('serviceTier') in (None, 'default')
        rpc.turn(thread,'Complete the task: write completion.txt with the remembered passphrase and checkpoint.txt contents. Preserve the existing files and do not commit.')
        text=(work/'completion.txt').read_text()
        assert 'glacier spoon' in text and 'routing_state_721' in text
        assert (work/'dirty.txt').read_text()=='operator uncommitted work\n'
        evidence['tests'] += ['same thread resumed on Sol 6.1 medium, standard tier','conversation and checkpoint preserved','operator dirty file preserved']
        evidence['native_thread_id']=thread
        evidence['passed']=True
    finally:
        rpc.close()
        (work/'result.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence,indent=2))


if __name__=='__main__':main()
