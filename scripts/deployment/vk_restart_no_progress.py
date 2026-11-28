"""Independent no-progress supervisor; elapsed operation time is never a cutoff."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time


class NoProgress(TimeoutError):
    pass


def token(path):
    try:
        return json.loads(Path(path).read_text()).get('sequence')
    except (FileNotFoundError, ValueError):
        return None


def supervise(command, progress, *, idle_seconds=600, interval=1, grace_seconds=10):
    """Terminate only our child process group, retaining independent recovery.

    The worker advances sequence on completed work/data progress, never on a
    timer or a successful liveness/health poll. stdout is inherited, not piped.
    """
    if idle_seconds <= 0 or interval <= 0:
        raise ValueError('Positive no-progress interval required')
    child = subprocess.Popen(command, start_new_session=True)
    last = token(progress)
    changed = time.monotonic()
    try:
        while child.poll() is None:
            current = token(progress)
            if current is not None and current != last:
                last = current
                changed = time.monotonic()
            if time.monotonic() - changed >= idle_seconds:
                raise NoProgress('No verified operation progress for ' + str(idle_seconds) + ' seconds')
            time.sleep(interval)
        if child.returncode:
            raise subprocess.CalledProcessError(child.returncode, command)
        return child.returncode
    except BaseException:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=grace_seconds)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
        raise
