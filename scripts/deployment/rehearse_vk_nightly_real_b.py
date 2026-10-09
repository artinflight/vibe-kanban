"""Explicit synthetic real-B acceptance via EXISTING Desktop SSH/WSL access.

No root writes, install, schedule, live backup enrollment or production reads.
All artifacts retained except exact synthetic old generations in retention tests.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time
import uuid

from vk_archive_store import SSH
from vk_candidate_direct_b import DirectBProvider
from vk_change_journal import Journal, scope
from vk_desktop_transport import DesktopTransport
from vk_direct_capture import capture
from vk_prep_common import identity, storage


def desktop(code):
    result = subprocess.run(SSH, input=code, text=True, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError('Existing Desktop SSH operation failed: ' + result.stderr[:2000])
    return json.loads(result.stdout)


def wsl_fixture(config, sources):
    code = ('import hashlib,json,sys,types\nCONFIG=' + repr(config) + '\n'
            'sources=' + repr(sources) + '\n'
            'for filename, source, expected in sources:\n'
            ' assert hashlib.sha256(source.encode()).hexdigest()==expected\n'
            ' if filename=="vk_nightly_generation.py":\n'
            '  module=types.ModuleType("vk_nightly_generation");sys.modules[module.__name__]=module\n'
            '  exec(compile(source,filename,"exec"),module.__dict__)\n'
            ' else:exec(compile(source,filename,"exec"),globals())\n')
    bridge = ('import json,subprocess\ncode=' + repr(code) + '\n'
              "r=subprocess.run(['wsl.exe','-d','VK-Candidate-20261009','--exec','setpriv',"
              "'--reuid','1000','--regid','1000','--clear-groups','python3','-B','-S','-'],"
              'input=code,capture_output=True,text=True,timeout=60)\n'
              "print(json.dumps({'rc':r.returncode,'stdout':r.stdout,'stderr':r.stderr}))\n")
    return desktop(bridge)


def native_recover(remote, case, expected_rows, volume_device):
    # Separate native Windows process reads current and ONLY its own objects.
    code = '''
import ctypes,hashlib,json,os,pathlib,sqlite3
assert os.stat('B:/').st_dev==VOLUME
root=pathlib.Path(ROOT)/CASE
pointer=json.loads((root/'current.json').read_text())
folder=root/pointer['generation'];raw=(folder/'manifest.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()==pointer['manifest_sha256']
m=json.loads(raw);assert m['parent'] is None
assert m['generation']==pointer['generation']
for h in {r['sha256'] for r in m['entries'].values() if r['kind']=='file'}:
 assert hashlib.sha256((folder/'objects'/h).read_bytes()).hexdigest()==h
dbfile=folder/'objects'/m['entries']['home/state/state.sqlite']['sha256']
with sqlite3.connect(dbfile.as_uri()+'?mode=ro',uri=True) as db:
 rows=db.execute('SELECT value FROM retained ORDER BY rowid').fetchall()
 assert [r[0] for r in rows]==ROWS
 assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
unchanged=folder/'objects'/m['entries']['home/state/unchanged']['sha256']
assert unchanged.read_bytes()==b'unchanged fixture content'
assert ('home/state/deleted' in m['entries'])==(ROWS==['before'])
print(json.dumps({'passed':True,'rows':[r[0] for r in rows],'integrity':'ok',
 'current_generation':m['generation'],'first_generation_reads':0,
 'deleted_entry_absent':'home/state/deleted' not in m['entries']}))
'''
    return desktop('ROOT,CASE,ROWS,VOLUME=' + repr((remote, case, expected_rows, volume_device)) + '\n' + code)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-synthetic-fixtures', action='store_true', required=True)
    parser.parse_args()
    started = time.monotonic()
    local = storage('/mnt/vk-storage/vk-restart-safeguards-20261009') / ('real-b-acceptance-' + uuid.uuid4().hex)
    local.mkdir()
    remote = 'B:/vk-backups/vk-nightly-acceptance-20261009-' + uuid.uuid4().hex
    ready = desktop('import json,os,pathlib,shutil\np=pathlib.Path(' + repr(remote) +
                    ");p.mkdir();print(json.dumps({'volume_device':os.stat('B:/').st_dev,'free':shutil.disk_usage('B:/').free}))\n")
    report = {'local': str(local), 'remote': remote, 'ready': ready, 'cases': {},
              'production_changes': False, 'schedule_enabled': False, 'fixture_artifacts_retained': True}
    (local / 'location.safe.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Fresh B fixture:', remote, 'local evidence:', local, flush=True)
    inc = local / 'source'
    state = inc / 'home/state';state.mkdir(parents=True)
    dbpath = state / 'state.sqlite'
    with sqlite3.connect(dbpath) as db:
        db.execute('CREATE TABLE retained(value TEXT)');db.execute("INSERT INTO retained VALUES('before')")
    (state / 'unchanged').write_bytes(b'unchanged fixture content')
    (state / 'deleted').write_bytes(b'owned removable fixture')
    plan = {'sources': [str(inc)], 'sqlite_snapshots': [str(dbpath)], 'excluded_rebuildable_directories': []}
    scoped = identity({'synthetic_test_only': True, 'source_plan': plan})
    provider = DirectBProvider(scoped, ['home/state/state.sqlite'])
    transport = DesktopTransport(local / 'transport')
    journal = Journal(plan);journal.tree(inc);journal.ready = True
    captures = {}
    parent = None
    try:
        for capture_id in ('first', 'second'):
            if capture_id == 'second':
                with sqlite3.connect(dbpath) as db:db.execute("INSERT INTO retained VALUES('second')")
                (state / 'deleted').unlink()  # Only this invocation's synthetic input.
            destination = remote + '/captures/' + capture_id
            result = capture(plan, local / ('capture-' + capture_id), journal.report,
                             lambda archive: transport.mirror(archive, destination), parent,
                             lambda metadata: transport.mirror(metadata, destination), max_snapshot_bytes=64*1024)
            provider.register(capture_id, result, identity(plan), identity(scope(plan)), inc,
                              origin_root_binding='synthetic-fixture-only')
            proof = provider.verify(capture_id)
            payloads = {}
            selected = {key for key,row in proof['entries'].items() if row['kind'] == 'file'}
            with provider.file_members(capture_id, selected) as members:
                for key, stream in members:
                    raw = stream.read(64*1024+1)
                    if len(raw)>64*1024:raise ValueError('synthetic payload bound exceeded')
                    payloads[key] = base64.b64encode(raw).decode()
            captures[capture_id] = {'proof': proof, 'payloads': payloads}
            parent = result
            (local / (capture_id + '-capture.safe.json')).write_text(json.dumps(result, indent=2) + '\n')
            print('Actual B capture/readback verified:', capture_id, flush=True)
    finally:
        journal.close()
    sources = []
    for name in ('vk_nightly_generation.py', 'vk_nightly_b_fixture.py'):
        source = Path(__file__).with_name(name).read_text()
        sources.append((name, source, hashlib.sha256(source.encode()).hexdigest()))
    report['source_sha256'] = {name: checksum for name,_,checksum in sources}
    report['source_head'] = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    report['actual_direct_B_capture_adapter'] = 'vk_direct_capture.capture + DesktopTransport + default DirectBProvider/Archive'
    report['captures'] = {key: {'entries':len(value['proof']['entries']), 'fixture_only':value['proof']['fixture_only'],
                                'manifest_sha256':value['proof']['manifest_sha256']} for key,value in captures.items()}
    failures = []
    for case, expected_exit in [('success',0),('before-publication',73),('after-publication',74),('during-retention',75)]:
        config = {'captures': captures, 'scope': scoped, 'volume_device': ready['volume_device'],
                  'wsl_root': '/mnt/b/' + remote[3:], 'case': case, 'action': 'run'}
        run = wsl_fixture(config, sources)
        item = {'run': run};report['cases'][case] = item
        if run['rc'] != expected_exit:
            failures.append(case + ': unexpected exit ' + str(run['rc']))
        try:
            config['action'] = 'reconcile'
            item['reconciliation'] = wsl_fixture(config, sources)
            assert item['reconciliation']['rc'] == 0, item['reconciliation']['stderr']
            rows = ['before'] if case == 'before-publication' else ['before','second']
            item['independent_native_windows_recovery'] = native_recover(remote, case, rows, ready['volume_device'])
        except Exception as error:
            item['acceptance_blocker'] = str(error);failures.append(case + ': ' + str(error))
        (local / 'acceptance.safe.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Fixture:',case,'exit:',run['rc'],'expected:',expected_exit,flush=True)
    report['failures'] = failures
    report['passed'] = not failures
    report['elapsed_seconds'] = time.monotonic()-started
    footprint = desktop('import json,os,pathlib\np=pathlib.Path('+repr(remote)+
                        ");files=[x for x in p.rglob('*') if x.is_file()];unique={}\n"
                        "for x in files:\n s=x.stat();unique[(s.st_dev,s.st_ino)]=s.st_size\n"
                        "print(json.dumps({'files':len(files),'logical_file_bytes':sum(x.stat().st_size for x in files),'unique_inode_bytes':sum(unique.values())}))\n")
    report['B_footprint'] = footprint
    report['SSD_footprint'] = subprocess.check_output(['du','-s','-B1',str(local)],text=True).strip()
    report['limits'] = 'Injected process exits, not host power-loss proof. WSL/NTFS operations and native readback measured; real scheduled capture/adoption and interruption reconciliation automation remain separate.'
    receipt = local / 'acceptance.safe.json';receipt.write_text(json.dumps(report,indent=2)+'\n')
    print('Receipt:',receipt,'SHA256:',hashlib.sha256(receipt.read_bytes()).hexdigest(),flush=True)
    print(json.dumps({'passed':report['passed'],'failures':failures,'B_footprint':footprint,'SSD_footprint':report['SSD_footprint']},indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
