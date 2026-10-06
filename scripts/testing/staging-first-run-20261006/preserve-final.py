"""Mirror bounded final software/evidence to Desktop; no production backup claim."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import time

sys.dont_write_bytecode=True
ROOT=Path('/mnt/vk-storage/vk-first-run-final-20261006')
SCRIPTS=Path(__file__).resolve().parent
REPO=SCRIPTS.parents[2]
sys.path.insert(0,'/mnt/vk-storage/vk-green-reprepare-20261005/operational-source/scripts/deployment')
from vk_desktop_transport import DesktopTransport

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
acceptance=json.loads((ROOT/'acceptance.json').read_text())
files=set(ROOT.glob('*.json'))|set(ROOT.glob('*.log'))|set(SCRIPTS.glob('*.py'))|set(SCRIPTS.glob('*.mjs'))|{SCRIPTS/'README.md'}
for name in ('VK_FIRST_RUN_FINAL_ACCEPTANCE_20261006.md','VK_FIRST_RUN_ROLLOUT_PLAN_20261006.md','VK_FIRST_RUN_STOP_REVIEW_20261006.md','VK_FIRST_RUN_FRONTEND_20261006.md','HANDOFF.md','STREAM.md'):
    files.add(REPO/name)
for group in acceptance['groups'].values():
    root=Path(group['root'])
    for name,digest in group['files'].items():
        path=root/name;assert sha(path)==digest;files.add(path)
    for pattern in ('fixtures.json','home/*timeline.jsonl','home/goals_1.sqlite*','home/vk-goal-progress/*.json'):
        files.update(root.glob(pattern))
# Preserve failed attempts as failures, never silently replace their evidence.
base=Path('/mnt/vk-storage/vk-sfr-http-20261006')
for suffix in ('fvi4by6h','qwufcmbc','vavimduc','iwcuzon1','ipyefy7c'):
    root=base/('vk-continuation-http-'+suffix)
    for pattern in ('driver.log','driver-result.json','provenance.json','fixture-cleanup.json','*-receipts-*.json','*-findings-*.json','backend-*.log'):
        files.update(root.glob(pattern))
developer=Path('/mnt/vk-storage/vk-scheduled-first-run-20261006')
for name in ('stop-response-handoff.md','stop-response-boundary-verification.json','revision-acceptance-9b3f8253879abdc5ebc88b3c3411946ce6f6a3b4.json'):
    files.add(developer/name)
files.add(Path('/mnt/vk-storage/vk-first-run-gates-20261006/original-stop-incident.json'))
packet=ROOT/('review-packet-'+str(time.time_ns())+'.tar.gz')
with tarfile.open(packet,'x:gz') as output:
    for path in sorted(files):output.add(path,arcname=str(path.relative_to('/mnt/vk-storage')),recursive=False)
with tarfile.open(packet) as source:
    for path in files:
        with source.extractfile(str(path.relative_to('/mnt/vk-storage'))) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==sha(path)
transport=DesktopTransport(ROOT/'desktop-transport')
payload=json.loads((ROOT/'deployment-payload-receipt.json').read_text())
receipts=[]
for path in (Path(payload['archive']),packet):
    receipts.append(transport.mirror(path,'B:/vk-backups/vk-first-run-final-20261006'))
assert all(r['desktop_verified'] for r in receipts)
result={'receipts':receipts,'packet':str(packet),'packetSha256':sha(packet),'filesVerified':len(files),'freshProductionBackup':False,'productionChanged':False,'deploymentAuthorized':False}
(ROOT/'desktop-preservation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
