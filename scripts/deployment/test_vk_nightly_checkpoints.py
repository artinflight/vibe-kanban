"""Tiny metadata fixtures: no source files, archive payloads or native actions."""
import copy
import json
import unittest
from unittest.mock import patch

import vk_nightly_checkpoints as c


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def seal(name, number=1):
    return dict(event='native_file_component_seal', name=name, bytes=16,
                sha256=str(number) * 64, file_identity=[99, number, 16, 100])


def sql(source, name, number):
    native = dict(seal(name, number), event='native_SQL_seal', integrity='ok',
                  schema_sha256='a' * 64)
    independent = {k: native[k] for k in ('name', 'bytes', 'sha256', 'integrity', 'schema_sha256')}
    independent['event'] = 'Linux_SQL_reopen_proof'
    independent['same_image_independently_reopened'] = True
    return dict(event='SQL_image_verified', source=source, native=native,
                Linux_reopen=independent)


class Checkpoints(unittest.TestCase):
    def setUp(self):
        self.root = 'B:/vk-backups/fixture'
        self.file_root = self.root + '/files'
        self.sql_root = self.root + '/fresh-sql'
        self.file_cfg = {'native_root': self.file_root}
        older = sql('/fixture/older.sqlite', 'old.sqlite', 3)
        fresh = sql('/fixture/new.sqlite', 'fresh.sqlite', 4)
        self.sql_cfg = dict(
            native_root=self.sql_root,
            pending_fresh_SQL_bounds={'/fixture/new.sqlite': {}},
            retained_verified_components={'/fixture/older.sqlite': dict(
                source='/fixture/older.sqlite', proof=older,
                native_identity=older['native']['file_identity'],
                native_path=self.root + '/old-sql/old.sqlite', seal_sha256='9' * 64)},
            SQL_snapshot_observer_epoch_binding_sha256='8' * 64,
            SQL_snapshot_observer_lower_bound_sequence=7)
        self.sql_result = dict(
            OS_SSD_payload_spool=0, native_root=self.sql_root,
            native=dict(event='current_SQL_component_complete',
                        schema='T17-current-SQL-component-v1',
                        source_images_consistent_and_independently_reopened=True,
                        SQL_images=[older, fresh]),
            terminal=dict(event='SQL_owned_children_terminal', full_backup_accepted=False))
        archive, records = seal('part.zip', 1), seal('part.jsonl', 2)
        self.rows = [
            dict(event='actual_SQL_dispatch', worker_sha256='7' * 64,
                 dispatch=dict(execution_config_sha256='', destination_root=self.file_root)),
            archive, records,
            dict(event='Linux_selected_files_decoded', archive=copy.deepcopy(archive),
                 records=copy.deepcopy(records), members=2, decoded_source_file_bytes=123,
                 all_member_hashes_and_Linux_metadata_match=True,
                 exact_Linux_metadata_in_sealed_records_and_ZIP_comments=True,
                 encoding='zip-member'),
            dict(event='current_SQL_phase_failed', child_terminal=True,
                 Linux_bridge_terminal=True, full_backup_accepted=False)]

    def inputs(self):
        file_cfg = encoded(self.file_cfg)
        self.rows[0]['dispatch']['execution_config_sha256'] = c.sha256(file_cfg)
        events = b''.join(encoded(row) + b'\n' for row in self.rows)
        inputs = dict(file_receipts=events, file_config=file_cfg,
                      sql_result=encoded(self.sql_result), sql_config=encoded(self.sql_cfg),
                      file_root=self.file_root, sql_root=self.sql_root, backup_prefix=self.root)
        inputs['pins'] = {name: c.sha256(inputs[name]) for name in
                          ('file_receipts', 'file_config', 'sql_result', 'sql_config')}
        inputs['pins']['file_worker'] = '7' * 64
        return inputs

    def adopt(self):
        return c.adopt(**self.inputs())

    def test_failed_parent_retains_only_proved_components_and_original_epochs(self):
        value = self.adopt()
        self.assertEqual(value['file_component_count'], 1)
        self.assertEqual(value['sql_image_count'], 2)
        self.assertEqual(value['verified_file_raw_bytes'], 123)
        self.assertEqual(value['sql_images']['/fixture/older.sqlite']['native_path'],
                         self.root + '/old-sql/old.sqlite')
        self.assertEqual(value['sql_images']['/fixture/new.sqlite']['native_path'],
                         self.sql_root + '/fresh.sqlite')
        self.assertEqual(value['sql_observer_lower_bound_sequence'], 7)
        for name in ('current_source_qualified', 'full_backup_accepted',
                     'writer_fence_verified', 'schedule_adoption_authorized'):
            self.assertIs(value[name], False)
        self.assertEqual(value['payload_bytes_copied'], 0)

    def test_repeated_adoption_is_identical_and_never_opens_or_copies_payload(self):
        args = self.inputs()
        with patch('builtins.open', side_effect=AssertionError('unexpected filesystem access')):
            self.assertEqual(c.adopt(**args), c.adopt(**args))

    def test_unpaired_native_seal_is_preserved_but_not_adopted(self):
        self.rows.insert(-1, seal('unfinished.zip', 5))
        self.assertEqual(self.adopt()['file_component_count'], 1)

    def test_missing_or_changed_native_seal_rejects_independent_boolean(self):
        self.rows[1]['sha256'] = '6' * 64
        with self.assertRaisesRegex(ValueError, 'matching prior native seals'):
            self.adopt()

    def test_independent_proof_before_native_seal_is_rejected(self):
        self.rows[1], self.rows[3] = self.rows[3], self.rows[1]
        with self.assertRaises(ValueError):
            self.adopt()

    def test_duplicate_component_proof_is_rejected(self):
        self.rows.insert(-1, copy.deepcopy(self.rows[3]))
        with self.assertRaisesRegex(ValueError, 'duplicate independent'):
            self.adopt()

    def test_native_seals_without_independent_decode_are_not_accepted(self):
        del self.rows[3]
        self.assertEqual(self.adopt()['file_component_count'], 0)

    def test_live_or_nonterminal_children_cannot_be_adopted(self):
        for key in ('child_terminal', 'Linux_bridge_terminal'):
            with self.subTest(key=key):
                self.rows[-1][key] = False
                with self.assertRaisesRegex(ValueError, 'must be terminal'):
                    self.adopt()
                self.rows[-1][key] = True

    def test_receipt_tampering_is_rejected_before_adoption(self):
        args = self.inputs()
        args['file_receipts'] += b' '
        with self.assertRaises(ValueError):
            c.adopt(**args)

    def test_truncated_jsonl_is_rejected_even_with_matching_new_pin(self):
        args = self.inputs()
        args['file_receipts'] = args['file_receipts'][:-1]
        args['pins']['file_receipts'] = c.sha256(args['file_receipts'])
        with self.assertRaises(ValueError):
            c.adopt(**args)

    def test_source_configuration_and_worker_binding_cannot_be_substituted(self):
        self.rows[0]['worker_sha256'] = '6' * 64
        with self.assertRaisesRegex(ValueError, 'worker/configuration/destination'):
            self.adopt()

    def test_exact_expected_destination_is_external_to_receipt(self):
        args = self.inputs()
        args['file_root'] = self.root + '/other'
        with self.assertRaisesRegex(ValueError, 'root differs'):
            c.adopt(**args)

    def test_E_OS_paths_and_traversals_are_rejected(self):
        for raw in ('E:/vk-backups/a', '/tmp/cache', 'B:/vk-backups/../a',
                    'B:/vk-backups/NUL', 'B:/vk-backups/file:stream', 'B:/vk-backups/trailing.'):
            with self.subTest(path=raw), self.assertRaises(ValueError):
                c.b_path(raw)

    def test_SQL_retained_identity_and_carrier_are_not_relabelled(self):
        previous = self.sql_cfg['retained_verified_components']['/fixture/older.sqlite']
        previous['native_identity'] = [99, 55, 16, 100]
        with self.assertRaisesRegex(ValueError, 'carrier/proof identity'):
            self.adopt()

    def test_SQL_hash_schema_and_integrity_require_actual_pair(self):
        row = self.sql_result['native']['SQL_images'][1]
        for key, value in [('sha256', '0' * 64), ('schema_sha256', 'b' * 64),
                           ('integrity', 'failed'), ('same_image_independently_reopened', False)]:
            with self.subTest(key=key):
                old = row['Linux_reopen'][key]
                row['Linux_reopen'][key] = value
                with self.assertRaises(ValueError):
                    self.adopt()
                row['Linux_reopen'][key] = old

    def test_missing_required_SQL_cannot_be_hidden_by_completed_parent_flag(self):
        self.sql_result['native']['SQL_images'].pop()
        with self.assertRaisesRegex(ValueError, 'cohort incomplete'):
            self.adopt()

    def test_unknown_and_duplicate_SQL_source_are_rejected(self):
        self.sql_result['native']['SQL_images'].append(
            copy.deepcopy(self.sql_result['native']['SQL_images'][1]))
        with self.assertRaisesRegex(ValueError, 'duplicate SQL'):
            self.adopt()

    def test_original_SQL_sequence_cannot_be_reset_or_boolean(self):
        self.sql_cfg['SQL_snapshot_observer_lower_bound_sequence'] = True
        with self.assertRaisesRegex(ValueError, 'original SQL journal anchor'):
            self.adopt()

    def test_duplicate_control_keys_and_nonfinite_metadata_are_rejected(self):
        for raw in (b'{"native_root":"a","native_root":"b"}', b'{"value":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                c.authenticated(raw, c.sha256(raw))

    def test_oversized_metadata_is_rejected_without_parsing(self):
        with patch.object(c, 'MAX_CONTROL', 10):
            with self.assertRaisesRegex(ValueError, 'bounded'):
                c.authenticated(b'x' * 11, '0' * 64)

    def test_wrapper_without_event_preserves_verified_nested_proofs_and_old_epoch(self):
        row = self.sql_result['native']['SQL_images'][0]
        del row['event']
        row['capture'] = dict(source_epoch='old-epoch', sequence_start=1, sequence_end=3)
        self.sql_cfg['retained_verified_components']['/fixture/older.sqlite']['proof'] = row
        value = self.adopt()['sql_images']['/fixture/older.sqlite']
        self.assertEqual(value['capture_epoch']['source_epoch'], 'old-epoch')
        self.assertIs(value['source_epoch_may_differ_from_current_run'], True)
        self.assertIs(value['current_source_qualified'], False)

    def test_missing_nested_independent_event_is_not_a_schema_upgrade(self):
        del self.sql_result['native']['SQL_images'][1]['Linux_reopen']['event']
        with self.assertRaises(ValueError):
            self.adopt()

    def test_false_or_mismatched_component_bounds_fail(self):
        for value in (True, -1, 0):
            row = seal('part.zip')
            row['bytes'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.seal(row)


class TypedComponentRowsTests(unittest.TestCase):
    def setUp(self):
        self.meta = dict(mode=0o644,uid=1000,gid=1000,mtime_ns=123,xattrs={})
        self.rows = [dict(action='directory',path='/source',metadata=self.meta),
                     dict(action='file',path='/source/a',metadata=self.meta,bytes=3,sha256='a'*64),
                     dict(action='symlink',path='/source/b',metadata=self.meta,target='a')]

    def component(self, rows=None):
        rows = self.rows if rows is None else rows
        raw = b''.join((json.dumps(row)+'\n').encode() for row in rows)
        def seal(name, size, sha):
            return dict(name=name,bytes=size,sha256=sha,file_identity=[1,2,size,123])
        value = dict(encoding='zip-member',members=len(rows),raw_bytes=3,
                     archive=seal('verified.zip',123,'f'*64),
                     records=seal('verified.jsonl',len(raw),c.sha256(raw)))
        return value, raw

    def test_complete_records_produce_typed_recipes_without_payload_read(self):
        component, raw = self.component()
        rows = c.typed_component_rows(component, raw, layer='retained-original')
        self.assertEqual(len(rows),3)
        member = rows[1][1]
        self.assertEqual(member['segments'][0]['member'],'source/a')
        self.assertEqual(member['segments'][0]['encoded_sha256'],'f'*64)
        self.assertFalse(member['component_provenance']['current_source_qualified'])
        self.assertFalse(member['component_provenance']['parent_backup_accepted'])
        self.assertEqual(rows,c.typed_component_rows(component,raw,layer='retained-original'))

    def test_hash_count_rawbytes_and_component_encoding_tamper_refused(self):
        component, raw = self.component()
        for updates in (dict(members=4),dict(raw_bytes=4),dict(encoding='raw'),dict(members=True)):
            with self.assertRaises(ValueError): c.typed_component_rows(dict(component,**updates),raw,layer='retained')
        with self.assertRaises(ValueError): c.typed_component_rows(component,raw+b' ',layer='retained')

    def test_duplicate_unsorted_paths_and_invalid_Linux_metadata_refused(self):
        for rows in (self.rows+self.rows, list(reversed(self.rows)),
                     [dict(self.rows[1],metadata=dict(self.meta,uid=-1))],
                     [dict(self.rows[1],path='/source/../escape')]):
            component,raw=self.component(rows)
            with self.assertRaises(ValueError): c.typed_component_rows(component,raw,layer='retained')

    def test_hardlink_resolution_is_explicitly_deferred(self):
        rows=self.rows+[dict(action='hardlink',path='/source/c',metadata=self.meta,target='source/a')]
        component,raw=self.component(rows)
        link=c.typed_component_rows(component,raw,layer='retained')[-1][1]
        self.assertTrue(link['hardlink_target_resolution_required'])
        self.assertNotIn('sha256',link)

    def test_unknown_action_missing_file_hash_and_bad_xattrs_refused(self):
        bad=[dict(self.rows[1],action='socket'),dict(self.rows[1],sha256='bad'),
             dict(self.rows[1],metadata=dict(self.meta,xattrs={'user.example':'not-base64!'}))]
        for row in bad:
            component,raw=self.component([row])
            with self.assertRaises(ValueError): c.typed_component_rows(component,raw,layer='retained')


if __name__ == '__main__':
    unittest.main()
