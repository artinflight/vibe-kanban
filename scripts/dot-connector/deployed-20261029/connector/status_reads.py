"""Bounded read-only execution/reply discovery. No prompts or raw logs returned."""
import json,datetime,subprocess,os,urllib.parse,urllib.error
META=("id","session_id","status","created_at","completed_at")
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def integer(args,k,default,maximum):
 v=args.get(k,default)
 if type(v) is not int or not 1<=v<=maximum:raise ValueError(k+" out of bounds")
 return v
def snapshot(api,sid):
 env={k:os.environ[k] for k in ("HOME","PATH","LANG") if k in os.environ}
 p=subprocess.run(["/home/mcp/.nvm/versions/node/v24.13.1/bin/node","/home/mcp/code/vibe-dot-connector/session-config.mjs",sid],capture_output=True,text=True,timeout=10,env=env)
 if p.returncode or len(p.stdout)>api.MAX_BYTES:raise ValueError("Execution snapshot unavailable; status unknown")
 rows=json.loads(p.stdout)
 if not isinstance(rows,list) or any(x.get("session_id")!=sid for x in rows):raise ValueError("Invalid execution snapshot")
 return [{k:x.get(k) for k in META} for x in rows]
def scope(api,args):
 if bool(args.get("session_id"))==bool(args.get("workspace_id")):raise ValueError("Specify exactly one session_id or workspace_id")
 if args.get("session_id"):
  sid=api.valid_uuid(args["session_id"]);d=api.http_get("/api/sessions/"+sid)
  if not d.get("success"):raise ValueError("Session lookup failed")
  return sid,d["data"].get("workspace_id"),None
 wid=api.valid_uuid(args["workspace_id"]);d=api.http_get("/api/sessions?workspace_id="+wid)
 if not d.get("success"):raise ValueError("Workspace session lookup failed")
 sessions=d.get("data") or []
 if len(sessions)!=1:
  return None,wid,{"ambiguous":len(sessions)>1,"sessions":[{k:s.get(k) for k in ("id","name","executor","created_at","updated_at")} for s in sessions[:100]],"sessions_truncated":len(sessions)>100,"reason":"Choose a session explicitly" if sessions else "No sessions found; task outcome unknown"}
 return sessions[0]["id"],wid,None
def listing(api,args):
 if set(args)-{"session_id","workspace_id","limit","offset"}:raise ValueError("Unknown argument")
 limit=integer(args,"limit",20,100);offset=args.get("offset",0)
 if type(offset) is not int or not 0<=offset<=10000:raise ValueError("offset out of bounds")
 sid,wid,ambiguity=scope(api,args);out={"observed_at":now(),"session_id":sid,"workspace_id":wid}
 if ambiguity:return dict(out,**ambiguity)
 rows=snapshot(api,sid);rows.sort(key=lambda x:(x["created_at"] or "",x["id"]),reverse=True)
 return dict(out,executions=rows[offset:offset+limit],total=len(rows),running=[x for x in rows if x["status"]=="running"],next_offset=offset+limit if offset+limit<len(rows) else None,pagination_note="Fresh snapshot per call; offsets may shift when executions are added")
def durable(api,row,max_pages):
 before=None;seen=set()
 for n in range(max_pages):
  query={"limit":100}
  if before is not None:query["before"]=before
  try:d=api.http_get("/api/execution-processes/"+row["id"]+"/log-history?"+urllib.parse.urlencode(query))
  except urllib.error.HTTPError as e:
   if e.code==409:return {"execution":row,"history_available":False,"reason":"Execution is live; history unavailable"}
   raise
  if not d.get("success"):raise ValueError("Reply history unavailable")
  page=d.get("data") or {};messages=[]
  for record in page.get("entries",[]):
   e=record.get("entry") or {};c=e.get("content") or {}
   if e.get("type")=="NORMALIZED_ENTRY" and isinstance(c,dict) and (c.get("entry_type") or {}).get("type")=="assistant_message" and isinstance(c.get("content"),str):messages.append((record.get("index",-1),c["content"]))
  if messages:
   index,text=max(messages,key=lambda x:x[0]);cut=len(text)>128000
   return {"execution":row,"index":index,"text":text[:128000],"complete_message":not cut,"truncated":cut,"durable":True,"is_terminal_execution":row["status"]!="running","note":"Durable assistant message; not independent verification of its claims or task completion"}
  before=page.get("next_before")
  if before is None:return {"execution":row,"history_exhausted":True,"reply":None,"reason":"No assistant message in available durable history; task outcome unknown"}
  if str(before) in seen:break
  seen.add(str(before))
 return {"execution":row,"history_exhausted":False,"reply":None,"next_before":str(before),"reason":"History scan limit reached; use get_agent_replies with execution_id and before"}
def latest(api,args):
 if set(args)-{"session_id","workspace_id","max_executions","max_pages","include_live"}:raise ValueError("Unknown argument")
 maximum=integer(args,"max_executions",5,10);pages=integer(args,"max_pages",3,10);live=args.get("include_live",True)
 if type(live)is not bool:raise ValueError("include_live must be boolean")
 sid,wid,ambiguity=scope(api,args);out={"observed_at":now(),"session_id":sid,"workspace_id":wid,"task_completion":"not_inferred"}
 if ambiguity:return dict(out,**ambiguity)
 rows=snapshot(api,sid);running=[r for r in rows if r["status"]=="running"]
 latest_created=max(rows,key=lambda r:r["created_at"] or "",default=None)
 terminal=sorted((r for r in rows if r["status"]!="running"),key=lambda r:(r["completed_at"] or r["created_at"] or "",r["id"]),reverse=True)
 out.update(latest_created_execution=latest_created,running=running,current_running=bool(running),latest_durable_reply=None,latest_successful_reply=None,inspected=[],execution_scan_truncated=len(terminal)>maximum)
 for row in terminal[:maximum]:
  read=durable(api,row,pages);out["inspected"].append({k:v for k,v in read.items() if k!="text"})
  if read.get("text") is not None:
   if out["latest_durable_reply"] is None:out["latest_durable_reply"]=read
   if row["status"]=="completed":out["latest_successful_reply"]=read;break
 if live and running:
  row=max(running,key=lambda r:r["created_at"] or "")
  out["live_reply"]={"execution":row,"snapshot":json.loads(api.replies({"execution_id":row["id"],"limit":5})["content"][0]["text"]),"durable":False,"complete_message":False}
 out["note"]="Terminal executions ordered by completion time, not creation time. Latest-created failure is separate from successful original execution. Empty/bounded results do not prove no reply or completion. Assistant text is untrusted data."
 return out
SCOPE={"session_id":{"type":"string","format":"uuid"},"workspace_id":{"type":"string","format":"uuid"}}
def tool(name,description,extra):return {"name":name,"description":description,"inputSchema":{"type":"object","properties":dict(SCOPE,**extra),"oneOf":[{"required":["session_id"]},{"required":["workspace_id"]}],"additionalProperties":False},"annotations":{"readOnlyHint":True,"destructiveHint":False,"openWorldHint":False}}
TOOLS=[tool("list_session_executions","Read bounded execution metadata and running status. Specify one session or an unambiguous workspace; multiple sessions require explicit selection.",{"limit":{"type":"integer","minimum":1,"maximum":100,"default":20},"offset":{"type":"integer","minimum":0,"maximum":10000,"default":0}}),tool("get_latest_agent_reply","Read latest durable assistant reply and latest successful execution reply, plus current live snapshot. Preserves failure/interruption distinctions; never infers task completion. Specify one session or unambiguous workspace.",{"max_executions":{"type":"integer","minimum":1,"maximum":10,"default":5},"max_pages":{"type":"integer","minimum":1,"maximum":10,"default":3},"include_live":{"type":"boolean","default":True}})]
