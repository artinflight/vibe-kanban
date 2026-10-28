"""Tiny metadata and physical lean restore fixtures; no live backup access."""
import hashlib
import json
from pathlib import Path
import tempfile
import sqlite3
import unittest

from vk_backup_content_audit import category, summarize, audit
from vk_backup_lean_contract import project


def file(data):
    return {'kind':'file','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
            'mode':0o600,'uid':1000,'gid':1000,'mtime_ns':123,'xattrs':{}}


def directory():return {'kind':'directory','mode':0o700,'uid':1000,'gid':1000,'mtime_ns':123,'xattrs':{}}


class MetadataAudit(unittest.TestCase):
    def row(self,path,data,link=''):
        return path,json.dumps({'kind':'f','size':len(data)}),hashlib.sha256(data).hexdigest(),link

    def test_logical_archive_hardlink_and_content_dedup_are_distinct(self):
        rows=[self.row('/repo/node_modules/lib/a',b'hello'),self.row('/repo/source/vendor-copy',b'hello','/repo/node_modules/lib/a'),self.row('/repo/source/another-copy',b'hello')]
        result=summarize(iter(rows),{'sources':['/repo']})
        self.assertEqual(sum(v.get('logical_path_bytes',0) for v in result['categories'].values()),15)
        self.assertEqual(sum(v.get('tar_regular_payload_bytes',0) for v in result['categories'].values()),10)
        self.assertEqual(result['hash_unique_bytes'],5)
        self.assertEqual(result['cross_category_shared_unique_bytes'],5)
        self.assertIsNone(result['compressed_category_bytes'])

    def test_counterfactual_plan_exclusions_do_not_change_actual_archive_totals(self):
        result=summarize(iter([self.row('/repo/node_modules/lib/a',b'hello'),self.row('/repo/source/a',b'work')]),
            {'sources':['/repo'],'excluded_rebuildable_directories':['/repo/node_modules']})
        self.assertEqual(result['categories']['node_modules']['tar_regular_payload_bytes'],5)
        self.assertNotIn('nightly_plan_file_paths',result['categories']['node_modules'])
        self.assertEqual(result['nightly_plan_hash_unique_bytes'],4)

    def test_existing_sqlite_index_is_read_only_and_never_opens_source_content(self):
        with tempfile.TemporaryDirectory(prefix='vk-index-audit-') as raw:
            index=Path(raw)/'verified.sqlite'
            with sqlite3.connect(index) as db:
                db.execute('CREATE TABLE baseline(path TEXT,meta TEXT,sha TEXT,hardlink TEXT)')
                db.execute('CREATE TABLE current(path TEXT,meta TEXT,sha TEXT,generation TEXT,db INTEGER)')
                row=self.row('/absent-source/must-not-open',b'data')
                db.execute('INSERT INTO baseline VALUES(?,?,?,?)',row)
                db.execute('INSERT INTO current VALUES(?,?,?,?,?)',(*row[:3],json.dumps([1,2,4]),0))
            before=index.stat()
            value=audit(index,{'sources':['/absent-source']})
            self.assertEqual(value['baseline']['hash_unique_bytes'],4)
            self.assertEqual(value['current']['source_inode_unique_bytes'],4)
            self.assertFalse(value['archive_payload_read']);self.assertFalse(value['source_content_read'])
            self.assertEqual(index.stat().st_mtime_ns,before.st_mtime_ns)

    def test_categories_are_hints_not_disposability(self):
        self.assertEqual(category('/repo/target/unpublished-source.py'),'build_output_candidates')
        self.assertEqual(category('/repo/node_modules/local-package/dirty.ts'),'node_modules')
        self.assertEqual(category('/home/.codex/sessions/history.jsonl'),'native_histories_logs')
        self.assertEqual(category('/home/.codex/state_5.sqlite',True),'databases')
        self.assertEqual(category('/repo/.git/objects/pack/only-local.pack'),'git_objects')

    def test_unknown_hashes_and_inode_dedup_are_honestly_separate(self):
        gen=json.dumps([1,2,4,0,0,0,0,0,2])
        rows=[('/repo/a',json.dumps({'kind':'f','size':4}),None,(gen,0)),('/repo/b',json.dumps({'kind':'f','size':4}),None,(gen,0))]
        value=summarize(iter(rows),{'sources':['/repo']},current=True)
        self.assertFalse(value['hash_dedup_complete']);self.assertEqual(value['bytes_without_content_hash'],8)
        self.assertEqual(value['source_inode_unique_bytes'],4)

    def test_explicit_cardinality_and_invalid_size_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'cardinality'):
            summarize(iter([self.row('/repo/a',b'a'),self.row('/repo/b',b'b')]),{'sources':['/repo']},max_unique=1)
        with self.assertRaisesRegex(ValueError,'logical size'):
            summarize(iter([('/repo/a',json.dumps({'kind':'f','size':-1}),None,'')]),{'sources':['/repo']})


class LeanRestore(unittest.TestCase):
    def setUp(self):
        self.data={'src/dirty.py':b'uncommitted source','notes/untracked.txt':b'irreplaceable note',
            'package-lock.json':b'pinned-dependency-v1','fixture-registry/lib.js':b'known pinned module',
            'node_modules/lib/index.js':b'known pinned module','target/generated.js':b'generated:uncommitted source',
            'runtime/server':b'current recovery artifact','sessions/turn.jsonl':b'original native history',
            'attachments/user.png':b'original attachment','.git/objects/pack/unpublished.pack':b'unpublished Git object'}
        self.entries={key:file(data) for key,data in self.data.items()}
        self.entries.update({key:directory() for key in ['src','notes','fixture-registry','node_modules','node_modules/lib','target','runtime','sessions','attachments','.git','.git/objects','.git/objects/pack']})
        self.protected={'src/dirty.py','notes/untracked.txt','runtime/server','sessions/turn.jsonl','attachments/user.png','.git/objects/pack/unpublished.pack'}
        self.recipe={'package-lock.json':self.entries['package-lock.json']['sha256'],'fixture-registry/lib.js':self.entries['fixture-registry/lib.js']['sha256']}

    def test_lean_projection_physically_restores_work_and_rebuilds_exact_fixture_dependency(self):
        generated_recipe={'src/dirty.py':self.entries['src/dirty.py']['sha256'],'package-lock.json':self.entries['package-lock.json']['sha256']}
        value=project(self.entries,{'node_modules':self.recipe,'target':generated_recipe},protected=self.protected)
        objects={hashlib.sha256(data).hexdigest():data for data in self.data.values()}
        with tempfile.TemporaryDirectory(prefix='vk-lean-restore-') as raw:
            root=Path(raw)
            for key,row in value['entries'].items():
                p=root/key
                if row['kind']=='directory':p.mkdir(parents=True,exist_ok=True)
                elif row['kind']=='file':p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(objects[row['sha256']])
            # This actual fixture has an offline, retained pinned dependency
            # source. Real package trees require their own verified rebuild route.
            self.assertEqual((root/'package-lock.json').read_bytes(),b'pinned-dependency-v1')
            rebuilt=root/'node_modules/lib/index.js';rebuilt.parent.mkdir(parents=True);rebuilt.write_bytes((root/'fixture-registry/lib.js').read_bytes())
            self.assertEqual(hashlib.sha256(rebuilt.read_bytes()).hexdigest(),self.entries['node_modules/lib/index.js']['sha256'])
            generated=root/'target/generated.js';generated.parent.mkdir();generated.write_bytes(b'generated:'+(root/'src/dirty.py').read_bytes())
            self.assertEqual(hashlib.sha256(generated.read_bytes()).hexdigest(),self.entries['target/generated.js']['sha256'])
            for key in self.protected:self.assertEqual((root/key).read_bytes(),self.data[key])
        self.assertFalse(value['exclusion_authorized'])
        self.assertEqual(value['unique_content_bytes_omitted'],len(self.data['target/generated.js']))  # Dependency bytes remain in the offline source.

    def test_embedded_unpublished_source_prevents_whole_dependency_or_build_exclusion(self):
        for root in ['node_modules','target']:
            entries={**self.entries,root+'/dirty.py':file(b'local unpublished fix')}
            with self.assertRaisesRegex(ValueError,'protected'):
                project(entries,{root:self.recipe},protected=self.protected|{root+'/dirty.py'})

    def test_excluded_canonical_hardlink_is_materialized_in_independent_kept_manifest(self):
        row={**self.entries['node_modules/lib/index.js'],'kind':'hardlink','target':'node_modules/lib/index.js'}
        value=project({**self.entries,'src/kept-alias.js':row},{'node_modules':self.recipe},protected=self.protected|{'src/kept-alias.js'})
        self.assertEqual(value['entries']['src/kept-alias.js']['kind'],'file')
        self.assertEqual(value['entries']['src/kept-alias.js']['sha256'],row['sha256'])

    def test_active_runtime_git_and_invalid_rebuild_inputs_cannot_be_excluded(self):
        for proposals in [{'runtime':self.recipe},{'.git/objects':self.recipe},{'node_modules':{}},
                          {'node_modules':{'package-lock.json':'0'*64}},
                          {'node_modules':{'node_modules/lib/index.js':self.entries['node_modules/lib/index.js']['sha256']}}]:
            with self.subTest(proposals=proposals),self.assertRaises(ValueError):project(self.entries,proposals,protected=self.protected)

    def test_symlink_traversal_and_missing_protected_inventory_fail(self):
        for proposals in [{'../node_modules':self.recipe},{'node_modules/lib/index.js':self.recipe}]:
            with self.assertRaises(ValueError):project(self.entries,proposals,protected=self.protected)
        with self.assertRaises(ValueError):project(self.entries,{},protected={'missing-work'})


if __name__=='__main__':unittest.main()
