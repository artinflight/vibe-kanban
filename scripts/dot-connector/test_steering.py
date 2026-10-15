import hashlib
import json
import unittest
import uuid
from unittest.mock import Mock

import steering
from prepare_connector import patched

SID, EID, RID = (str(uuid.uuid4()) for _ in range(3))
ARGS = dict(session_id=SID, execution_id=EID, request_id=RID, prompt="Use verified API")


def envelope(value):
    return {"success": True, "data": value}


def target(**changes):
    return dict(dict(session_id=SID, execution_id=EID, status="ready",
                     thread_id="isolated-thread", turn_id="isolated-turn"), **changes)


def receipt(**changes):
    return dict(dict(session_id=SID, execution_id=EID, request_id=RID,
                     thread_id="isolated-thread", turn_id="isolated-turn",
                     status="steered", delivered=True,
                     message_sha256=hashlib.sha256(ARGS["prompt"].encode()).hexdigest()), **changes)


def api():
    result = Mock()
    result.valid_uuid = lambda value: str(uuid.UUID(value))
    result.result = lambda value: {"content": [{"type": "text", "text": json.dumps(value)}], "isError": False}
    result.http_get.side_effect = [envelope(None), envelope(target())]
    result.post_fixed.return_value = receipt()
    return result


def content(reply):
    return json.loads(reply["content"][0]["text"])


class SteeringTests(unittest.TestCase):
    def test_active_exact_target_one_post_no_configuration_or_queue_mutation(self):
        service = api()
        reply = steering.steer(service, ARGS)
        self.assertFalse(reply["isError"])
        self.assertTrue(content(reply)["delivered"])
        path, payload = service.post_fixed.call_args.args
        self.assertEqual(path, f"/api/sessions/{SID}/steer")
        self.assertEqual(payload, dict(request_id=RID, execution_id=EID, message=ARGS["prompt"],
                                       thread_id="isolated-thread", turn_id="isolated-turn"))
        service.post_fixed.assert_called_once()
        self.assertNotIn(ARGS["prompt"], json.dumps(content(reply)))

    def test_replay_after_completion_only_reads_receipt(self):
        service = api()
        service.http_get.side_effect = [envelope(receipt())]
        self.assertTrue(content(steering.steer(service, ARGS))["delivered"])
        service.post_fixed.assert_not_called()
        service.http_get.assert_called_once()

    def test_changed_input_execution_session_or_request_id_never_reuses_receipt(self):
        for fields in [dict(message_sha256="wrong"), dict(execution_id=str(uuid.uuid4())),
                       dict(session_id=str(uuid.uuid4())), dict(request_id=str(uuid.uuid4()))]:
            with self.subTest(fields=fields):
                service = api()
                service.http_get.side_effect = [envelope(receipt(**fields))]
                with self.assertRaises(ValueError):
                    steering.steer(service, ARGS)
                service.post_fixed.assert_not_called()

    def test_idle_completed_racing_queued_unsupported_scheduled_and_failed_targets(self):
        for status in ["not_running", "not_ready", "unsupported_executor", "target_mismatch", "scheduled_work", "blocked"]:
            with self.subTest(status=status):
                service = api()
                service.http_get.side_effect = [envelope(None), envelope(target(status=status, thread_id=None, turn_id=None))]
                reply = steering.steer(service, ARGS)
                self.assertTrue(reply["isError"])
                self.assertEqual(content(reply)["status"], status)
                self.assertNotEqual(content(reply)["delivered"], True)
                service.post_fixed.assert_not_called()

    def test_native_rejection_or_uncertainty_never_claims_delivery(self):
        for status in ["not_running", "not_ready", "blocked", "unknown"]:
            service = api()
            service.post_fixed.return_value = receipt(status=status, delivered=None if status == "unknown" else False)
            reply = steering.steer(service, ARGS)
            self.assertTrue(reply["isError"])
            self.assertNotEqual(content(reply)["delivered"], True)
            service.post_fixed.assert_called_once()

    def test_timeout_reconciles_only_exact_receipt_without_resend(self):
        service = api()
        service.http_get.side_effect = [envelope(None), envelope(target()), envelope(receipt())]
        service.post_fixed.side_effect = TimeoutError("uncertain")
        reply = steering.steer(service, ARGS)
        self.assertTrue(content(reply)["delivered"])
        service.post_fixed.assert_called_once()

    def test_timeout_missing_wrong_or_unavailable_receipt_is_unknown(self):
        for value in [None, receipt(turn_id="replacement"), receipt(message_sha256="wrong"), OSError("unavailable")]:
            service = api()
            service.http_get.side_effect = [envelope(None), envelope(target()), value if isinstance(value, Exception) else envelope(value)]
            service.post_fixed.side_effect = OSError("lost")
            reply = steering.steer(service, ARGS)
            self.assertTrue(reply["isError"])
            self.assertEqual(content(reply)["status"], "unknown")
            service.post_fixed.assert_called_once()

    def test_malformed_success_is_never_delivery(self):
        for value in [None, {}, receipt(delivered=False), receipt(turn_id="wrong"), receipt(status="queued")]:
            service = api()
            service.post_fixed.return_value = value
            service.http_get.side_effect = [envelope(None), envelope(target()), envelope(None)]
            self.assertEqual(content(steering.steer(service, ARGS))["status"], "unknown")

    def test_missing_endpoint_fails_without_legacy_fallback(self):
        service = api()
        service.http_get.side_effect = ValueError("unsupported endpoint")
        with self.assertRaises(ValueError):
            steering.steer(service, ARGS)
        service.post_fixed.assert_not_called()

    def test_invalid_args_never_read_or_write(self):
        for changes in [dict(prompt=" "), dict(prompt="x" * 60001), dict(session_id="../bad"), dict(mode="auto")]:
            service = api()
            with self.assertRaises(ValueError):
                steering.steer(service, dict(ARGS, **changes))
            service.http_get.assert_not_called()
            service.post_fixed.assert_not_called()

    def test_read_receipt_is_read_only_and_checks_identity(self):
        service = api()
        service.http_get.side_effect = [envelope(receipt())]
        self.assertEqual(content(steering.get_receipt(service, dict(session_id=SID, request_id=RID)))["request_id"], RID)
        service.post_fixed.assert_not_called()

    def test_schema_explicit_write_and_read_with_stable_ids(self):
        write, read = steering.TOOLS
        self.assertFalse(write["annotations"]["readOnlyHint"])
        self.assertTrue(read["annotations"]["readOnlyHint"])
        self.assertIn("request_id", write["inputSchema"]["required"])
        self.assertIn("execution_id", write["inputSchema"]["required"])
        self.assertFalse(write["inputSchema"]["additionalProperties"])


class PreparationTests(unittest.TestCase):
    def test_patch_requires_capacity_correction_and_exact_anchors(self):
        for source in ["", '"connector_queued_for_capacity" "execution_capacity"']:
            with self.assertRaises(ValueError):
                patched(source)


if __name__ == "__main__":
    unittest.main()
