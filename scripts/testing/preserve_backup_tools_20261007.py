"""Preserve the new verified tool package on B; never publish a failed backup."""
import json
from pathlib import Path
import subprocess
import sys

root = Path('/mnt/vk-storage/vk-desktop-provider-20261007')
package = root / 'recovery-package-6db1a43e1'
sys.path.insert(0, str(package / 'tools'))
from vk_recovery_package import verify
from vk_desktop_transport import DesktopTransport

verification = verify(package)
assert verification['source_commit'] == '6db1a43e1bc10e991c5a9bfd27f3400166ec6594'
archive = root / 'desktop-provider-recovery-6db1a43e1.tar.gz'
assert not archive.exists()
subprocess.run(['tar', '-czf', str(archive), '-C', str(root), package.name], check=True)
transport = DesktopTransport(root / 'transport-6db1a43e1', hostname='10.0.0.109',
                             host_key_alias='100.70.23.123')
receipt = transport.mirror(archive, 'B:/vk-backups/vk-desktop-provider-20261007')
with (root / 'recovery-package-6db1a43e1-desktop.json').open('x') as stream:
    json.dump({'package': verification, 'receipt': receipt, 'production_changed': False,
               'failed_checkpoint_accepted': False}, stream, indent=2)
print(json.dumps(receipt))
