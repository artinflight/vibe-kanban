import unittest
import urllib.error
import uuid
from unittest.mock import Mock

import stop_control


IDENTITY = {k: str(uuid.uuid4()) for k in (*stop_control.IDENTITY, "request_id")}
ARGS = dict(IDENTITY, reason="user_request")
CREATED = "2026-10-17T00:00:00Z"


def envelope(data):
    return {"success": True, "data": data}


def target(**extra):
    return dict(IDENTITY, version=1, expected_created_at=CREATED, status="ready",
                serialized_admission=True, execution_status="running", run_reason="codingagent", dropped=False, **extra)


def receipt(**extra):
    return dict(ARGS, expected_created_at=CREATED, **dict(status="stopped", stopped=True, **extra))


def api():
    service = Mock()
    service.valid_uuid.side_effect = lambda value: str(uuid.UUID(value))
    service.result.side_effect = lambda value: value
    service.http_get.side_effect = [envelope(target()), envelope(None)]
    service.post_fixed.return_value = receipt()
    return service


class StopContracts(unittest.TestCase):
    def test_exact_one_post_and_supported_guarded_path(self):
        service = api()
        self.assertTrue(stop_control.stop(service, ARGS)["stopped"])
        service.post_fixed.assert_called_once_with(
            f'/api/execution-processes/{ARGS["execution_id"]}/stop-exact',
            dict(ARGS, expected_created_at=CREATED))

    def test_missing_guarded_backend_never_uses_legacy_stop(self):
        for code in (404, 405):
            service = api()
            service.http_get.side_effect = urllib.error.HTTPError("fixture", code, "absent", {}, None)
            result = stop_control.stop(service, ARGS)
            self.assertEqual("unsupported", result["status"])
            self.assertFalse(result["stopped"])
            service.post_fixed.assert_not_called()

    def test_unknown_fields_nil_uuid_wrong_scope_and_contradictory_target_are_rejected(self):
        for changes in ({"workspace_id": str(uuid.uuid4())}, {"serialized_admission": False},
                        {"dropped": True}, {"execution_status": "completed"}, {"run_reason": "devserver"}):
            service = api(); value = target(); value.update(changes)
            service.http_get.side_effect = [envelope(value)]
            with self.assertRaises(ValueError): stop_control.stop(service, ARGS)
            service.post_fixed.assert_not_called()
        for changes in ({"workspace": "unknown"}, {"execution_id": str(uuid.UUID(int=0))}, {"reason": "guess"}):
            service = api(); args = dict(ARGS, **changes)
            with self.assertRaises(ValueError): stop_control.stop(service, args)
            service.post_fixed.assert_not_called()

    def test_completed_failed_killed_unsupported_never_dispatch(self):
        for state in ("completed", "failed", "killed"):
            service = api(); value = target(); value.update(status="not_running", execution_status=state)
            service.http_get.side_effect = [envelope(value), envelope(None)]
            self.assertFalse(stop_control.stop(service, ARGS)["stopped"])
            service.post_fixed.assert_not_called()

    def test_replay_reads_receipt_even_after_execution_finished(self):
        service = api(); value = target(); value.update(status="not_running", execution_status="killed")
        service.http_get.side_effect = [envelope(value), envelope(receipt())]
        self.assertTrue(stop_control.stop(service, ARGS)["stopped"])
        service.post_fixed.assert_not_called()

    def test_timeout_reconciles_only_the_original_request(self):
        service = api(); service.post_fixed.side_effect = TimeoutError()
        service.http_get.side_effect = [envelope(target()), envelope(None), envelope(receipt())]
        self.assertTrue(stop_control.stop(service, ARGS)["stopped"])
        service.post_fixed.assert_called_once()
        service = api(); service.post_fixed.side_effect = TimeoutError()
        service.http_get.side_effect = [envelope(target()), envelope(None), envelope(None)]
        result = stop_control.stop(service, ARGS)
        self.assertIsNone(result["stopped"]); self.assertEqual("unknown", result["status"])
        service.post_fixed.assert_called_once()

    def test_malformed_or_foreign_receipts_never_confirm_stop(self):
        for changes in ({"workspace_id": str(uuid.uuid4())}, {"reason": "budget_exhausted"},
                        {"status": "unknown", "stopped": True}, {"request_id": str(uuid.uuid4())}):
            service = api(); value = receipt(); value.update(changes)
            service.http_get.side_effect = [envelope(target()), envelope(value)]
            with self.assertRaises(ValueError): stop_control.stop(service, ARGS)
            service.post_fixed.assert_not_called()

    def test_readback_never_dispatches_or_treats_killed_metadata_as_receipt(self):
        service = api(); value = target(); value.update(status="not_running", execution_status="killed")
        service.http_get.side_effect = [envelope(value), envelope(None)]
        result = stop_control.readback(service, IDENTITY)
        self.assertIsNone(result["receipt"])
        service.post_fixed.assert_not_called()

    def test_new_tools_explicitly_advertise_bounded_write_and_read(self):
        self.assertEqual(2, len(stop_control.TOOLS))
        self.assertTrue(stop_control.TOOLS[0]["annotations"]["destructiveHint"])
        self.assertTrue(stop_control.TOOLS[1]["annotations"]["readOnlyHint"])


if __name__ == "__main__":
    unittest.main()
