"""Disposable compiled-Rust HTTP acceptance only; no user delivery is invented.

Uses the installed restricted dispatcher/real receipt consumer. Transport and
ledger are bound in this child process to its private loopback test backend.
There is no Upstream, native worker, credentials, real ledger or live Vibe call.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

fixture = json.load(sys.stdin)
url = urlsplit(fixture['base'])
assert url.scheme == 'http' and url.hostname == '127.0.0.1' and url.port
assert not url.path and not url.query and not url.fragment
ledger = Path(fixture['ledger'])
root = Path(fixture['root']).resolve()
assert root.is_relative_to('/mnt/vk-storage')
assert ledger.is_absolute() and ledger.parent.resolve() == root / 'dev_assets'
sys.path.insert(0, '/home/mcp/code/vibe-dot-connector')
import adapter
import report_reconciliation as rr
adapter.BASE = fixture['base']
real_store = rr.Store
rr.Store = lambda: real_store(ledger)
connector = adapter.Adapter(None)
request = {'jsonrpc': '2.0', 'id': 'disposable-http-acceptance', 'method': 'tools/call',
           'params': {'name': 'record_workspace_report_delivery', 'arguments': fixture['receipt']}}
reply = connector.handle(request)
assert reply['result']['isError'] is False
result = json.loads(reply['result']['content'][0]['text'])
assert result['status'] == 'applied', result
assert result['proof']['authoritative_readback'] is False, result
print(json.dumps({'tool': request['params']['name'], 'result': result}))
