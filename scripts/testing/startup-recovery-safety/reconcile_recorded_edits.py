#!/usr/bin/env python3
"""Read-only, hash-bound replay of recorded owner patches against a Git commit.

Only textual patches are interpreted. Recorded shell/JavaScript is never run.
This certifies named edited contents only, never journal coverage or zero loss.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

from replay_recorded_patch import relative_name, replay

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('recovery_audit', REPO / 'scripts/verify_recovered_tree.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def literal_patches(payload):
    source = payload.get('input', payload.get('arguments', ''))
    if source.startswith('*** Begin Patch') and payload.get('name') in ('apply_patch', 'functions.apply_patch'):
        return [source]
    values = []
    for match in re.finditer(r'\btools\.apply_patch\s*\(\s*("(?:\\.|[^"\\])*")', source):
        value = json.loads(match.group(1))
        if value.startswith('*** Begin Patch'):
            values.append(value)
    return values


def accepted(output):
    # Historical functions.exec emitted the apply_patch result as a separate
    # empty-object text block. Later commands can fail after a successful patch.
    if not isinstance(output, list):
        return False
    texts = [item.get('text', '') for item in output if item.get('type') == 'input_text']
    return any(text.startswith('Script completed\n') for text in texts) and '{}' in texts


def collect(transcript, after, before):
    calls, outputs, errors = [], {}, []
    for number, line in enumerate(transcript.splitlines(), 1):
        try:
            row = json.loads(line)
        except (ValueError, UnicodeError):
            errors.append({'line': number, 'sha256': hashlib.sha256(line).hexdigest()})
            continue
        payload = row.get('payload', {})
        kind = payload.get('type')
        if kind in ('function_call_output', 'custom_tool_call_output'):
            outputs[payload.get('call_id')] = payload.get('output')
        if after <= row.get('timestamp', '') < before and kind in ('function_call', 'custom_tool_call'):
            for patch in literal_patches(payload):
                calls.append({'line': number, 'timestamp': row['timestamp'],
                              'call_id': payload.get('call_id'), 'patch': patch})
    for call in calls:
        output = outputs.get(call['call_id'])
        call['accepted'] = accepted(output)
        texts = [item.get('text', '') for item in output or [] if isinstance(item, dict)]
        call['failed_verification'] = any('apply_patch verification failed:' in text for text in texts)
    return calls, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transcript', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--owner', type=Path, required=True)
    parser.add_argument('--source-prefix', required=True)
    parser.add_argument('--base-commit', required=True)
    parser.add_argument('--after', required=True)
    parser.add_argument('--before', required=True)
    args = parser.parse_args()
    raw = args.transcript.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.sha256:
        raise ValueError('transcript authentication mismatch')
    calls, errors = collect(raw, args.after, args.before)
    files, rejected = {}, []
    env = {**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}
    base = subprocess.check_output(['git', 'rev-parse', args.base_commit + '^{commit}'],
                                   cwd=args.owner, env=env, text=True).strip()
    unresolved = []
    for call in calls:
        if not call['accepted']:
            if call['failed_verification']:
                rejected.append(call['line'])
            else:
                unresolved.append({'line': call['line'], 'reason': 'no accepted patch result'})
            continue
        for line in call['patch'].splitlines():
            if line.startswith(('*** Update File: ', '*** Add File: ')):
                name = relative_name(line.split(': ', 1)[1], args.source_prefix)
                if name not in files:
                    read = subprocess.run(['git', 'show', base + ':' + name], cwd=args.owner,
                                          env=env, capture_output=True)
                    if read.returncode == 0:
                        files[name] = read.stdout
        files = replay(call['patch'], args.source_prefix, files)
    findings = []
    for name, expected in sorted(files.items()):
        try:
            target = audit.no_link_path(args.owner.resolve(strict=True), name)
            current_sha = audit.file_hash(target)
        except (OSError, ValueError) as error:
            findings.append({'path': name, 'verified': False, 'reason': str(error)})
            continue
        expected_sha = hashlib.sha256(expected).hexdigest()
        findings.append({'path': name, 'expected_sha256': expected_sha,
                         'current_sha256': current_sha, 'verified': expected_sha == current_sha})
    result = {'scope': 'accepted recorded textual owner patches only', 'base_commit': base,
              'transcript_sha256': args.sha256, 'after': args.after, 'before': args.before,
              'accepted_patch_calls': sum(call['accepted'] for call in calls),
              'rejected_patch_lines': rejected, 'unresolved_calls': unresolved,
              'parse_failures_preserved': errors, 'files': findings,
              'recorded_edits_verified': bool(findings) and all(row['verified'] for row in findings) and not unresolved,
              'zero_loss_proven': False, 'shared_paths_written': False}
    print(json.dumps(result, indent=2))
    return 0 if result['recorded_edits_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
