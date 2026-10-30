from pathlib import Path
import hashlib
import tempfile
import unittest
from vk_restart_ingress_hold import install,release,verify


class IngressHold(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.temp.cleanup)
        path=Path(self.temp.name)/'fixture.service.d'/'owned.conf';body='[Unit]\nRefuseManualStart=yes\n'
        self.row=dict(unit='fixture.service',path=str(path),body=body,sha256=hashlib.sha256(body.encode()).hexdigest())
        self.live={'RefuseManualStart':'no'};self.events=[]
    def state(self,_):return self.live
    def refresh(self):self.live={'RefuseManualStart':'yes'}
    def test_durable_intent_precedes_create_and_release_only_own_file(self):
        def record(phase,row):self.assertFalse(Path(row['path']).exists());self.events.append(phase)
        install([self.row],record=record,state=self.state,refresh=self.refresh);verify([self.row],state=self.state)
        self.assertEqual(self.events,['ingress-start-hold-requested'])
        release([self.row],refresh=lambda:None);self.assertFalse(Path(self.row['path']).exists())
    def test_existing_or_external_start_hold_is_not_overwritten(self):
        self.live={'RefuseManualStart':'yes'}
        with self.assertRaises(ValueError):install([self.row],state=self.state)
        self.assertFalse(Path(self.row['path']).exists())
    def test_changed_file_cannot_be_deleted_by_recovery(self):
        install([self.row],state=self.state,refresh=self.refresh)
        Path(self.row['path']).write_text('external replacement')
        with self.assertRaises(ValueError):release([self.row],refresh=lambda:None)
        self.assertEqual(Path(self.row['path']).read_text(),'external replacement')
    def test_existing_service_flag_must_remain_effective(self):
        install([self.row],state=self.state,refresh=self.refresh);self.live={'RefuseManualStart':'no'}
        with self.assertRaises(ValueError):verify([self.row],state=self.state)


if __name__=='__main__':unittest.main()
