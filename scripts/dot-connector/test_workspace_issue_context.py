import hashlib
import unittest
from unittest.mock import Mock
import uuid

from workspace_issue_context import require_issue_context
from prepare_workspace_issue import prepare

PROJECT, ISSUE = str(uuid.uuid4()), str(uuid.uuid4())


class ContextTests(unittest.TestCase):
    def test_valid_issue_uses_only_fixed_read_and_does_not_copy_private_prompt(self):
        read = Mock(return_value={'issues': [{'id': ISSUE, 'project_id': PROJECT}]})
        args = {'project_id': PROJECT, 'issue_id': ISSUE, 'prompt': 'private prompt'}
        self.assertEqual({'project_id': PROJECT, 'issue_id': ISSUE}, require_issue_context(args, read))
        read.assert_called_once_with('/v1/fallback/issues?project_id='+PROJECT)
        self.assertEqual('private prompt', args['prompt'])

    def test_missing_link_never_reads_or_starts(self):
        for args in ({}, {'project_id': PROJECT}, {'issue_id': ISSUE},
                     {'project_id': PROJECT, 'issue_id': None}):
            read = Mock()
            with self.assertRaisesRegex(ValueError, 'No workspace or agent was started'):
                require_issue_context(args, read)
            read.assert_not_called()

    def test_invalid_identity_never_reads(self):
        for value in ('bad', True, 42, '../issue'):
            read = Mock()
            with self.assertRaises(ValueError):
                require_issue_context({'project_id': PROJECT, 'issue_id': value}, read)
            read.assert_not_called()

    def test_cross_project_missing_or_malformed_evidence_fails_closed(self):
        for page in ({'issues': []}, {'issues': [{'id': ISSUE, 'project_id': str(uuid.uuid4())}]},
                     {'issues': [{'id': str(uuid.uuid4()), 'project_id': PROJECT}]},
                     {'issues': [None]}, {'issues': None}, {}, []):
            with self.assertRaises(ValueError):
                require_issue_context({'project_id': PROJECT, 'issue_id': ISSUE}, Mock(return_value=page))

    def test_read_failure_never_returns_approval(self):
        with self.assertRaises(TimeoutError):
            require_issue_context({'project_id': PROJECT, 'issue_id': ISSUE}, Mock(side_effect=TimeoutError))

    def test_exact_preparation_preserves_other_functions_and_rejects_wrong_pin(self):
        fixture = b'''def local_start(args):
    allowed = set(args)
    if set(args)-allowed: raise ValueError("Unknown workspace argument")
    return "start"
class Adapter:
    def handle(self, schema):
        schema["required"]=list(set(schema.get("required",[])+["prompt"]))
        return "When linking issue_id, project_id is required."
def unrelated(): return "preserve"
'''
        candidate = prepare(fixture, hashlib.sha256(fixture).hexdigest())
        self.assertIn(b'require_issue_context(args, http_get)', candidate)
        self.assertIn(b'["prompt","project_id","issue_id"]', candidate)
        with self.assertRaises(ValueError): prepare(fixture, '0'*64)
        with self.assertRaises(ValueError): prepare(candidate, hashlib.sha256(candidate).hexdigest())


if __name__ == '__main__': unittest.main()
