"""The gateway's live release and the backend fallback have separate identities."""
import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_supervisor import served_frontend, frontend_observation


class ServedFrontend(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']);self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.body=b'current mobile Dot and report links'
        (self.root/'index.html').write_bytes(self.body)
        self.settings={'frontend_root':str(self.root),'backend_frontend_root':'/retained/backend/fallback',
            'frontend_url':'http://127.0.0.1:4720/','frontend_index_sha256':hashlib.sha256(self.body).hexdigest()}

    def response(self,data):
        value=io.BytesIO(data);value.status=200;return value

    def test_current_gateway_release_may_differ_from_retained_backend_fallback(self):
        with patch('vk_nightly_supervisor.urllib.request.urlopen',return_value=self.response(self.body)):
            served_frontend(self.settings)

    def test_changed_gateway_or_source_release_is_not_accepted(self):
        with patch('vk_nightly_supervisor.urllib.request.urlopen',return_value=self.response(b'older release')):
            with self.assertRaisesRegex(ValueError,'gateway frontend'):served_frontend(self.settings)
        (self.root/'index.html').write_bytes(b'changed locally')
        with self.assertRaisesRegex(ValueError,'served frontend bytes'):served_frontend(self.settings)

    def test_remote_or_unpinned_url_never_opens_a_channel(self):
        for url in ('https://example.com/','http://127.0.0.1:4720/?token=value','http://127.0.0.1:4720/api/info'):
            with patch('vk_nightly_supervisor.urllib.request.urlopen') as opened:
                with self.assertRaises(ValueError):served_frontend({**self.settings,'frontend_url':url})
                opened.assert_not_called()

    def private(self):
        return {'supervisor':self.settings,'capacity_measurement_only':True,
                'adoption_authorized':False,'retention_adopted':False,
                'schedule_enabled':False,'schedule':{'enabled':False}}

    def test_private_epoch_can_finish_after_frontend_publication_without_adoption(self):
        newer=b'newer authorized frontend'
        with patch('vk_nightly_supervisor.urllib.request.urlopen',return_value=self.response(newer)):
            value=frontend_observation(self.private(),allow_transition=True)
        self.assertEqual(value['frontend_transition']['captured_index_sha256'],self.settings['frontend_index_sha256'])
        self.assertEqual(value['frontend_transition']['observed_index_sha256'],hashlib.sha256(newer).hexdigest())
        self.assertFalse(value['frontend_transition']['exact_live_release_adoption_ready'])

    def test_default_admission_and_operational_mode_remain_strict(self):
        with patch('vk_nightly_supervisor.urllib.request.urlopen',return_value=self.response(b'newer')):
            with self.assertRaisesRegex(ValueError,'gateway frontend'):
                frontend_observation(self.private())
        for key in ('adoption_authorized','retention_adopted','schedule_enabled'):
            c=self.private();c[key]=True
            with self.assertRaisesRegex(ValueError,'unadopted private'):
                frontend_observation(c,allow_transition=True)

    def test_private_transition_does_not_excuse_changed_pinned_material(self):
        (self.root/'index.html').write_bytes(b'changed locally')
        with self.assertRaisesRegex(ValueError,'served frontend bytes'):
            frontend_observation(self.private(),allow_transition=True)

    def test_private_transition_does_not_excuse_unavailable_gateway(self):
        with patch('vk_nightly_supervisor.urllib.request.urlopen',side_effect=OSError('offline')):
            with self.assertRaises(OSError):frontend_observation(self.private(),allow_transition=True)


if __name__=='__main__':unittest.main()
