"""Verify installed signing transport offline with synthetic context and keys."""
import argparse
import base64
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock,patch
import urllib.parse


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transport-file',required=True)
    parser.add_argument('--sha256',required=True)
    args=parser.parse_args()
    source=Path(args.transport_file).read_bytes()
    if hashlib.sha256(source).hexdigest()!=args.sha256:raise SystemExit('Transport changed; review current source')
    spec=importlib.util.spec_from_file_location('sidechat_transport_under_test',args.transport_file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    event={'eventId':'fixture-event','name':'vk.sidechat.owner_message.created',
        'timestamp':'2026-10-16T00:00:00+00:00','cursor':None,
        'data':{'thread_id':'fixture-thread','project_id':'fixture-project',
            'issue_id':'fixture-issue','workspace_id':'fixture-workspace','message_id':'fixture-message',
            'sequence':1,'author_type':'authenticated_owner','intent':'sidechat_reply_requested',
            'reply_scope':'same_thread_only','message_sha256':hashlib.sha256(b'fixture').hexdigest()}}
    key=b'x'*32
    secret='whsec_'+base64.b64encode(key).decode()
    connection=Mock();connection.getresponse.return_value.status=200
    connection.getresponse.return_value.read.return_value=b''
    with patch.object(module,'public_address',return_value=(urllib.parse.urlsplit('https://fixture.invalid/callback'),'192.0.2.1')),\
         patch.object(module.socket,'create_connection',return_value=Mock()),\
         patch.object(module.ssl,'create_default_context',return_value=Mock()),\
         patch.object(module.http.client,'HTTPSConnection',return_value=connection):
        module.webhook('https://fixture.invalid/callback',secret,'fixture-subscription','fixture-event',event)
    method,path,raw,headers=connection.request.call_args.args
    assert method=='POST' and path=='/callback'
    assert json.loads(raw)==event
    assert headers['webhook-id']==event['eventId']
    signature=base64.b64encode(hmac.new(key,event['eventId'].encode()+b'.'+headers['webhook-timestamp'].encode()+b'.'+raw,hashlib.sha256).digest()).decode()
    assert headers['webhook-signature']=='v1,'+signature
    print(json.dumps({'transport_sha256':args.sha256,'all_context_preserved_in_signed_bytes':True,
                      'standard_webhook_signature_verified':True,'live_network_calls':0,'private_runtime_data_read':False}))


if __name__=='__main__':main()
