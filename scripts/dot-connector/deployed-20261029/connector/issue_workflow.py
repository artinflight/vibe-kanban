"""Backend-owned issue lifecycle. No client controller, journal or workspace scans.

Authority comes from the existing authenticated owner/project grant. Stable
request IDs bind native transactions; uncertain effects are read, never replayed.
"""
import json
import os
import uuid
import urllib.request

UUID = {'type': 'string', 'format': 'uuid'}
FIELDS = {'request_id': UUID, 'project_id': UUID,
          'title': {'type': 'string', 'minLength': 1, 'maxLength': 240},
          'description': {'type': 'string', 'maxLength': 20000},
          'status_id': {'type': 'string', 'minLength': 1, 'maxLength': 100}}
START = {'name': {'type': 'string', 'minLength': 1, 'maxLength': 240},
         'prompt': {'type': 'string', 'minLength': 1, 'maxLength': 60000},
         'executor': {'type': 'string', 'enum': ['CODEX']},
         'repositories': {'type': 'array', 'minItems': 1, 'maxItems': 8,
                          'items': {'type': 'object', 'properties': {'repo_id': UUID, 'branch': {'type': 'string', 'minLength': 1, 'maxLength': 250}},
                                    'required': ['repo_id', 'branch'], 'additionalProperties': False}}}
SELECTION = {k: {'type': 'string', 'minLength': 1, 'maxLength': 100} for k in ('variant', 'model_id', 'reasoning_id')}
LINK = {'workspace_id': UUID, 'expected_issue_id': UUID,
        'expected_link_revision': {'type': 'integer', 'minimum': 0}}
CHAT_OLD = {'chat_previous_issue_id': UUID}


def tool(name, properties, description, optional=None, write=True):
    return {'name': name, 'description': description,
            'inputSchema': {'type': 'object', 'properties': dict(properties, **(optional or {})),
                            'required': list(properties), 'additionalProperties': False},
            'annotations': {'readOnlyHint': not write, 'destructiveHint': False, 'openWorldHint': write}}


TOOLS = [tool('create_issue', FIELDS,
              'Only for explicit owner authorization. Atomically create a dedicated local issue assigned to verified dot. '
              'Keep request_id and identical inputs for reconciliation. Requires current authenticated project access.'),
         tool('create_issue_and_start_workspace', dict(FIELDS, **START),
              'Only for explicit owner authorization. Atomically reserve the dedicated dot issue, linked workspace, '
              'repositories and session before guarded launch. Retain request_id and exact selections; retries read '
              'native receipts and cannot start another workspace. Unknown launch is not success. Uses existing Recommend policy.', SELECTION),
         tool('create_issue_for_workspace', dict(FIELDS, **LINK),
              'Only for explicit create/assign/relink authorization. Atomically create a dedicated dot issue and '
              'conditionally relink the selected workspace in the same project. Read get_workspace_issue_context first; '
              'provide its expected_issue_id and expected_link_revision. Preserves original chat histories. Keep request_id.', CHAT_OLD),
         tool('link_workspace_issue', dict({'project_id': UUID, 'request_id': UUID, 'issue_id': UUID}, **LINK),
              'Only for explicit owner relink authorization. Same-project revision-fenced link and verified dot assignment, '
              'with history-safe chat migration. Exact expected old issue/revision required. A same-issue link can explicitly '
              'reconcile a bootstrap chat_previous_issue_id; it cannot move across projects. Keep request_id.', CHAT_OLD),
         tool('get_issue_workflow_receipt', {'project_id': UUID, 'request_id': UUID},
              'Read current native workflow receipt after project authorization. No launch or retry. Missing/uncertain '
              'execution evidence never proves non-delivery; retain the original request ID.', write=False),
         tool('get_workspace_issue_context', {'project_id': UUID, 'workspace_id': UUID},
              'Read native current issue and monotonic link_revision in this project. Use those as expected_issue_id '
              'and expected_link_revision for an explicitly authorized relink; stale snapshots reject.', write=False)]
NAMES = {t['name'] for t in TOOLS}
SCHEMAS = {t['name']: t['inputSchema'] for t in TOOLS}


class Blocked(ValueError):
    pass


def uid(value):
    if not isinstance(value, str):
        raise Blocked('invalid_uuid')
    try:
        parsed = uuid.UUID(value)
        if parsed.int == 0:
            raise ValueError()
        return str(parsed)
    except (ValueError, TypeError, AttributeError):
        raise Blocked('invalid_uuid') from None


def unwrap(value):
    if not isinstance(value, dict) or value.get('success') is not True or 'data' not in value:
        raise Blocked('backend_unavailable')
    return value['data']


def validate(name, args):
    schema = SCHEMAS.get(name)
    if schema is None or not isinstance(args, dict) or not set(schema['required']) <= set(args) or set(args) - set(schema['properties']):
        raise Blocked('exact_arguments_required')
    out = dict(args)
    for key, value in args.items():
        spec = schema['properties'][key]
        if spec.get('format') == 'uuid':
            out[key] = uid(value)
        elif spec['type'] == 'string':
            if not isinstance(value, str) or len(value) > spec.get('maxLength', 100000) or (spec.get('minLength') and not value.strip()):
                raise Blocked('invalid_bounded_input')
            if 'enum' in spec and value not in spec['enum']:
                raise Blocked('unsupported_executor')
        elif spec['type'] == 'integer':
            if type(value) is not int or not 0 <= value <= 2**63 - 1:
                raise Blocked('invalid_revision')
    if 'repositories' in out:
        repos = out['repositories']
        if not isinstance(repos, list) or not 1 <= len(repos) <= 8:
            raise Blocked('invalid_repositories')
        normalized = []
        for repo in repos:
            if not isinstance(repo, dict) or set(repo) != {'repo_id', 'branch'} or not isinstance(repo['branch'], str) or not repo['branch'].strip() or len(repo['branch']) > 250:
                raise Blocked('invalid_repository')
            normalized.append({'repo_id': uid(repo['repo_id']), 'branch': repo['branch']})
        if len({r['repo_id'] for r in normalized}) != len(normalized):
            raise Blocked('duplicate_repository')
        out['repositories'] = normalized
    return out


def receipt(value, project, request):
    if value is None:
        return None
    if not isinstance(value, dict) or value.get('project_id') != project or value.get('request_id') != request:
        raise Blocked('receipt_identity_mismatch')
    for key in ('issue_id', 'dot_user_id'):
        uid(value.get(key))
    if value.get('operation') not in ('create', 'start', 'relink') or value.get('phase') not in ('reserved', 'linked', 'launching', 'started', 'settled'):
        raise Blocked('receipt_phase_invalid')
    if not isinstance(value.get('request_hash'), str) or len(value['request_hash']) != 64 or any(c not in '0123456789abcdef' for c in value['request_hash']):
        raise Blocked('receipt_fingerprint_invalid')
    if any(type(value.get(k)) is not bool for k in ('current_link', 'assignment_verified', 'chat_completed')):
        raise Blocked('receipt_evidence_invalid')
    if value['operation'] != 'create':
        uid(value.get('workspace_id'))
        if type(value.get('link_revision')) is not int or value['link_revision'] < 0:
            raise Blocked('receipt_revision_invalid')
    if value['operation'] == 'start':
        uid(value.get('session_id'))
    if not isinstance(value.get('executions'), list) or len(value['executions']) > 100:
        raise Blocked('execution_evidence_invalid')
    for execution in value['executions']:
        if not isinstance(execution, dict):
            raise Blocked('execution_evidence_invalid')
        uid(execution.get('id'))
        if execution.get('status') not in ('running', 'completed', 'failed', 'killed') or type(execution.get('dropped')) is not bool:
            raise Blocked('execution_evidence_invalid')
    return value


class Workflow:
    def __init__(self, api):
        self.api = api

    def call(self, name, args):
        args = validate(name, args)
        pid = args['project_id']
        owner = self.api.authorize(pid)
        if not isinstance(owner, str) or not owner:
            raise Blocked('authenticated_owner_required')
        if name == 'get_workspace_issue_context':
            value = unwrap(self.api.get('/api/issue-workflows/workspaces/' + args['workspace_id'] + '?project_id=' + pid))
            if not isinstance(value, dict) or value.get('project_id') != pid or value.get('workspace_id') != args['workspace_id']:
                raise Blocked('workspace_context_mismatch')
            uid(value.get('issue_id'))
            if type(value.get('link_revision')) is not int or value['link_revision'] < 0:
                raise Blocked('workspace_revision_invalid')
            return value
        rid = args['request_id']
        read = lambda: receipt(unwrap(self.api.get('/api/issue-workflows/' + rid + '?project_id=' + pid)), pid, rid)
        if name == 'get_issue_workflow_receipt':
            return read()
        capabilities = unwrap(self.api.get('/api/issue-workflows/capabilities'))
        if not isinstance(capabilities, dict) or type(capabilities.get('version')) is not int or capabilities.get('version') != 1 or any(capabilities.get(k) is not True for k in ('atomic_reservation', 'conditional_relink', 'durable_launch_receipts')):
            raise Blocked('matching_backend_required')
        previous = read()  # Receipt first; never infer failure from a timeout.
        payload = {'request_id': rid, 'project_id': pid, 'operation': 'create',
                   'title': args.get('title'), 'description': args.get('description'),
                   'status_id': args.get('status_id'), 'start': None, 'link': None}
        if name == 'create_issue_and_start_workspace':
            config = {'executor': args['executor'], 'variant': args.get('variant') or 'DEFAULT'}
            config.update({k: args[k] for k in ('model_id', 'reasoning_id') if k in args})
            payload.update(operation='start', start={
                'name': args['name'], 'prompt': args['prompt'], 'executor_config': self.api.recommend_config(config),
                'repositories': [{'repo_id': r['repo_id'], 'target_branch': r['branch']} for r in args['repositories']]})
        elif name in ('create_issue_for_workspace', 'link_workspace_issue'):
            payload.update(operation='relink', link={k: args[k] for k in LINK})
            payload['link']['target_issue_id'] = args.get('issue_id')
            payload['link']['chat_previous_issue_id'] = args.get('chat_previous_issue_id')
            if previous is None:
                self.api.chat_preflight(owner, pid, args['workspace_id'], args.get('chat_previous_issue_id') or args['expected_issue_id'])
        if self.api.authorize(pid) != owner:
            raise Blocked('authenticated_owner_changed')
        # Always send the same canonical payload to reserve: the server verifies
        # its hash even when read() found a previous receipt. It cannot create again.
        value = receipt(unwrap(self.api.post('/api/issue-workflows', payload)), pid, rid)
        if value is None or value['operation'] != payload['operation']:
            raise Blocked('receipt_operation_mismatch')
        if not value['current_link'] or not value['assignment_verified']:
            raise Blocked('native_issue_link_or_assignment_changed')
        if value['operation'] == 'create':
            return dict(value, status='issue_ready')
        if self.api.authorize(pid) != owner:
            raise Blocked('authenticated_owner_changed')
        self.api.chat_scope(owner, value, read)
        value = receipt(unwrap(self.api.post('/api/issue-workflows/' + rid + '/chat-ready',
                                             {'project_id': pid, 'request_hash': value['request_hash']})), pid, rid)
        if not value or not value['chat_completed'] or not value['current_link']:
            raise Blocked('chat_acknowledgement_not_verified')
        if value['operation'] == 'relink':
            return dict(value, status='linked')
        if self.api.authorize(pid) != owner:
            raise Blocked('authenticated_owner_changed')
        # Repeated launch POSTs are safe: the backend claims the exact request
        # atomically. There is no call to legacy local_start/follow-up/queue here.
        value = receipt(unwrap(self.api.post('/api/issue-workflows/' + rid + '/launch', payload)), pid, rid)
        if not value or not value['current_link'] or not value['chat_completed']:
            raise Blocked('launch_scope_changed')
        if value['phase'] == 'started' and any(e['id'] == value.get('execution_process_id') and not e['dropped'] for e in value['executions']):
            return self.api.note(args, dict(value, status='started'))
        return dict(value, status='launch_settled' if value['phase'] == 'settled' else 'launch_unknown' if value['phase'] == 'launching' else 'reserved')


class Runtime:
    def __init__(self, adapter):
        import connector
        from browser_api import WorkspaceResolver
        from project_collaboration import ProjectCollaboration
        from sidechat import Principal
        self.adapter, self.hook, self.Principal = adapter, connector, Principal
        self.store = connector.opened()
        self.resolver = WorkspaceResolver(os.environ.get('VK_SIDECHAT_VIBE_DB', '/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban/db.v2.sqlite'))
        self.access = ProjectCollaboration(self.store, self.resolver)

    def close(self):
        self.store.close()

    def authorize(self, project):
        owner = self.hook.owner()
        self.access.authorize(self.Principal(owner, 'dot'), project)
        return owner

    def recommend_config(self, config):
        return self.adapter.recommend_config(config)

    def get(self, path):
        return self.adapter.http_get(path)

    def post(self, path, payload):
        # Only internally constructed UUID workflow paths. No generic HTTP tool.
        if path != '/api/issue-workflows':
            parts = path.split('/')
            if len(parts) != 5 or parts[1:3] != ['api', 'issue-workflows'] or parts[4] not in ('chat-ready', 'launch') or uid(parts[3]) != parts[3]:
                raise Blocked('unsupported_write_endpoint')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        request = urllib.request.Request(self.adapter.BASE + path, data=json.dumps(payload, ensure_ascii=False).encode(),
                                         headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.build_opener(NoRedirect).open(request, timeout=90) as response:
            body = response.read(self.adapter.MAX_BYTES + 1)
        if len(body) > self.adapter.MAX_BYTES:
            raise Blocked('write_outcome_unknown')
        return json.loads(body)

    def chat_preflight(self, owner, project, workspace, previous_issue):
        old = self.store.db.execute('SELECT project,issue FROM scopes WHERE owner=? AND workspace=?', (owner, workspace)).fetchone()
        if old and (old['project'], old['issue']) != (project, previous_issue):
            raise Blocked('explicit_chat_history_catchup_required')

    def chat_scope(self, owner, value, read):
        project, issue, workspace = value['project_id'], value['issue_id'], value['workspace_id']
        if self.authorize(project) != owner:
            raise Blocked('authenticated_owner_changed')
        actual = self.resolver(workspace)
        if (actual['project'], actual['issue'], actual['workspace']) != (project, issue, workspace):
            raise Blocked('native_chat_scope_changed')
        if value['operation'] == 'relink':
            from scope_migration import migrate
            migrate(self.store, self.Principal(owner, 'dot'), value, read)
        else:
            self.store.register_scope(owner, project, issue, workspace)
            self.store.resolve(self.Principal(owner, 'owner'), project, issue, workspace)
        from scope_migration import delivery_binding
        current = self.store.resolve(self.Principal(owner, 'owner'), project, issue, workspace)
        delivery_binding(self.store, self.Principal(owner, 'dot'), current['id'])

    def note(self, args, value):
        from dispatch_notes import observe, current_caller
        accepted = self.adapter.result({'workspace': {'id': value['workspace_id']},
                                        'execution_process': {'id': value['execution_process_id'], 'session_id': value['session_id']}})
        output = observe('start_workspace', dict(args, issue_id=value['issue_id']), accepted, caller=current_caller())
        for block in output.get('content', [])[1:]:
            if block.get('type') == 'text':
                value.update(json.loads(block['text']))
        return value


def call(adapter, name, args):
    runtime = None
    try:
        runtime = Runtime(adapter)
        value = Workflow(runtime).call(name, args)
        result = adapter.result(value)
        result['isError'] = name not in ('get_issue_workflow_receipt', 'get_workspace_issue_context') and (not value or value.get('status') not in ('issue_ready', 'started', 'linked'))
        return result
    except Exception:
        # A lost mutation response is not evidence of non-delivery. Reuse exact
        # request/project and inspect the durable native receipt; no auto retry.
        result = adapter.result({'status': 'blocked_or_unknown', 'reason': 'inspect_native_workflow_receipt',
                                 'next_step': 'Check project access and the same request receipt; retain all original inputs and never replace its ID.'})
        result['isError'] = True
        return result
    finally:
        if runtime is not None:
            runtime.close()
