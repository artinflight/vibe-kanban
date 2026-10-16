"""Additive connector hook. Installed through an exact-baseline adapter patch."""
import json
import os
from pathlib import Path
from sidechat import Store, Principal, Rejected
from events import Events

ROOT = Path(os.environ.get("VK_SIDECHAT_STATE", "/home/mcp/.config/vibe-dot-connector/sidechat"))
CONTRACTS = json.loads(Path(__file__).with_name("contracts.json").read_text())
TOOLS = CONTRACTS["tools"]
NAMES = {tool["name"] for tool in TOOLS}


def owner():
    value=os.environ.get("VK_APPROVAL_PRINCIPAL")
    if not value:
        raise Rejected("Authenticated connector owner is not configured")
    return value


def opened():
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    return Store(ROOT/"threads.sqlite")


def call(name,args):
    store=opened()
    try:
        return store.tool(Principal(owner(),"dot"),name,args)
    finally:
        store.close()


def event_call(message, approval_handler):
    method=message.get("method")
    params=message.get("params") or {}
    if method=="events/list":
        original=approval_handler(message)
        if original is None or "error" in original:
            return original
        # Never replace or mutate the existing approval event definitions.
        original["result"]["events"]=original["result"].get("events",[])+CONTRACTS["events"]
        return original
    if method not in ("events/subscribe","events/unsubscribe") or params.get("name")!=CONTRACTS["events"][0]["name"]:
        return approval_handler(message)
    from approval_event_store import webhook
    store=opened()
    try:
        result=Events(store,webhook).subscribe(Principal(owner(),"owner"),params,unsubscribe=method=="events/unsubscribe")
        return {"jsonrpc":"2.0","id":message.get("id"),"result":result}
    finally:
        store.close()
