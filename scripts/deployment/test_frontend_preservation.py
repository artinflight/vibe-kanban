import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from check_frontend_preservation import check


class FrontendPreservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.live = self.root / 'live'
        self.candidate = self.root / 'candidate'
        self.live.mkdir()
        self.candidate.mkdir()
        (self.live / 'menu.tsx').write_text('independent scrolling')
        (self.live / 'unread.tsx').write_text('explicit unread control')
        for path in self.live.iterdir():
            (self.candidate / path.name).write_bytes(path.read_bytes())
        self.artifact = self.root / 'artifact.json'
        self.artifact.write_text(json.dumps({'source_files': [
            {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in self.live.iterdir()
        ]}))

    def verify(self, allowed=()):
        return check(self.artifact, self.live, self.candidate, allowed)

    def test_preserved_live_source_passes(self):
        self.assertTrue(self.verify()['passed'])

    def test_unrelated_release_cannot_drop_scrolling(self):
        (self.candidate / 'unread.tsx').write_text('new unread correction')
        (self.candidate / 'menu.tsx').write_text('old expanding layout')
        result = self.verify(['unread.tsx'])
        self.assertFalse(result['passed'])
        self.assertEqual(result['unexpected_changed_paths'], ['menu.tsx'])

    def test_reviewed_change_preserves_other_live_features(self):
        (self.candidate / 'menu.tsx').write_text('improved independent scrolling')
        self.assertTrue(self.verify(['menu.tsx'])['passed'])

    def test_missing_unrelated_source_is_rejected(self):
        (self.candidate / 'unread.tsx').unlink()
        self.assertFalse(self.verify(['menu.tsx'])['passed'])

    def test_live_manifest_must_match_actual_live_source(self):
        (self.live / 'menu.tsx').write_text('changed after capture')
        with self.assertRaises(ValueError):
            self.verify()


if __name__ == '__main__':
    unittest.main()
