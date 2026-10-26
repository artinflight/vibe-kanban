import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest

from vk_nightly_file_version import capture_qualified_version,fingerprint


class QualifiedTransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'history';self.path.write_bytes(b'old\nnew\n')
        self.observation=dict(state='qualified-pending-body',source=str(self.path),
                              source_identity=fingerprint(self.path.stat()),
                              row=dict(bytes=8,sha256=hashlib.sha256(b'old\nnew\n').hexdigest()))
        self.prefix=dict(bytes=4,sha256=hashlib.sha256(b'old\n').hexdigest(),independent_proof_sha256='a'*64)

    def capture(self,output,prefix=None):
        return capture_qualified_version(self.observation,output,guard=lambda:None,prefix=prefix)

    def test_later_append_does_not_discard_the_exact_previously_qualified_version(self):
        with self.path.open('ab') as f:f.write(b'later\n')
        target=io.BytesIO();proof=self.capture(target)
        self.assertEqual(target.getvalue(),b'old\nnew\n');self.assertEqual(proof['copied_bytes'],8)
        self.assertTrue(proof['source_bytes_after_observation_not_claimed_backed_up'])
        self.assertFalse(proof['current_set_accepted'])

    def test_verified_accepted_prefix_is_not_copied_again(self):
        target=io.BytesIO();proof=self.capture(target,self.prefix)
        self.assertEqual(target.getvalue(),b'new\n');self.assertEqual(proof['copied_bytes'],4)
        self.assertEqual(proof['qualified_member_sha256'],self.observation['row']['sha256'])

    def test_prefix_or_complete_digest_mismatch_cannot_seal_partial_output(self):
        self.path.write_bytes(b'bad\nnew\n');target=io.BytesIO()
        with self.assertRaises(ValueError):self.capture(target,self.prefix)
        self.assertEqual(target.getvalue(),b'')
        self.path.write_bytes(b'old\nbad\n');target=io.BytesIO()
        with self.assertRaises(ValueError):self.capture(target,self.prefix)
        self.assertEqual(target.getvalue(),b'bad\n')

    def test_missing_replaced_truncated_or_unqualified_source_refused(self):
        self.path.write_bytes(b'tiny')
        with self.assertRaises(ValueError):self.capture(io.BytesIO())
        self.path.unlink();self.path.write_bytes(b'old\nnew\n')
        # A filesystem can immediately recycle an inode; force a distinct one.
        other=self.path.with_name('other');other.write_bytes(b'old\nnew\n');os.replace(other,self.path)
        with self.assertRaises(ValueError):self.capture(io.BytesIO())
        self.observation['state']='unqualified'
        with self.assertRaises(ValueError):self.capture(io.BytesIO())


if __name__=='__main__':unittest.main()
