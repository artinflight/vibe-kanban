"""Exercise real process/network events, never operational retirement or root proof."""
import ast
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

DRIVER = Path(__file__).resolve().parents[2] / 'deployment/receipts/retire-approved-single-incident-archive-prepare-first-20261009.py'
HELPER = DRIVER.with_name('excluded-incident-archive-consumer-check-threads-readonly.py')


class PrepareFirstOrderingTests(unittest.TestCase):
    def run_child(self, operation):
        tree = ast.parse(DRIVER.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == 'seal_managed_orchestration')
        code = 'import sys, subprocess, socket, os\n' + ast.unparse(function) + '\n' + operation
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_real_child_before_clearance_late_spawn_rejected(self):
        output = self.run_child("""
child = subprocess.Popen(['/bin/true'])
print('prepared-child-pid:' + str(child.pid), flush=True)
assert child.wait() == 0
seal_managed_orchestration()
try:
    subprocess.Popen(['/bin/true'])
except RuntimeError as error:
    assert 'forbidden after preparation' in str(error)
    print('late-child-blocked')
else:
    raise AssertionError('post-clearance process was created')
""")
        self.assertIn('prepared-child-pid:', output)
        self.assertIn('late-child-blocked', output)

    def test_real_fork_and_shell_rejected_after_clearance(self):
        output = self.run_child("""
seal_managed_orchestration()
for attempt in (os.fork, lambda: os.system('/bin/true')):
    try:
        attempt()
    except RuntimeError as error:
        assert 'process creation forbidden' in str(error)
    else:
        raise AssertionError('late fork/shell was allowed')
print('fork-and-shell-blocked')
""")
        self.assertIn('fork-and-shell-blocked', output)

    def test_real_tcp_and_unrelated_unix_connections_rejected(self):
        output = self.run_child("""
seal_managed_orchestration()
for family, address in ((socket.AF_INET, ('127.0.0.1', 5511)),
                        (socket.AF_UNIX, '/tmp/unrelated-ssh-control')):
    with socket.socket(family) as client:
        try:
            client.connect(address)
        except RuntimeError as error:
            assert 'network/channel creation forbidden' in str(error)
        else:
            raise AssertionError('late network/channel attempt was allowed')
print('network-and-channel-blocked')
""")
        self.assertIn('network-and-channel-blocked', output)

    def test_nonleader_private_descriptor_is_inspected(self):
        spec = importlib.util.spec_from_file_location('thread_fixture', HELPER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root = Path(tempfile.mkdtemp(prefix='retirement-thread-fixture-',
                                    dir='/mnt/vk-storage/vk-runtime-backup-20261009'))
        proc = root / 'proc'
        process = proc / '1000'
        process.mkdir(parents=True)
        stat_text = '1000 (fixture) S ' + '0 ' * 18 + '10\n'
        (process / 'stat').write_text(stat_text)
        for tid in ('1000', '1001'):
            task = process / 'task' / tid
            (task / 'fd').mkdir(parents=True)
            (task / 'stat').write_text(stat_text)
            (task / 'comm').write_text('fixture\n')
            (task / 'maps').write_text('')
        archive = root / 'fixture-archive'
        archive.write_bytes(b'thread-private fixture only')
        (process / 'task/1001/fd/7').symlink_to(archive)
        info = archive.stat()
        module.PROC = proc
        result = module.inspect_tasks({(info.st_dev, info.st_ino)})
        self.assertEqual(result['matches'], [{'pid': 1000, 'tid': 1001, 'kind': 'fd'}])
        self.assertEqual(result['new_uninspected_tasks'], [])

    def test_task_birth_during_traversal_is_explicitly_unproven(self):
        spec = importlib.util.spec_from_file_location('birth_fixture', HELPER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        newborn = (1000, 10, 1001, 11)
        with patch.object(module, 'task_inventory', side_effect=[set(), {newborn}]):
            result = module.inspect_tasks(set())
        self.assertEqual(result['new_uninspected_tasks'], [newborn])

    def test_expiry_during_actual_proof_fsync_preserves_archive(self):
        # Execute the driver's exact proof-write/late-age/unlink block on a
        # generated fixture. Delay a real fsync across the receipt lifetime.
        tree = ast.parse(DRIVER.read_text())
        age_function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                            and node.name == 'require_final_age')
        body = next(node for node in tree.body if isinstance(node, ast.Try)).body
        start = next(i for i, node in enumerate(body) if isinstance(node, ast.With)
                     and 'single-incident-retirement-prepared-boundary' in ast.unparse(node))
        statements = body[start:start + 3]
        self.assertIn('require_final_age(r)', ast.unparse(statements[1]))
        self.assertIn('os.unlink', ast.unparse(statements[2]))
        root = Path(tempfile.mkdtemp(prefix='retirement-expiry-fixture-',
                                    dir='/mnt/vk-storage/vk-runtime-backup-20261009'))
        archive = root / 'fixture-archive'
        archive.write_bytes(b'preserve on expiry')
        parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        issued = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=59.9)
        def require(value, message):
            if not value:
                raise RuntimeError(message)
        namespace = dict(os=os, json=json, time=time, datetime=datetime, require=require,
                         b=root, target=archive, parent=parent, proof={'fixture': True},
                         r={'utc': issued.isoformat()})
        exec(compile(ast.Module(body=[age_function], type_ignores=[]), '<age-function>', 'exec'), namespace)
        real_fsync = os.fsync
        def slow_fsync(fd):
            real_fsync(fd)
            time.sleep(0.15)
        try:
            with patch.object(os, 'fsync', slow_fsync), self.assertRaisesRegex(RuntimeError, 'expired before unlink'):
                exec(compile(ast.Module(body=statements, type_ignores=[]), '<actual-continuation-block>', 'exec'), namespace)
        finally:
            os.close(parent)
        self.assertEqual(archive.read_bytes(), b'preserve on expiry')


if __name__ == '__main__':
    unittest.main()
