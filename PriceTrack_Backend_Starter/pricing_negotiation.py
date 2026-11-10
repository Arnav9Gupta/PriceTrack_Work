from pricing_auth import CURRENT_ACTOR
from pricing_activity import record as record_activity
"""Append-only negotiation notes against saved versions; local demo identities."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import sqlite3
from margin_calculator import CalculationError

KINDS = ('Client Ask', 'Company Offer', 'Internal Note', 'Clarification', 'Approval Feedback')

def initialize(database):
    with sqlite3.connect(database) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS pricing_negotiation_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL, version_number INTEGER NOT NULL,
            kind TEXT NOT NULL, amount_usd TEXT, note TEXT NOT NULL,
            actor_id TEXT NOT NULL, actor_name TEXT NOT NULL, actor_role TEXT NOT NULL,
            created_at TEXT NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_negotiation_case ON pricing_negotiation_events(case_id,event_id)')

def _read(db, case_id):
    case=db.execute('SELECT opportunity_owner FROM pricing_cases WHERE case_id=?',(case_id,)).fetchone()
    if not case:raise CalculationError(404,'Pricing case not found')
    actors=[dict(user_id=r[0],display_name=r[1],role=r[2]) for r in db.execute(
        "SELECT user_id,display_name,role FROM users WHERE enabled=1 AND ((user_id='DEMO-Pricing-Analyst' AND role='Pricing Analyst') OR (role='Client Partner' AND display_name=?)) ORDER BY display_name", (case[0],))]
    signed_in=CURRENT_ACTOR.get()
    if signed_in:
        actors=[{k:signed_in[k] for k in ('user_id','display_name','role')}] if signed_in['role'] in ('Client Partner','Pricing Analyst') else []
    versions=[dict(number=r[0],calculation_revision=r[1],created_at=r[2]) for r in db.execute('SELECT number,calculation_revision,created_at FROM pricing_versions WHERE case_id=? ORDER BY number DESC',(case_id,))]
    rows=db.execute('SELECT event_id,version_number,kind,amount_usd,note,actor_id,actor_name,actor_role,created_at FROM pricing_negotiation_events WHERE case_id=? ORDER BY event_id DESC',(case_id,)).fetchall()
    keys=('event_id','version_number','kind','amount_usd','note','actor_id','actor_name','actor_role','created_at')
    return dict(case_id=case_id,revision=len(rows),demo_only=True,currency='USD',kinds=list(KINDS),actors=actors,versions=versions,events=[dict(zip(keys,r)) for r in rows])

def _amount(value):
    if value is None or value=='':return None
    # Use decimal text for money; do not silently round a submitted amount.
    if isinstance(value,bool) or not isinstance(value,(str,int,float)) or len(str(value))>40:
        raise CalculationError(400,'Enter a USD amount with up to two decimal places')
    try:amount=Decimal(str(value))
    except InvalidOperation:raise CalculationError(400,'Enter a valid USD amount')
    if not amount.is_finite() or amount<0 or amount>Decimal('999999999999.99') or amount!=amount.quantize(Decimal('.01')):
        raise CalculationError(400,'USD amount must be between 0 and 999999999999.99 with up to two decimal places')
    return format(amount,'.2f')

def negotiation(database,case_id,payload=None):
    with sqlite3.connect(database,timeout=10) as db:
        if payload is not None:db.execute('BEGIN IMMEDIATE')
        current=_read(db,case_id)
        if payload is None:return current
        if not isinstance(payload,dict) or type(payload.get('expected_revision')) is not int or type(payload.get('version_number')) is not int:
            raise CalculationError(400,'Negotiation revision and saved version number are required')
        if payload['expected_revision']!=current['revision']:
            raise CalculationError(409,'The negotiation log changed. Reload before saving; your note has not been saved.')
        actor=next((u for u in current['actors'] if u['user_id']==payload.get('actor_id')),None)
        if not actor:raise CalculationError(403,'Select an enabled demo Pricing Analyst or the case Client Partner')
        if not any(v['number']==payload['version_number'] for v in current['versions']):
            raise CalculationError(404,'Saved pricing version not found for this case')
        kind=payload.get('kind');note=payload.get('note')
        if kind not in KINDS:raise CalculationError(400,'Choose a supported negotiation event type')
        if not isinstance(note,str) or not note.strip() or len(note)>4000:
            raise CalculationError(400,'Enter a discussion note of 1 to 4000 characters')
        if payload.get('currency','USD')!='USD':raise CalculationError(400,'Negotiation amounts currently use USD only')
        amount=_amount(payload.get('amount_usd'))
        if kind not in ('Client Ask','Company Offer') and amount is not None:
            raise CalculationError(400,'An amount can only be attached to a Client Ask or Company Offer')
        event=db.execute('INSERT INTO pricing_negotiation_events(case_id,version_number,kind,amount_usd,note,actor_id,actor_name,actor_role,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                   (case_id,payload['version_number'],kind,amount,note.strip(),actor['user_id'],actor['display_name'],actor['role'],datetime.now(timezone.utc).isoformat(timespec='seconds')))
        record_activity(db,case_id,'negotiation:'+str(event.lastrowid),'negotiation',kind+' recorded',note.strip(),actor=actor['display_name']+' · '+actor['role']+(' · signed-in local user' if CURRENT_ACTOR.get() else ' · demo identity'),version=payload['version_number'])
        db.commit()
        return _read(db,case_id)
