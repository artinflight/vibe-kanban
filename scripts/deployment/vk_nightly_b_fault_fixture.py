"""Acceptance-only source instrumentation; never a production job option."""
import hashlib
from pathlib import Path


FAULT = '''
        from unittest.mock import patch
        real_replace=os.replace;real_fsync=os.fsync;real_unlink=os.unlink;real_rmdir=Path.rmdir
        renamed=False
        def replacement(src,dst,**kwargs):
            nonlocal renamed
            if Path(dst)==store.root/'current.json':
                if FAULT_STAGE=='before_publication':os._exit(81)
                if FAULT_STAGE=='candidate_objects_removed':raise OSError('fixture preparation interrupted')
                result=real_replace(src,dst,**kwargs);renamed=True;return result
            return real_replace(src,dst,**kwargs)
        def syncing(fd):
            info=os.fstat(fd)
            if FAULT_STAGE=='rename_before_fsync' and renamed and (info.st_dev,info.st_ino)==store.identity:os._exit(85)
            return real_fsync(fd)
        def unlinking(path,**kwargs):
            real_unlink(path,**kwargs)
            if FAULT_STAGE=='during_retention' and kwargs.get('dir_fd') is not None:
                previous=job.read()['previous'];info=os.fstat(kwargs['dir_fd'])
                if [info.st_dev,info.st_ino]==previous['objects']:os._exit(83)
        def removing(path):
            real_rmdir(path)
            if FAULT_STAGE=='candidate_objects_removed' and path==store.root/job.read()['candidate']/'objects':os._exit(84)
        real_reconcile=job._reconcile_held
        def reconciling():
            if FAULT_STAGE=='after_publication':os._exit(82)
            return real_reconcile()
        with patch('os.replace',replacement),patch('os.fsync',syncing),patch('os.unlink',unlinking),patch.object(Path,'rmdir',removing),patch.object(job,'_reconcile_held',reconciling):
            result=job.tick(factory,quiescent,retention_adopted=True,reserve_bytes=reserve)
            if FAULT_STAGE=='candidate_objects_removed':job.reconcile(retention_adopted=True,inputs_quiescent=True)
'''

RECOVERY = '''
        from unittest.mock import patch
        real_fsync=os.fsync;real_unlink=os.unlink;events=[];previous=job.read()['previous']
        old_parents={tuple(previous['folder']),tuple(previous['objects'])}
        def syncing(fd):
            result=real_fsync(fd);info=os.fstat(fd)
            if (info.st_dev,info.st_ino)==store.identity:events.append('store_fsync')
            return result
        def unlinking(path,**kwargs):
            if kwargs.get('dir_fd') is not None:
                info=os.fstat(kwargs['dir_fd'])
                if (info.st_dev,info.st_ino) in old_parents:
                    if 'store_fsync' not in events:raise AssertionError('old unlink before store fsync')
                    events.append('old_unlink')
            return real_unlink(path,**kwargs)
        with patch('os.fsync',syncing),patch('os.unlink',unlinking):
            result=job.reconcile(retention_adopted=True,inputs_quiescent=True)
        if FAULT_STAGE=='rename_before_fsync' and 'old_unlink' not in events:raise AssertionError('old unlink missing')
        with (root/'fixture-recovery-events.json').open('x') as stream:json.dump(events,stream)
'''


def instrument(source,stage,*,recover=False):
    if stage not in ('before_publication','after_publication','during_retention','candidate_objects_removed','rename_before_fsync'):
        raise ValueError('unknown fixture-only interruption')
    needle=('        result=job.reconcile(retention_adopted=True,inputs_quiescent=True)' if recover else
            "        result=job.tick(factory,quiescent,retention_adopted=True,reserve_bytes=reserve)")
    if source.count(needle)!=1:raise ValueError('fixed job source drift; fixture patch not applied')
    return 'FAULT_STAGE='+repr(stage)+'\n'+source.replace(needle,RECOVERY if recover else FAULT)
