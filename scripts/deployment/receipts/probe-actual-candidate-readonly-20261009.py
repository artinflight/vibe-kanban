"""Read-only namespace view; never start a server or alter either generation."""
import subprocess,json,hashlib,time
from pathlib import Path
root=Path('/mnt/vk-storage/vk-cutover-candidate-20261009/tree')
a=Path('/mnt/vk-storage/vk-cutover-artifacts-20261009/c3c48e63')
front=Path('/mnt/vk-storage/vk-safe-release-20261009/frontend66-over-c3/packages/local-web/dist-v6')
selectors={'database':'/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban/db.v2.sqlite','workspaces':'/home/mcp/code/worktrees','codex_home':'/home/mcp/.local/share/vibe-kanban-green-codex-home','controller':'/mnt/vk-storage/codexusage-capacity/runtime/controller','token':'/mnt/vk-storage/codexusage-capacity/runtime/control.token'}
expected={}
for key,p in selectors.items():
 backing=root/p.lstrip('/') if key!='workspaces' else root/'mnt/vk-storage/worktrees'
 s=backing.stat();expected[key]=[s.st_dev,s.st_ino]
program='''import os,json,hashlib,socket,sqlite3
from pathlib import Path
selectors,expected=json.loads(os.environ['VK_READONLY_SELECTORS']),json.loads(os.environ['VK_READONLY_IDENTITIES'])
actual={}
for k,p in selectors.items():
 s=Path(p).stat();actual[k]=[s.st_dev,s.st_ino]
 if actual[k]!=expected[k]:raise ValueError('candidate virtual identity mismatch: '+k)
assert str(Path(selectors['workspaces']).resolve())=='/mnt/vk-storage/worktrees'
assert not Path('/run/user/1000/systemd/private').exists()
assert not Path('/run/user/1000/bus').exists()
with socket.socket() as s:
 s.settimeout(.2)
 try:s.connect(('127.0.0.1',5511))
 except OSError:incumbent_network_hidden=True
 else:raise ValueError('incumbent network unexpectedly visible')
with sqlite3.connect(Path(selectors['database']).as_uri()+'?mode=ro&immutable=1',uri=True) as db:
 table=bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='vk_runtime_identity'").fetchall())
info={}
for role,expected_sha in [('candidate','2aa884b359d21373e38c49a6e1589a10e5f69f7c384d2be44515fc0fab41b70f'),('rollback','c6ebdd425e097f886cca8ae7781ddecb8b96cd96fde4e8c0f70362a5612faa91')]:
 with open('/run/vk-readonly-release/'+role+'/server','rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 assert h==expected_sha;info[role]=h
with open('/run/vk-readonly-frontend/index.html','rb') as f:
 assert hashlib.file_digest(f,'sha256').hexdigest()=='905c20c656e3eb4d9a514f5df199bcee5c6b23db4f016ff666ee32a39e3966ca'
print(json.dumps({'selector_identities':actual,'workspace_alias_resolves_to_candidate':True,'host_manager_hidden':True,'incumbent_network_hidden':incumbent_network_hidden,'backend_artifacts_sha256':info,'frontend_index_bound':True,'runtime_identity_enrolled':table,'application_started':False,'candidate_modified':False,'production_changed':False,'operational_acceptance':False}))
'''
argv=['/home/mcp/.local/bin/bwrap','--unshare-all','--new-session','--die-with-parent','--ro-bind','/','/','--tmpfs','/run','--tmpfs','/tmp','--proc','/proc','--dev','/dev','--ro-bind',str(a),'/run/vk-readonly-release','--ro-bind',str(front),'/run/vk-readonly-frontend','--ro-bind',str(root/'home/mcp'),'/home/mcp','--ro-bind',str(root/'mnt/vk-storage'),'/mnt/vk-storage','--chdir','/usr','--clearenv','--setenv','HOME','/home/mcp','--setenv','PATH','/usr/bin:/bin','--setenv','VK_READONLY_SELECTORS',json.dumps(selectors),'--setenv','VK_READONLY_IDENTITIES',json.dumps(expected),'--','/usr/bin/python3','-I','-B','-c',program]
r=subprocess.run(argv,capture_output=True,text=True,timeout=30)
if r.returncode:raise RuntimeError('Read-only actual candidate namespace probe failed: '+r.stderr[-2000:])
v=json.loads(r.stdout);v['utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());v['probe_kind']='read-only actual candidate mapping; no runtime/rehearsal acceptance';v['cleanup_available']=False
v['actual_root']='/mnt/vk-storage/vk-cutover-candidate-20261009';v['command_sha256']=hashlib.sha256(json.dumps(argv).encode()).hexdigest()
v['helper_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
v['prior_mount_target_failure']='read-only /opt target absent; corrected inside existing private /run tmpfs, no host permissions changed'
with Path('/mnt/vk-storage/vk-runtime-backup-20261009/actual-candidate-readonly-namespace-1500.safe.json').open('x') as f:json.dump(v,f,sort_keys=True,indent=2)
print(json.dumps(v))
