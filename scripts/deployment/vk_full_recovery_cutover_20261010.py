"""One scoped current-data handoff using the established ownership workflow."""
import ctypes
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import sqlite3
import ssl
import subprocess
import sys
import time
import urllib.request

sys.dont_write_bytecode = True
ROOT = Path('/mnt/vk-storage/vk-next-restart-20261010/full-recovery-readiness')
ATTEMPT = ROOT / 'attempt-measured-catchup-20261010T1740'
ATTEMPT.mkdir(mode=0o700, exist_ok=True)
DB = Path('/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban/db.v2.sqlite')
LIVE_FRONTEND = Path('/mnt/vk-storage/vk-safe-release-20261009/frontend66-over-c3/packages/local-web/dist-v6')
OLD = 'vibe-kanban-current-state-production-20261009.service'
NEW = 'vibe-kanban-full-recovery-production-20261010.service'
FALLBACK = 'vibe-kanban-full-recovery-cutback-20261010.service'
FALLBACK_PORT = 5601
PORT = 5591
BDEST = 'B:/vk-backups/vk-next-restart-full-reader-20261010/final-cutover/measured-catchup-20261010T1740'
PREPARATION_EXECUTION = '32e5299fdf5b47318b998d2522c41068'
OWNER_SESSION = '0a22fc62-fbb9-4d33-9ce3-cd2e48dac0bf'
RAW_PAYLOAD_LIMIT = 24 * 1024**3
STREAM_LIMIT = 26 * 1024**3
B_RESERVE = 2 * 1024**3
SSD_RESERVE = 2 * 1024**3
TARGETS = ['3ce20433-f984-4c33-800f-d4987145fa4a', 'c64a7b0c-9c34-43e0-b70d-7e05f93751ef']
SOURCE = 'de8dc3d527d927fbcdb98ff60769a1002ad5b0a4'
module_path = '/mnt/vk-storage/vk-runtime-backup-20261009/direct-current-state-release-20261009/release.py'
spec = importlib.util.spec_from_file_location('established_handoff', module_path)
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)
handoff.root = ROOT
sys.path.insert(0, '/home/mcp/code/worktrees/4e18-vk-staging-check/_vibe_kanban_repo/scripts')
import vk_workspace_review_snapshot as review


def save(name, value, private=False):
    p = ATTEMPT / name
    temp = p.with_name(p.name + '.next')
    with temp.open('w') as f:
        os.fchmod(f.fileno(), 0o600 if private else 0o644)
        json.dump(value, f, sort_keys=True, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    temp.replace(p)
    if name in ('actor-state.safe.json','PUBLICATION_READY.safe.json','failure.safe.json','recovery-owner-dispatch.safe.json','staging-followthrough-dispatch.safe.json'):
        alias = ROOT / name
        alias_next = alias.with_name(alias.name + '.schema-fix-next')
        with alias_next.open('w') as f:
            json.dump(value, f, sort_keys=True, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        alias_next.replace(alias)


def phase(value, **extra):
    state = dict(phase=value, at=datetime.datetime.now(datetime.timezone.utc).isoformat(), cleanup_available=False)
    state.update(extra)
    state['attempt_directory'] = str(ATTEMPT)
    save('actor-state.safe.json', state)


def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def active():
    with sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True) as c:
        return [r[0] for r in c.execute("select lower(hex(id)) from execution_processes where status='running' and dropped=0")]



def queued_sessions():
    import uuid
    with sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True) as c:
        sessions = [str(uuid.UUID(bytes=r[0])) for r in c.execute("select distinct session_id from execution_processes where julianday(created_at) >= julianday('2026-10-09T20:31:17Z')")]
    pending = []
    for sid in sessions:
        result = handoff.read_api(5561, 'sessions/' + sid + '/queue')
        assert result['success']
        if result['data']['status'] != 'empty':
            pending.append(sid)
    return pending


def backup(name):
    out = ATTEMPT / (name + '.sqlite')
    assert not out.exists()
    s = sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True)
    d = sqlite3.connect(out)
    s.backup(d, pages=1024)
    assert d.execute('pragma integrity_check').fetchall() == [('ok',)]
    d.close()
    s.close()
    out.chmod(0o600)
    receipt = review.mirror(out, 'desktop', BDEST, [])
    save(name + '.safe.json', dict(receipt, integrity='ok', source_identity=[DB.stat().st_dev, DB.stat().st_ino], scope='Current primary database only; unchanged authoritative roots and existing full B backup retained'))
    return receipt


def snapshot(name, base=None):
    value = review.capture(DB, 'Approved combined current-state handoff; preserve all current flags')
    if base:
        value['live'] = review.api_state(base)
        review.verify_api_identity(value, value['live'])
    p = ATTEMPT / name
    save(name, value, private=True)
    receipt = review.mirror(p, 'desktop', BDEST, [])
    save(name + '.receipt.safe.json', receipt)
    return value


def workspace_attachment_bases(connection):
    # Match attachments.rs resolve_session_base_path using cached paths only.
    # Never call ensure_container_exists or create a missing historical workspace.
    rows = connection.execute("""SELECT w.container_ref, s.agent_working_dir
        FROM workspaces w LEFT JOIN sessions s ON s.workspace_id = w.id
        WHERE w.container_ref IS NOT NULL""").fetchall()
    bases = set()
    for container_ref, working_dir in rows:
        if not container_ref:
            raise ValueError('Empty registered container_ref; no guessed path')
        container = Path(container_ref)
        bases.add(container)
        if working_dir:
            bases.add(container / working_dir)
    return bases


def select_native_catchup():
    from datetime import timezone
    since = int(datetime.datetime(2026, 10, 9, 10, 30, tzinfo=timezone.utc).timestamp() * 1_000_000_000)
    home = Path('/home/mcp/.local/share/vibe-kanban-green-codex-home')
    selected = []
    signatures = {}
    def walk_error(error):
        raise error
    def remember_directory(parent):
        f=Path(parent);st=f.lstat()
        if st.st_mtime_ns >= since and str(f) not in signatures:
            selected.append(f);signatures[str(f)]=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns]
    for base in (home / 'sessions', DB.parent / 'sessions', Path('/home/mcp/.cache/vibe-kanban/attachments')):
        if not base.exists():
            raise ValueError('Required current transcript root missing')
        for parent, dirs, files in os.walk(base, followlinks=False, onerror=walk_error):
            remember_directory(parent)
            for name in dirs:
                f=Path(parent)/name
                if f.is_symlink():
                    st=f.lstat()
                    if st.st_mtime_ns >= since and str(f) not in signatures:
                        selected.append(f);signatures[str(f)]=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns]
            for name in files:
                f = Path(parent) / name
                st = f.lstat()
                if st.st_mtime_ns >= since:
                    if str(f) not in signatures:
                        selected.append(f)
                    signatures[str(f)] = [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns]
    # Current configuration is part of the authoritative state; never print its contents.
    for f in DB.parent.iterdir():
        if f.is_file() and not f.name.startswith('db.v2.sqlite'):
            if str(f) not in signatures:
                selected.append(f)
            st=f.lstat(); signatures[str(f)]=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns]
    with sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True) as c:
        worktrees = workspace_attachment_bases(c)
    existing_attachment_roots = 0
    for worktree in set(worktrees):
        base = Path(worktree) / '.vibe-attachments'
        if base.is_dir():
            existing_attachment_roots += 1
            for parent, dirs, files in os.walk(base, followlinks=False, onerror=walk_error):
                remember_directory(parent)
                for name in files:
                    f=Path(parent)/name;st=f.lstat()
                    if st.st_mtime_ns >= since and str(f) not in signatures:
                        selected.append(f);signatures[str(f)]=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns]
    return selected, signatures, existing_attachment_roots


def desktop_free_bytes():
    value = subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes','desktop',
        'powershell.exe -NoProfile -NonInteractive -Command "(Get-PSDrive B).Free"'], text=True, timeout=20).strip()
    assert value.isdecimal(), 'Desktop B free-space response is not an integer'
    return int(value)


def check_catchup_budget(payload_bytes, count, desktop_free, ssd_free, snapshot_bytes):
    # Raw inputs and compressed stream have distinct measured budgets. No input omission.
    assert 0 <= payload_bytes <= RAW_PAYLOAD_LIMIT, 'Measured raw catch-up exceeds 24GiB allocation; retain all inputs'
    tar_upper = payload_bytes + count * 65536 + 1024**2
    assert tar_upper <= STREAM_LIMIT, 'Catch-up tar metadata estimate exceeds 26GiB stream allocation'
    assert desktop_free >= STREAM_LIMIT + B_RESERVE, 'Desktop B cannot hold bounded stream plus reserve'
    assert ssd_free >= snapshot_bytes + SSD_RESERVE, 'SSD cannot hold SQLite images plus reserve'
    return {'source_payload_bytes':payload_bytes,'selected_entries':count,'raw_limit_bytes':RAW_PAYLOAD_LIMIT,
            'tar_estimate_upper_bytes':tar_upper,'stream_limit_bytes':STREAM_LIMIT,'B_free_bytes':desktop_free,
            'B_reserve_bytes':B_RESERVE,'SSD_free_bytes':ssd_free,'snapshot_allocation_bytes':snapshot_bytes,'SSD_reserve_bytes':SSD_RESERVE}


def catchup_preflight():
    import shutil
    selected, signatures, roots = select_native_catchup()
    home = Path('/home/mcp/.local/share/vibe-kanban-green-codex-home')
    snapshot_bytes = 0
    for name in ('state_5.sqlite','goals_1.sqlite','queue_1.sqlite','memories_1.sqlite','thread_history_1.sqlite'):
        source = home/name
        assert source.is_file(), 'Required native database is absent'
        # Bound SQLite snapshot growth by the source image and existing WAL bytes.
        snapshot_bytes += source.stat().st_size
        wal = source.with_name(source.name + '-wal')
        if wal.exists():
            snapshot_bytes += wal.stat().st_size
    raw = sum(p.lstat().st_size for p in selected) + snapshot_bytes
    budget = check_catchup_budget(raw,len(selected)+5,desktop_free_bytes(),shutil.disk_usage(ROOT).free,snapshot_bytes + DB.stat().st_size)
    budget.update(existing_workspace_attachment_roots=roots,current_paths_unique=len(selected)==len(set(selected)),
                  selected_scope_unchanged=True, archive_payload_on_SSD=False,
                  at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save('catchup-preflight.safe.json',budget)
    return budget


def final_native_catchup():
    import shutil
    sys.path.insert(0, '/mnt/vk-storage/vk-runtime-backup-20261009/actual-candidate-controller-package-a7617608/tools')
    from vk_archive_stream import StreamingArchive, receiver_command
    budget = catchup_preflight()
    selected, signatures, existing_attachment_roots = select_native_catchup()
    images = ATTEMPT / 'final-native-db-images'
    images.mkdir(mode=0o700)
    dbs = []
    for name in ('state_5.sqlite', 'goals_1.sqlite', 'queue_1.sqlite', 'memories_1.sqlite', 'thread_history_1.sqlite'):
        source = home / name
        if not source.exists():
            raise ValueError('Required native database missing: ' + name)
        out = images / name
        a = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
        b = sqlite3.connect(out)
        a.backup(b, pages=1024)
        assert b.execute('pragma integrity_check').fetchall() == [('ok',)]
        b.close(); a.close(); out.chmod(0o600)
        selected.append(out)
        dbs.append({'name':name, 'sha256':digest(out), 'bytes':out.stat().st_size, 'integrity':'ok'})
    payload_bytes = sum(f.lstat().st_size for f in selected)
    measured = {'source_payload_bytes':payload_bytes,'selected_entries':len(selected),'sqlite_images':dbs}
    save('catchup-measurement.safe.json', measured)
    check_catchup_budget(payload_bytes,len(selected),budget['B_free_bytes'],shutil.disk_usage(ROOT).free,0)
    private = {'threshold':'2026-10-09T10:30:00Z', 'paths':[str(p) for p in selected], 'source_signatures':signatures, 'dbs':dbs}
    save('final-native-catchup.private.json', private, private=True)
    listing = b''.join(os.fsencode(str(p).lstrip('/')) + b'\0' for p in selected)
    def produce(out):
        proc = subprocess.Popen(['tar','--format=pax','--acls','--xattrs','--numeric-owner','--atime-preserve=system','--no-recursion','-C','/','-cf','-','--null','--verbatim-files-from','-T','-'], stdin=subprocess.PIPE, stdout=out, stderr=subprocess.PIPE)
        _, err = proc.communicate(listing, timeout=180)
        if proc.returncode:
            raise ValueError('Native archive production failed; no publication or ignored metadata warning')
    stream = StreamingArchive(ATTEMPT, 'final-recent-native-state.tar.zst', produce, max_bytes=STREAM_LIMIT)
    receipt = stream.deliver(BDEST, receiver_command(['-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes']))
    for path, before in signatures.items():
        st = Path(path).lstat()
        assert [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns] == before, 'Native evidence changed during catch-up'
    receipt.update(existing_workspace_attachment_roots=existing_attachment_roots, files=len(selected), source_payload_bytes=payload_bytes, sqlite_images=dbs, linux_metadata='GNU tar PAX ACL/xattr/numeric ownership/modes/timestamps/symlinks retained without following links', scope='Recent native/VK transcript and attachment files modified since retained Oct9 10:30 baseline, plus all five current native DB images; primary DB/review separately verified; not a replacement full historical backup', current_roots_reused=True)
    save('final-native-catchup.safe.json', receipt)
    return receipt


def exchange(a, b):
    assert a.is_dir() and b.is_dir() and not a.is_symlink() and not b.is_symlink()
    assert a.stat().st_dev == b.stat().st_dev
    lib = ctypes.CDLL(None, use_errno=True)
    result = lib.renameat2(-100, os.fsencode(a), -100, os.fsencode(b), 2)
    if result != 0:
        raise OSError(ctypes.get_errno(), 'Bounded frontend exchange failed')


def wait_health(port):
    limit = time.monotonic() + 40
    while True:
        try:
            return handoff.read_api(port, 'info')
        except Exception:
            if time.monotonic() >= limit:
                raise TimeoutError('Selected server health unavailable')
            time.sleep(0.25)


def main():
    lease = (ROOT / 'publication.lease').open('a')
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest = json.loads((ROOT / 'artifact/manifest.json').read_text())
    assert manifest['sourceCommit'] == SOURCE
    server = ROOT / 'artifact/server'
    staged = ROOT / 'prepared-frontend'
    assert digest(server) == manifest['files']['server']['sha256']
    assert digest(ROOT / 'artifact/migration-compatible-backstop/server') == manifest['files']['migration-compatible-backstop/server']['sha256']
    prepared = json.loads((ROOT / 'frontend-fallback-readiness.safe.json').read_text())
    assert digest(staged / 'index.html') == prepared['staged_index_sha256']
    assert manifest['sourceTree'] == '1d1fe17415a1aac5f18e5798d8ba15c61b54289b'
    assert manifest['queueRepairIncluded'] is False and manifest['routingMode'] == 'Recommend-only'
    assert handoff.prop(OLD, 'MainPID') == '1254186'
    assert handoff.prop(OLD, 'FreezerState') == 'running'
    assert digest(Path('/proc/1254186/exe')) == '2aa884b359d21373e38c49a6e1589a10e5f69f7c384d2be44515fc0fab41b70f'
    assert digest(LIVE_FRONTEND / 'index.html') == 'd690b1bf3ab5f3e7e6dfc2a53d3235b10cf94b58f87101f282467a4d2d563f80'
    phase('waiting-only-for-staging-preparation-to-complete', incumbent_usable=True)
    catchup_preflight()
    deadline = time.monotonic() + 900
    while True:
        running = active()
        if not running:
            break
        if running != [PREPARATION_EXECUTION]:
            phase('waiting-active-work-to-finish-without-interruption', running_executions=running, incumbent_usable=True)
        if time.monotonic() > deadline:
            phase('held-active-work-or-preparation-still-running', running_executions=running, incumbent_usable=True)
            return
        time.sleep(0.5)
    # Confirm actual managed execution units have drained, not merely DB status.
    unit_deadline = time.monotonic() + 30
    while True:
        units = subprocess.check_output(['systemctl', '--user', 'list-units', 'vk-exec-*', '--state=running', '--no-legend', '--plain'], text=True).strip()
        if not units:
            break
        if time.monotonic() > unit_deadline:
            phase('held-real-execution-unit-still-running', incumbent_usable=True)
            return
        time.sleep(0.5)
    catchup_preflight()  # Fresh capacity/input measurement after real execution drain.
    # Last pre-fence inputs. Do not interrupt active user work or outstanding grants.
    old_state = handoff.ownership(5561)
    assert old_state['owned'] and not any(g.get('grant') is not None for g in old_state['state']['goals'].values())
    old_info = handoff.read_api(5561, 'info')['data']
    old_projects = handoff.read_api(5561, 'projects')['data']
    old_messages = handoff.read_api(5561, 'saved-chat-messages')['data']
    old_route = json.loads(handoff.route_path.read_text())
    assert old_route['port'] == 5561 and old_route['mode'] == 'blue'
    assert (DB.stat().st_dev, DB.stat().st_ino) == (64512, 5922104)
    released = None
    exchanged = False
    candidate_started = False
    started = time.monotonic()
    try:
        assert handoff.prop(OLD, 'MainPID') == '1254186' and handoff.prop(OLD, 'FreezerState') == 'running'
        assert (DB.stat().st_dev, DB.stat().st_ino) == (64512, 5922104)
        handoff.route('maintenance', 5561)
        time.sleep(1.5)  # Retained existing preference flush interval.
        assert not active(), 'Work arrived; restore incumbent route without interruption'
        assert not queued_sessions(), 'Unconsumed queued user text must remain on incumbent'
        current = handoff.ownership(5561)
        released = handoff.ownership(5561, 'release', current['state'])['state']
        save('incumbent-released.private.json', released, private=True)
        handoff.ctl('freeze', OLD)
        assert handoff.prop(OLD, 'FreezerState') == 'frozen'
        phase('incumbent-protected-final-current-data-preimage')
        final = backup('final-fenced-current-db')
        before = snapshot('final-review-before.private.json')
        native_final = final_native_catchup()
        handoff.ctl('start', NEW)
        candidate_started = True
        info = wait_health(PORT)['data']
        pid = int(handoff.prop(NEW, 'MainPID'))
        assert digest(Path('/proc/' + str(pid) + '/exe')) == manifest['files']['server']['sha256']
        assert not handoff.ownership(PORT)['owned']
        acquired = handoff.ownership(PORT, 'acquire', released)
        assert acquired['owned']
        assert acquired['state']['goals'] == released['goals']
        assert set(released['issuedIds']) <= set(acquired['state']['issuedIds'])
        for key in ('config', 'executors'):
            assert info[key] == old_info[key], 'Current user configuration changed'
        assert handoff.read_api(PORT, 'projects')['data'] == old_projects
        assert handoff.read_api(PORT, 'saved-chat-messages')['data'] == old_messages
        after = review.capture(DB, 'Before public route; verify review preservation')
        assert {r['id']: (r['seen'], r['updated_at']) for r in before['tables']['coding_agent_turns']} == {r['id']: (r['seen'], r['updated_at']) for r in after['tables']['coding_agent_turns']}
        statuses = {}
        for eid in TARGETS:
            status = handoff.read_api(PORT, 'execution-processes/' + eid + '/native-recovery-status')['data']
            assert status['protocol'] == 1 and status['server_pid'] == pid and status['server_uid'] == os.getuid()
            assert status['execution_id'] == eid and status['writer_active'] is False and status['incomplete'] is True
            page = handoff.read_api(PORT, 'execution-processes/' + eid + '/log-history')['data']
            assert page['capture_pending'] is False
            statuses[eid] = dict(protocol=1, writer_active=False, incomplete=True, original_reader_ready=True)
        exchange(LIVE_FRONTEND, staged)
        exchanged = True
        handoff.route('blue', PORT)
        route_promoted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ca = '/mnt/vk-storage/vk-runtime-backup-20261009/direct-current-state-release-20261009/existing-homelab-ca.pem'
        context = ssl.create_default_context(cafile=ca)
        with urllib.request.urlopen('https://vibe.local/', context=context, timeout=10) as response:
            html = response.read()
        assert hashlib.sha256(html).hexdigest() == digest(LIVE_FRONTEND / 'index.html')
        served_assets = {}
        for path in re.findall(r'(?:src|href)=[\"\'](/assets/[^\"\']+\.(?:js|css))', html.decode()):
            with urllib.request.urlopen('https://vibe.local' + path, context=context, timeout=10) as response:
                actual = hashlib.sha256(response.read()).hexdigest()
            assert actual == digest(LIVE_FRONTEND / path.lstrip('/'))
            served_assets[path] = actual
        assert served_assets
        with urllib.request.urlopen('https://vibe.local/site.webmanifest', context=context, timeout=10) as response:
            manifest_hash = hashlib.sha256(response.read()).hexdigest()
        assert manifest_hash == digest(LIVE_FRONTEND / 'site.webmanifest')
        with urllib.request.urlopen('https://vibe.local/api/info', context=context, timeout=10) as response:
            assert json.load(response)['success']
        public_protocols = {}
        for eid in TARGETS:
            with urllib.request.urlopen('https://vibe.local/api/execution-processes/' + eid + '/native-recovery-status', context=context, timeout=10) as response:
                body = json.load(response)
            assert body['success']
            status = body['data']
            assert status['protocol'] == 1 and status['server_pid'] == pid and status['execution_id'] == eid
            assert status['writer_active'] is False
            public_protocols[eid] = {'protocol':1, 'server_pid':pid, 'http':200, 'json_verified':True, 'writer_active':False}
        final_review = snapshot('review-after.private.json', 'http://127.0.0.1:' + str(PORT))
        # Make normal boot select this already-tested same-data owner, retaining old units/artifacts.
        unit = Path('/home/mcp/.config/systemd/user') / NEW
        text = unit.read_text()
        assert 'VK_CAPACITY_START_PAUSED=1' in text
        unit.write_text(text.replace('VK_CAPACITY_START_PAUSED=1', 'VK_CAPACITY_START_PAUSED=0'))
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True, capture_output=True)
        subprocess.run(['systemctl', '--user', 'enable', NEW], check=True, capture_output=True)
        subprocess.run(['systemctl', '--user', 'disable', OLD], check=True, capture_output=True)
        receipt = dict(published_at=route_promoted_at, verification_finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), sourceCommit=SOURCE, server_pid=pid, port=PORT, server_sha256=manifest['files']['server']['sha256'], frontend_html_sha256=digest(LIVE_FRONTEND / 'index.html'), served_assets=served_assets, pwa_manifest_sha256=manifest_hash, final_preimage=final, final_native_catchup=native_final, statuses=statuses, public_protocols=public_protocols, incumbent_pid=1254186, incumbent_frozen=True, current_data_reused=True, database_identity=[DB.stat().st_dev, DB.stat().st_ino], schema_changed=True, additive_assignment_migration=True, matching_latest_data_fallback_sha256=manifest['files']['migration-compatible-backstop/server']['sha256'], staging_commit='2693c46d4725878f8e11310cb528b6665e916ff3', interruption_seconds=time.monotonic()-started, original_logs_or_native_transcripts_modified=False, recovered_messages_applied_by_staging=False, cleanup_available=False)
        save('PUBLICATION_READY.safe.json', receipt)
        phase('published-reader-and-protocol-ready-recovery-owner-must-import', **receipt)
    except Exception as exc:
        save('failure.safe.json', dict(error_type=type(exc).__name__, reason=str(exc)[:300], candidate_started=candidate_started, cleanup_available=False))
        if active():
            phase('held-active-work-preserved-after-handoff-failure', running_executions=active())
            raise
        handoff.route('maintenance', PORT if candidate_started else 5561)
        if handoff.prop(NEW, 'MainPID') not in ('', '0'):
            new_state = handoff.ownership(PORT)
            if new_state['owned']:
                released = handoff.ownership(PORT, 'release', new_state['state'])['state']
            handoff.ctl('freeze', NEW)
        if candidate_started:
            # Assignment migration may already exist. Never thaw c3 onto it.
            if released is None:
                released = json.loads(Path('/mnt/vk-storage/codexusage-capacity/runtime/controller/state.json').read_text())
            assert not any(g.get('grant') is not None for g in released['goals'].values())
            if not exchanged:
                exchange(LIVE_FRONTEND, staged)
                exchanged = True
            handoff.ctl('start', FALLBACK)
            wait_health(FALLBACK_PORT)
            assert digest(Path('/proc/' + handoff.prop(FALLBACK, 'MainPID') + '/exe')) == manifest['files']['migration-compatible-backstop/server']['sha256']
            assert handoff.ownership(FALLBACK_PORT, 'acquire', released)['owned']
            handoff.route('blue', FALLBACK_PORT)
            unit = Path('/home/mcp/.config/systemd/user') / FALLBACK
            body = unit.read_text()
            unit.write_text(body.replace('VK_CAPACITY_START_PAUSED=1', 'VK_CAPACITY_START_PAUSED=0'))
            subprocess.run(['systemctl','--user','daemon-reload'], check=True, capture_output=True)
            subprocess.run(['systemctl','--user','enable',FALLBACK], check=True, capture_output=True)
            subprocess.run(['systemctl','--user','disable',OLD], check=True, capture_output=True)
            phase('compatible-backstop-serving-latest-data-no-old-db-restore', fallback_pid=handoff.prop(FALLBACK, 'MainPID'), fallback_port=FALLBACK_PORT, incumbent_frozen=True, error_type=type(exc).__name__)
        else:
            if exchanged:
                exchange(LIVE_FRONTEND, staged)
            if handoff.prop(OLD, 'FreezerState') == 'frozen':
                handoff.ctl('thaw', OLD)
            if released is not None and not handoff.ownership(5561)['owned']:
                handoff.ownership(5561, 'acquire', released)
            handoff.route('blue', 5561)
            phase('incumbent-recovered-on-latest-current-data-no-old-db-restore', error_type=type(exc).__name__)
        raise
    # A real task handoff to the separately owned recovery session, never T18/MM.
    sys.path.insert(0, '/home/mcp/code/vibe-dot-connector')
    import adapter
    prompt = ('Staging scoped publication has completed. Read /mnt/vk-storage/vk-next-restart-20261010/full-recovery-readiness/PUBLICATION_READY.safe.json; exact live reader source ' + SOURCE + ', port5591, protocol1, original raw captures untouched, incumbent1254186 frozen and B final DB/review preimages verified. You remain sole exact-import owner. Under Seamus RESTORE THEM authorization, reverify actual live PID/port and your tested CLI SHA; perform the two original identity/hash-bound T18 and MM imports first using your reviewed CLI; then your separately tested18-authentic-final extension within Seamus restoration scope, with exact identities and no duplicate/replay, then verify original normal API replies and ordinary browser views if available, no duplicates/replay or rawlog/DB/badge mutations. Preserve all native evidence and record exact hashes/times. Do not restart, deploy, change security, queue tasks, clean up or prompt T18/MM. Staging has not applied either sidecar. Report each authentic restored chat promptly and persist safe restoration receipt. No new manual owner command or credential is needed.')
    try:
        result = adapter.local_followup({'session_id': OWNER_SESSION, 'prompt': prompt})
        payload = json.loads(result['content'][0]['text'])
        save('recovery-owner-dispatch.safe.json', dict(session_id=OWNER_SESSION, execution_id=payload['execution_id'], dispatched=True, only_recovery_owner=True))
    except Exception as exc:
        save('recovery-owner-dispatch.safe.json', dict(session_id=OWNER_SESSION, dispatched=False, error_type=type(exc).__name__, publication_remains_ready=True))


    # One follow-through receipt check in the existing Staging session, after its turn drained.
    # This is not a continuation loop and never retries an uncertain dispatch.
    prompt = ('The owner-approved quiet cutover actor completed. Immediately read /mnt/vk-storage/vk-next-restart-20261010/full-recovery-readiness/PUBLICATION_READY.safe.json and actor-state.safe.json, verify actual routed HTTPS/process/version and protocol1, and report the actual publication time. No restart or competing publication. The separate recovery owner remains sole original-two/18-authentic-final import owner; inspect its receipt/status and coordinate completion/ordinary visible API verification without duplicating its implementation, prompting T18/MM, or replaying tasks. Preserve all data, models/Recommend, fallback and human-QA cleanup gate. If actor publication failed or used cutback, report the exact observed result; no invented success. Persist brief safe final handoff and readback. No new build or broad cleanup.')
    try:
        result = adapter.local_followup({'session_id':'7d6734c1-c8d0-4d55-ac27-b1f763d15a6e', 'prompt':prompt})
        payload=json.loads(result['content'][0]['text'])
        save('staging-followthrough-dispatch.safe.json',dict(session_id='7d6734c1-c8d0-4d55-ac27-b1f763d15a6e',execution_id=payload['execution_id'],dispatched=True,no_duplicate_actor=True))
    except Exception as exc:
        save('staging-followthrough-dispatch.safe.json',dict(dispatched=False,error_type=type(exc).__name__,publication_remains_ready=True))


def mirror_terminal_outcome():
    results = []
    for name in ('actor-state.safe.json', 'PUBLICATION_READY.safe.json', 'failure.safe.json'):
        p = ATTEMPT / name
        if p.exists():
            try:
                results.append({'file':name, **review.mirror(p, 'desktop', BDEST, [])})
            except Exception as exc:
                results.append({'file':name, 'mirrored':False, 'error_type':type(exc).__name__})
    save('terminal-outcome-B-mirror.safe.json', {'receipts':results, 'chat_recorder_dependency':False})


def terminal_live_readback():
    live = {}
    try:
        route = json.loads(handoff.route_path.read_text())
        live['route_mode'] = route['mode']; live['port'] = route['port']
        unit = {5561:OLD,5591:NEW,5601:FALLBACK}.get(route['port'])
        if unit:
            pid = int(handoff.prop(unit,'MainPID')); live['pid']=pid
            live['active_state']=handoff.prop(unit,'ActiveState')
            if pid: live['server_sha256']=digest(Path('/proc/'+str(pid)+'/exe'))
        context=ssl.create_default_context(cafile='/mnt/vk-storage/vk-runtime-backup-20261009/direct-current-state-release-20261009/existing-homelab-ca.pem')
        with urllib.request.urlopen('https://vibe.local/api/info',context=context,timeout=5) as response:
            data=json.load(response); live['health_http']=response.status;live['info_success']=data['success']
        with urllib.request.urlopen('https://vibe.local/',context=context,timeout=5) as response:
            live['frontend_sha256']=hashlib.sha256(response.read()).hexdigest()
        protocols={}
        for eid in TARGETS:
            with urllib.request.urlopen('https://vibe.local/api/execution-processes/'+eid+'/native-recovery-status',context=context,timeout=5) as response:
                content=response.headers.get('Content-Type',''); body=response.read()
            protocols[eid]={'json':content.startswith('application/json')}
            if protocols[eid]['json']:
                data=json.loads(body);protocols[eid]['protocol']=data['data']['protocol'];protocols[eid]['server_pid']=data['data']['server_pid']
        live['normal_route_recovery_protocols']=protocols
    except Exception as exc:
        live['readback_error_type']=type(exc).__name__
    return live


def publish_github_terminal_outcome():
    state = json.loads((ATTEMPT/'actor-state.safe.json').read_text()) if (ATTEMPT/'actor-state.safe.json').exists() else {}
    failure = json.loads((ATTEMPT/'failure.safe.json').read_text()) if (ATTEMPT/'failure.safe.json').exists() else None
    publication = json.loads((ATTEMPT/'PUBLICATION_READY.safe.json').read_text()) if (ATTEMPT/'PUBLICATION_READY.safe.json').exists() else None
    public = {'attempt':ATTEMPT.name,'at':state.get('at'),'phase':state.get('phase'),
              'release_source':SOURCE,'staging':'2693c46d4725878f8e11310cb528b6665e916ff3',
              'candidate_started':failure.get('candidate_started') if failure else bool(publication),
              'cleanup_available':False,'imports_performed_by_staging':False}
    live = terminal_live_readback()
    public['actual_served_readback']=live
    if failure:
        public['failure_type']=failure.get('error_type')
        # Publish only bounded known operational reasons; never arbitrary exception payloads.
        reason=failure.get('reason','')
        known=('Measured raw catch-up','Catch-up tar','Desktop B cannot','SSD cannot','Native evidence changed','Native archive production failed','Unconsumed queued','Work arrived','Current user configuration changed')
        public['failure_reason']=reason if reason.startswith(known) else 'See preserved private failure receipt; exception content withheld'
    if publication:
        for key in ('published_at','verification_finished_at','server_pid','server_sha256','frontend_html_sha256','public_protocols','interruption_seconds','incumbent_frozen','current_data_reused','matching_latest_data_fallback_sha256'):
            public[key]=publication[key]
    else:
        public['publication_verified']=False
    text = '## Approved cutover terminal checkpoint — ' + ATTEMPT.name + '\n\n```json\n' + json.dumps(public,indent=2,sort_keys=True) + '\n```\n\nOriginal evidence, failed attempts, B backups and latest-data rollback are retained. No cleanup or imports performed by Staging. Native chat capture is not used as proof.'
    body=ATTEMPT/'github-terminal-comment.safe.txt';body.write_text(text+'\n')
    try:
        request=ATTEMPT/'github-terminal-request.safe.json'
        request.write_text(json.dumps({'body':text})+'\n')
        value=json.loads(subprocess.check_output(['/home/mcp/.local/bin/gh','api','repos/artinflight/vibe-kanban/issues/242/comments','--method','POST','--input',str(request)],text=True,timeout=30))
        observed=json.loads(subprocess.check_output(['/home/mcp/.local/bin/gh','api','repos/artinflight/vibe-kanban/issues/comments/'+str(value['id'])],text=True,timeout=30))
        assert observed['body']==text, 'GitHub terminal checkpoint readback mismatch'
        save('github-terminal-checkpoint.safe.json',{'verified':True,'url':observed['html_url'],'id':value['id'],'chat_recorder_dependency':False})
    except Exception as exc:
        save('github-terminal-checkpoint.safe.json',{'verified':False,'error_type':type(exc).__name__,'no_uncertain_write_retry':True,'body_preserved':True})


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if not (ATTEMPT / 'failure.safe.json').exists():
            save('failure.safe.json', {'error_type':type(exc).__name__, 'reason':str(exc)[:300], 'production_success_not_claimed':True})
        raise
    finally:
        mirror_terminal_outcome()
        publish_github_terminal_outcome()
        if (ATTEMPT / 'failure.safe.json').exists() and not (ATTEMPT / 'PUBLICATION_READY.safe.json').exists():
            try:
                sys.path.insert(0, '/home/mcp/code/vibe-dot-connector')
                import adapter
                result = adapter.local_followup({'session_id':'7d6734c1-c8d0-4d55-ac27-b1f763d15a6e', 'prompt':'STATUS ONLY: approved cutover retry ended with a failure receipt. Read /mnt/vk-storage/vk-next-restart-20261010/full-recovery-readiness/attempt-measured-catchup-20261010T1740/actor-state.safe.json, failure.safe.json and terminal-outcome-B-mirror.safe.json; check actual served identity/health and report precise result immediately in commentary. No builds, restart, repair, cleanup, queue change or imports in this callback. Preserve user work and rollback; no success inference. End promptly.'})
                payload = json.loads(result['content'][0]['text'])
                save('failure-readback-dispatch.safe.json', {'dispatched':True, 'execution_id':payload['execution_id'], 'one_status_only_callback':True})
            except Exception as exc:
                save('failure-readback-dispatch.safe.json', {'dispatched':False, 'error_type':type(exc).__name__, 'terminal_file_available':True})


