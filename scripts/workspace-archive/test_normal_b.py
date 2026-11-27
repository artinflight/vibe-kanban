"""Normal Nightly source contracts with local transport fixtures (not live B).

Set NIGHTLY_SOURCE_DIR to the exact qualified Nightly scripts/deployment folder.
Its real capture, row/index validation and decoder are exercised. Connections,
leases and independent remote verification are fixture-only and are NOT evidence
of actual Desktop B restore or production owner admission.
"""
from contextlib import contextmanager
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import uuid
import zlib

from lifecycle import digest
from normal_b import NormalB, Blocks, requests, nightly_digest
import payloads


class AdapterTests(unittest.TestCase):
    def test_bounded_stream_handles_empty_and_fragmented_normal_blocks(self):
        for blocks in ([], [b'a', b'bc', b'def'], [b'\0' * 1000]):
            with io.BufferedReader(Blocks(iter(blocks)), buffer_size=16) as stream:
                got = []
                while block := stream.read(7):
                    got.append(block)
                self.assertEqual(b''.join(got), b''.join(blocks))

    def test_non_ascii_plan_has_distinct_correct_nightly_and_catalog_bindings(self):
        manifest = {'name': '\u00e9'}
        self.assertNotEqual(digest(manifest), nightly_digest(manifest))
        self.assertEqual(nightly_digest(manifest), hashlib.sha256(b'{"name":"\\u00e9"}').hexdigest())


class DB:
    def __init__(self, client, key, path, readonly=False):
        self.client, self.key = client, key
        self.db = sqlite3.connect(path.as_uri() + ('?mode=ro' if readonly else '?mode=rwc'), uri=True, isolation_level=None)

    def execute(self, *args):
        return self.db.execute(*args)

    @property
    def in_transaction(self):
        return self.db.in_transaction

    def request(self, operation):
        return {'fixture_only': True}

    def close(self):
        self.db.close()


class NativeFixture:
    maximum = 1024**2

    def __init__(self, root):
        self.root, self.connections, self.uploads = root, {}, 0

    def connect(self, key, sha, readonly=False, **kwargs):
        path = self.root / (sha + '.sqlite' if readonly else hashlib.sha256(key.encode()).hexdigest() + '.working')
        result = DB(self, key, path, readonly)
        self.connections[key] = result
        return result

    def seal_checkpoint(self, key, metadata):
        candidate = self.root / (str(uuid.uuid4()) + '.seal')
        target = sqlite3.connect(candidate)
        self.connections[key].db.backup(target)
        target.close()
        raw = candidate.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        path = self.root / (sha + '.sqlite')
        if path.exists():
            candidate.unlink()
        else:
            candidate.rename(path)
        return dict(sha256=sha, bytes=len(raw), fixture_only=True)

    def ensure(self, raw, readback_sink=None):
        raw = bytes(raw)
        sha = hashlib.sha256(raw).hexdigest()
        path = self.root / (sha + '.zlib')
        if not path.exists():
            path.write_bytes(zlib.compress(raw))
            self.uploads += 1
        encoded = path.read_bytes()
        if readback_sink is not None:
            readback_sink.write(zlib.decompress(encoded))
        return dict(layer='nightly-objects-v1', selector=path.name, encoding='zlib',
                    bytes=len(raw), sha256=sha, encoded_bytes=len(encoded),
                    encoded_sha256=hashlib.sha256(encoded).hexdigest())


@unittest.skipUnless(os.environ.get('NIGHTLY_SOURCE_DIR'), 'explicit qualified Nightly source required')
class MaintainedNightlyContractTests(unittest.TestCase):
    def setUp(self):
        folder = Path(os.environ['NIGHTLY_SOURCE_DIR']).resolve()
        sys.path.insert(0, str(folder))
        self.addCleanup(lambda: sys.path.remove(str(folder)))
        self.factory = importlib.import_module('vk_nightly_selected_factory')
        self.selected = importlib.import_module('vk_nightly_selected_recovery')
        self.controls = importlib.import_module('vk_nightly_owner_controls')
        self.reader = importlib.import_module('vk_nightly_selected_reader')
        source_files = set()
        for module in (self.factory, self.selected, self.controls):
            source_files.update(self.factory.source_closure(folder, module.__name__))
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ('source', 'controls', 'fixture-B'):
            (self.root / name).mkdir(mode=0o700)
        self.source = self.root / 'source'
        for i in range(132):
            (self.source / ('file-' + str(i))).write_bytes(b'repeated small body')
        (self.source / '\u00e9').write_bytes(b'unicode filename')
        (self.source / 'empty').touch()
        os.symlink('file-0', self.source / 'link')
        tree = payloads.snapshot([self.source])
        self.manifest = dict(format='vk-workspace-archive-v1', workspace_id=str(uuid.uuid4()),
            operation_id=str(uuid.uuid4()), request_version=1, ownership={'fixture_only': True}, payloads=tree)
        self.client = NativeFixture(self.root / 'fixture-B')
        self.active_contexts = 0
        self.template = dict(format='vk-nightly-selected-original-recovery-config-v1',
            source_folder=str(folder), source_sha256={n: hashlib.sha256((folder/n).read_bytes()).hexdigest() for n in source_files},
            dependencies={'nightly-objects-v1': {'fixture_only': True}, 'nightly-controls-v1': {'fixture_only': True}},
            B_controls={'B_root': 'B:/vk-backups'}, host_admission={'fixture_only': True})
        self.provider = NormalB(self.context, self.factory, self.selected, self.controls,
                               self.template, self.root / 'controls', lambda: None)
        self.addCleanup(patch.stopall)
        patch.object(self.controls, 'verify_checkpoint', self.fixture_control_verification).start()
        patch.object(self.selected, 'open_recovery', self.fixture_selected).start()

    @contextmanager
    def context(self):
        self.assertEqual(self.active_contexts, 0, 'no nested competing backup contexts')
        self.active_contexts += 1
        try:
            yield types.SimpleNamespace(location='desktop:B:/vk-backups/fixture',
                provider_placement={'fixture_only': True}, check=lambda: None, native_SQL_client=self.client,
                handle=types.SimpleNamespace(db=types.SimpleNamespace(client=self.client), rows={}))
        finally:
            self.active_contexts -= 1

    def fixture_control_verification(self, recovery, controls, placement, dependencies, receipt, **kwargs):
        # The actual remote/lease assertion is deliberately not under test here.
        return {'actual_independent_normal_restore': dict(independent_owner_controls_restore_verified=True,
            manifest_sha256=receipt['manifest_sha256'], files=1, fixture_only=True)}

    @contextmanager
    def fixture_selected(self, config, plan):
        with self.context():
            config = json.loads(Path(config).read_text())
            request = json.loads(Path(config['request_file']).read_text())
            self.assertEqual(request['plan_sha256'], nightly_digest(plan))
            db = self.client.connect(config['index']['index_name'], config['index']['checkpoint_sha256'], readonly=True)
            try:
                rows = {name: self.factory.decode_member(raw) for name, raw in
                        db.execute('select name,row from selected_recovery_members')}
                qualified = self.reader.qualify(request, rows, config['dependencies'])
                client = self.client
                class Files:
                    def check(self): pass
                    @contextmanager
                    def open(self, layer, selector):
                        with (client.root / selector).open('rb') as stream:
                            yield stream
                handle = self.reader.SelectedFiles(Files(), qualified, lambda: None)
                yield types.SimpleNamespace(check=lambda: None, handle=handle)
            finally:
                db.close()

    def test_real_factory_index_and_decoder_restore_all_files_and_reuse_captured_versions(self):
        locator = self.provider.capture(self.manifest)
        initial = self.client.uploads
        self.assertEqual(initial, 3)  # repeated body, Unicode body, empty body
        again = self.provider.capture(self.manifest)
        self.assertEqual(again, locator)
        self.assertEqual(self.client.uploads, initial)
        with self.provider.recall(locator, digest(self.manifest)) as recalled:
            roots = payloads.restore(recalled.manifest['payloads'], self.root / 'restore', recalled.open_body)
        payloads.verify(self.manifest['payloads'], roots)
        self.assertEqual(self.active_contexts, 0)

    def test_real_decoder_rejects_corrupt_objects_and_preserves_originals(self):
        locator = self.provider.capture(self.manifest)
        object_path = next((self.root / 'fixture-B').glob('*.zlib'))
        object_path.write_bytes(b'damaged')
        with self.assertRaises((ValueError, zlib.error)):
            with self.provider.recall(locator, digest(self.manifest)) as recalled:
                payloads.restore(recalled.manifest['payloads'], self.root / 'bad-restore', recalled.open_body)
        payloads.verify(self.manifest['payloads'])
