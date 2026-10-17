"""Tiny transport tests; no SSH, production reads or scheduling."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from nightly_test_support import fixture_readback
from vk_archive_stream import StreamingArchive
from vk_nightly_capacity import StreamMeter
from vk_nightly_capture_adapter import Resident
from vk_nightly_generation import CHUNKED, MAX_INDEX, NightlyStore


class CapacityTransport(unittest.TestCase):
    def resident(self, budget, *, initial):
        config={'job_timeout_seconds':10,'initial_job_timeout_seconds':20,
                'capture_limit_bytes':32,'initial_capture_limit_bytes':64,
                'transport':'content-delta-v1'}
        ready={'event':'capture_ready','binding':{'fixture':True},
               'baseline':None if initial else {'fixture':True},
               'capture_budget_bytes':budget}
        with patch('vk_nightly_capture_adapter.subprocess.Popen') as popen, \
                patch.object(Resident,'response',return_value=ready):
            process=popen.return_value
            process.stdin=io.BytesIO();process.stdout=io.BytesIO()
            return Resident(config)

    def test_cold_shared_budget_is_bound_below_initial_ceiling(self):
        resident=self.resident(12,initial=True)
        self.assertEqual(resident.config['capture_limit_bytes'],12)
        self.assertEqual(resident.timeout,20);resident.close()

    def test_delta_shared_budget_is_bound_below_routine_ceiling(self):
        resident=self.resident(10,initial=False)
        self.assertEqual(resident.config['capture_limit_bytes'],10)
        self.assertEqual(resident.timeout,10);resident.close()

    def test_missing_boolean_negative_or_expanded_budget_is_rejected(self):
        for budget in (None,True,-1,0,65):
            with self.subTest(budget=budget),self.assertRaises(ValueError):
                self.resident(budget,initial=True)
        with self.assertRaises(ValueError):self.resident(33,initial=False)


class Capacity(unittest.TestCase):
    def test_producer_failure_survives_missing_or_truncated_manifest(self):
        for partial in (b'\0'*10240, b'x'*512):
            with self.subTest(partial=partial[:1]),tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as raw:
                root=Path(raw);meter=StreamMeter(root/'meter');self.addCleanup(meter.db.close)
                error=sqlite3.OperationalError('fixture source backup failed')
                error.nightly_sqlite_diagnostic={'source':'fixture.sqlite','stage':'source.backup(destination)',
                                                'sqlite_errorname':'FIXTURE_ONLY'}
                def produce(out):out.write(partial);raise error
                with self.assertRaises(sqlite3.OperationalError) as caught:
                    meter.measure(StreamingArchive(root,'fixture.tar.zst',produce))
                self.assertIs(caught.exception,error)
                receipt=json.loads((meter.root/'stream-failure.private.json').read_text())
                self.assertEqual(receipt['sqlite_diagnostic'],error.nightly_sqlite_diagnostic)
                self.assertIn('fixture source backup failed',receipt['traceback'])
                self.assertFalse((meter.root/'stream-measurement.private.json').exists())

    def test_parser_failure_is_not_replaced_by_cleanup_broken_pipe(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as raw:
            root=Path(raw);meter=StreamMeter(root/'meter');self.addCleanup(meter.db.close)
            with self.assertRaises(tarfile.ReadError):
                meter.measure(StreamingArchive(root,'fixture.tar.zst',lambda out:out.write(b'x'*512)))
            receipt=json.loads((meter.root/'stream-failure.private.json').read_text())
            self.assertEqual(receipt['error_type'],'ReadError')

    def test_entire_compressed_stream_and_unique_objects_match_actual_store(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as raw:
            root=Path(raw);payload=b'x'*(1024**2)+b'\x00unclosed history tail\xff'
            buffer=io.BytesIO()
            with tarfile.open(fileobj=buffer,mode='w|') as archive:
                def add(key,kind,data=b'',target=''):
                    member=tarfile.TarInfo(key);member.type=kind;member.uid=member.gid=1000
                    member.mode=0o644;member.mtime=1;member.linkname=target;member.size=len(data)
                    archive.addfile(member,io.BytesIO(data) if kind==tarfile.REGTYPE else None)
                add('payload/manifest.json',tarfile.REGTYPE,json.dumps({'sqlite_snapshots':{}}).encode())
                add('scope',tarfile.DIRTYPE)
                add('scope/a',tarfile.REGTYPE,payload);add('scope/b',tarfile.REGTYPE,payload)
                add('scope/link',tarfile.LNKTYPE,target='scope/a')
                add('scope/symlink',tarfile.SYMTYPE,target='/retained/literal')
            tar_bytes=buffer.getvalue();meter=StreamMeter(root/'meter')
            self.addCleanup(meter.db.close)
            source=StreamingArchive(root,'fixture.tar.zst',lambda out:out.write(tar_bytes))
            result=meter.measure(source)
            expected=subprocess.run(['zstd','-T1','-3','-c'],input=tar_bytes,capture_output=True,check=True).stdout
            self.assertEqual(result['compressed_archive_bytes'],len(expected))
            self.assertEqual(result['compressed_archive_sha256'],hashlib.sha256(expected).hexdigest())
            self.assertFalse(result['backup_created']);self.assertIsNone(source.sha256)
            rows={key:json.loads(row) for key,row in meter.db.execute('SELECT name,row FROM entries')}
            store_root=root/'store';store_root.mkdir()
            store=NightlyStore(store_root,'a'*64,lambda:root,object_encoding=CHUNKED,independent_readback=fixture_readback)
            store.enroll_empty()
            def changes():
                for key,row in rows.items():yield key,row,io.BytesIO(payload) if row['kind']=='file' else None
            generation=store.advance(changes(),set(),expected_previous=None,reserve_bytes=MAX_INDEX+1024**2)
            actual=list((store_root/generation['generation']/'objects').iterdir())
            self.assertEqual(result['unique_objects'],len(actual))
            self.assertEqual(result['encoded_object_bytes'],sum(p.stat().st_size for p in actual))
            self.assertEqual(result['cluster_rounded_object_payload_upper_bound'],sum(meter.allocated(p.stat().st_size) for p in actual))
            self.assertEqual(result['regular_files'],2);self.assertEqual(result['hardlinks'],1)
            self.assertEqual(result['full_tree_regular_payload_allocation'],2*meter.allocated(len(payload)))
            self.assertEqual(result['maximum_regular_file_bytes'],len(payload))


if __name__=='__main__':unittest.main()
