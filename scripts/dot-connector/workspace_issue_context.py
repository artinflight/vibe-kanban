"""Read-only preflight for issue-linked, Dot-capable workspace creation."""
import uuid


def require_issue_context(args, read):
    if not args.get('project_id') or not args.get('issue_id'):
        raise ValueError('Dot Chat requires an issue-linked workspace: create/select an issue in Vibe, '
                         'then pass both project_id and issue_id. No workspace or agent was started.')
    try:
        project, issue = (str(uuid.UUID(args[k])) for k in ('project_id', 'issue_id'))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Valid project_id and issue_id UUIDs required; no workspace started') from None
    page = read('/v1/fallback/issues?project_id=' + project)
    rows = page.get('issues') if isinstance(page, dict) else None
    if not isinstance(rows, list) or not any(
            isinstance(row, dict) and row.get('id') == issue and row.get('project_id') == project
            for row in rows):
        raise ValueError('Issue was not verified in the selected project; no workspace started')
    return {'project_id': project, 'issue_id': issue}
