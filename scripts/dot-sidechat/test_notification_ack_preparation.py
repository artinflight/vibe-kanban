import json
from pathlib import Path
import tempfile
import unittest

from prepare_notification_ack import prepare, sha


class NotificationPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bundle = self.root/'baseline'
        self.bundle.mkdir()
        self.source = "def call(name,args):\n    return ('existing',name,args)\n\ndef retained():\n    return 'newer shared feature'\n"
        (self.bundle/'connector.py').write_text(self.source)
        self.contracts = {'tools':[{'name':'incumbent_tool','inputSchema':{'additionalProperties':False}}],
                          'events':[{'name':'incumbent_event','payloadSchema':{'futureField':True}}],
                          'newerSharedMetadata':{'must':'survive'}}
        (self.bundle/'contracts.json').write_text(json.dumps(self.contracts))
        (self.bundle/'sidechat.py').write_text('unchanged_store = True\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_preparation_keeps_every_existing_definition_and_source_node(self):
        output=self.root/'candidate'
        report=prepare(self.bundle,sha(self.bundle/'connector.py'),sha(self.bundle/'contracts.json'),
                       sha(self.bundle/'sidechat.py'),output)
        after=json.loads((output/'contracts.json').read_text())
        self.assertEqual(self.contracts['tools'],after['tools'][:-2])
        self.assertEqual(self.contracts['events'],after['events'])
        self.assertEqual(self.contracts['newerSharedMetadata'],after['newerSharedMetadata'])
        self.assertEqual({'connector.py','contracts.json','notification_ack.py'}, {p.name for p in output.iterdir()})
        self.assertFalse(report['installed']);self.assertEqual(0,report['liveWrites'])
        self.assertEqual(self.source,(self.bundle/'connector.py').read_text())

    def test_stale_pin_rejects_without_preparing_or_mutating_source(self):
        output=self.root/'candidate'
        with self.assertRaises(ValueError):
            prepare(self.bundle,'0'*64,sha(self.bundle/'contracts.json'),sha(self.bundle/'sidechat.py'),output)
        self.assertFalse(output.exists())
        self.assertEqual(self.source,(self.bundle/'connector.py').read_text())
