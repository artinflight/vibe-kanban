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


def literal_argument(source, position):
    """Read JSON values or a flat JS object with identifier keys and JSON values.

    Historical tool calls use unquoted object keys. Expressions, spreading,
    computed keys, shorthand, comments and nested JS syntax remain unsupported.
    """
    decoder = json.JSONDecoder()
    if source[position:position + 1] != '{':
        return decoder.raw_decode(source, position)
    position += 1
    values = {}
    while True:
        space = re.match(r'\s*', source[position:])
        position += space.end()
        if source[position:position + 1] == '}':
            return values, position + 1
        key = re.match(r'([A-Za-z_][A-Za-z_0-9]*)\s*:', source[position:])
        if key:
            name = key.group(1)
            position += key.end()
        else:
            name, position = decoder.raw_decode(source, position)
            colon = re.match(r'\s*:', source[position:])
            if not isinstance(name, str) or not colon:
                raise ValueError('unsupported object key')
            position += colon.end()
        if name in values:
            raise ValueError('duplicate argument key')
        position += re.match(r'\s*', source[position:]).end()
        values[name], position = decoder.raw_decode(source, position)
        separator = re.match(r'\s*([,}])', source[position:])
        if not separator:
            raise ValueError('unsupported object expression')
        position += separator.end()
        if separator.group(1) == '}':
            return values, position


def recorded_program(payload):
    """Recognize a narrow sequential program, without evaluating JavaScript.

    Every statement must print its awaited tool result. Exactly one patch must
    be first. Comments, branches, literals embedded in other code, concurrent
    calls and multiple patches cannot establish execution/result attribution.
    Unsupported programs remain unresolved rather than guessing at execution.
    """
    if payload.get('name') != 'exec':
        raise ValueError('unsupported tool/program')
    source = payload.get('input', '')
    if not isinstance(source, str):
        raise ValueError('non-text program')
    statements, position = [], 0
    while position < len(source):
        start = re.match(r'\s*text\(await tools\.(apply_patch|exec_command|write_stdin)\(\s*', source[position:])
        if not start:
            if source[position:].strip():
                raise ValueError('unsupported or ambiguous program syntax')
            break
        name = start.group(1)
        position += start.end()
        argument, end = literal_argument(source, position)
        position = end
        close = re.match(r'\s*\)\);', source[position:])
        if not close:
            raise ValueError('unbound statement/result')
        position += close.end()
        if name == 'apply_patch':
            if statements or not isinstance(argument, str) or not argument.startswith('*** Begin Patch\n'):
                raise ValueError('patch must be the sole first patch statement')
        elif not isinstance(argument, dict):
            raise ValueError('unsupported command argument')
        statements.append((name, argument))
    if not statements or statements[0][0] != 'apply_patch':
        raise ValueError('no first patch statement')
    return statements


def bound_result(statements, output):
    """Bind the first patch to the first result slot, with exact cardinality."""
    if not isinstance(output, list) or any(not isinstance(item, dict) or
            item.get('type') != 'input_text' or not isinstance(item.get('text'), str) for item in output):
        return False, False
    texts = [item['text'] for item in output]
    if len(statements) == 1 and len(texts) == 2 and texts[0].startswith('Script failed\n') and texts[1].startswith(
            'Script error:\napply_patch verification failed:'):
        return False, True
    if len(texts) != len(statements) + 1 or not texts[0].startswith('Script completed\n'):
        return False, False
    if texts[1] != '{}':
        return False, False
    for (name, _), text in zip(statements[1:], texts[2:]):
        try:
            result = json.loads(text)
        except ValueError:
            return False, False
        if (name not in ('exec_command', 'write_stdin') or not isinstance(result, dict) or
                not isinstance(result.get('output'), str) or
                not isinstance(result.get('wall_time_seconds'), (int, float)) or
                not isinstance(result.get('chunk_id'), str) or
                not any(isinstance(result.get(key), int) for key in ('exit_code', 'session_id'))):
            return False, False
    return True, False


def evidence_verified(findings, unresolved, errors):
    return bool(findings) and all(row['verified'] for row in findings) and not unresolved and not errors


def collect(transcript, after, before):
    calls, outputs, errors, identities = [], {}, [], {}
    for number, line in enumerate(transcript.splitlines(), 1):
        try:
            row = json.loads(line)
        except (ValueError, UnicodeError):
            errors.append({'line': number, 'sha256': hashlib.sha256(line).hexdigest()})
            continue
        if not isinstance(row, dict) or not isinstance(row.get('payload', {}), dict):
            errors.append({'line': number, 'sha256': hashlib.sha256(line).hexdigest()})
            continue
        payload = row.get('payload', {})
        kind = payload.get('type')
        if kind in ('function_call_output', 'custom_tool_call_output'):
            identity = payload.get('call_id')
            if not isinstance(identity, str):
                errors.append({'line': number, 'reason': 'invalid output identity'})
                continue
            outputs.setdefault(identity, []).append((number, kind, payload.get('output')))
        if kind in ('function_call', 'custom_tool_call'):
            identity = payload.get('call_id')
            if not isinstance(identity, str):
                errors.append({'line': number, 'reason': 'invalid call identity'})
                continue
            identities[identity] = identities.get(identity, 0) + 1
            timestamp = row.get('timestamp', '')
            if not isinstance(timestamp, str) or not timestamp:
                errors.append({'line': number, 'reason': 'invalid call timestamp; scope uncertain'})
                continue
            source = payload.get('input', payload.get('arguments', ''))
            if isinstance(timestamp, str) and after <= timestamp < before and (
                    'apply_patch' in str(source) or 'apply_patch' in str(payload.get('name', ''))):
                call = {'line': number, 'timestamp': timestamp, 'call_id': identity,
                        'accepted': False, 'failed_verification': False}
                try:
                    call['statements'] = recorded_program(payload)
                    call['patch'] = call['statements'][0][1]
                except (ValueError, TypeError) as error:
                    call['reason'] = str(error)
                calls.append(call)
    for call in calls:
        matches = outputs.get(call['call_id'], [])
        if identities[call['call_id']] != 1 or len(matches) != 1:
            call['reason'] = 'missing or duplicate call/result identity'
        elif matches[0][0] <= call['line'] or matches[0][1] != 'custom_tool_call_output':
            call['reason'] = 'result precedes call or has incompatible type'
        elif 'statements' in call and 'reason' not in call:
            call['accepted'], call['failed_verification'] = bound_result(call['statements'], matches[0][2])
            call['result_line'] = matches[0][0]
            call['patch_sha256'] = hashlib.sha256(call['patch'].encode()).hexdigest()
            # Safe provenance: hashes of receipt blocks, never their private text.
            call['result_sha256'] = hashlib.sha256(json.dumps(matches[0][2], sort_keys=True).encode()).hexdigest()
            if not call['accepted'] and not call['failed_verification']:
                call['reason'] = 'ambiguous ordered tool results'
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
                unresolved.append({'line': call['line'], 'reason': call.get('reason', 'no accepted patch result')})
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
              'patch_result_bindings': [{key: call[key] for key in
                  ('line', 'result_line', 'patch_sha256', 'result_sha256', 'accepted', 'failed_verification')
                  if key in call} for call in calls],
              'rejected_patch_lines': rejected, 'unresolved_calls': unresolved,
              'parse_failures_preserved': errors, 'files': findings,
              'recorded_edits_verified': evidence_verified(findings, unresolved, errors),
              'zero_loss_proven': False, 'shared_paths_written': False}
    print(json.dumps(result, indent=2))
    return 0 if result['recorded_edits_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
