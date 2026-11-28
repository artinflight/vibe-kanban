"""Bounded transport/Bridge tests. Fixture HTTP is not native acceptance proof."""
import copy
from http.client import HTTPConnection as RealConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import uuid

from test_monitor import m, FakeBridge
from test_native_adapter import response
import native_adapter as n
import native_http as h


def config():
    binding=FakeBridge().binding()
    return {'activation_approved':True, 'admission_protocol':n.PROTOCOL,
        'workspace_id':binding['workspace_id'], 'session_id':binding['session_id'],
        'native_transport':{'enabled':True, 'route':'existing_local_gateway_v1',
            'executor_config_sha256':binding['executor_config_sha256'],
            'max_validation_age_seconds':60}}


class BoundedHTTP(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'state.sqlite'
        self.store=m.Store(self.path);self.fake=FakeBridge()
        self.store.observations(self.fake.samples,{},time.time())
        self.store.dispatch(self.fake.samples,self.fake,self.path)
        self.document=self.fake.calls[0];self.wire=n.request(self.document)
        self.client=h.LocalNativeHTTP(self.fake.binding())
        self.lookup=f"{h.COLLECTION}/{self.document['batch_id']}?intent_sha256={self.document['intent_sha256']}"

    def tearDown(self):
        self.store.close();self.temp.cleanup()

    def test_disabled_flags_never_construct_transport_or_connect(self):
        for change in ('activation','transport','both'):
            c=config()
            if change in ('activation','both'):c['activation_approved']=False
            if change in ('transport','both'):c['native_transport']['enabled']=False
            with patch.object(h,'HTTPConnection') as socket, patch.object(h,'LocalNativeHTTP') as client:
                bridge=m.Bridge(c)
                for operation in (bridge.ready,bridge.binding,lambda:bridge.send(self.document),
                                  lambda:bridge.lookup('x','y',self.document)):
                    with self.assertRaises(m.ReviewedProtocolUnavailable):operation()
                socket.assert_not_called();client.assert_not_called()

    def test_binding_configuration_is_explicit_and_not_a_url_option(self):
        changes=[('route','http://127.0.0.1:9999'),('extra_header','Authorization'),
                 ('executor_config_sha256','bad'),('max_validation_age_seconds',0),
                 ('max_validation_age_seconds',301),('max_validation_age_seconds',True)]
        for key,value in changes:
            c=config();c['native_transport'][key]=value
            with self.subTest(key=key),patch.object(h,'HTTPConnection') as socket:
                with self.assertRaises(ValueError):m.Bridge(c)
                socket.assert_not_called()
        for key in ('workspace_id','session_id','admission_protocol'):
            c=config();c[key]='invalid'
            with self.assertRaises(ValueError):m.Bridge(c)

    def test_method_path_and_get_shape_reject_before_socket(self):
        cases=[('DELETE',h.COLLECTION,None),('PUT',h.COLLECTION,self.wire),
               ('POST',h.COLLECTION+'/',self.wire),('GET',h.COLLECTION,None),
               ('POST','http://127.0.0.1:4720'+h.COLLECTION,self.wire),
               ('GET',self.lookup+'&extra=1',None),('GET',self.lookup,{}),
               ('GET',self.lookup.replace('/batches/','/batches/../'),None),
               ('GET',self.lookup.replace('/batches/','/batches/%2f'),None),
               ('GET',self.lookup+'\r\nOrigin: null',None),
               ('GET',self.lookup.replace(self.document['batch_id'],str(uuid.UUID(int=0))),None),
               ('GET',self.lookup.replace(self.document['intent_sha256'],'X'*64),None)]
        with patch.object(h,'HTTPConnection') as socket:
            for method,path,body in cases:
                with self.subTest(method=method,path=path), self.assertRaises(ValueError):
                    self.client(method,path,body)
            socket.assert_not_called()

    def test_intent_owner_config_hash_and_validation_cannot_drift(self):
        cases=[]
        for key in ('workspace_id','session_id','executor_config_sha256'):
            body=copy.deepcopy(self.wire);body['intent'][key]='0'*64
            body['intent_sha256']=n.digest(body['intent']);cases.append(body)
        body=copy.deepcopy(self.wire);body['intent']['prompt']+='changed';cases.append(body)
        body=copy.deepcopy(self.wire);body['intent']['prompt']='x'*h.MAX_BYTES
        body['intent_sha256']=n.digest(body['intent']);cases.append(body)
        for field,value in [('eligible_incident_ids',[]),('evidence_sha256','bad')]:
            body=copy.deepcopy(self.wire);body['validation'][field]=value;cases.append(body)
        body=copy.deepcopy(self.wire);body['extra']=True;cases.append(body)
        with patch.object(h,'HTTPConnection') as socket:
            for body in cases:
                with self.assertRaises(ValueError):self.client('POST',h.COLLECTION,body)
            socket.assert_not_called()

    def test_fixed_destination_headers_and_canonical_request(self):
        with patch.object(h,'HTTPConnection') as constructor:
            conn=constructor.return_value;reply=conn.getresponse.return_value
            reply.status=200;reply.getheader.return_value='application/json; charset=utf-8'
            reply.read.return_value=b'{}'
            self.client('POST',h.COLLECTION,self.wire)
            constructor.assert_called_once_with('127.0.0.1',4720,timeout=10)
            conn.request.assert_called_once_with('POST',h.COLLECTION,
                body=n.canonical(self.wire).encode(),headers={'Accept':'application/json',
                'Connection':'close','Content-Type':'application/json'})
            conn.close.assert_called_once()

    def test_redirect_access_error_or_bad_response_never_retries_or_falls_back(self):
        cases=[(status,'application/json',b'{}') for status in (301,302,307,308,401,403,404,409,429,500,503)]
        cases += [(200,'text/html',b'{}'),(200,'application/json',b'{"x":1,"x":2}'),
                  (200,'application/json',b'{"x":NaN}'),(200,'application/json',b'['),
                  (200,'application/json',b'[]'),(200,'application/json',b'\xff'),
                  (200,'application/json',b'x'*(h.MAX_BYTES+1))]
        for status,content,raw in cases:
            with self.subTest(status=status,raw=raw[:30]),patch.object(h,'HTTPConnection') as constructor:
                conn=constructor.return_value;reply=conn.getresponse.return_value
                reply.status=status;reply.getheader.return_value=content;reply.read.return_value=raw
                with self.assertRaises(ValueError):self.client('GET',self.lookup,None)
                constructor.assert_called_once_with('127.0.0.1',4720,timeout=10)
                self.assertEqual(conn.request.call_count,1);conn.close.assert_called_once()

    def test_production_bridge_requires_own_receipt_but_reconciles_old_config(self):
        c=config();bridge=m.Bridge(c)
        for field in ('workspace_id','session_id'):
            changed=copy.deepcopy(self.document);changed['intent'][field]=str(uuid.uuid4())
            changed['intent_sha256']=n.digest(changed['intent'])
            with patch.object(h,'HTTPConnection') as socket:
                with self.assertRaises(ValueError):
                    bridge.lookup(changed['batch_id'],changed['intent_sha256'],changed)
                socket.assert_not_called()
        c['native_transport']['executor_config_sha256']='b'*64
        bridge=m.Bridge(c)
        with patch.object(bridge,'transport',return_value=response(self.document)) as transport:
            result=bridge.lookup(self.document['batch_id'],self.document['intent_sha256'],self.document)
            self.assertEqual(result['kind'],'accepted');self.assertEqual(transport.call_args.args[0],'GET')
            with self.assertRaises(ValueError):bridge.send(self.document)
            self.assertEqual(transport.call_count,1)


class BridgeHTTPFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'state.sqlite'
        self.store=m.Store(self.path);self.fake=FakeBridge();self.calls=[];self.receipt=None
        self.outcome='accepted';self.http_status=200;self.drop=False
        fixture=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                wire=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                fixture.calls.append(('POST',self.path,dict(self.headers)))
                fixture.receipt=response(wire,fixture.outcome)
                if fixture.drop:
                    fixture.drop=False;self.close_connection=True;return
                self.reply(fixture.receipt)
            def do_GET(self):
                fixture.calls.append(('GET',self.path,dict(self.headers)));self.reply(fixture.receipt)
            def reply(self,body):
                self.send_response(fixture.http_status);self.send_header('Content-Type','application/json')
                self.end_headers();self.wfile.write(n.canonical(body).encode())
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        def remap(host,port,timeout):
            self.assertEqual((host,port),('127.0.0.1',4720))
            return RealConnection('127.0.0.1',self.server.server_port,timeout=timeout)
        self.patch=patch.object(h,'HTTPConnection',remap);self.patch.start()
        self.bridge=m.Bridge(config());self.bridge.observe=self.fake.observe
        self.store.observations(self.fake.samples,{},time.time())

    def tearDown(self):
        self.patch.stop();self.server.shutdown();self.server.server_close();self.thread.join()
        self.store.close();self.temp.cleanup()

    def poll(self):return self.store.dispatch(self.fake.samples,self.bridge,self.path)

    def test_real_http_commit_loss_restart_get_only_and_no_execution_recovery(self):
        self.drop=True
        self.assertEqual(self.poll(),'unknown')
        self.store.close();self.store=m.Store(self.path)
        self.assertEqual(self.poll(),'held_prior_delivery')
        self.receipt['execution_status']='completed'
        self.assertEqual(self.poll(),'no_action')
        self.assertEqual([v[0] for v in self.calls],['POST','GET','GET'])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents WHERE recovered IS NULL').fetchone()[0],2)
        for _,_,headers in self.calls:
            self.assertFalse(any(k.lower() in ('authorization','origin') or k.lower().startswith('x-relay') for k in headers))

    def test_deferral_needs_new_validation_and_preserves_exact_intent(self):
        self.outcome='deferred';at=time.time()
        self.bridge.observe=lambda key:{**self.fake.observe(key),'at':at}
        self.assertEqual(self.poll(),'deferred')
        row=self.store.db.execute('SELECT * FROM batches').fetchone();before=self.store.document(row)
        self.assertEqual(self.poll(),'deferred_fresh_validation_required')
        self.assertEqual(len(self.calls),1)
        self.outcome='accepted';self.bridge.observe=lambda key:{**self.fake.observe(key),'at':at+0.001}
        self.assertEqual(self.poll(),'accepted')
        row=self.store.db.execute('SELECT * FROM batches').fetchone();after=self.store.document(row)
        self.assertEqual(before['intent'],after['intent']);self.assertEqual(before['batch_id'],after['batch_id'])
        self.assertNotEqual(before['attempt_id'],after['attempt_id'])

    def test_status_alone_is_unknown_and_restart_never_resubmits(self):
        self.http_status=409
        self.assertEqual(self.poll(),'unknown')
        self.store.close();self.store=m.Store(self.path)
        self.assertEqual(self.poll(),'held_prior_delivery')
        self.assertEqual([v[0] for v in self.calls],['POST','GET'])
        self.assertEqual(self.store.db.execute('SELECT status FROM batches').fetchone()[0],'unknown')

    def test_definite_rejection_is_terminal_without_repeat(self):
        self.outcome='rejected'
        self.assertEqual(self.poll(),'rejected');self.assertEqual(self.poll(),'no_action')
        self.assertEqual([v[0] for v in self.calls],['POST'])


if __name__=='__main__':unittest.main()
