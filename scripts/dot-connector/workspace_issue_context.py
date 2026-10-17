"""Read-only issue preflight and stable, scope-safe MCP rejection details."""
import json
import uuid

# Public response contract: never include supplied IDs, prompts, lookup bodies,
# other-project metadata or exception diagnostics in an explanation.
EXPLANATIONS = {
    'workspace_issue_ids_missing': (
        'Workspace creation was blocked because both project_id and issue_id are required.',
        'Create or select an issue in Vibe, then provide its project_id and issue_id.'),
    'workspace_issue_ids_invalid': (
        'Workspace creation was blocked because project_id or issue_id is not a valid UUID.',
        'Copy the project and issue UUIDs from Vibe, then submit the matching IDs again.'),
    'workspace_issue_not_verified': (
        'The issue could not be verified in the selected project.',
        'List issues in the selected project and select one, or create a dedicated issue there; '
        'then provide its project_id and issue_id.'),
    'workspace_issue_lookup_unavailable': (
        'Vibe could not complete the selected project issue lookup.',
        'Retry the read-only project issue lookup when Vibe is available; '
        'start the workspace only after issue verification succeeds.'),
    'workspace_issue_lookup_malformed': (
        'Vibe returned incomplete or malformed project issue evidence.',
        'Check the project issue service response and retry the read-only lookup; '
        'start the workspace only after complete, valid evidence is available.'),
}


class IssueContextError(ValueError):
    """Known rejection before any workspace/agent side effect, never a POST error."""
    def __init__(self, code):
        reason, next_step = EXPLANATIONS[code]
        self.detail = {'code': code, 'reason': reason, 'next_step': next_step}
        super().__init__(reason + ' Next step: ' + next_step)

    def tool_result(self):
        detail = dict(self.detail)
        return {'isError': True,
                'content': [{'type': 'text', 'text': json.dumps(detail, sort_keys=True)}],
                'structuredContent': detail}


def dispatch_start(start, args):
    """Preserve successful/uncertain starts; serialize only typed preflight failures."""
    try:
        return start(args)
    except IssueContextError as error:
        return error.tool_result()


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError('UUID string required')
    return str(uuid.UUID(value))


def require_issue_context(args, read):
    if any(args.get(k) is None or (isinstance(args[k], str) and not args[k].strip())
           for k in ('project_id', 'issue_id')):
        raise IssueContextError('workspace_issue_ids_missing')
    try:
        project, issue = (_uuid(args[k]) for k in ('project_id', 'issue_id'))
    except (ValueError, TypeError, AttributeError):
        raise IssueContextError('workspace_issue_ids_invalid') from None
    try:
        page = read('/v1/fallback/issues?project_id=' + project)
    except Exception:
        # A failed lookup is not evidence that the issue was absent. Never echo
        # HTTP bodies/errors, credentials or a service-selected URL.
        raise IssueContextError('workspace_issue_lookup_unavailable') from None
    if isinstance(page, dict) and (page.get('success') is False or page.get('error')
                                  or page.get('error_data')):
        raise IssueContextError('workspace_issue_lookup_unavailable')
    rows = page.get('issues') if isinstance(page, dict) else None
    if isinstance(page, dict) and any(k in page and type(page[k]) is not bool
                                      for k in ('success', 'complete', 'has_more')):
        raise IssueContextError('workspace_issue_lookup_malformed')
    if not isinstance(rows, list) or page.get('complete') is False or any(
            page.get(k) is not None for k in ('next_offset', 'next_cursor')) or page.get('has_more'):
        raise IssueContextError('workspace_issue_lookup_malformed')
    total = page.get('total')
    if total is not None and (type(total) is not int or total != len(rows)):
        raise IssueContextError('workspace_issue_lookup_malformed')
    pairs = {}
    try:
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('Invalid issue evidence')
            rid, pid = _uuid(row.get('id')), _uuid(row.get('project_id'))
            if rid in pairs:
                raise ValueError('Ambiguous issue evidence')
            pairs[rid] = pid
    except (ValueError, TypeError, AttributeError):
        raise IssueContextError('workspace_issue_lookup_malformed') from None
    if pairs.get(issue) != project:
        # A positive mismatched-project row must not disclose cross-project
        # existence. It has exactly the same public outcome as scoped absence.
        # No global issue lookup, extra project read or raw evidence is returned.
        raise IssueContextError('workspace_issue_not_verified')
    return {'project_id': project, 'issue_id': issue}
