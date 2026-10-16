"""Exercise an installed facade using disposable data, never its live store.

The upstream is a metadata-only stub. This proves local installed discovery and
dispatch, not that ChatGPT has refreshed a conversation's tool inventory.
"""
import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
from unittest.mock import patch


def verify(facade, connector):
    from sidechat import Principal, Rejected

    reply = facade.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    definitions = reply["result"]["tools"]
    names = [tool["name"] for tool in definitions]
    assert len(names) == len(set(names)), "Duplicate advertised tool name"
    tools = {tool["name"]: tool for tool in definitions}
    assert connector.NAMES <= tools.keys(), "Sidechat tool missing from facade"
    append = tools["append_dot_reply"]["inputSchema"]
    assert append["properties"]["attention"]["enum"] == ["question", "action"]
    assert "attention" not in append["required"], "Legacy replies must remain supported"
    attention = tools["set_sidechat_attention"]["inputSchema"]
    assert set(attention["required"]) == {"thread", "workspace", "message", "action"}
    assert attention["properties"]["action"]["enum"] == ["question", "action", "resolve", "reopen"]

    def call(name, arguments):
        result = facade.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                "params": {"name": name, "arguments": arguments}})
        assert "error" not in result and not result["result"].get("isError"), "Dispatch failed"
        return json.loads(result["result"]["content"][0]["text"])

    with tempfile.TemporaryDirectory(prefix="dot-attention-contract-") as directory:
        # Patch the implementation module, not the installed shim's copied names.
        # Both authentication and data are isolated before calling any write tool.
        with patch.object(connector, "ROOT", Path(directory)), patch.dict(
            os.environ, {"VK_APPROVAL_PRINCIPAL": "attention-contract-fixture"}
        ):
            owner = Principal("attention-contract-fixture", "owner")
            store = connector.opened()
            try:
                def no_webhook(*_args):
                    raise AssertionError("A contract probe must never send a webhook")

                connector.Events(store, no_webhook)
                store.register_scope(owner.owner, "project", "issue", "workspace")
                store.register_scope(owner.owner, "project", "issue", "sibling")
                thread = store.resolve(owner, "project", "issue", "workspace")["id"]

                def seed():
                    return store.append(owner, thread, "workspace", str(uuid.uuid4()), "Synthetic owner")

                def arguments(message, **extra):
                    return dict(thread=thread, workspace="workspace", request=str(uuid.uuid4()),
                                body="Synthetic reply", reply_to=message["id"],
                                event_id="sidechat_" + message["id"], **extra)

                args = arguments(seed(), attention="question")
                reply = call("append_dot_reply", args)
                target = dict(thread=thread, workspace="workspace", message=reply["id"])
                state = call("set_sidechat_attention", dict(target, action="resolve"))
                assert state["attention"] == {"kind": "question", "resolved": True}
                assert call("append_dot_reply", args)["id"] == reply["id"], "Retry created another reply"
                page = call("read_sidechat_thread", {"thread": thread})
                message = next(m for m in page["messages"] if m["id"] == reply["id"])
                assert message["attention"]["resolved"] and not message["seen"], "Retry reset state"
                state = call("set_sidechat_attention", dict(target, action="reopen"))
                assert state["attention"] == {"kind": "question", "resolved": False}
                store.seen_replies(owner, thread, "sibling", [reply["id"]])
                call("set_sidechat_attention", dict(target, action="action"))
                call("set_sidechat_attention", dict(target, action="resolve"))
                page = call("read_sidechat_thread", {"thread": thread})
                message = next(m for m in page["messages"] if m["id"] == reply["id"])
                assert message["seen"] and message["attention"] == {"kind": "action", "resolved": True}

                legacy_args = arguments(seed())
                legacy = call("append_dot_reply", legacy_args)
                assert call("append_dot_reply", legacy_args)["id"] == legacy["id"]
                legacy_target = dict(thread=thread, workspace="workspace", message=legacy["id"])
                call("set_sidechat_attention", dict(legacy_target, action="action"))
                call("set_sidechat_attention", dict(legacy_target, action="resolve"))
                for forbidden in (dict(target, workspace="sibling", action="resolve"),
                                  dict(target, owner="spoof", action="resolve")):
                    try:
                        call("set_sidechat_attention", forbidden)
                    except Rejected:
                        pass
                    else:
                        raise AssertionError("Attention scope/identity guard bypassed")
                assert store.db.execute("SELECT count(*) FROM messages WHERE role='dot'").fetchone()[0] == 2
                assert store.db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 2
                assert store.db.execute("SELECT count(*) FROM sidechat_subscriptions").fetchone()[0] == 0
            finally:
                store.close()
    return {"installed_discovery_and_dispatch": "passed", "legacy_append": "passed",
            "attention_lifecycle_and_retry": "passed", "scope_guards": "passed",
            "live_store_opened": False, "network_calls": 0,
            "platform_inventory_adoption_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-directory", type=Path, required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.adapter_directory.resolve()))
    adapter = importlib.import_module("adapter")
    implementation = importlib.import_module(adapter.sidechat_connector.call.__module__)

    class MetadataOnly:
        def request(self, message):
            assert message["method"] == "tools/list", "Unexpected upstream operation"
            return {"jsonrpc": "2.0", "id": message["id"], "result": {"tools": []}}

    print(json.dumps(verify(adapter.Adapter(MetadataOnly()), implementation), indent=2))


if __name__ == "__main__":
    main()
