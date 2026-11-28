"""Versioned context extension using the original REAL pinned Reader class.

The caller pins this constructor and supplies its already-authenticated legacy
module. All original scope/hash/identity/STOP/lease/body/EOF checks are retained.
The extended context exposes the actual existing native object client so an
owner's final quiet SQL API capture does not acquire a conflicting second writer.
This is not a patched legacy module and never fabricates a verified handle.
"""
from vk_nightly_selected_recovery import *
@contextmanager
def open_recovery(config, plan, *, legacy, legacy_sha256):
    """One finite, real leased B context. Busy ownership fails without a retry.

    config is an authenticated Nightly-owned JSON file path, not a descriptor
    supplied by the backup itself. The caller must pin its SHA in its own release
    contract. No worker, schedule, source lease or production pointer is changed.
    """
    # Reuse the ACTUAL pinned Reader class, never a synthetic handle.
    if (hashlib.sha256(Path(legacy.__file__).read_bytes()).hexdigest()!=legacy_sha256
            or legacy.Reader.receive.__code__.co_filename!=str(legacy.__file__)):
        raise ValueError('actual source-pinned legacy Reader required')
    Reader=legacy.Reader
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
            # Export only the actual already-held native capabilities for the
            # existing serial SQL subphase; no second writer/lease/transport.
            recovery.native_SQL_client = objects.client
            recovery.native_SQL_guard = host
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
