"""Check deployed ChatGPT creation code without starting a workspace or provider.

The explicit connector path is required so a stale snapshot cannot masquerade as
live evidence. Only the creation function is loaded; network is mocked and counted.
"""
import ast
import importlib.util
import os
import pathlib
import sys
import unittest
import uuid
from unittest.mock import Mock

CONNECTOR = os.environ.get('VK_CONNECTOR_SOURCE')


@unittest.skipUnless(CONNECTOR, 'Set VK_CONNECTOR_SOURCE to verify an installed connector')
class ConnectorPreflight(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(CONNECTOR)
        self.previous = sys.modules.get('workspace_issue_context')
        spec = importlib.util.spec_from_file_location('workspace_issue_context', self.root/'workspace_issue_context.py')
        self.context = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.context
        spec.loader.exec_module(self.context)
        source = ast.parse((self.root/'adapter.py').read_text())
        function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'codex_local_start')
        self.read = Mock()
        self.post = Mock(side_effect=AssertionError('Unexpected POST/provider side effect'))
        namespace = {'http_get':self.read, 'urllib':Mock(request=Mock(Request=self.post))}
        exec(compile(ast.Module(body=[function],type_ignores=[]), str(self.root/'adapter.py'), 'exec'), namespace)
        self.start = namespace['codex_local_start']
        launcher = ast.parse((self.root/'launcher.py').read_text())
        launch = next(node for node in launcher.body if isinstance(node, ast.FunctionDef) and node.name == 'start')
        claude_namespace = {'SELECTION':frozenset(('variant','model_id','reasoning_id','permission_policy'))}
        exec(compile(ast.Module(body=[launch],type_ignores=[]), str(self.root/'launcher.py'), 'exec'), claude_namespace)
        self.claude_start = claude_namespace['start']
        self.project, self.issue = str(uuid.uuid4()), str(uuid.uuid4())

    def tearDown(self):
        if self.previous is None:
            sys.modules.pop('workspace_issue_context', None)
        else:
            sys.modules['workspace_issue_context'] = self.previous

    def rejected(self, args, expected):
        with self.assertRaises(self.context.IssueContextError) as result:
            self.start(args)
        self.assertEqual(result.exception.detail['code'], expected)
        self.post.assert_not_called()

    def test_missing_ids_reject_before_even_a_lookup(self):
        for args in [{}, {'project_id':self.project}, {'issue_id':self.issue}]:
            self.rejected(args,'workspace_issue_ids_missing')
        api = Mock(http_get=self.read, post_fixed=self.post)
        with self.assertRaises(self.context.IssueContextError):
            self.claude_start(api, {'executor':'CLAUDE_CODE'})
        self.read.assert_not_called()
        self.post.assert_not_called()

    def test_wrong_project_issue_and_absence_reject_before_post(self):
        for rows in [[], [{'id':self.issue, 'project_id':str(uuid.uuid4())}]]:
            self.read.return_value = {'issues':rows}
            self.rejected({'project_id':self.project, 'issue_id':self.issue}, 'workspace_issue_not_verified')

    def test_lookup_failure_is_not_retried_or_treated_as_missing(self):
        self.read.side_effect = OSError('synthetic unavailable service')
        self.rejected({'project_id':self.project, 'issue_id':self.issue}, 'workspace_issue_lookup_unavailable')
        self.read.assert_called_once()

    def test_valid_context_requires_exact_scoped_evidence(self):
        self.read.return_value = {'issues':[{'id':self.issue,'project_id':self.project}]}
        context = self.context.require_issue_context({'project_id':self.project, 'issue_id':self.issue}, self.read)
        self.assertEqual(context, {'project_id':self.project, 'issue_id':self.issue})
        self.read.assert_called_once_with('/v1/fallback/issues?project_id='+self.project)
        self.post.assert_not_called()
