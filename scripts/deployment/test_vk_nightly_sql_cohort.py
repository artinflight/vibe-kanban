import copy
import unittest

from vk_nightly_sql_cohort import inherit


class SQLReuseTests(unittest.TestCase):
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
