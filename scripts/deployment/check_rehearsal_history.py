"""Compare history without hiding content loss or arbitrary reordering.

An independently proven pair of leading startup diagnostics may race between
stdout and stderr. Only those exact two content hashes at indices 0 and 1 can
be put in a stable order. Keep raw page hashes in the private test evidence too.
"""
from copy import deepcopy
import hashlib
import json
import re


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def canonical_page(page, policy=None):
    result = deepcopy(page)
    if policy is None:
        return result
    expected = policy['pair_entry_sha256']
    if (not isinstance(expected, list) or len(expected) != 2
            or len(set(expected)) != 2
            or any(not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value)
                   for value in expected)):
        raise ValueError('Invalid independently verified diagnostic pair')
    entries = result['entries']
    if len(entries) < 2:
        raise ValueError('Verified diagnostic pair is missing')
    for index, row in enumerate(entries[:2]):
        if (set(row) != {'index', 'entry'} or type(row['index']) is not int
                or row['index'] != index):
            raise ValueError('Diagnostic pair moved outside its verified indices')
    actual = {digest(row['entry']): row['entry'] for row in entries[:2]}
    if set(actual) != set(expected):
        raise ValueError('Diagnostic content changed, duplicated or missing')
    for index, checksum in enumerate(sorted(expected)):
        entries[index]['entry'] = actual[checksum]
    return result
