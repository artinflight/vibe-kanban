#!/usr/bin/env python3
"""Read-only inventory, exact-schema rehearsal, and transactionally verified guards.

Online installation is deliberately limited to an already clean dataset. Repairs
of historical orphans must be rehearsed and reviewed separately. No HTTP calls,
agent launches, read acknowledgements, worktree operations or service restarts.
"""
import argparse
import hashlib
import json
import pathlib
import sqlite3
import uuid

MIGRATION = pathlib.Path(__file__).resolve().parents[2] / 'crates/db/migrations/20261103110000_workspace_issue_integrity.sql'


def statements(text):
    buffer = ''
    for char in text:
        buffer += char
        if char == ';' and sqlite3.complete_statement(buffer):
            yield buffer
            buffer = ''
    if buffer.strip():
        # sqlite3 accepts a trailing comment and rejects incomplete real SQL.
        yield buffer


def install(connection):
    # executescript would implicitly COMMIT and break the preservation boundary.
    for statement in statements(MIGRATION.read_text()):
        connection.execute(statement)


def inventory(db):
    total, missing, dangling, project_missing = db.execute('''
        SELECT count(*), coalesce(sum(w.task_id IS NULL),0),
        coalesce(sum(w.task_id IS NOT NULL AND t.id IS NULL),0),
        coalesce(sum(t.id IS NOT NULL AND p.id IS NULL),0)
        FROM workspaces w LEFT JOIN tasks t ON t.id=w.task_id
        LEFT JOIN projects p ON p.id=t.project_id''').fetchone()
    return dict(total=total, missing=missing, dangling=dangling, project_missing=project_missing)


def fingerprints(db):
    # All application tables except the bulky append-only execution log. The SQL
    # never targets that log; an authorizer also forbids its mutation below.
    out = {}
    for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
        if table == 'execution_process_logs':
            continue
        name = '"'+table.replace('"','""')+'"'
        digest, count = hashlib.sha256(), 0
        for row in db.execute('SELECT * FROM '+name+' ORDER BY rowid'):
            digest.update(repr(row).encode())
            digest.update(b'\n')
            count += 1
        out[table] = dict(rows=count, sha256=digest.hexdigest())
    return out


def probe(db, check_deletion=True):
    """Uncommitted fixture: never visible to UI/other connections; always undone."""
    workspace, invalid = uuid.uuid4().bytes, uuid.uuid4().bytes
    issue = db.execute('SELECT t.id FROM tasks t JOIN projects p ON p.id=t.project_id LIMIT 1').fetchone()
    if not issue:
        raise ValueError('A valid issue fixture is required')
    db.execute('SAVEPOINT workspace_issue_probe')
    try:
        db.execute('INSERT INTO workspaces(id,branch,name) VALUES(?,?,?)', (workspace, 'integrity-probe', 'Uncommitted integrity probe'))
        linked = db.execute('SELECT task_id FROM workspaces WHERE id=?', (workspace,)).fetchone()[0]
        assert linked == workspace
        assert not any(inventory(db)[k] for k in ['missing','dangling','project_missing'])
        for target in (None, invalid):
            try:
                db.execute('UPDATE workspaces SET task_id=? WHERE id=?', (target,workspace))
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError('Invalid link accepted')
        if check_deletion:
            try:
                db.execute('DELETE FROM tasks WHERE id=?', (linked,))
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError('Linked issue deletion accepted')
        db.execute('UPDATE workspaces SET task_id=? WHERE id=?', (issue[0],workspace))
    finally:
        db.execute('ROLLBACK TO workspace_issue_probe')
        db.execute('RELEASE workspace_issue_probe')
    return {'standalone_link': True, 'invalid_links_rejected': True,
            'linked_delete_rejected': True if check_deletion else 'schema_rehearsal_only', 'valid_relink': True, 'rolled_back': True}


def rehearse(source):
    # Schema only, no private histories or backup payloads copied to storage/RAM.
    db = sqlite3.connect(':memory:')
    for (sql,) in source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL"):
        db.execute(sql)
    for (sql,) in source.execute("SELECT sql FROM sqlite_master WHERE type IN ('index','trigger') AND sql IS NOT NULL"):
        db.execute(sql)
    project, issue, workspace = [uuid.uuid4().bytes for _ in range(3)]
    db.execute('INSERT INTO projects(id,name) VALUES(?,?)', (project,'Isolated schema rehearsal'))
    db.execute('INSERT INTO tasks(id,project_id,title,status) VALUES(?,?,?,?)', (issue,project,'Isolated fixture','todo'))
    db.execute('INSERT INTO workspaces(id,task_id,branch) VALUES(?,?,?)', (workspace,issue,'fixture'))
    db.commit()
    before = fingerprints(db)
    db.execute('BEGIN IMMEDIATE')
    install(db)
    result = probe(db)
    after = fingerprints(db)
    assert all(after.get(table) == value for table,value in before.items())
    db.commit()
    result['existing_tables_unchanged'] = True
    db.close()
    return result


def authorize(action, table, column, database, trigger):
    if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
        if database == 'main' and table not in {'sqlite_master', 'workspace_issue_recoveries', 'projects', 'tasks', 'workspaces', 'workspace_issue_link_revisions'}:
            return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=pathlib.Path, required=True)
    parser.add_argument('--apply-guards', action='store_true')
    args = parser.parse_args()
    database = args.database.resolve(strict=True)
    db = sqlite3.connect('file:'+str(database)+'?mode=ro', uri=True)
    report = {'database':str(database), 'sql_sha256':hashlib.sha256(MIGRATION.read_bytes()).hexdigest(),
              'inventory': inventory(db), 'schema_rehearsal':rehearse(db)}
    db.close()
    if args.apply_guards:
        db = sqlite3.connect('file:'+str(database)+'?mode=rw', uri=True, isolation_level=None, timeout=5)
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        try:
            assert inventory(db) == report['inventory'], 'Dataset changed; re-audit'
            assert all(report['inventory'][key] == 0 for key in ['missing','dangling','project_missing']), 'Historical repairs require separate review'
            before = fingerprints(db)
            db.set_authorizer(authorize)
            install(db)
            report['transactional_probe'] = probe(db, check_deletion=False)
            after = fingerprints(db)
            assert all(after.get(table) == value for table,value in before.items()), 'Existing rows changed; rollback'
            assert after['workspace_issue_recoveries']['rows'] == 0, 'Unexpected repair; rollback'
            report['existing_tables'] = before
            report['inventory_after'] = inventory(db)
            report['existing_rows_unchanged'] = True
            report['guard_triggers'] = [name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'workspace_issue_%' ORDER BY name")]
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
        report['applied'] = True
    else:
        report['applied'] = False
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
