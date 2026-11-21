import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest

import retirement_progress as rp


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'batch-0002'
        self.primary = self.root / 'primary'
        self.objects = []
        for number in range(3):
            relative = Path('12/session/processes/.log-objects') / (str(number)*64 + '.gz')
            p, q = self.folder / 'archive' / relative, self.primary / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            q.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(str(number).encode()); q.write_bytes(p.read_bytes())
            self.objects.append(dict(path=str(p),primary=str(q),identity=rp.identity(p.stat()),physical_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        self.save('PLAN.private.json',dict(source_root=str(self.primary)))
        self.save('CONVERSION.private.json',dict(complete=True,outcome='installed'))
        self.save('journal/state.json',dict(complete=True,outcome='installed'))
        self.save('DYNAMIC_RECOVERY.private.json',dict(actual_independent_normal_restore=dict(independent_owner_controls_restore_verified=True)))
        self.save('STAGING_RETIREMENT_PLAN.private.json',dict(objects=self.objects,original_or_primary_deletion=False))
        self.now = time.time()+1
        self.row = dict(state='stalled',progress_at=self.now-700,needs_attention=True)

    def save(self,name,value):
        p=self.folder/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))

    def test_only_new_verified_removal_advances_progress(self):
        row, old=rp.supplement(self.root,self.row,None,self.now)
        self.assertEqual(row['retirement_removed'],0)
        _, same=rp.supplement(self.root,self.row,old,self.now+10)
        self.assertEqual(same['at'],old['at'])
        Path(self.objects[0]['path']).unlink()
        row, new=rp.supplement(self.root,self.row,same,self.now+20)
        self.assertEqual(new['at'],self.now+20)
        self.assertEqual(row['retirement_removed'],1)
        row, _=rp.supplement(self.root,self.row,new,self.now+621)
        self.assertEqual(row['state'],'stalled')

    def test_terminal_failure_cannot_be_hidden(self):
        row=dict(self.row,state='failure_recovery_pending')
        self.assertEqual(rp.supplement(self.root,row,None,self.now),(row,None))

    def test_primary_corruption_and_foreign_path_refused(self):
        Path(self.objects[0]['path']).unlink()
        Path(self.objects[0]['primary']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Primary bytes'):rp.supplement(self.root,self.row,None,self.now)
        self.objects[0]['primary']=str(self.root/'foreign')
        self.save('STAGING_RETIREMENT_PLAN.private.json',dict(objects=self.objects,original_or_primary_deletion=False))
        with self.assertRaisesRegex(ValueError,'Foreign primary'):rp.supplement(self.root,self.row,None,self.now)

    def test_incomplete_recovery_and_changed_staging_refused(self):
        self.save('DYNAMIC_RECOVERY.private.json',{})
        with self.assertRaisesRegex(ValueError,'independent recovery'):rp.supplement(self.root,self.row,None,self.now)
        self.save('DYNAMIC_RECOVERY.private.json',dict(actual_independent_normal_restore=dict(independent_owner_controls_restore_verified=True)))
        Path(self.objects[0]['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'identity changed'):rp.supplement(self.root,self.row,None,self.now)

    def test_isolated_control_observer_follows_new_path_and_still_reports_failure(self):
        import os
        from checkpoint_control import atomic
        from control_observation import retirement_supplement
        controls=self.root/'checkpoint-controls-fixture';controls.mkdir(mode=0o700)
        parent=controls/'isolated-preparations';parent.mkdir(mode=0o700)
        target=parent/self.folder.name;self.folder.rename(target);old_folder=self.folder;self.folder=target
        for item in self.objects:
            item['path']=str(target/Path(item['path']).relative_to(old_folder))
        self.save('STAGING_RETIREMENT_PLAN.private.json',dict(objects=self.objects,original_or_primary_deletion=False))
        operation='a'*32;handoff=controls/'HANDOFF.private.json'
        atomic(handoff,dict(batch_override=dict(batch=2,path=str(target))))
        atomic(controls/'CONTROLLER_SEAL.private.json',dict(operation=operation,attempt='controlled1',handoff=str(handoff)))
        row=dict(self.row,operation=operation,attempt='controlled1');config=dict(operation_root=str(self.root),checkpoint_controls=str(controls))
        observed,previous=retirement_supplement(config,row,None,self.now)
        self.assertEqual(observed['retirement_removed'],0)
        Path(self.objects[0]['path']).unlink()
        observed,current=retirement_supplement(config,row,previous,self.now+20)
        self.assertEqual(observed['retirement_removed'],1);self.assertEqual(current['at'],self.now+20)
        failed=dict(row,state='failure_recovery_pending')
        self.assertEqual(retirement_supplement(config,failed,current,self.now+30),(failed,current))


if __name__=='__main__':unittest.main()
