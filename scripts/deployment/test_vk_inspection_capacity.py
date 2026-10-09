"""Host-sized output/real pipe regression; no root entrypoint or sudo invocation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch

import vk_retirement_preflight as client
import vk_historical_archive_preflight as archive
from test_vk_retirement_preflight import Fixtures, root
import test_vk_retirement_preflight as existing


class CapacityTests(Fixtures):
    def large_receipt(self, tasks=16384, processes=425):
        receipt = self.receipt(self.request)
        witness = [[100000 + i % processes, 100000 + i, '123456789'] for i in range(tasks)]
        receipt['visibility'].update(processes=processes, tasks=tasks, witness=witness)
        return receipt

    def test_large_host_both_profile_encoding_full_witness_and_client_validation(self):
        for historical in (False, True):
            receipt = self.large_receipt()
            if historical: receipt.update(profile=archive.PROFILE, library_sha256='c'*64)
            wire = root.encode_receipt(receipt).encode() + b'\n'
            self.assertGreater(len(wire), 65536)
            self.assertLess(len(wire), client.MAX_RECEIPT)
            checker = Mock(returncode=0)
            checker.communicate.return_value = (wire, None)
            actual = client.finish_checker(checker, self.request)
            self.assertEqual(actual['visibility']['witness'], receipt['visibility']['witness'])
            inventory = {tuple(row) for row in receipt['visibility']['witness']}
            before = time.monotonic()
            with patch.object(client, 'task_inventory', return_value=inventory):
                if historical:
                    archive.validate_receipt(actual, self.request, {**self.installation, 'library_sha256':'c'*64})
                else:
                    client.validate_receipt(actual, self.request, self.installation)
            self.assertLess(time.monotonic()-before, 5)

    def test_real_subprocess_pipe_above_old_64k_does_not_deadlock_or_truncate(self):
        receipt = self.large_receipt(tasks=8192)
        path = self.base / 'large.safe.json'
        path.write_bytes(root.encode_receipt(receipt).encode()+b'\n')
        child = subprocess.Popen([sys.executable, '-I', '-S', '-B', '-c',
            'import sys; from pathlib import Path; sys.stdin.buffer.read(); sys.stdout.buffer.write(Path(sys.argv[1]).read_bytes())',
            str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        result = client.finish_checker(child, self.request)
        self.assertEqual(result['visibility']['witness'], receipt['visibility']['witness'])
        self.assertEqual(result['visibility']['tasks'],8192)

    def test_output_oversize_still_fails_closed_root_and_client(self):
        with self.assertRaises(ValueError): root.encode_receipt(self.large_receipt(tasks=40000))
        child = Mock(returncode=0)
        child.communicate.return_value = (b' '* (client.MAX_RECEIPT+1),None)
        with self.assertRaises(ValueError): client.finish_checker(child, self.request)

    def test_request_status_input_limit_not_expanded(self):
        self.assertEqual(root.MAX_JSON,65536)
        self.assertEqual(root.MAX_RECEIPT,client.MAX_RECEIPT)
        with self.assertRaises(ValueError): root.parse_json(b' '*65537)

    def test_exact_output_bound_includes_newline(self):
        with patch.object(root,'MAX_RECEIPT', len(root.encode_receipt({'ok':True}).encode())):
            with self.assertRaises(ValueError): root.encode_receipt({'ok':True})

    def test_large_witness_still_rejects_new_uninspected_task_and_stale_result(self):
        receipt=self.large_receipt()
        with patch.object(client,'task_inventory',return_value={(9999999,9999999,'1')}):
            with self.assertRaises(ValueError): client.validate_receipt(receipt,self.request,self.installation)
        receipt['issued_ns']-=6_000_000_000
        with self.assertRaises(ValueError): client.validate_receipt(receipt,self.request,self.installation)

    def test_anonymous_fast_path_retains_zero_target_and_later_file_consumer(self):
        scanner=existing.ScanTests()
        proc,task=scanner.make_proc(maps='0-1 rw-p 0 00:00 0\n')
        self.assertEqual(root.scan_consumers({(99,999)},proc=proc)['tasks'],1)
        with self.assertRaises(ValueError): root.scan_consumers({(0,0)},proc=proc)
        target=proc/'target';target.write_bytes(b'full coverage')
        info=target.stat()
        with (task/'maps').open('a') as stream:
            stream.write(f'1-2 r--p 0 {os.major(info.st_dev):x}:{os.minor(info.st_dev):x} {info.st_ino} protected\n')
        with self.assertRaises(ValueError): root.scan_consumers({(info.st_dev,info.st_ino)},proc=proc)
        (task/'maps').write_text('0-1 rw-p 0 malformed 0\n')
        with self.assertRaises(ValueError): root.scan_consumers({(99,999)},proc=proc)

    def test_historical_root_entry_uses_shared_bounded_encoder(self):
        source=(Path(__file__).parent/'security/vk_historical_archive_check.py').read_text()
        self.assertIn('print(common.encode_receipt(result))',source)


if __name__=='__main__': unittest.main()
