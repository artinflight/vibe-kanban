"""Tiny owned fixture regressions; physical B acceptance is separate."""
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import subprocess
import sys
import socket
import unittest
from unittest.mock import patch

from vk_nightly_capture_adapter import RegisteredWorkspace, disk_snapshot, mcp_lease, allowed_sqlite
from vk_nightly_b_job import LocalVerifiedProvider, receive
from vk_nightly_job import inventory, validate_socket_exclusions
from vk_archive_stream import StreamingArchive


class FakeResident:
    def __init__(self,root,limit):
        self.root=root;self.config={'capture_limit_bytes':limit};self.timeout=30
        self.ready={'directory':'B:/vk-backups/vk-isolated-fixture'};self.events=[]
    def call(self,action,*,name,sqlite_integrity=False):
        self.events.append((action,name));path=self.root/name
        if action=='allocate':
            path.touch(exist_ok=False);return {'allocated':name}
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        value={'sealed':name,'sha256':digest,'bytes':path.stat().st_size}
        if sqlite_integrity:
            with sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
                assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
            value['integrity']='ok'
        return value


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(dir='/mnt/vk-storage/vk-restart-safeguards-20261009'))
        self.destination=self.root/'inputs';self.destination.mkdir()
        self.source=self.root/'source.sqlite';self.writer=sqlite3.connect(self.source)
        self.writer.execute('PRAGMA journal_mode=WAL');self.writer.execute('CREATE TABLE retained(value TEXT)')
        self.writer.execute("INSERT INTO retained VALUES('live WAL')");self.writer.commit()
        self.resident=FakeResident(self.destination,2*1024**2)
        with patch.object(RegisteredWorkspace,'checked_root',lambda self,path:self.root):
            self.workspace=RegisteredWorkspace(self.destination,self.resident)
        self.mount_patch=patch.object(self.workspace,'checked_root',lambda path:self.destination);self.mount_patch.start()
    def tearDown(self):self.writer.close();self.mount_patch.stop()  # Keep small owned fixtures.
    def snapshot(self,maximum=1024**2):
        return disk_snapshot(self.source,self.workspace,{str(self.source)},maximum_bytes=maximum,timeout_seconds=30)
    def test_registered_b_disk_backup_includes_wal_without_serialize_or_sidecars(self):
        connect=sqlite3.connect;uris=[]
        def checked(path,*args,**kwargs):
            self.assertNotEqual(str(path),':memory:');uris.append(str(path));return connect(path,*args,**kwargs)
        with patch('sqlite3.connect',checked):result=self.snapshot()
        target=self.destination/result['snapshot']
        with connect(target.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
            self.assertEqual(db.execute('SELECT value FROM retained').fetchall(),[('live WAL',)])
        self.assertEqual({p.name for p in self.destination.iterdir()},{target.name})
        self.assertEqual(self.resident.events,[('allocate',target.name),('seal',target.name)])
        self.assertTrue(any('immutable=1' in path for path in uris))
        self.assertNotIn('immutable=1',uris[0]);self.assertEqual(result['local_snapshot_payload_bytes'],0)
    def test_snapshot_bound_failure_retains_registered_unaccepted_image(self):
        with self.assertRaisesRegex(ValueError,'SQLite image exceeds'):self.snapshot(maximum=1)
        self.assertEqual(len(list(self.destination.iterdir())),1)
        self.assertEqual([event[0] for event in self.resident.events],['allocate'])
    def test_sqlite_failure_preserves_exact_error_and_stage_without_seal_or_retry(self):
        error=sqlite3.OperationalError('attempt to write a readonly database')
        error.sqlite_errorcode=1032;error.sqlite_errorname='SQLITE_READONLY_DBMOVED'
        connect=sqlite3.connect;backups=[]
        class Broken(sqlite3.Connection):
            def backup(self,*args,**kwargs):backups.append(kwargs['pages']);raise error
        def observed(path,*args,**kwargs):return connect(path,*args,factory=Broken,**kwargs)
        with patch('sqlite3.connect',observed),patch.object(self.workspace,'inspect_failure',return_value={'metadata_only':True}) as inspect:
            with self.assertRaises(sqlite3.OperationalError) as caught:self.snapshot()
        self.assertIs(caught.exception,error);self.assertEqual(backups,[1024])
        report=error.nightly_sqlite_diagnostic
        self.assertEqual(report['stage'],'source.backup(destination)')
        self.assertEqual(report['sqlite_errorcode'],1032);self.assertEqual(report['sqlite_errorname'],'SQLITE_READONLY_DBMOVED')
        self.assertEqual(report['source_journal_mode'],'wal');self.assertEqual(report['source_page_size'],4096)
        self.assertEqual(report['source'],str(self.source));self.assertEqual(report['destination_identity']['bytes'],0)
        self.assertIn('OperationalError',report['traceback']);self.assertEqual([x[0] for x in self.resident.events],['allocate'])
        inspect.assert_called_once()
    def test_secondary_metadata_failure_cannot_hide_original_sqlite_error(self):
        error=sqlite3.OperationalError('original failure');connect=sqlite3.connect
        class Broken(sqlite3.Connection):
            def backup(self,*args,**kwargs):raise error
        with patch('sqlite3.connect',lambda *a,**k:connect(*a,factory=Broken,**k)),patch.object(self.workspace,'inspect_failure',side_effect=TimeoutError('secondary')):
            with self.assertRaises(sqlite3.OperationalError) as caught:self.snapshot()
        self.assertIs(caught.exception,error)
        self.assertEqual(error.nightly_sqlite_diagnostic['diagnostic_errors'],[{'operation':'registered_destination','type':'TimeoutError'}])
    def test_successful_snapshot_adds_no_diagnostic_sqlite_queries_or_inspection(self):
        connect=sqlite3.connect;commands=[]
        class Observed(sqlite3.Connection):
            def execute(self,sql,*a,**k):commands.append(sql);return super().execute(sql,*a,**k)
        with patch('sqlite3.connect',lambda *a,**k:connect(*a,factory=Observed,**k)),patch.object(self.workspace,'inspect_failure') as inspect:
            self.snapshot()
        inspect.assert_not_called()
        self.assertNotIn('PRAGMA journal_mode',commands)
        self.assertEqual(commands.count('PRAGMA journal_mode=OFF'),1)
    def test_capacity_reservation_accepts_host_sized_image_without_allocating_payload(self):
        size=4_734_447_616;self.workspace.limit=size+1024
        self.workspace.reserve_file(self.destination/'sqlite-consistent-host.sqlite',size)
        self.workspace.reserve_file(self.destination/'manifest.json',1024)
        with self.assertRaisesRegex(ValueError,'aggregate'):
            self.workspace.reserve_file(self.destination/'archive.tar.zst',1)
        self.assertEqual(sum(self.workspace.reservations.values()),size+1024)
    def test_concurrent_outputs_share_aggregate_limit_before_write(self):
        self.workspace.limit=8
        with self.workspace.open_new(self.destination/'one') as one, self.workspace.open_new(self.destination/'two') as two:
            one.write(b'1234');two.write(b'5678')
            with self.assertRaisesRegex(ValueError,'aggregate'):one.write(b'9')
        self.assertEqual(sum(p.stat().st_size for p in self.destination.iterdir()),8)
    def test_real_compressor_archive_overflow_reports_shared_capacity_and_retains_partial(self):
        self.workspace.limit=96
        sealed=self.destination/'sealed.sqlite'
        with self.workspace.open_new(sealed) as stream:stream.write(b'x'*64)
        self.workspace.seal(sealed)
        source=StreamingArchive(self.destination,'host-sized.tar.zst',
            lambda stream:stream.write(bytes(range(100))))
        with self.assertRaisesRegex(ValueError,
                'archive allowance 32; capture limit 96; sealed input bytes 64'):
            self.workspace.mirror(source)
        self.assertEqual((self.destination/source.name).stat().st_size,0)
        self.assertNotIn(source.name,self.workspace.sealed)
        self.assertIsNone(source.sha256)
        self.assertEqual(sealed.read_bytes(),b'x'*64)
        self.assertEqual(self.resident.events,
            [('allocate',sealed.name),('seal',sealed.name),('allocate',source.name)])
    def test_compact_proof_stream_has_shared_capacity_bound(self):
        value={'proof':{'entries':{('path-%04d'%i):{'bytes':i,'sha256':'a'*64} for i in range(100)}}}
        path=self.destination/'nightly-proof.json'
        sealed=self.workspace.save_proof(path,value)
        self.assertEqual(json.loads(path.read_text()),value)
        self.assertEqual(sealed['bytes'],path.stat().st_size)
        self.assertNotIn('locations',value)
        self.assertNotIn(b'\n',path.read_bytes())
        with patch('vk_nightly_capture_adapter.MAX_INDEX',1):
            with self.assertRaisesRegex(ValueError,'proof metadata'):
                self.workspace.save_proof(self.destination/'oversized-proof.json',value)
        self.assertNotIn('oversized-proof.json',self.workspace.sealed)

    def test_path_and_mount_substitution_rejected_before_allocation(self):
        with self.assertRaisesRegex(ValueError,'DB outside'):
            disk_snapshot(self.source,self.workspace,set(),maximum_bytes=1024**2,timeout_seconds=30)
        self.assertEqual(self.resident.events,[])
        with patch('vk_nightly_capture_adapter.subprocess.check_output',return_value=b'{"filesystems":[{"target":"/other","fstype":"ext4","source":"/dev/sdb1"}]}'):
            with self.assertRaisesRegex(ValueError,'pinned fresh'):
                RegisteredWorkspace(self.destination,self.resident)
    def test_future_database_inside_approved_root_needs_no_inventory_amendment(self):
        future=self.root/'future.sqlite';future.touch()
        self.assertEqual(allowed_sqlite({'sources':[str(self.root)]},str(future)),{str(future)})
        with self.assertRaisesRegex(ValueError,'outside approved'):
            allowed_sqlite({'sources':[str(self.destination)]},str(future))
        with self.assertRaisesRegex(ValueError,'outside approved'):
            allowed_sqlite({'sources':[str(self.root)],'excluded_rebuildable_directories':[str(future)]},str(future))
        alias=self.root/'alias.sqlite';alias.symlink_to(future)
        with self.assertRaisesRegex(ValueError,'outside approved'):
            allowed_sqlite({'sources':[str(self.root)]},str(alias))

    def test_mcp_kernel_lease_rejects_concurrent_producer(self):
        with mcp_lease(self.root/'lease'):
            with self.assertRaises(BlockingIOError):
                with mcp_lease(self.root/'lease'):self.fail('concurrent producer admitted')
    def test_parent_close_does_not_unlock_inherited_producer_lease(self):
        lease=self.root/'lease';child=None
        try:
            with mcp_lease(lease) as fd:
                self.workspace.lease_fd=fd
                child=self.workspace.producer([sys.executable,'-B','-S','-c','import time;time.sleep(30)'])
            # Parent-side context is CLOSED; only the exact child holds it.
            with self.assertRaisesRegex(BlockingIOError,'inherited owned child'):
                with mcp_lease(lease):self.fail('orphaned producer admitted recovery')
            child.kill();child.wait()
            with mcp_lease(lease):pass
        finally:
            if child is not None and child.poll() is None:child.kill();child.wait()
    def test_bounded_protocol_rejects_eof_and_oversized_control(self):
        import struct
        for data,error in [(b'',EOFError),(struct.pack('!I',16385),ValueError)]:
            with self.assertRaises(error):receive(io.BytesIO(data))
    def test_local_provider_rejects_wrong_scope_before_replay(self):
        result={'parent':None,'passed':True,'direct_stream':True,'plan_sha256':'plan','scope_sha256':'source'}
        proof={'fixture_only':False,'full_current_state':True,'scope_sha256':'wrong','capture_id':'one'}
        with self.assertRaisesRegex(ValueError,'pinned live scope'):
            LocalVerifiedProvider(self.destination,{'result':result,'proof':proof,'capture_id':'one'},
                                  {'scope_sha256':'correct','plan_identity':'plan','source_scope_sha256':'source','source_prefix':'/'})
    def test_exact_socket_omission_accepts_only_owned_endpoint_or_absence(self):
        path=self.root/'owned.sock'
        validate_socket_exclusions([str(path)])
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
            listener.bind(str(path));validate_socket_exclusions([str(path)])
        path=self.root/'data';path.write_bytes(b'preserve')
        with self.assertRaisesRegex(ValueError,'changed type/owner'):validate_socket_exclusions([str(path)])
        self.assertEqual(path.read_bytes(),b'preserve')

    def test_socket_omission_rejects_symlink_substitution(self):
        data=self.root/'data';data.write_bytes(b'preserve')
        alias=self.root/'replacement.sock';alias.symlink_to(data)
        with self.assertRaisesRegex(ValueError,'changed type/owner'):validate_socket_exclusions([str(alias)])
        self.assertEqual(data.read_bytes(),b'preserve')

    def test_existing_timeout_stops_owned_job_with_finite_grace(self):
        result=subprocess.run(['/usr/bin/timeout','--signal=TERM','--kill-after=1s','0.1s',sys.executable,
                               '-c','import time;time.sleep(5)'],capture_output=True,timeout=3)
        self.assertEqual(result.returncode,124)

    def test_read_only_inventory_detects_required_db_and_preserves_source_modes(self):
        before=self.source.stat();value=inventory({'sources':[str(self.source)],'sqlite_snapshots':[str(self.source)]})
        self.assertEqual(value['databases'],{str(self.source):before.st_size});self.assertTrue(value['read_only'])
        self.assertEqual(self.source.stat().st_mode,before.st_mode)


if __name__=='__main__':unittest.main()
