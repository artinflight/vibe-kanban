"""Read-only input verification and inert release packaging; never activate services."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

SOURCE='9b3f8253879abdc5ebc88b3c3411946ce6f6a3b4'
CU='95e7aea47e137015daa8efcbb210184ee7ce723c'
ROOT=Path('/mnt/vk-storage/vk-first-run-final-20261006')
OLD=Path('/mnt/vk-storage/vk-first-run-gates-20261006')
DEV=Path('/mnt/vk-storage/worktrees/fa60-vk-scheduled-goa/_vibe_kanban_repo')
BUNDLE=Path('/mnt/vk-storage/vk-scheduled-first-run-20261006/bundle-'+SOURCE)

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def put(name,value):(ROOT/name).write_text(json.dumps(value,indent=2)+'\n')
def free():
    value=os.statvfs(ROOT);return value.f_bavail*value.f_frsize

assert os.path.ismount('/mnt/vk-storage')
ROOT.mkdir(exist_ok=True)
build=json.loads((OLD/'frontend-86f62b2/frontend-build.json').read_text())
manifest=json.loads((BUNDLE/'manifest.json').read_text())
assert manifest['sourceCommit']==SOURCE
changed=subprocess.check_output(['git','-C',str(DEV),'diff','--name-only',build['sourceCommit'],SOURCE],text=True).splitlines()
allowed={'DELTA.md','HANDOFF.md','STREAM.md','VK_SCHEDULED_FIRST_RUN.md','crates/executors/src/capacity/controller.rs','crates/executors/src/executors/codex/client.rs','crates/executors/src/executors/codex/jsonrpc.rs','crates/server/src/routes/capacity.rs','scripts/testing/codex_goal_provider.py','scripts/testing/scheduled-first-run-validation.py'}
assert set(changed)<=allowed,changed
files={}
for name in ('candidate/server','rollback/server','vk-capacity-guard'):
    path=BUNDLE/name;assert sha(path)==manifest['artifacts'][name]['sha256'];files[name]=path
for name,digest in build['assets'].items():
    path=Path(build['dist'])/name;assert sha(path)==digest;files['frontend/'+name]=path
put('frontend-compatibility.json',{'backendSource':SOURCE,'frontendSource':build['sourceCommit'],'changedFiles':changed,'frontendBuildInputsUnchanged':True,'assetsVerified':len(build['assets']),'originalBuildReceiptSha256':sha(OLD/'frontend-86f62b2/frontend-build.json'),'dist':build['dist'],'rebuildNeeded':False})
files['cu/source.tar']=OLD/('cu-source-'+CU+'.tar')
files['evidence/frontend-build.json']=OLD/'frontend-86f62b2/frontend-build.json'
files['evidence/frontend-compatibility.json']=ROOT/'frontend-compatibility.json'
files['evidence/backend-manifest.json']=BUNDLE/'manifest.json'
put('deployment-candidate.json',{'vkSource':SOURCE,'cuSource':CU,'version':'0.1.42','runtimeRequired':'0.159.2','productionChanged':False,'rolloutAuthorized':False,'sealedHandoverReady':False,'externalFrontendRequired':True,'runtimeEnvironment':{'VK_FRONTEND_DIST_DIR':'<release>/frontend'},'fallback':'rollback/server compile-disabled v2 reader with SAME LATEST DATA; old production reader unsafe','requiredOwnerChoices':{'routing':'Recommend','scheduling':True,'paidCredits':False},'remainingGates':['Explicit rollout approval and source promotion','Safe SSD headroom for fresh backup and complete-workload rehearsal','Fresh Desktop capture, single-writer configuration/rollback binding and final safe drain','Compatible CU deployed first, then VK capability exposure'],'files':{name:{'sha256':sha(path),'bytes':path.stat().st_size} for name,path in files.items()}})
files['manifest.json']=ROOT/'deployment-candidate.json'
# Bound storage by the uncompressed input size, not an optimistic compression ratio.
before=free();assert before>sum(p.stat().st_size for p in files.values())+100_000_000,before
archive=ROOT/('candidate-release-'+SOURCE+'.tar.gz')
with tarfile.open(archive,'x:gz',compresslevel=3) as output:
    for name,path in files.items():
        assert free()>100_000_000
        output.add(path,arcname=name,recursive=False)
with tarfile.open(archive) as source:
    assert {m.name for m in source.getmembers()}==set(files)
    for name,path in files.items():
        with source.extractfile(name) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==sha(path)
receipt={'archive':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size,'verifiedFiles':len(files),'source':SOURCE,'cu':CU,'freeBefore':before,'freeAfter':free(),'productionChanged':False,'rolloutAuthorized':False,'freshProductionBackup':False}
put('deployment-payload-receipt.json',receipt)
print(json.dumps(receipt))
