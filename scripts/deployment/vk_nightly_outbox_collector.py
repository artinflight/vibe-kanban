"""One guarded delivery of source events to B, then exact-generation ACK.

No source crawl, backup body, backend restart or scheduler installation. The
independent source observer survives this collector's Desktop/access failure.
Only the pinned normal consumer may acknowledge its issued same-owner report.
"""
import json
from pathlib import Path

from vk_nightly_b_controls import tracking_store
from vk_nightly_desktop_controls import DesktopControls
from vk_nightly_outbox_export import export,verify_delivery
from vk_nightly_tracking import request,query


def copy_once(config,*,guard):
    guard();path=Path(config['source_health'])
    with path.open('rb') as stream:raw=stream.read(65537)
    if len(raw)>65536:raise ValueError('bounded source owner status required')
    health=json.loads(raw);instance=health['instance']
    actual=int(Path('/proc/'+str(health['owner_pid'])+'/stat').read_text().rsplit(')',1)[1].split()[19])
    if actual!=health['owner_start_ticks']:raise ValueError('source observer owner changed')
    target=config['B_delivery_target']
    if target['B_root']!=config['controls']['B_root']:raise ValueError('delivery/normal provider roots differ')
    with DesktopControls(config['controls'],guard=guard) as remote:
        with tracking_store(remote.client,target['index_name'],target['checkpoint_sha256'],
                            maximum_bytes=config['maximum_B_index_bytes']) as store:
            row=store.db.execute('select cursor from epochs where instance=?',(instance,)).fetchone()
            since=row[0] if row else 0
            report=request(config['endpoint'],instance,since,barrier=True,for_delivery=True)
            proof=export(health,report,store,guard=guard)
        # FULL commit alone is insufficient: close the native writer and use
        # the normal independent readonly provider before releasing any events.
        db=remote.client.connect(target['index_name'],target['checkpoint_sha256'],readonly=True,working=True)
        try:
            actual=verify_delivery(db,proof)
            if actual!={k:v for k,v in report.items() if k!='delivery'}:
                raise ValueError('normal B reader differs from issued source report')
        finally:db.close()
        acknowledgement=dict(target,**report['delivery'],actual_native_B_reopen_verified=True)
        guard();result=query(config['endpoint'],dict(instance=instance,op='acknowledge_delivery',proof=acknowledgement))
        if result['acknowledged']!=proof['sequence']:raise ValueError('source delivery acknowledgement differs')
    return dict(proof,actual_native_B_reopen_verified=True,local_acknowledged=result['acknowledged'],
                newer_source_generations_preserved=True,whole_baseline_accepted=False)
