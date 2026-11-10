"""Persistent resource drafts; standard-library SQLite only."""
from pricing_activity import record as record_activity, preserve_latest, initialize as initialize_activity
import json
import math
import re
import sqlite3
from datetime import datetime, timezone

class PlanError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)

FIELDS = ('role', 'capability', 'secondary', 'department', 'location', 'country', 'grade')

def initialize(database):
    initialize_activity(database)
    with sqlite3.connect(database) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS pricing_resource_plans (
            case_id TEXT PRIMARY KEY REFERENCES pricing_cases(case_id),
            revision INTEGER NOT NULL, months_json TEXT NOT NULL, updated_at TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS pricing_resource_rows (
            case_id TEXT NOT NULL REFERENCES pricing_cases(case_id),
            row_id TEXT NOT NULL, position INTEGER NOT NULL,
            fields_json TEXT NOT NULL, hours_json TEXT NOT NULL,
            PRIMARY KEY(case_id, row_id))''')

def _read(db, case_id):
    if not db.execute('SELECT 1 FROM pricing_cases WHERE case_id=?', (case_id,)).fetchone():
        raise PlanError(404, 'Pricing case not found')
    header = db.execute('SELECT revision, months_json, updated_at FROM pricing_resource_plans WHERE case_id=?', (case_id,)).fetchone()
    if not header:
        return dict(case_id=case_id, revision=0, months=[], resources=[], updated_at=None)
    rows = db.execute('SELECT row_id, fields_json, hours_json FROM pricing_resource_rows WHERE case_id=? ORDER BY position', (case_id,)).fetchall()
    return dict(case_id=case_id, revision=header[0], months=json.loads(header[1]), updated_at=header[2],
                resources=[dict(id=r[0], **json.loads(r[1]), hours=json.loads(r[2])) for r in rows])

def read_plan(database, case_id):
    with sqlite3.connect(database) as db:
        return _read(db, case_id)

def validate(payload):
    if not isinstance(payload, dict):
        raise PlanError(400, 'Send a JSON object')
    expected = payload.get('expected_revision')
    if type(expected) is not int or expected < 0:
        raise PlanError(400, 'expected_revision must be a nonnegative integer')
    months, rows = payload.get('months'), payload.get('resources')
    if not isinstance(months, list) or not 1 <= len(months) <= 24:
        raise PlanError(400, 'Choose between 1 and 24 planning months')
    if any(not isinstance(m, str) or not re.fullmatch(r'[1-9][0-9]{3}-(0[1-9]|1[0-2])', m) for m in months):
        raise PlanError(400, 'Months must use YYYY-MM format')
    if months != sorted(set(months)):
        raise PlanError(400, 'Months must be unique and in chronological order')
    if not isinstance(rows, list) or len(rows) > 100:
        raise PlanError(400, 'A resource draft supports up to 100 rows')
    cleaned, ids = [], set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise PlanError(400, f'Resource {i+1} is invalid')
        ident = row.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', ident) or ident in ids:
            raise PlanError(400, 'Resource IDs must be unique and valid')
        ids.add(ident)
        fields = {}
        for field in FIELDS:
            value = row.get(field, '')
            if not isinstance(value, str) or len(value) > 200:
                raise PlanError(400, f'Resource {i+1}: invalid {field}')
            fields[field] = value.strip()
        # Incomplete dimensions can be saved as draft; readiness stays unreviewed.
        hours = row.get('hours')
        if not isinstance(hours, list) or len(hours) != len(months):
            raise PlanError(400, f'Resource {i+1}: hours must match the planning months')
        for value in hours:
            if value is not None and (type(value) not in (int, float) or not 0 <= value <= 10000 or not math.isfinite(value)):
                raise PlanError(400, f'Resource {i+1}: hours must be blank or between 0 and 10000')
        cleaned.append(dict(id=ident, **fields, hours=hours))
    return expected, months, cleaned

def save_plan(database, case_id, payload):
    expected, months, rows = validate(payload)
    with sqlite3.connect(database, timeout=10) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        current = _read(db, case_id)
        if current['revision'] != expected:
            raise PlanError(409, 'Another save changed this draft. Reload the saved plan before saving again. Your edits have not been overwritten.')
        if current['months'] == months and current['resources'] == rows:
            return current
        preserve_latest(db,case_id,'resource')
        revision = expected + 1
        timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        db.execute('''INSERT INTO pricing_resource_plans VALUES (?, ?, ?, ?)
                      ON CONFLICT(case_id) DO UPDATE SET revision=excluded.revision,
                      months_json=excluded.months_json, updated_at=excluded.updated_at''',
                   (case_id, revision, json.dumps(months), timestamp))
        db.execute('DELETE FROM pricing_resource_rows WHERE case_id=?', (case_id,))
        for position, row in enumerate(rows):
            fields = {key: row[key] for key in FIELDS}
            db.execute('INSERT INTO pricing_resource_rows VALUES (?, ?, ?, ?, ?)',
                       (case_id, row['id'], position, json.dumps(fields), json.dumps(row['hours'])))
        db.execute("UPDATE pricing_cases SET status='Draft' WHERE case_id=? AND status='Requested'", (case_id,))
        record_activity(db,case_id,'resource:'+str(revision),'resource','Resource plan r'+str(revision)+' saved',str(len(rows))+' resources · '+str(len(months))+' planning months.',created_at=timestamp)
        # No formal pricing version, approval or calculated amount is created here.
        return _read(db, case_id)
