// Read-only initial execution snapshot; emit configurations, never prompts.
const id=process.argv[2];
if(!/^[a-f0-9-]{36}$/.test(id))process.exit(2);
const ws=new WebSocket(`ws://127.0.0.1:4720/api/execution-processes/stream/session/ws?session_id=${id}`);
const timer=setTimeout(()=>process.exit(3),8000);
let received=false;
ws.onerror=()=>{if(!received)process.exit(4)};
process.stdout.on('error',()=>process.exit(5));
ws.onmessage=e=>{
  if(received)return;
  try{
    if(Buffer.byteLength(e.data)>8388608)throw Error();
    const j=JSON.parse(e.data);
    const p=(j.JsonPatch||[]).find(p=>p.path==='/execution_processes'&&p.value);
    if(!p)return;
    const rows=Object.values(p.value).map(x=>({id:x.id,session_id:x.session_id,status:x.status,created_at:x.created_at,completed_at:x.completed_at,config:x.executor_action?.typ?.executor_config}));
    received=true;
    ws.close();
    // Pipe writes are asynchronous. Exit only after the entire JSON is flushed.
    // Keep the existing watchdog active until then; never emit a second snapshot.
    process.stdout.write(JSON.stringify(rows)+'\n',error=>{
      if(error)process.exit(5);
      clearTimeout(timer);
      process.exit(0);
    });
  }catch{process.exit(5)}
};
