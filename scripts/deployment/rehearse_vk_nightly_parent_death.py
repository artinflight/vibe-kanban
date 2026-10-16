"""Parent-only SIGKILL regression; ONLY caller-owned real-B fixture resources."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from unittest.mock import patch

from vk_nightly_capture_adapter import mcp_lease, run_capture


def process_identity(pid):
    folder=Path('/proc')/str(pid)
    fields=(folder/'stat').read_text().rpartition(')')[2].split()
    return {'pid':pid,'start_ticks':int(fields[19]),'uid':folder.stat().st_uid,'state':fields[0]}


def exact_resource(row):
    try:current=process_identity(row['pid'])
    except FileNotFoundError:return False
    if any(current[key]!=row[key] for key in ('pid','start_ticks','uid')):
        raise AssertionError('fixture resource identity changed; do not signal')
    if current['state']=='Z':return False  # No further signal; final flock proves release.
    try:info=(Path('/proc')/str(row['pid'])/'fd'/str(row['lease_fd'])).stat()
    except FileNotFoundError:return False  # Exited/zombie has no lease or writer.
    if [info.st_dev,info.st_ino]!=row['lease_identity']:
        raise AssertionError('fixture inherited lease descriptor changed')
    if hashlib.sha256((Path('/proc')/str(row['pid'])/'exe').read_bytes()).hexdigest()!=row['executable_sha256']:
        raise AssertionError('fixture executable changed; do not signal')
    return True


def await_closed(row):
    deadline=time.monotonic()+30
    while exact_resource(row):
        if time.monotonic()>deadline:raise AssertionError('owned fixture resource did not finish')
        time.sleep(.05)


def stop_fixture(resources):
    # Test-only cleanup, never discover processes by name or signal a group.
    for role in ('tar','zstd'):
        row=resources['owned'][role]
        if exact_resource(row):os.kill(row['pid'],signal.SIGKILL)
        await_closed(row)
    row=resources['owned']['sshfs']
    if exact_resource(row):
        mounted=json.loads(subprocess.check_output(['findmnt','-J','-T',resources['mount']]))['filesystems'][0]
        if mounted['target']!=resources['mount'] or mounted['source']!=resources['mount_source']:
            raise AssertionError('fixture mount changed; do not unmount')
        os.kill(row['pid'],signal.SIGCONT)
        subprocess.run(['/usr/bin/fusermount','-u',resources['mount']],check=True,timeout=30)
        await_closed(row)


def worker(path):
    value=json.loads(path.read_text());config=value['config'];plan=value['plan']
    fixture=path.parent
    if (not fixture.is_relative_to('/mnt/vk-storage/vk-restart-safeguards-20261009')
            or fixture.resolve()!=fixture
            or not fixture.name.startswith('B-lifecycle-')
            or not config['wsl_root'].startswith('/mnt/b/vk-backups/vk-nightly-lifecycle-')
            or '..' in Path(config['wsl_root']).parts
            or config['staging']!=str(fixture/'control')
            or plan['sources']!=[str(fixture/'source')]):
        raise ValueError('parent-death worker requires exact isolated fixture scope')
    popen=subprocess.Popen;owned={}
    def tracked(command,*args,**kwargs):
        role=Path(command[0]).name
        # GNU tar emits at least a 10KiB record. A 4KiB fixture pipe keeps the
        # real child alive until its caller returns and starts draining it.
        if role=='tar' and kwargs.get('pass_fds'):kwargs['pipesize']=4096
        process=popen(command,*args,**kwargs)
        if role in ('sshfs','zstd','tar') and kwargs.get('pass_fds'):
            try:
                fd,=kwargs['pass_fds'];info=(Path('/proc')/str(process.pid)/'fd'/str(fd)).stat()
                owned[role]={**process_identity(process.pid),'lease_fd':fd,'lease_identity':[info.st_dev,info.st_ino],
                             'executable_sha256':hashlib.sha256((Path('/proc')/str(process.pid)/'exe').read_bytes()).hexdigest()}
            except BaseException:
                if process.poll() is None:process.kill()
                process.wait();raise
        if role=='tar' and kwargs.get('pass_fds'):
            if set(owned)!={'sshfs','zstd','tar'}:raise AssertionError('owned producer inventory incomplete')
            mount=str(Path(command[-1]).parent)
            mounted=json.loads(subprocess.check_output(['findmnt','-J','-T',mount]))['filesystems'][0]
            resources={'parent':process_identity(os.getpid()),'owned':owned,'mount':mount,'mount_source':mounted['source']}
            with (fixture/'parent-death.resources.safe.json').open('x') as stream:
                json.dump(resources,stream,indent=2);stream.flush();os.fsync(stream.fileno())
            # Hold actual producers ACTIVE before they can finish this tiny
            # archive. Only the parent is subsequently killed by the harness.
            for row in owned.values():os.kill(row['pid'],signal.SIGSTOP)
            os.kill(os.getpid(),signal.SIGSTOP)
        return process
    with patch('subprocess.Popen',tracked):run_capture(config,plan)
    raise AssertionError('parent-death barrier not reached')


def parent_death_case(config,plan,local):
    started=time.monotonic();control=local/'parent-death.control.private.json'
    with control.open('x') as stream:json.dump({'config':config,'plan':plan},stream)
    os.chmod(control,0o600)
    log=(local/'parent-death.worker.log').open('xb');resources=None
    process=subprocess.Popen([sys.executable,'-B','-S',__file__,'--fixture-worker',str(control)],stdout=log,stderr=log)
    try:
        deadline=time.monotonic()+60;path=local/'parent-death.resources.safe.json'
        while not path.exists() or process_identity(process.pid)['state']!='T':
            if process.poll() is not None:raise AssertionError('fixture worker failed; retain worker log')
            if time.monotonic()>deadline:raise AssertionError('active producer barrier timed out')
            time.sleep(.05)
        resources=json.loads(path.read_text())
        if resources['parent']['pid']!=process.pid:raise AssertionError('wrong fixture parent')
        lease=Path(config['staging'])/'producer.lock';info=lease.stat()
        for row in resources['owned'].values():
            if row['lease_identity']!=[info.st_dev,info.st_ino] or not exact_resource(row):
                raise AssertionError('actual pinned child does not hold exact inherited lease')
        os.kill(process.pid,signal.SIGKILL)
        # Let outstanding FUSE syscalls finish so all killed Python threads
        # actually exit. Keep tar/zstd stopped and the foreground mount alive;
        # otherwise a dead leader with blocked threads would still hold its FD.
        os.kill(resources['owned']['sshfs']['pid'],signal.SIGCONT)
        process.wait(timeout=30)
        if process.returncode!=-signal.SIGKILL:raise AssertionError('parent-only SIGKILL not exercised')
        # Retry the REAL entry point: acquisition must fail before any resident
        # exists or any B recovery attestation/mutation can be issued.
        with patch('vk_nightly_capture_adapter.Resident',side_effect=AssertionError('recovery launched despite active orphan')):
            try:run_capture(config,plan)
            except BlockingIOError as error:deferral=str(error)
            else:raise AssertionError('active orphan allowed recovery')
        for row in resources['owned'].values():
            if not exact_resource(row):raise AssertionError('test did not retain actual orphaned producer')
        def blocked():
            try:
                with mcp_lease(lease):raise AssertionError('active child allowed lease acquisition')
            except BlockingIOError:pass
        blocked()
        # Separately prove zstd and the foreground mount keep the same lease
        # after the tar holder exits; never kill an unrelated process.
        for role in ('tar','zstd'):
            row=resources['owned'][role];os.kill(row['pid'],signal.SIGKILL);await_closed(row);blocked()
        stop_fixture(resources)
        with mcp_lease(lease):pass
        retry=run_capture(config,plan)
        if not retry['result']['passed']:raise AssertionError('closed-orphan retry failed')
        return {'passed':True,'parent_only_exit':process.returncode,'retry_deferred_before_resident':True,
                'deferral':deferral,'resources':resources,'each_remaining_holder_blocks':True,
                'exact_fixture_resources_closed':True,'retry':retry,'elapsed_seconds':time.monotonic()-started}
    finally:
        if process.poll() is None:process.kill();process.wait()
        if resources is None:
            path=local/'parent-death.resources.safe.json'
            if path.exists():resources=json.loads(path.read_text())
        if resources is not None:stop_fixture(resources)
        log.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fixture-worker',type=Path,required=True)
    worker(parser.parse_args().fixture_worker)
