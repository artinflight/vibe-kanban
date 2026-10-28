"""Bounded stderr draining and first-error-preserving owned SSH cleanup."""
import threading
import json
import sys
import os
import re
import math


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


def Desktop_unavailable(process,code,detail):
    """Only positive owned-SSH network evidence, never a missing observation.

    Authentication/host-key/native fault/STOP errors and mixed/unknown stderr
    are deliberately NOT retryable. The next attempt uses the same pinned
    route and must regain actual ownership, identity and health admission.
    """
    argv=getattr(process,'args',None)
    if (code!=255 or not isinstance(argv,(list,tuple)) or not argv
            or not isinstance(argv[0],str) or os.path.basename(argv[0])!='ssh'):
        return False
    patterns=(
        r'ssh: connect to host \S+ port [0-9]+: (?:Connection timed out|Connection refused|No route to host|Network is unreachable|Connection reset by peer)',
        r'client_loop: send disconnect: (?:Broken pipe|Connection reset by peer)',
        r'Timeout, server \S+ not responding\.',
        r'Connection to \S+ closed by remote host\.',
        r'kex_exchange_identification: read: Connection reset by peer',
    )
    found=False
    for line in detail.splitlines():
        line=line.strip()
        if not line:continue
        if any(re.fullmatch(p,line) for p in patterns):found=True;continue
        try:value=json.loads(line)
        except (ValueError,TypeError):return False
        # Healthy native telemetry can precede a real mid-stream network loss.
        # Missing/faulted observations or any unknown record remain failures.
        if (not isinstance(value,dict) or set(value)!={'event','query_seconds','health_observations','health_query_seconds','reported_drive_fault','UTC'}
                or value.get('event')!='native-health-observation' or value.get('reported_drive_fault') is not False
                or type(value['health_observations']) is not int or value['health_observations']<1
                or not isinstance(value['UTC'],str)
                or any(type(value[k]) not in (int,float) or not math.isfinite(value[k]) or value[k]<0
                       for k in ('query_seconds','health_query_seconds'))):return False
    return found


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
        symptom=(isinstance(target,(EOFError,ConnectionError))
            or (type(target) is RuntimeError and str(target) in
                ('native B readiness stream ended','native B child exited 255'))
            or (type(target) is ValueError and str(target) in
                ('native B control readiness unavailable',
                 'normal composed-consumer terminal result missing; preserve all data'))
            or (type(target) is TimeoutError and str(target) in
                ('native B readiness','native B control readiness')))
        if symptom and Desktop_unavailable(process,code,detail):
            # Preserve the original error and all cleanup notes. The trusted
            # top-level controller maps this evidence to its finite retry code.
            target.nightly_Desktop_transport_unavailable=True
            target.nightly_transport_exit_code=code
        for error in faults:
            if hasattr(target,'add_note'):target.add_note('secondary transport cleanup: '+repr(error))
        if detail and hasattr(target,'add_note'):target.add_note('native B stderr tail: '+detail)
        if original is None:raise target
    return code
