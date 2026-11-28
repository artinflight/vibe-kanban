"""B-resident whole-cycle progress and atomic accepted-baseline publication.

The fixed controller holds its own lifetime lease and genuine native B admission.
This ledger stores small receipts, never bodies or an SSD SQLite replica. Each
completed phase is independently reopened before reuse. An interruption cannot
restart the original whole-night clock or promote a partial recovery set.
"""
from contextlib import contextmanager
from datetime import datetime
import json
import hashlib
import zlib
import math

from vk_typed_recovery import checksum,digest
from vk_nightly_window import validate as overnight_window


PHASES=('files','SQL','runtime','candidate','restore')
MAX_RECEIPT=2*1024**2
MAX_LOGICAL_RECEIPT=16*1024**2
INLINE_RECEIPT=128*1024
RECEIPT_PART=32768
PARTS_FORMAT='vk-nightly-compressed-receipt-parts-v1'


def encoded(value,maximum=MAX_RECEIPT):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(raw.encode())>maximum:raise ValueError('bounded whole-cycle receipt required: bytes='+str(len(raw.encode()))+' maximum='+str(maximum))
    return raw


def window(binding):
    start=datetime.fromisoformat(binding['started_UTC'])
    end=datetime.fromisoformat(binding['deadline_UTC'])
    if start.tzinfo is None or end.tzinfo is None:raise ValueError('aware original whole-cycle window required')
    seconds=(end-start).total_seconds()
    if binding.get('cycle_kind')=='incremental':
        overnight_window(start,end)
        return start.timestamp(),end.timestamp()
    maximum=6*3600 if binding.get('cycle_kind')=='qualification-incremental' else 8*3600
    if not math.isfinite(seconds) or not 0<seconds<=maximum:
        raise ValueError('finite original commissioning window required; not recurring overnight acceptance')
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

    def stored_receipt(self,db,value):
        """Bounded B-only payload parts; phase header and parts commit together."""
        raw=encoded(value,MAX_LOGICAL_RECEIPT).encode()
        if len(raw)<=INLINE_RECEIPT:return raw.decode()
        packed=zlib.compress(raw,6);key=hashlib.sha256(packed).hexdigest()
        if len(packed)>MAX_LOGICAL_RECEIPT:raise ValueError('bounded compressed cycle receipt required')
        for part,offset in enumerate(range(0,len(packed),RECEIPT_PART)):
            self.guard();data=packed[offset:offset+RECEIPT_PART]
            db.execute('insert into nightly_cycle_receipt_parts values(?,?,?) on conflict(sha256,part) do nothing',(key,part,data))
            if db.execute('select data from nightly_cycle_receipt_parts where sha256=? and part=?',(key,part)).fetchone()!=(data,):
                raise ValueError('cycle receipt part collision; preserve existing data')
        return encoded(dict(format=PARTS_FORMAT,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
            compressed_sha256=key,compressed_bytes=len(packed),parts=(len(packed)+RECEIPT_PART-1)//RECEIPT_PART))

    def reopened_receipt(self,db,raw):
        if len(raw.encode())>MAX_RECEIPT:raise ValueError('bounded receipt header required')
        value=json.loads(raw)
        if value.get('format')!=PARTS_FORMAT:return value
        if (set(value)!={'format','sha256','bytes','compressed_sha256','compressed_bytes','parts'}
                or any(type(value[k]) is not int or not 0<value[k]<=MAX_LOGICAL_RECEIPT
                       for k in ('bytes','compressed_bytes'))
                or type(value['parts']) is not int
                or value['parts']!=(value['compressed_bytes']+RECEIPT_PART-1)//RECEIPT_PART):
            raise ValueError('bounded complete receipt part descriptor required')
        key=digest(value['compressed_sha256']);digest(value['sha256'])
        if db.execute('select count(*) from nightly_cycle_receipt_parts where sha256=?',(key,)).fetchone()!=(value['parts'],):
            raise ValueError('cycle receipt parts missing or extra')
        packed=bytearray()
        for part in range(value['parts']):
            self.guard();row=db.execute('select data from nightly_cycle_receipt_parts where sha256=? and part=?',(key,part)).fetchone()
            expected=min(RECEIPT_PART,value['compressed_bytes']-len(packed))
            if not row or not isinstance(row[0],bytes) or len(row[0])!=expected:
                raise ValueError('cycle receipt part length differs')
            packed.extend(row[0])
        if hashlib.sha256(packed).hexdigest()!=key:raise ValueError('cycle receipt compressed hash differs')
        decoder=zlib.decompressobj();decoded=decoder.decompress(packed,value['bytes']+1)
        if (len(decoded)!=value['bytes'] or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data
                or hashlib.sha256(decoded).hexdigest()!=value['sha256']):
            raise ValueError('cycle receipt full decoded hash/length differs')
        return json.loads(decoded)

    def initialize(self,binding):
        window(binding);raw=encoded(binding);cycle_id=checksum(binding)
        with self.opened() as db:
            db.execute('create table if not exists nightly_cycles(cycle_id text primary key,binding text not null)')
            db.execute('create table if not exists nightly_cycle_receipt_parts(sha256 text,part integer,data blob not null,primary key(sha256,part)) without rowid')
            db.execute('create table if not exists nightly_cycle_phases(cycle_id text,ordinal integer,receipt text not null,sha256 text not null,primary key(cycle_id,ordinal))')
            db.execute('create table if not exists nightly_accepted_baseline(id integer primary key check(id=1),revision integer not null,receipt text not null,sha256 text not null)')
            db.execute('insert into nightly_cycles values(?,?) on conflict(cycle_id) do nothing',(cycle_id,raw))
        with self.opened(readonly=True) as db:
            if db.execute('select binding from nightly_cycles where cycle_id=?',(cycle_id,)).fetchone()!=(raw,):
                raise ValueError('independently reopened original cycle binding differs')
        return cycle_id

    def scheduled_binding(self,binding):
        """Freeze this evening's accepted predecessor once, including retries.

        The calendar/controller lease serializes callers. The caller supplies
        deterministic night/template/cohort fields; no completed receipt is
        re-labelled as new work or given another deadline on a retry.
        """
        window(binding)
        if binding.get('cycle_kind')!='incremental':raise ValueError('ordinary scheduled cycle required')
        with self.opened() as db:
            db.execute('create table if not exists nightly_cycles(cycle_id text primary key,binding text not null)')
            rows=db.execute("select binding from nightly_cycles where json_extract(binding,'$.scheduled_night')=? "
                "and json_extract(binding,'$.schedule_template_sha256')=?",
                (binding['scheduled_night'],binding['schedule_template_sha256'])).fetchall()
        if rows:
            if len(rows)!=1:raise ValueError('ambiguous scheduled cycle; preserve and reconcile')
            old=json.loads(rows[0][0]);expected=dict(binding,previous_accepted_sha256=old['previous_accepted_sha256'])
            if old!=expected:raise ValueError('original scheduled cycle bindings differ; no clock reset')
            return old
        accepted=self.accepted()
        if not accepted:raise ValueError('independently accepted current baseline required before recurring capture')
        value=dict(binding,previous_accepted_sha256=checksum(accepted))
        self.initialize(value)
        return value

    def phases(self,cycle_id):
        digest(cycle_id);values=[];previous=cycle_id
        with self.opened(readonly=True) as db:
            rows=db.execute('select ordinal,receipt,sha256 from nightly_cycle_phases where cycle_id=? order by ordinal',(cycle_id,)).fetchall()
            rows=[(ordinal,self.reopened_receipt(db,raw),sha) for ordinal,raw,sha in rows]
        if len(rows)>len(PHASES):raise ValueError('unexpected completed cycle phase; preserve')
        for expected,(ordinal,raw,sha) in enumerate(rows):
            value=raw
            if (ordinal!=expected or checksum(value)!=digest(sha) or value.get('cycle_id')!=cycle_id
                    or value.get('phase')!=PHASES[ordinal] or value.get('previous_sha256')!=previous):
                raise ValueError('independent completed phase chain differs; preserve')
            values.append(value);previous=sha
        return values

    def record(self,cycle_id,phase,result):
        values=self.phases(cycle_id);ordinal=PHASES.index(phase)
        if ordinal!=len(values):raise ValueError('only the next fixed cycle phase can be recorded')
        value=dict(cycle_id=cycle_id,phase=phase,previous_sha256=checksum(values[-1]) if values else cycle_id,result=result)
        encoded(value,MAX_LOGICAL_RECEIPT);sha=checksum(value)
        with self.opened() as db:
            db.execute('begin immediate')
            try:
                raw=self.stored_receipt(db,value)
                db.execute('insert into nightly_cycle_phases values(?,?,?,?)',(cycle_id,ordinal,raw,sha))
                self.guard();db.execute('commit')
            except BaseException:
                if db.in_transaction:db.execute('rollback')
                raise
        # A lost write reply is resolved on the next normal reopen; no phase
        # copy is repeated just because this optional caller result was lost.
        if self.phases(cycle_id)[-1]!=value:raise ValueError('independent completed phase reopen differs')
        return value

    def adopt_completed_prefix(self,parent_binding,binding,*,parent_phase_sha256,phase_count=3):
        """Explicit source-upgrade adoption, preserving the original window.

        Caller authenticates both installed configurations and identical map,
        source/cohort/runtime references under the controller/body lanes. This
        copies only reopened receipts, never images or timing claims. It cannot
        qualify a recurring cycle, a completed parent or a different SQL epoch.
        """
        window(parent_binding);window(binding)
        if type(phase_count) is not int or phase_count not in (2,3):
            raise ValueError('only completed files/SQL, optionally runtime, may be adopted')
        if (parent_binding.get('cycle_kind')!='bootstrap-current'
                or binding.get('cycle_kind')!='bootstrap-current'
                or binding==parent_binding
                or binding!=dict(parent_binding,config_sha256=binding.get('config_sha256'))):
            raise ValueError('source upgrade must preserve exact original bootstrap window/cohort')
        digest(binding['config_sha256']);digest(parent_phase_sha256)
        parent_id=checksum(parent_binding);parent=self.phases(parent_id)
        if len(parent) not in (2,3) or len(parent)<phase_count or checksum(parent[-1])!=parent_phase_sha256:
            raise ValueError('exact independently reopened completed parent prefix required')
        with self.opened(readonly=True) as db:
            if db.execute('select binding from nightly_cycles where cycle_id=?',(parent_id,)).fetchone()!=(encoded(parent_binding),):
                raise ValueError('actual parent cycle binding differs')
        required=('actual_independent_B_file_cycle_receipt_reopen_verified',
                  'actual_independent_B_SQL_cycle_receipt_reopen_verified',
                  'actual_independent_B_runtime_component_reopen_verified')
        for item,field in zip(parent,required):
            if (item['result'].get(field) is not True or item['result'].get('more_pending',False) is not False
                    or item['result'].get('deferred_SQL')):
                raise ValueError('complete independent parent phase proof required')
        current_id=self.initialize(binding);actual=self.phases(current_id)
        for number,item in enumerate(parent[:phase_count]):
            result=dict(item['result'],retained_phase_origin=dict(cycle_id=parent_id,
                phase_sha256=checksum(item),original_window_preserved=True,backup_payload_bytes_copied=0))
            if number<len(actual):
                if actual[number]['result']!=result:raise ValueError('adopted parent phase differs')
            else:self.record(current_id,item['phase'],result)
        return dict(parent_cycle_id=parent_id,cycle_id=current_id,completed_phases_reused=phase_count,
            backup_payload_bytes_copied=0,original_deadline_UTC=binding['deadline_UTC'],schedule_enabled=False)

    def accepted(self):
        with self.opened(readonly=True) as db:
            row=db.execute('select revision,receipt,sha256 from nightly_accepted_baseline where id=1').fetchone()
            value=self.reopened_receipt(db,row[1]) if row else None
        if row is None:return None
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
        encoded(value,MAX_LOGICAL_RECEIPT);sha=checksum(value)
        with self.opened() as db:
            db.execute('begin immediate')
            try:
                actual=db.execute('select sha256 from nightly_accepted_baseline where id=1').fetchone()
                expected=(previous,) if previous is not None else None
                if actual!=expected:
                    raise ValueError('accepted baseline compare-and-swap conflict; preserve both cycles')
                raw=self.stored_receipt(db,value)
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
