#!/usr/bin/env python3
"""Bounded, credential-free host diagnostics for shared agent startup failures."""

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import ipaddress
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import time


HOSTS = ('chatgpt.com', 'api.openai.com', 'github.com', 'api.github.com')
JOURNAL_PATTERN = 'Codex spawn error|routing discovery timed out|Could not resolve host|Temporary failure in name resolution'
UUID = re.compile(r'^[0-9a-fA-F-]{32,36}$')


def utc(timestamp=None):
    return datetime.fromtimestamp(timestamp or time.time(), timezone.utc).isoformat()


def classify(body):
    """Return fixed labels only; never persist the original message."""
    # journalctl JSON encodes non-printable MESSAGE fields as byte arrays.
    if isinstance(body, list):
        try:
            body = bytes(body).decode(errors='replace')
        except (TypeError, ValueError):
            return None
    if not isinstance(body, str):
        return None
    text = body.lower()
    if 'routing discovery timed out' in text:
        return 'routing_discovery_timeout'
    if 'failed to refresh available models' in text:
        if 'child process' in text and 'timeout' in text:
            return 'model_refresh_child_timeout'
        if 'timed out' in text or 'timeout' in text:
            return 'model_refresh_request_timeout'
    if any(term in text for term in (
        'could not resolve host', 'temporary failure in name resolution',
        'dns error', 'failed to lookup address',
    )):
        return 'dns_failure'
    return None


def run(argv, timeout=8):
    """No shell, stdin, inherited curl configuration, or error-output logging."""
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                timeout=timeout, check=False)
        return result.returncode, result.stdout.decode(errors='replace')[:2_000_000]
    except subprocess.TimeoutExpired:
        return 124, ''
    except OSError:
        return 127, ''


def connect_readonly(path):
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    deadline = time.monotonic() + 2
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    return connection


def dns_probe(host, resolver, record='A'):
    start = time.monotonic()
    code, out = run(['dig', '@' + resolver, host, record, '+time=2', '+tries=1',
                     '+noall', '+comments', '+answer', '+stats'], timeout=3)
    status = re.search(r'status: ([A-Z]+)', out)
    answers = []
    for line in out.splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[3] in ('A', 'AAAA'):
            try:
                answers.append(str(ipaddress.ip_address(fields[4])))
            except ValueError:
                pass
    return dict(kind='dns', host=host, resolver=resolver, record=record, exit=code,
                status=status.group(1) if status else 'NO_RESPONSE',
                probe_error=code < 0 or code == 127,
                answers=answers, elapsed_ms=round((time.monotonic() - start) * 1000))


def https_probe(host, ipv4=False, pinned=None):
    argv = ['curl', '-q', '--silent', '--head', '--output', '/dev/null',
            '--connect-timeout', '3', '--max-time', '6', '--noproxy', '*',
            '--proto', '=https', '--write-out',
            '%{http_code} %{remote_ip} %{time_namelookup} %{time_connect} '
            '%{time_appconnect} %{time_starttransfer} %{time_total}']
    if ipv4:
        argv.append('-4')
    if pinned:
        argv += ['--resolve', f'{host}:443:{pinned}']
    code, out = run(argv + ['https://' + host + '/'], timeout=7)
    fields = out.split()
    result = dict(kind='https', host=host, family='ipv4' if ipv4 else 'default',
                  pinned=bool(pinned), exit=code)
    # HTTP 401/403/429/5xx still proves a server answered; no auth is sent.
    if len(fields) == 7:
        try:
            result.update(http_status=int(fields[0]), remote_ip=str(ipaddress.ip_address(fields[1])))
            result.update(zip(('dns_s', 'connect_s', 'tls_s', 'first_byte_s', 'total_s'),
                              [float(value) for value in fields[2:]]))
        except ValueError:
            pass
    result['transport_ok'] = code == 0 and bool(result.get('http_status'))
    return result


class Watcher:
    def __init__(self, args):
        self.args = args
        self.root = args.output
        if not os.path.ismount('/mnt/vk-storage'):
            raise RuntimeError('secondary SSD is not mounted')
        if not self.root.resolve().is_relative_to(Path('/mnt/vk-storage')):
            raise RuntimeError('diagnostic output must be on secondary SSD')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self.lock = (self.root / 'watch.lock').open('w')
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.log = logging.getLogger('connectivity')
        self.log.setLevel(logging.INFO)
        self.log.addHandler(RotatingFileHandler(self.root / 'events.jsonl',
                                               maxBytes=5_000_000, backupCount=8))
        self.state_path = self.root / 'cursor.json'
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        self.recent = deque(maxlen=256)
        self.pinned = {}
        self.last_snapshot = 0
        self.source_errors = 0

    def emit(self, event):
        if event['kind'] == 'source_error':
            self.source_errors += 1
        self.log.info(json.dumps({'observed_at': utc(), **event}, sort_keys=True))

    def save(self):
        temporary = self.state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state))
        temporary.replace(self.state_path)

    def native_events(self):
        with connect_readonly(self.args.codex_logs) as connection:
            high = connection.execute('SELECT coalesce(max(id),0) FROM logs').fetchone()[0]
            cursor = self.state.get('native_id')
            if cursor is None or cursor > high:
                cursor = connection.execute(
                    'SELECT coalesce(min(id),?,0) FROM logs WHERE ts>=?',
                    (high, int(time.time()) - self.args.lookback),
                ).fetchone()[0] - 1
            rows = connection.execute(
                "SELECT id,ts,level,target,feedback_log_body,thread_id,process_uuid FROM logs "
                "WHERE id>? AND id<=? AND level IN ('WARN','ERROR') ORDER BY id LIMIT 500",
                (cursor, high),
            ).fetchall()
            for row in rows:
                # Avoid quoted prompts/tool payloads masquerading as diagnostics.
                target = row['target']
                if not (target.startswith('codex_models_manager::') or target in (
                    'codex_core::responses_retry', 'codex_api::transport',
                    'codex_core::client',
                )):
                    continue
                category = classify(row['feedback_log_body'] or '')
                if category:
                    process = row['process_uuid'] or ''
                    process = process if re.fullmatch(r'pid:\d+:[0-9a-f-]+', process) else None
                    thread = row['thread_id'] or ''
                    self.emit(dict(kind='native_error', category=category, event_at=utc(row['ts']),
                                   native_id=row['id'], target=target, process=process,
                                   thread_id=thread if UUID.fullmatch(thread) else None))
                    self.recent.append((row['ts'], process, category))
            self.state['native_id'] = rows[-1]['id'] if len(rows) == 500 else high

    def journal_events(self):
        since = self.state.get('journal_since', time.time() - self.args.lookback)
        # journalctl expands unit globs against historical journal fields, which
        # can dominate each poll on this host. Discover current units over D-Bus
        # and query exact names; repeat discovery to follow application releases.
        code, out = run(['systemctl', '--user', 'list-units', '--type=service',
                         '--state=running', '--plain', '--no-legend',
                         'vibe-kanban*.service'], timeout=3)
        units = [line.split()[0] for line in out.splitlines() if line.split()
                 and re.fullmatch(r'vibe-kanban[\w.-]*\.service', line.split()[0])]
        if code != 0 or not units:
            self.emit(dict(kind='source_error', source='journal_units', exit=code))
            return
        argv = ['journalctl', '--user']
        for unit in units:
            argv += ['-u', unit]
        code, out = run(argv + ['--since', '@' + str(int(since)),
                               '--grep', JOURNAL_PATTERN, '--no-pager', '-o', 'json'], timeout=15)
        if code not in (0, 1):
            self.emit(dict(kind='source_error', source='journal', exit=code))
            return
        seen = deque(self.state.get('journal_seen', []), maxlen=256)
        for line in out.splitlines():
            row = json.loads(line)
            unit = row.get('_SYSTEMD_USER_UNIT', '')
            if not (unit.startswith('vibe-kanban') or unit.startswith('vk-exec-')):
                continue
            key = row.get('__CURSOR')
            if key in seen:
                continue
            seen.append(key)
            category = classify(row.get('MESSAGE', ''))
            if category:
                self.emit(dict(kind='journal_error', category=category, unit=unit,
                               event_at=utc(int(row['__REALTIME_TIMESTAMP']) / 1_000_000)))
        self.state.update(journal_since=time.time() - 5, journal_seen=list(seen))

    def execution_events(self):
        since = self.state.get('execution_since', time.time() - self.args.lookback)
        with connect_readonly(self.args.vk_db) as connection:
            rows = connection.execute(
                "SELECT hex(e.id) id,hex(e.session_id) session_id,hex(s.workspace_id) workspace_id,"
                "e.status,e.exit_code,e.started_at,e.completed_at FROM execution_processes e "
                "JOIN sessions s ON s.id=e.session_id WHERE e.status='failed' "
                "AND e.completed_at>=? ORDER BY e.completed_at LIMIT 100",
                (utc(since),),
            ).fetchall()
        seen = deque(self.state.get('failed_seen', []), maxlen=256)
        for row in rows:
            if row['id'] not in seen:
                self.emit(dict(kind='failed_execution', **dict(row)))
                seen.append(row['id'])
        # Keep overlap for concurrent completions, deduplicated by execution ID.
        if len(rows) < 100:
            self.state['execution_since'] = time.time() - 60
        else:
            self.state['execution_since'] = datetime.fromisoformat(rows[-1]['completed_at']).timestamp()
        self.state['failed_seen'] = list(seen)

    def snapshot(self):
        for name, command in (
            ('dns_config', ['resolvectl', 'status']),
            ('routes_v4', ['ip', '-4', 'route', 'show', 'default']),
            ('routes_v6', ['ip', '-6', 'route', 'show', 'default']),
            ('resolver_stats', ['resolvectl', 'statistics']),
        ):
            code, out = run(command, timeout=3)
            self.emit(dict(kind='context', source=name, exit=code, text=out[:8192]))
        self.emit(dict(kind='host_load', load=os.getloadavg(),
                       mem_available_kb=next((int(line.split()[1]) for line in
                       Path('/proc/meminfo').read_text().splitlines()
                       if line.startswith('MemAvailable:')), None)))
        self.last_snapshot = time.time()

    def cycle(self):
        began = time.monotonic()
        self.source_errors = 0
        for name, callback in (('native', self.native_events), ('journal', self.journal_events),
                               ('executions', self.execution_events)):
            try:
                callback()
            except (sqlite3.Error, OSError, ValueError, KeyError) as error:
                self.emit(dict(kind='source_error', source=name, error_type=type(error).__name__))
        now = time.time()
        recent = [(p, c) for t, p, c in self.recent if t >= now - 120 and p]
        processes = sorted({p for p, _ in recent})
        if len(processes) >= 2:
            self.emit(dict(kind='shared_failure_window', window_s=120, processes=processes,
                           categories=sorted({c for _, c in recent})))
        jobs = []
        for host in HOSTS:
            for resolver in self.args.resolvers:
                jobs.append((dns_probe, (host, resolver)))
            jobs.append((dns_probe, (host, '127.0.0.53', 'AAAA')))
            jobs += [(https_probe, (host,)), (https_probe, (host, True))]
        failures = 0
        probe_errors = 0
        fallback = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(fn, *args) for fn, args in jobs]
            for future in futures:
                event = future.result()
                self.emit(event)
                if event['kind'] == 'dns':
                    probe_errors += event['probe_error']
                    failures += not event['probe_error'] and (event['exit'] != 0 or event['status'] != 'NOERROR')
                    if event['record'] == 'A' and event['resolver'] == '127.0.0.53' and event['answers']:
                        self.pinned[event['host']] = (event['answers'][0], now)
                else:
                    failures += not event['transport_ok']
                    cached = self.pinned.get(event['host'])
                    if not event['transport_ok'] and cached and now - cached[1] < 900:
                        fallback.append(pool.submit(https_probe, event['host'], True, cached[0]))
            for future in fallback:
                self.emit(future.result())
        if failures or probe_errors or now - self.last_snapshot >= 300:
            self.snapshot()
        self.save()
        status = dict(kind='heartbeat', failures=failures, probe_errors=probe_errors,
                      source_errors=self.source_errors,
                      cycle_s=round(time.monotonic() - began, 3), expires_at=utc(self.args.until))
        self.emit(status)
        temporary = self.root / 'latest.tmp'
        temporary.write_text(json.dumps({'observed_at': utc(), **status}, indent=2))
        temporary.replace(self.root / 'latest.json')
        print(json.dumps(dict(at=utc(), failures=failures, probe_errors=probe_errors,
                              source_errors=self.source_errors,
                              output=str(self.root))), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--codex-logs', type=Path, required=True)
    parser.add_argument('--vk-db', type=Path, required=True)
    parser.add_argument('--resolvers', nargs='+', default=['127.0.0.53', '100.100.100.100', '1.1.1.1'])
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--lookback', type=int, default=600)
    parser.add_argument('--until', type=float, required=True, help='Fixed UTC Unix expiry, survives restarts')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if args.interval < 15 or args.lookback < 0:
        parser.error('interval must be >=15 seconds; lookback must be nonnegative')
    for resolver in args.resolvers:
        ipaddress.ip_address(resolver)
    os.umask(0o077)
    watcher = Watcher(args)
    stopping = False

    def stop(_signal, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    watcher.emit(dict(kind='watcher_start', expires_at=utc(args.until), interval_s=args.interval))
    while not stopping and time.time() < args.until:
        start = time.monotonic()
        watcher.cycle()
        if args.once:
            break
        while not stopping and time.monotonic() - start < args.interval and time.time() < args.until:
            time.sleep(0.25)
    watcher.emit(dict(kind='watcher_stop', expired=time.time() >= args.until))


if __name__ == '__main__':
    main()
