"""Production adapter for the finite packed controller; no service actions.

The caller supplies the actual held normal-B context and current serving roster.
The source-pinned deployment entrypoint, not configuration flags or this module's
presence, establishes authority. Old/non-pinning serving readers are refused.
"""
from pathlib import Path
import json
import subprocess
import time

import log_dedup as logs
from online_owner import LiveReaders
from packed_admission import NormalPreparedRecovery, pinned
from packed_plan import migrate_group
from packed_publication import PinnedReaders
import packed_recovery as checkpoints
import reclaim
from scoped_fence import WriterRoster


class Adapter:
    def __init__(self, readers, recovery, checkpoint_files, *, reserve_bytes, reader_artifacts):
        if (not isinstance(readers, LiveReaders) or not isinstance(recovery, NormalPreparedRecovery)
                or not callable(checkpoint_files) or type(reserve_bytes) is not int
                or not 3*1024**3 <= reserve_bytes <= 16*1024**3):
            raise ValueError('Actual production readers/recovery and explicit reserve required')
        self.readers, self.recovery = readers, recovery
        self.capture, self.reserve = checkpoint_files, reserve_bytes
        self.check()
        rows = readers.config['readers']
        self.pins = PinnedReaders([dict(pid=r['server_pid'],sha256=r['sha256'])
                                   for r in rows.values()], self.check)
        main = rows['main']
        self.writer = WriterRoster([dict(pid=main['server_pid'],sha256=main['sha256'])], self.check)
        self.writer.qualify()
        if set(reader_artifacts) != set(rows):
            raise ValueError('Exact reader-build artifact roster required')
        self.probes = {}
        for name, reference in reader_artifacts.items():
            artifact = pinned(reference)
            path = Path(reference['path']).parent/'archive-reader-probe'
            if (artifact['artifact_sha256'] != rows[name]['sha256']
                    or reclaim.file_hash(path) != artifact['probe_sha256']):
                raise ValueError('Probe and live reader must share the exact qualified build')
            self.probes[name] = (path, logs.version(logs.regular(path)))

    def check(self):
        self.readers.check()
        self.recovery.check()

    def convert(self, group, journal, progress):
        self.pins.check(); self.writer.check()
        return migrate_group(group, journal, self.readers, self.recovery,
                             reserve_bytes=self.reserve, checkpoint=progress,
                             verify_published=self.verify_published)

    def verify_published(self, group, journal):
        """Use the exact qualified production-reader builds before retirement."""
        self.check()
        paths = [logs.safe_path(self.readers.source,r['path']) for r in group['plan']['files']]
        versions = {str(p):logs.version(logs.regular(p)) for p in paths}
        expected = [(r['sha256'],r['raw_bytes']) for r in group['plan']['files']]
        began = time.monotonic()
        for name,(probe,identity) in self.probes.items():
            if logs.version(logs.regular(probe)) != identity:
                raise ValueError('Qualified production-reader probe changed')
            reply = subprocess.run([str(probe), *map(str,paths)], check=True,
                                   capture_output=True, timeout=600)
            proofs = json.loads(reply.stdout)
            if (len(proofs) != len(expected) or any(not p['full_eof_verified']
                    or (p['sha256'],p['bytes'])!=e for p,e in zip(proofs,expected))):
                raise ValueError('Qualified production-reader full EOF differs')
            self.check()
        proof = dict(plan_sha256=group['plan_sha256'], files=len(paths),
                     raw_bytes=sum(n for _,n in expected), full_EOF_verified=True,
                     production_reader_builds=len(self.probes), versions=versions,
                     elapsed_seconds=time.monotonic()-began)
        self._unchanged(group,proof)
        checkpoints.write_new(Path(journal)/'READER_EOF.json',proof)
        return proof

    def _unchanged(self, group, proof):
        if (proof['plan_sha256'] != group['plan_sha256']
                or set(proof['versions']) != {str(self.readers.source/r['path']) for r in group['files']}):
            raise ValueError('Reader proof belongs to another selection')
        for row in group['files']:
            path = logs.safe_path(self.readers.source,row['path'])
            if logs.version(logs.regular(path)) != proof['versions'][str(path)]:
                raise ValueError('Published history changed after full EOF verification')
            if ({k:v for k,v in reclaim.metadata_for(path).items()if k!='atime_ns'}
                    != {k:v for k,v in row['metadata'].items()if k!='atime_ns'}):
                raise ValueError('Published Linux metadata differs')

    def verify(self, group, journal):
        # Retirement changes loose objects and retained originals only. Reuse
        # full EOF only while every published manifest version is unchanged.
        self.check()
        proof = json.loads((Path(journal)/'READER_EOF.json').read_bytes())
        retired = json.loads((Path(journal)/'RETIRED.json').read_bytes())
        if not retired['originals_released'] or retired['plan_sha256']!=group['plan_sha256']:
            raise ValueError('Exact retirement receipt required')
        self._unchanged(group,proof)
        return proof

    def seal(self, paths):
        refs = []
        rows = []
        for p in paths:
            st = logs.regular(p)
            rows.append(dict(path=str(p), bytes=st.st_size, sha256=reclaim.file_hash(p)))
        for number, batch in enumerate(checkpoints.batches(rows)):
            self.check()
            proof = self.capture(batch, f'RUN_JOURNAL_{number:04d}')
            checkpoints.verify_scope(proof['checkpoint'], batch)
            actual=proof['actual_independent_normal_restore']
            if (not actual['independent_owner_controls_restore_verified']
                    or not actual['normal_leased_consumer_entrypoint_verified']
                    or actual['files']!=len(batch)
                    or actual['raw_bytes']!=sum(r['bytes']for r in batch)):
                raise ValueError('Actual run-journal restore required')
            refs.append(dict(index_reference=proof['checkpoint']['index_reference'],
                             manifest_sha256=proof['checkpoint']['manifest_sha256']))
        return dict(independent_recovery_verified=True, checkpoints=refs, files=len(rows))
