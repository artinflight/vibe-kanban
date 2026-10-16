#!/usr/bin/env python3
"""Publish one explicit deliverable through VK's existing attachment API."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


class Resources(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if value and ((name == "src" and tag != "a") or
                          (tag == "link" and name == "href") or
                          (tag == "object" and name == "data")):
                if not value.startswith("data:"):
                    raise ValueError("HTML preview requires embedded resources; inline " + value[:120])


def origin(value):
    url = urllib.parse.urlsplit(value)
    if (url.scheme not in ("http", "https") or not url.hostname or url.username or
            url.password or url.path not in ("", "/") or url.query or url.fragment):
        raise ValueError("Expected an HTTP(S) origin without credentials, path or query")
    return value.rstrip("/")


def request(url, data=None, headers=None, context=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30, context=context) as response:
        return response.read()


def save_receipt(path, record):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex)
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    temporary.replace(path)


def publish(path, api_base, public_origin, receipts, label=None, download=False, ca_file=None,
            workspace_id=None, session_id=None):
    api_base, public_origin = origin(api_base), origin(public_origin)
    if urllib.parse.urlsplit(api_base).hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("The upload API must be a loopback VK origin")
    if not workspace_id or not session_id:
        raise ValueError("Run inside a VK task or supply --workspace-id and --session-id")
    workspace_id, session_id = str(uuid.UUID(workspace_id)), str(uuid.UUID(session_id))
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("Choose one regular deliverable of at most 50 MiB")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    context = ssl.create_default_context(cafile=ca_file)
    if ca_file:
        context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    html = not download and path.suffix.lower() in (".html", ".htm")
    if html:
        Resources().feed(data.decode("utf-8-sig"))
        viewer = request(public_origin + "/vk-artifact-viewer.html", context=context)
        if b"vk-artifact-viewer-v1" not in viewer:
            raise ValueError("The public origin does not have the VK artifact viewer")
    receipts = Path(receipts)
    receipts.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((api_base + "\0" + workspace_id + "\0" + session_id + "\0" + path.name + "\0" + digest).encode()).hexdigest()
    receipt = receipts / (key + ".json")
    if receipt.exists():
        record = json.loads(receipt.read_text())
        if record.get("pending"):
            raise ValueError("An earlier upload has an uncertain outcome; reconcile SHA256 " + digest)
        file_id = str(uuid.UUID(record["attachment_id"]))
    else:
        boundary = "vk-artifact-" + uuid.uuid4().hex
        # RFC 7578 filename uses an ASCII fallback; UTF-8 originals live in the receipt.
        filename = path.name.encode("ascii", "replace").decode().replace('"', "_").replace("\r", "_").replace("\n", "_")
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\n'
                'Content-Type: application/octet-stream\r\n\r\n').encode() + data + f"\r\n--{boundary}--\r\n".encode()
        save_receipt(receipt, {"pending": True, "sha256": digest, "source": str(path), "api_base": api_base})
        upload_path = f"/api/workspaces/{workspace_id}/attachments/upload?session_id={session_id}"
        payload = json.loads(request(api_base + upload_path, body,
                                     {"Content-Type": "multipart/form-data; boundary=" + boundary}, context))
        if not payload.get("success"):
            raise ValueError("VK rejected the attachment upload")
        file_id = str(uuid.UUID(payload["data"]["id"]))
        record = {"attachment_id": file_id, "sha256": digest, "source": str(path), "api_base": api_base,
                  "workspace_id": workspace_id, "session_id": session_id}
        # Preserve the acknowledged upload before verification; retries reuse this ID.
        save_receipt(receipt, record)
    api_path = "/api/attachments/" + file_id + "/file"
    if hashlib.sha256(request(api_base + api_path, context=context)).hexdigest() != digest:
        raise ValueError("Stored attachment did not match the source; no link delivered")
    if hashlib.sha256(request(public_origin + api_path, context=context)).hexdigest() != digest:
        raise ValueError("Operator-facing attachment did not match; no link delivered")
    query = urllib.parse.urlencode({"id": file_id, "name": path.name})
    url = public_origin + ("/vk-artifact-viewer.html?" + query if html else api_path)
    text = (label or path.name).replace("\n", " ").replace("\r", " ")
    for char in ("\\", "[", "]"):
        text = text.replace(char, "\\" + char)
    record.update({"url": url, "markdown": f"[{text}]({url})", "mode": "html-preview" if html else "download", "verified": True})
    save_receipt(receipt, record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file")
    parser.add_argument("--label")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--api-base", default=os.environ.get("VK_ARTIFACT_API_BASE", "http://127.0.0.1:4720"))
    parser.add_argument("--public-origin", default=os.environ.get("VK_ARTIFACT_PUBLIC_ORIGIN", "https://vibe.local"))
    parser.add_argument("--receipts-dir", default="/mnt/vk-storage/vk-published-artifacts/receipts")
    parser.add_argument("--ca-file", default=os.environ.get("VK_ARTIFACT_CA_FILE"))
    parser.add_argument("--workspace-id", default=os.environ.get("VK_WORKSPACE_ID"))
    parser.add_argument("--session-id", default=os.environ.get("VK_SESSION_ID"))
    args = parser.parse_args()
    try:
        if args.receipts_dir.startswith("/mnt/vk-storage/") and not os.path.ismount("/mnt/vk-storage"):
            raise ValueError("Mount /mnt/vk-storage before publishing")
        result = publish(args.file, args.api_base, args.public_origin, args.receipts_dir, args.label, args.download,
                         args.ca_file, args.workspace_id, args.session_id)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, urllib.error.URLError) as error:
        print("Artifact publication failed: " + str(error) + ". Do not blindly retry an uncertain upload; reconcile its attachment first.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
