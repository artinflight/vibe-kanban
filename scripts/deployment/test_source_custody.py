from pathlib import Path
import tempfile
import unittest

from source_custody import restored_files, sha256, verified_files


class CustodyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_exact_private_roundtrip_without_installation(self):
        original = b"value='11111111-1111-4111-8111-111111111111'\n"
        token = 'INCIDENT_UUID_0123456789ABCDEF'
        raw = original.replace(b'11111111-1111-4111-8111-111111111111', token.encode())
        (self.root / 'source.py.txt').write_bytes(raw)
        catalog = {'files': [dict(template='source.py.txt', template_sha256=sha256(raw), original_sha256=sha256(original))]}
        files = verified_files(self.root, catalog)
        restored = restored_files(files, {token: '11111111-1111-4111-8111-111111111111'})
        self.assertEqual(restored, [('source.py.txt', original)])
        self.assertEqual((self.root / 'source.py.txt').read_bytes(), raw)

    def test_changed_source_refuses(self):
        (self.root / 'source').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            verified_files(self.root, {'files': [dict(path='source', public_sha256=sha256(b'original'))]})

    def test_path_escape_and_symlink_refuse(self):
        (self.root / 'link').symlink_to('/etc/passwd')
        for path in ('../outside', '/etc/passwd', str(self.root / 'inside'), 'nested/../inside', 'link'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                verified_files(self.root, {'files': [dict(path=path, public_sha256='0' * 64)]})

    def test_missing_binding_cannot_create_falsely_verified_original(self):
        files = [('source.txt', b'INCIDENT_UUID_0123456789ABCDEF', dict(original_sha256='0' * 64))]
        with self.assertRaises(ValueError):
            restored_files(files, {})


if __name__ == '__main__':
    unittest.main()
