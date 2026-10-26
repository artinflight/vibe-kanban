"""Cookie/inode-qualified directory moves for the Nightly source observer.

Existing kernel watches survive an in-scope rename. Relabel them only with a
real source-parent move cookie and either its destination event or the same
kernel watch/inode found while enrolling a newly created destination parent.
Pending pairs are unready; unmatched moves, root moves and overflow stay faults.
This does not repair an older observer epoch or erase any existing error.
"""
from collections import deque
import os
from pathlib import Path
import stat
import struct
import time

from vk_change_journal import Journal as OriginalJournal, OVERFLOW, UNMOUNT, ISDIR, MASK

FROM, TO, SELF = 0x40, 0x80, 0x800
PAIR_SECONDS = 1.0


def under(path, root):
    return path == root or path.startswith(root.rstrip('/') + '/')


class WatchMap(dict):
    def __init__(self, owner):
        super().__init__()
        self.owner, self.identities = owner, {}

    def __setitem__(self, wd, path):
        old = self.get(wd)
        try:
            info = os.stat(path, follow_symlinks=False)
        except OSError as error:
            self.owner.errors.append({'watch_reenrollment_stat_failed': path, 'errno': error.errno})
            return super().__setitem__(wd, path)
        identity = (info.st_dev, info.st_ino)
        if old is not None and old != path and stat.S_ISDIR(info.st_mode):
            if self.identities.get(wd) != identity:
                self.owner.errors.append({'watch_identity_rebound': wd})
            elif not os.path.lexists(old):
                self.owner.registered_move(wd, old, path, identity)
        self.identities[wd] = identity
        super().__setitem__(wd, path)


class Journal(OriginalJournal):
    def __init__(self, plan):
        super().__init__(plan)
        self.pending_moves, self.pending_self, self.allowed_self = {}, {}, {}
        self.enrolled_moves, self.rename_pairs = {}, deque(maxlen=128)
        self.rename_count = 0
        self.watches = WatchMap(self)

    def tree(self, root):
        # Subscribe BEFORE enumerating each directory. os.walk yields after
        # listing it, which otherwise leaves an enrollment race for new child
        # directories. Their parent is now subscribed throughout enumeration.
        pending = [str(root)]
        while pending:
            directory = pending.pop()
            with self.lock:
                if self.excluded_path(directory):
                    continue
                try:
                    info = os.lstat(directory)
                    if stat.S_ISLNK(info.st_mode):
                        self.errors.append({'enrollment_directory_became_link': directory})
                        continue
                    is_directory = stat.S_ISDIR(info.st_mode)
                    mask = MASK | 0x02000000 | (0x01000000 if is_directory else 0)
                    wd = self.lib.inotify_add_watch(self.fd, os.fsencode(directory), mask)
                    if wd < 0:
                        import ctypes
                        self.errors.append({'watch_failed': directory, 'errno': ctypes.get_errno()})
                        continue
                    self.watches[wd] = directory
                    if is_directory:
                        with os.scandir(directory) as entries:
                            pending.extend(entry.path for entry in entries
                                           if entry.is_dir(follow_symlinks=False)
                                           and not self.excluded_path(entry.path))
                except OSError as error:
                    self.errors.append({'watch_enrollment_failed': directory, 'errno': error.errno})

    def protected(self, old):
        return any(under(root, old) for root in self.roots)

    def remap(self, old, new):
        count, roots = 0, []
        for wd, previous in list(self.watches.items()):
            if under(previous, old):
                if previous == old:
                    roots.append(wd)
                dict.__setitem__(self.watches, wd, new + previous[len(old):])
                count += 1
        for wd in roots:
            if wd in self.pending_self:
                del self.pending_self[wd]
            else:
                self.allowed_self[wd] = time.monotonic()
        return count

    def record(self, old, new, cookie, count, qualification):
        self.rename_count += 1
        self.rename_pairs.append(dict(cookie=cookie, source=old, destination=new,
                                      retained_watches=count, qualification=qualification))

    def registered_move(self, wd, old, new, identity):
        if self.protected(old):
            self.errors.append({'protected_root_reenrolled_after_move': old, 'to': new})
            return
        if (not any(under(new, root) for root in self.roots)
                or str(Path(old).parent) not in self.watches.values()):
            self.errors.append({'unqualified_watch_reenrollment': old, 'to': new})
            return
        count = self.remap(old, new)
        for cookie, item in list(self.pending_moves.items()):
            if item['old'] == old:
                del self.pending_moves[cookie]
                self.record(old, new, cookie, count, 'same kernel watch/inode plus source-parent cookie')
                break
        else:
            self.enrolled_moves[old] = dict(to=new, watch=wd, identity=identity, count=count, at=time.monotonic())

    def expire(self):
        now = time.monotonic()
        for cookie, item in list(self.pending_moves.items()):
            if now - item['at'] > PAIR_SECONDS:
                self.errors.append({'unmatched_directory_move': item['old'], 'cookie': cookie})
                del self.pending_moves[cookie]
        for wd, item in list(self.pending_self.items()):
            if now - item['at'] > PAIR_SECONDS:
                self.errors.append({'directory_moved': item['path'], 'unpaired_watch': wd})
                del self.pending_self[wd]
        for old, item in list(self.enrolled_moves.items()):
            if now - item['at'] > PAIR_SECONDS:
                self.errors.append({'unacknowledged_watch_reenrollment': old, 'to': item['to']})
                del self.enrolled_moves[old]
        for wd, at in list(self.allowed_self.items()):
            if now - at > PAIR_SECONDS:
                del self.allowed_self[wd]

    def event(self, wd, mask, name, cookie=0):
        with self.lock:
            parent = self.watches.get(wd)
            if parent is None or mask & (OVERFLOW | UNMOUNT):
                return super().event(wd, mask, name)
            path = str(Path(parent) / name) if name else parent
            if self.excluded_path(path):
                return super().event(wd, mask, name)
            paired = False
            if mask & FROM and mask & ISDIR:
                if not cookie:
                    self.errors.append({'directory_move_cookie_missing': path})
                elif path in self.enrolled_moves:
                    entry = self.enrolled_moves.pop(path)
                    self.record(path, entry['to'], cookie, entry['count'],
                                'same kernel watch/inode plus source-parent cookie')
                elif cookie in self.pending_moves:
                    self.errors.append({'duplicate_directory_move_cookie': cookie})
                else:
                    self.pending_moves[cookie] = dict(old=path, parent=parent, at=time.monotonic())
            if mask & TO and mask & ISDIR and cookie in self.pending_moves:
                item = self.pending_moves.pop(cookie)
                old = item['old']
                if self.protected(old):
                    self.errors.append({'protected_root_moved': old, 'to': path})
                elif (item['parent'] not in self.watches.values()
                      or not any(under(path, root) for root in self.roots)):
                    self.errors.append({'unqualified_directory_move_pair': old, 'to': path})
                else:
                    count = self.remap(old, path)
                    self.record(old, path, cookie, count, 'both watched parents and actual cookie')
                    paired = count > 0
            if mask & SELF:
                if wd in self.allowed_self:
                    del self.allowed_self[wd]
                else:
                    self.pending_self[wd] = dict(path=path, at=time.monotonic())
                super().event(wd, mask & ~SELF, name)
                self.events.setdefault(path, {})[SELF] = self.seq
                return
            if paired:
                # All retained watches still cover their inodes; no re-walk.
                super().event(wd, mask & ~TO, name)
                self.events.setdefault(path, {})[TO] = self.seq
            else:
                super().event(wd, mask, name)

    def read(self):
        with self.lock:
            while True:
                try:
                    data = os.read(self.fd, 1024 * 1024)
                except BlockingIOError:
                    break
                offset = 0
                while offset < len(data):
                    wd, mask, cookie, size = struct.unpack_from('iIII', data, offset)
                    name = os.fsdecode(data[offset + 16:offset + 16 + size].split(b'\0')[0])
                    self.event(wd, mask, name, cookie)
                    offset += 16 + size
            self.expire()

    def report(self, since=0):
        with self.lock:
            value = super().report(since)
            pending = len(self.pending_moves) + len(self.pending_self) + len(self.enrolled_moves)
            value.update(pending_directory_moves=pending, rename_pairs=list(self.rename_pairs),
                         rename_count=self.rename_count,
                         ready=value['ready'] and not pending)
            return value
