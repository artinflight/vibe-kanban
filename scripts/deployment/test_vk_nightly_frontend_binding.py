"""The gateway's live release and the backend fallback have separate identities."""
import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_supervisor import served_frontend


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


if __name__=='__main__':unittest.main()
