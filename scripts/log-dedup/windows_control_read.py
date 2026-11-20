"""Current Windows control reads compatible with atomic publication.
Same identity, ACL and path; no cached PASS or alternate file. Only native
sharing/lock conflicts use MM's existing four-read/80ms patience.
"""
import os
import stat
import time
MAX_CONTROL_BYTES = 262144

def _version(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)

def _read_once(path):
    import ctypes
    import ctypes.wintypes as wt
    import msvcrt
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
    api.CreateFileW.restype = wt.HANDLE
    api.CloseHandle.argtypes = [wt.HANDLE]
    api.CloseHandle.restype = wt.BOOL
    # GENERIC_READ, SHARE_READ|WRITE|DELETE, OPEN_EXISTING, OPEN_REPARSE_POINT.
    handle = api.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x00200000, None)
    if handle == wt.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        api.CloseHandle(handle)
        raise
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or getattr(before, 'st_file_attributes', 0) & 0x400
                or before.st_size > MAX_CONTROL_BYTES):
            raise ValueError('Unsafe or oversized current Windows control')
        raw = stream.read(MAX_CONTROL_BYTES + 1)
        after = os.fstat(stream.fileno())
        current = os.stat(path, follow_symlinks=False)
        if (len(raw) > MAX_CONTROL_BYTES or len(raw) != before.st_size
                or _version(before) != _version(after) or _version(after) != _version(current)):
            raise ValueError('Current Windows control changed during read')
        return raw

def read_current(path, *, read_once=_read_once, sleep=time.sleep, check_deadline=lambda: None):
    for attempt in range(4):
        check_deadline()
        try:
            raw = read_once(path)
        except OSError as error:
            # WinError5 is access denial. errno13 alone is ambiguous.
            if getattr(error, 'winerror', None) not in (32, 33) or attempt == 3:
                raise
            sleep(0.08)
            continue
        check_deadline()
        return raw
