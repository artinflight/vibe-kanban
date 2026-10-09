"""Synthetic delivery-boundary tests; never contact a live workspace."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from caller import Caller, GUARD_KEYS, IDENTITY_KEYS, LocalTools


IDENTITY = {"workspace_id": "a0000000-0000-0000-0000-000000000001",
            "execution_id": "b0000000-0000-0000-0000-000000000002",
            "session_id": "c0000000-0000-0000-0000-000000000003",
            "message_index": 92, "reply_sha256": "a" * 64,
            "hash_version": "utf8-sha256-v1",
            "execution_revision": "2026-10-07T12:33:15.980774402Z"}
EVENT = {"outcome": "chat_delivered", "actor": "root", "channel": "chat",
         "event_id": "synthetic-chat-event", "evidence": "DISPOSABLE fixture delivery only"}


class FakeTools:
    def __init__(self):
        self.calls = []
        self.held = False
        self.fail = False
        self.epoch = 3

    def validate_source(self, source):
        if source["actor"] not in ("root", "dot") or source["channel"] not in ("chat", "voice"):
            raise ValueError("Invalid source")

    def call(self, name, args):
        self.calls.append((name, copy.deepcopy(args)))
        if name == "prepare_workspace_report_delivery":
            return {"delivery_context_version": 1, "identity": args,
                    "expected_intent_version": self.epoch, "expected_hold_version": 4, "held": self.held}
        if self.fail:
            raise TimeoutError("Uncertain synthetic result")
        return {"recorded": True, "status": "applied", "receipt_id": "fixture",
                "readback_fresh": True,
                "proof": {"authoritative_readback": False,
                          "authoritative_readback_observed_at": "2026-10-09T22:00:00+00:00"}}


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tools = FakeTools()
        self.path = Path(self.tmp.name) / "outbox.sqlite"
        self.caller = Caller(self.path, self.tools)

    def prepared(self):
        return self.caller.prepare(IDENTITY)["token"]

    def test_prepare_is_read_only_and_does_not_infer_delivery(self):
        token = self.prepared()
        with self.assertRaises(ValueError):
            self.caller.retry(token)
        self.assertEqual([name for name, _ in self.tools.calls], ["prepare_workspace_report_delivery"])

    def test_confirm_routes_exact_identity_and_pre_presentation_intent(self):
        token = self.prepared()
        self.tools.epoch += 1
        value = self.caller.confirm(token, EVENT)
        self.assertEqual(value["status"], "applied")
        name, request = self.tools.calls[-1]
        self.assertEqual(name, "record_workspace_report_delivery")
        self.assertEqual(request["expected_intent_version"], 3)
        self.assertEqual(request["expected_hold_version"], 4)
        self.assertEqual({k: request[k] for k in IDENTITY_KEYS}, IDENTITY)

    def test_voice_only_after_completed_playback(self):
        event = dict(EVENT, channel="voice", outcome="voice_playback_completed")
        self.caller.confirm(self.prepared(), event)
        self.assertEqual(self.tools.calls[-1][1]["source"]["channel"], "voice")

    def test_explicit_handled_acknowledgement_supported(self):
        self.caller.confirm(self.prepared(), dict(EVENT, outcome="user_handled"))
        self.assertEqual(self.tools.calls[-1][1]["disposition"], "handled")

    def test_cancelled_partial_fetch_and_process_completion_send_no_receipt(self):
        token = self.prepared()
        for outcome in ("cancelled", "partial", "failed", "fetched", "completed"):
            self.assertFalse(self.caller.confirm(token, dict(EVENT, outcome=outcome))["recorded"])
        self.assertEqual(len(self.tools.calls), 1)

    def test_channel_mismatch_unknown_signal_and_agent_claim_rejected(self):
        token = self.prepared()
        for change in ({"channel": "voice"}, {"outcome": "silence"}, {"actor": "worker"}):
            with self.assertRaises(ValueError):
                self.caller.confirm(token, dict(EVENT, **change))
        self.assertEqual(len(self.tools.calls), 1)

    def test_held_report_not_prepared_or_cleared(self):
        self.tools.held = True
        self.assertEqual(self.caller.prepare(IDENTITY), {"prepared": False, "held": True})
        self.assertFalse(self.path.exists())

    def test_missing_identity_and_old_connector_context_fail_closed(self):
        for key in IDENTITY_KEYS:
            bad = dict(IDENTITY)
            del bad[key]
            with self.assertRaises(ValueError):
                self.caller.prepare(bad)
        self.assertFalse(self.tools.calls)
        self.tools.call = lambda *args: {"held": False, "identity": IDENTITY}
        with self.assertRaises(ValueError):
            self.prepared()
        self.assertFalse(self.path.exists())

    def test_unprepared_delivery_and_missing_evidence_fail_closed(self):
        with self.assertRaises(ValueError):
            self.caller.confirm("unknown", EVENT)
        bad = dict(EVENT)
        del bad["evidence"]
        with self.assertRaises(ValueError):
            self.caller.confirm(self.prepared(), bad)
        self.assertFalse(any(name == "record_workspace_report_delivery" for name, _ in self.tools.calls))

    def test_applied_duplicate_never_calls_marker_again_after_restart(self):
        token = self.prepared()
        self.caller.confirm(token, EVENT)
        again = Caller(self.path, self.tools).confirm(token, EVENT)
        self.assertTrue(again["duplicate"])
        self.assertFalse(again["readback_fresh"])
        self.assertEqual(again["result_origin"], "outbox_cache")
        self.assertNotIn("authoritative_readback", again["proof"])
        self.assertNotIn("authoritative_readback_observed_at", again["proof"])
        self.assertEqual(again["historical_readback"], {
            "has_unseen_turns": False, "observed_at": "2026-10-09T22:00:00+00:00", "fresh": False})
        self.assertEqual(len(self.tools.calls), 2)

    def test_uncertain_delivery_persists_identical_request_before_call(self):
        token = self.prepared()
        self.tools.fail = True
        with self.assertRaises(TimeoutError):
            self.caller.confirm(token, EVENT)
        original = self.tools.calls[-1][1]
        self.tools.epoch += 10
        self.tools.fail = False
        Caller(self.path, self.tools).retry(token)
        self.assertEqual(self.tools.calls[-1][1], original)

    def test_changed_source_or_event_cannot_reuse_prepared_delivery(self):
        token = self.prepared()
        self.caller.confirm(token, EVENT)
        for change in ({"event_id": "new"}, {"evidence": "Changed"}):
            with self.assertRaises(ValueError):
                self.caller.confirm(token, dict(EVENT, **change))
        self.assertEqual(len(self.tools.calls), 2)

    def test_one_actual_channel_event_can_convey_individually_prepared_workspaces(self):
        first = self.prepared()
        other = dict(IDENTITY, workspace_id="d0000000-0000-0000-0000-000000000004")
        second = self.caller.prepare(other)["token"]
        self.caller.confirm(first, EVENT)
        self.caller.confirm(second, EVENT)
        delivered = [args["workspace_id"] for name, args in self.tools.calls
                     if name == "record_workspace_report_delivery"]
        self.assertEqual(delivered, [IDENTITY["workspace_id"], other["workspace_id"]])

    def test_no_report_text_or_credentials_stored(self):
        token = self.prepared()
        with self.caller.database() as db:
            context = json.loads(db.execute("SELECT context FROM presentations WHERE token=?", (token,)).fetchone()[0])
        self.assertEqual(set(context), IDENTITY_KEYS | GUARD_KEYS)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_automatic_local_caller_cannot_invoke_broad_clear(self):
        tools = LocalTools.__new__(LocalTools)
        with self.assertRaises(ValueError):
            tools.call("mark_workspace_read", {"workspace_id": IDENTITY["workspace_id"]})

    def test_automatic_transport_rejects_legacy_record_before_dispatch(self):
        tools = LocalTools.__new__(LocalTools)
        for guards in ({}, {"expected_intent_version": 3},
                       {"expected_intent_version": True, "expected_hold_version": 4}):
            with self.subTest(guards=guards), self.assertRaises(ValueError):
                tools.call("record_workspace_report_delivery", dict(IDENTITY, **guards))

    def test_retry_rejects_legacy_outbox_request_before_any_tool_call(self):
        # Seed an old malformed automatic request: even an injected tool client
        # must never receive an unpinned receipt through Caller.retry.
        token = self.prepared()
        self.tools.fail = True
        with self.assertRaises(TimeoutError):
            self.caller.confirm(token, EVENT)
        with self.caller.database() as db:
            request = json.loads(db.execute("SELECT request FROM events WHERE token=?", (token,)).fetchone()[0])
            for key in GUARD_KEYS:
                del request[key]
            db.execute("UPDATE events SET request=? WHERE token=?", (json.dumps(request), token))
        previous_calls = len(self.tools.calls)
        with self.assertRaises(ValueError):
            self.caller.retry(token)
        self.assertEqual(len(self.tools.calls), previous_calls)


if __name__ == "__main__":
    unittest.main()
