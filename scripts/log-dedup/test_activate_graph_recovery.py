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

class InstalledActivationTests(TerminalTests):
    def setUp(self):
        super().setUp();self.p.pop('pending_graph')
        self.p['recovered_installed']={'path':'/recovered','sha256':'proof'}
        self.cp.update(next_batch=70,completed_batches=70,checkpoint_sha256='checkpoint')
        self.proof=dict(verified=True,operation='op',no_conversion_or_dispatch_replayed=True,
            all_prior_epochs_preserved=True,batch=69,checkpoint=dict(checkpoint_sha256='checkpoint'),
            before=dict(pins=[dict(path='/not-used/FAILURE.private.json',sha256='digest')]))

    def inspect(self):
        with patch.object(activate,'unit',return_value=self.unit), \
             patch.object(activate,'process_identity',side_effect=FileNotFoundError), \
             patch.object(activate,'read',side_effect=lambda path,*a:self.proof if str(path)=='/recovered' else self.failure), \
             patch.object(activate,'sha',return_value='digest'), \
             patch.object(activate,'verify_pins'), \
             patch.object(activate,'checkpoint',return_value=self.cp):
            return activate.terminal(self.p)

    def test_wrong_failure_or_prefix_is_refused(self):
        self.cp['completed_batches']=71
        with self.assertRaisesRegex(ValueError,'installed checkpoint'):self.inspect()

    def test_recovery_cannot_hide_rewritten_failure_or_checkpoint(self):
        self.proof['before']['pins'][0]['sha256']='changed'
        with self.assertRaisesRegex(ValueError,'installed checkpoint'):self.inspect()

    def test_two_recovery_routes_are_refused(self):
        self.p['pending_graph']={'batch':69}
        with self.assertRaisesRegex(ValueError,'exactly one'):self.inspect()

if __name__=='__main__':unittest.main()
