#!/usr/bin/env python3
"""Opt-in real native persistence/resume acceptance, without model inference.

Creates only a new caller-supplied disposable fixture root. No real credentials,
existing session homes, production services or backup archives are opened. Test
content is synthetic; real model continuation and Vibe UI replay are NOT tested.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import queue
import signal
import sqlite3
import subprocess
import tarfile
import threading
import time
import zlib

import vk_history_archive_acceptance as archive
import vk_history_compaction_probe as codec

ALLOWED = {'initialize', 'thread/start', 'thread/resume', 'thread/inject_items',
           'thread/unsubscribe', 'thread/read', 'thread/items/list', 'account/read'}


class Rpc:
    def __init__(self, launcher, home, work, evidence):
        self.home = home
        self.evidence = evidence
        home.mkdir(mode=0o700, exist_ok=True)
        temp = home / '.fixture-tmp'
        temp.mkdir(mode=0o700, exist_ok=True)
        env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'C.UTF-8',
               'CODEX_HOME': str(home), 'TMPDIR': str(temp),
               'XDG_CACHE_HOME': str(home / 'cache'), 'XDG_CONFIG_HOME': str(home / 'xdg-config'),
               'XDG_DATA_HOME': str(home / 'xdg-data')}
        self.stderr = evidence.with_suffix('.stderr.private').open('xb')
        self.process = subprocess.Popen([launcher, 'app-server', '-c', 'features.multi_agent=false',
                                         '-c', 'features.multi_agent_v2=false'],
                                        cwd=work, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.stderr, start_new_session=True)
        self.queue = queue.Queue(maxsize=64)
        self.seq = 0
        self.events = []
        def pump():
            try:
                for _ in range(1024):
                    line = self.process.stdout.readline(codec.MAX_BYTES + 1)
                    if not line:
                        break
                    if len(line) > codec.MAX_BYTES:
                        raise ValueError('native response bound exceeded')
                    self.queue.put(json.loads(line), timeout=5)
            except BaseException as exc:
                self.queue.put(exc, timeout=5)
            finally:
                self.queue.put(None, timeout=5)
        self.pump = threading.Thread(target=pump, daemon=True)
        self.pump.start()

    def call(self, method, params, *, optional=False):
        if method not in ALLOWED:
            raise ValueError('non-inference fixture RPC allowlist rejected method')
        self.seq += 1
        self.process.stdin.write(archive.encoded({'id': self.seq, 'method': method, 'params': params}) + b'\n')
        self.process.stdin.flush()
        end = time.monotonic() + 20
        while True:
            obj = self.queue.get(timeout=max(.01, end - time.monotonic()))
            if obj is None or isinstance(obj, BaseException):
                raise RuntimeError('native RPC stream failed')
            if obj.get('id') == self.seq:
                event = {'method': method, 'response': obj}
                if 'error' in obj:
                    event['scope_at_error'] = scope_metrics()
                self.events.append(event)
                if 'error' in obj and not optional:
                    raise RuntimeError(f'native {method} rejected: {obj["error"]}')
                return obj.get('result') if 'result' in obj else {'error': obj['error']}

    def initialize(self):
        result = self.call('initialize', {'clientInfo': {'name': 'vk_whole_session_archive', 'version': '1'},
                                          'capabilities': {'experimentalApi': True}})
        self.process.stdin.write(b'{"method":"initialized","params":{}}\n')
        self.process.stdin.flush()
        return result

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            # Only the exact new process group created by this fixture.
            os.killpg(self.process.pid, signal.SIGTERM)
            self.process.wait(timeout=5)
        # Native startup may leave plugin-discovery children after its launcher
        # exits. This brand-new session/group belongs solely to this fixture.
        # Do not enumerate, signal or stop any other process group or service.
        owned_startup_children_signalled = False
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
            owned_startup_children_signalled = True
        except ProcessLookupError:
            pass
        self.pump.join(timeout=2)
        self.process.stdout.close()
        self.stderr.close()
        self.evidence.write_bytes(archive.encoded({'pid': self.process.pid, 'returncode': self.process.returncode,
                                                  'owned_startup_children_signalled': owned_startup_children_signalled,
                                                  'events': self.events}))


def bounded_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if before.st_size > codec.MAX_BYTES:
            raise ValueError('fixture file exceeded capture bound')
        data = bytearray()
        while True:
            block = os.read(fd, min(65536, codec.MAX_BYTES + 1 - len(data)))
            if not block:
                break
            data.extend(block)
            if len(data) > codec.MAX_BYTES:
                raise ValueError('fixture capture grew beyond bound')
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError('closed fixture file changed during capture')
        return bytes(data)
    finally:
        os.close(fd)


def tar_bytes(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as tar:
        for key, data in sorted(files.items()):
            header = tarfile.TarInfo(key)
            header.mode = 0o600
            header.size = len(data)
            tar.addfile(header, io.BytesIO(data))
    return output.getvalue()


def consistent_history_database(home):
    """Snapshot only this new fixture's closed native paginated store, including WAL.

    The serialized consistent image is the archived source, not an exact copy of
    the old WAL/main-file representation. Production databases are never opened.
    """
    path = home / 'thread_history_1.sqlite'
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as source:
        size = source.execute('pragma page_size').fetchone()[0] * source.execute('pragma page_count').fetchone()[0]
        if size > codec.MAX_BYTES:
            raise ValueError('fixture history database size exceeded')
        snapshot = sqlite3.connect(':memory:')
        try:
            source.backup(snapshot)
            assert snapshot.execute('pragma integrity_check').fetchone() == ('ok',)
            assert snapshot.execute('pragma foreign_key_check').fetchall() == []
            tables = {row[0] for row in snapshot.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'thread_turns', 'thread_items', 'thread_history_projection_state'} <= tables:
                raise ValueError('unsupported native paginated history schema')
            return snapshot.serialize()
        finally:
            snapshot.close()


def payload(generation):
    # Deterministic moderately compressible test content, not a sample of user history.
    count = 1024 if generation == 0 else 64
    return f'WHOLE_SESSION_MARKER_GEN_{generation}\n' + '\n'.join(
        f'fixture output record {i} {hashlib.sha256(f"{generation}:{i}".encode()).hexdigest()}' for i in range(count))


def scope_metrics():
    result = {'host_memory_psi': Path('/proc/pressure/memory').read_text()}
    entries = Path('/proc/self/cgroup').read_text().splitlines()
    unified = next((entry.split(':', 2)[2] for entry in entries if entry.startswith('0::')), None)
    if unified:
        root = Path('/sys/fs/cgroup') / unified.lstrip('/')
        result['cgroup'] = unified
        for name in ('memory.current', 'memory.peak', 'memory.swap.current', 'memory.events',
                     'memory.max', 'memory.high', 'memory.swap.max', 'memory.pressure', 'cpu.stat',
                     'pids.current', 'pids.peak', 'pids.max', 'pids.events'):
            try:
                result[name] = (root / name).read_text().strip()
            except OSError as exc:
                result[name] = {'unavailable': type(exc).__name__}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='New disposable private fixture root on approved bulk storage')
    parser.add_argument('--codex', required=True, help='Existing authorized installed launcher; no download')
    parser.add_argument('--zstd', required=True, help='Existing compression binary; no download')
    parser.add_argument('--history-mode', choices=('legacy', 'paginated'), help='Omit to test the installed runtime default')
    args = parser.parse_args()
    root = args.root.absolute()
    root.mkdir(mode=0o700, exist_ok=False)
    work = root / 'work'
    work.mkdir(mode=0o700)
    source = root / 'source-home'
    source.mkdir(mode=0o700)
    versions = []
    evidence = {'source': 'native runtime persisted synthetic injected messages', 'model_requests': 0,
                'credentials_copied': False, 'existing_history_read': False, 'B_payload_read': False,
                'generations': [], 'native_resume_checks': []}
    source_directory = Path(__file__).absolute().parent
    evidence['source_files_sha256'] = {name: codec.digest((source_directory / name).read_bytes()) for name in
        ('verify_vk_native_history_archive.py', 'vk_history_archive_acceptance.py', 'vk_history_compaction_probe.py')}
    evidence['source_head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source_directory.parents[1], text=True).strip()
    evidence['scope_before'] = scope_metrics()
    zstd = lambda data: subprocess.run([args.zstd, '-q', '-3', '-c'], input=data,
                                       stdout=subprocess.PIPE, check=True).stdout
    zstd_pool = {}
    zstd_rows = []
    started = time.monotonic()
    try:
        thread = key = None
        for generation in range(3):
            rpc = Rpc(args.codex, source, work, root / f'source-{generation}.rpc.private.json')
            try:
                evidence['runtime'] = rpc.initialize().get('userAgent')
                params = {'cwd': str(work), 'sandbox': 'read-only', 'approvalPolicy': 'never'}
                if thread is None:
                    start_params = {**params, 'ephemeral': False}
                    if args.history_mode:
                        start_params['historyMode'] = args.history_mode
                    result = rpc.call('thread/start', start_params)
                    thread = result['thread']['id']
                    path = Path(result['thread']['path'])
                    key = path.relative_to(source).as_posix()
                    evidence['history_mode_observed'] = result['thread']['historyMode']
                    evidence['history_mode_explicitly_requested'] = args.history_mode
                else:
                    rpc.call('thread/resume', {**params, 'threadId': thread})
                rpc.call('thread/inject_items', {'threadId': thread, 'items': [
                    {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': payload(generation)}]},
                    {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': f'Fixture acknowledgement {generation}.'}]}]})
                rpc.call('thread/unsubscribe', {'threadId': thread})
            finally:
                rpc.close()
            files = {key: bounded_file(source / key)}
            required = {'native_rollout': key}
            if evidence['history_mode_observed'] == 'paginated':
                files['thread_history_1.sqlite'] = consistent_history_database(source)
                required['native_thread_history'] = 'thread_history_1.sqlite'
            assert all(any(f'WHOLE_SESSION_MARKER_GEN_{i}'.encode() in data for data in files.values()) for i in range(generation + 1))
            versions.append(files)
            raw, objects = archive.seal(files, session_id=thread, required=required,
                                        history_mode=evidence['history_mode_observed'])
            new_zstd = 0
            for checksum, data in objects.items():
                if checksum not in zstd_pool:
                    zstd_pool[checksum] = len(zstd(zlib.decompress(data)))
                    new_zstd += zstd_pool[checksum]
            meta_zstd = len(zstd(raw))
            zstd_rows.append({'independent_closure_bytes': sum(zstd_pool[k] for k in objects) + meta_zstd,
                              'new_objects_bytes': new_zstd, 'manifest_bytes': meta_zstd,
                              'new_transfer_with_manifest_bytes': new_zstd + meta_zstd})
            package = root / f'generation-{generation}'
            package.mkdir(mode=0o700)
            (package / 'manifest.json').write_bytes(raw)
            object_dir = package / 'objects'
            object_dir.mkdir(mode=0o700)
            for checksum, data in objects.items():
                (object_dir / checksum).write_bytes(data)
            restored_home = root / f'restored-home-{generation}'
            def reader(home):
                assert bounded_file(home / key) == files[key]
                if 'thread_history_1.sqlite' in files:
                    assert bounded_file(home / 'thread_history_1.sqlite') == files['thread_history_1.sqlite']
                consumer = Rpc(args.codex, home, work, root / f'restored-{generation}.rpc.private.json')
                try:
                    consumer.initialize()
                    account = consumer.call('account/read', {})
                    resumed = consumer.call('thread/resume', {**params, 'threadId': thread})
                    resumed_path = Path(resumed['thread']['path'])
                    assert resumed_path == home / key, 'native used original home instead of restored file'
                    assert resumed['thread']['id'] == thread
                    items = consumer.call('thread/items/list', {'threadId': thread, 'limit': 100,
                                          'sortDirection': 'asc', 'itemsView': 'full'}, optional=True)
                    return {'native_thread_resume_succeeded': True, 'restored_path_used': True,
                            'account_available': account.get('account') is not None,
                            'items_api_error': items.get('error'),
                            'items_api_markers_visible': all(f'WHOLE_SESSION_MARKER_GEN_{i}' in json.dumps(items) for i in range(generation + 1)),
                            'model_continuation_exercised': False}
                finally:
                    consumer.close()
            # Exercise persisted package bytes, not the producer's in-memory objects.
            disk_raw = (package / 'manifest.json').read_bytes()
            disk_objects = {checksum: (object_dir / checksum).read_bytes() for checksum in objects}
            for broken in ({}, {**disk_objects, next(iter(disk_objects)): b'corrupt'}):
                rejected_destination = root / f'must-not-exist-{generation}'
                try:
                    archive.hydrate(disk_raw, broken, rejected_destination,
                                    expected_sha256=codec.digest(raw), session_id=thread,
                                    reader=lambda _: (_ for _ in ()).throw(AssertionError('reader ran on bad archive')))
                except ValueError:
                    assert not rejected_destination.exists()
                else:
                    raise AssertionError('bad archive was accepted')
            checked = archive.hydrate(disk_raw, disk_objects, restored_home,
                                     expected_sha256=codec.digest(raw), session_id=thread, reader=reader)
            evidence['native_resume_checks'].append(checked)
            with sqlite3.connect('file:' + str(restored_home / 'state_5.sqlite') + '?mode=ro', uri=True) as db:
                assert db.execute('pragma integrity_check').fetchone() == ('ok',)
                native_row = db.execute('SELECT rollout_path FROM threads WHERE id=?', (thread,)).fetchone()
                assert native_row and Path(native_row[0]) == restored_home / key
            packed_tar = tar_bytes(files)
            compressed = zstd(packed_tar)
            (package / 'complete-session.tar.zst').write_bytes(compressed)
            expanded = subprocess.run([args.zstd, '-q', '-d', '-c'], input=compressed,
                                      stdout=subprocess.PIPE, check=True).stdout
            assert expanded == packed_tar
            with tarfile.open(fileobj=io.BytesIO(expanded), mode='r:') as tar:
                assert [member.name for member in tar.getmembers()] == sorted(files)
                for member in tar:
                    assert member.isfile() and tar.extractfile(member).read() == files[member.name]
            evidence['generations'].append({'session_file_bytes': len(files[key]), 'session_file_sha256': codec.digest(files[key]),
                                            'capture_file_bytes': {k: len(v) for k, v in files.items()},
                                            'tar_bytes': len(packed_tar), 'whole_session_tar_zstd3_bytes': len(compressed),
                                            'tar_zstd3_sha256': codec.digest(compressed), 'tar_zstd_byte_exact_restore': True,
                                            'manifest_sha256': codec.digest(raw), 'complete_markers_retained': generation + 1,
                                            'parent_manifest_required': False})
        evidence['incremental_comparison'] = archive.compare(versions, session_id=thread, required=required,
                                                            history_mode=evidence['history_mode_observed'])
        evidence['repeated_complete_tar_zstd3_bytes'] = sum(row['whole_session_tar_zstd3_bytes'] for row in evidence['generations'])
        evidence['zstd3_incremental_comparison'] = {
            'generations': zstd_rows,
            'cumulative_unique_objects_and_all_manifests_bytes': sum(zstd_pool.values()) + sum(r['manifest_bytes'] for r in zstd_rows),
            'latest_independent_closure_bytes': zstd_rows[-1]['independent_closure_bytes'],
            'parent_manifest_required': False,
            'synthetic_fixture_not_whole_production_estimate': True}
        evidence['tested_fixture_recovery_set'] = {'files': list(versions[-1]), 'bytes': sum(map(len, versions[-1].values())),
            'scope': 'this isolated native thread only; not production Vibe, goals, queues, work or attachments'}
        evidence['limitations'] = [
            'Injected messages produce no real model-generated turns; history-items visibility is not a browse acceptance.',
            'Native thread/resume is real; authenticated model continuation is not exercised.',
            'Fixture history DB projection has no model turns; real populated history DB rebuild is not certified.',
            'Retain the complete existing registered DB/work/config/attachment scope; this is not a production minimum.',
            'Hydration is fresh-directory content recovery only, not production metadata/reader/lifecycle integration.']
        evidence['passed'] = True
    except BaseException as exc:
        evidence.update({'passed': False, 'failure_type': type(exc).__name__, 'failure': str(exc)})
        raise
    finally:
        evidence['seconds'] = time.monotonic() - started
        evidence['own_test_processes_waited'] = True
        evidence['scope_before_exit'] = scope_metrics()
        (root / 'acceptance.private.json').write_bytes(archive.encoded(evidence))
        print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
