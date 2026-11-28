import json,os,sqlite3,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from vk_nightly_tracking import source_bindings,serve,request
from vk_nightly_inode_journal import Journal
from vk_nightly_current_map import encode_member
from vk_nightly_finalize_current import bind_contained_aliases


class ContainedAliasTests(unittest.TestCase):
    def test_real_inotify_retarget_keeps_epoch_and_tracks_new_target_writes(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm')as tmp:
            root=Path(tmp);links=root/'links';releases=root/'releases';links.mkdir();releases.mkdir()
            for n in ['a','b']:(releases/n).mkdir();(releases/n/'body').write_text(n)
            alias=links/'current';alias.symlink_to(releases/'a')
            plan=dict(sources=[str(links),str(releases),str(alias)],contained_alias_watch_roots={str(alias):dict(alias_parent=str(links),target_root=str(releases))})
            before=source_bindings(plan);stop=threading.Event();errors=[];endpoint=root/'journal.sock';status=root/'status.json'
            def work():
                try:serve(plan,root/'tracking.sqlite',endpoint,guard=lambda:None,status_path=status,stop=stop,journal_factory=Journal)
                except BaseException as e:errors.append(e)
            worker=threading.Thread(target=work);worker.start()
            try:
                deadline=time.monotonic()+10
                while not endpoint.exists():
                    if errors:raise errors[0]
                    if time.monotonic()>deadline:self.fail('fixture did not enroll')
                    time.sleep(.01)
                h=json.loads(status.read_text());new=links/'new';new.symlink_to(releases/'b');os.replace(new,alias);body=releases/'b'/'body';body.write_text('new target content')
                self.assertEqual(source_bindings(plan),before)
                while True:
                    if errors:raise errors[0]
                    r=request(endpoint,h['instance'],0)
                    if str(alias)in r['changed']and str(body)in r['changed']:break
                    if time.monotonic()>deadline:self.fail('actual alias/body events missing')
                    time.sleep(.01)
                self.assertTrue(r['ready']);self.assertEqual(r['errors'],[]);self.assertTrue(worker.is_alive())
                self.assertEqual(r['instance'],h['instance'])
            finally:stop.set();worker.join(5)
            self.assertEqual(errors,[]);self.assertFalse(worker.is_alive())

    def test_terminal_scope_expansion_preserves_alias_parent_and_target(self):
        import copy,stat
        from vk_nightly_current_map import terminal_epoch_successor
        parent=dict(identity=[1,1,stat.S_IFDIR],target_identity=[1,1,stat.S_IFDIR],resolved='/links',literal=None)
        target=dict(identity=[2,2,stat.S_IFDIR],target_identity=[2,2,stat.S_IFDIR],resolved='/release',literal=None)
        link=dict(identity=[1,3,stat.S_IFLNK],target_identity=[2,4,stat.S_IFDIR],resolved='/release/a',literal='/release/a')
        old=dict(instance='old',start_sequence=0,plan_sha256='a'*64,scope_sha256='b'*64,required_root_bindings={'/links':parent,'/links/current':link})
        after=dict(target,format='vk-nightly-contained-alias-watch-root-v1',alias_parent='/links',target_root='/release')
        new=dict(old,instance='new',plan_sha256='c'*64,scope_sha256='d'*64,required_root_bindings={'/links':parent,'/links/current':after,'/release':target})
        proof=dict(format='vk-nightly-closed-source-additive-gap-v3',old_instance='old',new_instance='new',
            **{k:old[k]for k in ('plan_sha256','scope_sha256','required_root_bindings')},new_plan_sha256=new['plan_sha256'],new_scope_sha256=new['scope_sha256'],new_required_root_bindings=new['required_root_bindings'],added_roots=['/release'],changed_alias_roots=['/links/current'],old_owner_verified_terminal=True,old_MainPID=0,old_committed_sequence=1,old_B_delivered_sequence=0,old_gap_continuity_proven=False,original_epoch_repaired=False,current_baseline_accepted=False,complete_later_metadata_required=True,reason='full target-root expansion retains all logical roots and old gap',old_source_database_sha256='e'*64)
        self.assertEqual(json.loads(terminal_epoch_successor(old,new,proof)),proof)
        for field,value in [('alias_parent','/outside'),('target_root','/outside'),('literal','/release/a')]:
            bad=copy.deepcopy(new);bad['required_root_bindings']['/links/current'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):terminal_epoch_successor(old,bad,dict(proof,new_required_root_bindings=bad['required_root_bindings']))

    def test_contained_alias_successor_retains_old_target_when_adding_new_release(self):
        import copy,stat
        from vk_nightly_current_map import terminal_epoch_successor
        def directory(name,inode):
            return dict(identity=[1,inode,stat.S_IFDIR],target_identity=[1,inode,stat.S_IFDIR],resolved=name,literal=None)
        parent=directory('/links',1);a=directory('/release-a',2);b=directory('/release-b',3)
        def alias(target,row):
            return dict(row,format='vk-nightly-contained-alias-watch-root-v1',alias_parent='/links',target_root=target)
        old=dict(instance='old',start_sequence=0,plan_sha256='a'*64,scope_sha256='b'*64,
                 required_root_bindings={'/links':parent,'/release-a':a,'/links/current':alias('/release-a',a)})
        new=dict(old,instance='new',plan_sha256='c'*64,scope_sha256='d'*64,
                 required_root_bindings=dict(old['required_root_bindings'],**{'/release-b':b,'/links/current':alias('/release-b',b)}))
        def proof(current):
            return dict(format='vk-nightly-closed-source-additive-gap-v3',old_instance='old',new_instance='new',
                **{k:old[k] for k in ('plan_sha256','scope_sha256','required_root_bindings')},
                new_plan_sha256=current['plan_sha256'],new_scope_sha256=current['scope_sha256'],
                new_required_root_bindings=current['required_root_bindings'],added_roots=['/release-b'],
                changed_alias_roots=sorted(k for k in old['required_root_bindings'] if old['required_root_bindings'][k]!=current['required_root_bindings'].get(k)),
                old_owner_verified_terminal=True,old_MainPID=0,old_committed_sequence=10,old_B_delivered_sequence=9,
                old_gap_continuity_proven=False,original_epoch_repaired=False,current_baseline_accepted=False,
                complete_later_metadata_required=True,reason='explicit new release and retained old coverage',old_source_database_sha256='e'*64)
        self.assertEqual(json.loads(terminal_epoch_successor(old,new,proof(new))),proof(new))
        for target in ['/release-a','/links']:
            bad=copy.deepcopy(new);bad['required_root_bindings'][target]['identity'][1]+=10
            with self.subTest(target=target),self.assertRaises(ValueError):terminal_epoch_successor(old,bad,proof(bad))
        bad=copy.deepcopy(new);del bad['required_root_bindings']['/release-a']
        with self.assertRaises(ValueError):terminal_epoch_successor(old,bad,proof(bad))
        bad=copy.deepcopy(new);bad['required_root_bindings']['/links/current']['alias_parent']='/release-a'
        with self.assertRaises(ValueError):terminal_epoch_successor(old,bad,proof(bad))

    def test_uncovered_alias_target_or_missing_parent_fails_closed(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm')as tmp:
            r=Path(tmp);(r/'links').mkdir();(r/'release').mkdir();(r/'outside').mkdir();alias=r/'links/current';alias.symlink_to(r/'outside')
            plan=dict(sources=[str(r/'links'),str(r/'release'),str(alias)],contained_alias_watch_roots={str(alias):dict(alias_parent=str(r/'links'),target_root=str(r/'release'))})
            with self.assertRaises(ValueError):source_bindings(plan)
            alias.unlink();alias.symlink_to(r/'release');plan['sources'].remove(str(r/'links'))
            with self.assertRaises(ValueError):source_bindings(plan)

    def fixture(self,folder,*,target='/release/b',complete=1,coverage=True):
        p=Path(folder)/'map.sqlite';alias='/links/current';rule=dict(alias_parent='/links',target_root='/release')
        roots={alias:dict(rule,format='vk-nightly-contained-alias-watch-root-v1'if coverage else 'unsupported'),'/links':{},'/release':{}}
        binding=dict(plan_sha256='a'*64,scope_sha256='b'*64,required_root_bindings=roots)
        with sqlite3.connect(p)as db:
            db.execute('create table namespace_reconciliation(id integer,binding text,complete integer,suffix_complete integer)');db.execute('insert into namespace_reconciliation values(1,?,?,1)',(json.dumps(binding),complete))
            db.execute('create table members(name text,state text,row blob)');db.execute('insert into members values(?,?,?)',(alias[1:],'symlink',encode_member(dict(member=dict(kind='symlink',target=target)))))
            db.execute('insert into members values(?,?,?)',('release/b','directory',b''))
        contract=dict(plan_sha256='a'*64,scope_sha256='b'*64,sources=list(roots),contained_root_aliases={alias:rule},root_aliases={alias:dict(literal='/release/a',resolved='/release/a')})
        return SimpleNamespace(connect=lambda *args,**kwargs:sqlite3.connect(p)),contract

    def test_final_alias_comes_from_complete_journal_backed_map(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm')as tmp:
            client,contract=self.fixture(tmp);bind_contained_aliases(client,dict(index_name='map',checkpoint_sha256='a'*64),contract,guard=lambda:None)
            self.assertEqual(contract['root_aliases']['/links/current'],dict(literal='/release/b',resolved='/release/b'))

    def test_incomplete_or_uncovered_or_outside_map_cannot_rebind_contract(self):
        for change in [dict(complete=0),dict(coverage=False),dict(target='/outside/body')]:
            with self.subTest(change=change),tempfile.TemporaryDirectory(dir='/dev/shm')as tmp:
                client,contract=self.fixture(tmp,**change)
                with self.assertRaises(ValueError):bind_contained_aliases(client,dict(index_name='map',checkpoint_sha256='a'*64),contract,guard=lambda:None)
                self.assertEqual(contract['root_aliases']['/links/current']['resolved'],'/release/a')


if __name__=='__main__':unittest.main()
