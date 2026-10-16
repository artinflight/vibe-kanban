"""Prepare/review an explicit project snapshot; apply only after owner approval.

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
    return {'sessions':sessions,'project_grants':grants,'subscriptions':subscriptions}


def build_plan(sidechat, vibe, include_archived=False, now=None):
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
        if set(filters)!={'project_id'}:raise ValueError('Review non-project subscriptions before adding destinations')
        covered.add(filters['project_id'])
    if len(covered)!=len(expected['subscriptions']):
        raise ValueError('Overlapping project subscriptions require reconciliation')
    body={'version':1,'created':now,'expires':now+3600,'owner':owner,
        'include_archived':include_archived,'future_projects':False,
        'target_projects':selected,'expected':expected,
        'subscription_requests':[{'name':'vk.sidechat.owner_message.created','arguments':{'project_id':p}}
                                 for p in sorted(target-covered)]}
    body['plan_sha256']=hashlib.sha256(canonical(body).encode()).hexdigest()
    return body


def apply_plan(db,vibe,plan,approved_hash,now=None):
    # This digest fences a reviewed snapshot; it is not evidence of human consent.
    # The operator/agent must obtain that decision before calling the apply CLI.
    now=time.time() if now is None else now
    body={k:v for k,v in plan.items() if k!='plan_sha256'}
    if approved_hash!=plan.get('plan_sha256') or approved_hash!=hashlib.sha256(canonical(body).encode()).hexdigest():
        raise ValueError('Exact reviewed plan digest required')
    if not plan['created']<=now<plan['expires'] or plan['version']!=1 or plan['future_projects'] is not False:
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
        db.commit()
    except BaseException:
        db.rollback();raise
    return {'paired_sessions_updated':len(plan['expected']['sessions']),
            'projects_per_session':len(target),'subscriptions_changed':0,'future_projects':False}


def summary(plan):
    return {'plan_sha256':plan['plan_sha256'],'paired_sessions':len(plan['expected']['sessions']),
        'projects':len(plan['target_projects']),'archived_projects':sum(p['archived'] for p in plan['target_projects']),
        'indefinite_sessions':sum(s['expires']==0 for s in plan['expected']['sessions']),
        'existing_subscriptions_preserved':len(plan['expected']['subscriptions']),
        'additional_platform_subscriptions_needed':len(plan['subscription_requests']),
        'future_projects':False,'applied':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sidechat-db',required=True)
    parser.add_argument('--vibe-db',required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    plan=sub.add_parser('plan')
    plan.add_argument('--include-archived',action='store_true')
    plan.add_argument('--output',required=True,help='New mode-0600 private plan; never commit')
    apply=sub.add_parser('apply')
    apply.add_argument('--plan',required=True)
    apply.add_argument('--approved-plan-sha256',required=True)
    apply.add_argument('--backup',required=True,help='Existing private SQLite backup verified/mirrored per rollout runbook')
    args=parser.parse_args()
    with readonly(args.vibe_db) as vibe:
        if args.command=='plan':
            with readonly(args.sidechat_db) as db:result=build_plan(db,vibe,args.include_archived)
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
