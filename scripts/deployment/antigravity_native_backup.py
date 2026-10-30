"""Final fenced native recovery: bounded RAM SQLite images and Desktop B objects.

Loaded only by the owned activation controller. The prior accepted checkpoint
continues to retain older rollouts; this captures the complete changed selection.
No original history or credential content is printed, copied into Git or deleted.
"""
from pathlib import Path
import copy
import datetime
import hashlib
import json
import os
import sys
import time

D = Path(sys.argv[1]).resolve(strict=True)
N = D / 'native-recovery-fenced'
ROOT = Path('/home/mcp/.local/share/vibe-kanban-green-codex-home')
SINCE = datetime.datetime(2026, 10, 29, 20, 55, tzinfo=datetime.timezone.utc).timestamp()
BINDING = json.loads((D / 'BINDING.private.json').read_text())
module = Path(__file__).with_name('vk_native_stream_backup.py')
assert hashlib.sha256(module.read_bytes()).hexdigest() == BINDING['stream_backup_module_sha256']
from vk_native_stream_backup import capture_sqlite, generation, identity, verify_unchanged
from vk_restart_writer_fence import unit_state


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sig(path):
    return identity(path.resolve(strict=True)) if path.exists() else None


def sessions():
    return sorted(p for p in (ROOT / 'sessions').rglob('*.jsonl') if p.stat().st_mtime >= SINCE)


def guard(additional=0):
    assert os.path.ismount('/mnt/vk-storage')
    for path in ['/', str(D)]:
        space = os.statvfs(path)
        assert space.f_bavail * space.f_frsize > 2 * 1024**3, 'Host storage reserve'
    available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:'))) * 1024
    assert available > additional + 4 * 1024**3, 'Host memory reserve'


def fence():
    initial = json.loads((D / 'INITIAL.private.json').read_text())
    for name in ['vibe-kanban-native-review-20261015.service', 'fitrdy-manager.service', 'codexusage-preview.service']:
        state = unit_state(name)
        assert state['FreezerState'] == 'frozen'
        assert all(state[key] == initial['units'][name][key] for key in ['MainPID', 'InvocationID'])
    for name in ['vibe-dot-connector.service', 'vibe-dot-sidechat-publisher.service']:
        state = unit_state(name)
        assert state['MainPID'] == '0' and state['ActiveState'] == 'inactive'


def save(value):
    temporary = N / 'RECEIPT.next'
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(N / 'RECEIPT.private.json')


def progress(phase, **details):
    print(json.dumps(dict(phase=phase, **details)), flush=True)


def main():
    guard()
    fence()
    N.mkdir(mode=0o700)
    manifest = Path('/mnt/vk-storage/vk-staging-catchup-20261028/cutover-v5-20261029/MANIFEST.private.json')
    assert sha(manifest) == '703488c3caa16d48336049e9be23e60967cccb95c4a48b10466b896200d0c961'
    cfg = json.loads(manifest.read_text())
    assert sha(cfg['plan']['path']) == cfg['plan']['sha256']
    plan = json.loads(Path(cfg['plan']['path']).read_text())
    sys.path.insert(0, plan['source_folder'])
    from vk_nightly_desktop_objects import DesktopObjects
    control = copy.deepcopy(plan['workers']['files']['desktop'])
    control.pop('whole_cycle_deadline_UTC', None)
    ref = BINDING['native_baseline']
    assert sha(ref['path']) == ref['sha256']
    baseline = json.loads(Path(ref['path']).read_text())
    records, bindings = [], {}
    selected = sessions()
    result = dict(complete=False, files=records, source_signatures=bindings,
                  session_selection_since=SINCE, selected_sessions=[str(p) for p in selected],
                  B_root=control['B_root'], disk_payload_bytes_written=0)
    save(result)
    with DesktopObjects(control, guard=guard) as remote:
        for name in ['state_5.sqlite', 'goals_1.sqlite', 'memories_1.sqlite', 'queue_1.sqlite', 'thread_history_1.sqlite', 'logs_2.sqlite']:
            fence()
            source = (ROOT / name).resolve(strict=True)
            before = generation(source)
            relay = lambda **value: progress(database=name, **value)
            if str(source) == baseline['source'] and before == baseline['source_generation']:
                verified = verify_unchanged(baseline, remote.client, guard=guard, progress=relay)
                row = copy.deepcopy(baseline)
                row['final_unchanged_reverification'] = verified
                row['online_checkpoint_only'] = False
            else:
                row = capture_sqlite(source, remote.client, maximum_image_bytes=3500*1024**2,
                                     chunk_bytes=control['maximum_object_bytes'], guard=guard, progress=relay)
                row['captured_under_final_fence'] = True
            assert before == generation(source), 'Native writer changed during recovery capture'
            bindings.update({str(source)+suffix: value for suffix, value in before.items()})
            descriptor = remote.client.ensure((json.dumps(row, sort_keys=True)+'\n').encode())
            row['descriptor'] = descriptor
            records.append(row)
            save(result)
        for source in selected:
            fence()
            before = sig(source)
            expected, restored, segments = hashlib.sha256(), hashlib.sha256(), []
            size = 0
            class Sink:
                def write(self, raw):
                    restored.update(raw)
                    return len(raw)
            with source.open('rb') as stream:
                while raw := stream.read(control['maximum_object_bytes']):
                    guard(len(raw)*2)
                    expected.update(raw)
                    size += len(raw)
                    segments.append(remote.client.ensure(raw, readback_sink=Sink()))
                    progress('native-rollout-B-readback', file_index=len(records), verified_bytes=size)
            assert sig(source) == before and expected.hexdigest() == restored.hexdigest()
            row = dict(source=str(source), bytes=size, sha256=expected.hexdigest(), segments=segments,
                       independent_native_readback_verified=True)
            row['descriptor'] = remote.client.ensure((json.dumps(row, sort_keys=True)+'\n').encode())
            bindings[str(source)] = before
            records.append(row)
            save(result)
    fence()
    assert {path: sig(Path(path)) for path in bindings} == bindings
    assert sessions() == selected
    result.update(complete=True, UTC=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    save(result)
    progress('native-final-recovery-verified', files=len(records), bytes=sum(row['bytes'] for row in records))


if __name__ == '__main__':
    raise SystemExit('Load through the owned activation controller; standalone backup is not a writer fence')
