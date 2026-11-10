"""Recorded client acceptance and local handoff preparation; no external project creation."""
import json
import sqlite3
from datetime import datetime, timezone, date
from pricing_auth import CURRENT_ACTOR
from pricing_activity import record
from margin_calculator import CalculationError

def initialize(database):
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE IF NOT EXISTS pricing_handoff_events(id INTEGER PRIMARY KEY AUTOINCREMENT,case_id TEXT NOT NULL,action TEXT NOT NULL,version_number INTEGER NOT NULL,details TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL)')

def handoff(database, case_id, payload=None):
    with sqlite3.connect(database,timeout=10) as db:
        if payload is not None: db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT 1 FROM pricing_cases WHERE case_id=?',(case_id,)).fetchone(): raise CalculationError(404,'Case not found')
        versions=[r[0] for r in db.execute('SELECT number FROM pricing_versions WHERE case_id=? ORDER BY number DESC',(case_id,))]
        rows=db.execute('SELECT id,action,version_number,details,actor,created_at FROM pricing_handoff_events WHERE case_id=? ORDER BY id',(case_id,)).fetchall()
        events=[dict(id=r[0],action=r[1],version_number=r[2],details=json.loads(r[3]),actor=r[4],created_at=r[5]) for r in rows]
        active=None; prepared=None
        for e in events:
            if e['action']=='record_agreement': active=e;prepared=None
            elif e['action']=='withdraw_agreement': active=None;prepared=None
            else: prepared=e
        if payload is not None:
            actor=CURRENT_ACTOR.get()
            if not actor or actor['role'] not in ('Client Partner','Pricing Analyst'): raise CalculationError(403,'Your role cannot record agreements or prepare handoffs')
            if type(payload.get('expected_revision')) is not int or payload['expected_revision']!=len(events): raise CalculationError(409,'Record changed. Reload before saving.')
            action=payload.get('action');v=payload.get('version_number')
            if type(v) is not int or not versions or v!=versions[0]: raise CalculationError(409,'Choose the latest saved pricing version.')
            details={}
            def text(key):
                value=payload.get(key)
                if not isinstance(value,str) or not value.strip() or len(value)>2000: raise CalculationError(400,'Provide '+key.replace('_',' ')+' (maximum 2000 characters).')
                details[key]=value.strip();return details[key]
            if action=='record_agreement':
                if active: raise CalculationError(409,'Withdraw the existing agreement before recording a replacement.')
                text('client_contact');text('evidence_reference');text('note')
                try:
                    accepted=date.fromisoformat(text('accepted_date'))
                    if accepted>date.today(): raise ValueError()
                except ValueError: raise CalculationError(400,'Acceptance date must be a valid date, today or earlier.')
                if payload.get('confirm') is not True: raise CalculationError(400,'Confirm that client acceptance was received for this exact version.')
            elif action=='withdraw_agreement':
                if not active: raise CalculationError(409,'No active agreement to withdraw.')
                text('note');details['agreement_id']=active['id']
            elif action=='prepare_handoff':
                if not active or active['version_number']!=v: raise CalculationError(409,'Record client acceptance for the latest version first.')
                if prepared: raise CalculationError(409,'Handoff already prepared for this agreement.')
                text('delivery_owner');text('handoff_note');details.update(agreement_id=active['id'],status='Prepared locally — pending company approval and Project Tracker integration')
            else: raise CalculationError(400,'Unsupported action')
            now=datetime.now(timezone.utc).isoformat(timespec='seconds')
            cursor=db.execute('INSERT INTO pricing_handoff_events(case_id,action,version_number,details,actor,created_at) VALUES(?,?,?,?,?,?)',(case_id,action,v,json.dumps(details),actor['user_id'],now))
            record(db,case_id,'handoff:'+str(cursor.lastrowid),'handoff',action.replace('_',' ').capitalize(),json.dumps(details),version=v)
            db.commit()
            return handoff(database,case_id)
        return dict(case_id=case_id,revision=len(events),versions=versions,agreement=active,handoff=prepared,agreement_outdated=bool(active and versions and active['version_number']!=versions[0]),events=list(reversed(events)),integration_status='Not connected',company_approval_status='Unconfirmed — production release blocked')
