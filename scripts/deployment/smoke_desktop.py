"""Opt-in real Desktop smoke test using only tiny, newly owned fixture data."""
import argparse
import datetime
import json
from pathlib import Path
import sqlite3
import tempfile

from vk_archive_store import Archive, reference
from vk_change_journal import Journal
from vk_desktop_transport import DesktopTransport
from vk_prep_common import digest, save, storage
from vk_rolling_backup import capture, restore_chain, resume_delivery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--run-desktop-smoke', action='store_true', required=True)
    args = parser.parse_args()
    base = storage(args.root)
    base.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='desktop-smoke-', dir=base))
    source = root / 'fixture';source.mkdir()
    dbpath = source / 'fixture.sqlite'
    with sqlite3.connect(dbpath) as db:
        db.execute('CREATE TABLE fixture (message TEXT)')
        db.execute("INSERT INTO fixture VALUES ('before')")
    (source / 'attachment.bin').write_bytes(b'tiny synthetic attachment, not VK data')
    note = source / 'uncommitted.txt';note.write_text('synthetic uncommitted work')
    plan = {'sources': [str(source)], 'sqlite_snapshots': [str(dbpath)],
            'excluded_rebuildable_directories': []}
    journal = Journal(plan);journal.tree(source);journal.ready = True
    transport = DesktopTransport(root / 'transport')
    remote = 'B:/vk-backups/vk-desktop-backup-20261007/' + root.name
    mirror = lambda p: transport.mirror(p, remote)
    removed = []
    try:
        first = capture(plan, root / 'backups', journal.report, mirror, publish=mirror)
        for result in (first,):
            path = Path(result['folder']) / result['archive']
            Archive(reference(result), desktop_only=True).verify()
            path.with_name(path.name + '.MOVED-TO-DESKTOP.txt').write_text(
                remote + '/' + path.name + '\nSHA256: ' + digest(path) + '\nSynthetic smoke fixture only.\n')
            path.unlink();removed.append(str(path))
        with sqlite3.connect(dbpath) as db:db.execute("UPDATE fixture SET message='after'")
        note.write_text('latest synthetic uncommitted work')
        before = {p.name: digest(p) for p in source.iterdir() if p.is_file()}
        try:
            capture(plan, root / 'backups', journal.report, mirror, first,
                    lambda _: (_ for _ in ()).throw(RuntimeError('fixture publish interruption')))
        except RuntimeError as error:
            assert str(error) == 'fixture publish interruption'
        pending = list((root / 'backups').glob('delta-/*/pending-delivery.json'))
        assert len(pending) == 1
        second = resume_delivery(plan, root / 'backups', pending[0].parent, journal.report,
                                 mirror, mirror, first)
        path = Path(second['folder']) / second['archive']
        Archive(reference(second), desktop_only=True).verify()
        path.with_name(path.name + '.MOVED-TO-DESKTOP.txt').write_text(
            remote + '/' + path.name + '\nSHA256: ' + digest(path) + '\nSynthetic smoke fixture only.\n')
        path.unlink();removed.append(str(path))
        restored = restore_chain(second, root / 'backups/restore', desktop_only=True)
        files = Path(restored['destination']) / 'files' / str(source).lstrip('/')
        with sqlite3.connect(files / dbpath.name) as db:
            assert db.execute('SELECT message FROM fixture').fetchone()[0] == 'after'
        assert (files / note.name).read_text() == note.read_text()
        assert (files / 'attachment.bin').read_bytes() == (source / 'attachment.bin').read_bytes()
        assert before == {p.name: digest(p) for p in source.iterdir() if p.is_file()}
        assert all(not Path(p).exists() for p in removed)
        result = {'passed': True, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'root': str(root), 'desktop_directory': remote,
                  'local_fixture_archives_removed': removed, 'restore': restored,
                  'remote_parent_capture_passed': True, 'interrupted_delivery_resume_passed': True, 'production_data_touched': False,
                  'retained_remote_archive_bytes': first['receipt']['bytes'] + second['receipt']['bytes']}
        save(root / 'smoke-result.json', result)
        print(json.dumps(result), flush=True)
    finally:
        journal.close()


if __name__ == '__main__':main()

