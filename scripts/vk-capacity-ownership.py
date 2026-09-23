#!/usr/bin/env python3
"""Authenticated ownership RPCs, not a service switch or deployment authorization.

Fence callers and drain executions before release. Persist its receipt before
freezing the old owner. Acquire requires that exact receipt's epoch/revision.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import urllib.error
import urllib.parse
import urllib.request


def request(origin, token_file, action='status', receipt=None):
    url = urllib.parse.urlsplit(origin)
    if (url.scheme != 'http' or url.hostname not in ('127.0.0.1', '::1', 'localhost')
            or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment):
        raise ValueError('Use the direct loopback backend origin, not the public gateway')
    if action not in ('status', 'release', 'acquire'):
        raise ValueError('Unknown ownership action')
    path = Path(token_file)
    metadata = path.lstat()
    if not path.is_absolute() or not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        raise ValueError('Token must be a private regular file owned by this user')
    token = path.read_text().strip()
    if len(token) < 32:
        raise ValueError('Invalid token length')
    body = None
    suffix = ''
    if action != 'status':
        if (not isinstance(receipt, dict) or not isinstance(receipt.get('epoch'), str)
                or not receipt['epoch'] or type(receipt.get('revision')) is not int or receipt['revision'] < 0):
            raise ValueError('Expected explicit ownership epoch and revision')
        body = json.dumps({'epoch': receipt['epoch'], 'revision': receipt['revision']}).encode()
        suffix = '/' + action
    req = urllib.request.Request(origin.rstrip('/') + '/api/capacity/ownership' + suffix,
        data=body, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise ValueError('Backend lacks ownership handover support; do not freeze it for this protocol') from error
        raise
    if result.get('protocolVersion') != 1:
        raise ValueError('Unsupported ownership protocol')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['status', 'release', 'acquire'])
    p.add_argument('--origin', required=True)
    p.add_argument('--token-file', required=True, type=Path)
    p.add_argument('--receipt', type=Path, help='JSON state or ownership response from the last owner')
    args = p.parse_args()
    receipt = json.loads(args.receipt.read_text()) if args.receipt else None
    if isinstance(receipt, dict) and 'state' in receipt:
        receipt = receipt['state']
    print(json.dumps(request(args.origin, args.token_file, args.action, receipt)))


if __name__ == '__main__':
    main()
