"""Disabled package uses the actual plan and fixed calendar, never live cron."""
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from build_vk_nightly_job_config import build
from vk_prep_common import identity


class Package(unittest.TestCase):
    def test_current_plan_and_complete_calendar_source_are_bound_without_adoption(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as raw:
            root=Path(raw);source=root/'source';source.mkdir()
            recipe={'sources':[str(source)],'excluded_rebuildable_directories':[],
                    'nightly_exact_socket_omission_proposal':[]}
            plan=root/'plan.json';plan.write_text(json.dumps(recipe))
            info=source.stat()
            value={'plan_identity':identity(recipe),'roots':{str(source):{
                'device':info.st_dev,'inode':info.st_ino,'mode_type':stat.S_IFDIR}},
                'files':0,'paths':1,'databases':{},'logical_file_bytes':0,
                'maximum_DB_bytes':0,'elapsed_seconds':0}
            inventory=root/'inventory.json';inventory.write_text(json.dumps(value))
            output=root/'package'
            built=build(inventory,output,plan_path=plan,compressed_delta=True,chunked_delta=True)
            config=json.loads((output/'nightly-production.disabled.private.json').read_text())
            self.assertFalse(config['adoption_authorized']);self.assertFalse(config['schedule']['enabled'])
            self.assertEqual(json.loads(Path(config['plan_path']).read_text()),recipe)
            self.assertEqual(config['object_encoding'],'chunked-zlib-1-v1')
            for name in ('vk_nightly_supervisor.py','vk_nightly_calendar.py','vk_nightly_schedule.py'):
                self.assertIn(name,config['source_sha256'])
                self.assertEqual(hashlib.sha256((output/name).read_bytes()).hexdigest(),config['source_sha256'][name])
            cron=(output/'cron.proposed').read_text()
            self.assertIn('*/15 * * * *',cron)
            self.assertIn('vk_nightly_calendar.py',cron)
            self.assertNotIn('0 2 * * *',cron)
            self.assertTrue(built['cron_proposed_sha256'])


if __name__=='__main__':unittest.main()
