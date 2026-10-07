"""Preserve parseable current-turn edit evidence without rewriting the transcript."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
source = ROOT / 'original-thread.jsonl'
calls, errors, kinds = [], [], {}
for number, line in enumerate(source.open('rb'), 1):
    try:
        row = json.loads(line)
    except (ValueError, UnicodeError):
        errors.append({'line': number, 'sha256': hashlib.sha256(line).hexdigest()})
        continue
    if row.get('timestamp', '') < '2026-10-07T22:47:00':
        continue
    payload = row.get('payload', {})
    key = str((row.get('type'), payload.get('type'), payload.get('name')))
    kinds[key] = kinds.get(key, 0) + 1
    if payload.get('type') in ('function_call', 'custom_tool_call'):
        calls.append({'line': number, 'timestamp': row.get('timestamp'), 'payload': payload})
result = {'calls': calls, 'parse_failures_preserved': errors, 'kinds': kinds,
          'source_sha256': hashlib.file_digest(source.open('rb'), 'sha256').hexdigest()}
(ROOT / 'current-turn-tool-calls.json').write_text(json.dumps(result, indent=2))
print(json.dumps({'calls': len(calls), 'unparseable_historical_lines': len(errors), 'kinds': kinds}))
