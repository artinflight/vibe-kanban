import json
from pathlib import Path
import tempfile
import unittest
import checkpoint_job as subject


class ClaimTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        script = self.root/'script.py'
        script.write_text('raise RuntimeError("never execute fixtures")\n')
        config = self.root/'config.json'
        config.write_text(json.dumps(dict(entrypoint_sha256=subject.digest(script))))
        predecessor = self.root/'prior.json'
        predecessor.write_text('{"complete":true}')
        self.args = dict(config=config, config_sha256=subject.digest(config), script=script,
                         script_sha256=subject.digest(script), predecessor=predecessor,
                         predecessor_sha256=subject.digest(predecessor),
                         invocation='12345678123456781234567812345678', pid=10, now=100)

    def test_durable_claim_blocks_an_uncertain_replay(self):
        first = subject.claim(**self.args)
        saved = (self.root/'STARTED.private.json').read_bytes()
        self.assertEqual(first['pid'], 10)
        with self.assertRaisesRegex(ValueError, 'no replay'):
            subject.claim(**self.args)
        self.assertEqual((self.root/'STARTED.private.json').read_bytes(), saved)

    def test_changed_predecessor_is_rejected_before_claim(self):
        self.args['predecessor'].write_text('{"complete":false}')
        with self.assertRaises(ValueError):
            subject.claim(**self.args)
        self.assertFalse((self.root/'STARTED.private.json').exists())

    def test_existing_success_or_fault_cannot_be_overwritten(self):
        for name in ('RESULT.private.json', 'STOP.private.json'):
            with self.subTest(name=name):
                (self.root/name).write_text('{}')
                with self.assertRaises(ValueError):
                    subject.claim(**self.args)
                self.assertFalse((self.root/'STARTED.private.json').exists())
                (self.root/name).unlink()


if __name__ == '__main__':
    unittest.main()
