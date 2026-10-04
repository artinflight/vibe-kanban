"""Whole-unit writer fencing; preserve children and pipes for same-process thaw."""
from pathlib import Path
import subprocess


def process_identity(pid):
    proc = Path("/proc") / str(pid)
    fields = (proc / "stat").read_text().rpartition(") ")[2].split()
    executable = (proc / "exe").stat()
    return {"pid": int(pid), "start": fields[19], "device": executable.st_dev,
            "inode": executable.st_ino, "cgroup": (proc / "cgroup").read_text().strip()}


def prop(unit, key):
    return subprocess.check_output(["systemctl", "--user", "show", unit, "-p", key, "--value"], text=True).strip()


class ServiceFence:
    def __init__(self, unit, expected, validate_children, *, approved=False):
        if not approved or not unit.endswith(".service") or "/" in unit:
            raise ValueError("Whole-unit pause requires an explicitly coordinated service")
        self.unit, self.expected, self.validate_children = unit, expected, validate_children

    def identity(self):
        if prop(self.unit, "MainPID") != str(self.expected["pid"]):
            raise ValueError("Writer service restarted")
        if process_identity(self.expected["pid"]) != self.expected:
            raise ValueError("Writer identity changed")

    def preflight(self):
        self.identity()
        if prop(self.unit, "FreezerState") != "running":
            raise ValueError("Writer is already frozen")
        self.validate_children(False)

    def freeze(self):
        self.preflight()
        subprocess.run(["systemctl", "--user", "freeze", self.unit], check=True, timeout=10)
        try:
            self.verify()
        except Exception:
            self.thaw()
            raise

    def verify(self):
        self.identity()
        if prop(self.unit, "FreezerState") != "frozen":
            raise ValueError("Whole writer unit is not frozen")
        self.validate_children(True)
        return {"verified": True, "unit": self.unit, "identity": self.expected}

    def thaw(self):
        # Never resume a replacement process under an old approval.
        self.identity()
        subprocess.run(["systemctl", "--user", "thaw", self.unit], check=True, timeout=10)
        if prop(self.unit, "FreezerState") != "running":
            raise ValueError("Writer unit did not thaw")
