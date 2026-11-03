"""Read-only registration health; never renews or gates agent dispatch."""
import datetime
import time


def iso(value):
    return datetime.datetime.fromtimestamp(value, datetime.timezone.utc).isoformat()


def registration_health(store, principal, context, now=None):
    from events import Events
    now = time.time() if now is None else now
    thread = store._thread(principal, context['thread_id'])
    # Do not run Events.__init__ (DDL) on this read-only status path.
    events = Events.__new__(Events)
    events.store, events.db, events.clock = store, store.db, lambda: now
    exists = store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sidechat_subscriptions'").fetchone()
    rows = store.db.execute('''SELECT id,owner,filters,expires,active FROM sidechat_subscriptions
        WHERE owner=?''', (principal.owner,)).fetchall() if exists else []
    matched = [r for r in rows if events._matches(r, thread)]
    live = [r for r in matched if r['active'] and r['expires'] > now]
    result = {'observed_at': iso(now), 'delivery': 'not_confirmed',
              'agent_prompt_dependency': False}
    if len(live) > 1:
        return dict(result, status='ambiguous', active_destinations=len(live),
                    next_step='Reconcile existing registrations; overlapping destinations fail closed.')
    if len(live) == 1:
        row = live[0]
        return dict(result, status='registered', subscription_id=row['id'],
                    expires_at=iso(row['expires']), renewal_due=row['expires'] - now <= 3600,
                    next_step='The platform must renew this existing registration before expiry; status reads never renew it.')
    expired = [r for r in matched if r['active'] and r['expires'] <= now]
    return dict(result, status='expired' if expired else 'unavailable',
                next_step='Restore the same registration using signed events/subscribe verification; keep credentials and filters unchanged.')
