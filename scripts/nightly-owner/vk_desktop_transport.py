"""Resumable Desktop delivery; retain SSH host identity and verify full SHA256."""
from pathlib import Path, PurePosixPath
import re
import subprocess
import time
import uuid

from vk_prep_common import digest, storage


class DesktopTransport:
    def __init__(self, staging, *, hostname=None, host_key_alias=None):
        self.staging = storage(staging)
        self.staging.mkdir(parents=True, exist_ok=True, mode=0o700)
        if bool(hostname) != bool(host_key_alias):
            raise ValueError("A direct address requires the existing verified Desktop host-key alias")
        if any(value and not re.fullmatch(r"[A-Za-z0-9.:_-]+", value)
               for value in (hostname, host_key_alias)):
            raise ValueError("Unsafe SSH identity option")
        self.options = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                        "-o", "StrictHostKeyChecking=yes", "-o", "ControlMaster=no", "-o", "ControlPath=none"]
        if hostname:
            self.options.extend(["-o", "Hostname=" + hostname, "-o", "HostKeyAlias=" + host_key_alias])
        self.retries = 0

    def command(self, command, timeout=60):
        for attempt in range(3):
            try:
                return subprocess.check_output(["ssh", *self.options, "desktop", command],
                    text=True, stderr=subprocess.PIPE, timeout=timeout).strip()
            except subprocess.CalledProcessError as error:
                if (error.returncode != 255 or "exec request failed on channel" not in (error.stderr or "")
                        or attempt == 2):
                    raise
                self.retries += 1
                time.sleep(1)

    def mirror(self, archive, destination):
        from vk_archive_stream import StreamingArchive, receiver_command
        if isinstance(archive, StreamingArchive):
            return archive.deliver(destination, receiver_command(self.options))
        if (not re.fullmatch(r"B:/vk-backups/[A-Za-z0-9_./-]+", destination)
                or ".." in PurePosixPath(destination).parts):
            raise ValueError("Use a Desktop B:/vk-backups task directory")
        archive = storage(archive)
        if (not archive.is_file() or not re.fullmatch(r"[A-Za-z0-9_.-]+", archive.name)
                or any(character in str(archive) for character in ('"', '\\', '\n', '\r'))):
            raise ValueError("Invalid archive")
        retries = self.retries
        self.command("powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path '" + destination + "' | Out-Null\"")
        if archive.stat().st_size < 10_000_000:
            subprocess.run(["scp", *self.options, str(archive), "desktop:" + destination + "/"], check=True, timeout=1800)
        else:
            remote = destination + "/" + archive.name
            size = int(self.command("powershell -NoProfile -Command \"if (Test-Path -LiteralPath '" + remote +
                "') { (Get-Item -LiteralPath '" + remote + "').Length } else { -1 }\""))
            if not -1 <= size <= archive.stat().st_size:
                raise ValueError("Unexpected remote size; reconcile before writing")
            verb = "put" if size == -1 else "reput"
            batch = self.staging / ("sftp-" + uuid.uuid4().hex + ".batch")
            batch.write_text(verb + ' "' + str(archive) + '" "/' + remote + '"\n')
            batch.chmod(0o600)
            try:
                subprocess.run(["sftp", *self.options, "-b", str(batch), "desktop"], check=True, timeout=1800)
            finally:
                batch.unlink()
        remote_hash = self.command("powershell -NoProfile -Command \"(Get-FileHash -Algorithm SHA256 -LiteralPath '" +
            destination + "/" + archive.name + "').Hash\"", timeout=1800).lower()
        checksum = digest(archive)
        if remote_hash != checksum:
            raise ValueError("Desktop full-file checksum mismatch")
        return {"name": archive.name, "sha256": checksum, "bytes": archive.stat().st_size,
                "desktop_verified": True, "desktop_directory": destination,
                "transient_command_retries": self.retries - retries}
