"""Pure proposal validation for lean-backup fixtures, never a production filter.

Exact paths and pinned rebuild inputs are required. Category names, directory
basenames and same-account review do not authorize exclusions or retirement.
The controller still owns authoritative dirty/untracked/required-state coverage,
independent restore acceptance and any production plan/scope approval.
"""
import copy
import re
from pathlib import PurePosixPath

from vk_nightly_archive_index import validate_backup_entries
from vk_nightly_generation import name


def below(path, root):return path == root or path.startswith(root + '/')


def project(entries, proposals, *, protected):
    """Return a recovery projection; never mutate inputs, plans or files.

    proposals maps each exact output directory to preserved input file hashes.
    Presence of a recipe is not proof that a real external package registry,
    toolchain or rebuild route is available; actual restore tests remain required.
    """
    validate_backup_entries(entries)
    roots = tuple(proposals)
    for root in roots:
        name(root)
        if '.git' in PurePosixPath(root).parts:
            raise ValueError('Git state requires its independent preservation authority')
        if entries.get(root, {}).get('kind') != 'directory':
            raise ValueError('exact indexed output directory required; no symlink/file exclusion')
        if any(below(p, root) for p in protected):
            raise ValueError('proposal contains protected runtime, user work or recovery state')
        inputs = proposals[root]
        if not inputs:
            raise ValueError('pinned preserved rebuild inputs required')
        for key, checksum in inputs.items():
            name(key)
            if (not re.fullmatch('[0-9a-f]{64}', checksum)
                    or any(below(key, r) for r in roots)
                    or entries.get(key, {}).get('kind') != 'file'
                    or entries[key]['sha256'] != checksum):
                raise ValueError('rebuild input missing, changed or excluded')
    for key in protected:
        name(key)
        if key not in entries:
            raise ValueError('protected inventory entry missing')
    result = {key:copy.deepcopy(row) for key,row in entries.items() if not any(below(key,r) for r in roots)}
    for key,row in result.items():
        if row['kind'] == 'hardlink' and row['target'] not in result:
            # The independent manifest must retain this content object even if
            # its old canonical pathname was reproducible output. No dangling
            # link or dependency on an excluded tree is allowed.
            row['kind'] = 'file';row.pop('target')
    validate_backup_entries(result)
    def unique(values):
        objects = {}
        for row in values:
            if row['kind'] not in ('file','hardlink'):continue
            if row['sha256'] in objects and objects[row['sha256']] != row['bytes']:
                raise ValueError('conflicting preserved object sizes')
            objects[row['sha256']] = row['bytes']
        return objects
    before = unique(entries.values());after = unique(result.values())
    return {'entries':result,'removed_paths':len(entries)-len(result),
            'unique_content_bytes_before':sum(before.values()),'unique_content_bytes_after':sum(after.values()),
            'unique_content_bytes_omitted':sum(size for h,size in before.items() if h not in after),
            'production_plan_modified':False,'exclusion_authorized':False,'restore_acceptance_required':True}
