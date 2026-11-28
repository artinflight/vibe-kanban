"""Eligibility for an unchanged, same-epoch SQLite API image with sidecars.

The caller must authenticate the independently restored immutable checkpoint,
its SQL request/points/sidecar observations and the complete real B/live report.
This reads a main-file header and metadata only. It neither accepts a backup
nor adopts an image. Final adoption needs the original native B acceptance,
actual writer fence and fresh pre/post checks. Old API epochs remain old.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat

from vk_restart_sql_reuse import attributes, fingerprint


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def qualify_sidecar_source(path, point, sidecars, request, report, *, guard):
    """Sidecars maps '-wal'/'-journal' to sealed observations, or explicit None."""
    path = Path(path);source = str(path)
    result = dict(source=source, eligible_unchanged_SQL_reuse=False, new_API_epoch_claimed=False,
                  backup_acceptance_claimed=False, source_body_bytes_copied=0)
    def refused(reason):
        return dict(result, reason=reason)
    cohort = request.get('cohort_id');binding = request.get('binding', {})
    if (not digest(cohort) or hashlib.sha256(canonical({k:v for k,v in request.items() if k != 'cohort_id'})).hexdigest() != cohort
            or request.get('format') != 'vk-nightly-current-SQL-cohort-request-v1'
            or source not in request.get('sources', []) or source in request.get('always_SQL_API_sources', [])
            or point.get('SQL_cohort_id') != cohort):
        return refused('Authenticated same-cohort non-mandatory API point required')
    since = request.get('metadata_delta', {}).get('through');barrier = report.get('barrier', {})
    if (type(since) is not int or report.get('since') != since or type(report.get('sequence')) is not int
            or report['sequence'] < since or report.get('ready') is not True or report.get('errors') or report.get('terminal')
            or report.get('coverage_model') != 'all-selected-inodes-v1'
            or barrier != dict(kernel_drain_completed=True, durable_sequence=report['sequence'], instance=binding.get('source_instance'))
            or report.get('instance') != binding.get('source_instance')
            or any(report.get(k) != binding.get(k) for k in ('plan_sha256', 'scope_sha256'))
            or set(report.get('changed', [])) != set(report.get('events', {}))):
        return refused('Complete same-epoch history from before API capture required')
    # Even a permission/rename/replacement event is conservative fresh-API
    # work. CLOSE_WRITE alone is insufficient; exact metadata is also required.
    for name, mask in report['events'].items():
        if (name in (source, source+'-wal', source+'-journal') or source.startswith(name.rstrip('/')+'/')):
            if type(mask) is not int or mask <= 0 or mask >= 2**32 or mask & ~0x8:
                return refused('Actual main/WAL/journal or ancestor change requires API')
    member = point.get('member', {});proof = point.get('independent', {});epoch = point.get('original_source_API_point_at')
    if (point.get('source') != source or point.get('status') != 'consistent_SQL_point_verified'
            or point.get('method') != 'SQLite-backup-API' or point.get('source_changed_online') is not False
            or point.get('source_API_point_qualifies_later_epoch_not_original') is not True
            or member.get('kind') != 'file' or not digest(point.get('sha256'))
            or not digest(point.get('B_acceptance_object', {}).get('sha256')) or proof.get('integrity') != 'ok'
            or type(epoch) not in (int, float) or not math.isfinite(epoch) or epoch <= 0
            or type(point.get('bytes')) is not int or point['bytes'] <= 0
            or any(point.get(k) != member.get(k) or proof.get(k) != member.get(k) for k in ('bytes', 'sha256'))):
        return refused('Stable independently restored API image required')
    before = point.get('source_metadata_before', {});after = point.get('source_metadata_after', {})
    fields = ('device', 'inode', 'uid', 'gid', 'mode', 'mtime_ns', 'ctime_ns', 'xattrs')
    expected = point.get('source_identity_before')
    if (any(k not in before or k not in after or before[k] != after[k] for k in fields)
            or not isinstance(expected, list) or len(expected) != 9 or expected[8] != 1
            or expected != [before['device'], before['inode'], stat.S_IFREG | before['mode'], expected[3],
                            before['mtime_ns'], before['ctime_ns'], before['uid'], before['gid'], expected[8]]
            or any(member.get(k) != before[k] for k in ('uid', 'gid', 'mode', 'mtime_ns', 'xattrs'))):
        return refused('Stable unique main identity and Linux metadata required')
    if set(sidecars) != {'-wal', '-journal'}:
        return refused('Explicit sealed WAL and rollback-journal dispositions required')
    def check():
        guard()
        if not path.is_absolute() or path.resolve() != path or fingerprint(path.lstat()) != expected or attributes(path) != before['xattrs']:
            return False
        for suffix, old in sidecars.items():
            current = Path(source + suffix)
            if old is None:
                if os.path.lexists(current): return False
            else:
                observation = old.get('namespace', {});identity = observation.get('identity', [])
                if (old.get('source') != str(current) or old.get('required_SQL_source') != source
                        or observation.get('kind') != 'file' or len(identity) != 9 or identity[8] != 1
                        or current.resolve() != current or fingerprint(current.lstat()) != identity
                        or identity[2:5] != [stat.S_IFREG | observation['mode'], observation['bytes'], observation['mtime_ns']]
                        or identity[6:8] != [observation['uid'], observation['gid']]
                        or attributes(current) != observation['xattrs']):
                    return False
        return True
    try:
        if not check(): return refused('Current main or WAL/journal disposition differs')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            if fingerprint(os.fstat(fd)) != expected or os.read(fd, 16) != b'SQLite format 3\0' or not check() or fingerprint(os.fstat(fd)) != expected:
                return refused('Source changed during eligibility observation')
        finally:
            os.close(fd)
    except (OSError, KeyError):
        return refused('Current source metadata unavailable or incomplete')
    return dict(result, eligible_unchanged_SQL_reuse=True, accepted_API_point_at=epoch,
                accepted_image_sha256=point['sha256'], accepted_image_bytes=point['bytes'],
                accepted_B_object_sha256=point['B_acceptance_object']['sha256'], SQL_cohort_id=cohort,
                source_instance=report['instance'], since=since, through=report['sequence'],
                complete_report_sha256=hashlib.sha256(canonical(report)).hexdigest(),
                source_header_bytes_read=16, source_identity=expected,
                sealed_sidecar_dispositions_sha256=hashlib.sha256(canonical(sidecars)).hexdigest(),
                fresh_journal_and_final_source_recheck_required=True,
                baseline_independent_restore_and_native_B_acceptance_required=True)
