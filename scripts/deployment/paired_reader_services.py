"""Exact drained reader transitions; caller owns approval, data, route and recovery.

No database/configuration changes, queue drain, backup, capacity acquisition or
retry. Durable intent precedes each action. Existing journals require reconciliation.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import signal
import subprocess
import time
import urllib.request


def identity(state):
    return {k: state[k] for k in ('MainPID', 'InvocationID')}


def require_owner(actual, expected):
    if (actual['MainPID'] == '0' or not actual['InvocationID']
            or identity(actual) != identity(expected)):
        raise ValueError('Reader owner changed; preserve the observed service')


class Systemd:
    def state(self, name):
        output = subprocess.check_output(['systemctl', '--user', 'show', name,
            '-p', 'MainPID', '-p', 'InvocationID', '-p', 'ActiveState',
            '-p', 'FreezerState', '-p', 'ControlGroup'], text=True, timeout=10)
        return dict(line.split('=', 1) for line in output.splitlines())

    def action(self, verb, name):
        if verb not in ('stop', 'start', 'freeze', 'thaw'):
            raise ValueError('Unsupported reader action')
        subprocess.run(['systemctl', '--user', verb, name], check=True, timeout=30)

    def members(self, state):
        if not state['ControlGroup']:
            return set()
        root = Path('/sys/fs/cgroup') / state['ControlGroup'].lstrip('/')
        return {int(pid) for file in root.rglob('cgroup.procs')
                for pid in file.read_text().split()}

    def executable_matches(self, state, expected):
        matches = []
        for pid in self.members(state):
            try:
                with Path('/proc', str(pid), 'exe').open('rb') as f:
                    if hashlib.file_digest(f, 'sha256').hexdigest() == expected:
                        matches.append(pid)
            except (FileNotFoundError, ProcessLookupError):
                continue
        return matches

    def api_ready(self, port):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(f'http://127.0.0.1:{port}/api/info', timeout=5) as f:
                return json.load(f).get('success') is True
        except (OSError, ValueError):
            return False


class Pair:
    def __init__(self, roster, journal, guard, *, system=None, timeout=120):
        if (set(roster) != {'main', 'protected'} or not callable(guard)
                or not 1 <= timeout <= 300
                or len({r['unit'] for r in roster.values()}) != 2):
            raise ValueError('Exact paired roster and finite custody required')
        for row in roster.values():
            if (not re.fullmatch(r'[A-Za-z0-9_-]+\.service', row['unit'])
                    or type(row['port']) is not int or not 1 <= row['port'] <= 65535
                    or type(row['expected_members']) is not int or not 1 <= row['expected_members'] <= 4):
                raise ValueError('Plain units, loopback ports and exact member counts required')
        self.roster, self.path, self.guard = roster, Path(journal), guard
        self.system, self.timeout = system or Systemd(), timeout
        self.events = []
        with self.path.open('x') as f:
            os.chmod(self.path, 0o600)
            json.dump({'events': [], 'replay_allowed': False}, f)
            f.flush()
            os.fsync(f.fileno())

    def record(self, phase, role, **detail):
        self.events.append(dict(at=time.time(), phase=phase, role=role, **detail))
        temp = self.path.with_suffix('.tmp')
        with temp.open('x') as f:
            os.chmod(temp, 0o600)
            json.dump(dict(events=self.events, replay_allowed=False), f, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, self.path)
        fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def stop(self, role, expected):
        self.guard()
        name = self.roster[role]['unit']
        require_owner(self.system.state(name), expected)
        self.record('stop_intent', role, owner=identity(expected))
        self.system.action('stop', name)
        current = self.system.state(name)
        if current['MainPID'] != '0' or current['ControlGroup']:
            raise ValueError('Reader service still contains processes')
        self.record('stopped', role, state=current)

    def start(self, role, artifact_sha256, *, launch=None, freeze=True):
        self.guard()
        row = self.roster[role]
        name = row['unit']
        current = self.system.state(name)
        if current['MainPID'] != '0' or current['ControlGroup']:
            raise ValueError('Preserve existing reader; no duplicate start')
        if len(artifact_sha256) != 64 or any(c not in '0123456789abcdef' for c in artifact_sha256):
            raise ValueError('Exact reader artifact SHA-256 required')
        prior = [event for event in self.events if event['role'] == role]
        if not prior or prior[-1]['phase'] != 'stopped':
            raise ValueError('Explicit completed stop required; never replay uncertain dispatch')
        self.record('start_intent', role, artifact_sha256=artifact_sha256)
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
        try:
            try:
                launch() if launch is not None else self.system.action('start', name)
            finally:
                owner = self.system.state(name)
                self.record('start_observed', role, state=owner)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
        require_owner(owner, owner)
        deadline = time.monotonic() + self.timeout
        while True:
            self.guard()
            state = self.system.state(name)
            require_owner(state, owner)
            if state['ActiveState'] != 'active':
                raise ValueError('Reader did not remain active')
            if time.monotonic() >= deadline:
                raise TimeoutError('Reader activation did not qualify in time')
            matches = self.system.executable_matches(state, artifact_sha256)
            if len(matches) == 1 and self.system.api_ready(row['port']):
                break
            time.sleep(.25)
        self.record('reader_API_and_executable_verified', role, server_pid=matches[0])
        if freeze:
            while True:
                self.guard()
                state = self.system.state(name)
                require_owner(state, owner)
                members = self.system.members(state)
                if time.monotonic() >= deadline:
                    raise TimeoutError('Reader helpers did not drain in time')
                if len(members) != row['expected_members']:
                    time.sleep(.25)
                    continue
                self.record('freeze_intent', role, owner=identity(owner))
                self.system.action('freeze', name)
                state = self.system.state(name)
                require_owner(state, owner)
                if state['FreezerState'] != 'frozen':
                    raise ValueError('Exact reader did not freeze')
                if self.system.members(state) == members:
                    break
                self.system.action('thaw', name)
            self.record('frozen', role, state=state)
        return state
