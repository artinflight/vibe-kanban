"""Caller -> actual connector dispatcher/ledger -> existing synthetic backend.

Set VK_CONNECTOR_SOURCE to the reviewed isolated connector candidate. Without it,
these integration cases are explicitly skipped; the ordinary caller suite runs.
"""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from caller import Caller, LocalTools

SOURCE = os.environ.get("VK_CONNECTOR_SOURCE")
if SOURCE:
    sys.path.insert(0, SOURCE)
    import adapter
    import report_reconciliation as rr
    import test_report_reconciliation as fixtures


@unittest.skipUnless(SOURCE, "Set VK_CONNECTOR_SOURCE for actual connector integration")
class Tests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.Tests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.tools = LocalTools.__new__(LocalTools)
        self.tools.adapter = adapter
        self.tools.reconciliation = rr
        self.store_patch = patch.object(rr, "Store", return_value=self.fixture.store)
        self.store_patch.start()
        self.addCleanup(self.store_patch.stop)
        self.caller = Caller(Path(self.fixture.tmp.name) / "outbox.sqlite", self.tools)
        payload = fixtures.receipt()
        self.identity = {k: v for k, v in payload.items() if k not in ("source", "disposition")}
        self.event = dict(payload["source"], outcome="user_handled")
        self.event["evidence"] = "DISPOSABLE fixture: explicit synthetic handled event"

    def prepare(self):
        return self.caller.prepare(self.identity)["token"]

    def test_end_to_end_confirmation_records_and_reads_back(self):
        result = self.caller.confirm(self.prepare(), self.event)
        self.assertEqual(result["status"], "applied")
        self.assertFalse(result["proof"]["authoritative_readback"])
        self.assertEqual(len(self.fixture.atomic.posts), 1)
        self.assertNotIn("expected_intent_version", self.fixture.atomic.posts[0])
        self.assertEqual(self.fixture.atomic.posts[0]["intent_version"], 0)

    def test_manual_unread_then_release_before_delivery_does_not_adopt_epoch(self):
        token = self.prepare()
        self.fixture.atomic.epoch += 2
        result = self.caller.confirm(token, self.event)
        self.assertEqual(result["status"], "stale_intent")
        self.assertFalse(self.fixture.atomic.posts)

    def test_local_offline_hold_release_before_delivery_remains_stale(self):
        token = self.prepare()
        self.fixture.atomic.fail = True
        self.fixture.hold()
        self.fixture.hold(False, "release-fixture")
        self.fixture.atomic.fail = False
        self.assertEqual(self.caller.confirm(token, self.event)["status"], "stale_intent")
        self.assertFalse(self.fixture.atomic.posts)

    def test_manual_hold_during_delayed_delivery_stops_receipt(self):
        token = self.prepare()
        self.fixture.hold()
        self.assertEqual(self.caller.confirm(token, self.event)["status"], "held")
        self.assertFalse(self.fixture.atomic.posts)

    def test_new_reply_or_running_other_session_is_rejected(self):
        for flag in ("newer", "running"):
            with self.subTest(flag=flag):
                setattr(self.fixture.atomic, flag, True)
                result = self.caller.confirm(self.prepare(), self.event)
                self.assertEqual(result["status"], "backend_conflict")
                setattr(self.fixture.atomic, flag, False)
        self.assertFalse(self.fixture.atomic.applied)

    def test_new_reply_after_mark_readback_stays_unread(self):
        self.fixture.atomic.after_apply = lambda: setattr(self.fixture.atomic, "newer", True)
        self.assertTrue(self.caller.confirm(self.prepare(), self.event)["proof"]["authoritative_readback"])

    def test_backend_intent_race_after_preflight_rejected_atomically(self):
        token = self.prepare()
        original = self.fixture.atomic.__call__
        def race(api, wid, suffix, method="GET", payload=None):
            if suffix == "review-receipts":
                self.fixture.atomic.epoch += 2
            return original(api, wid, suffix, method, payload)
        self.fixture.backend.side_effect = race
        self.assertEqual(self.caller.confirm(token, self.event)["status"], "backend_conflict")
        self.assertFalse(self.fixture.atomic.applied)

    def test_duplicate_cannot_change_prepared_epoch(self):
        token = self.prepare()
        self.caller.confirm(token, self.event)
        payload = dict(fixtures.receipt(), source={k: self.event[k] for k in ("actor", "channel", "event_id", "evidence")},
                       expected_intent_version=1, expected_hold_version=0)
        with self.assertRaises(ValueError):
            rr.record(adapter, payload, self.fixture.store)
        self.assertEqual(len(self.fixture.atomic.posts), 1)

    def test_unsupported_backend_cannot_prepare_or_emit_receipt(self):
        self.fixture.atomic.fail = True
        with self.assertRaises(OSError):
            self.prepare()
        self.assertFalse(self.fixture.store.status(fixtures.W)["receipts"])

    def test_prepare_is_read_only_and_held_fails_closed(self):
        self.fixture.hold()
        self.assertEqual(self.caller.prepare(self.identity), {"prepared": False, "held": True})
        self.assertFalse(self.fixture.store.status(fixtures.W)["receipts"])
        self.assertFalse(self.fixture.atomic.posts)

    def test_both_guard_versions_are_required_and_strict(self):
        for guards in ({"expected_intent_version": 0},
                       {"expected_intent_version": True, "expected_hold_version": 0},
                       {"expected_intent_version": -1, "expected_hold_version": 0},
                       {"expected_intent_version": 0, "expected_hold_version": 2**63}):
            with self.subTest(guards=guards), self.assertRaises(ValueError):
                rr.record(adapter, dict(fixtures.receipt(), **guards), self.fixture.store)
        self.assertFalse(self.fixture.atomic.posts)


if __name__ == "__main__":
    unittest.main()
