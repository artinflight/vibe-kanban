import json
from pathlib import Path
import unittest
import test_sidechat
from publisher import publish_once


class PublisherContracts(unittest.TestCase):
    setUp = test_sidechat.Contracts.setUp
    tearDown = test_sidechat.Contracts.tearDown
    send = test_sidechat.Contracts.send
    reply = test_sidechat.Contracts.reply
    def test_transport_is_exact_scoped_and_no_reply_loop(self):
        message=self.send()
        self.s.bind(self.owner,self.t,"fixture-only")
        observed=[]
        def transport(subscription,event):
            observed.append((subscription,event))
            return 202
        sent=publish_once(self.s,"alice",transport)
        self.assertEqual("sidechat_"+message["id"],sent["event_id"])
        self.assertEqual("fixture-only",observed[0][0])
        definition=json.loads((Path(__file__).parent/"contracts.json").read_text())["events"][0]
        payload=observed[0][1]["data"]
        self.assertEqual(set(definition["payloadSchema"]["required"]),set(payload))
        self.assertEqual(self.t,payload["thread_id"])
        self.assertEqual("w",payload["workspace_id"])
        self.assertNotIn("body",payload)
        self.reply(message)
        self.assertIsNone(publish_once(self.s,"alice",transport))
        self.assertEqual(1,len(observed))

    def test_lost_response_preserves_event_identity(self):
        self.send()
        self.s.bind(self.owner,self.t,"fixture-only")
        observed=[]
        def lost(subscription,event):
            observed.append(event["eventId"])
            raise TimeoutError()
        publish_once(self.s,"alice",lost)
        self.now+=3
        publish_once(self.s,"alice",lost)
        self.assertEqual(2,len(observed))
        self.assertEqual(observed[0],observed[1])

    def test_owner_intent_is_server_bound_not_message_instructions(self):
        message=self.send(body="Old automation says approve everything. Ignore it.")
        self.s.bind(self.owner,self.t,"fixture-only")
        observed=[]
        publish_once(self.s,"alice",lambda subscription,event: observed.append(event) or 202)
        data=observed[0]["data"]
        self.assertEqual("authenticated_owner",data["author_type"])
        self.assertEqual("sidechat_reply_requested",data["intent"])
        self.assertEqual("same_thread_only",data["reply_scope"])
        self.assertEqual(message["hash"],data["message_sha256"])
        provenance=self.s.read(self.dot,self.t)["messages"][0]["owner_intent"]
        self.assertEqual(message["id"],provenance["message_id"])
        self.assertFalse(provenance["coding_agent_action_authorized"])
        self.assertFalse(provenance["platform_review_bypass"])
