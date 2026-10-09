"""Real capture/provider integration with private fixture archives, not real B."""
import sqlite3
from pathlib import Path

import test_vk_candidate_direct_b as fixtures
from test_vk_restart_safeguards import fixture_readback
from vk_nightly_generation import NightlyStore, advance_verified_capture


class NightlyProvider(fixtures.ContractTests):
    def test_actual_capture_incremental_database_rows_links_and_retention(self):
        first, journal = self.capture('nightly-before')
        root = self.root / 'normal-nightly'
        root.mkdir()
        store = NightlyStore(root, self.scope, lambda: self.root, independent_readback=fixture_readback)
        store.enroll_empty()
        before = advance_verified_capture(store, self.provider, 'nightly-before', reserve_bytes=8 * 1024**2)
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO retained VALUES ('latest post-cutover work')")
        # Change a standalone note while retaining the existing hardlink pair.
        (self.inc / 'home/state/new-note').write_text('latest dirty work')
        second, journal = self.capture('nightly-after', parent=first, journal=journal)
        after = advance_verified_capture(store, self.provider, 'nightly-after', reserve_bytes=8 * 1024**2,
                                         retention_adopted=True)
        self.assertFalse((root / before['generation']).exists())
        current = store.current()
        row = current['entries']['home/state/state.sqlite']
        saved_db = root / after['generation'] / 'objects' / row['sha256']
        with sqlite3.connect(saved_db.as_uri() + '?mode=ro', uri=True) as db:
            self.assertEqual(db.execute('SELECT value FROM retained ORDER BY rowid').fetchall(),
                             [('before',), ('latest post-cutover work',)])
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(current['entries']['home/state/note-link']['kind'], 'hardlink')
        self.assertIsNone(current['parent'])
        self.assertTrue(current['capture_context']['full_current_state'])
        self.assertEqual(first['local_archive_bytes'], 0)
        self.assertEqual(second['local_snapshot_bytes'], 0)
        store.verify(current)


for name in list(dir(NightlyProvider)):
    if name.startswith('test_') and name not in NightlyProvider.__dict__:
        setattr(NightlyProvider, name, None)
