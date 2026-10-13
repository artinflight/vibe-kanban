"""One-off administrator replacement of TWO exact installed code files only.

Builder embeds the already tested FD-relative Host implementation and exact old/
new code bytes. No grant/policy/anchor/adoption changes, downloads or compilation.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

SOURCE_HEAD = 'd32d40574070b1dc66cb74eb3d55fd55bfb96a7e'
PLAN_HEAD = '29af1c33e029bc1fe9ef9467fd51a03eb586105d'
PLAN_SHA = 'a17d7f29b4b47c25811e8bf3d992f09ecd5084812d666dc761fbf4afff8a5357'
ANCHOR = '/mnt/vk-storage/vk-process-inspection-managed-v1'
EVIDENCE = ANCHOR + '/installation.safe.json'
UPDATE_EVIDENCE = ANCHOR + '/capacity-update.safe.json'
PAYLOAD = None
PINS = {
 '/usr/local/libexec/vk-process-inspection-v1.py': (
  '6e898eeb21d04cfbf4d94e5939eb20b27d89f069ee99b8b021d63893b4263d63',
  '4a752a726f7ccf9cf756cedf87a2c8132e7c2c8097da88be72a83519665e77bb'),
 '/usr/local/libexec/vk-historical-archive-inspection-v1.py': (
  '4b1b4f607f6be9059e060d84e1b062f97bb535b11d776cc748969b647651f481',
  '17c3d68338972964f1450c9f31f4a4ce76214469763c8b57a90e0e512c4b453a')}


def require(value, reason='capacity update blocked'):
    if not value: raise ValueError(reason)


def digest(data): return hashlib.sha256(data).hexdigest()


def load(payload):
    require(set(payload) == {'host_source','host_sha256','files'})
    common = base64.b64decode(payload['host_source'], validate=True)
    require(digest(common) == payload['host_sha256'] == '303103593cca96d008933f3fb0892c152623b8abbcb0b96418ee8d13e511b7cf')
    namespace = {'__name__':'verified_fd_helpers'}
    exec(compile(common, 'verified_fd_helpers', 'exec'), namespace)
    files = {path: tuple(base64.b64decode(data, validate=True) for data in versions)
             for path, versions in payload['files'].items()}
    require(set(files) == set(PINS))
    for path, versions in files.items():
        require(len(versions)==2 and tuple(digest(data) for data in versions)==PINS[path])
    return namespace['Host'], files


class Update:
    def __init__(self, host, files):
        self.host,self.files=host,files

    def preflight(self, updated=False):
        raw,_=self.host.read(EVIDENCE,0o600)
        receipt=json.loads(raw)
        require(receipt['approved_plan_head']==PLAN_HEAD and receipt['plan_sha256']==PLAN_SHA)
        info=self.host.metadata(ANCHOR)
        require(stat.S_ISDIR(info.st_mode) and info.st_uid==self.host.root_uid
                and stat.S_IMODE(info.st_mode)==0o755
                and list((info.st_dev,info.st_ino))==receipt['anchor_identity'])
        for path,checksum in receipt['installed_files'].items():
            # Never accept an arbitrary root-read path from even retained evidence.
            require(path in {*PINS, '/usr/local/sbin/vk-process-inspect-v1',
             '/usr/local/sbin/vk-historical-archive-inspect-v1',
             '/etc/vibe-kanban/process-inspection-v1.json',
             '/etc/vibe-kanban/historical-archive-inspection-v1.json',
             '/etc/sudoers.d/vk-process-inspection-v1'})
            mode=0o440 if '/sudoers.d/' in path else 0o600 if path.endswith('.json') else \
                 0o644 if path.endswith('.py') else 0o755
            data,_=self.host.read(path,mode)
            expected=(PINS[path] if updated is None else (PINS[path][int(updated)],)) if path in PINS else (checksum,)
            require(digest(data) in expected,'unexpected installed file; refuse overwrite')
        require(set(receipt['installed_files'])=={*PINS,
         '/usr/local/sbin/vk-process-inspect-v1','/usr/local/sbin/vk-historical-archive-inspect-v1',
         '/etc/vibe-kanban/process-inspection-v1.json','/etc/vibe-kanban/historical-archive-inspection-v1.json',
         '/etc/sudoers.d/vk-process-inspection-v1'})
        return receipt

    def replace(self, path, data, expected):
        # Temporary and destination are in the same immutable root-owned directory.
        staged=path+'.capacity-'+uuid.uuid4().hex
        self.host.create(staged,data,0o644)
        current,_=self.host.read(path,0o644)
        require(digest(current)==expected,'concurrent code change; refuse overwrite')
        parent=self.host.directory(str(Path(path).parent),immutable=True)
        try:
            os.replace(Path(staged).name,Path(path).name,src_dir_fd=parent,dst_dir_fd=parent)
            os.fsync(parent)
        finally: os.close(parent)

    def apply(self):
        receipt=self.preflight()
        self.host.absent(UPDATE_EVIDENCE)
        changed=[]
        try:
            # Managed library first; mixed-version invocations can only fail closed.
            for path,(old,new) in self.files.items():
                self.replace(path,new,PINS[path][0]);changed.append(path)
            self.preflight(updated=True)
            receipt['capacity_update_source']=SOURCE_HEAD
            receipt['capacity_update_performed']=True
            receipt['operational_adoption_changed']=False
            for path in PINS: receipt['installed_files'][path]=PINS[path][1]
            self.host.create(UPDATE_EVIDENCE,(json.dumps(receipt,indent=2,sort_keys=True)+'\n').encode(),0o600)
            return receipt  # authentic stdout; feed this updated receipt to acceptance
        except BaseException:
            errors=[]
            for path in reversed(tuple(self.files)):
                try:
                    raw,_=self.host.read(path,0o644)
                    if digest(raw)==PINS[path][1]: self.replace(path,self.files[path][0],PINS[path][1])
                    elif digest(raw)!=PINS[path][0]: errors.append(path)
                except Exception:errors.append(path)
            print(json.dumps({'passed':False,'changed_code_rollback_blocked':errors,
                              'policies_grants_anchor_adoption_unchanged':True}))
            raise

    def rollback(self):
        receipt=self.preflight(updated=None)
        for path,(old,new) in reversed(tuple(self.files.items())):
            raw,_=self.host.read(path,0o644)
            if digest(raw)==PINS[path][1]: self.replace(path,old,PINS[path][1])
        self.preflight()
        return {'capacity_code_restored':True,'policies_grants_anchor_adoption_unchanged':True}


def main():
    parser=argparse.ArgumentParser(description='Exact two-code-file capacity update only')
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--dry-run',action='store_true')
    group.add_argument('--apply',action='store_true')
    group.add_argument('--verify',action='store_true')
    group.add_argument('--rollback',action='store_true')
    parser.add_argument('--approved-update')
    args=parser.parse_args()
    try:
        import sys
        require(os.geteuid()==0 and sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode,
                'isolated administrator authentication required')
        if args.apply or args.rollback:
            require(args.approved_update==SOURCE_HEAD,'exact source action approval required')
        Host,files=load(PAYLOAD)
        update=Update(Host(),files)
        result=update.apply() if args.apply else update.rollback() if args.rollback else \
               update.preflight(updated=args.verify)
        print(json.dumps(result,sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({'passed':False,'error_type':type(error).__name__,
                          'policies_grants_anchor_adoption_unchanged':True}))
        return 1


if __name__=='__main__': raise SystemExit(main())
