import copy
import unittest

from vk_nightly_sql_cohort import inherit,statistics


class SQLReuseTests(unittest.TestCase):
    def test_inherited_transfer_counts_are_not_recharged_as_incremental_demand(self):
        old=dict(new_B_encoded_payload_bytes=1000,source_API_image_bytes=10000)
        new=dict(new_B_encoded_payload_bytes=17,source_API_image_bytes=500)
        state=dict(completed={'/old':old,'/new':new},inherited_SQL_points=[dict(source_names=['/old'])])
        result=statistics(state)
        self.assertEqual(result['new_B_SQL_payload_encoded_bytes'],17)
        self.assertEqual(result['source_API_image_bytes'],500)
        self.assertEqual(result['accepted_SQL_payload_encoded_bytes_including_inherited_points'],1017)
        self.assertEqual(result['accepted_SQL_points_inherited_without_recopy'],1)
        self.assertEqual(result['new_images_in_current_cohort'],1)
        self.assertEqual(statistics(dict(completed=state['completed']))['new_B_SQL_payload_encoded_bytes'],1017)

    def test_expanded_cohort_preserves_exact_prior_epochs_without_source_or_copy(self):
        binding=dict(sources=['/old'],B_root='B:/vk-backups/same/objects-v1',catalog_sha256='a'*64)
        record=dict(source='/old',B_acceptance_object={'sha256':'b'*64},original_source_API_point_at=123)
        previous=dict(binding=binding,completed={'/old':record},partial={},deferred={})
        target=dict(binding=dict(binding,sources=['/old','/new']),completed={},partial={},deferred={})
        old=copy.deepcopy(previous);new=copy.deepcopy(target);verified=[]
        result=inherit(target,previous,reference=dict(index_name='old-cohort',checkpoint_sha256='c'*64),verify=verified.append)
        self.assertEqual(verified,[record]);self.assertEqual(result['completed']['/old'],record)
        self.assertNotIn('/new',result['completed']);self.assertEqual(previous,old);self.assertEqual(target,new)
        def denied(_):raise PermissionError('old proof unreadable')
        with self.assertRaises(PermissionError):inherit(target,previous,reference=dict(index_name='old-cohort',checkpoint_sha256='c'*64),verify=denied)
        self.assertEqual(target,new)
        previous['binding']=dict(binding,B_root='B:/vk-backups/different/objects-v1')
        with self.assertRaisesRegex(ValueError,'same authenticated'):
            inherit(target,previous,reference=dict(index_name='old-cohort',checkpoint_sha256='c'*64),verify=verified.append)
