"""Explicit clear publication/readback checks. Every mark is mocked."""
import copy
import json
import os
import sys
import unittest
from unittest.mock import patch

from verify_explicit_read import verify

SOURCE = os.environ.get("VK_CONNECTOR_SOURCE")
if SOURCE:
    sys.path.insert(0, SOURCE)
    import adapter
    import workspace_unread as unread
    import test_report_reconciliation as fixtures


MARK = {"name": "mark_workspace_read", "inputSchema": {
    "properties": {"workspace_id": {"format": "uuid"}}, "required": ["workspace_id"],
    "additionalProperties": False}, "annotations": {"readOnlyHint": False, "openWorldHint": False}}
READ = {"name": "list_workspace_unread_summaries", "annotations": {"readOnlyHint": True}}


class Client:
    def __init__(self):
        self.tools = [copy.deepcopy(MARK), copy.deepcopy(READ)]
        self.calls = []

    def handle(self, message):
        self.calls.append(message)
        if message["method"] == "tools/list":
            return {"result": {"tools": self.tools}}
        assert message["params"]["name"] == "list_workspace_unread_summaries"
        return {"result": {"content": [{"text": json.dumps({
            "observed_at": "2026-10-10T00:00:00Z", "summaries": []})}], "isError": False}}


class ReadinessTests(unittest.TestCase):
    def test_verification_never_calls_mark_or_claims_client_refresh(self):
        client = Client()
        result = verify(client)
        self.assertEqual(result["mark_requests"], 0)
        self.assertFalse(result["client_refresh_verified"])
        self.assertEqual([call["method"] for call in client.calls], ["tools/list", "tools/call"])
        self.assertEqual(client.calls[1]["params"], {
            "name": "list_workspace_unread_summaries", "arguments": {"limit": 1}})

    def test_expanded_clear_contract_rejected_before_any_call(self):
        for key, value in (("additionalProperties", True), ("required", [])):
            client = Client()
            client.tools[0]["inputSchema"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify(client)
            self.assertEqual(len(client.calls), 1)

    def test_read_error_does_not_establish_readiness(self):
        client = Client()
        original = client.handle
        def failed(message):
            return original(message) if message["method"] == "tools/list" else {"result": {"isError": True}}
        client.handle = failed
        with self.assertRaises(ValueError):
            verify(client)


@unittest.skipUnless(SOURCE, "Set VK_CONNECTOR_SOURCE for actual explicit clear dispatcher")
class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.Tests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = adapter.Adapter(None)

    def call(self, name, args):
        response = self.client.handle({"jsonrpc": "2.0", "id": "explicit-fixture", "method": "tools/call",
                                       "params": {"name": name, "arguments": args}})
        return json.loads(response["result"]["content"][0]["text"])

    def test_acknowledgement_is_not_current_unread_readback_or_delivery(self):
        calls = []
        def request(api, wid=None):
            calls.append(wid)
            if wid is not None:
                return None  # existing /seen success data=null
            # A new reply or manual-unread arrived after the clear transaction.
            return {"summaries": [{"workspace_id": fixtures.W, "has_unseen_turns": True}]}
        with patch.object(unread, "request", side_effect=request):
            accepted = self.call("mark_workspace_read", {"workspace_id": fixtures.W})
            current = self.call("list_workspace_unread_summaries", {})
        self.assertTrue(accepted["marked_read"])
        self.assertNotIn("has_unseen_turns", accepted)
        self.assertNotIn("proof", accepted)
        self.assertTrue(current["summaries"][0]["has_unseen_turns"])
        self.assertTrue(current["observed_at"])
        self.assertEqual(calls, [fixtures.W, None])
        self.assertFalse(self.fixture.atomic.posts)

    def test_explicit_clear_does_not_release_local_hold_or_reconcile_receipts(self):
        self.fixture.hold(True, "synthetic-local-review-hold")
        with self.fixture.store.locked() as db:
            before = [tuple(row) for row in db.execute("SELECT * FROM holds")]
        with patch.object(unread, "request", return_value=None) as request:
            self.call("mark_workspace_read", {"workspace_id": fixtures.W})
        request.assert_called_once_with(adapter, fixtures.W)
        with self.fixture.store.locked() as db:
            self.assertEqual([tuple(row) for row in db.execute("SELECT * FROM holds")], before)
            self.assertEqual(db.execute("SELECT count(*) FROM receipts").fetchone()[0], 0)
        self.assertFalse(self.fixture.atomic.posts)

    def test_uncertain_write_not_retried_and_readback_is_independent(self):
        with patch.object(unread, "request", side_effect=TimeoutError("synthetic lost response")) as request:
            with self.assertRaises(TimeoutError):
                self.call("mark_workspace_read", {"workspace_id": fixtures.W})
        self.assertEqual(request.call_count, 1)
        with patch.object(unread, "request", return_value={"summaries": [
                {"workspace_id": fixtures.W, "has_unseen_turns": False}]}) as read:
            observed = self.call("list_workspace_unread_summaries", {})
        read.assert_called_once_with(adapter)
        self.assertFalse(observed["summaries"][0]["has_unseen_turns"])
        self.assertNotIn("marked_read", observed)

    def test_missing_post_clear_flag_is_unknown_not_assumed_false(self):
        with patch.object(unread, "request", return_value=None):
            self.call("mark_workspace_read", {"workspace_id": fixtures.W})
        with patch.object(unread, "request", return_value={"summaries": [
                {"workspace_id": fixtures.W}]}) as read:
            with self.assertRaises(ValueError):
                self.call("list_workspace_unread_summaries", {})
        self.assertEqual(read.call_count, 1)


if __name__ == "__main__":
    unittest.main()
