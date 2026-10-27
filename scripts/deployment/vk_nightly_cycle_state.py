"""B-resident whole-cycle progress and atomic accepted-baseline publication.

The fixed controller holds its own lifetime lease and genuine native B admission.
This ledger stores small receipts, never bodies or an SSD SQLite replica. Each
completed phase is independently reopened before reuse. An interruption cannot
restart the original whole-night clock or promote a partial recovery set.
"""
from contextlib import contextmanager
from datetime import datetime
import json
import math

from vk_typed_recovery import checksum,digest


PHASES=('files','SQL','runtime','candidate','restore')
MAX_RECEIPT=2*1024**2


def encoded(value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(raw.encode())>MAX_RECEIPT:raise ValueError('bounded whole-cycle receipt required')
    return raw


def window(binding):
    start=datetime.fromisoformat(binding['started_UTC'])
    end=datetime.fromisoformat(binding['deadline_UTC'])
    if start.tzinfo is None or end.tzinfo is None:raise ValueError('aware original whole-cycle window required')
    seconds=(end-start).total_seconds()
    if not math.isfinite(seconds) or not 0<seconds<=8*3600:
        raise ValueError('whole cycle must fit the installed eight-hour overnight window')
    return start.timestamp(),end.timestamp()


class CycleState:
    def __init__(self,client,reference,*,guard):
        self.client=client;self.reference=reference;self.guard=guard

    @contextmanager
    def opened(self,*,readonly=False):
        self.guard();r=self.reference
        db=self.client.connect(r['index_name'],r['checkpoint_sha256'],readonly=readonly,working=readonly)
        try:yield db
        finally:db.close()

    def initialize(self,binding):
        window(binding);raw=encoded(binding);cycle_id=checksum(binding)
        with self.opened() as db:
            db.execute('create table if not exists nightly_cycles(cycle_id text primary key,binding text not null)')
            db.execute('create table if not exists nightly_cycle_phases(cycle_id text,ordinal integer,receipt text not null,sha256 text not null,primary key(cycle_id,ordinal))')
            db.execute('create table if not exists nightly_accepted_baseline(id integer primary key check(id=1),revision integer not null,receipt text not null,sha256 text not null)')
            db.execute('insert into nightly_cycles values(?,?) on conflict(cycle_id) do nothing',(cycle_id,raw))
        with self.opened(readonly=True) as db:
            if db.execute('select binding from nightly_cycles where cycle_id=?',(cycle_id,)).fetchone()!=(raw,):
                raise ValueError('independently reopened original cycle binding differs')
        return cycle_id

    def phases(self,cycle_id):
        digest(cycle_id);values=[];previous=cycle_id
        with self.opened(readonly=True) as db:
            rows=db.execute('select ordinal,receipt,sha256 from nightly_cycle_phases where cycle_id=? order by ordinal',(cycle_id,)).fetchall()
        if len(rows)>len(PHASES):raise ValueError('unexpected completed cycle phase; preserve')
        for expected,(ordinal,raw,sha) in enumerate(rows):
            value=json.loads(raw)
            if (ordinal!=expected or checksum(value)!=digest(sha) or value.get('cycle_id')!=cycle_id
                    or value.get('phase')!=PHASES[ordinal] or value.get('previous_sha256')!=previous):
                raise ValueError('independent completed phase chain differs; preserve')
            values.append(value);previous=sha
        return values

    def record(self,cycle_id,phase,result):
        values=self.phases(cycle_id);ordinal=PHASES.index(phase)
        if ordinal!=len(values):raise ValueError('only the next fixed cycle phase can be recorded')
        value=dict(cycle_id=cycle_id,phase=phase,previous_sha256=checksum(values[-1]) if values else cycle_id,result=result)
        raw=encoded(value);sha=checksum(value)
        with self.opened() as db:
            db.execute('insert into nightly_cycle_phases values(?,?,?,?)',(cycle_id,ordinal,raw,sha))
        # A lost write reply is resolved on the next normal reopen; no phase
        # copy is repeated just because this optional caller result was lost.
        if self.phases(cycle_id)[-1]!=value:raise ValueError('independent completed phase reopen differs')
        return value

    def accepted(self):
        with self.opened(readonly=True) as db:
            row=db.execute('select revision,receipt,sha256 from nightly_accepted_baseline where id=1').fetchone()
        if row is None:return None
        value=json.loads(row[1])
        if value.get('revision')!=row[0] or checksum(value)!=digest(row[2]):
            raise ValueError('independently reopened accepted baseline differs')
        return value

    def publish(self,cycle_id,*,finished_UTC):
        values=self.phases(cycle_id)
        if len(values)!=len(PHASES):raise ValueError('all complete cycle phases required before publication')
        candidate=values[3]['result'];packet=candidate['packet'];current=candidate['candidate'];restored=values[4]['result']
        if (current.get('format')!='vk-nightly-finalized-current-candidate-v1'
                or current['descriptor_sha256']!=checksum(current['descriptor'])
                or packet['descriptor_sha256']!=current['descriptor_sha256']
                or packet['consumer_contract_sha256']!=current['consumer_contract_sha256']
                or restored.get('normal_leased_consumer_entrypoint_verified') is not True
                or restored.get('independent_composed_restore_verified') is not True
                or restored.get('consumer_packet_sha256')!=checksum(packet)
                or restored.get('descriptor_sha256')!=current['descriptor_sha256']
                or restored.get('content_proof_sha256')!=current['content_proof_sha256']
                or restored.get('consumer_contract_sha256')!=current['consumer_contract_sha256']):
            raise ValueError('actual authenticated normal composed restore is required before publication')
        with self.opened(readonly=True) as db:
            row=db.execute('select binding from nightly_cycles where cycle_id=?',(cycle_id,)).fetchone()
        binding=json.loads(row[0]);start,end=window(binding);finished=datetime.fromisoformat(finished_UTC)
        if finished.tzinfo is None or not start<=finished.timestamp()<end:
            raise TimeoutError('original whole-night window expired; retain completed proof without advancing baseline')
        old=self.accepted()
        if old and old['cycle_id']==cycle_id:
            if old['phase_chain_sha256']!=checksum(values[-1]):raise ValueError('published cycle evidence changed')
            return dict(old,reused_completed_publication=True)
        previous=binding['previous_accepted_sha256']
        if previous!=(checksum(old) if old else None):raise ValueError('another accepted baseline advanced; no overwrite')
        value=dict(format='vk-nightly-accepted-current-baseline-v1',revision=old['revision']+1 if old else 1,
            cycle_id=cycle_id,phase_chain_sha256=checksum(values[-1]),previous_accepted_sha256=previous,
            descriptor_sha256=current['descriptor_sha256'],descriptor=current['descriptor'],
            consumer_contract_sha256=current['consumer_contract_sha256'],consumer_contract=current['consumer_contract'],
            content_proof_sha256=current['content_proof_sha256'],restore_receipt_sha256=checksum(restored),
            completed_UTC=finished_UTC,elapsed_seconds=finished.timestamp()-start,
            original_epoch=current['descriptor']['original_epoch'],current_recoverable_set_accepted=True,
            schedule_enabled=False,OS_SSD_payload_or_index_bytes=0)
        raw=encoded(value);sha=checksum(value)
        with self.opened() as db:
            db.execute('begin immediate')
            try:
                actual=db.execute('select sha256 from nightly_accepted_baseline where id=1').fetchone()
                expected=(previous,) if previous is not None else None
                if actual!=expected:
                    raise ValueError('accepted baseline compare-and-swap conflict; preserve both cycles')
                db.execute('insert into nightly_accepted_baseline values(1,?,?,?) on conflict(id) do update set revision=excluded.revision,receipt=excluded.receipt,sha256=excluded.sha256',
                    (value['revision'],raw,sha))
                self.guard();db.execute('commit')
            except BaseException:
                if db.in_transaction:db.execute('rollback')
                raise
        if self.accepted()!=value:raise ValueError('normal independent accepted-pointer reopen differs')
        return value


def run_cycle(store,binding,*,files,SQL,runtime,finalize,restore,guard,now,report=lambda _:None):
    """Fixed trusted source adapters, never commands/callbacks from a manifest.

    Adapters retain real source/drive/access/STOP guards and receive the same
    absolute deadline. Completed entries are reopened without invoking them.
    The external lifetime controller lease excludes a second cycle owner.
    """
    start,end=window(binding)
    def check():
        guard();current=now();t=current.timestamp()
        if current.tzinfo is None or not start<=t<end:raise TimeoutError('original whole-cycle deadline expired')
    check();cycle_id=store.initialize(binding);completed=store.phases(cycle_id)
    callbacks=(files,SQL,runtime,finalize,restore)
    for number,phase in enumerate(PHASES):
        check()
        if number<len(completed):
            report(dict(phase='reusing-independent-completed-cycle-phase',completed_phase=phase,cycle_id=cycle_id))
            continue
        results={v['phase']:v['result'] for v in completed}
        value=callbacks[number](results,binding['deadline_UTC'],check)
        if phase in ('files','SQL') and (value.get('more_pending') is not False or value.get('deferred_SQL')):
            raise ValueError('incomplete '+phase+' phase; retain points without advancing acceptance')
        required={'files':'actual_independent_B_file_cycle_receipt_reopen_verified',
                  'SQL':'actual_independent_B_SQL_cycle_receipt_reopen_verified',
                  'runtime':'actual_independent_B_runtime_component_reopen_verified'}
        if phase in required and value.get(required[phase]) is not True:
            raise ValueError('independent '+phase+' completion receipt required')
        check();completed.append(store.record(cycle_id,phase,value))
        report(dict(phase='whole-cycle-phase-independently-reopened',completed_phase=phase,cycle_id=cycle_id))
    check();return store.publish(cycle_id,finished_UTC=now().isoformat())
