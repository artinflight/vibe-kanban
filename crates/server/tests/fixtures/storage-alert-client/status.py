#!/usr/bin/env python3
"""Private read-only status. Output is an operational receipt, never a Git artifact."""
import argparse
import json
from pathlib import Path
import sqlite3


def status(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        return {table: [dict(row) for row in db.execute(query)] for table, query in (
            ('incidents', 'SELECT * FROM incidents ORDER BY opened DESC LIMIT 20'),
            ('batches', 'SELECT * FROM batches ORDER BY created DESC LIMIT 20'),
            ('volume_state', 'SELECT * FROM volume_state'),
            ('incident_evidence', 'SELECT * FROM incident_evidence LIMIT 20'),
            ('attempts', 'SELECT * FROM attempts ORDER BY at DESC LIMIT 20'),
            ('phones', 'SELECT * FROM phones'),
            ('audit', 'SELECT * FROM audit ORDER BY id DESC LIMIT 30'))}
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('state')
    args = p.parse_args()
    try:
        print(json.dumps(status(args.state), indent=2))
    except Exception:
        raise SystemExit('State unavailable; no state was created or reset')
