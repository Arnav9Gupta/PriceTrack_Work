from pricing_auth import CURRENT_ACTOR
"""Transactional local activity events plus clearly identified existing records."""
import json
import sqlite3
from datetime import datetime, timezone

class ActivityError(Exception):
    def __init__(self,status,message):self.status=status;self.message=message;super().__init__(message)

def ensure(db):
    db.execute('''CREATE TABLE IF NOT EXISTS pricing_activity_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL,
        event_key TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
        detail TEXT NOT NULL, actor TEXT NOT NULL, version_number INTEGER,
        created_at TEXT NOT NULL, provenance TEXT NOT NULL DEFAULT 'Recorded event', UNIQUE(case_id,event_key))''')

def initialize(database):
    with sqlite3.connect(database) as db:ensure(db)

def record(db,case_id,key,kind,title,detail='',actor='Local demo session · identity not authenticated',version=None,created_at=None,provenance='Recorded event'):
    signed_in=CURRENT_ACTOR.get()
    if signed_in and actor=='Local demo session · identity not authenticated':actor=signed_in['display_name']+' · '+signed_in['role']+' · '+signed_in['user_id']+' · signed-in local user'
    # Called within the mutation's existing transaction; failure rolls back both.
    ensure(db)
    db.execute('INSERT INTO pricing_activity_events(case_id,event_key,kind,title,detail,actor,version_number,created_at,provenance) VALUES(?,?,?,?,?,?,?,?,?)',
               (case_id,key,kind,title,detail,actor,version,created_at or datetime.now(timezone.utc).isoformat(timespec='seconds'),provenance))

def preserve_latest(db,case_id,kind):
    ensure(db)
    table,at,label={'resource':('pricing_resource_plans','updated_at','Resource plan'),'calculation':('pricing_workbook_calculations','calculated_at','Calculation')}[kind]
    row=db.execute('SELECT revision,'+at+' FROM '+table+' WHERE case_id=?',(case_id,)).fetchone()
    if row and not db.execute('SELECT 1 FROM pricing_activity_events WHERE case_id=? AND event_key=?',(case_id,kind+':'+str(row[0]))).fetchone():
        record(db,case_id,kind+':'+str(row[0]),kind,label+' r'+str(row[0])+' saved','Retained state captured before a later save; earlier edits may be unavailable.',actor='Identity not recorded',created_at=row[1],provenance='Retained state before save')

def timeline(database,case_id):
    with sqlite3.connect(database) as db:
        db.execute('BEGIN')
        case=db.execute('SELECT created_at FROM pricing_cases WHERE case_id=?',(case_id,)).fetchone()
        if not case:raise ActivityError(404,'Pricing case not found')
        events=[dict(event_id=r[0],key=r[1],kind=r[2],title=r[3],detail=r[4],actor=r[5],version_number=r[6],created_at=r[7],provenance=r[8]) for r in db.execute('SELECT event_id,event_key,kind,title,detail,actor,version_number,created_at,provenance FROM pricing_activity_events WHERE case_id=?',(case_id,))]
        keys={event['key'] for event in events}
        def existing(key,kind,title,detail,at,version=None,actor='Identity not recorded',provenance='Existing record'):
            if key in keys:return
            keys.add(key);events.append(dict(event_id=None,key=key,kind=kind,title=title,detail=detail,actor=actor,version_number=version,created_at=at,provenance=provenance))
        existing('case-created','case','Pricing case created','Created from an imported opportunity.',case[0])
        plan=db.execute('SELECT revision,updated_at FROM pricing_resource_plans WHERE case_id=?',(case_id,)).fetchone()
        if plan:existing('resource:'+str(plan[0]),'resource','Resource plan r'+str(plan[0])+' saved','Latest retained resource state; earlier saves may be unavailable.',plan[1],provenance='Latest retained state')
        calculation=db.execute('SELECT revision,calculated_at FROM pricing_workbook_calculations WHERE case_id=?',(case_id,)).fetchone()
        if calculation:existing('calculation:'+str(calculation[0]),'calculation','Calculation r'+str(calculation[0])+' saved','Latest retained calculation.',calculation[1],provenance='Latest retained state')
        for number,revision,snapshot,at in db.execute('SELECT number,calculation_revision,snapshot_json,created_at FROM pricing_versions WHERE case_id=?',(case_id,)):
            existing('version:'+str(number),'version','Pricing version V'+str(number)+' saved','Calculation r'+str(revision)+'.',at,number)
            saved=json.loads(snapshot)
            if saved.get('calculated_at'):
                existing('calculation:'+str(revision),'calculation','Calculation r'+str(revision)+' saved','Retained in a saved version snapshot.',saved['calculated_at'])
        for ident,number,name,role,action,note,at in db.execute('SELECT event_id,version_number,actor_name,actor_role,action,comment,created_at FROM pricing_demo_review_events WHERE case_id=?',(case_id,)):
            existing('review:'+str(ident),'review',{'submit':'Demo review requested','approve':'Demo review step approved','reject':'Demo version rejected','request_changes':'Changes requested'}[action],note,at,number,name+' · '+role+' · demo identity')
        for ident,number,kind,name,role,note,at in db.execute('SELECT event_id,version_number,kind,actor_name,actor_role,note,created_at FROM pricing_negotiation_events WHERE case_id=?',(case_id,)):
            existing('negotiation:'+str(ident),'negotiation',kind+' recorded',note,at,number,name+' · '+role+' · demo identity')
        def order(event):
            try:at=datetime.fromisoformat(event['created_at']).replace(tzinfo=timezone.utc) if datetime.fromisoformat(event['created_at']).tzinfo is None else datetime.fromisoformat(event['created_at'])
            except (ValueError,TypeError):at=datetime.min.replace(tzinfo=timezone.utc)
            return at,event['event_id'] or 0,event['key']
        events.sort(key=order,reverse=True)
        return dict(case_id=case_id,events=events,total=len(events),complete_history=False,
                    note='Future saves are recorded as separate events. Older records are identified by provenance; earlier overwritten resource/calculation edits may be unavailable. Earlier demo actor selections were not authenticated; new event actors reflect signed-in local accounts when available. This is application history, not a tamper-proof compliance archive.')
