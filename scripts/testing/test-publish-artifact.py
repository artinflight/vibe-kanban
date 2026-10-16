"""Real HTTP acceptance for first-response artifact publication; no live writes."""
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import sys

sys.dont_write_bytecode = True

spec = importlib.util.spec_from_file_location("publisher", Path(__file__).parents[1] / "vk-publish-artifact.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)
FILE_ID = "e4be627d-9de5-4861-8a60-746ffb9f2478"
WORKSPACE_ID = "3ea0757d-b922-451a-95d0-9f9878f00b98"
SESSION_ID = "b75d26d8-755a-4668-9b52-b98e28967377"


class Publication(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ.get("VK_TEST_OUTPUT"))
        self.root = Path(self.temporary.name)
        self.payload = b"<!doctype html><title>Report</title><p>Chosen report</p>"
        self.uploads = 0
        self.bad_bytes = False
        self.uncertain = False
        self.viewer = True
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                if self.path == "/vk-artifact-viewer.html":
                    self.wfile.write(b"vk-artifact-viewer-v1" if owner.viewer else b"SPA fallback")
                else:
                    self.wfile.write(b"wrong file" if owner.bad_bytes else owner.payload)

            def do_POST(self):
                self.server.upload_path = self.path
                self.server.request_body = self.rfile.read(int(self.headers["Content-Length"]))
                owner.uploads += 1
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"uncertain" if owner.uncertain else json.dumps({"success": True, "data": {"id": FILE_ID}}).encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)
        self.file = self.root / "review.html"
        self.file.write_bytes(self.payload)

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.temporary.cleanup()

    def publish(self, **kwargs):
        return publisher.publish(self.file, self.origin, self.origin, self.root / "receipts",
                                 workspace_id=WORKSPACE_ID, session_id=SESSION_ID, **kwargs)

    def test_first_response_is_verified_web_markdown_and_retry_reuses_upload(self):
        result = self.publish(label="Frame-by-frame review")
        self.assertTrue(result["verified"])
        self.assertEqual(result["mode"], "html-preview")
        self.assertEqual(result["markdown"], "[Frame-by-frame review](" + self.origin + "/vk-artifact-viewer.html?id=" + FILE_ID + "&name=review.html)")
        self.assertIn(self.payload, self.server.request_body)
        self.assertEqual(self.server.upload_path, f"/api/workspaces/{WORKSPACE_ID}/attachments/upload?session_id={SESSION_ID}")
        self.assertEqual(self.publish()["attachment_id"], FILE_ID)
        self.assertEqual(self.uploads, 1)

    def test_download_does_not_need_html_viewer(self):
        self.viewer = False
        result = self.publish(download=True)
        self.assertEqual(result["url"], self.origin + "/api/attachments/" + FILE_ID + "/file")
        self.assertEqual(result["mode"], "download")

    def test_wrong_stored_bytes_deliver_no_link_and_retry_reuses_id(self):
        self.bad_bytes = True
        with self.assertRaisesRegex(ValueError, "did not match"):
            self.publish()
        self.bad_bytes = False
        self.assertTrue(self.publish()["verified"])
        self.assertEqual(self.uploads, 1)

    def test_uncertain_upload_is_not_blindly_repeated(self):
        self.uncertain = True
        with self.assertRaises(ValueError):
            self.publish()
        self.uncertain = False
        with self.assertRaisesRegex(ValueError, "uncertain outcome"):
            self.publish()
        self.assertEqual(self.uploads, 1)

    def test_missing_viewer_does_not_deliver_spa_fallback(self):
        self.viewer = False
        with self.assertRaisesRegex(ValueError, "does not have"):
            self.publish()
        self.assertEqual(self.uploads, 0)

    def test_report_with_unpublished_images_fails_before_upload(self):
        self.file.write_text('<img src="../private-frame.jpg">')
        with self.assertRaisesRegex(ValueError, "embedded resources"):
            self.publish()
        self.assertEqual(self.uploads, 0)

    def test_remote_uploads_and_credential_bearing_origins_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            publisher.publish(self.file, "https://example.invalid", self.origin, self.root)
        with self.assertRaisesRegex(ValueError, "credentials"):
            publisher.origin("https://user:password@example.invalid")
        self.assertEqual(self.uploads, 0)


if __name__ == "__main__":
    unittest.main()
