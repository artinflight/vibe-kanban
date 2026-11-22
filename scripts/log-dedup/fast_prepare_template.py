"""Prepared-archive import only; remaining normal-B preparation is unchanged.
Loaded into the qualified worker namespace by the sealed acceleration adapter.
"""
def prepare(folder,names,workspace,recovery=None):
 folder.mkdir(mode=0o700);readers.check()
 plan=_parallel_preparation.payload(folder,names,workspace)
 if plan is None:
  with support.admitted_chunks(logs,readers.check,progress):
   plan=logs.scan(Path(C['source_root']),names);logs.pack(plan,folder/'archive')
 support.write_new(folder/'PLAN_ALL.private.json',plan);support.capture_staging_identities(plan,folder/'archive',folder)
 plan,skipped=positive(plan,folder/'archive');support.write_new(folder/'NONBENEFICIAL.private.json',skipped)
 if not plan['files']:save(folder/'SKIPPED.private.json',dict(all_nonbeneficial=True));return
 planref=support.write_new(folder/'PLAN.private.json',plan);request=support.request_for(plan,planref['path'],folder);progress('batch_packed',dict(folder=folder.name,files=len(plan['files']),bytes=sum(r['raw_bytes']for r in plan['files'])))
 def produce(current):
  def store(name,value):return support.write_new(folder/name,value)
  value=factory.prepare(current,request_path=folder/'B_REQUEST.private.json',request_sha256=sha(folder/'B_REQUEST.private.json'),base_config=normal,retained_map=C['retained_map'],source_folder=C['nightly']['folder'],save=store,maximum_missing_source_bytes=request['total_readback_bytes'],chunk_bytes=1024**2)
  assert value['native_immutable_index_verified'];return value
 if recovery is not None:prepared=produce(recovery)
 else:
  with bridge.pinned_modules(legacy_manifest)as legacy:
   with owned.open_recovery(C['seed_config']['path'],json.loads(read(C['seed_plan'])),legacy=legacy,legacy_sha256=C['nightly']['legacy_factory_sha256'])as recovery:
    prepared=produce(recovery)

 cfg=dict(resource_wait_seconds=600,format='vk-scoped-online-owner-v1',archive_transport='packed-control-graph-v1',operation=uuid.uuid4().hex,plan_sha256=logs.sha(canonical(plan)),reserve_bytes=C['reserve_bytes'],readers=C['readers'],archive=str(folder/'archive'),backup_receipts=str(folder/'graph-recovery'),database=C['database'],workspace_id=workspace,nightly=dict(C['nightly'],selected_config=ref(folder/'CONFIGURATION.private.json')))
 support.write_new(folder/'OWNER.private.json',cfg);save(folder/'PREPARATION_COMPLETE.private.json',dict(files=len(plan['files']),source_bytes_captured=prepared['source_bytes_captured'],exact_current_readers=True));progress('selected_original_backup_index_prepared',dict(folder=folder.name,source_bytes_captured=prepared['source_bytes_captured']))
