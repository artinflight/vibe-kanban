"""Source-pinned callback for the existing owner's final quiet checkpoint.

Root owns ExitStack/custody and supplies the real recovery opener. The first
callback may open it INSIDE host preparation; the SAME object remains held for
prewarm/activation/Batch and subsequent journal checkpoints. No lease is reacquired.
"""
import hashlib,json,os
from pathlib import Path


def make_callback(*,sdk,acquire_recovery,controls,provider_placement,dependencies,
                  resource_admission,plan_sha256,seed_checkpoint_sha256,output_folder,
                  required_sources=(),capture_SQL=None):
    if not callable(acquire_recovery):raise ValueError('actual owner-held context opener required')
    state={'recovery':None,'accepted':[]}
    def checkpoint_request(request):
        if request.get('format')not in ('vk-reader-final-quiet-checkpoint-request-v1','vk-reader-operation-checkpoint-request-v1'):
            raise ValueError('exact owner checkpoint request required')
        if request.get('plan_sha256',plan_sha256)!=plan_sha256:raise ValueError('actual owner plan changed')
        expected=request['files'];paths=[v['path']for v in expected]
        if not expected or len(set(paths))!=len(paths):raise ValueError('finite unique actual owner files required')
        for row in expected:
            p=Path(row['path']);h=hashlib.sha256()
            with p.open('rb')as f:
                for block in iter(lambda:f.read(65536),b''):h.update(block)
            if p.stat().st_size!=row['bytes']or h.hexdigest()!=row['sha256']:
                raise ValueError('owner file changed after quiet request')
        for path in [*required_sources,str(Path(__file__).resolve()),request.get('host_state')]:
            if path and path not in paths:paths.append(path)
        # Explicit measured byte/metadata scope, no global enumeration or DB copy.
        maximum=sum(Path(p).stat().st_size for p in paths)
        if maximum>64*1024**2 or len(paths)>64:raise ValueError('actual owner request exceeds bounded control protocol')
        if state['recovery']is None:state['recovery']=acquire_recovery()
        recovery=state['recovery'];recovery.check()
        SQL_points=[]
        if request.get('SQL_sources'):
            if not callable(capture_SQL):raise ValueError('actual SQL API callback required; raw main files or metadata flags are insufficient')
            SQL_points=capture_SQL(recovery,request['SQL_sources'])
            if {r['source']for r in SQL_points}!=set(request['SQL_sources'])or any(r.get('status')!='consistent_SQL_point_verified'or r.get('method')!='SQLite-backup-API'or r.get('independent',{}).get('integrity')!='ok'or not r.get('B_acceptance_object')or not (r.get('independent',{}).get('independent_Linux_metadata_verified')or r.get('independent',{}).get('current_Linux_metadata_verified'))for r in SQL_points):
                raise ValueError('complete actual current SQL API point evidence required')
            for row in SQL_points:
                payload=json.dumps(row,sort_keys=True,separators=(',',':')).encode()+b'\n'
                note=Path(output_folder)/(request['operation']+'-SQL-'+hashlib.sha256(payload).hexdigest()+'.json')
                if not note.exists():
                    with note.open('xb')as f:f.write(payload);f.flush();os.fsync(f.fileno())
                elif note.read_bytes()!=payload:raise ValueError('conflicting SQL acceptance epoch; preserve both')
                paths.append(str(note))
            maximum=sum(Path(p).stat().st_size for p in paths)
        accepted=sdk.checkpoint(recovery,operation=request['operation'],plan_sha256=plan_sha256,paths=paths,
            maximum_bytes=max(1,maximum),seed_checkpoint_sha256=seed_checkpoint_sha256)
        points={v['source']:v['member']for v in accepted['manifest']['files']}
        for row in expected:
            if any(points[row['path']][k]!=row[k]for k in ('bytes','sha256')):
                raise ValueError('checkpoint did not preserve exact final owner bytes')
        verified=sdk.verify_checkpoint(recovery,controls,provider_placement,dependencies,accepted,resource_admission=resource_admission)
        proof=verified['actual_independent_normal_restore']
        if proof.get('independent_owner_controls_restore_verified')is not True:
            raise ValueError('actual normal owner control restore missing')
        receipt=dict(verified,SQL_API_points=SQL_points)
        raw=json.dumps(receipt,sort_keys=True,separators=(',',':')).encode()+b'\n'
        output=Path(output_folder)
        if not output.is_absolute()or output.resolve()!=output or not output.is_relative_to('/mnt/vk-storage')or not os.path.ismount('/mnt/vk-storage'):
            raise ValueError('actual mounted bounded owner control output required')
        target=output/(request['operation']+'-'+accepted['manifest_sha256']+'.json')
        if target.exists():
            if target.read_bytes()!=raw:raise ValueError('conflicting accepted owner receipt; preserve both epochs')
        else:
            with target.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
            target.chmod(0o400)
        ref=dict(path=str(target),sha256=hashlib.sha256(raw).hexdigest());state['accepted'].append(ref)
        recovery.check();return ref
    return checkpoint_request,state
