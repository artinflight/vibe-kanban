import tempfile
from pathlib import Path
import unittest
from pair_frontend_assets import compose

class FrontendPairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for name in ['new','old']:
            p=self.root/name;(p/'assets').mkdir(parents=True)
            (p/'index.html').write_text(name);(p/'assets'/('index-'+name+'.js')).write_text(name)
    def tearDown(self):self.temp.cleanup()
    def test_both_directions_keep_old_and_new_chunks_without_changing_entrypoint(self):
        result=compose(self.root/'new',self.root/'old',self.root/'paired')
        self.assertEqual(result['retained_asset_count'],2)
        for variant,label in [('candidate','new'),('fallback','old')]:
            p=self.root/'paired'/variant;self.assertEqual((p/'index.html').read_text(),label)
            self.assertEqual(sorted(f.name for f in (p/'assets').iterdir()),['index-new.js','index-old.js'])
        self.assertFalse((self.root/'old/assets/index-new.js').exists())
    def test_conflicting_hashed_asset_refuses_before_output(self):
        (self.root/'old/assets/index-new.js').write_text('conflict')
        with self.assertRaisesRegex(ValueError,'Conflicting'):compose(self.root/'new',self.root/'old',self.root/'paired')
        self.assertFalse((self.root/'paired').exists())
if __name__=='__main__':unittest.main()
