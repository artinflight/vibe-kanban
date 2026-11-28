"""Small read-only HUD projection embedded in the existing public progress page.

No new endpoint, service, dispatcher, source-log scan or controller mutation.
Only fixed counters and safe state tokens are published, never paths or errors.
"""
import json
import re
from pathlib import Path


def integer(value):
    if type(value) not in (int, float) or not 0 <= value <= 10**16:
        raise ValueError('invalid HUD counter')
    return int(value)


def token(value):
    value = str(value).lower()
    return value if re.fullmatch('[a-z][a-z0-9_]{0,95}', value) else 'unavailable'


def payload(config, result):
    source = result.get('source') or {}
    if result.get('source_error') or not source.get('total_files'):
        return dict(version=1, observed=integer(result['at']), state='unavailable')
    values = dict(version=1, observed=integer(result['at']),
                  progress=integer(source.get('progress_at', 0)),
                  state=token(source.get('state', 'unavailable')),
                  phase=token(source.get('phase', 'unavailable')))
    for name in ('completed_files', 'resolved_files', 'total_files',
                 'completed_batches', 'total_batches', 'completed_raw_bytes'):
        values[name] = integer(source.get(name, 0))
    if not (values['completed_files'] <= values['resolved_files'] <= values['total_files']
            and values['completed_batches'] <= values['total_batches']):
        raise ValueError('inconsistent HUD counters')
    values['reclaimed_bytes'] = -1
    path = Path(config['operation_root']) / 'COMMITTED.private.json'
    if path.stat().st_size > 8 * 1024**2:
        raise ValueError('oversized committed receipt')
    committed = json.loads(path.read_bytes())
    if (committed['operation'] != config['operation']
            or any(committed.get(k) != source.get(k) for k in
                   ('completed_files', 'completed_batches', 'completed_raw_bytes'))):
        return values  # A new commit raced this snapshot: omit savings, never guess.
    values['reclaimed_bytes'] = integer(committed.get('canary_live_log_allocated_recovery', 0)) + sum(
        integer(row['allocated_release']) for row in committed['batches'])
    return values


def embed(html, config, result):
    try:
        values = payload(config, result)
    except (OSError, ValueError, KeyError, TypeError):
        values = dict(version=1, observed=integer(result['at']), state='unavailable')
    lines = '\n'.join(f'{key}={value}' for key, value in values.items())
    block = '<!-- VK_DEDUP_HUD_V1\n' + lines + '\nEND_VK_DEDUP_HUD -->\n'
    return html.replace('</html>', block + '</html>')
