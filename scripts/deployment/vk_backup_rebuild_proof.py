"""Exact-root rebuild proof for a proposed backup projection, never activation.

The controller supplies the current captured inventory, approved exact roots,
retained recipe/input pins, and a separately rebuilt inventory plus bounded
readback callbacks. No source discovery, registry access, recipe execution,
filesystem write, deletion, scheduler or privilege operation occurs here.
"""
import hashlib
import json
import re

from vk_backup_lean_contract import below, project
from vk_nightly_archive_index import validate_backup_entries
from vk_nightly_generation import name


def digest(value):
    result = hashlib.sha256()
    for part in json.JSONEncoder(sort_keys=True, separators=(',', ':')).iterencode(value):
        result.update(part.encode())
    return result.hexdigest()


def content(row):
    kind = row['kind']
    if kind in ('file', 'hardlink'):
        return {'kind': 'file', 'sha256': row['sha256'], 'bytes': row['bytes']}
    if kind == 'symlink':
        return {'kind': kind, 'target': row['target']}
    return {'kind': kind}


def certify(entries, rebuilt_entries, recipes, *, approved_roots, protected,
            read_rebuilt_file, read_rebuilt_link, readback_budget_bytes):
    """Certify only an exact independently reproduced subtree.

    Dirty/ignored patches, additions, missing files, or changed link literals
    reject the ENTIRE root. Original metadata remains in the complete restore
    catalog; a retained hardlink alias never depends on an omitted pathname.

    Callbacks must read the independently rebuilt artifact, not the original
    source/captured objects. Their provenance/hermetic recipe acceptance and
    authoritative protected-work inventory belong to the existing controller.
    Same-account evidence is operational review, not a security boundary.
    """
    validate_backup_entries(entries)
    validate_backup_entries(rebuilt_entries)
    if type(readback_budget_bytes) is not int or readback_budget_bytes < 0:
        raise ValueError('measured readback byte budget required')
    roots = tuple(approved_roots)
    # Freeze one-shot inventories before hashing or validating them. Otherwise
    # a generator could be consumed by the binding and omit protected work.
    protected = tuple(protected)
    if not roots or len(roots) > 64 or len(set(roots)) != len(roots) or set(recipes) != set(roots):
        raise ValueError('exact approved root/recipe inventory required')
    for root in roots:
        name(root)
        if any(other != root and below(root, other) for other in roots):
            raise ValueError('overlapping rebuild roots rejected')
    if any(not any(below(key, root) for root in roots) for key in rebuilt_entries):
        raise ValueError('rebuilt artifact expands approved root scope')
    before = digest({'entries': entries, 'rebuilt': rebuilt_entries, 'recipes': recipes,
                     'approved_roots': roots, 'protected': sorted(protected)})
    pinned_inputs = {}
    for root, recipe in recipes.items():
        if (not isinstance(recipe, dict)
                or set(recipe) != {'id', 'source', 'inputs'}
                or not isinstance(recipe['id'], str)
                or not re.fullmatch('[a-z0-9][a-z0-9.-]{0,63}', recipe['id'])
                or not isinstance(recipe['inputs'], dict)
                or not isinstance(recipe['source'], str)
                or recipe['source'] not in recipe['inputs']):
            raise ValueError('retained fixed recipe source and input pins required')
        name(recipe['source'])
        pinned_inputs[root] = recipe['inputs']
    # The existing projection validator checks every input hash, protected work,
    # exact directory identity, Git restriction, and retained hardlink aliases.
    projection = project(entries, pinned_inputs, protected=protected)
    shapes = {}
    for root in roots:
        actual = {key: content(row) for key, row in entries.items() if below(key, root)}
        rebuilt = {key: content(row) for key, row in rebuilt_entries.items() if below(key, root)}
        if actual != rebuilt:
            raise ValueError('rebuild differs: preserve root including local patches, additions and absences')
        shapes[root] = digest(actual)
    expected_bytes = sum(row['bytes'] for row in rebuilt_entries.values() if row['kind'] in ('file', 'hardlink'))
    if expected_bytes > readback_budget_bytes:
        raise ValueError('rebuild readback exceeds measured approved byte budget')
    checked_bytes = 0
    for key, row in rebuilt_entries.items():
        if row['kind'] in ('file', 'hardlink'):
            count = 0
            checksum = hashlib.sha256()
            with read_rebuilt_file(key) as source:
                while True:
                    data = source.read(min(65536, row['bytes'] - count + 1))
                    if not data:
                        break
                    if not isinstance(data, bytes):
                        raise ValueError('rebuilt readback must return bytes')
                    count += len(data)
                    checked_bytes += len(data)
                    if count > row['bytes'] or checked_bytes > readback_budget_bytes:
                        raise ValueError('rebuilt file exceeds captured size/readback budget')
                    checksum.update(data)
            if count != row['bytes'] or checksum.hexdigest() != row['sha256']:
                raise ValueError('independent rebuilt artifact readback differs')
        elif row['kind'] == 'symlink' and read_rebuilt_link(key) != row['target']:
            raise ValueError('independent rebuilt symlink literal differs')
    if digest({'entries': entries, 'rebuilt': rebuilt_entries, 'recipes': recipes,
               'approved_roots': roots, 'protected': sorted(protected)}) != before:
        raise ValueError('captured inventory/recipe/protected work changed during proof')
    return {'version': 1, 'policy': 'exact-root-independent-rebuild-v1',
            'input_binding_sha256': before, 'root_content_inventory_sha256': shapes,
            'readback_bytes': checked_bytes, 'capture_projection': projection,
            # Retain every original pathname/metadata, including omitted outputs
            # and hardlink relationships, in the eventual independent manifest.
            'complete_restore_catalog': entries, 'rebuild_recipes': recipes,
            'omitted_payload_paths': sorted(set(entries) - set(projection['entries'])),
            'production_plan_modified': False, 'adoption_authorized': False,
            'whole_plan_restore_acceptance_required': True}
