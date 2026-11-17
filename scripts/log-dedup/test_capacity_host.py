"""Optional exact retained-host integration; no RPC/service/production actions.

Set VK_LOG_DEDUP_HOST_SOURCE to the retained source for production qualification.
The portable release tests remain mandatory without private host inputs.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import unittest

import prepare_capacity_host
import test_capacity_release


class ReachedFreeze(Exception):
    pass


@unittest.skipUnless(os.environ.get('VK_LOG_DEDUP_HOST_SOURCE'), 'Retained private host not supplied')
class HostIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_capacity_release.CapacityReleaseTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.boundary = self.fixture.boundary
        self.namespace = {'__name__': 'offline_exact_host'}
        source = prepare_capacity_host.patched_source(
            Path(os.environ['VK_LOG_DEDUP_HOST_SOURCE']).read_bytes())
        exec(compile(source, 'patched-host', 'exec'), self.namespace)
        helper = self.fixture.root / 'capacity_release.py'
        helper.write_bytes(Path(__file__).with_name('capacity_release.py').read_bytes())
        helper.chmod(0o400)
        self.boundary.config['capacity_release_source'] = dict(
            path=str(helper), sha256=hashlib.sha256(helper.read_bytes()).hexdigest())
        self.boundary.config['old_units'] = {
            self.namespace[name]: dict(MainPID='fixture', InvocationID='fixture')
            for name in ['MAIN', 'READER', 'PROXY']}
        self.boundary.quiet = lambda: {}
        self.boundary.observe_review = lambda: dict(tables={})
        self.boundary.data['review_projection_sha256'] = hashlib.sha256(b'{}').hexdigest()

    def test_exact_freeze_method_survives_lost_release_response(self):
        def request(origin, token, action='status', receipt=None):
            if not self.fixture.calls:
                self.fixture.calls.append(action)
                return dict(protocolVersion=1, owned=True, state=self.fixture.state)
            return self.fixture.rpc(origin, token, action, receipt)
        self.boundary.rpc.request = request
        def stop_before_real_freeze(name):
            raise ReachedFreeze()
        self.namespace['unit'] = stop_before_real_freeze
        with self.assertRaises(ReachedFreeze):
            self.namespace['Boundary'].freeze_boundary(self.boundary)
        self.assertEqual(self.fixture.calls, ['status', 'release', 'status'])
        self.assertEqual(self.boundary.data['released']['state'], self.fixture.state)

    def setup_recovery(self):
        self.fixture.run_release()
        self.boundary.data = json.loads(json.dumps(self.fixture.records[0][1]))
        self.boundary.data.update(frozen={}, route_changed=True, stopped=[], holds=[{}])
        self.boundary.operation = 'fixture'
        self.boundary.fence_context = None
        self.boundary.recovery_lease_fd = None
        self.boundary.config['route_bytes_b64'] = base64.b64encode(b'{}').decode()
        route = self.fixture.root / 'route'
        route.write_text('maintenance')
        self.boundary.config['route_path'] = str(route)
        self.namespace['ROOT'] = self.fixture.root
        self.namespace['unit'] = lambda name: dict(MainPID='fixture', InvocationID='fixture')
        def recovered(**kwargs):
            self.assertIsNotNone(self.boundary.recovery_lease_fd)
            self.assertEqual(self.boundary.data['released']['state'], self.fixture.state)
            os.close(self.boundary.recovery_lease_fd)
            self.boundary.recovery_lease_fd = None
            return {'entered_capacity_reacquisition_path': True}
        self.boundary.release_boundary = recovered

    def test_journal_recovery_reconciles_before_no_release_branch(self):
        self.setup_recovery()
        result = self.namespace['Boundary'].recover_boundary(
            self.boundary, acceptance=None, acceptance_pin=None)
        self.assertTrue(result['entered_capacity_reacquisition_path'])
        self.assertEqual(self.fixture.calls.count('release'), 1)

    def test_journal_recovery_never_reopens_ingress_for_unknown_owner(self):
        self.setup_recovery()
        self.fixture.reply = dict(protocolVersion=1, owned=True, state=self.fixture.state)
        with self.assertRaisesRegex(ValueError, 'unresolved or foreign'):
            self.namespace['Boundary'].recover_boundary(
                self.boundary, acceptance=None, acceptance_pin=None)
        self.assertIsNone(self.boundary.recovery_lease_fd)
        self.assertIsNone(self.boundary.data['released'])


if __name__ == '__main__':
    unittest.main()
