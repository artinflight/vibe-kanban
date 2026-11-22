import unittest
from unittest.mock import patch
import activate_graph_recovery as activate

class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.unit=dict(MainPID='0',ActiveState='inactive',InvocationID='',ControlGroup='')
        self.p=dict(unit=activate.UNIT,authorization_ref='actual operator request',terminal_unit=self.unit,
            old_process={'pid':999999999},serving_units={},operation_root='/not-used',operation='op',
            old_attempt='prior',failure_sha256='digest',batch_override=None,pending_graph={'batch':69})
        self.failure=dict(operation='op',attempt='prior',completed_batches=69)
        self.cp=dict(next_batch=69,completed_batches=69)

    def inspect(self):
        with patch.object(activate,'unit',return_value=self.unit), \
             patch.object(activate,'process_identity',side_effect=FileNotFoundError), \
             patch.object(activate,'read',return_value=self.failure), \
             patch.object(activate,'sha',return_value='digest'), \
             patch.object(activate,'checkpoint',return_value=self.cp), \
             patch.object(activate.subprocess,'run',side_effect=AssertionError('preflight mutated services')):
            return activate.terminal(self.p)

    def test_terminal_preflight_does_not_launch_or_restart_services(self):
        self.assertEqual(self.inspect(),self.cp)

    def test_live_or_different_unit_is_refused(self):
        self.p['unit']='vibe-kanban-native-review-20261015.service'
        with self.assertRaisesRegex(ValueError,'exact finite'):self.inspect()
        self.p['unit']=activate.UNIT;self.unit['MainPID']='12'
        with self.assertRaisesRegex(ValueError,'terminal unit'):self.inspect()

    def test_wrong_failure_or_prefix_is_refused(self):
        self.failure['attempt']='other'
        with self.assertRaisesRegex(ValueError,'failure binding'):self.inspect()
        self.failure['attempt']='prior';self.cp['next_batch']=70
        with self.assertRaisesRegex(ValueError,'failure checkpoint'):self.inspect()

if __name__=='__main__':unittest.main()
