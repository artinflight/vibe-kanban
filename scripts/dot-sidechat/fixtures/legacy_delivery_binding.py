"""Isolated existing authorized-destination binding fixture."""
def delivery_binding(store, principal, thread_id):
    """Bind only an ALREADY authorized unique destination for the new thread.

    Never clone a thread-only subscription, rewrite a filter, read a callback
    credential or broaden access. Old thread subscriptions/bindings stay intact.
    """
    from sidechat import Rejected
    from events import Events
    store._principal(principal, ('owner', 'dot'))
    thread = store._thread(principal, thread_id)
    events = Events(store, None, clock=store.clock)
    candidates = store.db.execute('''SELECT id,owner,filters,expires FROM sidechat_subscriptions
        WHERE owner=? AND active=1 AND expires>?''', (principal.owner, store.clock())).fetchall()
    matches = [row for row in candidates if events._matches(row, thread)]
    if len(matches) != 1:
        raise Rejected('Existing unique authorized chat subscription required; filters unchanged')
    selected = matches[0]
    from sidechat import Principal
    store.bind(Principal(principal.owner, 'owner'), thread_id, selected['id'],
               ttl=max(60, min(86400, int(selected['expires'] - store.clock()))))
    return {'subscription_id': selected['id']}

