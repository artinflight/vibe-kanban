"""Failure/streaming contracts for the normal-reader bridge; no B connection."""
import hashlib
import unittest

import log_dedup as logs
from reclaim import verify_recovery
from recovery_stream import NormalRecovery, MAX_READ


SESSION = 'abcd1234-1234-1234-1234-123456789abc'
EXECUTION = '11111111-2222-3333-4444-555555555555'
RELATIVE = f'ab/{SESSION}/processes/{EXECUTION}.jsonl'
PREFIX = '/home/operator/live/sessions'
B = 'desktop:B:/vk-backups/qualified-current-set/'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class Held:
    def __init__(self, files):
        self.files = files
        self.active = True
        self.started = []
        self.closed = []
        self.rows = {name: {'kind': 'file', 'sha256': digest(raw), 'bytes': len(raw)}
                     for name, raw in files.items()}
        self.index = self

    def check(self):
        if not self.active:
            raise logs.ArchiveError('Actual recovery lease ended')

    def entry(self, name):
        self.check()
        return self.rows[name]

    def blocks(self, name):
        self.check()
        self.started.append(name)
        try:
            raw = self.files[name]
            for offset in range(0, len(raw), 17):
                self.check()
                yield raw[offset:offset + 17]
        finally:
            self.closed.append(name)


class RecoveryStreamTests(unittest.TestCase):
    def fixture(self, raw=b'original repeated conversation\n' * 53, relative=RELATIVE):
        name = PREFIX[1:] + '/' + relative
        handle = Held({name: raw})
        return handle, NormalRecovery(handle, source_namespace=PREFIX, location=B, guard=handle.check), name

    def test_exact_streaming_normal_namespace_and_eof(self):
        raw = ('readable history \u2713\n' * 300).encode()
        handle, provider, name = self.fixture(raw)
        with provider.open_original(RELATIVE, digest(raw)) as stream:
            result = bytearray()
            while chunk := stream.read(31):
                result.extend(chunk)
            self.assertEqual(bytes(result), raw)
        self.assertEqual(handle.started, [name])
        self.assertEqual(handle.closed, [name])

    def test_rejects_wrong_selected_version_before_body_read(self):
        handle, provider, _ = self.fixture()
        with self.assertRaisesRegex(logs.ArchiveError, 'exact selected version'):
            with provider.open_original(RELATIVE, '0' * 64):
                self.fail('wrong version admitted')
        self.assertEqual(handle.started, [])

    def test_detects_truncated_extended_and_same_size_corrupted_content(self):
        original = b'complete exact original'
        for actual in [original[:-1], original + b'x', b'X' + original[1:]]:
            with self.subTest(actual=actual):
                handle, provider, name = self.fixture(original)
                handle.files[name] = actual
                with self.assertRaises(logs.ArchiveError):
                    with provider.open_original(RELATIVE, digest(original)) as stream:
                        while stream.read(256):
                            pass
                self.assertEqual(handle.closed, [name])

    def test_prefix_is_not_recovery_acceptance_and_does_not_drain(self):
        handle, provider, name = self.fixture()
        with self.assertRaisesRegex(logs.ArchiveError, 'verified EOF'):
            with provider.open_original(RELATIVE, handle.rows[name]['sha256']) as stream:
                self.assertEqual(len(stream.read(1)), 1)
        self.assertEqual(handle.closed, [name])

    def test_lost_real_lease_aborts_stream_and_closes_generator(self):
        handle, provider, name = self.fixture()
        with self.assertRaisesRegex(logs.ArchiveError, 'lease ended'):
            with provider.open_original(RELATIVE, handle.rows[name]['sha256']) as stream:
                stream.read(7)
                handle.active = False
                stream.read(7)
        self.assertEqual(handle.closed, [name])

    def test_traversal_and_other_session_shard_never_reach_reader(self):
        handle, provider, _ = self.fixture()
        for path in ['../' + RELATIVE, RELATIVE.replace('ab/', 'cd/', 1), '/'+RELATIVE,
                     RELATIVE.replace('/processes/', '/processes/../processes/')]:
            with self.subTest(path=path), self.assertRaises(logs.ArchiveError):
                with provider.open_original(path, '0' * 64):
                    pass
        self.assertEqual(handle.started, [])
        for namespace in ['/', '//host/path', PREFIX + '/', '/home/../sessions']:
            with self.subTest(namespace=namespace), self.assertRaises(logs.ArchiveError):
                NormalRecovery(handle, source_namespace=namespace, location=B, guard=handle.check)

    def test_bounded_reads_objects_and_empty_physical_body(self):
        object_path = f'ab/{SESSION}/processes/.log-objects/' + 'a' * 64 + '.gz'
        handle, provider, name = self.fixture(b'physical gzip bytes', object_path)
        with self.assertRaises(logs.ArchiveError):
            provider.open_original(object_path, handle.rows[name]['sha256'])
        with provider.open_member(object_path, handle.rows[name]['sha256']) as stream:
            for size in [-1, 0, MAX_READ + 1, True]:
                with self.subTest(size=size), self.assertRaises(logs.ArchiveError):
                    stream.read(size)
            self.assertEqual(stream.read(100), b'physical gzip bytes')
            self.assertEqual(stream.read(100), b'')
        _, empty, _ = self.fixture(b'')
        with empty.open_original(RELATIVE, digest(b'')) as stream:
            self.assertEqual(stream.read(1), b'')

    def test_existing_full_original_and_sidecar_verifier_uses_bridge(self):
        raw, sidecar = b'original log bytes\n', b'{"capture_state":"closed"}\n'
        side_relative = RELATIVE[:-6] + '.capture.json'
        handle = Held({PREFIX[1:]+'/'+RELATIVE: raw, PREFIX[1:]+'/'+side_relative: sidecar})
        provider = NormalRecovery(handle, source_namespace=PREFIX, location=B, guard=handle.check)
        plan = {'files': [{'path': RELATIVE, 'sha256': digest(raw), 'raw_bytes': len(raw),
                          'sidecars': [{'extension': 'capture.json', 'sha256': digest(sidecar),
                                        'identity': [0, 0, len(sidecar), 0, 0]}]}]}
        verify_recovery(provider, plan, handle.check)
        self.assertEqual(set(handle.started), set(handle.files))
        self.assertEqual(set(handle.closed), set(handle.files))


if __name__ == '__main__':
    unittest.main()
