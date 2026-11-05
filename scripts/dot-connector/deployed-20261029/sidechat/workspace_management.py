"""Explicit display-only management associations; trusted local provisioning only.

Not a tool or HTTP mutation. Reads, messages and dispatch receipts never enroll a
workspace. This metadata grants no access and authorizes no coding-agent action.
"""
import argparse
import json
from pathlib import Path
import uuid

from sidechat import Rejected, Store


class WorkspaceManagement:
    def __init__(self, store):
        self.store = store
        store.db.executescript("""
        CREATE TABLE IF NOT EXISTS dot_workspace_management(
          seq INTEGER PRIMARY KEY AUTOINCREMENT,
          owner TEXT NOT NULL, project TEXT NOT NULL, issue TEXT NOT NULL,
          workspace TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('managed','released')),
          approval_ref TEXT NOT NULL, updated REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS dot_workspace_management_owner_workspace
          ON dot_workspace_management(owner,workspace,seq);
        """)

    def change(self, owner, expected, state, approval_ref, resolver):
        """Local administrator supplies an explicit owner-approved exact scope.

        Assignment survives reading/completion until explicitly released. Release
        retains the audit trail; reassignment needs a new explicit approval. Scope
        migration is deliberately unsupported. No auth/scope rows are created.
        """
        if set(expected) != {'project', 'issue', 'workspace'}:
            raise Rejected('Exact management scope required')
        scope = {k: str(uuid.UUID(v)) for k, v in expected.items()}
        if state not in ('managed', 'released') or not isinstance(approval_ref, str) or not 1 <= len(approval_ref.strip()) <= 500:
            raise Rejected('Explicit state and owner approval reference required')
        actual = resolver(scope['workspace'])
        if any(actual.get(k) != v for k, v in scope.items()):
            raise Rejected('Authoritative management scope changed')
        with self.store.transaction():
            if not self.store.db.execute(
                'SELECT 1 FROM scopes WHERE owner=? AND project=? AND issue=? AND workspace=?',
                (owner, scope['project'], scope['issue'], scope['workspace'])).fetchone():
                raise Rejected('An existing exact owner scope is required')
            old = self.store.db.execute(
                'SELECT * FROM dot_workspace_management WHERE owner=? AND workspace=? ORDER BY seq DESC LIMIT 1',
                (owner, scope['workspace'])).fetchone()
            if old and (old['project'], old['issue']) != (scope['project'], scope['issue']):
                raise Rejected('Management scope migration requires separate review')
            if old and old['state'] == state:
                return {'changed': False, 'state': state, 'seq': old['seq']}
            if not old and state == 'released':
                return {'changed': False, 'state': 'unknown', 'seq': None}
            row = self.store.db.execute(
                'INSERT INTO dot_workspace_management(owner,project,issue,workspace,state,approval_ref,updated) VALUES (?,?,?,?,?,?,?)',
                (owner, scope['project'], scope['issue'], scope['workspace'], state, approval_ref.strip(), self.store.clock()))
            return {'changed': True, 'state': state, 'seq': row.lastrowid}

    def visible(self, principal, projects, resolver):
        self.store._principal(principal, ('owner',))
        allowed = set(projects)
        rows = self.store.db.execute("""
          SELECT m.* FROM dot_workspace_management m JOIN scopes s
            ON s.owner=m.owner AND s.workspace=m.workspace
            AND s.project=m.project AND s.issue=m.issue
          WHERE m.owner=? AND m.state='managed' AND m.seq=(
            SELECT MAX(latest.seq) FROM dot_workspace_management latest
            WHERE latest.owner=m.owner AND latest.workspace=m.workspace)
          ORDER BY m.workspace""", (principal.owner,)).fetchall()
        result = []
        for row in rows:
            if row['project'] not in allowed:
                continue
            try:
                actual = resolver(row['workspace'])
            except (Rejected, ValueError):
                continue
            if any(actual.get(k) != row[k] for k in ('project', 'issue', 'workspace')):
                continue
            result.append({'project_id': row['project'], 'issue_id': row['issue'],
                           'workspace_id': row['workspace'], 'manager': 'dot', 'state': 'managed'})
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True, help='Existing private sidechat database')
    parser.add_argument('--vibe-db', required=True, help='Authoritative Vibe database, read-only')
    parser.add_argument('--owner', required=True, help='Existing scoped owner; never a credential')
    for name in ('project', 'issue', 'workspace'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--state', choices=('managed', 'released'), required=True)
    parser.add_argument('--approval-ref', required=True)
    parser.add_argument('--apply', action='store_true', required=True,
                        help='Explicit trusted local metadata mutation; no access/agent authority')
    args = parser.parse_args()
    from browser_api import WorkspaceResolver
    path = Path(args.data)
    if path.is_symlink() or not path.is_file():
        raise Rejected('Existing private database required')
    store = Store(path)
    try:
        print(json.dumps(WorkspaceManagement(store).change(
            args.owner, {k: getattr(args, k) for k in ('project', 'issue', 'workspace')},
            args.state, args.approval_ref, WorkspaceResolver(args.vibe_db))))
    finally:
        store.close()


if __name__ == '__main__':
    main()
