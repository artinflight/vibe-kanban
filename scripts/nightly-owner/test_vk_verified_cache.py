import base64
import fcntl
import gzip
import hashlib
import io
import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zlib

import vk_verified_cache as cache


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='nightly-cache-fixture-')
        self.root = Path(self.work.name).resolve()
        self.raw = self.root / 'index.sqlite'
        con = sqlite3.connect(self.raw)
        con.execute('create table entries(name text primary key,row text)')
        con.execute("insert into entries values('kept','accepted')")
        con.commit()
        con.close()
        os.chmod(self.raw, 0o640)
        os.setxattr(self.raw, 'user.nightly-fixture', b'metadata-proof')
        os.utime(self.raw, ns=(1700000000123456789, 1700000000987654321))
        self.meta = cache.metadata(self.raw)
        self.data = self.raw.read_bytes()
        os.utime(self.raw, ns=(self.meta['atime_ns'], self.meta['mtime_ns']))
        self.archive = self.root / 'index.sqlite.zlib'
        self.archive.write_bytes(zlib.compress(self.data))
        self.lease = self.root / 'owner.lease'
        self.lease.touch(mode=0o600)
        self.spec = dict(format='vk-verified-sqlite-cache-v1', raw_path=str(self.raw),
                         archive_path=str(self.archive), lease_path=str(self.lease),
                         lease_identity=[self.lease.stat().st_dev, self.lease.stat().st_ino],
                         encoding='zlib', raw_bytes=len(self.data),
                         raw_allocated_bytes=self.raw.stat().st_blocks * 512,
                         raw_sha256=hashlib.sha256(self.data).hexdigest(),
                         archive_bytes=self.archive.stat().st_size,
                         archive_sha256=hashlib.sha256(self.archive.read_bytes()).hexdigest(),
                         metadata=self.meta)
        self.calls = []

    def tearDown(self):
        self.work.cleanup()

    def admit(self, remaining):
        self.calls.append(remaining)
        return True

    def checksum(self):
        return hashlib.sha256(cache.canonical(self.spec)).hexdigest()

    def read(self, **kwargs):
        with cache.open_immutable(self.spec, self.checksum(),
                                  admit=kwargs.get('admit', self.admit)) as con:
            self.assertEqual(con.execute('select * from entries').fetchall(), [('kept', 'accepted')])
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("insert into entries values('forbidden','write')")

    def test_absent_raw_restores_exact_bytes_metadata_then_readonly_SQLite(self):
        self.raw.unlink()
        self.read()
        self.assertEqual(self.raw.read_bytes(), self.data)
        # SQLite/read_bytes can advance atime after the required pre-open check.
        actual = cache.metadata(self.raw)
        self.assertEqual({k:v for k,v in actual.items() if k != 'atime_ns'},
                         {k:v for k,v in self.meta.items() if k != 'atime_ns'})
        self.assertGreaterEqual(max(self.calls), self.spec['raw_allocated_bytes'])
        self.assertTrue(self.archive.is_file())

    def test_resident_raw_validates_without_restoration_scratch(self):
        self.read()
        os.utime(self.raw, ns=(self.meta['atime_ns'] + 1000000000, self.meta['mtime_ns']))
        self.read()
        self.assertEqual(set(self.calls), {0})

    def test_missing_archive_fails_even_when_raw_resident(self):
        self.archive.unlink()
        with self.assertRaises(FileNotFoundError):
            self.read()
        self.assertTrue(self.raw.is_file())

    def test_invalid_archive_retains_partial_and_never_publishes_raw(self):
        self.raw.unlink()
        self.archive.write_bytes(self.archive.read_bytes()[:-3])
        self.spec['archive_bytes'] = self.archive.stat().st_size
        with self.assertRaises(ValueError):
            self.read()
        self.assertFalse(self.raw.exists())
        self.assertTrue(list(self.root.glob('index.sqlite.hydrate-*')))

    def test_corrupt_resident_raw_is_never_replaced(self):
        self.raw.write_bytes(b'wrong')
        with self.assertRaises(ValueError):
            self.read()
        self.assertEqual(self.raw.read_bytes(), b'wrong')

    def test_low_scratch_admission_before_any_partial_or_SQLite(self):
        self.raw.unlink()
        with self.assertRaises(RuntimeError):
            self.read(admit=lambda remaining: remaining == 0)
        self.assertFalse(self.raw.exists())
        self.assertFalse(list(self.root.glob('*.hydrate-*')))

    def test_missing_owner_lease_is_not_created(self):
        self.lease.unlink()
        with self.assertRaises(FileNotFoundError):
            self.read()
        self.assertFalse(self.lease.exists())

    def test_replaced_owner_lease_is_not_adopted(self):
        self.lease.rename(self.root / 'original-owner.lease')
        self.lease.touch(mode=0o600)
        with self.assertRaises(ValueError):
            self.read()

    def test_raw_symlink_and_different_manifest_fail_closed(self):
        self.raw.unlink()
        self.raw.symlink_to(self.archive)
        with self.assertRaises(ValueError):
            self.read()
        with self.assertRaises(ValueError):
            with cache.held_cache(self.spec, '0' * 64, admit=self.admit):
                self.fail('Unverified manifest admitted')

    def test_shared_reader_lease_blocks_owner_retirement(self):
        with cache.open_immutable(self.spec, self.checksum(), admit=self.admit):
            with self.lease.open('rb') as other:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_gzip_single_member_supported_trailing_member_rejected(self):
        self.raw.unlink()
        self.archive.write_bytes(gzip.compress(self.data))
        self.spec.update(encoding='gzip', archive_bytes=self.archive.stat().st_size,
                         archive_sha256=hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.read()
        self.raw.unlink()
        self.archive.write_bytes(self.archive.read_bytes() + gzip.compress(b'extra'))
        self.spec.update(archive_bytes=self.archive.stat().st_size,
                         archive_sha256=hashlib.sha256(self.archive.read_bytes()).hexdigest())
        with self.assertRaises(ValueError):
            self.read()
        self.assertFalse(self.raw.exists())

    def test_historical_direct_SQLite_consumer_uses_guarded_entrypoint(self):
        self.raw.unlink()
        script = self.root / 'consumer.py'
        script.write_text('import sqlite3\nc=sqlite3.connect(' +
                          repr(self.raw.as_uri() + '?mode=ro&immutable=1') +
                          ',uri=True)\nassert c.execute("select count(*) from entries").fetchone()==(1,)\nc.close()\n')
        source_hash = hashlib.sha256(script.read_bytes()).hexdigest()
        self.spec['consumers'] = {str(script): source_hash}
        cache.run_consumer(script, source_hash, self.spec, self.checksum(), admit=self.admit)
        with self.assertRaises(ValueError):
            cache.run_consumer(script, '0' * 64, self.spec, self.checksum(), admit=self.admit)

    def pax_archive(self, *, second_member=False, wrong_name=False):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode='w', format=tarfile.PAX_FORMAT) as tar:
            member = tarfile.TarInfo('../escape' if wrong_name else self.raw.name)
            member.size = len(self.data)
            member.uid, member.gid, member.mode = self.meta['uid'], self.meta['gid'], self.meta['mode']
            member.pax_headers = {'mtime': str(cache.Decimal(self.meta['mtime_ns']) / 10**9),
                                  'atime': str(cache.Decimal(self.meta['atime_ns']) / 10**9)}
            tar.addfile(member, io.BytesIO(self.data))
            if second_member:
                tar.addfile(member, io.BytesIO(self.data))
        self.archive.write_bytes(subprocess.check_output(['zstd', '-q', '-c'], input=out.getvalue()))
        self.spec.update(encoding='tar-zstd', metadata=dict(self.meta, xattrs={}),
                         archive_bytes=self.archive.stat().st_size,
                         archive_sha256=hashlib.sha256(self.archive.read_bytes()).hexdigest())

    def test_actual_single_member_PAX_zstd_contract_hydrates_before_legacy_consumer(self):
        self.pax_archive()
        self.raw.unlink()
        self.read()
        self.assertEqual(self.raw.read_bytes(), self.data)
        self.assertEqual(os.listxattr(self.raw), [])

    def test_PAX_extra_member_or_path_traversal_rejected(self):
        for extra, traversal in [(True, False), (False, True)]:
            with self.subTest(extra=extra, traversal=traversal):
                self.pax_archive(second_member=extra, wrong_name=traversal)
                if self.raw.exists():
                    self.raw.unlink()
                with self.assertRaises(ValueError):
                    self.read()
                self.assertFalse(self.raw.exists())

    def test_current_floor_and_future_are_once_charged_not_old_T18(self):
        with patch.object(cache.os.path, 'ismount', return_value=True), \
             patch.object(cache.os, 'statvfs') as sv:
            sv.return_value.f_bavail = 2200000000
            sv.return_value.f_frsize = 1
            admit = cache.ssd_admission(future_bytes=lambda: 9793536,
                                        health_check=lambda: True,
                                        floor_bytes=2147483648, stop_bytes=1048576)
            self.assertIs(admit(1000000), True)
            with self.assertRaises(RuntimeError):
                admit(852303872)
            sv.return_value.f_bavail = 2147483648 + 9793536 + 1048576
            with self.assertRaises(RuntimeError):
                admit(0)


if __name__ == '__main__':
    unittest.main()
