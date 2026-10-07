"""Synthetic-only app-server transport fault; native/provider remain real offline fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

home = Path(os.environ['CODEX_HOME'])
assert '/vk-continuation-http-' in str(home)
provider = '/mnt/vk-storage/vk-combined-release-20261007/source/scripts/testing/codex_goal_provider.py'
child = subprocess.Popen([sys.executable, '-B', provider, *sys.argv[1:]], stdin=subprocess.PIPE)
try:
    for line in sys.stdin.buffer:
        message = json.loads(line)
        if message.get('method') in ('thread/goal/set', 'turn/interrupt') and (
            message.get('method') == 'turn/interrupt'
            or message.get('params', {}).get('status') == 'paused'
        ):
            with (home / ('dropped-' + os.environ['VK_STALLED_TIMELINE'])).open('a') as log:
                log.write(json.dumps({'atMs': int(time.time()*1000), 'method': message['method'], 'id': message.get('id')})+'\n')
            continue
        child.stdin.write(line)
        child.stdin.flush()
finally:
    child.stdin.close()
    child.wait(timeout=10)
