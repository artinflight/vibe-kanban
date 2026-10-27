"""Bounded capture/readback of only unresolved qualified member-map points.

The controller holds CurrentMap's exclusive lease and the sole admitted native
B object session. No global source inventory or accepted-carrier copy occurs.
Each completed file is committed only after an ordered independent B readback
matches its full qualified digest. Native candidates/completed chunks survive
interruption before this commit and are reused by content identity on resume.
The resulting points retain their epochs; this worker cannot accept the final
namespace, SQL cohort, runtime binding or calendar on its own.
"""
import hashlib

from vk_nightly_current_map import decode_member
from vk_nightly_objects import ChunkSink
from vk_nightly_file_version import capture_qualified_version,PrefixMismatch,QualifiedVersionUnavailable
from vk_nightly_checkpoints import digest
from vk_nightly_b_controls import retry_native_busy


class HashSink:
    def __init__(self):self.hash=hashlib.sha256();self.bytes=0

    def write(self,block):
        self.hash.update(block);self.bytes+=len(block);return len(block)


def capture_pending(current_map,client,*,guard,maximum_members,maximum_source_bytes,
                    chunk_bytes,on_progress=lambda _:None,read_prefix=None):
    if (type(maximum_members) is not int or maximum_members<1
            or type(maximum_source_bytes) is not int or maximum_source_bytes<1):
        raise ValueError('finite admitted file/byte capture batch required')
    current_map.check();db=current_map.db
    if not db.execute('select complete from metadata').fetchone()[0]:
        raise ValueError('finish retained namespace composition before its capture batch')
    db.execute('create table if not exists file_acceptance(name text primary key,proof blob not null) without rowid')
    done=0;deferred=0;source_bytes=0;initial_upload=client.payload_bytes_sent
    reused_before=client.native_receipts_reused
    readbacks_before=client.independent_readback_objects;readback_bytes_before=client.independent_readback_bytes
    for name,raw in current_map.pending_files(maximum_members):
        guard();current_map.source_phase_check()
        value=decode_member(raw);point=value['qualification'];row=value['member']
        if (point.get('source')!='/'+name or point.get('row')!=row
                or point.get('state')!='qualified-pending-body' or row.get('segments')):
            raise ValueError('exact unresolved qualified member required')
        prefix=value.get('candidate_accepted_prefix')
        if prefix is not None:
            digest(prefix['sha256']);digest(prefix['independent_proof_sha256'])
            if (type(prefix['bytes']) is not int or not 0<prefix['bytes']<row['bytes']
                    or not prefix.get('segments') or sum(s['bytes'] for s in prefix['segments'])!=prefix['bytes']):
                raise ValueError('exact independently accepted prefix recipe required')
            if read_prefix is None:raise ValueError('accepted prefix requires its authenticated B reader; no full recopy fallback')
        worst_source_bytes=row['bytes']+(prefix['bytes'] if prefix else 0)
        if source_bytes+worst_source_bytes>maximum_source_bytes:
            return dict(completed_members=done,source_bytes_read=source_bytes,
                        encoded_payload_bytes_sent=client.payload_bytes_sent-initial_upload,
                        next_point_bytes=row['bytes'],more_pending=True,current_baseline_accepted=False)
        independent=HashSink()
        class OrderedReadback:
            prefix_read=False
            def write(self,block):
                if not self.prefix_read:
                    if prefix is not None:
                        before=independent.bytes;read_prefix(prefix,independent)
                        if independent.bytes-before!=prefix['bytes']:
                            raise ValueError('authenticated prefix reader length differs')
                    self.prefix_read=True
                return independent.write(block)
        sink=ChunkSink(client,chunk_bytes=chunk_bytes,readback_sink=OrderedReadback())
        prefix_retry_bytes=0
        try:
            try:transfer=capture_qualified_version(point,sink,guard=guard,prefix=prefix)
            except PrefixMismatch as error:
                if sink.raw_bytes or sink.segments or sink.buffer:raise ValueError('prefix mismatch emitted unexpected bytes')
                prefix_retry_bytes=error.bytes_read;prefix=None
                transfer=capture_qualified_version(point,sink,guard=guard)
        except QualifiedVersionUnavailable as error:
            current_map.defer_file(name,hashlib.sha256(raw).hexdigest(),str(error),checkpoint=guard)
            source_bytes+=error.bytes_read+prefix_retry_bytes;deferred+=1
            on_progress(dict(completed_members=done,deferred_source_points=deferred,last_name=name,
                             source_bytes_read=source_bytes,requires_source_requalification=True,
                             encoded_payload_bytes_sent=client.payload_bytes_sent-initial_upload))
            continue
        new_segments=sink.finish();segments=(prefix['segments'] if prefix else [])+new_segments
        if (independent.bytes!=row['bytes'] or independent.hash.hexdigest()!=row['sha256']
                or sum(s['bytes'] for s in segments)!=row['bytes']):
            raise ValueError('ordered independently restored full file differs; keep pending point')
        member=dict(row,segments=segments)
        proof=dict(qualified_journal=point.get('journal'),transfer=transfer,
                   accepted_prefix_bytes_reused=prefix['bytes'] if prefix else 0,
                   prefix_retry_source_bytes=prefix_retry_bytes,
                   independent_ordered_B_readback_bytes=independent.bytes,
                   independent_ordered_B_readback_sha256=independent.hash.hexdigest(),
                   independent_readback_strategy='ordered-object-acceptance-readback-v1',
                   source_metadata=dict(mode=row['mode'],uid=row['uid'],gid=row['gid'],
                                        mtime_ns=row['mtime_ns'],xattrs=row['xattrs']),
                   original_epoch_repaired=False,current_baseline_accepted=False)
        accepted=dict(value,member=member,qualification=dict(point,row=member,state='qualified-retained-body'),
                      independent_file_proof=proof)
        # A concurrent bounded metadata reader can briefly hold a native
        # SQLite read lock. Retry only final idempotent acceptance, retaining
        # the completed upload/readback instead of recopying the point.
        retry_native_busy(lambda:current_map.accept_file(name,hashlib.sha256(raw).hexdigest(),
            accepted,proof,checkpoint=guard),guard=guard)
        done+=1;source_bytes+=row['bytes']+prefix_retry_bytes
        on_progress(dict(completed_members=done,last_name=name,source_bytes_read=source_bytes,
                         independent_object_readbacks=client.independent_readback_objects-readbacks_before,
                         independent_object_readback_bytes=client.independent_readback_bytes-readback_bytes_before,
                         encoded_payload_bytes_sent=client.payload_bytes_sent-initial_upload))
    more=db.execute("select 1 from members where state='file-needs-capture' limit 1").fetchone() is not None
    deferred_table=db.execute("select 1 from sqlite_master where name='file_transfer_deferred'").fetchone()
    requalify=bool(deferred_table and db.execute("select 1 from members m join file_transfer_deferred d on m.name=d.name where m.state='current-namespace-replay-required' limit 1").fetchone())
    return dict(completed_members=done,source_bytes_read=source_bytes,
                encoded_payload_bytes_sent=client.payload_bytes_sent-initial_upload,
                native_receipts_reused=client.native_receipts_reused-reused_before,
                independent_object_readbacks=client.independent_readback_objects-readbacks_before,
                independent_object_readback_bytes=client.independent_readback_bytes-readback_bytes_before,
                more_pending=more or requalify,requires_source_requalification=requalify,deferred_source_points=deferred,
                current_baseline_accepted=False)
