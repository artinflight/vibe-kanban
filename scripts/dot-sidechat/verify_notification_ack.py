"""Fixture-only candidate checks against pinned deployed Store/adapter bytes.

Does not open live state, call a live tool, or install/reload anything.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


def pinned(path, digest):
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('Shared source changed; reconcile before verification')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--store-sha', required=True)
    p.add_argument('--adapter', type=Path, required=True)
    p.add_argument('--adapter-sha', required=True)
    a = p.parse_args()
    pinned(a.bundle/'sidechat.py', a.store_sha); pinned(a.adapter, a.adapter_sha)
    sys.path[:0] = [str(a.candidate), str(a.bundle), str(Path(__file__).parent), str(a.adapter.parent)]
    load('sidechat', a.bundle/'sidechat.py')
    import connector
    import test_notification_ack
    import notification_ack
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_notification_ack)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    shim = types.SimpleNamespace(TOOLS=connector.TOOLS, NAMES=connector.NAMES,
                                call=connector.call, event_call=lambda *unused: None)
    with patch.dict(sys.modules, {'sidechat_connector': shim}):
        adapter = load('ack_fixture_adapter', a.adapter)
    test = test_notification_ack.NotificationAcknowledgementTests(); test.setUp()
    try:
        upstream = Mock(); facade = adapter.Adapter(upstream)
        def dispatch(name, args):
            return facade.handle({'jsonrpc':'2.0','id':7,'method':'tools/call',
                'params':{'name':name,'arguments':args}})['result']
        with patch.object(connector,'ROOT',test.path.parent), patch.object(connector,'owner',return_value='alice'), \
             patch.object(adapter.urllib.request,'build_opener',side_effect=AssertionError('No network in fixtures')):
            data = dispatch(notification_ack.INVENTORY, {'workspace_id':test.workspace})
            page = json.loads(data['content'][0]['text'])
            row = next(r for r in page['notifications'] if r['message_id'] == test.first)
            selection = {k:row[k] for k in ('thread_id','message_id','state_token')}
            data = dispatch(notification_ack.ACKNOWLEDGE, {'workspace_id':test.workspace,'items':[selection]})
            proof = json.loads(data['content'][0]['text'])['outcomes'][0]
            assert proof['outcome'] == 'acknowledged' and proof['seen']
            assert test.state(test.other)['seen'] == 0
            assert test.state(test.conversation)['seen'] == 0
            upstream.request.assert_not_called()
    finally:
        test.tearDown()
    print(json.dumps({'fixtureTestsAgainstDeployedStore':result.testsRun,
        'actualAdapterMockedDispatch':'inventory and acknowledgement pass',
        'adapterSha256':a.adapter_sha,'storeSha256':a.store_sha,
        'liveToolCalls':0,'liveStateOpened':False,'credentialChanges':0,'reloads':0,'agentLaunches':0}))


if __name__ == '__main__':
    main()
