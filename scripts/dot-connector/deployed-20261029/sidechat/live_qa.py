"""Bounded synthetic live QA, controlled over private fd3; never uses an owner's session.

Only the deployment runner invokes this trusted local helper. No HTTP identity
route is added. Temporary QA browser access expires after ten minutes, covers
one existing project, and is removed in finally. No real owner grant is changed.
"""
import json,os,sys,uuid,time,sqlite3,hashlib
from pathlib import Path
sys.path.insert(0,os.environ['VK_DOT_QA_RELEASE'])
from sidechat import Store,Principal
from browser_api import BrowserAuth,WorkspaceResolver
DATA=Path(os.environ['VK_DOT_QA_DATA']);VIBE=Path(os.environ['VK_DOT_QA_VIBE_DB']);W=os.environ['VK_DOT_QA_WORKSPACE']
PREFIX='dot-notifications-live-qa-'
def coding_hash():
 c=sqlite3.connect(VIBE.as_uri()+'?mode=ro',uri=True)
 rows=c.execute('SELECT hex(t.id),t.seen FROM coding_agent_turns t JOIN execution_processes e ON e.id=t.execution_process_id JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? ORDER BY t.id',(uuid.UUID(W).bytes,)).fetchall();c.close()
 return hashlib.sha256(json.dumps(rows).encode()).hexdigest()
def seeded(s,owner,thread,body,attention=None):
 m=s.append(Principal(owner,'owner'),thread,W,str(uuid.uuid4()),'Synthetic deployment verification; no action required.')
 event=s.db.execute('SELECT event FROM outbox WHERE message=?',(m['id'],)).fetchone()[0]
 reply=s.tool(Principal(owner,'dot'),'append_dot_reply',{'thread':thread,'workspace':W,'request':str(uuid.uuid4()),'body':body,'reply_to':m['id'],'event_id':event,**({'attention':attention} if attention else {})})
 return reply['id']
def cleanup(s,owner):
 assert owner.startswith(PREFIX);uuid.UUID(owner[len(PREFIX):])
 with s.transaction():
  s.db.execute('UPDATE browser_sessions SET revoked=1 WHERE owner=?',(owner,))
  s.db.execute('DELETE FROM dot_reply_state WHERE message IN (SELECT m.id FROM messages m JOIN threads t ON t.id=m.thread WHERE t.owner=?)',(owner,))
  for table in ['outbox','bindings','messages']:s.db.execute('DELETE FROM '+table+' WHERE thread IN (SELECT id FROM threads WHERE owner=?)',(owner,))
  for table in ['threads','scopes','browser_sessions','browser_grants']:s.db.execute('DELETE FROM '+table+' WHERE owner=?',(owner,))
command=sys.argv[1];args=json.load(sys.stdin);s=Store(DATA)
try:
 if command=='setup':
  scope=WorkspaceResolver(VIBE)(W);owner=PREFIX+str(uuid.uuid4())
  try:
   auth=BrowserAuth(s);grant=auth.grant(owner,[scope['project']]);token,session=auth.pair(grant['pairing_code'])
   s.db.execute('UPDATE browser_sessions SET expires=? WHERE id=?',(time.time()+600,session['id']))
   s.register_scope(owner,scope['project'],scope['issue'],W);thread=s.resolve(Principal(owner,'owner'),scope['project'],scope['issue'],W)['id']
   assert not s.db.execute('SELECT 1 FROM sidechat_subscriptions WHERE owner=?',(owner,)).fetchone()
   reply=seeded(s,owner,thread,'Synthetic Dot verification: can this question be resolved?','question')
   result={'owner':owner,'thread':thread,'reply':reply,'token':token,'csrf':session['csrf'],'workspace':W,'issue':scope['issue'],'project':scope['project'],'coding_hash':coding_hash()}
   with os.fdopen(3,'w') as control:json.dump(result,control)
  except BaseException:cleanup(s,owner);raise
 elif command=='next':
  owner=args['owner'];assert owner.startswith(PREFIX);assert s.db.execute('SELECT 1 FROM threads WHERE id=? AND owner=?',(args['thread'],owner)).fetchone()
  reply=seeded(s,owner,args['thread'],'Synthetic long verification reply.\n'*90)
  with os.fdopen(3,'w') as control:json.dump({'reply':reply},control)
 elif command=='inspect':
  rows=s.notifications(Principal(args['owner'],'owner'),[args['project']])['issues'];row=next((r for r in rows if r['issue_id']==args['issue']),{})
  result={'unread':row.get('unread_count',0),'attention':row.get('needs_attention_count',0),'coding_unchanged':coding_hash()==args['coding_hash'],'outbound_attempts':s.db.execute('SELECT COALESCE(SUM(o.attempts),0) FROM outbox o JOIN threads t ON t.id=o.thread WHERE t.owner=?',(args['owner'],)).fetchone()[0]}
  with os.fdopen(3,'w') as control:json.dump(result,control)
 elif command=='cleanup':
  cleanup(s,args['owner'])
  with os.fdopen(3,'w') as control:json.dump({'removed':True},control)
 else:raise ValueError('Unknown QA command')
finally:s.close()
