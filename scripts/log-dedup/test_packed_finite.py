import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import packed_finite as finite


class ActivationGateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.package = self.write('CONFIG.private.json', dict(artifacts={
            k:dict(sha256=k) for k in ['main','protected']}))
        self.accepted = self.write('accepted.json', dict(complete=True,
            actual_pair_engine_qualified=True, package_B_recovery_verified=True,
            cutover_config_sha256=self.package['sha256']))
        self.mapping = dict(path='/selected',sha256='map')
        self.rc = dict(readers={k:dict(sha256=a,main_pid=n,invocation=a)
            for k,a,n in [('main','main',42),('protected5650','protected',43)]})
        self.reader_ref = self.write('readers.json', self.rc)
        self.post = dict(readers=self.reader_ref,backward_mapping=self.mapping,
                         existing_owner_lock='/existing-lock')
        self.write('POST_ACTIVATION.private.json',self.post)
        self.result = dict(complete=True,cutover_only=True,bulk_conversion_started=False,
            operation='exact',release=dict(public_route_restored=True),
            main=dict(MainPID='42',InvocationID='main'),
            protected=dict(MainPID='43',InvocationID='protected'))
        self.write('RESULT.private.json',self.result)
        self.c = dict(cutover_config=self.package,pair_acceptance=self.accepted,
            operation='exact',mapping_source=self.mapping,
            production_lock='/existing-lock',source_root='/selected-root')

    def write(self,name,value):
        p=self.root/name
        p.write_text(json.dumps(value))
        return finite.reference(p)

    def test_prepared_but_unactivated_package_is_refused(self):
        (self.root/'RESULT.private.json').unlink()
        with patch.object(finite.online_owner,'LiveReaders') as live:
            with self.assertRaises(FileNotFoundError):finite.accepted_readers(self.c)
            live.assert_not_called()

    def test_changed_runtime_owner_is_refused(self):
        self.result['main']['InvocationID']='foreign'
        self.write('RESULT.private.json',self.result)
        with patch.object(finite.online_owner,'LiveReaders') as live:
            with self.assertRaisesRegex(ValueError,'identity differs'):finite.accepted_readers(self.c)
            live.assert_not_called()

    def test_changed_conversion_lock_is_refused(self):
        self.post['existing_owner_lock']='/new-lock'
        self.write('POST_ACTIVATION.private.json',self.post)
        with self.assertRaisesRegex(ValueError,'custody'):finite.accepted_readers(self.c)

    def test_valid_receipt_still_requires_actual_live_identity_check(self):
        with patch.object(finite.online_owner,'LiveReaders',side_effect=ValueError('not live')) as live:
            with self.assertRaisesRegex(ValueError,'not live'):finite.accepted_readers(self.c)
            live.assert_called_once_with(self.rc,'/selected-root')

    def test_existing_failed_dispatch_never_reopens_recovery(self):
        output=self.root/'prior';output.mkdir()
        (output/'FAILURE.json').write_text('{}')
        with patch.object(finite,'configuration',return_value=self.c),patch.object(finite,'accepted_readers') as readers:
            with self.assertRaisesRegex(FileExistsError,'no replay'):
                finite.run({},output,progress=lambda _:None)
            readers.assert_not_called()
        self.assertEqual((output/'FAILURE.json').read_text(),'{}')


if __name__=='__main__':unittest.main()
