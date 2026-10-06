"""Bounded private FIFO read fault for real HTTP controller-lock contention."""
import json
import os
from pathlib import Path
import sys
import time

root=Path(sys.argv[1]);thread=sys.argv[2];tag=sys.argv[3]
assert root.name.startswith('vk-continuation-http-')
assert '/' not in thread and '/' not in tag
directory=root/'home/vk-goal-progress';directory.mkdir(exist_ok=True)
path=directory/(thread+'.json');assert not path.exists()
os.mkfifo(path,0o600)
(root/(tag+'-ready')).write_text('private FIFO created')
try:
    # Open nonblocking so a missing reader cannot leave a fixture helper alive.
    end=time.monotonic()+8
    while True:
        try:fd=os.open(path,os.O_WRONLY|os.O_NONBLOCK);break
        except OSError:
            if time.monotonic()>end:raise RuntimeError('No private FIFO reader')
            time.sleep(.01)
    with os.fdopen(fd,'w') as pipe:
        (root/(tag+'-connected')).write_text(json.dumps({'atMs':int(time.time()*1000)}))
        end=time.monotonic()+5
        while not (root/(tag+'-release')).exists() and time.monotonic()<end:time.sleep(.01)
        pipe.write('deliberately invalid synthetic progress')
finally:
    path.unlink()
