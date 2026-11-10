from pricing_activity import record as record_activity
import json, sqlite3
from datetime import datetime, timezone
from margin_calculator import CalculationError, reference

def initialize(database):
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE IF NOT EXISTS pricing_versions(case_id TEXT NOT NULL, number INTEGER NOT NULL, calculation_revision INTEGER NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(case_id,number), UNIQUE(case_id,calculation_revision))")

def versions(database, case_id, payload=None):
    with sqlite3.connect(database, timeout=10) as db:
        if payload is not None:
            if not isinstance(payload,dict) or type(payload.get('expected_revision')) is not int:
                raise CalculationError(400,'Calculate and save your draft first.')
            db.execute('BEGIN IMMEDIATE')
        case=db.execute('SELECT * FROM pricing_cases WHERE case_id=?',(case_id,)).fetchone()
        if not case: raise CalculationError(404,'Pricing case not found')
        if payload is not None:
            row=db.execute('SELECT revision,resource_revision,reference_hash,inputs_json,result_json,calculated_at FROM pricing_workbook_calculations WHERE case_id=?',(case_id,)).fetchone()
            plan=db.execute('SELECT revision FROM pricing_resource_plans WHERE case_id=?',(case_id,)).fetchone()
            if not row: raise CalculationError(409,'Calculate and save your draft first.')
            if row[0]!=payload['expected_revision'] or row[1]!=(plan[0] if plan else 0) or row[2]!=reference()['source_sha256']:
                raise CalculationError(409,'Draft changed or calculation is outdated. Recalculate and reload before saving a version.')
            existing=db.execute('SELECT number FROM pricing_versions WHERE case_id=? AND calculation_revision=?',(case_id,row[0])).fetchone()
            if not existing:
                number=db.execute('SELECT COALESCE(MAX(number),0)+1 FROM pricing_versions WHERE case_id=?',(case_id,)).fetchone()[0]
                resources=[dict(row_id=r[0],fields=json.loads(r[1]),hours=json.loads(r[2])) for r in db.execute('SELECT row_id,fields_json,hours_json FROM pricing_resource_rows WHERE case_id=? ORDER BY position',(case_id,))]
                months=db.execute('SELECT months_json FROM pricing_resource_plans WHERE case_id=?',(case_id,)).fetchone()
                snapshot=dict(inputs=json.loads(row[3]),result=json.loads(row[4]),resource_revision=row[1],reference_hash=row[2],calculated_at=row[5],resources=resources,months=json.loads(months[0]) if months else [])
                db.execute('INSERT INTO pricing_versions VALUES(?,?,?,?,?)',(case_id,number,row[0],json.dumps(snapshot),datetime.now(timezone.utc).isoformat(timespec='seconds')))
                record_activity(db,case_id,'version:'+str(number),'version','Pricing version V'+str(number)+' saved','Calculation r'+str(row[0])+'.',version=number)
            db.commit()
        return {'versions':[dict(number=r[0],calculation_revision=r[1],snapshot=json.loads(r[2]),created_at=r[3]) for r in db.execute('SELECT number,calculation_revision,snapshot_json,created_at FROM pricing_versions WHERE case_id=? ORDER BY number DESC',(case_id,))]}
