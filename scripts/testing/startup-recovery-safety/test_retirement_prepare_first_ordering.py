"""Exercise real process/network events, never operational retirement or root proof."""
import ast
from pathlib import Path
import subprocess
import sys
import unittest

DRIVER = Path(__file__).resolve().parents[2] / 'deployment/receipts/retire-approved-single-incident-archive-prepare-first-20261009.py'


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


if __name__ == '__main__':
    unittest.main()
