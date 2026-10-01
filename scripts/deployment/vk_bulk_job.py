#!/usr/bin/env python3
"""Run bulky preparation outside the Codex memory cgroup, within explicit limits."""
import argparse
from pathlib import Path
import re
import subprocess
import time
import uuid
from vk_prep_common import save, storage


def run(root, command, *, cwd, memory_high="4G", memory_max="6G"):
    root = storage(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not command or any(not re.fullmatch(r"[1-9][0-9]*[MG]", value) for value in (memory_high, memory_max)):
        raise ValueError("Specify a command and finite memory limits")
    sizes = [int(value[:-1]) * (1024 if value[-1] == "G" else 1) for value in (memory_high, memory_max)]
    if sizes[0] > sizes[1]:
        raise ValueError("MemoryHigh must not exceed MemoryMax")
    unit = "vk-preparation-bulk-" + uuid.uuid4().hex
    argv = ["systemd-run", "--user", "--collect", "--wait", "--pipe", "--unit", unit,
            "--working-directory", str(Path(cwd).resolve()),
            "-p", "MemoryHigh=" + memory_high, "-p", "MemoryMax=" + memory_max,
            "-p", "CPUWeight=50", "-p", "IOWeight=50", "--setenv", "TMPDIR=" + str(root), "--", *command]
    started = time.monotonic()
    result = subprocess.run(argv)
    save(root / (unit + ".json"), {"unit": unit, "memory_high": memory_high, "memory_max": memory_max,
        "seconds": time.monotonic() - started, "exit_code": result.returncode, "production_services_changed": False})
    return result.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--cwd", required=True, type=Path)
    parser.add_argument("--memory-high", default="4G")
    parser.add_argument("--memory-max", default="6G")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    raise SystemExit(run(args.root, command, cwd=args.cwd, memory_high=args.memory_high, memory_max=args.memory_max))
