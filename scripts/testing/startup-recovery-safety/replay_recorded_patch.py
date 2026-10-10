"""Replay recorded textual patches in memory, never execute recorded commands.

This deliberately accepts only exact, unambiguous context. A failed call must be
excluded by its paired tool result before invoking replay. Git reads and evidence
authentication belong to the caller; this module cannot write a recovered tree.
"""
from pathlib import PurePosixPath


def relative_name(name, prefix):
    if not name.startswith(prefix + '/'):
        raise ValueError('patch outside declared owner')
    relative = name[len(prefix) + 1:]
    path = PurePosixPath(relative)
    if not relative or path.is_absolute() or '..' in path.parts or str(path) != relative:
        raise ValueError('unsafe patch path')
    return relative


def replay(patch, prefix, files):
    lines = patch.splitlines()
    if not lines or lines[0] != '*** Begin Patch' or lines[-1] != '*** End Patch':
        raise ValueError('incomplete patch')
    # Work on a copy so a later invalid file cannot partially apply a call.
    result = dict(files)
    index = 1
    while index < len(lines) - 1:
        header = lines[index]
        if header.startswith('*** Add File: '):
            operation = 'add'
        elif header.startswith('*** Update File: '):
            operation = 'update'
        else:
            raise ValueError('unsupported patch operation')
        name = relative_name(header.split(': ', 1)[1], prefix)
        index += 1
        body = []
        while index < len(lines) - 1 and not lines[index].startswith('*** '):
            body.append(lines[index])
            index += 1
        if operation == 'add':
            if name in result or not body or any(not line.startswith('+') for line in body):
                raise ValueError('invalid new file')
            result[name] = ('\n'.join(line[1:] for line in body) + '\n').encode()
            continue
        if name not in result or not body or not body[0].startswith('@@'):
            raise ValueError('missing preimage or hunk')
        original = result[name].decode()
        source = original.splitlines()
        position = 0
        hunk = 0
        while hunk < len(body):
            if not body[hunk].startswith('@@'):
                raise ValueError('invalid hunk marker')
            hunk += 1
            old, new = [], []
            while hunk < len(body) and not body[hunk].startswith('@@'):
                line = body[hunk]
                if not line or line[0] not in ' +-':
                    raise ValueError('invalid hunk line')
                if line[0] != '+':
                    old.append(line[1:])
                if line[0] != '-':
                    new.append(line[1:])
                hunk += 1
            if not old:
                raise ValueError('insertion without context')
            matches = [i for i in range(position, len(source) - len(old) + 1)
                       if source[i:i + len(old)] == old]
            if len(matches) != 1:
                raise ValueError('missing or ambiguous exact context')
            start = matches[0]
            source[start:start + len(old)] = new
            position = start + len(new)
        result[name] = ('\n'.join(source) + ('\n' if original.endswith('\n') else '')).encode()
    return result
