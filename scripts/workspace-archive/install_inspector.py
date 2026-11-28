#!/usr/bin/env python3
"""External-manager-only installation of one reviewed metadata capability.

No backend restart, general sudo grant, service, database or payload mutation.
Existing differing installed files are preserved and require reconciliation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

DESTINATIONS={
    'launcher':('/usr/local/sbin/vk-workspace-archive-inspect-v1',0o755),
    'inspector.py':('/usr/local/libexec/vk-workspace-archive-inspection-v1.py',0o644),
    'policy.json':('/etc/vibe-kanban/workspace-archive-inspection-v1.json',0o600),
    'sudoers':('/etc/sudoers.d/vk-workspace-archive-inspect-v1',0o440),
}


def install(package,expected):
    if os.geteuid()!=0:
        raise PermissionError('The dedicated external managing agent must perform this root installation')
    raw=(package/'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('Reviewed installation manifest differs')
    manifest=json.loads(raw)
    if manifest['format']!='vk-workspace-inspector-package-v1' or set(manifest['files'])!=set(DESTINATIONS):
        raise ValueError('Fixed metadata-only installation package required')
    bodies={}
    for name,(destination,mode) in DESTINATIONS.items():
        body=(package/name).read_bytes()
        if hashlib.sha256(body).hexdigest()!=manifest['files'][name]:
            raise ValueError('Reviewed installation member differs')
        target=Path(destination)
        for parent in (target.parent,*target.parent.parents):
            st=parent.lstat()
            if parent.resolve()!=parent or st.st_uid!=0 or st.st_mode & 0o022 or not stat.S_ISDIR(st.st_mode):
                raise ValueError('Trusted existing root installation directory required')
        if os.path.lexists(target):
            st=target.lstat()
            if (not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_nlink!=1
                    or stat.S_IMODE(st.st_mode)!=mode or target.read_bytes()!=body):
                raise ValueError('Different installed capability exists; preserve and reconcile it')
        bodies[name]=body
    # Parse the exact fragment before installing it. No caller-supplied command.
    subprocess.run(['/usr/sbin/visudo','-cf',str(package/'sudoers')],check=True)
    policy=json.loads(bodies['policy.json'])
    for row in [policy['custody_root'],*policy['scopes']]:
        path=Path(row['path']);st=path.lstat()
        if path.resolve()!=path or [st.st_dev,st.st_ino]!=row['identity'] or st.st_uid!=policy['caller_uid']:
            raise ValueError('Reviewed workspace storage binding changed')
    installed=[]
    for name,(destination,mode) in DESTINATIONS.items():
        target=Path(destination)
        if target.exists():continue
        fd,temporary=tempfile.mkstemp(prefix='.workspace-inspector-',dir=target.parent)
        try:
            with os.fdopen(fd,'wb') as out:
                out.write(bodies[name]);out.flush();os.fchmod(out.fileno(),mode);os.fsync(out.fileno())
            os.link(temporary,target,follow_symlinks=False)
            installed.append(destination)
        finally:
            os.unlink(temporary)
        fd=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    subprocess.run(['/usr/sbin/visudo','-c'],check=True)
    return dict(installed=installed,backend_restarted=False,workspace_payloads_changed=False,
                manifest_sha256=expected,live_clearance_still_required=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path)
    parser.add_argument('--manifest-sha256',required=True)
    args=parser.parse_args()
    print(json.dumps(install(args.package,args.manifest_sha256),sort_keys=True))
