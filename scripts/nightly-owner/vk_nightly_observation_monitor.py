"""Temporary observation only: bounded local metadata, no AI or repair actions."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import time

UNITS = ('vk-nightly-observer.service', 'vk-nightly-journal-delivery.service',
         'vk-nightly-journal-delivery.timer')
ALIAS = Path('/home/mcp/.local/share/vibe-kanban/frontend-dist/current')
STATUS = Path('/mnt/vk-storage/vk-nightly-efficiency-20261017/commissioning-20261103/observer-v19-release-20261105/STATUS.private.json')
UNIT_FILE = Path('/home/mcp/.config/systemd/user/vk-nightly-observer.service')
MAX_LOG = 2 * 1024 * 1024  # Current plus one rotated file: at most 4 MiB.


def utc():
    return datetime.now(timezone.utc).isoformat()


def bounded_read(path, maximum=65536):
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('metadata exceeds bound')
    return raw


def snapshot(expected_unit_sha256):
    result = {}
    try:
        info = ALIAS.lstat()
        target = ALIAS.resolve(strict=True)
        target_info = target.stat()
        result['release'] = dict(link=os.readlink(ALIAS) if ALIAS.is_symlink() else None,
                                 resolved=str(target), device=info.st_dev, inode=info.st_ino,
                                 target_device=target_info.st_dev, target_inode=target_info.st_ino)
    except OSError as error:
        result['release'] = dict(error=type(error).__name__)
    try:
        run = subprocess.run(['systemctl', '--user', 'show', *UNITS,
                              '-p', 'Id', '-p', 'ActiveState', '-p', 'SubState',
                              '-p', 'Result', '-p', 'MainPID', '-p', 'ExecMainStatus'],
                             capture_output=True, text=True, timeout=5, check=True)
        if len(run.stdout) > 16384:
            raise ValueError('service metadata exceeds bound')
        services = {}
        for block in run.stdout.strip().split('\n\n'):
            fields = dict(line.split('=', 1) for line in block.splitlines() if '=' in line)
            name = fields.pop('Id', None)
            if name in UNITS:
                services[name] = fields
        if set(services) != set(UNITS):
            raise ValueError('incomplete service observation')
        result['services'] = services
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result['services'] = dict(error=type(error).__name__)
    try:
        digest = hashlib.sha256(bounded_read(UNIT_FILE)).hexdigest()
        current = digest == expected_unit_sha256
        health = dict(unit_sha256=digest, status_binding_current=current)
        # A new unit may point to a new epoch. Never report old health as current.
        if current:
            data = json.loads(bounded_read(STATUS))
            for key in ('phase', 'ready', 'instance', 'reason'):
                value = data.get(key)
                if value is None or isinstance(value, (str, bool, int)):
                    health[key] = value[:512] if isinstance(value, str) else value
        result['observer_health'] = health
    except (OSError, ValueError, TypeError) as error:
        result['observer_health'] = dict(error=type(error).__name__)
    return result


def event_kind(previous, current, now, last_event, heartbeat=3600):
    if previous is None:
        return 'initial'
    if previous != current:
        return 'change'
    if now - last_event >= heartbeat:
        return 'heartbeat'
    return None


def append_event(directory, event, maximum=MAX_LOG):
    raw = (json.dumps(event, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if len(raw) > 16384 or len(raw) > maximum:
        raise ValueError('event exceeds bound')
    current = directory / 'events.jsonl'
    older = directory / 'events.previous.jsonl'
    for path in (current, older):
        if path.is_symlink() or (path.exists() and not stat.S_ISREG(path.stat().st_mode)):
            raise ValueError('log path is not a regular file')
    if current.exists() and current.stat().st_size + len(raw) > maximum:
        os.replace(current, older)
    fd = os.open(current, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)


def save_status(directory, value):
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    if len(raw) > 16384:
        raise ValueError('status exceeds bound')
    temp = directory / 'status.tmp'
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    os.replace(temp, directory / 'status.json')


def storage_ready(directory):
    return (os.path.ismount('/mnt/vk-storage') and directory.resolve() == directory
            and directory.is_dir() and directory.stat().st_uid == os.getuid()
            and stat.S_IMODE(directory.stat().st_mode) == 0o700)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--until', required=True)
    parser.add_argument('--observer-unit-sha256', required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    deadline = datetime.fromisoformat(args.until)
    if deadline.tzinfo is None or not args.directory.is_relative_to('/mnt/vk-storage'):
        parser.error('aware deadline and SSD directory required')
    if datetime.now(timezone.utc) >= deadline:
        return 0  # Expired service does not inspect sources or write logs.
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    previous, last_event = None, 0.0
    while not stopping and datetime.now(timezone.utc) < deadline:
        if not storage_ready(args.directory):
            return 1  # Never fall back to the unmounted directory/system disk.
        current = snapshot(args.observer_unit_sha256)
        now = time.monotonic()
        kind = event_kind(previous, current, now, last_event)
        if not storage_ready(args.directory):
            return 1
        if kind:
            changed = sorted(k for k in current if previous is None or previous.get(k) != current[k])
            append_event(args.directory, dict(at_UTC=utc(), event=kind,
                                             changed_sections=changed, observation=current))
            last_event = now
        save_status(args.directory, dict(at_UTC=utc(), phase='observing',
                                         stops_at_UTC=deadline.isoformat(), poll_seconds=300,
                                         observation=current, automatic_repairs=False, AI_calls=0))
        previous = current
        if args.once:
            return 0
        wake = min(time.monotonic() + 300,
                   time.monotonic() + max(0, (deadline - datetime.now(timezone.utc)).total_seconds()))
        while not stopping and time.monotonic() < wake:
            time.sleep(min(1, max(0, wake - time.monotonic())))
    if storage_ready(args.directory):
        reason = 'signal' if stopping else 'deadline'
        append_event(args.directory, dict(at_UTC=utc(), event='stopped', reason=reason))
        save_status(args.directory, dict(at_UTC=utc(), phase='stopped', reason=reason,
                                         stops_at_UTC=deadline.isoformat(), AI_calls=0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
