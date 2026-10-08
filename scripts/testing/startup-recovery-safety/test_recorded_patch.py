import unittest
import json

from replay_recorded_patch import replay
from reconcile_recorded_edits import accepted, collect, literal_patches


class RecordedPatchTests(unittest.TestCase):
    def patch(self, body):
        return '*** Begin Patch\n' + body + '\n*** End Patch'

    def test_new_file_and_existing_filename_edit(self):
        files = {'edit': b'before\n'}
        patch = self.patch('*** Update File: /owner/edit\n@@\n-before\n+after\n'
                           '*** Add File: /owner/new\n+unique later bytes')
        self.assertEqual(replay(patch, '/owner', files),
                         {'edit': b'after\n', 'new': b'unique later bytes\n'})
        self.assertEqual(files, {'edit': b'before\n'})

    def test_multiple_hunks_follow_changed_positions(self):
        files = {'edit': b'a\nb\nc\n'}
        patch = self.patch('*** Update File: /owner/edit\n@@\n-a\n+A\n+added\n@@\n-c\n+C')
        self.assertEqual(replay(patch, '/owner', files)['edit'], b'A\nadded\nb\nC\n')

    def test_failed_last_file_preserves_entire_input(self):
        files = {'edit': b'before\n'}
        patch = self.patch('*** Update File: /owner/edit\n@@\n-before\n+after\n'
                           '*** Update File: /owner/missing\n@@\n-old\n+new')
        with self.assertRaises(ValueError):
            replay(patch, '/owner', files)
        self.assertEqual(files, {'edit': b'before\n'})

    def test_ambiguous_context_cannot_certify_bytes(self):
        patch = self.patch('*** Update File: /owner/edit\n@@\n-duplicate\n+after')
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            replay(patch, '/owner', {'edit': b'duplicate\nduplicate\n'})

    def test_scope_escape_and_prefix_collision_rejected(self):
        for name in ['/other/new', '/owner/../new', '/ownerish/new', '/owner//new']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                replay(self.patch('*** Add File: ' + name + '\n+content'), '/owner', {})

    def test_missing_preimage_and_unsupported_operations_rejected(self):
        for body in ['*** Update File: /owner/edit\n@@\n-old\n+new',
                     '*** Delete File: /owner/edit', '*** Add File: /owner/edit\nraw']:
            with self.subTest(body=body), self.assertRaises(ValueError):
                replay(self.patch(body), '/owner', {})

    def test_existing_new_file_cannot_be_overwritten(self):
        with self.assertRaises(ValueError):
            replay(self.patch('*** Add File: /owner/edit\n+lost'), '/owner', {'edit': b'survivor'})

    def test_incomplete_evidence_and_context_free_insertion_rejected(self):
        for patch in ['*** Begin Patch\n*** Add File: /owner/edit\n+new',
                      self.patch('*** Update File: /owner/edit\n@@\n+new')]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                replay(patch, '/owner', {'edit': b'old\n'})

    def test_command_failure_after_patch_does_not_erase_accepted_edit(self):
        self.assertTrue(accepted([
            {'type': 'input_text', 'text': 'Script completed\nOutput:\n'},
            {'type': 'input_text', 'text': '{}'},
            {'type': 'input_text', 'text': '{"exit_code":1,"output":"later test failed"}'}]))

    def test_missing_or_failed_patch_receipt_cannot_certify_edit(self):
        for output in [None, '{}', [{'type': 'input_text', 'text': '{}'}],
                       [{'type': 'input_text', 'text': 'Script failed\n'},
                        {'type': 'input_text', 'text': '{}'}]]:
            with self.subTest(output=output):
                self.assertFalse(accepted(output))

    def test_collect_binds_call_result_and_keeps_parse_failure(self):
        patch = self.patch('*** Add File: /owner/edit\n+unique')
        call = {'timestamp': 'b', 'payload': {'type': 'custom_tool_call',
                'call_id': 'one', 'input': 'await tools.apply_patch(' + json.dumps(patch) + ')'}}
        output = {'payload': {'type': 'custom_tool_call_output', 'call_id': 'one',
                  'output': [{'type': 'input_text', 'text': 'Script completed\n'},
                             {'type': 'input_text', 'text': '{}'}]}}
        raw = (json.dumps(call) + '\nunparseable historical line\n' + json.dumps(output)).encode()
        calls, errors = collect(raw, 'a', 'c')
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]['accepted'])
        self.assertEqual(calls[0]['patch'], patch)
        self.assertEqual(errors[0]['line'], 2)
        self.assertEqual(collect(raw, 'c', 'd')[0], [])

    def test_other_call_result_cannot_authorize_patch(self):
        patch = self.patch('*** Add File: /owner/edit\n+unique')
        call = {'timestamp': 'b', 'payload': {'type': 'custom_tool_call',
                'call_id': 'one', 'input': 'tools.apply_patch(' + json.dumps(patch) + ')'}}
        output = {'payload': {'type': 'custom_tool_call_output', 'call_id': 'another',
                  'output': [{'type': 'input_text', 'text': 'Script completed\n'},
                             {'type': 'input_text', 'text': '{}'}]}}
        calls, _ = collect((json.dumps(call) + '\n' + json.dumps(output)).encode(), 'a', 'c')
        self.assertFalse(calls[0]['accepted'])

    def test_patch_literal_in_unrelated_command_is_not_an_edit(self):
        patch = self.patch('*** Add File: /owner/edit\n+unique')
        self.assertEqual(literal_patches({'input': 'text(' + json.dumps(patch) + ')'}), [])
        self.assertEqual(literal_patches({'input': patch, 'name': 'exec'}), [])


if __name__ == '__main__':
    unittest.main()
