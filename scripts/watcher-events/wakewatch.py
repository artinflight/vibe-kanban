#!/usr/bin/env python3
"""WakeWatch status, read-only readiness, and one bounded connector delivery test."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import time
import uuid
import monitor
import connector_adapter as adapter

CONFIG=Path('/mnt/vk-storage/t26-disk-space-watcher/config.json')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['status','check','queue-test'])
    args=parser.parse_args()
    config=monitor.read_config(CONFIG)
    state=Path(config['state_file']);probe_path=state.parent/'connector-probe.json'
    if args.action=='status':
        latest=json.loads((state.parent/'latest.json').read_text())
        result={'transport':config.get('dispatch_transport','storage-admission-v2'),
                'enabled':monitor.transport_enabled(config),'native_route_enabled':config.get('native_transport',{}).get('enabled') is True,
                'last_observation':{k:latest.get(k) for k in ('at','status','pending_incidents','dispatch_transport','wake_dispatch_enabled')},
                'runbook':'/home/mcp/code/Operations/docs/wakewatch-access.md'}
        if probe_path.exists():
            probe=json.loads(probe_path.read_text());result['delivery_test']={k:probe.get(k) for k in ('state','expected_reply','expires_at')}
            result['delivery_test']['execution_id']=probe.get('outcome',{}).get('execution_id')
        print(json.dumps(result,indent=2));return
    bridge=adapter.ConnectorBridge(config)
    if args.action=='check':
        print(json.dumps({'ready_now':bridge.ready(),'transport':adapter.TRANSPORT,'mutated':False}));return
    # Explicit user invocation queues exactly one bounded probe. It does not
    # start a second agent, interrupt current work, or submit a prompt now.
    with state.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if probe_path.exists():
            print(json.dumps({'status':'already_exists','state':json.loads(probe_path.read_text())['state']}));return
        bid,aid=str(uuid.uuid4()),str(uuid.uuid4());marker='WAKEWATCH_READY_'+bid[:8]
        prompt=('[storage-response '+bid+'] The operator authorized a one-time WakeWatch delivery test using the existing printer-style connector. '
                'This is not a disk-pressure incident and does not request cleanup. Reply with exactly '+marker+'. '
                'Do not run commands, change files, create agents/goals, schedule follow-ups, or perform cleanup. Then stop.')
        intent={**bridge.binding(),'prompt':prompt,'incidents':[]}
        doc={'batch_id':bid,'attempt_id':aid,'intent':intent,'intent_sha256':adapter.codec.digest(intent),
             'validation':{'observed_at':adapter.codec.utc(time.time())},'known_attempt_ids':[aid]}
        adapter.save_private(probe_path,{'state':'pending','created_at':time.time(),'expires_at':time.time()+3600,
                                         'expected_reply':marker,'document':doc})
        print(json.dumps({'status':'pending_until_existing_owner_idle','maximum_model_turns':1,'expected_reply':marker}))

if __name__=='__main__':
    try:main()
    except Exception:
        print(json.dumps({'status':'held','reason':'configuration_or_owner_inventory_unavailable'}))
        raise SystemExit(1)
