"""Source-only pinned user-job artifact; never enroll, install or schedule."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from vk_candidate_direct_b import source_pins
from vk_nightly_generation import MAX_INDEX
from vk_nightly_job import checksum, validate_socket_exclusions
from vk_prep_common import identity, storage


def build(inventory_path,output):
    base=Path(__file__).parent;output=storage(output);output.mkdir(exist_ok=False)
    inventory=json.loads(Path(inventory_path).read_text())
    plan_path=Path('/mnt/vk-storage/vk-runtime-backup-20261009/backup-plan.json')
    plan=json.loads(plan_path.read_text());historical_sha256=checksum(plan_path)
    if inventory['plan_identity']!=identity(plan):raise ValueError('inventory/plan binding changed')
    for raw,row in inventory['roots'].items():
        info=Path(raw).lstat()
        if [info.st_dev,info.st_ino]!=[row['device'],row['inode']]:raise ValueError('root changed since census')
        row['resolved_target']=str(Path(raw).resolve())
    # Scope-only proposal: never edit the historical Staging plan or endpoint.
    # GNU tar cannot restore this process-owned socket. Existing Exclusions
    # accepts exact paths; the runtime type/owner guard prevents data omission
    # if an ordinary file/symlink is substituted at this reviewed name.
    sockets=['/home/mcp/.codex/app-server-daemon/daemon-updater.sock']
    validate_socket_exclusions(sockets)
    plan={**plan,'excluded_rebuildable_directories':[*plan.get('excluded_rebuildable_directories',[]),*sockets],
          'nightly_exact_socket_omission_proposal':sockets}
    plan_path=output/'nightly-source-plan.proposed.private.json'
    plan_path.write_text(json.dumps(plan,indent=2,sort_keys=True)+'\n');os.chmod(plan_path,0o600)
    from vk_change_journal import scope
    from vk_rolling_backup import Exclusions
    modules=set();queue=['vk_nightly_job','vk_nightly_b_job','vk_nightly_lifecycle','vk_nightly_generation']
    while queue:
        module=queue.pop();file=base/(module+'.py')
        if module in modules or not file.exists():continue
        modules.add(module)
        for node in ast.walk(ast.parse(file.read_text())):
            names=[node.module] if isinstance(node,ast.ImportFrom) else [x.name for x in node.names] if isinstance(node,ast.Import) else []
            queue.extend(x for x in names if x and (base/(x+'.py')).exists())
    reviewed=source_pins()
    names={name+'.py' for name in modules}|{Path(raw).name for raw in reviewed}
    for name in sorted(names):shutil.copyfile(base/name,output/name)
    (output/'receipts').mkdir();shutil.copyfile(base/'receipts/direct-stream-20261008.json',output/'receipts/direct-stream-20261008.json')
    pins={name:checksum(output/name) for name in sorted(names)}
    GiB=1024**3;capture=20*GiB;initial=96*GiB;changed=8*GiB;floor=2*GiB
    config={'adoption_authorized':False,'retention_adopted':False,'schedule_enabled':False,
      'plan_path':str(plan_path),'plan_file_sha256':checksum(plan_path),'plan_identity':identity(plan),
      'source_scope_sha256':identity(scope(plan)),
      'historical_plan_sha256':historical_sha256,'socket_exclusions':sockets,
      'scope_sha256':identity({'producer':'vk-normal-nightly-v1','source_plan':identity(plan),'source_scope':identity(scope(plan))}),
      'source_prefix':'/','source_roots':inventory['roots'],'exclusion_targets':[str(p) for p in Exclusions(plan).roots],
      'inventoried_databases':sorted(inventory['databases']),'volume_device':2360624474,
      'wsl_root':'/mnt/b/vk-backups/vk-normal-nightly-v1','staging':'/mnt/vk-storage/vk-normal-nightly-control-v1',
      'sshfs_binary':'/mnt/vk-storage/vk-runtime-backup-20261009/sshfs-tool/usr/bin/sshfs','fusermount_binary':'/usr/bin/fusermount',
      'capture_limit_bytes':capture,'initial_changed_limit_bytes':initial,'changed_limit_bytes':changed,
      'snapshot_limit_bytes':6*GiB,'initial_reserve_bytes':capture+initial+MAX_INDEX+floor,
      'reserve_bytes':capture+changed+MAX_INDEX+floor,'preserved_B_floor_bytes':floor,
      'snapshot_timeout_seconds':1800,'readback_timeout_seconds':3600,'job_timeout_seconds':7200,
      'source_sha256':pins,'binary_sha256':{raw:checksum(raw) for raw in
        ('/usr/bin/python3','/usr/bin/zstd','/usr/bin/tar','/usr/bin/ssh','/usr/bin/fusermount','/usr/bin/findmnt',
         '/usr/bin/timeout','/usr/bin/logger','/usr/bin/crontab',
         '/mnt/vk-storage/vk-runtime-backup-20261009/sshfs-tool/usr/bin/sshfs')},
      'measurement':{'inventory_files':inventory['files'],'inventory_paths':inventory['paths'],
        'logical_source_bytes':inventory['logical_file_bytes'],'sqlite_total_bytes':sum(inventory['databases'].values()),
        'maximum_sqlite_bytes':inventory['maximum_DB_bytes'],'inventory_seconds':inventory['elapsed_seconds'],
        'full_production_transfer_and_runtime_accepted':False,
        'limits_basis':'read-only current census plus finite headroom; tiny fixtures do not predict whole-host throughput'}}
    path=output/'nightly-production.disabled.private.json'
    path.write_text(json.dumps(config,indent=2)+'\n');os.chmod(path,0o600)
    command='/usr/bin/timeout --verbose --signal=TERM --kill-after=30s 7200s /usr/bin/python3 -B -S '+str(output/'vk_nightly_job.py')
    def entry(path):
        return '0 2 * * * '+command+' --config '+str(path)+' --config-sha256 '+checksum(path)+' 2>&1 | /usr/bin/logger -t vk-normal-nightly-v1\n'
    (output/'cron.disabled').write_text('# PROPOSAL ONLY; not installed. Existing host cron timezone verified Etc/UTC.\n# '+entry(path))
    # This immutable proposal is NOT operational authorization. It exists so a
    # single final approval can name exact bytes without post-approval editing.
    proposed=output/'nightly-production.proposed-adoption.private.json'
    proposed.write_text(json.dumps({**config,'adoption_authorized':True,'retention_adopted':True},indent=2)+'\n');os.chmod(proposed,0o600)
    (output/'cron.proposed').write_text('# Source-only approval proposal. Enable ONLY after full-plan recovery test receipt.\n'+entry(proposed))
    validation=subprocess.run(['/usr/bin/crontab','-n',str(output/'cron.proposed')],capture_output=True,text=True)
    if validation.returncode:raise ValueError('cron syntax rejected: '+validation.stderr)
    report={'source_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
      'source_sha256':pins,'disabled_config_sha256':checksum(path),'proposed_adoption_config_sha256':checksum(proposed),
      'cron_proposed_sha256':checksum(output/'cron.proposed'),'cron_syntax_validated':True,'schedule_installed':False,
      'production_backup_touched':False,'new_privileges':False,'files_sha256':{str(p.relative_to(output)):checksum(p) for p in output.rglob('*') if p.is_file()},
      'exact_scope_amendment':sockets,'historical_plan_changed':False,
      'adoption_action':'Review exact source/config and exact guarded socket omission; explicitly authorize fresh normal scope enrollment/retention and test-run. Only after full-plan recovery/capacity/runtime acceptance, add only proposed cron row preserving existing disabled entries. No owner commands needed.'}
    receipt=output/'package.safe.json';receipt.write_text(json.dumps(report,indent=2)+'\n')
    return {'output':str(output),'package_receipt_sha256':checksum(receipt),**{k:report[k] for k in ('disabled_config_sha256','proposed_adoption_config_sha256','cron_proposed_sha256')}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inventory',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(build(args.inventory,args.output),indent=2))
