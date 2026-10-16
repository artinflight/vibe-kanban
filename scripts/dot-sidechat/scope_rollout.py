"""Prepare/review project access; persistent all-project mode needs owner approval.

No callback secrets, browser cookies, token hashes, CSRF values or message bodies
are read. Applying changes existing paired-session project lists only; expiration,
credentials, existing grants, messages and subscriptions are preserved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def readonly(path):
    db=sqlite3.connect(Path(path).resolve(strict=True).as_uri()+"?mode=ro",uri=True)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


def projects(db, include_archived):
    result=[]
    for row in db.execute("SELECT id,archived FROM projects ORDER BY id"):
        if row[1] and not include_archived:continue
        value=str(uuid.UUID(bytes=row[0])) if isinstance(row[0],bytes) else str(uuid.UUID(row[0]))
        result.append({'id':value,'archived':bool(row[1])})
    return sorted(result,key=lambda x:x['id'])


def snapshot(db, owner, now):
    sessions=[{'id':r['id'],'projects':json.loads(r['projects']),'expires':r['expires']}
        for r in db.execute("SELECT id,projects,expires FROM browser_sessions WHERE owner=? AND revoked=0 AND (expires=0 OR expires>?) ORDER BY id",(owner,now))]
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    grants=[r[0] for r in db.execute("SELECT project FROM project_grants WHERE owner=? ORDER BY project",(owner,))] if 'project_grants' in tables else []
    subscriptions=[dict(r) for r in db.execute("SELECT id,filters,expires FROM sidechat_subscriptions WHERE owner=? AND active=1 AND expires>? ORDER BY id",(owner,now))]
    policy=[dict(r) for r in db.execute('SELECT enabled FROM owner_project_policies WHERE owner=?',(owner,))] if 'owner_project_policies' in tables else []
    policy_sessions=[r[0] for r in db.execute('SELECT session FROM all_project_sessions WHERE owner=? ORDER BY session',(owner,))] if 'all_project_sessions' in tables else []
    return {'sessions':sessions,'project_grants':grants,'subscriptions':subscriptions,
            'policy':policy,'policy_sessions':policy_sessions}


def build_plan(sidechat, vibe, include_archived=False, now=None, future_projects=False):
    if future_projects:include_archived=True
    now=time.time() if now is None else now
    owners=[r[0] for r in sidechat.execute("SELECT DISTINCT owner FROM browser_sessions WHERE revoked=0 AND (expires=0 OR expires>?)",(now,))]
    if len(owners)!=1:raise ValueError('Exactly one paired owner is required; never guess ownership')
    owner=owners[0]
    selected=projects(vibe,include_archived)
    if not selected:raise ValueError('No projects selected')
    expected=snapshot(sidechat,owner,now)
    target={p['id'] for p in selected}
    if any(not set(s['projects'])<=target for s in expected['sessions']):
        raise ValueError('Plan would remove an existing browser project scope')
    covered=set()
    for subscription in expected['subscriptions']:
        filters=json.loads(subscription['filters'])
        if set(filters)=={'project_id'}:values={filters['project_id']}
        elif set(filters)=={'project_ids'}:values=set(filters['project_ids'])
        elif filters.get('all_projects') is True:
            raise ValueError('All-project subscription already exists; reconcile rather than duplicate')
        else:raise ValueError('Review non-project subscriptions before adding destinations')
        if covered & values:raise ValueError('Overlapping project subscriptions require reconciliation')
        covered.update(values)
    remaining=sorted(target-covered)
    requests=[{'name':'vk.sidechat.owner_message.created','arguments':{'project_ids':remaining[i:i+100]}}
              for i in range(0,len(remaining),100)]
    if future_projects:
        if len(covered)>1000:raise ValueError('Too many existing covered projects for the event exclusion schema')
        requests=[{'name':'vk.sidechat.owner_message.created',
                   'arguments':{'all_projects':True,'exclude_project_ids':sorted(covered)}}]
    body={'version':2 if future_projects else 1,'created':now,'expires':now+3600,'owner':owner,
        'include_archived':include_archived,'future_projects':future_projects,
        'target_projects':selected,'expected':expected,
        'subscription_requests':requests}
    body['plan_sha256']=hashlib.sha256(canonical(body).encode()).hexdigest()
    return body


def apply_plan(db,vibe,plan,approved_hash,now=None):
    # This digest fences a reviewed snapshot; it is not evidence of human consent.
    # The operator/agent must obtain that decision before calling the apply CLI.
    now=time.time() if now is None else now
    body={k:v for k,v in plan.items() if k!='plan_sha256'}
    if approved_hash!=plan.get('plan_sha256') or approved_hash!=hashlib.sha256(canonical(body).encode()).hexdigest():
        raise ValueError('Exact reviewed plan digest required')
    if not plan['created']<=now<plan['expires'] or (plan['version'],plan['future_projects'],plan['include_archived']) not in ((1,False,False),(1,False,True),(2,True,True)):
        raise ValueError('Expired or unsupported plan; prepare a fresh review')
    if projects(vibe,plan['include_archived'])!=plan['target_projects']:
        raise ValueError('Project inventory changed; prepare a fresh plan')
    db.execute('BEGIN IMMEDIATE')
    try:
        if snapshot(db,plan['owner'],now)!=plan['expected']:
            raise ValueError('Pairing, grants or subscriptions changed; no access was modified')
        target=sorted(p['id'] for p in plan['target_projects'])
        if not target or any(not set(s['projects'])<=set(target) for s in plan['expected']['sessions']):
            raise ValueError('Scope removal is not supported')
        db.execute('CREATE TABLE IF NOT EXISTS project_grants(owner TEXT NOT NULL,project TEXT NOT NULL,PRIMARY KEY(owner,project))')
        for project in target:
            db.execute('INSERT OR IGNORE INTO project_grants VALUES (?,?)',(plan['owner'],project))
        for session in plan['expected']['sessions']:
            db.execute('UPDATE browser_sessions SET projects=? WHERE id=? AND owner=? AND revoked=0',
                       (canonical(target),session['id'],plan['owner']))
        if plan['future_projects']:
            db.execute('CREATE TABLE IF NOT EXISTS owner_project_policies(owner TEXT PRIMARY KEY,enabled INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS all_project_sessions(owner TEXT NOT NULL,session TEXT NOT NULL,PRIMARY KEY(owner,session))')
            db.execute('INSERT INTO owner_project_policies VALUES (?,1) ON CONFLICT(owner) DO UPDATE SET enabled=1',(plan['owner'],))
            for session in plan['expected']['sessions']:
                db.execute('INSERT OR IGNORE INTO all_project_sessions VALUES (?,?)',(plan['owner'],session['id']))
        db.commit()
    except BaseException:
        db.rollback();raise
    return {'paired_sessions_updated':len(plan['expected']['sessions']),
            'projects_per_session':len(target),'subscriptions_changed':0,'future_projects':plan['future_projects']}


def reconcile_projects(db,vibe,now=None):
    """Trusted publisher only: expand approved sessions; never create/revive sessions.

    Reads physical projects including archived rows. No callback/subscription writes,
    message writes, token reads, or browser/backend restart. Removed projects retain
    their old history grants; authoritative workspace resolution still gates use.
    """
    now=time.time() if now is None else now
    target={p['id'] for p in projects(vibe,True)}
    changed=0
    db.execute('BEGIN IMMEDIATE')
    try:
        owners=[r[0] for r in db.execute('SELECT owner FROM owner_project_policies WHERE enabled=1')]
        for owner in owners:
            for project in target:
                db.execute('INSERT OR IGNORE INTO project_grants VALUES (?,?)',(owner,project))
            for session in db.execute("""SELECT s.id,s.projects FROM browser_sessions s
                    JOIN all_project_sessions a ON a.session=s.id AND a.owner=s.owner
                    WHERE s.owner=? AND s.revoked=0 AND (s.expires=0 OR s.expires>?)""",(owner,now)).fetchall():
                previous=set(json.loads(session['projects']))
                if not target<=previous:
                    db.execute('UPDATE browser_sessions SET projects=? WHERE id=? AND owner=? AND revoked=0',
                               (canonical(sorted(target|previous)),session['id'],owner))
                    changed+=1
        db.commit()
    except BaseException:
        db.rollback();raise
    return {'projects':len(target),'sessions_updated':changed}


def summary(plan):
    return {'plan_sha256':plan['plan_sha256'],'paired_sessions':len(plan['expected']['sessions']),
        'projects':len(plan['target_projects']),'archived_projects':sum(p['archived'] for p in plan['target_projects']),
        'indefinite_sessions':sum(s['expires']==0 for s in plan['expected']['sessions']),
        'existing_subscriptions_preserved':len(plan['expected']['subscriptions']),
        'additional_platform_subscriptions_needed':len(plan['subscription_requests']),
        'additional_finite_projects_requested':sum(len(r['arguments'].get('project_ids',[])) for r in plan['subscription_requests']),
        'future_projects':plan['future_projects'],'all_projects_subscription_requested':plan['future_projects'],'applied':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sidechat-db',required=True)
    parser.add_argument('--vibe-db',required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    plan=sub.add_parser('plan')
    plan.add_argument('--include-archived',action='store_true')
    plan.add_argument('--all-projects',action='store_true',help='Persistent current, archived and future project policy for the reviewed paired sessions')
    plan.add_argument('--output',required=True,help='New mode-0600 private plan; never commit')
    apply=sub.add_parser('apply')
    apply.add_argument('--plan',required=True)
    apply.add_argument('--approved-plan-sha256',required=True)
    apply.add_argument('--backup',required=True,help='Existing private SQLite backup verified/mirrored per rollout runbook')
    args=parser.parse_args()
    with readonly(args.vibe_db) as vibe:
        if args.command=='plan':
            with readonly(args.sidechat_db) as db:result=build_plan(db,vibe,args.include_archived,future_projects=args.all_projects)
            fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as output:json.dump(result,output,indent=2);output.write('\n')
            print(json.dumps(summary(result)))
        else:
            plan=json.loads(Path(args.plan).read_text())
            source=Path(args.sidechat_db).resolve(strict=True)
            backup=Path(args.backup).resolve(strict=True)
            if source==backup or backup.stat().st_mode&0o077:
                raise ValueError('Separate private backup required')
            with readonly(backup) as saved:
                if saved.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or snapshot(saved,plan['owner'],plan['created'])!=plan['expected']:
                    raise ValueError('Backup does not preserve the reviewed pairing state')
            with sqlite3.connect(source,isolation_level=None) as db:
                db.row_factory=sqlite3.Row
                print(json.dumps(apply_plan(db,vibe,plan,args.approved_plan_sha256)))


if __name__=='__main__':main()
