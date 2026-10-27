"""Bounded stderr draining and first-error-preserving owned SSH cleanup."""
import threading
import json
import sys


class Diagnostics:
    def __init__(self,pipe,maximum_bytes=65536):
        self.pipe=pipe;self.maximum_bytes=maximum_bytes;self.tail=b''
        self.lock=threading.Lock();self.done=threading.Event()
        self.thread=threading.Thread(target=self._read,daemon=True);self.thread.start()

    def _read(self):
        try:
            while True:
                raw=self.pipe.read1(4096)
                if not raw:break
                with self.lock:self.tail=(self.tail+raw)[-self.maximum_bytes:]
        except (OSError,ValueError) as error:
            with self.lock:self.tail=(self.tail+str(error).encode())[-self.maximum_bytes:]
        finally:self.done.set()

    def text(self):
        with self.lock:return self.tail.decode(errors='replace')


def finish(process,*,original=None,diagnostics=None,timeout=60):
    """Never replace a producer failure with a secondary close/BrokenPipe.

    We do not kill any worker. A wait timeout remains explicit; an inherited
    writer lease stays with the actual SSH child until that child terminates.
    """
    faults=[];code=None
    for pipe in (process.stdin,process.stdout):
        if pipe is None or pipe.closed:continue
        try:pipe.close()
        except (OSError,ValueError) as error:faults.append(error)
    try:code=process.wait(timeout=timeout)
    except BaseException as error:faults.append(error)
    if diagnostics is not None:
        diagnostics.thread.join(timeout=.5)
        detail=diagnostics.text()
        # Only the bounded native health telemetry, never arbitrary stderr or
        # SQL parameters. The last successful observation carries cumulative
        # query count/time, including final acceptance, for the owned unit log.
        health=[]
        for line in detail.splitlines():
            try:value=json.loads(line)
            except (ValueError,TypeError):continue
            if isinstance(value,dict) and value.get('event')=='native-health-observation':health.append(value)
        if health:print(json.dumps(dict(event='native-health-session-summary',last_observation=health[-1])),file=sys.stderr,flush=True)
        if diagnostics.done.is_set() and not process.stderr.closed:process.stderr.close()
    else:
        detail=''
        if code is not None and process.stderr is not None:
            try:detail=process.stderr.read(65536).decode(errors='replace')
            except (OSError,ValueError) as error:faults.append(error)
            finally:
                if not process.stderr.closed:process.stderr.close()
    target=original
    if target is None and (faults or code):
        target=faults.pop(0) if faults else RuntimeError('native B child exited '+str(code))
    if target is not None:
        for error in faults:
            if hasattr(target,'add_note'):target.add_note('secondary transport cleanup: '+repr(error))
        if detail and hasattr(target,'add_note'):target.add_note('native B stderr tail: '+detail)
        if original is None:raise target
    return code
