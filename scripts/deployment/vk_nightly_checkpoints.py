"""Authenticate reusable components from a terminal, possibly failed backup.

Metadata-only adoption: not a producer or whole-backup acceptance. The caller
pins owner-reviewed receipts/configuration and exact B destinations. Components
retain their original carriers/epochs. Consumers still need actual owner leases,
B identity checks and accepted journal/current-source qualification. No source is
scanned, copied or omitted here; this module grants no STOP/access exception.
"""
import hashlib
import json
import ntpath
import posixpath
import re

FORMAT = 'vk-nightly-terminal-components-v1'
MAX_CONTROL = 64 * 1024**2
MAX_EVENT = 1024**2


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value),
            'exact SHA256 required')
    return value


def unique_pairs(pairs):
    result = {}
    for name, value in pairs:
        require(name not in result, 'duplicate control key')
        result[name] = value
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=unique_pairs,
                      parse_constant=lambda _: require(False, 'nonfinite control'))


def authenticated(raw, expected):
    require(isinstance(raw, bytes) and len(raw) <= MAX_CONTROL,
            'bounded metadata bytes required')
    require(sha256(raw) == digest(expected), 'authenticated control differs')
    return parse(raw)


def b_path(raw):
    require(isinstance(raw, str), 'B carrier path required')
    value = raw.replace('\\', '/')
    require(value.startswith('B:/'), 'only Desktop B carriers are supported')
    parts = value[3:].split('/')
    require(all(p and p not in ('.', '..') and p == p.rstrip(' .')
                and not any(c in p for c in ':*?<>|\x00\r\n')
                and not re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', p)
                for p in parts), 'unsafe B carrier selector')
    return value


def under(raw, prefix):
    value, root = b_path(raw), b_path(prefix)
    require(value.casefold().startswith(root.casefold() + '/'),
            'carrier is outside reviewed B prefix')
    return value


def source_path(raw):
    require(isinstance(raw, str) and raw.startswith('/') and '\x00' not in raw
            and posixpath.normpath(raw) == raw, 'canonical source path required')
    return raw


def seal(row):
    name = row.get('name')
    require(isinstance(name, str) and ntpath.basename(name) == name
            and name not in ('', '.', '..') and '/' not in name
            and not any(c in name for c in ':*?<>|\x00\r\n'),
            'component must have an exact basename')
    size = row.get('bytes')
    require(type(size) is int and size > 0, 'positive component byte count required')
    identity = row.get('file_identity')
    require(isinstance(identity, list) and len(identity) == 4
            and all(type(v) is int and v >= 0 for v in identity)
            and identity[2] == size, 'native carrier identity/size differs')
    return dict(name=name, bytes=size, sha256=digest(row.get('sha256')),
                file_identity=identity)


def events(raw, expected):
    require(isinstance(raw, bytes) and len(raw) <= MAX_CONTROL
            and raw.endswith(b'\n') and sha256(raw) == digest(expected),
            'complete authenticated event stream required')
    rows = []
    for line in raw.splitlines():
        require(0 < len(line) <= MAX_EVENT, 'bounded complete event required')
        row = parse(line)
        require(isinstance(row, dict), 'event object required')
        rows.append(row)
    require(rows and rows[-1].get('event') == 'current_SQL_phase_failed'
            and rows[-1].get('child_terminal') is True
            and rows[-1].get('Linux_bridge_terminal') is True,
            'both original failed-run children must be terminal')
    return rows


def file_components(rows, config, *, configuration_sha256, worker_sha256,
                    expected_root, backup_prefix):
    root = b_path(expected_root)
    require(b_path(config['native_root']) == root, 'file configuration root differs')
    dispatches = [r for r in rows if r.get('event') == 'actual_SQL_dispatch']
    require(len(dispatches) == 1, 'one original file dispatch required')
    dispatch = dispatches[0]
    require(dispatch['worker_sha256'] == digest(worker_sha256)
            and dispatch['dispatch']['execution_config_sha256'] == configuration_sha256
            and b_path(dispatch['dispatch']['destination_root']) == root,
            'original file worker/configuration/destination differs')
    under(root, backup_prefix)
    sealed, paired = {}, {}
    for row in rows:
        if row.get('event') == 'native_file_component_seal':
            item = seal(row)
            require(item['name'] not in sealed, 'duplicate native component seal')
            sealed[item['name']] = item
        if row.get('event') != 'Linux_selected_files_decoded':
            continue
        archive, records = seal(row['archive']), seal(row['records'])
        require(archive['name'].endswith('.zip') and records['name'].endswith('.jsonl')
                and archive['name'][:-4] == records['name'][:-6],
                'paired archive/records names differ')
        require(archive == sealed.get(archive['name'])
                and records == sealed.get(records['name']),
                'independent proof lacks matching prior native seals')
        require(row.get('all_member_hashes_and_Linux_metadata_match') is True
                and row.get('exact_Linux_metadata_in_sealed_records_and_ZIP_comments') is True
                and row.get('encoding') == 'zip-member'
                and type(row.get('members')) is int and row['members'] > 0
                and type(row.get('decoded_source_file_bytes')) is int
                and row['decoded_source_file_bytes'] >= 0,
                'complete independent member/hash/metadata proof required')
        require(archive['name'] not in paired, 'duplicate independent component proof')
        paired[archive['name']] = dict(
            archive={**archive, 'native_path': under(root + '/' + archive['name'], backup_prefix)},
            records={**records, 'native_path': under(root + '/' + records['name'], backup_prefix)},
            members=row['members'], raw_bytes=row['decoded_source_file_bytes'],
            encoding='zip-member', proof=row)
    return list(paired.values())


def sql_components(result, config, *, expected_root, backup_prefix):
    require(result.get('OS_SSD_payload_spool') == 0
            and result['terminal'].get('event') == 'SQL_owned_children_terminal'
            and result['terminal'].get('full_backup_accepted') is False,
            'terminal SQL component result required')
    native = result['native']
    require(native.get('event') == 'current_SQL_component_complete'
            and native.get('schema') == 'T17-current-SQL-component-v1'
            and native.get('source_images_consistent_and_independently_reopened') is True,
            'independently completed SQL component required')
    root = b_path(expected_root)
    require(b_path(result['native_root']) == root and b_path(config['native_root']) == root,
            'SQL configuration/result destination differs')
    under(root, backup_prefix)
    retained, pending = config['retained_verified_components'], config['pending_fresh_SQL_bounds']
    require(not set(retained) & set(pending), 'ambiguous SQL component ownership')
    output = {}
    for row in native['SQL_images']:
        source = source_path(row['source'])
        require(source not in output, 'duplicate SQL source proof')
        n, independent = seal(row['native']), row['Linux_reopen']
        require(row.get('event') in (None, 'SQL_image_verified')
                and row['native'].get('event') == 'native_SQL_seal'
                and independent.get('event') == 'Linux_SQL_reopen_proof'
                and row['native'].get('integrity') == 'ok'
                and independent.get('integrity') == 'ok'
                and independent.get('same_image_independently_reopened') is True
                and all(row['native'][k] == independent[k]
                        for k in ('name', 'bytes', 'sha256', 'schema_sha256')),
                'SQL native/independent integrity/schema/hash proofs differ')
        digest(independent['schema_sha256'])
        if source in retained:
            previous = retained[source]
            require(previous['source'] == source and previous['proof'] == row
                    and previous['native_identity'] == n['file_identity'],
                    'retained SQL carrier/proof identity differs')
            path = under(previous['native_path'], backup_prefix)
            require(path.endswith('/' + n['name']), 'retained SQL basename differs')
            provenance = dict(kind='retained', seal_sha256=digest(previous['seal_sha256']))
        else:
            require(source in pending, 'SQL proof has no reviewed source request')
            path = under(root + '/' + n['name'], backup_prefix)
            provenance = dict(kind='fresh-in-original-run')
        output[source] = dict(**n, native_path=path, schema_sha256=independent['schema_sha256'],
                              provenance=provenance, capture_epoch=row.get('capture'),
                              source_epoch_may_differ_from_current_run=source in retained,
                              current_source_qualified=False, proof=row)
    require(set(output) == set(retained) | set(pending), 'SQL component cohort incomplete')
    return output


def adopt(*, file_receipts, file_config, sql_result, sql_config, pins,
          file_root, sql_root, backup_prefix):
    """No filesystem/transport effects; pins come from an external owner seal.

    A failed source read never revokes completed immutable component proofs. It
    also never upgrades them to current-source, complete-baseline or fence proof.
    """
    files_cfg = authenticated(file_config, pins['file_config'])
    sql_cfg = authenticated(sql_config, pins['sql_config'])
    sql = authenticated(sql_result, pins['sql_result'])
    rows = events(file_receipts, pins['file_receipts'])
    sequence = sql_cfg['SQL_snapshot_observer_lower_bound_sequence']
    require(type(sequence) is int and sequence >= 0, 'original SQL journal anchor required')
    files = file_components(rows, files_cfg, configuration_sha256=pins['file_config'],
                            worker_sha256=pins['file_worker'], expected_root=file_root,
                            backup_prefix=backup_prefix)
    images = sql_components(sql, sql_cfg, expected_root=sql_root, backup_prefix=backup_prefix)
    return dict(format=FORMAT, source_receipt_pins=dict(pins), file_components=files,
                sql_images=images, file_component_count=len(files), sql_image_count=len(images),
                verified_file_raw_bytes=sum(r['raw_bytes'] for r in files),
                sql_observer_epoch_binding_sha256=digest(sql_cfg['SQL_snapshot_observer_epoch_binding_sha256']),
                sql_observer_lower_bound_sequence=sequence,
                reuse_requires=['native identities and held dependency leases',
                                'member lookup in authenticated records',
                                'accepted same-epoch journal/current-source qualification'],
                parent_failed=True, current_source_qualified=False,
                full_backup_accepted=False, writer_fence_verified=False,
                schedule_adoption_authorized=False, payload_bytes_copied=0)


def typed_component_rows(component, records_raw, *, layer):
    """Map authenticated completed ZIP records into existing typed recipes.

    The catalog is externally pinned by the caller and already authenticates the
    native/independent pair. Re-read records, not completed ZIP payloads. These
    recipes preserve original component versions; current-source qualification,
    all cross-component link checks and journal-gap closure remain separate.
    """
    require(isinstance(layer, str) and re.fullmatch('[A-Za-z0-9_.-]+', layer),
            'explicit typed carrier layer required')
    archive, records = component['archive'], component['records']
    require(type(component.get('members')) is int and component['members'] > 0
            and type(component.get('raw_bytes')) is int and component['raw_bytes'] >= 0,
            'finite complete component counts required')
    require(component.get('encoding') == 'zip-member', 'verified ZIP-member component required')
    seal(archive); seal(records)
    require(isinstance(records_raw, bytes) and len(records_raw) == records['bytes']
            and len(records_raw) <= MAX_CONTROL and records_raw.endswith(b'\n')
            and sha256(records_raw) == records['sha256'], 'exact retained component records differ')
    rows = []; total = 0; previous = ''
    for line in records_raw.splitlines():
        require(0 < len(line) <= 65536, 'bounded complete retained member record required')
        original = parse(line); path = source_path(original['path']); name = path.lstrip('/')
        require(name and name > previous, 'record member ordering/uniqueness differs')
        previous = name; action = original['action']; metadata = original['metadata']
        require(action in ('file', 'directory', 'symlink', 'hardlink'), 'unsupported retained member')
        require(set(metadata) == {'mode', 'uid', 'gid', 'mtime_ns', 'xattrs'}
                and all(type(metadata[k]) is int and metadata[k] >= 0 for k in ('mode', 'uid', 'gid', 'mtime_ns'))
                and metadata['mode'] <= 0o7777 and isinstance(metadata['xattrs'], dict),
                'exact retained Linux metadata required')
        import base64
        for key, value in metadata['xattrs'].items():
            require(isinstance(key, str) and '\x00' not in key, 'invalid retained xattr')
            base64.b64decode(value, validate=True)
        row = {'kind': action, **metadata, 'component_provenance': {
            'record_sha256': records['sha256'], 'archive_sha256': archive['sha256'],
            'current_source_qualified': False, 'parent_backup_accepted': False,
            **({'source_read_view': original['source_read_view']} if 'source_read_view' in original else {})}}
        if action == 'file':
            size = original['bytes']; checksum = digest(original['sha256'])
            require(type(size) is int and size >= 0, 'nonnegative retained member size required')
            total += size
            row.update(bytes=size, sha256=checksum, segments=[{
                'layer': layer, 'selector': archive['name'], 'member': name,
                'bytes': size, 'sha256': checksum, 'encoding': 'zip-member',
                'encoded_bytes': archive['bytes'], 'encoded_sha256': archive['sha256']}])
        elif action in ('symlink', 'hardlink'):
            target = original['target']
            require(isinstance(target, str) and target and '\x00' not in target,
                    'retained link literal required')
            row['target'] = target
            if action == 'hardlink':
                # Native records may not carry content hashes for a tar link.
                # The complete-map compiler must resolve it against the retained
                # target and add bytes/hash; do not invent them here.
                row['hardlink_target_resolution_required'] = True
        rows.append((name, row))
    require(len(rows) == component['members'] and total == component['raw_bytes'],
            'complete retained component member count/raw bytes differ')
    return rows
