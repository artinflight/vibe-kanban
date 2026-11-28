from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
import uuid

import graph
import nightly_graph as ng
import test_reclaim


class GraphOwnerTests(unittest.TestCase):
    def setUp(self):
        fixture = test_reclaim.ReclaimTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        self.f = fixture
        self.graph = graph.inventory(fixture.archive, fixture.plan)
        self.databases, self.proofs, self.saved = {}, [], []
        self.corrupt, self.deny, self.closed = False, False, 0
        owner = self
        class Client:
            def connect(self, name, digest, *, readonly):
                owner.assertTrue(readonly)
                conn = sqlite3.connect(owner.databases[digest].as_uri()+'?mode=ro', uri=True)
                class DB:
                    def execute(self, *args):return conn.execute(*args)
                    def request(self, op):owner.assertEqual(op,'check')
                    def close(self):conn.close();owner.closed += 1
                return DB()
        self.recovery=SimpleNamespace(location='desktop:B:/vk-backups/fixture',provider_placement={},
                                      check=lambda:None,handle=SimpleNamespace(db=SimpleNamespace(client=Client())))
        class Hook:
            def checkpoint(self, recovery, *, paths, operation, plan_sha256, maximum_bytes, seed_checkpoint_sha256):
                points=[]; conn=sqlite3.connect(':memory:')
                conn.executescript('CREATE TABLE owner_control_manifest(sha256,row);CREATE TABLE owner_control_files(source,point);CREATE TABLE owner_control_parts(source,part,data);')
                for value in paths:
                    p=Path(value); raw=p.read_bytes()
                    point=dict(source=value,member=dict(kind='file',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                    points.append(point);conn.execute('INSERT INTO owner_control_files VALUES(?,?)',(value,ng.canonical(point).decode()))
                    for part,start in enumerate(range(0,len(raw),1024**2)):
                        conn.execute('INSERT INTO owner_control_parts VALUES(?,?,?)',(value,part,b'bad' if owner.corrupt else raw[start:start+1024**2]))
                manifest=dict(operation=operation,plan_sha256=plan_sha256,files=points);sha=hashlib.sha256(ng.canonical(manifest)).hexdigest()
                conn.execute('INSERT INTO owner_control_manifest VALUES(?,?)',(sha,ng.canonical(manifest).decode()));conn.commit()
                dest=owner.f.base/(sha+'.sqlite')
                with sqlite3.connect(dest) as other:conn.backup(other)
                conn.close();owner.databases[sha]=dest
                return dict(manifest=manifest,manifest_sha256=sha,index_reference=dict(sha256=sha))
            def verify_checkpoint(self,recovery,controls,placement,dependencies,receipt,*,resource_admission):
                owner.proofs.append(receipt)
                return dict(actual_independent_normal_restore=dict(independent_owner_controls_restore_verified=not owner.deny,
                    manifest_sha256=receipt['manifest_sha256'],files=len(receipt['manifest']['files'])))
        self.hook=Hook();self.normal=dict(B_controls={},dependencies={},host_admission={})

    @contextmanager
    def held(self):
        with ng.checkpoint_graph(self.recovery,self.graph,hook=self.hook,normal=self.normal,
              operation=uuid.uuid4().hex,plan_sha256='1'*64,seed='2'*64,
              save=lambda n,r:self.saved.append(r)) as provider:yield provider

    def test_actual_bytes_survive_absent_staging_and_reopen_exact_saved_epochs(self):
        with self.held() as provider:
            for row in self.graph['members']:(self.f.archive/row['path']).unlink()
            self.assertTrue(graph.verify_provider(self.graph,provider,lambda:None)['independent_backup_verified'])
        self.assertGreater(self.closed,0)
        with ng.reopen_graph(self.recovery,self.graph,self.saved,hook=self.hook,normal=self.normal) as provider:
            self.assertTrue(graph.verify_provider(self.graph,provider,lambda:None)['independent_backup_verified'])
        self.assertEqual(len(self.proofs),2)

    def test_corrupt_B_bytes_and_failed_independent_restore_refuse(self):
        self.corrupt=True
        with self.assertRaises(ValueError):
            with self.held() as provider:graph.verify_provider(self.graph,provider,lambda:None)
        self.assertGreater(self.closed,0)
        self.deny=True
        with self.assertRaisesRegex(ValueError,'normal B graph restore'):
            with self.held():self.fail('failed restore admitted')

    def test_missing_members_and_extra_checkpoint_members_refuse(self):
        with self.held():pass
        smaller=dict(self.graph,members=self.graph['members'][:-1])
        with self.assertRaisesRegex(ValueError,'exact archive graph'):ng.ControlGraph(self.recovery,smaller,self.saved)
        extra=dict(self.graph,members=[*self.graph['members'],dict(self.graph['members'][0],path=self.graph['members'][0]['path'].replace('12/','13/',1))])
        with self.assertRaises(ValueError):ng.ControlGraph(self.recovery,extra,self.saved)

    def test_oversized_members_cannot_silently_expand_checkpoint_budget(self):
        with self.assertRaisesRegex(ValueError,'bounded checkpoint'):
            list(ng.groups(dict(members=[dict(path='a',bytes=ng.LIMIT+1)])))


if __name__=='__main__':unittest.main()
