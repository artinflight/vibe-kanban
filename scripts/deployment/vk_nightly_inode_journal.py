"""Opt-in full inode observation, including writes through external hardlinks.

One inotify watch per directory/regular/symlink inode; aliases share a watch.
No file content is read, writers are never fenced and kernel limits are never
changed. A failed watch aborts enrollment, preserving the earlier observer.
"""
import bisect
from collections import deque, OrderedDict
import ctypes
import errno
import os
from pathlib import Path
import select
import stat
import struct
import threading

from vk_change_journal import MASK,OVERFLOW,UNMOUNT,IGNORED,ISDIR
from vk_nightly_move_journal import Journal as DirectoryJournal,under


class WatchAdmissionError(RuntimeError):pass


def require_full_coverage(report):
    """Operational adoption gate; historical directory reports stay readable.

    A ready namespace observer cannot establish file-content change coverage.
    The caller still authenticates owner, epoch, scope and the actual barrier.
    """
    barrier=report.get('barrier')
    if (report.get('coverage_model')!='all-selected-inodes-v1'
            or report.get('ready') is not True or report.get('errors') or report.get('terminal')
            or not isinstance(barrier,dict) or barrier.get('kernel_drain_completed') is not True
            or not isinstance(report.get('instance'),str) or not report['instance']
            or type(report.get('sequence')) is not int or report['sequence']<0
            or barrier.get('instance')!=report['instance'] or type(barrier.get('durable_sequence')) is not int
            or barrier['durable_sequence']!=report['sequence']):
        raise ValueError('complete inode change coverage and actual healthy barrier required')


def check_watch_demand(required,maximum):
    """Reject a known insufficient kernel limit; never raise or change it.

    Passing this necessary condition is not admission: other UID watches and
    subsequent growth still require real successful enrollment and handover.
    """
    if type(required) is not int or required<1 or type(maximum) is not int or maximum<1:
        raise ValueError('positive measured watch demand and live kernel limit required')
    if required>maximum:
        raise WatchAdmissionError('retained scope needs at least '+str(required)+
                                  ' inode watches; kernel per-user maximum is '+str(maximum))


class Journal(DirectoryJournal):
    coverage_model='all-selected-inodes-v1'
    def __init__(self,plan,*,maximum_raw_bytes=16*1024**2):
        if type(maximum_raw_bytes) is not int or not 4096<=maximum_raw_bytes<=16*1024**2:
            raise ValueError('finite inode event buffer required')
        super().__init__(plan)
        self.file_aliases={};self.path_watches={};self.expected_ignored=set()
        self.sorted_paths=[];self.paths_dirty=True
        self.inode_kinds={};self.root_aliases_enrolled=False
        self.kind_counts={stat.S_IFREG:0,stat.S_IFLNK:0}
        self.pending_file_enrollments=set()
        # Concurrent fsnotify callbacks can enqueue a final inode event after
        # rm_watch's IN_IGNORED. Attribute only known retirements, never exempt
        # arbitrary unknown WDs. Recheck the current name before readiness.
        self.retired_files=OrderedDict();self.maximum_retired_paths=8192
        self.retired_path_count=0;self.late_retired_events=0
        self.lib.inotify_rm_watch.argtypes=[ctypes.c_int,ctypes.c_int]
        self.lib.inotify_rm_watch.restype=ctypes.c_int
        # Only ordered kernel bytes enter this finite FIFO. The reader never
        # takes the metadata/enrollment lock or performs path lookups.
        self.maximum_raw_bytes=maximum_raw_bytes
        self.raw_chunks=deque();self.raw_bytes=0;self.raw_peak_bytes=0
        self.raw_lock=threading.Lock();self.raw_stop=threading.Event()
        self.raw_failure=None;self.raw_closed=False
        self.raw_reader=threading.Thread(target=self.kernel_reader,daemon=True)
        self.raw_reader.start()

    def fill_raw_locked(self):
        while self.maximum_raw_bytes-self.raw_bytes>=4096 and not self.raw_stop.is_set():
            try:data=os.read(self.fd,min(1024**2,self.maximum_raw_bytes-self.raw_bytes))
            except BlockingIOError:return
            except OSError as error:
                self.raw_failure=repr(error);self.raw_stop.set();return
            if not data:
                self.raw_failure='unexpected empty inotify read';self.raw_stop.set();return
            self.raw_chunks.append(data);self.raw_bytes+=len(data)
            self.raw_peak_bytes=max(self.raw_peak_bytes,self.raw_bytes)

    def kernel_reader(self):
        try:
            while not self.raw_stop.is_set():
                select.select([self.fd],[],[],.05)
                with self.raw_lock:
                    self.fill_raw_locked()
                    full=self.maximum_raw_bytes-self.raw_bytes<4096
                if full:self.raw_stop.wait(.01)
        except BaseException as error:
            with self.raw_lock:self.raw_failure=repr(error)
            self.raw_stop.set()

    def read(self):
        with self.lock:
            if self.raw_closed:return
            while True:
                with self.raw_lock:
                    self.fill_raw_locked()
                    if self.raw_failure:
                        self.errors.append({'kernel_reader_failed':self.raw_failure})
                        raise RuntimeError(self.raw_failure)
                    chunks=list(self.raw_chunks);self.raw_chunks.clear()
                if not chunks:break
                for data in chunks:
                    offset=0
                    while offset<len(data):
                        wd,mask,cookie,size=struct.unpack_from('iIII',data,offset)
                        name=os.fsdecode(data[offset+16:offset+16+size].split(b'\0')[0])
                        self.event(wd,mask,name,cookie);offset+=16+size
                    # Active processing bytes still count: extracting the
                    # FIFO cannot double its admitted memory.
                    with self.raw_lock:self.raw_bytes-=len(data)
            self.expire()
            # A subscribed parent protects namespace transitions while a
            # replaced child is enrolled again. Keep its point dirty/unready
            # until the actual current inode has passed the final identity check.
            for path in list(sorted(self.pending_file_enrollments))[:64]:
                self.pending_file_enrollments.remove(path);self.enroll_file(path)

    def close(self):
        self.raw_stop.set();self.raw_reader.join(timeout=2)
        if self.raw_reader.is_alive():raise RuntimeError('owned kernel reader did not close; preserve FD')
        with self.lock:
            if self.raw_closed:return
            self.raw_closed=True;self.ready=False
            super().close()

    def protected(self,path):
        return super().protected(path) or any(under(root,path) for root in self.plan['sources'])

    def excluded_path(self,path):
        try:return super().excluded_path(path)
        except OSError as error:
            if error.errno not in (errno.EINVAL,errno.ENOENT,errno.ENOTDIR):raise
            # resolve() may lstat a link replaced before readlink(). Never
            # omit that name; normal no-follow enrollment/identity checks run.
            return False

    def retain_retired(self,wd,paths):
        paths=set(paths)
        if not paths:return
        if len(paths)>self.maximum_retired_paths:
            raise WatchAdmissionError('bounded retired inode attribution exceeded')
        old=self.retired_files.setdefault(wd,set())
        self.retired_path_count+=len(paths-old);old.update(paths)
        self.retired_files.move_to_end(wd)
        while self.retired_path_count>self.maximum_retired_paths:
            _,removed=self.retired_files.popitem(last=False)
            self.retired_path_count-=len(removed)

    def late_retired(self,wd,mask):
        paths=self.retired_files.get(wd)
        if not paths or mask&(OVERFLOW|UNMOUNT|IGNORED):return False
        # Root loss or loss of the covering parent still fails closed.
        if any(self.protected(p) or str(Path(p).parent) not in self.watches.values() for p in paths):
            return False
        if len(self.pending_file_enrollments|paths)>10000:
            raise WatchAdmissionError('bounded pending inode enrollment exceeded')
        for path in paths:self.changed_name(path,mask)
        self.pending_file_enrollments.update(paths);self.late_retired_events+=1
        return True

    def changed_name(self,path,mask):
        self.seq+=1;self.changed[path]=self.seq;bits=self.events.setdefault(path,{})
        for bit in range(32):
            flag=1<<bit
            if mask&flag:bits[flag]=self.seq

    def forget(self,path):
        wd=self.path_watches.pop(path,None)
        if wd is None:return
        self.paths_dirty=True;self.file_aliases[wd].discard(path)
        if not self.file_aliases[wd]:
            self.retain_retired(wd,[path])
            self.expected_ignored.add(wd)
            if self.lib.inotify_rm_watch(self.fd,wd)<0 and ctypes.get_errno()!=errno.EINVAL:
                self.errors.append({'inode_watch_remove_failed':path,'errno':ctypes.get_errno()})

    def enroll_file(self,path):
        fd=None
        try:
            fd=os.open(path,os.O_PATH|os.O_NOFOLLOW|os.O_CLOEXEC)
            before=os.fstat(fd)
            if not (stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode)):return
            # Own O_PATH FD pins the actual inode across rename/replacement.
            # Do not use DONT_FOLLOW on this deliberately controlled FD link.
            # A procfs magic FD link resolves directly to the pinned inode,
            # including an O_PATH|O_NOFOLLOW symlink inode (not its target).
            # Using the mutable source name here would allow a symlink ABA.
            watch_path='/proc/self/fd/'+str(fd)
            wd=self.lib.inotify_add_watch(self.fd,os.fsencode(watch_path),MASK)
            if wd<0:
                code=ctypes.get_errno()
                if code==errno.ENOENT:raise FileNotFoundError(code,os.strerror(code),path)
                self.errors.append({'watch_failed':path,'errno':code})
                raise WatchAdmissionError('source inode watch refused: '+path+': '+os.strerror(code))
            if wd in self.retired_files:
                raise WatchAdmissionError('retired kernel watch descriptor reused; reconcile source epoch')
            prior=self.path_watches.get(path)
            if prior is not None and prior!=wd:self.forget(path)
            self.file_aliases.setdefault(wd,set()).add(path);self.path_watches[path]=wd;self.paths_dirty=True
            after=os.lstat(path)
            if (after.st_dev,after.st_ino)!=(before.st_dev,before.st_ino):
                self.forget(path)
                if str(Path(path).parent) in self.watches.values():
                    if len(self.pending_file_enrollments)>=10000:
                        raise WatchAdmissionError('bounded pending inode enrollment exceeded')
                    self.pending_file_enrollments.add(path);self.changed_name(path,0x100)
                    return
                self.errors.append({'inode_enrollment_replaced':path})
                raise WatchAdmissionError('source replaced during inode enrollment without subscribed parent')
            kind=stat.S_IFMT(before.st_mode)
            if wd not in self.inode_kinds:self.kind_counts[kind]+=1
            elif self.inode_kinds[wd]!=kind:raise WatchAdmissionError('kernel inode watch type changed')
            self.inode_kinds[wd]=kind
        except FileNotFoundError:
            if self.protected(path):
                self.errors.append({'initial_required_root_absent':path})
                raise WatchAdmissionError('required file root absent')
            # The subscribed parent covers recreation; the named tombstone is
            # replayed before acceptance. No nonexistent inode is certified.
            self.forget(path);self.changed_name(path,0x200)
        finally:
            if fd is not None:os.close(fd)

    def tree(self,root):
        if not self.root_aliases_enrolled:
            for alias in self.plan['sources']:
                if os.path.islink(alias):self.enroll_file(alias)
            self.root_aliases_enrolled=True
        pending=[str(root)]
        while pending:
            path=pending.pop()
            with self.lock:
                if self.excluded_path(path):continue
                directory_fd=None
                try:
                    directory_fd=os.open(path,os.O_PATH|os.O_NOFOLLOW|os.O_CLOEXEC)
                    info=os.fstat(directory_fd)
                    if stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):self.enroll_file(path);continue
                    if not stat.S_ISDIR(info.st_mode):
                        self.errors.append({'enrollment_directory_became_link':path});continue
                    # The owned O_PATH FD pins the actual directory across
                    # rename/deletion; do not re-stat a vanished pathname after
                    # registering its watch. Parent events cover its successor.
                    wd=self.lib.inotify_add_watch(self.fd,os.fsencode('/proc/self/fd/'+str(directory_fd)),MASK|0x01000000)
                    if wd<0:
                        code=ctypes.get_errno()
                        if code==errno.ENOENT:raise FileNotFoundError(code,os.strerror(code),path)
                        self.errors.append({'watch_failed':path,'errno':code})
                        raise WatchAdmissionError('directory watch refused: '+path+': '+os.strerror(code))
                    self.watches.bind(wd,path,(info.st_dev,info.st_ino))
                    with os.scandir(path) as entries:
                        for entry in entries:
                            if self.excluded_path(entry.path):continue
                            if entry.is_dir(follow_symlinks=False):pending.append(entry.path)
                            elif entry.is_file(follow_symlinks=False) or entry.is_symlink():self.enroll_file(entry.path)
                except FileNotFoundError:
                    if self.protected(path):
                        self.errors.append({'initial_required_root_absent':path});raise WatchAdmissionError('required directory absent')
                    self.changed_name(path,0x200|ISDIR)
                except OSError as error:
                    self.errors.append({'watch_enrollment_failed':path,'errno':error.errno})
                    raise WatchAdmissionError('inode enrollment access/resource failure') from error
                finally:
                    if directory_fd is not None:os.close(directory_fd)

    def remap(self,old,new):
        count=super().remap(old,new)
        if self.paths_dirty:self.sorted_paths=sorted(self.path_watches);self.paths_dirty=False
        first=bisect.bisect_left(self.sorted_paths,old+'/')
        moved=[]
        for path in self.sorted_paths[first:]:
            if not under(path,old):break
            moved.append(path)
        for path in moved:
            wd=self.path_watches.pop(path);target=new+path[len(old):]
            self.file_aliases[wd].remove(path);self.file_aliases[wd].add(target);self.path_watches[target]=wd
        self.paths_dirty=bool(moved) or self.paths_dirty
        return count+len(moved)

    def event(self,wd,mask,name,cookie=0):
        with self.lock:
            if wd in self.file_aliases and not mask&(OVERFLOW|UNMOUNT):
                aliases=list(self.file_aliases[wd])
                if not aliases and self.late_retired(wd,mask):return
                if mask&0x400:
                    self.expected_ignored.add(wd)
                    for path in aliases:
                        if self.protected(path):self.errors.append({'protected_root_deleted':path})
                if mask&IGNORED:
                    if wd not in self.expected_ignored:self.errors.append({'inode_watch_removed':aliases})
                    elif aliases:self.retain_retired(wd,aliases)
                    self.expected_ignored.discard(wd)
                    for path in aliases:
                        # A queued IGNORED for the replaced old inode must not
                        # erase a new inode's already-enrolled name mapping.
                        if self.path_watches.get(path)==wd:self.path_watches.pop(path,None)
                    self.file_aliases.pop(wd,None);kind=self.inode_kinds.pop(wd,None)
                    if kind is not None:self.kind_counts[kind]-=1
                    self.paths_dirty=True
                for path in aliases:self.changed_name(path,mask)
                return
            if self.late_retired(wd,mask):return
            parent=self.watches.get(wd);path=str(Path(parent)/name) if parent and name else parent
            super().event(wd,mask,name,cookie)
            if path and not self.excluded_path(path):
                if mask&(0x40|0x200) and not mask&ISDIR:self.forget(path)
                if mask&(0x80|0x100) and not mask&ISDIR and os.path.lexists(path):self.enroll_file(path)

    def report(self,since=0):
        value=super().report(since)
        value.update(coverage_model=self.coverage_model,
                     pending_file_enrollments=len(self.pending_file_enrollments),
                     ready=value['ready'] and not self.pending_file_enrollments,
                     directory_watches=len(self.watches),regular_inode_watches=self.kind_counts[stat.S_IFREG],
                     symlink_inode_watches=self.kind_counts[stat.S_IFLNK],
                     regular_alias_paths=len(self.path_watches),watches=len(self.watches)+len(self.file_aliases),
                     retained_retired_paths=self.retired_path_count,late_retired_inode_events=self.late_retired_events,
                     kernel_raw_buffer_peak_bytes=self.raw_peak_bytes,kernel_raw_buffer_maximum_bytes=self.maximum_raw_bytes)
        return value
