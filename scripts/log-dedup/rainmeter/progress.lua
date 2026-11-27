local current, offline, previous, lastReceipt = nil, false, nil, nil
local numbers = {'observed','progress','completed_files','resolved_files','total_files','completed_batches','total_batches','completed_raw_bytes','reclaimed_bytes'}
local phases = {
  actual_source_bytes_processed='Reading and packing closed history',
  batch_packed='Preparing verified backup capture',
  selected_original_backup_index_prepared='Original backup index ready',
  normal_b_graph_backup_and_restore_started='Backing up and testing archive recovery',
  archive_carrier_members_packed='Packing archive backup',
  archive_graph_members_verified='Verifying archive recovery',
  actual_production_reader_full_eof_verified='Live history reader verified',
  verified_duplicate_staging_retirement='Reclaiming verified staging copies',
  finite_batch_committed='Batch verified and committed',
  recovered_completed_batch_committed='Recovered checkpoint verified',
  paused_at_verified_checkpoint='Paused safely; backup access available',
  waiting_for_backup_access='Waiting for the shared backup lane',
  finite_conversion_complete_final_acceptance_pending='History converted; final checks pending'
}
local states = {
  running={'RUNNING','Green'}, paused={'PAUSED','Amber'}, waiting_for_backup={'BACKUP WAIT','Amber'},
  stalled={'STALLED','Red'}, controller_stopped={'STOPPED','Red'},
  failure_recovery_pending={'STOPPED','Red'}, recovery_failed={'RECOVERY ISSUE','Red'},
  failed_recovered={'STOPPED','Red'}, admission_expired={'STOPPED','Red'},
  success={'CHECKS PENDING','Cyan'}, preparing={'PREPARING','Amber'},
  waiting_for_current_turn={'WAITING','Amber'}
}
function Parse(text)
  if type(text)~='string' or #text>4096 then return nil end
  local data={}
  for line in text:gmatch('[^\r\n]+') do
    local key,value=line:match('^([a-z_]+)=(.*)$')
    if not key or data[key] then return nil end
    data[key]=value
  end
  if data.version~='1' or not states[data.state] then return nil end
  for _,key in ipairs(numbers) do
    local value=tonumber(data[key])
    if not value or value~=value or value==math.huge or value<0 and key~='reclaimed_bytes' then return nil end
    data[key]=value
  end
  if data.total_files<=0 or data.completed_files>data.resolved_files or data.resolved_files>data.total_files
    or data.completed_batches>data.total_batches or not data.phase or not data.phase:match('^[a-z0-9_]+$') then return nil end
  return data
end
local function comma(number)
  local value=string.format('%.0f',number)
  while true do local n;value,n=value:gsub('^(%-?%d+)(%d%d%d)','%1,%2');if n==0 then break end end
  return value
end
local function age(seconds)
  seconds=math.max(0,math.floor(seconds))
  if seconds<60 then return seconds..'s' end
  if seconds<3600 then return math.floor(seconds/60)..'m' end
  return string.format('%dh %dm',math.floor(seconds/3600),math.floor(seconds%3600/60))
end
function View(data,now,failed)
  if not data then return {state='NO LIVE DATA',color='Red',phase='Waiting for a valid monitor response',freshness='Connection unavailable or not yet initialized'} end
  local base=states[data.state] or {'UNKNOWN','Red'}
  local view={state=base[1],color=base[2],phase=phases[data.phase] or data.phase:gsub('_',' '),
    percent=100*data.resolved_files/data.total_files,
    count=comma(data.resolved_files)..' / '..comma(data.total_files)..' logs',
    verified=comma(data.completed_files)..' verified  |  '..comma(data.completed_batches)..' / '..comma(data.total_batches)..' batches',
    space=data.reclaimed_bytes>=0 and string.format('Log space recovered: %.2f GiB',data.reclaimed_bytes/1073741824) or 'Log space recovered: updating',
    processed=string.format('History processed: %.2f GiB',data.completed_raw_bytes/1073741824),
    freshness='Updated '..age(now-data.observed)..' ago  |  Progress '..age(now-data.progress)..' ago'}
  if data.state=='success' then view.phase='History converted; final validation pending' end
  if failed then view.state='OFFLINE';view.color='Red';view.phase='Connection lost; last known values shown'
  elseif data.observed>now+30 then view.state='CLOCK ERROR';view.color='Red';view.phase='Monitor timestamp is ahead of Desktop'
  elseif now-data.observed>180 then view.state='STALE';view.color='Red';view.phase='Monitor is stale; last known values shown'
  elseif data.state=='running' and now-data.progress>=600 then view.state='STALLED';view.color='Red';view.phase='No verified progress for 10 minutes' end
  return view
end
local function option(name,key,value) SKIN:Bang('!SetOption',name,key,tostring(value)) end
function FeedError() offline=true end
function FeedReady()
  local parsed=Parse(SKIN:GetMeasure('MeasureData'):GetStringValue())
  if parsed and (not current or parsed.observed>=current.observed) then current=parsed;offline=false else offline=true end
end
function Initialize() current=nil;offline=false;previous=nil;lastReceipt=nil end
function Update()
  local text=SKIN:GetMeasure('MeasureData'):GetStringValue()
  if text~=previous then previous=text;local parsed=Parse(text);if parsed and (not current or parsed.observed>=current.observed) then current=parsed;offline=false end end
  local view=View(current,os.time(),offline)
  option('State','Text',view.state);option('State','FontColor',SKIN:GetVariable(view.color))
  option('Phase','Text',view.phase);option('Freshness','Text',view.freshness)
  if view.percent then
    option('Count','Text',view.count);option('Percent','Text',string.format('%.1f%%',view.percent))
    option('Verified','Text',view.verified);option('Space','Text',view.space);option('Processed','Text',view.processed)
    option('BarFill','Shape',string.format('Rectangle 26,61,%.2f,4,2 | Fill Color %s | StrokeWidth 0',370*view.percent/100,SKIN:GetVariable(view.color)))
  end
  -- Bounded local observation receipt: permits independent live acceptance, no data collection.
  local stamp=current and current.observed or 0
  local receipt=stamp..'|'..view.state
  if receipt~=lastReceipt then
    local f=io.open(SKIN:GetVariable('@')..'display-state.txt','w')
    if f then f:write('observed='..stamp..'\nstate='..view.state..'\nresolved='..(current and current.resolved_files or 0)..'\n');f:close();lastReceipt=receipt end
  end
  return view.percent or 0
end
