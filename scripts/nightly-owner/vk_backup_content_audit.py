"""Read-only, bounded audit of an existing verified reconciliation index.

Category names are measurement hints, never exclusion or cleanup authority.
No archive payload, repository content, production plan or source file is read.
"""
import argparse
import collections
import hashlib
import heapq
import json
from pathlib import Path
import resource
import sqlite3
import struct
import time


CATEGORIES = ('node_modules', 'package_caches', 'build_output_candidates', 'virtualenv_candidates',
              'git_objects', 'git_metadata', 'native_histories_logs', 'databases',
              'attachments_media', 'source_config_other')
PACK = struct.Struct('<QQI')
PLAN_BIT = 1 << 63
MAX_UNIQUE = 1_000_000


def category(raw, database=False):
    parts = Path(raw).parts;low = tuple(p.lower() for p in parts)
    if 'node_modules' in low:return 'node_modules'
    if any(p in low for p in ('.venv', 'venv', 'virtualenv')):return 'virtualenv_candidates'
    if '.git' in low:
        return 'git_objects' if 'objects' in low[low.index('.git') + 1:] else 'git_metadata'
    if database or raw.endswith(('.sqlite', '.sqlite3', '.db')) or '.sqlite.backup' in raw:return 'databases'
    if any(p in low for p in ('.npm', '.pnpm-store', '.yarn', '.cache')) or ('registry' in low and '.cargo' in low):return 'package_caches'
    if any(p in low for p in ('target', 'dist', 'build', '.next', '.turbo', '__pycache__', '.pytest_cache')):return 'build_output_candidates'
    if raw.endswith(('.jsonl', '.log')) and any(p in low for p in ('.codex', 'vibe-kanban-green-codex-home', 'sessions', 'logs')):return 'native_histories_logs'
    if any(p in low for p in ('attachments', 'uploads', 'media', 'recordings')) or Path(raw).suffix.lower() in ('.png','.jpg','.jpeg','.webp','.avif','.gif','.mp4','.mov','.wav','.mp3','.pdf'):
        return 'attachments_media'
    return 'source_config_other'


def group(raw):
    parts = Path(raw).parts
    if 'worktrees' in parts:
        at = parts.index('worktrees')
        return '/'.join(parts[1:at + 2])
    # Bound prefix summary size even for many flat files.
    return '/'.join(parts[1:5])


def included(raw, plan):
    roots = plan.get('_resolved_sources', plan['sources'])
    excluded = plan.get('_resolved_exclusions', plan.get('excluded_rebuildable_directories', []))
    def below(path, root):return path == root or path.startswith(root.rstrip('/') + '/')
    return any(below(raw, p) for p in roots) and not any(below(raw, p) for p in excluded)


def summarize(rows, plan, *, current=False, checkpoint=None, max_unique=MAX_UNIQUE):
    stats = {c:collections.Counter() for c in CATEGORIES};objects = {};inodes = {}
    prefixes = collections.defaultdict(collections.Counter);top = [];count = 0
    kinds = collections.Counter();unknown_hash = 0
    for raw, meta_json, checksum, extra in rows:
        meta = json.loads(meta_json);count += 1;kinds[meta['kind']] += 1
        if count % 25000 == 0 and checkpoint:checkpoint({'rows':count,'categories':{k:dict(v) for k,v in stats.items()}})
        if meta['kind'] != 'f':continue
        size = meta['size']
        if type(size) is not int or size < 0:raise ValueError('invalid indexed logical size')
        cat = category(raw, bool(extra[1]) if current else False);index = CATEGORIES.index(cat)
        yes = included(raw, plan);row = stats[cat]
        row['file_paths'] += 1;row['logical_path_bytes'] += size
        if yes:row['nightly_plan_logical_path_bytes'] += size;row['nightly_plan_file_paths'] += 1
        hardlink = False
        if current:
            gen = json.loads(extra[0]);key = struct.pack('<QQ', gen[0], gen[1])
            if key not in inodes:
                if len(inodes) >= max_unique:raise ValueError('explicit inode cardinality bound exceeded')
                inodes[key] = size
                row['inode_unique_bytes_at_first_path'] += size
        else:
            hardlink = bool(extra)
            if not hardlink:
                row['tar_regular_payload_bytes'] += size
                if yes:row['nightly_plan_tar_regular_payload_bytes'] += size
            else:row['tar_hardlink_paths'] += 1
        prefix = group(raw);prefixes[prefix]['logical_path_bytes'] += size;prefixes[prefix]['file_paths'] += 1
        if len(prefixes) > 50000:raise ValueError('explicit prefix cardinality bound exceeded')
        if not checksum:
            unknown_hash += size;row['bytes_without_content_hash'] += size
        else:
            key = bytes.fromhex(checksum)
            if len(key) != 32:raise ValueError('invalid verified content digest')
            bits = (1 << index) | (PLAN_BIT if yes else 0)
            if key in objects:
                before,flags,refs = PACK.unpack(objects[key])
                if before != size:raise ValueError('same digest has conflicting logical sizes')
                objects[key] = PACK.pack(size, flags | bits, refs + 1)
            else:
                if len(objects) >= max_unique:raise ValueError('explicit content cardinality bound exceeded')
                objects[key] = PACK.pack(size, bits, 1)
        item = (size, raw, cat, hardlink, checksum)
        if len(top) < 128:heapq.heappush(top,item)
        elif item[:2] > top[0][:2]:heapq.heapreplace(top,item)
    unique_total = plan_unique = 0;cross_category = 0;unique_counts = collections.Counter()
    for packed in objects.values():
        size,bits,refs = PACK.unpack(packed);unique_total += size
        if bits & PLAN_BIT:plan_unique += size
        mask = bits & ~PLAN_BIT
        if mask.bit_count() > 1:cross_category += size
        for i,cat in enumerate(CATEGORIES):
            if mask & (1 << i):
                stats[cat]['hash_unique_bytes_in_category'] += size;unique_counts[cat] += 1
    return {'rows':count,'kinds':dict(kinds),'categories':{k:dict(v) for k,v in stats.items()},
            'hash_unique_objects':len(objects),'hash_unique_bytes':unique_total,'nightly_plan_hash_unique_bytes':plan_unique,
            'cross_category_shared_unique_bytes':cross_category,'bytes_without_content_hash':unknown_hash,
            'hash_dedup_complete':unknown_hash == 0,'source_inode_unique_bytes':sum(inodes.values()) if current else None,
            'source_inode_unique_files':len(inodes) if current else None,
            'top_paths':[{'bytes':n,'path':p,'category':c,'tar_hardlink':h,'sha256':sha} for n,p,c,h,sha in sorted(top,reverse=True)],
            'top_groups':[{'path':p,**dict(v)} for p,v in sorted(prefixes.items(),key=lambda x:x[1]['logical_path_bytes'],reverse=True)[:80]],
            'compressed_category_bytes':None,'allocated_category_bytes':None,
            'limits':'unique hashes/inodes <=%d; prefix groups <=50000; top paths128; SQLite cache8MiB; no payload reads'%max_unique}


def audit(index, plan, *, checkpoint=None):
    before = Path(index).stat();started = time.monotonic();values = {}
    with sqlite3.connect(Path(index).as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        db.execute('PRAGMA cache_size=-8192');db.execute('PRAGMA mmap_size=0');db.execute('PRAGMA query_only=ON')
        for table in ('baseline','current'):
            cols = [r[1] for r in db.execute('PRAGMA table_info('+table+')')]
            if not {'path','meta','sha'} <= set(cols):raise ValueError('unexpected verified index schema')
            sql = 'SELECT path,meta,sha,' + ('generation,db' if table == 'current' else 'hardlink') + ' FROM '+table
            def rows():
                for row in db.execute(sql):
                    yield row[0],row[1],row[2],(row[3],row[4]) if table == 'current' else row[3]
            values[table] = summarize(rows(),plan,current=table == 'current',
                checkpoint=(lambda v:checkpoint({'phase':table,**v})) if checkpoint else None)
    after = Path(index).stat()
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('verified index changed during audit')
    return {'schema':1,'index_identity':[before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns],
            'source_index_read_only':True,'archive_payload_read':False,'source_content_read':False,
            'seconds':time.monotonic()-started,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,**values}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__);p.add_argument('--index',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--owner-db',type=Path);a = p.parse_args();plan = json.loads(a.plan.read_text())
    last_guard = [0.0]
    for key,field in [('sources','_resolved_sources'),('excluded_rebuildable_directories','_resolved_exclusions')]:
        plan[field] = list(dict.fromkeys([*plan.get(key,[]),*[str(Path(x).resolve()) for x in plan.get(key,[])]]))
    def progress(value):
        if time.monotonic()-last_guard[0] > 10:
            last_guard[0] = time.monotonic()
            mem = {k:int(v.split()[0])*1024 for k,v in (x.split(':',1) for x in Path('/proc/meminfo').read_text().splitlines()) if k in ('MemAvailable','SwapFree')}
            if mem['MemAvailable'] < 5*1024**3//2 or mem['SwapFree'] < 512*1024**2:raise RuntimeError('host resource floor; own audit stopped')
            if a.owner_db:
                with sqlite3.connect(a.owner_db.as_uri()+'?mode=ro',uri=True,timeout=2) as owners:
                    count = owners.execute("SELECT count(*) FROM execution_processes WHERE status='running' AND dropped=0 AND run_reason='codingagent'").fetchone()[0]
                if count > 7:raise RuntimeError('coding admission limit; own audit stopped')
            value['host_memory'] = mem
        temporary = a.output.with_suffix('.progress.next');temporary.write_text(json.dumps(value));temporary.replace(a.output.with_suffix('.progress.json'))
    progress({'phase':'baseline','rows':0})
    value = audit(a.index,plan,checkpoint=progress)
    cg = Path('/sys/fs/cgroup') / next(x.split(':',2)[2].lstrip('/') for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0:'))
    value['scope_metrics_before_exit']={name:(cg/name).read_text().strip() for name in ('memory.current','memory.peak','memory.swap.current','memory.events','memory.pressure')}
    with a.output.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps({'receipt':str(a.output),'seconds':value['seconds'],'peak_rss_bytes':value['peak_rss_bytes'],'rows':{k:value[k]['rows'] for k in ('baseline','current')}}))
