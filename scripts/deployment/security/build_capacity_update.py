"""Build as ordinary mcp from pinned local Git; never fetch/execute at root."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess

OLD='29af1c33e029bc1fe9ef9467fd51a03eb586105d'
NEW='d32d40574070b1dc66cb74eb3d55fd55bfb96a7e'
FILES={'/usr/local/libexec/vk-process-inspection-v1.py':'scripts/deployment/security/vk_retirement_check.py',
       '/usr/local/libexec/vk-historical-archive-inspection-v1.py':'scripts/deployment/security/vk_historical_archive_check.py'}

def build():
    read=lambda head,path:subprocess.check_output(['git','show',head+':'+path])
    encode=lambda data:base64.b64encode(data).decode('ascii')
    common=read('a875ccfe2d7ac094a93422cacd2a24d9a0f7803e','scripts/deployment/security/vk_inspection_installer.py')
    payload={'host_source':encode(common),'host_sha256':hashlib.sha256(common).hexdigest(),
             'files':{path:(encode(read(OLD,source)),encode(read(NEW,source))) for path,source in FILES.items()}}
    template=Path(__file__).with_name('vk_inspection_capacity_update.py').read_text()
    require_marker='PAYLOAD = None\n'
    if template.count(require_marker)!=1:raise ValueError('marker mismatch')
    return template.replace(require_marker,'PAYLOAD = '+repr(payload)+'\n').encode()

if __name__=='__main__':
    if os.geteuid()==0 or not os.path.ismount('/mnt/vk-storage'):raise SystemExit('ordinary-user mounted SSD build required')
    output=Path('/mnt/vk-storage/vk-retirement-preflight-tests/update-inspection-capacity-d32d40574.py')
    data=build()
    with output.open('xb') as stream:stream.write(data)
    print(json.dumps({'path':str(output),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}))
