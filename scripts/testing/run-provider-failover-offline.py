#!/usr/bin/env python3
"""Compile ONLY the dormant failover module using existing cached dependencies.
No Cargo build/download, provider call or production path. Output on mounted SSD.
"""
import argparse, hashlib, json, os, pathlib, subprocess
p=argparse.ArgumentParser()
p.add_argument('--output',type=pathlib.Path,required=True)
p.add_argument('--deps',type=pathlib.Path,default=pathlib.Path('/mnt/vk-storage/cargo-target/debug/deps'))
a=p.parse_args()
subprocess.run(['mountpoint','-q','/mnt/vk-storage'],check=True)
if not a.output.resolve().is_relative_to('/mnt/vk-storage'):raise SystemExit('Output must be on mounted SSD')
a.output.mkdir(parents=True,exist_ok=True)
root=pathlib.Path(__file__).resolve().parents[2]
# Match serde_core metadata, not an arbitrary pair of cached dependency versions.
fingerprints=a.deps.parent/'.fingerprint'
def variants(name):
    for meta in sorted(fingerprints.glob(name+'*/lib-'+name+'.json')):
        lib=a.deps/('lib'+meta.parent.name+'.rlib')
        if not lib.exists():continue
        data=json.loads(meta.read_text())
        core=[v[-1] for v in data['deps'] if v[1]=='serde_core']
        if len(core)==1:yield lib,core[0],data['rustc']
pair=next(((s,j) for s,c,r in variants('serde') for j,d,t in variants('serde_json') if c==d and r==t),None)
if pair is None:raise SystemExit('No compatible cached serde pair; do not start a broad build')
worker=a.output/'provider-failover-tests'
command=['rustc','--edition=2024','--test',str(root/'crates/executors/src/provider_failover/mod.rs'),'-C','debuginfo=0','-L','dependency='+str(a.deps),'--extern','serde='+str(pair[0]),'--extern','serde_json='+str(pair[1]),'-o',str(worker)]
env=dict(os.environ,TMPDIR=str(a.output),CARGO_INCREMENTAL='0')
with (a.output/'compile.log').open('w') as log:
    subprocess.run(['/usr/bin/time','-v',*command],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
with (a.output/'tests.log').open('w') as log:
    subprocess.run(['/usr/bin/time','-v',str(worker),'--test-threads=1','--nocapture'],env=dict(env,VK_FAILOVER_TEST_ROOT=str(a.output)),stdout=log,stderr=subprocess.STDOUT,check=True)
files=[root/'crates/executors/src/provider_failover/mod.rs',root/'crates/executors/src/provider_failover/tests.rs',*pair,worker]
receipt={'syntheticOnly':True,'paidCalls':0,'cargoBuild':False,'commands':[command,[str(worker),'--test-threads=1','--nocapture']],'sha256':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},'rustc':subprocess.check_output(['rustc','--version'],text=True).strip()}
(a.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print((a.output/'tests.log').read_text())
