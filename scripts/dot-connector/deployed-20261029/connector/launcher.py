"""Explicit Claude launch/dispatch and identity-fenced Codex handoff.

No billing/provider refresh, generic HTTP, model fallback, retry or background job.
The existing adapter owns authentication, observation and CODEX dispatch policy.
"""
import copy
import hashlib
import json
import re
import urllib.error

CLAUDE_MODELS = frozenset(('opus', 'opus[1m]', 'sonnet', 'haiku'))
EFFORTS = frozenset(('low', 'medium', 'high', 'max'))
SELECTION = frozenset(('variant', 'model_id', 'reasoning_id', 'permission_policy'))
UUID = {'type': 'string', 'format': 'uuid'}


def workspace_schema():
    return {'type': 'object', 'properties': {
        'name': {'type': 'string', 'minLength': 1},
        'prompt': {'type': 'string', 'minLength': 1, 'maxLength': 60000},
        'executor': {'type': 'string', 'enum': ['CODEX', 'CLAUDE_CODE']},
        'variant': {'type': ['string', 'null']},
        'repositories': {'type': 'array', 'minItems': 1, 'maxItems': 8,
                         'items': {'type': 'object', 'properties': {'repo_id': UUID,
                                   'branch': {'type': 'string', 'minLength': 1, 'maxLength': 250}},
                                   'required': ['repo_id', 'branch'], 'additionalProperties': False}},
        'project_id': UUID, 'issue_id': UUID,
        'model_id': {'type': ['string', 'null'], 'maxLength': 100},
        'reasoning_id': {'type': ['string', 'null'], 'maxLength': 100},
        'permission_policy': {'type': 'string', 'enum': ['AUTO', 'SUPERVISED', 'PLAN']},
    }, 'required': ['name', 'prompt', 'executor', 'repositories', 'project_id', 'issue_id'],
        'additionalProperties': False, 'allOf': [
            {'if': {'properties': {'executor': {'const': 'CLAUDE_CODE'}}},
             'then': {'required': ['model_id'], 'properties': {'variant': {'enum': ['DEFAULT', None]}, 'model_id': {'enum': sorted(CLAUDE_MODELS)},
                      'reasoning_id': {'enum': sorted(EFFORTS)}},
                      'allOf': [{'if': {'properties': {'model_id': {'const': 'haiku'}}},
                                 'then': {'not': {'required': ['reasoning_id']}}}]}},
            {'if': {'properties': {'executor': {'const': 'CODEX'}}},
             'then': {'not': {'required': ['permission_policy']}}},
        ]}


def claude_config(config):
    config = copy.deepcopy(config)
    if config.get('executor') != 'CLAUDE_CODE':
        raise ValueError('Executor mismatch; no request sent')
    if set(config) - (SELECTION | {'executor', 'agent_id', 'routing'}):
        raise ValueError('Unsupported executor setting; no request sent')
    model = config.get('model_id')
    if not isinstance(model, str) or model not in CLAUDE_MODELS:
        raise ValueError('Unsupported or missing Claude model; select an exact supported model, no fallback')
    effort = config.get('reasoning_id')
    if effort is not None and (not isinstance(effort, str) or model == 'haiku' or effort not in EFFORTS):
        raise ValueError('Unsupported Claude reasoning effort; no request sent')
    if config.get('variant') not in (None, 'DEFAULT'):
        raise ValueError('Unsupported Claude variant; no default-profile fallback')
    for key in ('variant', 'agent_id'):
        if config.get(key) is not None and (not isinstance(config[key], str)
                                           or not config[key].strip() or len(config[key]) > 100):
            raise ValueError('Invalid executor selection')
    if config.get('permission_policy') not in (None, 'AUTO', 'SUPERVISED', 'PLAN'):
        raise ValueError('Unsupported permission policy')
    policy = config.get('routing')
    if policy is not None:
        if not isinstance(policy, dict) or set(policy) - {'mode', 'floor', 'denied_models', 'allow_escalation'}:
            raise ValueError('Unsupported routing policy; no request sent')
        if model in policy.get('denied_models', []):
            raise ValueError('Selected model is denied; no fallback')
        # Preserve exclusions/floor, but Claude has no Codex recommendation engine.
        policy['mode'] = 'shadow'
    return config


def recommend(api, config):
    if config.get('executor') == 'CODEX':
        return api.codex_recommend_config(config)
    return claude_config(config)


def start(api, args):
    if args.get('executor') == 'CODEX':
        return api.codex_local_start(args)
    if set(args) - ({'name', 'prompt', 'executor', 'repositories', 'project_id', 'issue_id'} | SELECTION):
        raise ValueError('Unknown workspace argument')
    from workspace_issue_context import require_issue_context
    require_issue_context(args, api.http_get)
    if not isinstance(args.get('name'), str) or not args['name'].strip():
        raise ValueError('Name required')
    prompt = bounded_prompt(args.get('prompt'))
    config = claude_config(dict({'executor': args.get('executor')},
                                **{k: args[k] for k in SELECTION if k in args}))
    repos = args.get('repositories')
    if not isinstance(repos, list) or not 1 <= len(repos) <= 8:
        raise ValueError('1..8 repositories required')
    mapped = []
    for repo in repos:
        if not isinstance(repo, dict) or set(repo) != {'repo_id', 'branch'}:
            raise ValueError('Invalid repository')
        if not isinstance(repo['branch'], str) or not repo['branch'] or len(repo['branch']) > 250:
            raise ValueError('Explicit base branch required')
        mapped.append({'repo_id': api.valid_uuid(repo['repo_id']), 'target_branch': repo['branch']})
    payload = {'name': args['name'], 'prompt': prompt, 'repos': mapped,
               'linked_issue': {'issue_id': api.valid_uuid(args['issue_id']),
                                'remote_project_id': api.valid_uuid(args['project_id'])},
               'executor_config': config}
    # A single fixed POST. Unknown quota grants no extra-usage authorization.
    value = api.post_fixed('/api/workspaces/start', payload)
    return api.result(value)


def bounded_prompt(prompt):
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 60000:
        raise ValueError('Explicit bounded prompt required')
    return prompt


def resolve_claude(api, sid, session, overrides=None):
    rows = api.session_configs(sid)  # Existing idle gate and exact snapshot identity.
    configs = [row['config'] for row in rows if row.get('config')]
    if any(c.get('executor') != 'CLAUDE_CODE' for c in configs):
        raise ValueError('Session execution executor mismatch; no request sent')
    has_selection = bool(configs)
    config = copy.deepcopy(configs[0]) if configs else {'executor': 'CLAUDE_CODE'}
    old_policy = next((c['routing'] for c in configs if c.get('routing')), None)
    try:
        draft = api.http_get('/api/scratch/DRAFT_FOLLOW_UP/' + sid)
    except urllib.error.HTTPError as error:
        if error.code != 400 or b'"Scratch not found"' not in error.read(4096):
            raise ValueError('Saved draft lookup failed; no request sent') from error
    else:
        if draft.get('success') is not True:
            raise ValueError('Saved draft lookup failed; no request sent')
        scratch = draft.get('data') or {}
        saved = ((scratch.get('payload') or {}).get('data') or {}).get('executor_config')
        if saved:
            has_selection = True
            config = copy.deepcopy(saved)
        elif scratch:
            raise ValueError('Unknown saved draft format; no request sent')
    if overrides:
        # A conflicting saved choice requires the owner to update the draft first.
        if has_selection:
            if any(config.get(k) != v for k, v in overrides.items()):
                raise ValueError('Selection conflicts with saved model/effort; no request sent')
        config.update(overrides)
    if not config.get('routing') and old_policy:
        config['routing'] = old_policy
    return claude_config(config)


def followup(api, args):
    if not set(args) <= ({'session_id', 'prompt'} | SELECTION):
        raise ValueError('Unknown follow-up argument')
    if not set(args) & SELECTION:
        return api.codex_local_followup(args)  # Resolver below now accepts exact Claude config too.
    sid = api.valid_uuid(args.get('session_id'))
    prompt = bounded_prompt(args.get('prompt'))
    session = unwrap(api.http_get('/api/sessions/' + sid))
    if session.get('id') != sid or session.get('executor') != 'CLAUDE_CODE':
        raise ValueError('Explicit follow-up overrides require a Claude session; CODEX selection uses its saved draft')
    config = resolve_claude(api, sid, session, {k: args[k] for k in SELECTION if k in args})
    execution = api.post_fixed('/api/sessions/' + sid + '/follow-up',
                              {'prompt': prompt, 'executor_config': config, 'retry_process_id': None,
                               'force_when_dirty': None, 'perform_git_reset': None})
    if execution.get('connector_queued_for_capacity'):
        return api.result({'session_id': sid, 'status': 'queued', 'reason': 'execution_capacity',
                           'execution_id': None, 'queued_at': execution.get('queued_at'),
                           'message': 'Accepted for automatic execution when capacity opens. Do not resend this prompt.'})
    return api.result({'session_id': sid, 'execution_id': execution['id'], 'execution': execution})


def unwrap(value):
    if not isinstance(value, dict) or value.get('success') is not True or 'data' not in value:
        raise ValueError('Handoff capability unavailable; no fallback')
    return value['data']


def handoff(api, args):
    required = {'session_id', 'execution_id', 'request_id', 'prompt', 'model_id', 'reasoning_id'}
    if set(args) != required:
        raise ValueError('Exact source session/execution, stable request UUID and explicit Codex model/effort required')
    sid, eid, rid = (api.valid_uuid(args[k]) for k in ('session_id', 'execution_id', 'request_id'))
    bounded_prompt(args['prompt'])
    for key in ('model_id', 'reasoning_id'):
        if not isinstance(args[key], str) or not args[key].strip() or len(args[key]) > 100:
            raise ValueError('Explicit Codex model and reasoning effort required')
    payload = {k: args[k] for k in ('prompt', 'model_id', 'reasoning_id')}
    payload.update(request_id=rid, execution_id=eid)
    path = '/api/sessions/' + sid + '/handoff'
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

    def receipt(value):
        value = validate_receipt(api, value, sid, rid)
        if value['execution_id'] != eid or value['request_sha256'] != digest:
            raise ValueError('Handoff receipt identity conflict; do not resend')
        return value

    def report(value):
        return api.handoff_result(receipt(value))

    previous = unwrap(api.http_get(path + '/' + rid))
    if previous is not None:
        return report(previous)
    # GET identifies the guarded protocol. SPA/old backend never gets a POST.
    capability = unwrap(api.http_get(path))
    if capability != {'version': 1, 'serialized': True, 'quota': 'unknown', 'extra_usage_authorized': False}:
        raise ValueError('Guarded handoff unavailable; no request sent')
    try:
        return report(api.post_fixed(path, payload))
    except Exception:
        try:
            value = unwrap(api.http_get(path + '/' + rid))
            if value is not None:
                return report(value)
        except Exception:
            pass
        reply = api.result({'session_id': sid, 'execution_id': eid, 'request_id': rid,
                            'status': 'unknown', 'request_sha256': digest,
                            'message': 'Handoff outcome uncertain. Read this request receipt; never resend under a new ID.'})
        reply['isError'] = True
        return reply


def validate_receipt(api, value, sid, rid):
    if not isinstance(value, dict) or value.get('session_id') != sid or value.get('request_id') != rid:
        raise ValueError('Handoff receipt scope conflict; do not resend')
    if value.get('status') not in ('started', 'unknown'):
        raise ValueError('Invalid handoff receipt; do not resend')
    for key in ('execution_id', 'target_session_id'):
        if api.valid_uuid(value.get(key)) != value[key]:
            raise ValueError('Invalid handoff receipt identity')
    for key in ('request_sha256', 'context_sha256'):
        if not isinstance(value.get(key), str) or re.fullmatch('[0-9a-f]{64}', value[key]) is None:
            raise ValueError('Invalid handoff receipt fingerprint')
    target = value.get('target_execution_id')
    if target is not None:
        if api.valid_uuid(target) != target:
            raise ValueError('Invalid target execution identity')
    elif value['status'] == 'started':
        raise ValueError('Incomplete handoff receipt; do not resend')
    return {key: value.get(key) for key in ('session_id', 'execution_id', 'request_id',
            'request_sha256', 'context_sha256', 'target_session_id', 'target_execution_id', 'status')}


def get_handoff(api, args):
    if set(args) != {'session_id', 'request_id'}:
        raise ValueError('Exact session_id and request_id required')
    sid, rid = (api.valid_uuid(args[k]) for k in ('session_id', 'request_id'))
    value = unwrap(api.http_get('/api/sessions/' + sid + '/handoff/' + rid))
    return api.result(None if value is None else validate_receipt(api, value, sid, rid))


TOOLS = [
    {'name': 'handoff_claude_to_codex',
     'description': 'Only for an explicit owner-requested handoff at an idle successful Claude checkpoint. '
                    'Requires the exact source session/execution and stable request_id; selects the supplied Codex model/effort. '
                    'Preserves complete bounded durable source history in a new session in the same workspace. '
                    'Never stops agents, retries launches, buys extras or falls back on missing quota. Unknown outcomes require receipt reconciliation.',
     'inputSchema': {'type': 'object', 'properties': {'session_id': UUID, 'execution_id': UUID, 'request_id': UUID,
                     'prompt': {'type': 'string', 'minLength': 1, 'maxLength': 60000},
                     'model_id': {'type': 'string', 'minLength': 1, 'maxLength': 100},
                     'reasoning_id': {'type': 'string', 'minLength': 1, 'maxLength': 100}},
                     'required': ['session_id', 'execution_id', 'request_id', 'prompt', 'model_id', 'reasoning_id'],
                     'additionalProperties': False},
     'annotations': {'readOnlyHint': False, 'destructiveHint': False, 'openWorldHint': True}},
    {'name': 'get_claude_codex_handoff', 'description': 'Read the exact durable handoff receipt. Unknown is not permission to relaunch.',
     'inputSchema': {'type': 'object', 'properties': {'session_id': UUID, 'request_id': UUID},
                     'required': ['session_id', 'request_id'], 'additionalProperties': False},
     'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False}},
]
HANDLERS = {'handoff_claude_to_codex': handoff, 'get_claude_codex_handoff': get_handoff}
