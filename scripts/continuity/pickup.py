#!/usr/bin/env python3
"""Verify lossless pickup archives or locate a dated section without dumping history."""

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def manifest(root=ROOT):
    return json.loads((root / "CONTINUITY_ARCHIVE.json").read_text())


def verify(root=ROOT):
    data = manifest(root)
    if data["schema"] != 1 or data["mandatory_budget_bytes"] != 16384:
        raise ValueError("Unsupported continuity schema or changed pickup budget")
    total = 0
    for row in data["archives"]:
        archive = root / row["archive"]
        raw = archive.read_bytes()
        if archive.is_symlink() or len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Historical pickup evidence changed: " + row["archive"])
        headings = [{"line": i, "heading": line} for i, line in enumerate(raw.decode().splitlines(), 1)
                    if re.match(r"^#{1,6} ", line)]
        if headings != row["sections"]:
            raise ValueError("Archive section catalogue changed: " + row["archive"])
        current = root / row["original"]
        if row["archive"] not in current.read_text():
            raise ValueError("Pickup index must link its complete archive")
        total += current.stat().st_size
    if total > data["mandatory_budget_bytes"]:
        raise ValueError("Mandatory pickup exceeds combined 16 KiB budget; move detail into topic guides")
    return {"passed": True, "historical_bytes_preserved": sum(r["bytes"] for r in data["archives"]),
            "mandatory_bytes": total, "budget_bytes": data["mandatory_budget_bytes"]}


def find(query, root=ROOT):
    """Return locators only, including duplicate headings as distinct sections."""
    if not query.strip():
        raise ValueError("Supply a specific topic")
    matches = []
    for row in manifest(root)["archives"]:
        for i, section in enumerate(row["sections"]):
            if query.casefold() in section["heading"].casefold():
                end = row["sections"][i + 1]["line"] - 1 if i + 1 < len(row["sections"]) else None
                matches.append({"archive": row["archive"], **section, "through_line": end})
    return matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("check")
    lookup = sub.add_parser("find")
    lookup.add_argument("query")
    args = parser.parse_args()
    print(json.dumps(verify() if args.action == "check" else find(args.query), indent=2))


if __name__ == "__main__":
    main()
