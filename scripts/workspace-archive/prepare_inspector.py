#!/usr/bin/env python3
"""Prepare a reviewable root capability package; never install or activate it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--custody-root',type=Path,required=True)
    parser.add_argument('--scope',type=Path,action='append',required=True)
    args=parser.parse_args()
    if not os.path.ismount('/mnt/vk-storage') or not args.output.is_relative_to('/mnt/vk-storage'):
        raise ValueError('Mounted secondary SSD package staging required')
    def binding(path,private=False):
        st=path.lstat()
        if (path.resolve()!=path or not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.getuid()
                or (private and stat.S_IMODE(st.st_mode)!=0o700)):
            raise ValueError('Canonical owned current storage root required')
        return dict(path=str(path),identity=[st.st_dev,st.st_ino])
    policy=dict(abi=1,caller_uid=os.getuid(),custody_root=binding(args.custody_root,True),
                scopes=[binding(p)for p in sorted(set(args.scope))])
    user=pwd.getpwuid(os.getuid()).pw_name
    if not re.fullmatch('[a-z_][a-z0-9_-]*',user):raise ValueError('Exact existing sudo principal required')
    args.output.mkdir(mode=0o700)
    source=Path(__file__).resolve().parent
    subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror','-fstack-protector-strong','-D_FORTIFY_SOURCE=2',
                    '-Wl,-z,relro,-z,now',str(source/'inspect_launcher.c'),'-o',str(args.output/'launcher')],check=True)
    (args.output/'inspector.py').write_bytes((source/'privileged_inspector.py').read_bytes())
    (args.output/'policy.json').write_text(json.dumps(policy,sort_keys=True,indent=2)+'\n')
    sha=hashlib.sha256((args.output/'launcher').read_bytes()).hexdigest()
    (args.output/'sudoers').write_text(user+' ALL=(root) NOPASSWD: sha256:'+sha+
        ' /usr/local/sbin/vk-workspace-archive-inspect-v1 ""\n')
    names=('launcher','inspector.py','policy.json','sudoers')
    manifest=dict(format='vk-workspace-inspector-package-v1',files={
        name:hashlib.sha256((args.output/name).read_bytes()).hexdigest()for name in names})
    raw=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    (args.output/'manifest.json').write_bytes(raw)
    for path in args.output.iterdir():path.chmod(0o600)
    print(json.dumps(dict(package=str(args.output),manifest_sha256=hashlib.sha256(raw).hexdigest(),
                         installed=False,backend_restarted=False),sort_keys=True))


if __name__=='__main__':main()
