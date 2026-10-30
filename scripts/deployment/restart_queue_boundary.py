"""Read-only original-Restart boundary. Observation is never a writer fence.

No queue cancellation, acknowledgement, replay, process control or DB writes.
A real controller supplies the route/consumer fence, freezes its verified
incumbent, then calls frozen() before any candidate or migration may start.
"""
from pathlib import Path
import hashlib
import json
import sqlite3
import time
import urllib.request


class BoundaryHeld(RuntimeError):
    pass


def inventory(database, seconds=5):
    path = Path(database).resolve(strict=True)
    start = path.stat()
    deadline = time.monotonic() + seconds
    conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=1)
    conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    result = {'database_identity': [start.st_dev, start.st_ino],
              'active': [], 'durable_queue': [], 'incoming_pending': [],
              'complete': False, 'read_only': True, 'writer_fence_established': False}
    fingerprint = hashlib.sha256()
    try:
        conn.execute('BEGIN')
        for table in ['sessions', 'execution_processes', 'turn_github_sync_user_queue', 'turn_github_sync_incoming']:
            if not conn.execute('SELECT 1 FROM sqlite_master WHERE type="table" AND name=?', (table,)).fetchone():
                raise BoundaryHeld('Required durable inventory table unavailable: ' + table)
        queries = [
            ('sessions', 'SELECT lower(hex(id)) FROM sessions ORDER BY id'),
            ('executions', 'SELECT lower(hex(id)), status, completed_at FROM execution_processes ORDER BY id'),
            ('queue', 'SELECT lower(hex(session_id)), state, length(data) FROM turn_github_sync_user_queue ORDER BY session_id'),
            ('incoming', 'SELECT rowid, lower(hex(id)), lower(hex(session_id)), state, length(data) FROM turn_github_sync_incoming ORDER BY rowid')]
        counts = {}
        for kind, sql in queries:
            count = 0
            for row in conn.execute(sql):
                if time.monotonic() > deadline: raise BoundaryHeld('Durable inventory time bound exceeded; incomplete observation')
                extra = None
                if kind == 'incoming' and row[3] == 'received':
                    payload = hashlib.sha256()
                    with conn.blobopen('turn_github_sync_incoming', 'data', row[0], readonly=True) as blob:
                        while chunk := blob.read(65536):
                            if time.monotonic() > deadline: raise BoundaryHeld('Pending-input fingerprint work bound exceeded')
                            payload.update(chunk)
                    extra = payload.hexdigest()
                fingerprint.update(json.dumps([kind, list(row), extra], separators=(',', ':')).encode() + b'\n')
                count += 1
                if kind == 'sessions' and len(row[0]) != 32: raise BoundaryHeld('Invalid session identity')
                if kind == 'executions' and row[1] == 'running': result['active'].append(row[0])
                if kind == 'queue':
                    if row[1] not in ('queued', 'dispatching'): raise BoundaryHeld('Unknown durable queue state; input retained')
                    result['durable_queue'].append({'session': row[0], 'state': row[1], 'payload_bytes': row[2]})
                if kind == 'incoming':
                    if row[3] not in ('received', 'handled', 'dismissed'): raise BoundaryHeld('Unknown incoming state; input retained')
                    if row[3] == 'received': result['incoming_pending'].append({'rowid': row[0], 'id': row[1], 'session': row[2], 'payload_bytes': row[4], 'payload_sha256': extra})
            counts[kind] = count
        end = path.stat()
        if (start.st_dev, start.st_ino) != (end.st_dev, end.st_ino): raise BoundaryHeld('Database identity changed')
        result.update(complete=True, counts=counts, fingerprint=fingerprint.hexdigest(), unresolved_incoming_preserved_not_resumed=len(result['incoming_pending']), incoming_automatic_replay=False)
        return result
    except sqlite3.Error as error:
        raise BoundaryHeld('Durable inventory unavailable; pending state is unproved') from error
    finally:
        conn.close()


def require_dispatch_quiet(result):
    if (result.get('complete') is not True or result['active'] or result['durable_queue']):
        raise BoundaryHeld('Current work not quiet: active=%d durable_queue=%d incoming_received=%d; preserve all records' %
                           (len(result['active']), len(result['durable_queue']), len(result['incoming_pending'])))
    return result


def live(database, api_queues):
    """DB/API/DB sandwich. api_queues must read the already-supported queue API.

    Received incoming entries are private uncertainty receipts, not dispatchable
    queue items (sealed queued_message.rs receive/acknowledge contract). Carry
    them byte-for-byte and in row order; never clear, acknowledge or claim them
    resumed. Their exact fingerprints must survive both checks and cutback.

    Does not establish admission ownership or authorize mutation. Missing API,
    partial coverage or changed inputs fail closed. Historical handled/dismissed
    input is preserved, and is not mislabeled as currently pending work.
    """
    before = require_dispatch_quiet(inventory(database))
    memory = api_queues()
    if memory.get('complete') is not True or memory.get('pending_sessions'):
        raise BoundaryHeld('Volatile queue inventory incomplete or pending; no handoff')
    after = require_dispatch_quiet(inventory(database))
    if before['database_identity'] != after['database_identity'] or before['fingerprint'] != after['fingerprint']:
        raise BoundaryHeld('Work changed during quiet observation; no handoff')
    return after


def frozen(database, before, *, incumbent_frozen, consumers_quiet):
    """No HTTP while the incumbent is frozen. Caller attests actual verified
    freeze/consumer controls; fake booleans are not deployment evidence.
    """
    if not incumbent_frozen or not consumers_quiet: raise BoundaryHeld('Verified freeze/consumer boundary required')
    after = require_dispatch_quiet(inventory(database))
    if before['database_identity'] != after['database_identity'] or before['fingerprint'] != after['fingerprint']:
        raise BoundaryHeld('Work changed before freeze; abort before candidate, preserve latest data')
    return after
