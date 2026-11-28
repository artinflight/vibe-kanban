import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from paired_reader_services import Pair


class FakeSystem:
    def __init__(self):
        self.current = dict(MainPID='42', InvocationID='old', ActiveState='active',
                            FreezerState='running', ControlGroup='/private')
        self.actions = []
        self.residual = False
        self.fail_start = False

    def state(self, _):
        return dict(self.current)

    def action(self, verb, name):
        self.actions.append((verb, name))
        if verb == 'stop':
            self.current.update(MainPID='0', InvocationID='', ActiveState='inactive',
                                ControlGroup='/residual' if self.residual else '')
        elif verb == 'start':
            self.current.update(MainPID='43', InvocationID='new', ActiveState='active', ControlGroup='/private')
            if self.fail_start:
                raise TimeoutError('uncertain dispatch')
        elif verb == 'freeze':
            self.current['FreezerState'] = 'frozen'

    def members(self, _):
        return {43}

    def executable_matches(self, _, sha):
        return [43] if sha == 'a'*64 else []

    def api_ready(self, _):
        return True


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'journal.json'
        self.system = FakeSystem()
        self.roster = {r:dict(unit=r+'.service', port=3456+i, expected_members=1)
                       for i,r in enumerate(('main', 'protected'))}
        self.pair = Pair(self.roster, self.path, lambda:None, system=self.system)
        self.old = self.system.state('main.service')

    def test_foreign_owner_never_stopped(self):
        self.system.current['InvocationID'] = 'other'
        with self.assertRaisesRegex(ValueError, 'owner changed'):
            self.pair.stop('main', self.old)
        self.assertEqual(self.system.actions, [])

    def test_residual_processes_block_restart(self):
        self.system.residual = True
        with self.assertRaisesRegex(ValueError, 'still contains'):
            self.pair.stop('main', self.old)
        with self.assertRaisesRegex(ValueError, 'duplicate start'):
            self.pair.start('main', 'a'*64)
        self.assertEqual([x[0] for x in self.system.actions], ['stop'])

    def test_exact_start_freeze_and_durable_receipts(self):
        self.pair.stop('main', self.old)
        result = self.pair.start('main', 'a'*64)
        self.assertEqual(result['FreezerState'], 'frozen')
        events = json.loads(self.path.read_text())['events']
        self.assertEqual([e['phase'] for e in events], ['stop_intent','stopped',
            'start_intent','start_observed','reader_API_and_executable_verified','freeze_intent','frozen'])
        self.assertEqual([x[0] for x in self.system.actions], ['stop','start','freeze'])

    def test_uncertain_start_receipt_and_no_replay(self):
        self.pair.stop('main', self.old)
        self.system.fail_start = True
        with self.assertRaises(TimeoutError):
            self.pair.start('main', 'a'*64)
        self.assertEqual(self.pair.events[-1]['state']['InvocationID'], 'new')
        self.system.current.update(MainPID='0', ControlGroup='')
        with self.assertRaisesRegex(ValueError, 'never replay'):
            self.pair.start('main', 'a'*64)
        self.assertEqual(sum(v=='start' for v,_ in self.system.actions), 1)

    def test_existing_journal_never_reopened(self):
        with self.assertRaises(FileExistsError):
            Pair(self.roster, self.path, lambda:None, system=self.system)

    def test_wrong_binary_is_not_frozen_or_retried(self):
        self.pair.stop('main', self.old)
        with patch('paired_reader_services.time.monotonic', side_effect=[0,121]):
            with self.assertRaises(TimeoutError):
                self.pair.start('main', 'b'*64)
        self.assertEqual([x[0] for x in self.system.actions], ['stop','start'])


if __name__ == '__main__':
    unittest.main()
