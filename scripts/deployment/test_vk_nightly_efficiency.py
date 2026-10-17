"""Exact-byte chunk recovery and restart reuse on tiny isolated SSD fixtures."""
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import tempfile
import unittest
from unittest.mock import patch

from nightly_test_support import fixture_readback
from vk_nightly_generation import (CHUNKED, CHUNK_BYTES, NightlyStore,
                                   chunk_layout, object_blocks)
from vk_nightly_b_job import WINDOWS_READBACK
import test_vk_nightly_restart_baseline as baseline_tests
import test_vk_nightly_lifecycle as lifecycle_tests


class ChunkedHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = NightlyStore(self.root, 'a'*64, lambda: self.root.parent,
                                 independent_readback=fixture_readback, object_encoding=CHUNKED)
        self.store.enroll_empty()

    def row(self, data):
        return {'kind': 'file', 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}

    def advance(self, files, previous=None, reserve=8*1024**2):
        return self.store.advance([(k, self.row(v), io.BytesIO(v)) for k, v in files.items()], (),
                                  expected_previous=previous, reserve_bytes=reserve, retention_adopted=True)

    def recover(self, key):
        manifest = self.store.current();row = manifest['entries'][key]
        return b''.join(object_blocks(self.root/manifest['generation']/'objects'/row['sha256'],
                                     row['sha256'], row['bytes'], CHUNKED))

    def test_append_reuses_prefix_and_new_current_restores_without_old_generation(self):
        # Incompressible prefixes make stored-byte measurements meaningful.
        data = os.urandom(2*CHUNK_BYTES) + b'partial\xff\x00\n{"unfinished":'
        first = self.advance({'native/history.jsonl': data, 'process/duplicate.jsonl': data})
        old = self.store.current();objects = self.root/old['generation']/'objects'
        refs = chunk_layout(objects/self.row(data)['sha256'], self.row(data)['sha256'], len(data))
        prefix_inode = (objects/('chunk-'+refs[0]['sha256'])).stat().st_ino
        latest = data+b'"exact escaping \\n and duplicate records"}\n'*7
        second = self.advance({'native/history.jsonl': latest}, first['generation'])
        self.assertLess(second['stored_changed_bytes'], 8192)
        self.assertFalse((self.root/first['generation']).exists())
        self.assertEqual(self.recover('native/history.jsonl'), latest)
        self.assertEqual(self.recover('process/duplicate.jsonl'), data)
        current = self.store.current()
        self.assertEqual((self.root/current['generation']/'objects'/('chunk-'+refs[0]['sha256'])).stat().st_ino, prefix_inode)
        self.assertIsNone(current['parent'])
        self.store.verify(current)

    def test_corrupt_missing_and_trailing_chunks_fail_recovery(self):
        data = b'original records\n'*100
        self.advance({'history': data})
        manifest = self.store.current();objects = self.root/manifest['generation']/'objects'
        refs = chunk_layout(objects/self.row(data)['sha256'], self.row(data)['sha256'], len(data))
        path = objects/('chunk-'+refs[0]['sha256']);original = path.read_bytes()
        for bad in (b'corrupt', original[:-1], original+b'trailing'):
            path.write_bytes(bad)
            with self.assertRaises((ValueError, __import__('zlib').error)):
                self.recover('history')
        path.unlink()
        with self.assertRaises(FileNotFoundError):self.recover('history')

    def test_layout_full_hash_order_and_bounds_are_verified(self):
        data = os.urandom(CHUNK_BYTES)+os.urandom(CHUNK_BYTES)
        self.advance({'history': data})
        m = self.store.current();p = self.root/m['generation']/'objects'/self.row(data)['sha256']
        layout = json.loads(p.read_bytes());layout['chunks'].reverse();p.write_text(json.dumps(layout))
        with self.assertRaisesRegex(ValueError, 'full-file checksum'):self.recover('history')
        layout['chunks'][0]['bytes'] = CHUNK_BYTES+1;p.write_text(json.dumps(layout))
        with self.assertRaisesRegex(ValueError, 'chunk reference'):self.recover('history')

    def test_failed_capacity_does_not_advance_current_or_remove_originals(self):
        first = self.advance({'history': b'original'})
        pointer = (self.root/'current.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'reservation'):
            self.advance({'history': os.urandom(CHUNK_BYTES)}, first['generation'], reserve=1)
        self.assertEqual((self.root/'current.json').read_bytes(), pointer)
        self.assertEqual(self.recover('history'), b'original')
        with self.assertRaisesRegex(ValueError, 'overlap needs reconciliation'):
            self.advance({'history': b'another attempt'}, first['generation'])

    def test_empty_file_and_short_read_stream(self):
        class ShortReads(io.BytesIO):
            def read(self, size=-1):return super().read(min(size, 71))
        data = b'raw\x00\xffunfinished'*1000
        self.store.advance([('empty', self.row(b''), io.BytesIO()), ('history', self.row(data), ShortReads(data))], (),
                           expected_previous=None, reserve_bytes=1024**2)
        self.assertEqual(self.recover('empty'), b'')
        self.assertEqual(self.recover('history'), data)

    def test_native_readback_program_decodes_same_complete_chunk_closure(self):
        data = os.urandom(CHUNK_BYTES)+b'incomplete final record\xff'
        self.advance({'history': data})
        manifest = self.store.current();folder = self.root/manifest['generation']
        request = {'folder': str(folder), 'manifest_sha256': hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest(),
                   'volume_device': self.root.stat().st_dev, 'scope': self.store.scope,
                   'databases': [], 'source_prefix': '/'}
        # Exercise the EXACT native verifier source on a Linux fixture. Only
        # the Windows drive observation is redirected; no real B claim.
        code = WINDOWS_READBACK.replace("os.stat('B:/')", 'os.stat('+repr(str(self.root))+')')
        completed = subprocess.run([sys.executable, '-B', '-c', code], input=json.dumps(request),
                                   text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['manifest_sha256'], request['manifest_sha256'])
        chunk = next((folder/'objects').glob('chunk-*'));chunk.write_bytes(b'corrupt')
        failed = subprocess.run([sys.executable, '-B', '-c', code], input=json.dumps(request),
                                text=True, capture_output=True)
        self.assertNotEqual(failed.returncode, 0)


class ChunkedBaseline(baseline_tests.BaselineTests):
    def setUp(self):
        super().setUp()
        self.store.object_encoding = CHUNKED


class ChunkedLifecycle(lifecycle_tests.NightlyLifecycle):
    def setUp(self):
        super().setUp()
        self.store_job.object_encoding = CHUNKED

    def latest_rows(self):
        m = self.store_job.current();self.store_job.verify(m)
        row = m['entries']['home/state/state.sqlite']
        data = b''.join(object_blocks(self.nightly/m['generation']/'objects'/row['sha256'], row['sha256'], row['bytes'], CHUNKED))
        with sqlite3.connect(':memory:') as db:
            db.deserialize(data)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone(), ('ok',))
            return db.execute('SELECT value FROM retained ORDER BY rowid').fetchall()

    def interrupt_chunk(self, *, die=False):
        link = os.link
        def after_link(source, target, **kwargs):
            link(source, target, **kwargs)
            if Path(target).name.startswith('chunk-'):
                if die:os._exit(77)
                raise OSError('owned producer interrupted after sealed chunk')
        with patch('vk_nightly_generation.os.link', after_link):
            return self.run_nightly()

    def test_guard_abort_before_manifest_reconciles_exact_chunks_and_retries(self):
        self.assertTrue(self.run_nightly()['passed']);self.change()
        before = (self.nightly/'current.json').read_bytes()
        failed = self.interrupt_chunk()
        self.assertFalse(failed['passed'])
        candidate = self.nightly/self.job.read()['candidate']
        self.assertFalse((candidate/'manifest.json').exists())
        self.assertTrue(list((candidate/'objects').glob('chunk-*')))
        self.assertEqual((self.nightly/'current.json').read_bytes(), before)
        self.job.reconcile(retention_adopted=True, inputs_quiescent=True)
        self.assertFalse(candidate.exists())
        self.assertEqual(self.latest_rows(), [('before',)])
        self.assertTrue(self.run_nightly()['passed'])
        self.assertEqual(self.latest_rows(), [('before',), ('second',)])

    def test_parent_death_during_unsealed_chunk_candidate_recovers(self):
        self.assertTrue(self.run_nightly()['passed']);self.change()
        child = os.fork()
        if child == 0:
            self.interrupt_chunk(die=True);os._exit(90)
        deadline = time.monotonic()+15
        pid = 0
        try:
            while not pid and time.monotonic() < deadline:
                pid, status = os.waitpid(child, os.WNOHANG)
                if not pid:time.sleep(.05)
            self.assertTrue(pid, 'owned fixture child exceeded deadline')
            self.assertEqual(os.waitstatus_to_exitcode(status), 77)
        finally:
            if not pid:os.kill(child, 9);os.waitpid(child, 0)
        self.job.reconcile(retention_adopted=True, inputs_quiescent=True)
        self.assertTrue(self.run_nightly()['passed'])
        self.assertEqual(self.latest_rows(), [('before',), ('second',)])

    def test_changed_sealed_chunk_is_preserved_on_reconciliation(self):
        self.assertTrue(self.run_nightly()['passed']);self.change()
        self.interrupt_chunk()
        candidate = self.nightly/self.job.read()['candidate']
        chunk = next((candidate/'objects').glob('chunk-*'))
        chunk.write_bytes(b'unknown substituted evidence')
        with self.assertRaisesRegex(ValueError, 'substituted'):
            self.job.reconcile(retention_adopted=True, inputs_quiescent=True)
        self.assertEqual(chunk.read_bytes(), b'unknown substituted evidence')
        self.assertEqual(self.latest_rows(), [('before',)])

    def test_torn_unlinked_final_intent_does_not_block_owned_recovery(self):
        self.assertTrue(self.run_nightly()['passed']);self.change();self.interrupt_chunk()
        with (self.jobs/'object-ledger.jsonl').open('ab') as ledger:ledger.write(b'{"candidate":')
        self.job.reconcile(retention_adopted=True,inputs_quiescent=True)
        self.assertTrue(self.run_nightly()['passed'])
        self.assertEqual(self.latest_rows(),[('before',),('second',)])

    def test_missing_ownership_record_still_preserves_existing_chunk(self):
        self.assertTrue(self.run_nightly()['passed']);self.change();self.interrupt_chunk()
        ledger=self.jobs/'object-ledger.jsonl';ledger.write_bytes(b'{"candidate":')
        candidate=self.nightly/self.job.read()['candidate']
        with self.assertRaisesRegex(ValueError,'unexpected incomplete candidate evidence'):
            self.job.reconcile(retention_adopted=True,inputs_quiescent=True)
        self.assertTrue(list((candidate/'objects').glob('chunk-*')))

    def test_chunked_current_reconciliation_and_sqlite_restore(self):
        first = self.run_nightly()
        self.assertTrue(first['passed'], first)
        with sqlite3.connect(self.db) as db:db.execute("INSERT INTO retained VALUES ('latest chunked work')")
        second = self.run_nightly()
        self.assertTrue(second['passed'], second)
        m = self.store_job.current();row = m['entries']['home/state/state.sqlite']
        data = b''.join(object_blocks(self.nightly/m['generation']/'objects'/row['sha256'], row['sha256'], row['bytes'], CHUNKED))
        with sqlite3.connect(':memory:') as db:
            db.deserialize(data)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone(), ('ok',))
            self.assertIn(('latest chunked work',), db.execute('SELECT value FROM retained').fetchall())


if __name__ == '__main__':unittest.main()
