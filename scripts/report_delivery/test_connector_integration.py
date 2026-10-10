"""Caller -> actual connector dispatcher/ledger -> existing synthetic backend.

Set VK_CONNECTOR_SOURCE to the reviewed isolated connector candidate. Without it,
these integration cases are explicitly skipped; the ordinary caller suite runs.
"""
import os
import json
from pathlib import Path
import sys
import threading
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

    def prepare_nonzero_intent(self):
        self.fixture.hold(True, "initial-held-fixture")
        self.fixture.hold(False, "initial-release-fixture")
        self.fixture.atomic.epoch = 7
        return self.prepare()

    def receipt_snapshot(self):
        with self.fixture.store.locked() as db:
            return dict(db.execute("SELECT receipt_id,payload,backend_intent_version,hold_version "
                                   "FROM receipts").fetchone())

    def lose_first_commit_response(self):
        original = self.fixture.atomic.__call__
        first = [True]
        def uncertain(api, wid, suffix, method="GET", payload=None):
            value = original(api, wid, suffix, method, payload)
            if suffix == "review-receipts" and first[0]:
                first[0] = False
                raise TimeoutError("Synthetic backend committed; response lost")
            return value
        self.fixture.backend.side_effect = uncertain

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

    def test_pending_retries_preserve_nonzero_pins_and_payload_across_restart(self):
        token = self.prepare_nonzero_intent()
        self.fixture.atomic.fail = True
        self.assertEqual(self.caller.confirm(token, self.event)["status"], "blocked_backend")
        snapshot = self.receipt_snapshot()
        self.assertEqual((snapshot["backend_intent_version"], snapshot["hold_version"]), (7, 2))
        fresh_store = type(self.fixture.store)(self.fixture.store.path)
        # New caller/store instances; the connector ledger is the same durable file.
        for retry in (lambda: Caller(self.caller.path, self.tools).retry(token),
                      lambda: rr.consume(adapter, fresh_store, snapshot["receipt_id"]),
                      lambda: rr.reconcile(adapter, {"workspace_id": fixtures.W}, self.fixture.store)):
            retry()
            self.assertEqual(self.receipt_snapshot(), snapshot)
        self.fixture.atomic.fail = False
        self.assertEqual(self.caller.retry(token)["status"], "applied")
        self.assertEqual(self.receipt_snapshot(), snapshot)
        self.assertEqual(self.fixture.atomic.posts[0]["intent_version"], 7)

    def test_lost_backend_commit_response_retries_identical_request_without_rebasing(self):
        token = self.prepare_nonzero_intent()
        self.lose_first_commit_response()
        first = self.caller.confirm(token, self.event)
        self.assertEqual(first["status"], "blocked_backend")
        self.assertFalse(first["readback_fresh"])
        snapshot = self.receipt_snapshot()
        original_request = dict(self.fixture.atomic.posts[0])
        result = Caller(self.caller.path, self.tools).retry(token)
        self.assertEqual(result["status"], "applied")
        self.assertTrue(result["readback_fresh"])
        self.assertEqual(self.fixture.atomic.posts[1], original_request)
        self.assertEqual(self.receipt_snapshot(), snapshot)
        self.assertEqual(len(self.fixture.atomic.applied), 1)

    def test_lost_commit_response_then_mirrored_hold_release_cannot_replay_or_adopt(self):
        token = self.prepare_nonzero_intent()
        self.lose_first_commit_response()
        self.caller.confirm(token, self.event)
        snapshot = self.receipt_snapshot()
        self.fixture.hold(True, "manual-held-after-lost-commit")
        self.assertEqual(rr.consume(adapter, self.fixture.store, snapshot["receipt_id"])["status"], "held")
        self.assertEqual(self.receipt_snapshot(), snapshot)
        self.fixture.hold(False, "manual-release-after-lost-commit")
        self.assertEqual(self.fixture.atomic.epoch, 9)
        for retry in (lambda: rr.consume(adapter, self.fixture.store, snapshot["receipt_id"]),
                      lambda: self.caller.retry(token)):
            self.assertEqual(retry()["status"], "stale_intent")
            self.assertEqual(self.receipt_snapshot(), snapshot)
        self.assertEqual(len(self.fixture.atomic.posts), 1)

    def test_lost_commit_response_then_offline_hold_release_preserves_local_pin(self):
        token = self.prepare_nonzero_intent()
        self.lose_first_commit_response()
        self.caller.confirm(token, self.event)
        snapshot = self.receipt_snapshot()
        self.fixture.atomic.fail = True
        self.fixture.hold(True, "offline-held-after-lost-commit")
        self.fixture.hold(False, "offline-release-after-lost-commit")
        self.fixture.atomic.fail = False
        self.assertEqual(self.fixture.atomic.epoch, 7)
        self.assertEqual(self.caller.retry(token)["status"], "stale_intent")
        self.assertEqual(self.receipt_snapshot(), snapshot)
        self.assertEqual(len(self.fixture.atomic.posts), 1)

    def test_lost_commit_response_then_ui_intent_change_preserves_backend_pin(self):
        token = self.prepare_nonzero_intent()
        self.lose_first_commit_response()
        self.caller.confirm(token, self.event)
        snapshot = self.receipt_snapshot()
        self.fixture.atomic.held = True
        self.fixture.atomic.epoch += 1
        self.assertEqual(self.caller.retry(token)["status"], "stale_intent")
        self.fixture.atomic.held = False
        self.fixture.atomic.epoch += 1
        self.assertEqual(self.caller.retry(token)["status"], "stale_intent")
        self.assertEqual(self.receipt_snapshot(), snapshot)
        self.assertEqual(len(self.fixture.atomic.posts), 1)

    def test_lost_readback_after_commit_never_returns_cached_flag_as_fresh(self):
        token = self.prepare_nonzero_intent()
        self.fixture.readback.side_effect = TimeoutError("Synthetic summary response lost")
        first = self.caller.confirm(token, self.event)
        snapshot = self.receipt_snapshot()
        self.assertEqual(first["status"], "blocked_backend")
        self.assertFalse(first["readback_fresh"])
        self.assertNotIn("authoritative_readback", first["proof"])
        again = self.caller.retry(token)
        self.assertFalse(again["readback_fresh"])
        self.assertEqual(self.receipt_snapshot(), snapshot)
        self.fixture.readback.side_effect = lambda _: {"summaries": [
            {"workspace_id": fixtures.W, "has_unseen_turns": True}]}
        result = self.caller.retry(token)
        self.assertTrue(result["readback_fresh"])
        self.assertTrue(result["proof"]["authoritative_readback"])
        self.assertTrue(result["proof"]["authoritative_readback_observed_at"])
        self.assertEqual(self.receipt_snapshot(), snapshot)
        self.assertEqual(len(self.fixture.atomic.applied), 1)
        self.assertTrue(all(request == self.fixture.atomic.posts[0] for request in self.fixture.atomic.posts))

    def test_legacy_null_intent_stays_null_instead_of_adopting_current_backend(self):
        self.fixture.atomic.fail = True
        result = rr.record(adapter, fixtures.receipt(), self.fixture.store)
        snapshot = self.receipt_snapshot()
        self.assertIsNone(snapshot["backend_intent_version"])
        self.fixture.atomic.fail = False
        self.fixture.atomic.epoch = 7
        self.assertEqual(rr.consume(adapter, self.fixture.store, result["receipt_id"])["status"], "stale_intent")
        self.assertEqual(self.receipt_snapshot(), snapshot)
        self.assertFalse(self.fixture.atomic.posts)

    def test_applied_cache_after_manual_hold_has_only_historical_readback(self):
        token = self.prepare_nonzero_intent()
        first = self.caller.confirm(token, self.event)
        self.assertTrue(first["readback_fresh"])
        snapshot = self.receipt_snapshot()
        reads = self.fixture.readback.call_count
        self.fixture.hold(True, "held-after-confirmed-apply")
        self.fixture.atomic.newer = True
        cached = Caller(self.caller.path, self.tools).retry(token)
        self.assertEqual(cached["status"], "applied")
        self.assertFalse(cached["readback_fresh"])
        self.assertNotIn("authoritative_readback", cached["proof"])
        self.assertFalse(cached["historical_readback"]["has_unseen_turns"])
        duplicate = rr.consume(adapter, self.fixture.store, snapshot["receipt_id"])
        self.assertFalse(duplicate["readback_fresh"])
        self.assertNotIn("proof", duplicate)
        self.assertEqual(self.fixture.readback.call_count, reads)
        audit = rr.status(adapter, {"workspace_id": fixtures.W}, self.fixture.store)
        self.assertFalse(audit["readback_fresh"])
        self.assertEqual(audit["proof_origin"], "receipt_ledger")
        self.assertEqual(self.receipt_snapshot(), snapshot)
        self.assertEqual(len(self.fixture.atomic.posts), 1)

    def test_concurrent_uncertain_retry_returns_saved_proof_only_as_historical(self):
        token = self.prepare_nonzero_intent()
        original = self.fixture.atomic.__call__
        entered, release = threading.Event(), threading.Event()
        first = [True]
        results, errors = [], []
        def race(api, wid, suffix, method="GET", payload=None):
            if suffix == "review-receipts" and first[0]:
                first[0] = False
                entered.set()
                if not release.wait(5):
                    raise TimeoutError()
                original(api, wid, suffix, method, payload)
                raise TimeoutError("Concurrent duplicate response lost")
            return original(api, wid, suffix, method, payload)
        self.fixture.backend.side_effect = race
        def confirm():
            try:
                results.append(self.caller.confirm(token, self.event))
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=confirm)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertTrue(self.caller.confirm(token, self.event)["readback_fresh"])
        finally:
            release.set()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertEqual(results[0]["status"], "applied")
        self.assertFalse(results[0]["readback_fresh"])
        self.assertNotIn("authoritative_readback", results[0]["proof"])
        self.assertEqual(len(self.fixture.atomic.applied), 1)


if __name__ == "__main__":
    unittest.main()
