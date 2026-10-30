"""Prepare a candidate adapter; never edits the live connector."""
import argparse
import hashlib
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument("--adapter",required=True)
parser.add_argument("--sha256",required=True)
parser.add_argument("--output",required=True)
args=parser.parse_args()
source=Path(args.adapter).read_bytes()
if hashlib.sha256(source).hexdigest()!=args.sha256:
    raise SystemExit("Adapter changed; reconcile baseline")
text=source.decode()
anchors={
 "import approval_notifications":"import approval_notifications\nimport sidechat_connector",
 "event_reply = connector_events.handle(msg)":"event_reply = sidechat_connector.event_call(msg, connector_events.handle)",
 " + report_reconciliation.TOOLS":" + sidechat_connector.TOOLS + report_reconciliation.TOOLS",
 '            if name == "list_approval_notifications":':'            if name in sidechat_connector.NAMES:\n                return {"jsonrpc":"2.0","id":msg["id"],"result":result(sidechat_connector.call(name,args))}\n            if name == "list_approval_notifications":'
}
for old,new in anchors.items():
    if text.count(old)!=1:
        raise SystemExit("Integration anchor changed")
    text=text.replace(old,new)
if "connector_queued_for_capacity" not in text:
    raise SystemExit("Required capacity-queue fix missing")
output=Path(args.output)
output.mkdir(parents=True,exist_ok=False)
(output/"adapter.py").write_text(text)
(output/"sidechat_connector.py").write_text(
 'import sys\nfrom pathlib import Path\n'
 'sys.path.insert(0, "/mnt/vk-storage/vk-dot-sidechat-live/current")\n'
 'from connector import TOOLS, NAMES, call, event_call\n')
print("Candidate prepared; live files unchanged.")
