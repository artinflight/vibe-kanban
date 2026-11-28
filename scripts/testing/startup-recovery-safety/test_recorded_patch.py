import unittest
import json
import contextlib
import hashlib
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch as mock_patch

from replay_recorded_patch import replay
from reconcile_recorded_edits import bound_result, collect, recorded_program, evidence_verified
from reconcile_recorded_edits import main


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

    def program(self, suffix=''):
        patch = self.patch('*** Add File: /owner/edit\n+unique')
        return {'name': 'exec', 'input': 'text(await tools.apply_patch(' + json.dumps(patch) + '));' + suffix}

    def receipt(self, *results):
        return [{'type': 'input_text', 'text': 'Script completed\nOutput:\n'},
                {'type': 'input_text', 'text': '{}'}] + [
                {'type': 'input_text', 'text': json.dumps(result)} for result in results]

    def transcript(self, payload=None, output=None, extra=(), output_first=False):
        call = {'timestamp': 'b', 'payload': {'type': 'custom_tool_call', 'call_id': 'one',
                                            **(payload or self.program())}}
        result = {'payload': {'type': 'custom_tool_call_output', 'call_id': 'one',
                              'output': output if output is not None else self.receipt()}}
        rows = [result, call] if output_first else [call, result]
        rows.extend(extra)
        return '\n'.join(json.dumps(row) for row in rows).encode()

    def test_command_failure_after_bound_patch_is_not_patch_failure(self):
        statements = recorded_program(self.program('text(await tools.exec_command({"cmd":"test"}));'))
        result = {'chunk_id': 'abc', 'wall_time_seconds': 1, 'exit_code': 1, 'output': 'test failed'}
        self.assertEqual(bound_result(statements, self.receipt(result)), (True, False))

    def test_multiple_patches_with_one_receipt_fail_closed(self):
        payload = self.program()
        payload['input'] *= 2
        calls, _ = collect(self.transcript(payload), 'a', 'c')
        self.assertFalse(calls[0]['accepted'])
        self.assertIn('sole first', calls[0]['reason'])

    def test_comments_branches_strings_and_concurrency_are_unresolved(self):
        source = self.program()['input']
        for text in ['// ' + source, '/* ' + source + ' */', 'if (false) {' + source + '}',
                     'text(' + json.dumps(source) + ');', 'Promise.all([' + source + ']);',
                     source + '// unsupported trailing code', 'function unused() {' + source + '}']:
            with self.subTest(text=text):
                calls, _ = collect(self.transcript({'name': 'exec', 'input': text}), 'a', 'c')
                self.assertEqual(len(calls), 1)
                self.assertFalse(calls[0]['accepted'])

    def test_extra_missing_reordered_or_non_tool_slots_are_unresolved(self):
        statements = recorded_program(self.program('text(await tools.exec_command({"cmd":"test"}));'))
        result = {'chunk_id': 'abc', 'wall_time_seconds': 0.1, 'exit_code': 0, 'output': ''}
        valid = self.receipt(result)
        for output in [None, '{}', self.receipt(), self.receipt(result, result),
                       [valid[0], valid[2], valid[1]], self.receipt({}),
                       self.receipt({'exit_code': 0, 'output': '{}'}),
                       [{'type': 'image', 'text': 'Script completed\n'}, *valid[1:]]]:
            with self.subTest(output=output):
                self.assertEqual(bound_result(statements, output), (False, False))

    def test_rejected_patch_requires_exact_receipt_and_program(self):
        failed = [{'type': 'input_text', 'text': 'Script failed\n'},
                  {'type': 'input_text', 'text': 'Script error:\napply_patch verification failed: absent context'}]
        calls, _ = collect(self.transcript(output=failed), 'a', 'c')
        self.assertFalse(calls[0]['accepted'])
        self.assertTrue(calls[0]['failed_verification'])
        failed[1]['text'] = 'later command printed apply_patch verification failed:'
        calls, _ = collect(self.transcript(output=failed), 'a', 'c')
        self.assertFalse(calls[0]['failed_verification'])

    def test_unique_ordered_identity_is_required(self):
        call = {'timestamp': 'outside', 'payload': {'type': 'custom_tool_call', 'call_id': 'one', **self.program()}}
        result = {'payload': {'type': 'custom_tool_call_output', 'call_id': 'one', 'output': self.receipt()}}
        for raw in [self.transcript(extra=[call]), self.transcript(extra=[result]),
                    self.transcript(output_first=True),
                    self.transcript().replace(b'"call_id": "one", "output"', b'"call_id": "other", "output"')]:
            with self.subTest(raw=raw):
                calls, _ = collect(raw, 'a', 'c')
                self.assertFalse(calls[0]['accepted'])

    def test_parse_failure_prevents_pass_even_outside_window(self):
        raw = b'not-json\n' + self.transcript()
        calls, errors = collect(raw, 'a', 'c')
        self.assertTrue(calls[0]['accepted'])
        self.assertEqual(errors[0]['line'], 1)
        self.assertFalse(evidence_verified([{'verified': True}], [], errors))
        self.assertFalse(evidence_verified([{'verified': True}], [{'line': 1}], []))
        self.assertTrue(evidence_verified([{'verified': True}], [], []))

    def test_cli_returns_failure_despite_matching_files_when_transcript_has_parse_error(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('VK_SAFETY_TEST_ROOT')) as directory:
            owner = Path(directory)
            (owner / 'edit').write_bytes(b'unique\n')
            transcript = owner / 'transcript.jsonl'
            raw = b'preserved parse failure\n' + self.transcript()
            transcript.write_bytes(raw)
            args = SimpleNamespace(transcript=transcript, sha256=hashlib.sha256(raw).hexdigest(),
                                   owner=owner, source_prefix='/owner', base_commit='base',
                                   after='a', before='c')
            output = io.StringIO()
            with mock_patch('argparse.ArgumentParser.parse_args', return_value=args), \
                    mock_patch('subprocess.check_output', return_value='base\n'), \
                    mock_patch('subprocess.run', return_value=SimpleNamespace(returncode=1)), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(main(), 1)
            result = json.loads(output.getvalue())
            self.assertTrue(result['files'][0]['verified'])
            self.assertEqual(result['accepted_patch_calls'], 1)
            self.assertFalse(result['recorded_edits_verified'])

    def test_wrong_tool_and_unprinted_patch_cannot_certify(self):
        for payload in [{'name': 'exec', 'input': self.program()['input'].replace('text(await ', 'await ')},
                        {'name': 'other', 'input': self.program()['input']}]:
            with self.subTest(payload=payload):
                calls, _ = collect(self.transcript(payload), 'a', 'c')
                self.assertFalse(calls[0]['accepted'])

    def test_missing_timestamp_cannot_silently_exclude_patch_from_scope(self):
        raw = self.transcript().replace(b'"timestamp": "b", ', b'')
        calls, errors = collect(raw, 'a', 'c')
        self.assertEqual(calls, [])
        self.assertEqual(errors[0]['reason'], 'invalid call timestamp; scope uncertain')
        self.assertFalse(evidence_verified([{'verified': True}], [], errors))

    def test_js_identifier_keys_require_literal_values_and_unique_keys(self):
        valid = self.program('text(await tools.exec_command({cmd: "test", yield_time_ms: 1000}));')
        self.assertEqual(len(recorded_program(valid)), 2)
        for argument in ['{cmd: doWork()}', '{...options}', '{[key]: "test"}',
                         '{cmd: "first", cmd: "second"}', '{cmd: `template`}',
                         '{cmd: "test" /* comment */}']:
            with self.subTest(argument=argument), self.assertRaises(ValueError):
                recorded_program(self.program('text(await tools.exec_command(' + argument + '));'))

    def test_later_error_cannot_be_assigned_to_first_patch(self):
        statements = recorded_program(self.program('text(await tools.exec_command({cmd: "test"}));'))
        receipt = [{'type': 'input_text', 'text': 'Script failed\n'},
                   {'type': 'input_text', 'text': 'Script error:\napply_patch verification failed: ambiguous origin'}]
        self.assertEqual(bound_result(statements, receipt), (False, False))

    def test_window_does_not_resume_or_execute_transcript(self):
        raw = self.transcript()
        self.assertEqual(collect(raw, 'c', 'd')[0], [])
        calls, errors = collect(raw, 'a', 'c')
        self.assertEqual(errors, [])
        self.assertTrue(calls[0]['accepted'])
        self.assertIn('patch_sha256', calls[0])
        self.assertIn('result_sha256', calls[0])


if __name__ == '__main__':
    unittest.main()
