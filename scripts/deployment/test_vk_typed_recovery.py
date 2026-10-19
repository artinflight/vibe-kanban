import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zlib
import zipfile

from vk_typed_recovery import (FORMAT, ComposedIndex, HeldRecoverySet, LocalDependencies,
                               build_overlay, canonical, checksum, held_index, read_rows)
from vk_typed_recovery import bind_components, retained_prefix, verify_overlay_contents


class TypedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('VK_TEST_TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base, self.new = self.root / 'base', self.root / 'new'
        for path in (self.base, self.new):
            path.mkdir(); (path / 'RECOVERY_READ.lease').touch()
        (self.base / 'home/state').mkdir(parents=True)
        (self.base / 'home/state/log').write_bytes(b'original\n')
        self.body = b'original\nnew\n'
        suffix = zlib.compress(b'new\n'); (self.new / 'suffix').write_bytes(suffix)
        self.meta = dict(uid=os.getuid(), gid=os.getgid(), mode=0o600, mtime_ns=123, xattrs={})
        self.rows = {'home/state': dict(self.meta, kind='directory'),
                     'home/state/log': self.file(self.body, segments=[
                         self.segment('accepted-base', 'home/state/log', b'original\n'),
                         self.segment('current', 'suffix', b'new\n', suffix)]),
                     'home/state/link': dict(self.meta, kind='hardlink', target='home/state/log',
                                            bytes=len(self.body), sha256=hashlib.sha256(self.body).hexdigest()),
                     'home/state/literal': dict(self.meta, kind='symlink', target='../external-literal')}
        db = sqlite3.connect(self.base / 'index.sqlite')
        db.execute('create table entries(name text primary key,row text) without rowid')
        db.execute('insert into entries values(?,?)', ('home/state', json.dumps(self.rows['home/state'])))
        db.execute('insert into entries values(?,?)', ('home/state/removed', json.dumps(self.file(b'old'))))
        db.commit(); db.close()
        self.write_overlay()
        self.identities = {layer: {'accepted_proof_sha256': '1' * 64} for layer in ('accepted-base', 'current')}
        self.provider = LocalDependencies({'accepted-base': self.base, 'current': self.new},
                                          self.identities, admission_check=lambda: None)

    def file(self, body, **extra):
        return dict(self.meta, kind='file', bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), **extra)

    def segment(self, layer, selector, body, encoded=None):
        row = dict(layer=layer, selector=selector, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        if encoded is not None:
            row.update(encoding='zlib', encoded_bytes=len(encoded), encoded_sha256=hashlib.sha256(encoded).hexdigest())
        return row

    def write_overlay(self):
        path = self.new / 'overlay.sqlite'
        if path.exists():
            path.unlink()
        db = sqlite3.connect(path)
        db.execute('create table puts(name text primary key,row text) without rowid')
        db.execute('create table removes(name text primary key) without rowid')
        db.executemany('insert into puts values(?,?)', [(n, json.dumps(r)) for n, r in self.rows.items() if n != 'home/state'])
        db.execute('insert into removes values(?)', ('home/state/removed',))
        db.commit(); db.close()

    def reference(self, root, name, layer):
        path = root / name
        return dict(layer=layer, selector=name, bytes=path.stat().st_size,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def descriptor(self):
        refs = [self.reference(self.base, 'index.sqlite', 'accepted-base'),
                self.reference(self.new, 'overlay.sqlite', 'current')]
        body = b''.join(canonical({'name': n, 'entry': r}) + b'\n' for n, r in sorted(self.rows.items()))
        return dict(format=FORMAT, source_prefix='/', writer_fence_verified=False,
                    original_epoch_complete=False, plan_sha256='2' * 64, scope_sha256='3' * 64,
                    sources=['/home/state'], original_source_dispositions={'/home/state': 'retained'},
                    dependencies=self.identities, indexes=refs, member_count=len(self.rows),
                    member_map_sha256=hashlib.sha256(body).hexdigest(), SQLite={},
                    journal=dict(instance='new-observer', scope_sha256='3' * 64, start=10, end=20,
                                 errors=[], event_closure_verified=True))

    def validate(self, handle, **overrides):
        args = dict(plan_sha256='2' * 64, scope_sha256='3' * 64, required_sources=['/home/state'],
                    original_sources=['/home/state'], required_pins={'/home/state/log': self.rows['home/state/log']}, required_SQL=[])
        args.update(overrides)
        return handle.validate(**args)

    def use(self, callback, descriptor=None):
        d = descriptor or self.descriptor()
        with self.provider.held(), held_index(self.provider, *d['indexes']) as index:
            handle = HeldRecoverySet(d, checksum(d), self.provider, index)
            return callback(handle)

    def test_real_base_overlay_append_hardlink_and_literal_link(self):
        def check(h):
            proof = self.validate(h)
            self.assertFalse(proof['writer_fence_verified'])
            self.assertEqual(b''.join(h.blocks('home/state/log')), self.body)
            self.assertEqual(b''.join(h.blocks('home/state/link')), self.body)
            with self.assertRaises(KeyError): h.index.entry('home/state/removed')
            with self.assertRaises(ValueError): list(h.blocks('home/state/literal'))
        self.use(check)

    def test_changed_index_bytes_fail_authentication(self):
        d = self.descriptor()
        with (self.new / 'overlay.sqlite').open('ab') as f: f.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'index bytes'): self.use(lambda h: None, d)

    def test_descriptor_digest_cannot_be_replaced_by_passed_boolean(self):
        with self.provider.held(), held_index(self.provider, *self.descriptor()['indexes']) as index:
            with self.assertRaises(ValueError): HeldRecoverySet(self.descriptor(), 'f' * 64, self.provider, index)

    def test_missing_required_root_or_SQL_or_runtime_pin_fails(self):
        for overrides in [dict(required_sources=['/home/state', '/another']),
                          dict(required_SQL=['/home/state/missing.sqlite']),
                          dict(required_pins={'/home/state/log': {'bytes': 1, 'sha256': 'a' * 64}})]:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.use(lambda h: self.validate(h, **overrides))

    def test_unclosed_journal_and_original_epoch_relabel_fail(self):
        for field in ('event_closure', 'original_epoch', 'store_format'):
            d = self.descriptor()
            if field == 'event_closure': d['journal']['event_closure_verified'] = False
            elif field == 'original_epoch': d['original_epoch_complete'] = True
            else: d['format'] = 'vk-nightly-restart-baseline-v1'
            with self.subTest(field=field), self.assertRaises(ValueError): self.use(self.validate, d)

    def test_hardlink_metadata_mismatch_fails(self):
        self.rows['home/state/link']['mode'] = 0o777
        self.write_overlay()
        with self.assertRaisesRegex(ValueError, 'hardlink'): self.use(self.validate)

    def test_truncated_overflow_and_trailing_zlib_fail(self):
        for data in (zlib.compress(b'new\n')[:-1], zlib.compress(b'new\n') + b'x', zlib.compress(b'too much')):
            (self.new / 'suffix').write_bytes(data)
            def read(h):
                self.validate(h); list(h.blocks('home/state/log'))
            with self.subTest(data=data), self.assertRaises(ValueError): self.use(read)

    def test_linked_parent_cannot_escape_dependency_root(self):
        (self.new / 'suffix').unlink()
        (self.new / 'suffix').symlink_to(self.base / 'home/state/log')
        def read(h):
            self.validate(h); list(h.blocks('home/state/log'))
        with self.assertRaises(OSError): self.use(read)

    def test_member_below_archived_symlink_rejected(self):
        self.rows['home/state/literal/child'] = self.file(b'')
        self.write_overlay()
        with self.assertRaisesRegex(ValueError, 'traverses'): self.use(self.validate)

    def test_read_requires_map_validation_and_live_lease(self):
        held = []
        def read(h):
            with self.assertRaisesRegex(ValueError, 'not been validated'): list(h.blocks('home/state/log'))
            self.validate(h); held.append(h)
        self.use(read)
        with self.assertRaisesRegex(ValueError, 'lease has ended'): list(held[0].blocks('home/state/log'))

    def test_journal_catchup_requires_same_scope_instance_and_forward_sequence(self):
        def check(h):
            self.validate(h)
            good = dict(ready=True, errors=[], instance='new-observer', scope_sha256='3' * 64, sequence=21)
            result = h.catchup(lambda seq: good)
            self.assertFalse(result['activation_authorized'])
            self.assertTrue(result['fresh_final_SQLite_API_required'])
            for change in (dict(instance='other'), dict(scope_sha256='4' * 64), dict(sequence=19), dict(errors=['overflow'])):
                with self.assertRaisesRegex(ValueError, 'continuity'): h.catchup(lambda seq: dict(good, **change))
        self.use(check)

    def test_undeclared_component_and_ambiguous_tombstone_fail(self):
        self.rows['home/state/log']['segments'][1]['layer'] = 'undeclared'
        self.write_overlay()
        with self.assertRaisesRegex(ValueError, 'dependency'): self.use(self.validate)
        self.rows['home/state/log']['segments'][1]['layer'] = 'current'
        self.write_overlay()
        db = sqlite3.connect(self.new / 'overlay.sqlite')
        db.execute('insert into removes values(?)', ('home/state/log',)); db.commit(); db.close()
        with self.assertRaisesRegex(ValueError, 'ambiguous'): self.use(self.validate)

    def test_sealed_source_rows_reject_truncation_trailing_and_error(self):
        rows = [dict(name='home/state', **self.rows['home/state'])]
        raw = b''.join(canonical(row) + b'\n' for row in rows)
        encoded = zlib.compress(raw)
        args = dict(expected_sha256=hashlib.sha256(raw).hexdigest(), expected_count=1)
        self.assertEqual(list(read_rows(io.BytesIO(encoded), **args)), rows)
        for bad in (encoded[:-1], encoded + b'x', zlib.compress(raw + raw)):
            with self.subTest(bad=bad), self.assertRaises(ValueError): list(read_rows(io.BytesIO(bad), **args))
        row = canonical(dict(name='home/state', unaccepted_source_error={'error': 'changed'})) + b'\n'
        with self.assertRaisesRegex(ValueError, 'unaccepted'):
            list(read_rows(io.BytesIO(zlib.compress(row)), expected_sha256=hashlib.sha256(row).hexdigest(), expected_count=1))

    def test_overlay_derivation_reuses_cross_path_body_and_records_gaps(self):
        base = sqlite3.connect(self.base / 'index.sqlite')
        base.execute('insert into entries values(?,?)', ('home/state/log', json.dumps(self.file(b'original\n'))))
        base.commit(); self.addCleanup(base.close)
        observations = [dict(name='home/state', **self.rows['home/state']),
                        dict(name='home/state/alias', **self.file(b'original\n'),
                             authenticated_accepted_base_body_carrier='home/state/log', source_device=1, source_inode=1),
                        dict(name='home/state/new', **self.file(b'new'),
                             authenticated_accepted_base_body_carrier=None, old_body_is_exact_current_prefix=False,
                             source_device=1, source_inode=2)]
        body = sqlite3.connect(':memory:'); self.addCleanup(body.close)
        body.execute('create table bodies(dev,ino,bytes,mode,uid,gid,mtime,ctime,sha)')
        body.execute('insert into bodies values(?,?,?,?,?,?,?,?,?)',
                     (1, 2, 3, 0o100600, os.getuid(), os.getgid(), 123, 123, bytes.fromhex(hashlib.sha256(b'new').hexdigest())))
        overlay = sqlite3.connect(':memory:'); self.addCleanup(overlay.close)
        result = build_overlay(base, overlay, iter(observations), sql_components={}, source_body_index=body)
        self.assertEqual(result['member_count'], 3)
        self.assertFalse(result['full_current_set_accepted'])
        alias = json.loads(overlay.execute('select row from puts where name=?', ('home/state/alias',)).fetchone()[0])
        self.assertEqual(alias['segments'][0]['selector'], 'home/state/log')
        self.assertEqual(overlay.execute('select count(*) from requests').fetchone()[0], 1)
        self.assertEqual({n for n, in overlay.execute('select name from removes')}, {'home/state/log', 'home/state/removed'})

    def test_pinned_ZIP_member_reuses_existing_release_without_extraction(self):
        with zipfile.ZipFile(self.new / 'release.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('assets/current.js', b'new\n')
        encoded = (self.new / 'release.zip').read_bytes()
        self.rows['home/state/log']['segments'][1] = dict(
            self.segment('current', 'release.zip', b'new\n', encoded),
            encoding='zip-member', member='assets/current.js')
        self.write_overlay()
        def read(h):
            self.validate(h)
            self.assertEqual(b''.join(h.blocks('home/state/log')), self.body)
            proof = verify_overlay_contents(h, accepted_components={})
            self.assertEqual(proof['new_composed_bodies_readback'], 1)
            self.assertEqual(proof['new_composed_body_readback_bytes'], len(self.body))
            self.assertFalse(proof['activation_authorized'])
        self.use(read)

    def test_reused_independent_component_must_match_exact_body(self):
        def read(h):
            self.validate(h)
            accepted = {'home/state/log': dict(self.rows['home/state/log'], independent_proof_sha256='f' * 64)}
            proof = verify_overlay_contents(h, accepted_components=accepted)
            self.assertEqual(proof['exact_independent_component_proofs_reused'], 1)
            accepted['home/state/log']['bytes'] += 1
            with self.assertRaisesRegex(ValueError, 'component differs'):
                verify_overlay_contents(h, accepted_components=accepted)
        self.use(read)

    def test_immutable_extra_root_has_explicit_closure_not_fabricated_journal_scope(self):
        self.rows['home/release'] = dict(self.meta, kind='directory')
        self.write_overlay()
        d = self.descriptor(); d['sources'].append('/home/release')
        d['scope_sha256'] = '4' * 64
        raw = canonical({'name': 'home/release', 'entry': self.rows['home/release']}) + b'\n'
        frozen = {'/home/release': dict(member_count=1, member_map_sha256=hashlib.sha256(raw).hexdigest(),
                                       independent_proof_sha256='f' * 64)}
        d['immutable_sources'] = frozen; d['journal_sources'] = ['/home/state']
        args = dict(scope_sha256='4' * 64, required_sources=d['sources'],
                    journal_scope_sha256='3' * 64, immutable_sources=frozen)
        self.use(lambda h: self.validate(h, **args), d)
        wrong = copy.deepcopy(d); wrong['journal_sources'] = []
        with self.assertRaisesRegex(ValueError, 'source coverage'): self.use(lambda h: self.validate(h, **args), wrong)

    def test_replacing_lease_or_mutating_held_index_fails(self):
        def read(h):
            self.validate(h)
            (self.new / 'RECOVERY_READ.lease').unlink()
            (self.new / 'RECOVERY_READ.lease').touch()
            with self.assertRaisesRegex(ValueError, 'lease replaced'): h.check()
            # Restore the expected name before context finalizers run. Keeping
            # the old inode is impossible here, so the finalizer must also fail.
        with self.assertRaisesRegex(ValueError, 'lease replaced'): self.use(read)

    def test_pending_recipe_requires_exact_independent_component_readback(self):
        row = copy.deepcopy(self.rows['home/state/log'])
        prefix, tail = row.pop('segments')
        row.update(pending_content_request='request', prefix_segments=[prefix])
        db = sqlite3.connect(':memory:'); self.addCleanup(db.close)
        db.execute('create table puts(name text primary key,row text)')
        db.execute('insert into puts values(?,?)', ('home/state/log', json.dumps(row))); db.commit()
        measured = dict(tail, selected_member_sha256=row['sha256'])
        restored = dict(tail, file='objects/tail.zlib', independent_file_readback_sha256=tail['sha256'], independently_allocated=True)
        invalid = dict(restored, encoded_sha256='f' * 64)
        with self.assertRaisesRegex(ValueError, 'differs'):
            bind_components(db, {'request': measured}, {tail['sha256']: invalid}, layer='current')
        self.assertEqual(bind_components(db, {'request': measured}, {tail['sha256']: restored}, layer='current'), 1)
        sealed = json.loads(db.execute('select row from puts').fetchone()[0])
        self.assertNotIn('pending_content_request', sealed)
        self.assertEqual(sealed['segments'][0], prefix)
        self.assertEqual(sum(s['bytes'] for s in sealed['segments']), len(self.body))

    def test_retained_unsealed_prefix_requires_exact_partial_and_encoded_identity(self):
        rows = [dict(name='home/a', kind='directory'), dict(name='home/b', kind='directory')]
        complete = b''.join(canonical(r) + b'\n' for r in rows)
        partial = b'{"name":"home/c"'
        compressor = zlib.compressobj()
        encoded = compressor.compress(complete + partial) + compressor.flush(zlib.Z_SYNC_FLUSH)
        args = dict(encoded_sha256=hashlib.sha256(encoded).hexdigest(), encoded_bytes=len(encoded),
                    complete_sha256=hashlib.sha256(complete).hexdigest(), complete_count=2,
                    partial_sha256=hashlib.sha256(partial).hexdigest(), partial_bytes=len(partial), last_name='home/b')
        self.assertEqual(list(retained_prefix(io.BytesIO(encoded), **args)), rows)
        for change in ({'complete_count': 1}, {'partial_bytes': 0}, {'last_name': 'home/c'},
                       {'encoded_sha256': 'f' * 64}, {'complete_sha256': 'f' * 64},
                       {'partial_sha256': 'f' * 64}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                list(retained_prefix(io.BytesIO(encoded), **{**args, **change}))
        with self.assertRaises(ValueError):
            list(retained_prefix(io.BytesIO(encoded + b'extra'), **args))
        with self.assertRaises(ValueError):
            list(retained_prefix(io.BytesIO(zlib.compress(complete)), **args))

    def test_sealed_suffix_fingerprint_can_replace_retained_cache_lookup(self):
        base = sqlite3.connect(self.base / 'index.sqlite'); self.addCleanup(base.close)
        row = dict(name='home/state/new', **self.file(b'new'), source_device=1, source_inode=2,
                   recorded_body_fingerprint=[3, 0o100600, os.getuid(), os.getgid(), 123, 456])
        for malformed in (False, True):
            overlay = sqlite3.connect(':memory:'); self.addCleanup(overlay.close)
            observation = copy.deepcopy(row)
            if malformed:
                observation['recorded_body_fingerprint'][0] = 4
                with self.assertRaisesRegex(ValueError, 'fingerprint differs'):
                    build_overlay(base, overlay, [observation], sql_components={}, source_body_index=None)
            else:
                result = build_overlay(base, overlay, [observation], sql_components={}, source_body_index=None)
                self.assertEqual(result['member_count'], 1)
                request = json.loads(overlay.execute('select row from requests').fetchone()[0])
                self.assertEqual(request['recorded_body_fingerprint'], row['recorded_body_fingerprint'])


if __name__ == '__main__':
    unittest.main()
