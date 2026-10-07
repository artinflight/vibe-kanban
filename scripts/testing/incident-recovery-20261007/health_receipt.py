"""Read-only live checks and preservation of the unintended new legacy DB."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time
import urllib.request
from place_missing import ROOT, save

legacy = Path('/home/mcp/.local/share/vibe-kanban/db.v2.sqlite')
snapshot = ROOT / 'unintended-legacy-database.sqlite'
assert not snapshot.exists() and not Path('/proc/2670802').exists()
with closing(sqlite3.connect(legacy.as_uri() + '?mode=ro', uri=True)) as source:
    with closing(sqlite3.connect(snapshot)) as destination:
        source.backup(destination)
        legacy_check = destination.execute('PRAGMA integrity_check').fetchone()[0]
        legacy_executions = destination.execute('SELECT count(*) FROM execution_processes').fetchone()[0]
prod = Path('/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban/db.v2.sqlite')
with closing(sqlite3.connect(prod.as_uri() + '?mode=ro', uri=True)) as db:
    quick = db.execute('PRAGMA quick_check').fetchone()[0]
    running = db.execute("SELECT count(*) FROM execution_processes WHERE status='running'").fetchone()[0]
    saved = db.execute('SELECT count(*) FROM saved_chat_messages').fetchone()[0]
request = urllib.request.urlopen('http://127.0.0.1:5511/api/info', timeout=5)
data = json.load(request)
units = subprocess.check_output(['systemctl', '--user', 'show',
    'vibe-kanban-green-production-20261005.service', 'codexusage-preview.service',
    'vibe-kanban-blue-production-20261004.service', '-p', 'Id', '-p', 'MainPID',
    '-p', 'ActiveState', '-p', 'FreezerState'], text=True)
exe = Path('/proc/3027197/exe')
receipt = {'at': time.time(), 'production_http': request.status, 'version': data['data']['version'],
    'production_pid': 3027197, 'binary_sha256': hashlib.file_digest(exe.open('rb'), 'sha256').hexdigest(),
    'production_quick_check': quick, 'running_execution_count': running, 'saved_message_count': saved,
    'route': json.loads(Path('/mnt/vk-storage/vk-cutover-20260911/production-route.json').read_text()),
    'services': units, 'unintended_pid_gone': True,
    'unintended_db_not_in_baseline_69': True, 'unintended_db_integrity': legacy_check,
    'unintended_db_execution_count': legacy_executions,
    'unintended_db_snapshot_sha256': hashlib.file_digest(snapshot.open('rb'), 'sha256').hexdigest(),
    'production_database_restored': False, 'production_cutover_performed': False}
save(ROOT / 'health.json', receipt)
print(json.dumps({k: receipt[k] for k in ['production_http', 'version', 'production_quick_check',
    'running_execution_count', 'saved_message_count', 'unintended_db_execution_count']}))
