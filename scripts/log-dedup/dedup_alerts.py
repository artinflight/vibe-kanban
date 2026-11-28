"""Bounded event identities for the existing dedup WakeWatch ledger."""
import hashlib
import uuid
SOURCE="dedup-cutover"

def event_resource(kind, identity):
    original=kind+"-"+identity
    # Keep every historically valid incident key unchanged.
    return original if len(original)<=48 else kind+"-"+hashlib.sha256(identity.encode()).hexdigest()[:40]


def observe(store,registry,row,now,activated_at=None):
    # One stall warning, terminal failure and success per reconciled attempt.
    # Old accepted dispatches remain immutable; no controller retry is launched here.
    # Accepted/queued/unknown batches retain their exact receipt and are never resent.
    identity=row['operation']+('-'+row['attempt']if row.get('attempt')else '')
    state=store.meta('cutover_source:'+identity,{'pending':{},'sequence':{}});samples={}
    if row['needs_attention']:
        key='success'if row['state']=='success'else ('issue'if row['state']=='stalled'else 'failure')
        state['pending'][key]=row
    for kind in state['pending']:
        resource=event_resource(kind,identity);key=SOURCE+':completion:'+resource
        old=store.db.execute('SELECT batch FROM incidents WHERE volume=?',(key,)).fetchone()
        if old and old['batch']:
            batch=store.db.execute('SELECT status FROM batches WHERE id=?',(old['batch'],)).fetchone()
            if batch and batch['status']!='deferred':continue
        seq=state['sequence'].get(kind,0)+1;state['sequence'][kind]=seq
        values={k:v for k,v in row.items() if type(v) in (str,int,float,bool)}
        values.update(needs_attention=True,event_kind=kind)
        event={'version':1,'source':SOURCE,'resource':resource,'event_id':str(uuid.uuid4()),'sequence':seq,'observed_at':now,'values':values,
               'report':'Fresh read of exact controller receipts and unit state. progress_at is actual verified progress; checked_at is observation only. Finite conversion success still requires final recovery, service and accounting acceptance.'}
        for target,rkey,sample in registry.event(SOURCE,event,now):samples[rkey]=sample
    with store.db:store.put('cutover_source:'+identity,state);store.observations(samples,{},now)
    return dict(row,pending_event_kinds=list(state['pending']),fresh_pending_observations=len(samples))

