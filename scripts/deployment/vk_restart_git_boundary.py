"""Opt-in check-all consumer; production writer-fence/controller binding unadopted.

Callbacks are trusted controller code, not request booleans or a same-UID security
boundary. read_binding must enumerate ALL authoritative latest affected turns,
original ledgers and the authenticated operation owner. writer_fence must keep
those writers excluded through handover, using the EXISTING real lifecycle gate.
This adapter creates no fence, policy, historical receipt, publication or grants.
"""
from contextlib import contextmanager
import hashlib
import json
import os
import selectors
import signal
from pathlib import Path
import subprocess
import sys
import time

HELPER_SHA256 = 'd921135c0f784d06fe3f2ced25fdead8a1da749b047c7d88c6bfd6c9a85a9e34'
MAX_JSON = 16 * 1024**2


def digest(value):
    # Same canonicalization as the audited schema-2 Git helper.
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def require(ok, reason):
    if not ok:
        raise ValueError('Git boundary: ' + reason)


def read_pinned(path, expected):
    path = Path(path)
    require(path.is_absolute() and not path.is_symlink(), 'fixed input path required')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected, 'fixed helper/policy changed')
    return raw


def invoke_check_all(helper, policy, request, timeout):
    """Fixed argv, bounded pipe transport and exact-child cleanup; no shell."""
    payload = json.dumps(request).encode()
    require(len(payload) <= MAX_JSON and 0 < timeout <= 600, 'bounded request/time required')
    process = subprocess.Popen([sys.executable, '-B', '-S', str(helper), 'check-all',
                                '--config', str(policy)], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + timeout
    output = bytearray(); offset = 0
    try:
        with selectors.DefaultSelector() as poll:
            for stream, events in ((process.stdin, selectors.EVENT_WRITE), (process.stdout, selectors.EVENT_READ)):
                os.set_blocking(stream.fileno(), False); poll.register(stream, events)
            while poll.get_map():
                left = deadline - time.monotonic()
                require(left > 0, 'check-all timeout')
                for key, event in poll.select(left):
                    if key.fileobj is process.stdin:
                        offset += os.write(key.fd, payload[offset:offset + 65536])
                        if offset == len(payload):
                            poll.unregister(key.fileobj); key.fileobj.close()
                    else:
                        block = os.read(key.fd, 65536)
                        if not block:
                            poll.unregister(key.fileobj); key.fileobj.close()
                        else:
                            output.extend(block)
                            require(len(output) <= MAX_JSON, 'check-all response bound exceeded')
            code = process.wait(timeout=max(0.001, deadline - time.monotonic()))
        return code, bytes(output)
    finally:
        if process.poll() is None:
            # The fixed helper and its synchronous Git/scanner children belong
            # to this newly created session, never an incumbent/agent unit.
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        for stream in (process.stdin, process.stdout):
            if not stream.closed: stream.close()


class HeldGitCheck:
    def __init__(self, helper, policy, policy_sha256, expected_binding_sha256,
                 read_binding, writer_fence):
        self.helper, self.policy = Path(helper), Path(policy)
        self.policy_sha256 = policy_sha256
        self.expected = expected_binding_sha256
        self.read_binding, self.writer_fence = read_binding, writer_fence

    def binding(self):
        value = self.read_binding()
        require(type(value) is dict and set(value) == {'owner', 'turns', 'ledgers'},
                'authoritative owner/inventory/original ledgers missing')
        require(type(value['owner']) is dict and bool(value['owner']), 'authenticated operation owner missing')
        require(type(value['turns']) is list and bool(value['turns']), 'complete latest-turn inventory missing')
        keys = [(t['workspace'], t['turn']) for t in value['turns']]
        require(len(set(keys)) == len(keys), 'duplicate latest-turn inventory')
        require(set(value['ledgers']) == {w + '/' + t for w, t in keys}, 'original ledger inventory differs')
        require(digest(value) == self.expected, 'owner/inventory/original ledger changed')
        return json.loads(json.dumps(value))

    @contextmanager
    def held(self, remaining):
        # All code paths are fixed; no shell or command string from a manifest.
        read_pinned(self.helper, HELPER_SHA256)
        policy = json.loads(read_pinned(self.policy, self.policy_sha256))
        before = self.binding()
        with self.writer_fence(before) as fence:
            require(not isinstance(fence, (dict, bool)) and callable(getattr(fence, 'assert_held', None)),
                    'actual controller writer-fence capability required; boolean is insufficient')
            require(fence.assert_held(before) is None, 'writer-fence verification must raise on failure')
            require(self.binding() == before, 'inventory changed while entering writer fence')
            # This boolean satisfies the helper wire ABI ONLY after actual gate
            # verification. It cannot establish exclusion on its own.
            request = {'writers_fenced': True, 'turns': before['turns']}
            started = time.time()
            code, raw = invoke_check_all(self.helper, self.policy, request, min(600, remaining()))
            require(code == 0, 'check-all exit status rejected')
            output = json.loads(raw)
            require(type(output) is dict and output.get('version') == 2
                    and output.get('state') == 'verified'
                    and output.get('scope') == 'eligible-repository-work-only', 'schema-2 verified output required')
            checked = output.get('checked_at')
            require(type(checked) in (int, float) and started - 1 <= checked <= time.time() + 1,
                    'fresh check-all timestamp required')
            turns = output.get('turns')
            require(type(turns) is list and len(turns) == len(before['turns']), 'complete verified output inventory required')
            for expected, found in zip(before['turns'], turns):
                key = expected['workspace'] + '/' + expected['turn']
                ledger = before['ledgers'][key]
                require(ledger.get('version') == 2 and ledger.get('state') == 'verified'
                        and ledger.get('config') == digest(policy)
                        and type(ledger.get('obligations')) is dict and bool(ledger['obligations']),
                        'policy/original ledger not verified')
                require(found.get('version') == 2 and found.get('state') == 'verified'
                        and (found.get('workspace'), found.get('turn')) == (expected['workspace'], expected['turn'])
                        and found.get('receipt_digest') == digest(ledger)
                        and found.get('repositories') == ledger.get('repositories'), 'ledger/turn/output binding differs')
            # Hold and revalidate the original actual controller gate, not a
            # receipt loop. Owner/ledger/inventory must remain pinned through use.
            require(fence.assert_held(before) is None, 'writer fence released during check-all')
            require(self.binding() == before, 'original ledger changed during check-all')
            read_pinned(self.policy, self.policy_sha256)
            read_pinned(self.helper, HELPER_SHA256)
            witness = {'version': 2, 'state': 'verified', 'binding_sha256': self.expected,
                       'policy_sha256': self.policy_sha256, 'helper_sha256': HELPER_SHA256,
                       'check_all_sha256': digest(output)}
            yield witness
            require(fence.assert_held(before) is None, 'writer fence released before handover completed')
            require(self.binding() == before, 'owner/inventory/ledger changed through handover')
