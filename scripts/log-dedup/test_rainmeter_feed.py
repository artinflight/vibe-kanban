import json
from pathlib import Path
import tempfile
import unittest
import rainmeter_feed as hud

class FeedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.config={'operation_root':str(self.root),'operation':'owned'}
        self.source=dict(state='running',phase='batch_packed',progress_at=90,completed_files=3,resolved_files=4,total_files=10,completed_batches=1,total_batches=3,completed_raw_bytes=1000)
        self.result=dict(at=100,source=self.source,source_error=None)
        self.committed=dict(self.source,operation='owned',canary_live_log_allocated_recovery=5,batches=[{'allocated_release':50}])
        self.save()
    def save(self):(self.root/'COMMITTED.private.json').write_text(json.dumps(self.committed))
    def test_only_committed_recovery_is_reported_without_private_fields(self):
        self.result['secret']='do not publish';self.source['path']='/private/history'
        value=hud.payload(self.config,self.result);self.assertEqual(value['reclaimed_bytes'],55)
        text=hud.embed('<html></html>',self.config,self.result)
        self.assertNotIn('/private',text);self.assertNotIn('secret',text);self.assertIn('resolved_files=4',text)
    def test_commit_race_omits_savings_and_preserves_observed_counts(self):
        self.committed['completed_files']=5;self.save()
        value=hud.payload(self.config,self.result);self.assertEqual(value['reclaimed_bytes'],-1);self.assertEqual(value['completed_files'],3)
    def test_unavailable_corrupt_or_inconsistent_data_never_looks_live(self):
        self.source['resolved_files']=100
        self.assertIn('state=unavailable',hud.embed('</html>',self.config,self.result))
        self.source['resolved_files']=4;self.result['source_error']='private exception'
        self.assertNotIn('private exception',hud.embed('</html>',self.config,self.result))
        self.assertIn('state=unavailable',hud.embed('</html>',self.config,self.result))
    def test_real_phase_names_with_uppercase_tokens_are_normalized(self):
        self.source['phase']='actual_production_reader_full_EOF_verified'
        self.assertEqual(hud.payload(self.config,self.result)['phase'],'actual_production_reader_full_eof_verified')
    def test_payload_cannot_inject_html_or_rainmeter_commands(self):
        self.source['phase']='[!Execute bad]--><script>'
        value=hud.payload(self.config,self.result);self.assertEqual(value['phase'],'unavailable')

if __name__=='__main__':unittest.main()
