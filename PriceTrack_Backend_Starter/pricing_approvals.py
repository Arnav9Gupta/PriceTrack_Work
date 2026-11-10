from pricing_auth import CURRENT_ACTOR
from pricing_activity import record as record_activity
"""Local synthetic-user approval demonstration. Not authenticated company approval."""
import json
import sqlite3
from datetime import datetime, timezone
from margin_calculator import CalculationError, reference

ROUTE = ('BU Head', 'Finance')
ACTORS = {'DEMO-Pricing-Analyst': 'Pricing Analyst', 'DEMO-BU-Head': 'BU Head', 'DEMO-Finance': 'Finance'}

def initialize(database):
    with sqlite3.connect(database) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS pricing_demo_reviews (
            case_id TEXT NOT NULL, version_number INTEGER NOT NULL,
            status TEXT NOT NULL, step INTEGER NOT NULL, submitted_by TEXT NOT NULL,
            PRIMARY KEY(case_id,version_number))''')
        db.execute('''CREATE TABLE IF NOT EXISTS pricing_demo_review_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL,
            version_number INTEGER NOT NULL, actor_id TEXT NOT NULL,
            actor_name TEXT NOT NULL, actor_role TEXT NOT NULL, action TEXT NOT NULL,
            comment TEXT NOT NULL, created_at TEXT NOT NULL)''')

def _actors(db):
    return [dict(user_id=r[0],display_name=r[1],role=r[2]) for r in db.execute(
        "SELECT user_id,display_name,role FROM users WHERE enabled=1 ORDER BY display_name")
        if r[2] in ('Pricing Analyst','BU Head','Finance')]

def _configured(db):
    return db.execute("SELECT 1 FROM workflow_config WHERE setting_group='Approval route' AND source_value='Demo sequential' AND application_value='BU Head > Finance' AND status='Illustrative demo only'").fetchone() is not None

def _read(db, case_id):
    if not db.execute('SELECT 1 FROM pricing_cases WHERE case_id=?',(case_id,)).fetchone():
        raise CalculationError(404,'Pricing case not found')
    rows=db.execute('SELECT number,calculation_revision,snapshot_json,created_at FROM pricing_versions WHERE case_id=? ORDER BY number DESC',(case_id,)).fetchall()
    latest=rows[0][0] if rows else 0
    reviews=[]
    for number, revision, snapshot, created in rows:
        review=db.execute('SELECT status,step,submitted_by FROM pricing_demo_reviews WHERE case_id=? AND version_number=?',(case_id,number)).fetchone()
        status,step,submitter=review if review else ('Not requested',0,None)
        superseded=number<latest and status=='Pending'
        reviews.append(dict(number=number,calculation_revision=revision,result=json.loads(snapshot)['result'],created_at=created,
                            status='Superseded' if superseded else status,step=step,
                            waiting_on=ROUTE[step] if status=='Pending' and not superseded else None,submitted_by=submitter))
    events=[dict(event_id=r[0],version_number=r[1],actor_id=r[2],actor_name=r[3],actor_role=r[4],action=r[5],comment=r[6],created_at=r[7]) for r in db.execute('SELECT event_id,version_number,actor_id,actor_name,actor_role,action,comment,created_at FROM pricing_demo_review_events WHERE case_id=? ORDER BY event_id',(case_id,))]
    return dict(case_id=case_id,demo_only=True,route=list(ROUTE),route_available=_configured(db),actors=_actors(db),revision=len(events),versions=reviews,events=events)

def approvals(database,case_id,payload=None):
    with sqlite3.connect(database,timeout=10) as db:
        if payload is not None: db.execute('BEGIN IMMEDIATE')
        current=_read(db,case_id)
        if payload is None:return current
        if not isinstance(payload,dict) or type(payload.get('expected_revision')) is not int or type(payload.get('version_number')) is not int:
            raise CalculationError(400,'Version number and approval revision are required')
        if payload['expected_revision']!=current['revision']:raise CalculationError(409,'Review changed. Reload before continuing.')
        if not current['route_available']:raise CalculationError(409,'The illustrative demo route is unavailable. Company approval policy remains pending.')
        actor=next((u for u in current['actors'] if u['user_id']==payload.get('actor_id')),None)
        if not actor:raise CalculationError(403,'Select an enabled synthetic demo actor.')
        version=next((v for v in current['versions'] if v['number']==payload['version_number']),None)
        if not version:raise CalculationError(404,'Saved pricing version not found')
        action=payload.get('action');comment=payload.get('comment','')
        if not isinstance(comment,str) or len(comment)>2000:raise CalculationError(400,'Comments must be text, up to 2000 characters')
        comment=comment.strip()
        if action=='submit':
            if actor['role']!='Pricing Analyst':raise CalculationError(403,'Only the demo Pricing Analyst can request review.')
            if version['status']!='Not requested':raise CalculationError(409,'This version already has a review. Save a revised calculation as a new version.')
            if version['number']!=current['versions'][0]['number']:raise CalculationError(409,'Request review for the latest saved version.')
            calculation=db.execute('SELECT revision,resource_revision,reference_hash FROM pricing_workbook_calculations WHERE case_id=?',(case_id,)).fetchone()
            plan=db.execute('SELECT revision FROM pricing_resource_plans WHERE case_id=?',(case_id,)).fetchone()
            if not calculation or calculation[0]!=version['calculation_revision'] or calculation[1]!=(plan[0] if plan else 0) or calculation[2]!=reference()['source_sha256']:
                raise CalculationError(409,'The saved version is outdated. Recalculate and save a new version before requesting review.')
            db.execute('INSERT INTO pricing_demo_reviews VALUES(?,?,?,?,?)',(case_id,version['number'],'Pending',0,actor['user_id']))
        elif action in ('approve','reject','request_changes'):
            if version['status']!='Pending':raise CalculationError(409,'This version has no active review.')
            if actor['role']!=version['waiting_on']:raise CalculationError(403,'This step is assigned to the demo '+version['waiting_on']+'.')
            if not comment:raise CalculationError(400,'Enter a comment explaining your decision.')
            if action=='approve':status,step=('Approved in demo',1) if version['step']==1 else ('Pending',1)
            else:status,step=('Rejected in demo' if action=='reject' else 'Changes requested'),version['step']
            db.execute('UPDATE pricing_demo_reviews SET status=?,step=? WHERE case_id=? AND version_number=?',(status,step,case_id,version['number']))
        else:raise CalculationError(400,'Unknown review action')
        event=db.execute('INSERT INTO pricing_demo_review_events(case_id,version_number,actor_id,actor_name,actor_role,action,comment,created_at) VALUES(?,?,?,?,?,?,?,?)',
                   (case_id,version['number'],actor['user_id'],actor['display_name'],actor['role'],action,comment,datetime.now(timezone.utc).isoformat(timespec='seconds')))
        record_activity(db,case_id,'review:'+str(event.lastrowid),'review',{'submit':'Demo review requested','approve':'Demo review step approved','reject':'Demo version rejected','request_changes':'Changes requested'}[action],comment,actor=actor['display_name']+' · '+actor['role']+(' · signed-in local user' if CURRENT_ACTOR.get() else ' · demo identity'),version=version['number'])
        db.commit()
        return _read(db,case_id)

def inbox(database):
    with sqlite3.connect(database) as db:
        rows=db.execute('SELECT DISTINCT c.case_id,c.account_name FROM pricing_cases c JOIN pricing_demo_reviews r ON r.case_id=c.case_id ORDER BY c.created_at DESC').fetchall()
        return dict(demo_only=True,items=[dict(case_id=case_id,account_name=name,version_number=v['number'],status=v['status'],waiting_on=v['waiting_on']) for case_id,name in rows for v in _read(db,case_id)['versions'] if v['status']!='Not requested'])
