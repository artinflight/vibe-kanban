import gzip
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

import log_dedup as loose
import packed_objects as packed


class PackedObjectsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root/'source'
        self.source.mkdir()
        (self.source/'.log-objects').mkdir()
        self.target = self.root/'packed'

    def log(self, name, blocks):
        chunks = []
        for body in blocks:
            key = loose.sha(body)
            (self.source/'.log-objects'/(key+'.gz')).write_bytes(gzip.compress(body, mtime=0))
            chunks.append(dict(sha256=key, bytes=len(body)))
        raw = b''.join(blocks)
        path = self.source/name
        path.write_bytes(loose.encode(dict(version=1, raw_bytes=len(raw), sha256=loose.sha(raw), chunks=chunks)))
        return path, raw

    def test_shared_pieces_have_one_pack_and_exact_stream(self):
        a, raw_a = self.log('a.jsonl', [b'utf8:\xe2', b'\x9c\x93\n', b'repeated']*100)
        b, raw_b = self.log('b.jsonl', [b'repeated', b'second'])
        before = {p: p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        result = packed.prepare([a, b], self.target)
        self.assertEqual(result['unique_objects'], 4)
        self.assertEqual(result['physical_files'], 3)
        for name, expected in [('a.jsonl',raw_a), ('b.jsonl',raw_b)]:
            output = io.BytesIO()
            proof = packed.verify(self.target/name, output)
            self.assertEqual(output.getvalue(), expected)
            self.assertEqual(proof['pack_opens'], 1)
            self.assertTrue(proof['full_EOF_verified'])
        self.assertEqual(before, {p:p.read_bytes() for p in before})

    def test_bounds_cross_pack_edges_and_descriptor_cache(self):
        blocks = [os.urandom(loose.MAX_CHUNK) for _ in range(6)]
        path, expected = self.log('a.jsonl', blocks*2)
        result = packed.prepare([path], self.target, maximum_pack_bytes=loose.MAX_CHUNK+2048)
        self.assertEqual(result['packs'], 6)
        with packed.Reader(self.target/path.name) as reader:
            output = bytearray();buf = bytearray(1001)
            while n := reader.readinto(buf):
                self.assertLessEqual(len(reader.handles), 4)
                output.extend(buf[:n])
            self.assertEqual(output, expected)

    def test_truncated_corrupt_or_substituted_pack_fails(self):
        path, _ = self.log('a.jsonl', [b'first', b'second'])
        packed.prepare([path], self.target)
        file = next((self.target/'.log-packs').glob('*.pack'))
        original = file.read_bytes()
        for bad in [original[:-1], b'bad-header'+original[len(packed.PACK_MAGIC):], original[:-8]+b'12345678']:
            file.write_bytes(bad)
            with self.assertRaises((ValueError, OSError)):
                packed.verify(self.target/path.name)
        file.write_bytes(original)
        other = file.with_suffix('.saved');file.rename(other);file.symlink_to(other)
        with self.assertRaises(ValueError):
            packed.verify(self.target/path.name)

    def test_invalid_offsets_lengths_paths_and_full_hash_fail(self):
        path, _ = self.log('a.jsonl', [b'one', b'two'])
        packed.prepare([path], self.target)
        dest = self.target/path.name
        initial = packed.load_manifest(dest)
        for field, value in [('offset',0), ('encoded_bytes',0), ('encoded_bytes',loose.MAX_CHUNK+1025), ('pack',-1), ('pack',True)]:
            changed = json.loads(json.dumps(initial));changed['chunks'][0][field] = value
            dest.write_bytes(packed.encode(changed))
            with self.assertRaises(ValueError):packed.verify(dest)
        for changes in [dict(packs=['../escape']), dict(sha256='0'*64)]:
            dest.write_bytes(packed.encode(dict(initial, **changes)))
            with self.assertRaises(ValueError):packed.verify(dest)

    def test_full_eof_is_required_for_full_hash_claim(self):
        path, _ = self.log('a.jsonl', [b'first', b'second'])
        packed.prepare([path], self.target)
        with packed.Reader(self.target/path.name) as reader:
            self.assertEqual(reader.read(2), b'fi')
            self.assertFalse(reader.verified)

    def test_no_existing_destination_or_cross_session_reuse(self):
        path, _ = self.log('a.jsonl', [b'hello'])
        self.target.mkdir()
        with self.assertRaises(FileExistsError):packed.prepare([path], self.target)
        other = self.root/'other';other.mkdir();fake = other/path.name;fake.write_bytes(path.read_bytes())
        with self.assertRaises(ValueError):packed.prepare([path, fake], self.root/'new')
        with self.assertRaises(ValueError):packed.prepare([path], self.source/'inside')

    def test_gzip_extra_data_and_expansion_are_rejected(self):
        body = b'a'*100
        chunk = dict(bytes=len(body),sha256=loose.sha(body))
        for encoded in [gzip.compress(body)+b'extra', gzip.compress(body)+gzip.compress(body), gzip.compress(body)[:-1]]:
            with self.assertRaises(ValueError):packed.decode(encoded, chunk)
        with self.assertRaises(ValueError):packed.decode(gzip.compress(body), dict(chunk, bytes=1))


if __name__ == '__main__':
    unittest.main()
