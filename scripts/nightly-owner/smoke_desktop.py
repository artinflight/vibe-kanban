"""Opt-in small real B: test; retains every fixture, no live state changes.

--archive-only does NOT claim full restore verification. Default mode still
requires the unchanged production restore capacity/integrity checks.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import resource
import sqlite3
import tempfile
import threading

from vk_archive_store import Archive, reference
from vk_change_journal import Journal
from vk_desktop_transport import DesktopTransport
from vk_prep_common import digest, save, storage
from vk_rolling_backup import capture, restore_chain


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--run-desktop-smoke', action='store_true', required=True)
    parser.add_argument('--archive-only', action='store_true')
    args = parser.parse_args()
    base = storage(args.root);base.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='desktop-smoke-', dir=base))
    source = root/'fixture';source.mkdir()
    dbpath = source/'fixture.sqlite'
    with sqlite3.connect(dbpath) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE fixture (message TEXT)')
        db.execute("INSERT INTO fixture VALUES ('before')")
    db.close()
    (source/'attachment.bin').write_bytes(os.urandom(2*1024**2))
    note = source/'uncommitted.txt';note.write_text('synthetic uncommitted work')
    plan = {'sources':[str(source)], 'sqlite_snapshots':[str(dbpath)], 'excluded_rebuildable_directories':[]}
    journal = Journal(plan);journal.tree(source);journal.ready = True
    transport = DesktopTransport(root/'transport')
    remote = 'B:/vk-backups/vk-direct-stream-20261008/' + root.name
    mirror = lambda p: transport.mirror(p, remote)
    stop = threading.Event()
    samples = {'peak_local_backup_allocated_bytes':0, 'peak_local_backup_logical_bytes':0,
               'observed_local_archive_bytes':0, 'observed_local_snapshot_bytes':0, 'samples':0}

    def sample():
        logical = allocated = archive_bytes = snapshots = 0
        for path in (root/'backups').rglob('*'):
            try:
                if not path.is_file():continue
                st = path.stat()
                logical += st.st_size;allocated += st.st_blocks*512
                if path.name.endswith('.tar.zst'):archive_bytes += st.st_size
                if path.suffix == '.sqlite':snapshots += st.st_size
            except FileNotFoundError:continue
        samples['peak_local_backup_allocated_bytes'] = max(samples['peak_local_backup_allocated_bytes'], allocated)
        samples['peak_local_backup_logical_bytes'] = max(samples['peak_local_backup_logical_bytes'], logical)
        samples['observed_local_archive_bytes'] = max(samples['observed_local_archive_bytes'], archive_bytes)
        samples['observed_local_snapshot_bytes'] = max(samples['observed_local_snapshot_bytes'], snapshots)
        samples['samples'] += 1

    def monitor():
        while not stop.wait(0.025):sample()

    watcher = threading.Thread(target=monitor, daemon=True);watcher.start()
    captures = []
    try:
        print('Starting bounded synthetic stream to ' + remote, flush=True)
        first = capture(plan, root/'backups', journal.report, mirror, publish=mirror)
        captures.append(first)
        print('Checkpoint uploaded, hashed and archive/snapshot readback verified', flush=True)
        with sqlite3.connect(dbpath) as db:db.execute("UPDATE fixture SET message='after'")
        db.close()
        note.write_text('latest synthetic uncommitted work')
        # SQLite readers may create/change WAL bookkeeping, never treat SHM
        # byte identity as user content. Check DB logical state separately.
        before = {p.name:digest(p) for p in (source/'attachment.bin', note)}
        head = (root/'backups/latest-result.json').read_bytes()
        try:
            capture(plan, root/'backups', journal.report, mirror, first,
                    lambda _: (_ for _ in ()).throw(RuntimeError('fixture publish interruption')))
        except RuntimeError as error:
            assert str(error) == 'fixture publish interruption'
        else:raise AssertionError('Injected interruption did not fail')
        assert (root/'backups/latest-result.json').read_bytes() == head
        Archive(reference(first)).verify()
        second = capture(plan, root/'backups', journal.report, mirror, first, mirror)
        captures.append(second)
        print('Failed metadata delivery retained prior head; fresh delta accepted', flush=True)
        restored = None
        if not args.archive_only:
            restored = restore_chain(second, root/'backups/restore', desktop_only=True)
            files = Path(restored['destination'])/'files'/str(source).lstrip('/')
            with sqlite3.connect(files/dbpath.name) as db:
                assert db.execute('SELECT message FROM fixture').fetchone()[0] == 'after'
            assert (files/note.name).read_text() == note.read_text()
            assert digest(files/'attachment.bin') == digest(source/'attachment.bin')
        assert before == {p.name:digest(p) for p in (source/'attachment.bin', note)}
        with sqlite3.connect(dbpath) as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert db.execute('SELECT message FROM fixture').fetchall() == [('after',)]
        db.close()
        stop.set();watcher.join();sample()
        if args.archive_only:
            assert samples['observed_local_archive_bytes'] == samples['observed_local_snapshot_bytes'] == 0
        receipts = [json.loads(p.read_text())['receipt'] for p in (root/'backups').rglob('*.tar.zst.result.json')]
        result = {'passed':True, 'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'root':str(root), 'desktop_directory':remote, 'archive_only':args.archive_only,
                  'full_restore_verified':restored is not None, 'restore':restored,
                  'remote_parent_capture_passed':True, 'interrupted_publish_fresh_capture_passed':True,
                  'production_data_touched':False, 'cleanup_performed':False,
                  'retained_remote_archive_bytes':sum(r['bytes'] for r in receipts),
                  'accepted_captures':[reference(r) for r in captures],
                  'all_uploaded_archive_receipts':receipts, 'disk_samples':samples,
                  'sampling_interval_seconds':0.025,
                  'python_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                  'local_fixture_source_bytes':sum(p.stat().st_size for p in source.iterdir() if p.is_file())}
        save(root/'smoke-result.json', result)
        print(json.dumps(result, indent=2), flush=True)
    finally:
        stop.set();watcher.join();journal.close()


if __name__ == '__main__':main()
