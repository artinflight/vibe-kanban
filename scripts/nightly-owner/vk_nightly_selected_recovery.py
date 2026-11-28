"""Nightly-owned PROTOCOL1 selected-original recall over NORMAL Desktop B.

This is a finite read consumer, not another capture or calendar. Normal global
controller/body ownership, native B identity/STOP/health and capacity admission,
actual SQLite SHARED read transaction and Linux provider leases remain held.
Exact externally requested versions may qualify without whole-set acceptance.
"""
import base64
from contextlib import contextmanager, ExitStack
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
import types

# Support source-pinned dynamic import by the existing deployment controller.
# The exact owned closure is authenticated again before opening a B context.
_SOURCE_FOLDER = str(Path(__file__).resolve().parent)
if _SOURCE_FOLDER not in sys.path:sys.path.insert(0, _SOURCE_FOLDER)

from vk_nightly_capture_adapter import mcp_lease
from vk_nightly_current_map import decode_member
from vk_nightly_desktop_controls import DesktopControls
from vk_nightly_desktop_objects import DesktopObjects, ssh_command
from vk_nightly_remote_consumer import probe_placement
from vk_nightly_selected_reader import qualify, PROTOCOL, MAX_FRAME
from vk_nightly_transport_diagnostics import Diagnostics, finish
from vk_nightly_typed_worker import source_closure
from vk_typed_recovery import checksum


LOADER = r'''
import hashlib,importlib.abc,importlib.util,json,re,sys
raw=sys.stdin.buffer.readline(1048577)
if len(raw)>1048576 or not raw.endswith(b'\n'):raise ValueError('bounded source bootstrap required')
value=json.loads(raw);sources=value['sources']
if not isinstance(sources,dict) or not 1<=len(sources)<=64:raise ValueError('exact selected-reader source closure required')
for name,row in sources.items():
 if not re.fullmatch('vk_[a-z0-9_]+',name) or hashlib.sha256(row['source'].encode()).hexdigest()!=row['sha256']:raise ValueError('selected-reader source binding differs')
class Loader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in sources:return importlib.util.spec_from_loader(fullname,self)
  if fullname.startswith('vk_'):raise ImportError('undeclared selected-reader dependency')
 def create_module(self,spec):return None
 def exec_module(self,module):
  module.__file__='<pinned-selected-reader>/'+module.__name__+'.py'
  exec(compile(sources[module.__name__]['source'],module.__file__,'exec'),module.__dict__)
sys.meta_path.insert(0,Loader());sys.argv=['vk_nightly_selected_reader',value['packet_sha256']]
import vk_nightly_selected_reader
vk_nightly_selected_reader.main()
'''


def command(controls):
    # Same existing B-backed unprivileged consumer; no install/mount/account change.
    program = 'LOADER=' + repr(LOADER) + '\n' + r'''
import subprocess,json,sys
q="Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Lxss\\*' | Where-Object DistributionName -eq 'VK-Candidate-20261009' | Select-Object DistributionName,BasePath | ConvertTo-Json -Compress"
r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',q],capture_output=True,text=True,timeout=30,check=True)
v=json.loads(r.stdout)
if not isinstance(v,dict) or v.get('DistributionName')!='VK-Candidate-20261009' or v.get('BasePath')!=r'\\?\B:\vk-backups\vk-safe-release-20261009\linux-candidate\distribution':raise ValueError('normal reader B placement differs')
raise SystemExit(subprocess.call(['wsl.exe','-d','VK-Candidate-20261009','--exec','setpriv','--reuid','1000','--regid','1000','--clear-groups','python3','-B','-u','-c',LOADER],stdin=sys.stdin.buffer,stdout=sys.stdout.buffer,stderr=sys.stderr.buffer))
'''
    return ssh_command(controls, 'python -B -u -c "import base64;exec(base64.b64decode(\''
        + base64.b64encode(program.encode()).decode() + '\'))"')


def bridge(config):
    """Load only the owner's exact existing bridge and its one local dependency."""
    loaded = {}
    original_import = __import__
    def pinned_import(name, *args, **kwargs):
        if name == 'log_dedup':return loaded[name]
        return original_import(name, *args, **kwargs)
    for name in ('log_dedup', 'recovery_stream'):
        ref = config['bridge_sources'][name]
        path = Path(ref['path'])
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref['sha256']:
            raise ValueError('pinned dedup bridge source changed')
        module = types.ModuleType('_nightly_pinned_'+name)
        module.__file__ = str(path)
        module.__dict__['__builtins__'] = dict(vars(__import__('builtins')), __import__=pinned_import)
        exec(compile(raw, str(path), 'exec'), module.__dict__)
        loaded[name] = module
    return loaded['recovery_stream'].NormalRecovery


class Reader:
    def __init__(self, process, rows, db, guard):
        self.process, self.rows, self.db, self.guard = process, rows, db, guard
        self.buffer = bytearray()
        self.active_body = False
        self.poisoned = False
        self.index = self
        self.completed = []

    def send(self, value):
        raw = json.dumps(value, separators=(',', ':')).encode() + b'\n'
        if len(raw) > MAX_FRAME:
            raise ValueError('bounded recall command required')
        self.process.stdin.write(raw)
        self.process.stdin.flush()

    def receive(self):
        while b'\n' not in self.buffer:
            self.guard()
            if not select.select([self.process.stdout], [], [], 1)[0]:
                if self.process.poll() is not None:
                    raise EOFError('owned B reader ended without a terminal frame')
                continue
            block = os.read(self.process.stdout.fileno(), 65536)
            if not block:
                raise EOFError('B reader closed before complete verified EOF')
            self.buffer.extend(block)
            if len(self.buffer) > MAX_FRAME:
                raise ValueError('bounded B recall frame exceeded')
        line, _, rest = self.buffer.partition(b'\n')
        self.buffer = bytearray(rest)
        return json.loads(line)

    def entry(self, name):
        self.check()
        expected = self.rows[name]
        value = self.db.execute('select row from selected_recovery_members where name=?', (name,)).fetchone()
        if not value or decode_member(value[0])['member'] != expected:
            raise ValueError('held NORMAL B selected index version changed')
        return expected

    def check(self):
        self.guard()
        if self.poisoned:
            raise ValueError('incomplete selected body; close context before retry')
        # While a body is streaming, the remote checks its actual leases on
        # every normal decoder block. Interleaving a check request would corrupt
        # the ordered stream protocol; do not pretend it was acknowledged.
        if not self.active_body:
            self.send(dict(op='check'))
            if self.receive() != dict(checked=True):
                raise ValueError('normal provider lease check failed')

    def blocks(self, name):
        row = self.entry(name)
        if self.active_body:
            raise ValueError('one serial selected body required')
        self.active_body = True
        finished = False
        try:
            self.send(dict(op='read', name=name, sha256=row['sha256']))
            if self.receive() != dict(opened=True, name=name, bytes=row['bytes'], sha256=row['sha256']):
                raise ValueError('exact selected B read header differs')
            total, hashed = 0, hashlib.sha256()
            while True:
                value = self.receive()
                if value == dict(eof=True, bytes=row['bytes'], sha256=row['sha256']):
                    if total != row['bytes'] or hashed.hexdigest() != row['sha256']:
                        raise ValueError('independent selected B EOF hash/length differs')
                    finished = True
                    self.completed.append(dict(name=name, bytes=total, sha256=hashed.hexdigest(),
                        Linux_metadata={k:row[k] for k in ('uid','gid','mode','mtime_ns','xattrs')},
                        independently_reopened_NORMAL_B_body_EOF_verified=True))
                    break
                if set(value) != {'data'}:
                    raise ValueError('unexpected selected B stream frame')
                block = base64.b64decode(value['data'], validate=True)
                if not 0 < len(block) <= 65536:
                    raise ValueError('bounded normal decoder block required')
                total += len(block)
                if total > row['bytes']:
                    raise ValueError('selected B stream exceeds version length')
                hashed.update(block)
                yield block
        finally:
            self.active_body = False
            self.poisoned = not finished


@contextmanager
def open_recovery(config, plan):
    """One finite, real leased B context. Busy ownership fails without a retry.

    config is an authenticated Nightly-owned JSON file path, not a descriptor
    supplied by the backup itself. The caller must pin its SHA in its own release
    contract. No worker, schedule, source lease or production pointer is changed.
    """
    from datetime import datetime, timezone, timedelta
    from vk_nightly_typed_worker import host_guard
    config = json.loads(Path(config).read_bytes())
    if config.get('format') != 'vk-nightly-selected-original-recovery-config-v1':
        raise ValueError('exact Nightly selected-recovery configuration required')
    folder = Path(config['source_folder'])
    for name, sha in config['source_sha256'].items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest() != sha:
            raise ValueError('selected-recovery source closure changed')
    request_raw = Path(config['request_file']).read_bytes()
    if hashlib.sha256(request_raw).hexdigest() != config['request_file_sha256']:
        raise ValueError('exact selected-version request changed')
    request = json.loads(request_raw)
    if checksum(plan) != request['plan_sha256']:
        raise ValueError('canonical external dedup plan differs')
    NormalRecovery = bridge(config)
    seconds = config.get('maximum_seconds')
    if seconds is not None and (type(seconds) is not int or seconds <= 0):
        raise ValueError('optional explicit positive consumer duration required')
    began = time.monotonic()
    deadline_epoch = time.time()+seconds if seconds is not None else None
    explicit = config.get('operation_deadline_UTC')
    if explicit is not None:
        bound = datetime.fromisoformat(explicit)
        if bound.tzinfo is None:raise ValueError('aware owner consumer deadline required')
        deadline_epoch = min(deadline_epoch, bound.timestamp()) if deadline_epoch is not None else bound.timestamp()
    deadline = datetime.fromtimestamp(deadline_epoch, timezone.utc).isoformat() if deadline_epoch is not None else None
    controls, desktop = dict(config['B_controls']), dict(config['desktop'])
    admission = dict(config['host_admission'], timeout_seconds=seconds)
    if deadline is not None:
        controls['whole_cycle_deadline_UTC'] = desktop['whole_cycle_deadline_UTC'] = deadline
        admission['whole_cycle_deadline_UTC'] = deadline
    def host():
        host_guard(admission, began)
    with ExitStack() as stack:
        controller_fd = stack.enter_context(mcp_lease(Path(config['controller_lease'])))
        objects = stack.enter_context(DesktopObjects(desktop, guard=host))
        remote = stack.enter_context(DesktopControls(controls, guard=host))
        ref = config['index']
        db = remote.client.connect(ref['index_name'], ref['checkpoint_sha256'], readonly=True)
        stack.callback(db.close)
        # An independently accepted immutable selected index has the real
        # native per-index kernel lease plus this SQLite read transaction.
        # The Linux consumer separately reopens/hash-checks the same image.
        db.execute('begin')
        rows = {}
        for f in request['files']:
            row = db.execute('select row from selected_recovery_members where name=?', (f['normal_namespace_name'],)).fetchone()
            if not row:
                raise ValueError('selected exact NORMAL B point is unavailable')
            rows[f['normal_namespace_name']] = decode_member(row[0])
        layers = {s['layer'] for v in rows.values() for s in v['member']['segments']} | {config['index_reference']['layer']}
        dependencies = {k:config['dependencies'][k] for k in layers}
        selected = qualify(request, rows, dependencies)
        placement = json.loads(json.dumps(config['provider_placement']))
        for field in ('roots', 'root_bindings', 'lease_paths'):
            placement[field] = {k:placement[field][k] for k in layers}
        # Keep the existing bounded placement QUERY, without inventing a total
        # production dedup/rollback duration. Native B polling/STOP is unchanged.
        probe_end = datetime.now(timezone.utc)+timedelta(seconds=95)
        if deadline_epoch is not None:probe_end = min(probe_end, datetime.fromtimestamp(deadline_epoch, timezone.utc))
        placement = probe_placement(controls, placement, guard=host, deadline=probe_end.isoformat())
        packet = dict(request=request, request_sha256=checksum(request), rows=rows,
            dependencies=dependencies, provider_placement=placement,index_reference=config['index_reference'],
            deadline_epoch=deadline_epoch, memory_floor_bytes=admission['memory_floor_bytes'],
            swap_floor_bytes=admission['swap_floor_bytes'])
        native_last = [float('-inf')]
        def guard():
            host()
            if time.monotonic()-native_last[0] >= 5:
                objects.client.health()
                db.request('check')
                native_last[0] = time.monotonic()
        guard()
        sources = {}
        for name in sorted(source_closure(folder, 'vk_nightly_selected_reader')):
            raw = (folder/name).read_text()
            if hashlib.sha256(raw.encode()).hexdigest() != config['source_sha256'][name]:
                raise ValueError('remote selected-reader source differs')
            sources[name[:-3]] = dict(source=raw, sha256=config['source_sha256'][name])
        header = json.dumps(dict(sources=sources, packet_sha256=checksum(packet)), separators=(',', ':')).encode()+b'\n'
        body = json.dumps(packet, separators=(',', ':')).encode()+b'\n'
        if len(header) > 1024**2 or len(body) > MAX_FRAME:
            raise ValueError('bounded selected-reader bootstrap required')
        process = subprocess.Popen(command(controls), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            pass_fds=(controller_fd, objects.lease.fileno()))
        diagnostics = Diagnostics(process.stderr)
        client = Reader(process, selected, db, guard)
        original = None
        try:
            process.stdin.write(header+body)
            process.stdin.flush()
            if client.receive() != dict(ready=True, protocol=PROTOCOL, packet_sha256=checksum(packet)):
                raise ValueError('real normal selected-reader readiness unavailable')
            recovery = NormalRecovery(client, source_namespace=request['source_root'],
                location='desktop:'+controls['B_root']+'/'+config['index_reference']['selector'], guard=guard)
            recovery.completed = client.completed
            recovery.provider_placement = placement
            recovery.index_identity = db.request('check')
            yield recovery
            recovery.check()
            client.send(dict(op='close'))
            if client.receive() != dict(closed=True):
                raise ValueError('real selected reader did not close successfully')
            objects.client.health()
        except BaseException as error:
            original = error
            raise
        finally:
            finish(process, original=original, diagnostics=diagnostics)
