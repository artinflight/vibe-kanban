"""Final quiet SQL subphase over the SAME actual native writer capability."""
import os,tempfile
from pathlib import Path
from vk_nightly_sql_point import capture_SQL_point


def capture(recovery,sources,*,maximum_image_bytes,chunk_bytes,memory_floor_bytes,save,timeout_seconds=None):
    base=getattr(recovery,'original',recovery)
    if not hasattr(base,'native_SQL_client')or not callable(getattr(base,'native_SQL_guard',None)):
        raise ValueError('actual extended owned context required; do not open a second SQL writer')
    if not isinstance(sources,list)or not 1<=len(sources)<=16 or len(set(sources))!=len(sources):
        raise ValueError('exact finite canonical SQL source request required')
    records=[];recovery.check()
    for source in sources:
        folder=Path(tempfile.mkdtemp(prefix='nightly-owner-sql-',dir='/dev/shm'))
        def prepared(value):save(source,value)
        record=capture_SQL_point(source,base.native_SQL_client,allowed_sources=sources,
            guard=base.native_SQL_guard,retained_by_sha=lambda sha,size:None,ram_root=folder,
            maximum_image_bytes=maximum_image_bytes,chunk_bytes=chunk_bytes,
            timeout_seconds=timeout_seconds,on_prepared=prepared,memory_floor_bytes=memory_floor_bytes)
        recovery.check();records.append(record);save(source,dict(accepted=record));folder.rmdir()
    return records
