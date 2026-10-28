"""Retained-image provenance, alias identity, and no live recapture regressions."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_retained import RetainedSnapshots, retained_root
from vk_nightly_lifecycle import NightlyJob
from vk_nightly_b_job import resident_scope
from vk_nightly_job import validate


class RetainedTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(dir=os.environ['TMPDIR']))
        self.jobs=self.root/'jobs';self.jobs.mkdir();(self.jobs/'job.lock').touch()
        self.folder=self.jobs/('input-'+'1'*32);self.folder.mkdir()
        self.source='/fixture/db.sqlite';self.name='sqlite-consistent-'+'2'*32+'.sqlite'
        p=self.folder/self.name;p.write_bytes(b'retained consistent image')
        info=p.stat();self.seal={'identity':[info.st_dev,info.st_ino],'sealed':True,'bytes':info.st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        image={'source':self.source,'snapshot':self.name,'bytes':info.st_size,'sha256':self.seal['sha256'],
               'physical_b_verified':True,'integrity':'ok','backup_api_consistent_image':True,
               'writer_fenced':False,'online_preparation_only':True}
        manifest={'plan_sha256':'a'*64,'scope_sha256':'b'*64,'large_b_disk_snapshots':{self.source:image}}
        raw=json.dumps(manifest).encode();(self.folder/'manifest.json').write_bytes(raw)
        pin=lambda p:[p.stat().st_dev,p.stat().st_ino]
        self.attempt={'candidate':'generation-'+'3'*32,'input_name':self.folder.name,
            'binding':{'root_identity':pin(self.jobs)},'input_identity':pin(self.folder),'inputs':{
            self.name:self.seal,'manifest.json':{'identity':pin(self.folder/'manifest.json'),
                'bytes':len(raw),'sealed':True,'sha256':hashlib.sha256(raw).hexdigest()}}}
        (self.jobs/'attempt.json').write_text(json.dumps(self.attempt))
        self.binding={'root':str(self.root),'candidate':self.attempt['candidate'],'input_name':self.folder.name,
                      'manifest_sha256':hashlib.sha256(raw).hexdigest(),'plan_sha256':'a'*64,
                      'source_scope_sha256':'b'*64,'snapshot_count':1,'volume_device':123}

    def manager(self):
        with patch('vk_nightly_retained.retained_root',return_value=self.root):return RetainedSnapshots(self.binding)

    def alias_job(self):
        jobs=self.root/'new-jobs';jobs.mkdir();folder=jobs/('input-'+'4'*32);folder.mkdir()
        job=NightlyJob.__new__(NightlyJob);job.root=jobs;job.capture_limit=1024**2
        value={'input_name':folder.name,'inputs':{},'capture_budget_bytes':1024**2}
        job.read=lambda:copy.deepcopy(value)
        def save(v):value.clear();value.update(copy.deepcopy(v))
        job.save=save
        def register(p,fd):
            st=os.fstat(fd);value['inputs'][p.name]={'identity':[st.st_dev,st.st_ino],'sealed':False}
        return folder,job,register,value

    def test_real_hardlink_transfers_exact_original_seal_without_payload_rehash(self):
        manager=self.manager();self.addCleanup(manager.close);folder,job,register,value=self.alias_job()
        original=(self.jobs/'attempt.json').read_bytes()
        image,receipt=manager.alias(self.source,folder,job,register,link=lambda a,b,v:os.link(a,b))
        self.assertEqual(os.stat(folder/self.name).st_ino,os.stat(self.folder/self.name).st_ino)
        self.assertEqual((self.jobs/'attempt.json').read_bytes(),original)
        self.assertTrue(receipt['reused_native_integrity']);self.assertFalse(image['new_SQLite_backup_api_capture'])
        self.assertEqual(value['inputs'][self.name]['sha256'],self.seal['sha256'])
        self.assertEqual((folder/self.name).read_bytes(),b'retained consistent image')

    def test_equal_content_copy_is_not_accepted_as_a_sealed_alias(self):
        manager=self.manager();self.addCleanup(manager.close);folder,job,register,value=self.alias_job()
        def copy_file(a,b,v):b.write_bytes(a.read_bytes())
        with self.assertRaisesRegex(ValueError,'original inode'):
            manager.alias(self.source,folder,job,register,link=copy_file)
        self.assertFalse(value['inputs'][self.name]['sealed'])

    def test_wrong_manifest_and_replaced_image_are_rejected(self):
        self.binding['manifest_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'manifest binding'):self.manager()
        self.binding['manifest_sha256']=self.attempt['inputs']['manifest.json']['sha256']
        manager=self.manager();self.addCleanup(manager.close)
        p=self.folder/self.name;p.rename(p.with_suffix('.kept'));p.write_bytes(b'retained consistent image')
        with self.assertRaisesRegex(ValueError,'identity differs'):manager.check(self.source)

    def test_original_job_lease_prevents_simultaneous_recovery(self):
        manager=self.manager();self.addCleanup(manager.close)
        with self.assertRaises(BlockingIOError):self.manager()

    def test_no_unknown_snapshot_or_operational_adoption(self):
        manager=self.manager();self.addCleanup(manager.close)
        self.assertIsNone(manager.alias('/unknown',None,None,None))
        with self.assertRaisesRegex(ValueError,'private proof only'):
            resident_scope({'wsl_root':'/mnt/b/vk-backups/vk-test','retained_recovery':self.binding,'retention_adopted':True})
        with self.assertRaisesRegex(ValueError,'private proof only'):
            validate({'retained_recovery':self.binding},{})
        with self.assertRaisesRegex(ValueError,'exact private capacity'):
            retained_root('/mnt/b/vk-backups/an-unrelated-backup')
