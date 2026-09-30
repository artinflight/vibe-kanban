#!/usr/bin/env python3
"""Real systemd/cgroup failure tests; no Codex credentials, goals, or quota used.

Usage: python3 scripts/test-capacity-guard.py --guard /absolute/vk-capacity-guard
All artifacts live on the mounted secondary SSD. Only this run's units are stopped.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import uuid


def wall():
    return int(time.time() * 1000)


def write(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as file:
        os.chmod(temporary, 0o600)
        json.dump(value, file)
        file.flush()
        os.fsync(file.fileno())
    temporary.replace(path)


def alive(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().split(') ')[1][0] != 'Z'
    except FileNotFoundError:
        return False


def test(guard, root, scenario):
    directory = root / scenario
    directory.mkdir()
    permission = directory / 'permission.json'
    pids = directory / 'children.json'
    fixture = directory / 'child.py'
    fixture.write_text('''import json,os,signal,time,sys
signal.signal(signal.SIGTERM, signal.SIG_IGN)
child=os.fork()
if child==0:
    os.setsid()
    time.sleep(60)
else:
    with open(sys.argv[1], 'w') as f: json.dump([os.getpid(),child],f)
    time.sleep(60)
''')
    began = wall()
    hard = began + 6000
    lease = dict(version=1, id=str(uuid.uuid4()), allocationId='old-week:day', executionId=str(uuid.uuid4()), expiresAtMs=began+3000, stopAtMs=hard, sequence=0, revoked=False)
    if scenario == 'expired-start':
        lease['expiresAtMs'] = began - 1
    write(permission, lease)
    unit = 'vk-capacity-test-' + uuid.uuid4().hex + '.service'
    timer = unit.replace('.service', '-deadline')
    subprocess.run(['systemd-run', '--user', '--quiet', '--collect', '--unit='+timer,
                    '--on-calendar=@'+str((hard-500)//1000), '--timer-property=AccuracySec=100ms',
                    '--timer-property=Persistent=true', '/usr/bin/systemctl', '--user', 'kill',
                    '--kill-whom=all', '--signal=KILL', unit], check=True)
    command = ['systemd-run', '--user', '--quiet', '--pipe', '--service-type=exec', '--unit', unit,
               '--property=RuntimeMaxSec=4s', '--property=TimeoutStopSec=1s',
               '--property=KillMode=control-group', '--property=Restart=no',
               str(guard), str(permission), '/usr/bin/python3', str(fixture), str(pids)]
    with (directory/'stderr.log').open('w') as log:
        runner = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log)
        try:
            launch_limit = time.monotonic()+2
            while not pids.exists() and runner.poll() is None and time.monotonic() < launch_limit:
                time.sleep(.03)
            if scenario == 'expired-start':
                runner.wait(timeout=3)
                assert not pids.exists(), 'Expired permission launched a child'
                return dict(scenario=scenario, passed=True)
            assert pids.exists(), 'Guard did not start fixture: ' + (directory/'stderr.log').read_text()
            children = json.loads(pids.read_text())
            assert all(alive(pid) for pid in children)
            if scenario == 'missing-permission':
                permission.unlink()
            elif scenario == 'changed-cycle':
                lease['allocationId'] = 'fresh-week:day'
                lease['sequence'] += 1
                write(permission, lease)
            elif scenario == 'stalled-guard':
                pid = int(subprocess.check_output(['systemctl', '--user', 'show', unit, '-p', 'MainPID', '--value'], text=True))
                os.kill(pid, signal.SIGSTOP)
            elif scenario == 'lost-supervisor':
                runner.kill()
                runner.wait(timeout=2)
            # Timely renewals cannot extend the original hard deadline.
            while any(alive(pid) for pid in children) and wall() < hard+2000:
                if scenario == 'renew-to-deadline' and wall() < hard-1500:
                    lease['sequence'] += 1
                    lease['expiresAtMs'] = min(wall()+3000, hard)
                    write(permission, lease)
                time.sleep(.1)
            stopped = wall()
            assert not any(alive(pid) for pid in children), 'Root or detached descendant survived the fence'
            assert stopped <= hard, f'Work crossed the final deadline: {stopped-hard} ms'
            if scenario in ['expiry', 'lost-supervisor']:
                # Guard allows 250ms to terminate its child group; systemd then
                # allows 1s before killing detached cgroup descendants.
                assert stopped <= began+4700, f'Supervision loss exceeded expiry plus shutdown grace: {stopped-began}ms'
            if scenario in ['missing-permission', 'changed-cycle']:
                assert stopped <= began+2000, 'Invalid permission did not stop promptly'
            # Reusing the same started permission cannot relaunch after restart,
            # even if someone rewrites it with a new expiry and sequence.
            pids.unlink()
            lease['expiresAtMs'] = wall()+3000
            lease['stopAtMs'] = wall()+6000
            write(permission, lease)
            replay = command.copy()
            replay[replay.index(unit)] = unit.replace('.service', '-replay.service')
            replay_runner = subprocess.run(replay, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log, timeout=3)
            assert replay_runner.returncode != 0 and not pids.exists(), 'Spent permission relaunched work'
            subprocess.run(['systemctl', '--user', 'reset-failed', replay[replay.index('--unit')+1]], capture_output=True)
            return dict(scenario=scenario, passed=True, stoppedAfterMs=stopped-began, finalDeadlineMs=hard-began, detachedDescendantStopped=True, replayRejected=True)
        finally:
            subprocess.run(['systemctl', '--user', 'stop', unit], capture_output=True, timeout=4)
            subprocess.run(['systemctl', '--user', 'stop', timer+'.timer'], capture_output=True, timeout=4)
            subprocess.run(['systemctl', '--user', 'reset-failed', unit], capture_output=True)
            if runner.poll() is None:
                runner.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--guard', type=Path, required=True)
    options = parser.parse_args()
    subprocess.run(['mountpoint', '-q', '/mnt/vk-storage'], check=True)
    root = Path(tempfile.mkdtemp(prefix='guard-acceptance-', dir='/mnt/vk-storage/codexusage-capacity'))
    results = []
    for scenario in ['expired-start', 'expiry', 'lost-supervisor', 'missing-permission', 'changed-cycle', 'renew-to-deadline', 'stalled-guard']:
        result = test(options.guard.resolve(), root, scenario)
        results.append(result)
        print(json.dumps(result), flush=True)
        write(root/'results.json', results)
    print('Evidence: ' + str(root/'results.json'), flush=True)


if __name__ == '__main__':
    main()
