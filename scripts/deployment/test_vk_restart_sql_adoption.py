"""Bound receipt intake; these synthetic receipts are never live B proof."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from vk_restart_sql_adoption import load_checkpoint, open_accepted_SQL_map
from vk_restart_sql_sidecar_reuse import canonical


class SQLCheckpointIntake(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='vk-SQL-intake-',dir='/dev/shm');self.root=Path(self.temp.name)
        self.path=self.root/'result.json'
        candidate=dict(sealed_map=dict(sha256='a'*64,bytes=4096),
            descriptor=dict(indexes=[dict(sha256='a'*64,bytes=4096)],journal=dict(instance='b'*32)),
            consumer_contract=dict(current_SQL_request=dict(binding=dict(source_instance='b'*32))),content_proof=dict(fixture=True))
        packet={}
        for name in ['descriptor','consumer_contract','content_proof']:
            sha=hashlib.sha256(canonical(candidate[name])).hexdigest();candidate[name+'_sha256']=sha
            packet[name]=candidate[name];packet[name+'_sha256']=sha
        restore=dict(normal_leased_consumer_entrypoint_verified=True,independent_composed_restore_verified=True,
            actual_existing_B_backed_consumer_route_verified=True,consumer_packet_sha256=hashlib.sha256(canonical(packet)).hexdigest(),
            **{name+'_sha256':candidate[name+'_sha256'] for name in ['descriptor','consumer_contract','content_proof']})
        self.value=dict(recovery_checkpoint_verified=True,accepted_current_pointer_modified=False,
            live_later_changes_not_claimed_backed_up=True,all_old_recovery_retained=True,candidate=candidate,consumer_packet=packet,normal_restore=restore)

    def tearDown(self):self.temp.cleanup()

    def reference(self):
        raw=canonical(self.value);self.path.write_bytes(raw)
        return dict(path=str(self.path),sha256=hashlib.sha256(raw).hexdigest())

    def test_complete_bound_receipt_can_be_loaded_without_native_actions(self):
        self.assertEqual(load_checkpoint(self.reference()),self.value)

    def test_missing_independent_restore_cannot_be_replaced_with_component_success(self):
        self.value['normal_restore']['independent_composed_restore_verified']=False
        with self.assertRaises(ValueError):load_checkpoint(self.reference())

    def test_unrelated_packet_cannot_supply_restore_acceptance(self):
        self.value['normal_restore']['consumer_packet_sha256']='f'*64
        with self.assertRaises(ValueError):load_checkpoint(self.reference())

    def test_changed_descriptor_or_content_proof_cannot_be_relabelled(self):
        self.value['candidate']['content_proof']['new-point']='unverified'
        with self.assertRaises(ValueError):load_checkpoint(self.reference())

    def test_different_immutable_map_cannot_be_adopted(self):
        self.value['candidate']['sealed_map']['sha256']='e'*64
        with self.assertRaises(ValueError):load_checkpoint(self.reference())

    def test_receipt_rewrite_and_alias_refuse(self):
        ref=self.reference();self.path.write_text('{}')
        with self.assertRaises(ValueError):load_checkpoint(ref)
        ref=self.reference();alias=self.root/'alias.json';alias.symlink_to(self.path)
        with self.assertRaises(ValueError):load_checkpoint(dict(ref,path=str(alias)))


@unittest.skipUnless(importlib.util.find_spec('vk_nightly_b_controls'), 'Native control source required; run with the sealed source on PYTHONPATH')
class NativeSQLMapHandle(unittest.TestCase):
    def test_accepted_map_handle_passes_real_native_validator_and_is_readonly(self):
        from vk_nightly_b_controls import name
        class Client:
            def connect(self, key, digest, **options):
                return name(key), digest, options
        value=open_accepted_SQL_map(Client(), {'sha256':'a'*64})
        self.assertEqual(value,('sql-reuse-accepted-catchup','a'*64,{'readonly':True}))
        with self.assertRaises(ValueError):name('SQL-reuse-accepted-catchup')


if __name__=='__main__':unittest.main()
