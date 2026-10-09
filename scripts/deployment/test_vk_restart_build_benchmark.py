"""Real tiny Rust release builds; this is NOT a full VK build/SLA measurement."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from vk_restart_build_benchmark import benchmark


class BuildBenchmark(unittest.TestCase):
    def setUp(self):
        if not os.path.ismount('/mnt/vk-storage'):
            raise RuntimeError('mounted SSD required')
        self.tmp = tempfile.TemporaryDirectory(prefix='restart-build-fixture-', dir='/mnt/vk-storage')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'; self.source.mkdir()
        self.warm = self.root / 'warm'; self.warm.mkdir()
        self.output = self.root / 'evidence'; self.output.mkdir()
        self.cold = self.root / 'cold-new'
        (self.source / 'Cargo.toml').write_text('[package]\nname="server"\nversion="0.1.0"\nedition="2021"\n')
        (self.source / 'src').mkdir()
        (self.source / 'src/main.rs').write_text('fn main(){println!("isolated compile fixture");}\n')
        subprocess.run(['cargo', 'generate-lockfile', '--offline'], cwd=self.source, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for args in [('init', '-q'), ('add', '.'), ('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'isolated fixture')]:
            subprocess.run(['git', *args], cwd=self.source, check=True)
        self.head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.source, text=True).strip()

    def test_actual_fixed_builds_preserve_warm_cache_and_use_fresh_cold_cache(self):
        # Prime only this disposable fixture cache; preserve the real VK cache.
        subprocess.run(['cargo', 'build', '--offline', '--locked', '--release', '--bin', 'server'],
                       cwd=self.source, env=dict(os.environ, CARGO_TARGET_DIR=str(self.warm), CARGO_INCREMENTAL='0'),
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        marker = self.warm / 'preserved-cache-evidence'; marker.write_text('retain')
        result = benchmark(self.source, self.head, self.warm, self.cold, self.output,
                           cold_space_bytes=1024**2, fixture_only=True)
        self.assertTrue(result['passed'], result)
        self.assertEqual(set(result['builds']), {'warm', 'cold'})
        self.assertTrue(result['fixture_only'])
        self.assertFalse(result['full_pipeline_measured'])
        self.assertEqual(marker.read_text(), 'retain')
        self.assertTrue((self.cold / 'release/server').is_file())

    def test_capacity_failure_creates_no_cold_cache_and_does_not_clear_warm(self):
        result = benchmark(self.source, self.head, self.warm, self.cold, self.output, cold_space_bytes=10**20)
        self.assertFalse(result['passed'])
        self.assertFalse(self.cold.exists())
        self.assertTrue(self.warm.exists())

    def test_existing_cold_cache_and_source_substitution_rejected(self):
        with self.assertRaises(ValueError):
            benchmark(self.source, 'wrong', self.warm, self.cold, self.output)
        self.cold.mkdir()
        with self.assertRaises(ValueError):
            benchmark(self.source, self.head, self.warm, self.cold, self.output)
