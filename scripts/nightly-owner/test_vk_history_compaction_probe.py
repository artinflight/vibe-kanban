import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zlib

import vk_history_compaction_probe as probe


class HistoryCompaction(unittest.TestCase):
    def test_physical_current_recovers_complete_session_catalog_and_sqlite_references(self):
        db = sqlite3.connect(':memory:')
        db.executescript('CREATE TABLE sessions(id TEXT PRIMARY KEY, native_id TEXT);'
                         'CREATE TABLE processes(id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(id));'
                         "INSERT INTO sessions VALUES('old-session','old-native'),('active-session','active-native');"
                         "INSERT INTO processes VALUES('old-process','old-session'),('active-process','active-session');")
        files = {'state/primary.sqlite': db.serialize(),
                 'vibe/old-session/old-process.jsonl': b'{"Stdout":"entire old turn\\n"}\n',
                 'vibe/active-session/active-process.jsonl': b'{"Stdout":"first turn\\n"}\n',
                 'native/old-native.jsonl': b'{"type":"session_meta"}\n{"type":"response_item"}\n',
                 'native/active-native.jsonl': b'{"type":"session_meta"}\n',
                 'work/dirty.py': b'uncommitted', 'attachments/user.bin': b'original'}
        first, first_objects = probe.pack(files, 'chunk')
        files['native/active-native.jsonl'] += b'{"type":"response_item"}\n'
        second, second_objects = probe.pack(probe.project_stdout(files), 'chunk')
        first.clear()
        first_objects.clear()
        restored = probe.restore_stdout(probe.restore(second, second_objects))
        with tempfile.TemporaryDirectory(prefix='vk-history-restore-') as directory:
            root = Path(directory)
            for key, payload in restored.items():
                path = root / key
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
                self.assertEqual(path.read_bytes(), files[key])
            recovered_db = sqlite3.connect('file:' + str(root / 'state/primary.sqlite') + '?mode=ro', uri=True)
            self.assertEqual(recovered_db.execute('pragma integrity_check').fetchone(), ('ok',))
            self.assertEqual(recovered_db.execute('pragma foreign_key_check').fetchall(), [])
            for process, session, native in recovered_db.execute('SELECT p.id,s.id,s.native_id FROM processes p JOIN sessions s ON p.session_id=s.id'):
                self.assertTrue((root / f'vibe/{session}/{process}.jsonl').is_file())
                self.assertTrue((root / f'native/{native}.jsonl').is_file())
            recovered_db.close()
        db.close()

    def test_reversible_stdout_framing_keeps_noncanonical_and_partial_records(self):
        data = (json.dumps({'Stdout': 'é\\\"\n\t\x00'}, ensure_ascii=False, separators=(',', ':')).encode() + b'\n'
                + b'{ "Stdout" : "noncanonical" }\r\n'
                + b'{"Stderr":"important"}\n' + b'\xffpartial')
        files = {'session/a': data}
        projected = probe.project_stdout(files)
        manifest, objects = probe.pack(projected, 'chunk')
        self.assertEqual(probe.restore_stdout(probe.restore(manifest, objects)), files)

    def test_reversible_stdout_reuses_payload_despite_fragment_boundaries(self):
        payload = b''.join(hashlib.sha256(str(i).encode()).hexdigest().encode() for i in range(2000))
        def wrap(data, width):
            return b''.join(json.dumps({'Stdout': data[p:p+width].decode()}, separators=(',', ':')).encode() + b'\n'
                            for p in range(0, len(data), width))
        files = {'a': wrap(payload, 4096), 'b': wrap(payload, 3997)}
        projected = probe.project_stdout(files)
        measured = probe.measure(projected, 'chunk')
        self.assertLess(measured['unique_raw_bytes'], measured['input_bytes'] * .65)
        self.assertEqual(probe.restore_stdout(projected), files)

    def test_projection_tamper_or_missing_stream_fails(self):
        projected = probe.project_stdout({'a': b'{"Stdout":"abc"}\n'})
        projected['projection/0/stdout'] = b'bad'
        with self.assertRaises(ValueError):
            probe.restore_stdout(projected)
        del projected['projection/0/stdout']
        with self.assertRaises(KeyError):
            probe.restore_stdout(projected)

    def test_exact_bytes_duplicate_records_binary_and_unterminated_tail(self):
        files = {'session/a': b'{"x":1}\r\n' * 100 + b'\x00\xfftail',
                 'session/b': b'{"x":1}\r\n' * 30, 'session/empty': b''}
        for mode in ('record', 'chunk'):
            manifest, objects = probe.pack(files, mode)
            self.assertEqual(probe.restore(manifest, objects), files)
        measured = probe.measure(files, 'record')
        self.assertLess(measured['unique_blocks'], measured['references'])

    def test_independent_next_generation_keeps_entire_old_session_and_append(self):
        old = b'{"tool":"complete"}\n' * 100
        first, first_objects = probe.pack({'closed/old': old, 'active/a': b'first\n'}, 'record')
        second_files = {'closed/old': old, 'active/a': b'first\nsecond\n'}
        second, second_objects = probe.pack(second_files, 'record')
        first.clear()
        first_objects.clear()
        self.assertEqual(probe.restore(second, second_objects), second_files)

    def test_chunk_reuse_despite_changed_wrapper_and_whole_file_hash(self):
        payload = b''.join(hashlib.sha256(str(i).encode()).digest() for i in range(4000))
        files = {'a': b'wrapper one:' + payload + b':end',
                 'b': b'a different wrapper:' + payload + b':another end'}
        measured = probe.measure(files, 'chunk')
        self.assertLess(measured['unique_raw_bytes'], measured['input_bytes'] * .7)
        self.assertTrue(measured['byte_exact_restore'])

    def test_giant_record_is_bounded_and_exact(self):
        files = {'a': b'x' * (probe.MAX_BLOCK * 3) + b'\nlast'}
        for mode in ('record', 'chunk'):
            manifest, objects = probe.pack(files, mode)
            self.assertLessEqual(max(r['bytes'] for r in manifest['files']['a']['blocks']), probe.MAX_BLOCK)
            self.assertEqual(probe.restore(manifest, objects), files)

    def test_missing_corrupt_trailing_and_wrong_object_fail_closed(self):
        manifest, objects = probe.pack({'a': b'first\nsecond\n'}, 'record')
        key = next(iter(objects))
        for bad in (None, b'corrupt', objects[key] + b'trailing', zlib.compress(b'wrong\n')):
            changed = dict(objects)
            if bad is None:
                del changed[key]
            else:
                changed[key] = bad
            with self.assertRaises(ValueError):
                probe.restore(manifest, changed)

    def test_reorder_omit_or_replay_block_fails_file_hash(self):
        manifest, objects = probe.pack({'a': b'first\nsecond\n'}, 'record')
        for refs in (list(reversed(manifest['files']['a']['blocks'])),
                     manifest['files']['a']['blocks'][:1],
                     manifest['files']['a']['blocks'] * 2):
            changed = copy.deepcopy(manifest)
            changed['files']['a']['blocks'] = refs
            with self.assertRaises(ValueError):
                probe.restore(changed, objects)

    def test_path_and_restore_expansion_bounds(self):
        for key in ('../a', '/a', 'a/../b', 'a//b', 'a\\b', './a'):
            with self.assertRaises(ValueError):
                probe.pack({key: b'x'}, 'record')
        manifest, objects = probe.pack({'a': b'x'}, 'record')
        manifest['files']['a']['bytes'] = probe.MAX_BYTES + 1
        with self.assertRaises(ValueError):
            probe.restore(manifest, objects)
        manifest['files']['a']['bytes'] = 1
        key = next(iter(objects))
        objects[key] = zlib.compress(b'x' * 1000000)
        with self.assertRaises(ValueError):
            probe.restore(manifest, objects)


if __name__ == '__main__':
    unittest.main()
