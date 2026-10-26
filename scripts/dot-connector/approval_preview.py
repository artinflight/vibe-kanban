"""Display-only previews for existing authenticated approval notifications.

Never accept grants, prompts, file contents or permission suggestions here.
A complete command is shown or withheld; a prefix is never presented as complete.
"""
import json

FIELDS = ('command', 'file_path', 'path', 'url')
SENSITIVE = ('password', 'passwd', 'secret', 'token', 'api_key', 'api-key',
             'apikey', 'authorization', 'cookie', 'credential', 'private_key',
             'private-key', 'bearer ', '-----begin', 'sk-', 'ghp_', 'github_pat_',
             'x-amz-', 'signature=', 'sig=', 'sas=')


def safe_text(value):
    if not isinstance(value, str) or len(value.encode()) > 4096:
        return False
    if any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0x202a <= ord(c) <= 0x202e or
           0x2066 <= ord(c) <= 0x2069 for c in value):
        return False
    if any(part in value.lower() for part in SENSITIVE):
        return False
    return not any('@' in rest.split('/')[0] for rest in value.split('://')[1:])


def preview(parameters):
    if not isinstance(parameters, dict):
        return {'status': 'unavailable'}
    result, withheld = {}, False
    for key in FIELDS:
        if key not in parameters:
            continue
        if safe_text(parameters[key]):
            result[key] = parameters[key]
        else:
            withheld = True
    if len(json.dumps(result).encode()) > 6000:
        result, withheld = {}, True
    result['status'] = ('partial' if result else 'withheld') if withheld else (
        'available' if result else 'unavailable')
    return result


def validate(value):
    if not isinstance(value, dict) or set(value) - {*FIELDS, 'status'}:
        raise ValueError('Invalid action preview')
    expected = preview(value)
    status = value.get('status')
    if status not in ('available', 'partial', 'withheld', 'unavailable'):
        raise ValueError('Invalid action availability')
    if any(key in value and key not in expected for key in FIELDS):
        raise ValueError('Unsafe action preview')
    if (status in ('available', 'partial')) != any(key in value for key in FIELDS):
        raise ValueError('Action availability mismatch')
    return dict(value)


SCHEMA = {'type': 'object', 'properties': {
    **{key: {'type': 'string', 'maxLength': 4096} for key in FIELDS},
    'status': {'enum': ['available', 'partial', 'withheld', 'unavailable']}},
    'required': ['status'], 'additionalProperties': False}
