from pricing_activity import record as record_activity, preserve_latest
"""Workbook-equivalent USD model. Source workbook is never opened for writing.
Rate values are a private immutable export of its cached reference cells.
No source-cost access or Finance authentication is provided by this local MVP.
"""
from pathlib import Path
from decimal import Decimal, InvalidOperation, localcontext
from datetime import datetime, timezone
import json, sqlite3, math
from resource_plan import read_plan

REFERENCE = Path(__file__).resolve().parent / 'references' / 'margin_workbook.json'
class CalculationError(Exception):
    def __init__(self,status,message):self.status=status;self.message=message;super().__init__(message)

def reference():
    return json.loads(REFERENCE.read_text(encoding='utf-8'))

def public_reference():
    ref=reference()
    return {**{k:ref[k] for k in ['source_name','source_sha256','currency','defaults','provenance']},'rates':[{k:r[k] for k in ['id','category','role','experience','key']} for r in ref['rates']],'verticals':[v['name'] for v in ref['verticals']]}

def initialize(database):
    with sqlite3.connect(database) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS pricing_workbook_calculations (
         case_id TEXT PRIMARY KEY REFERENCES pricing_cases(case_id), revision INTEGER NOT NULL,
         resource_revision INTEGER NOT NULL, reference_hash TEXT NOT NULL,
         inputs_json TEXT NOT NULL, result_json TEXT NOT NULL, calculated_at TEXT NOT NULL)''')

def number(value,label,minimum=0,maximum=None,strict_max=False):
    if value is None or isinstance(value,bool) or not isinstance(value,(str,int,float)) or len(str(value))>100:
        raise CalculationError(400,label+' is required and must be numeric')
    try:n=Decimal(str(value))
    except InvalidOperation:raise CalculationError(400,label+' must be numeric')
    if not n.is_finite() or n<Decimal(str(minimum)) or (maximum is not None and (n>=Decimal(str(maximum)) if strict_max else n>Decimal(str(maximum)))):
        raise CalculationError(400,label+' is outside its supported range')
    return n

def _calculate(inputs,ref):
    if not isinstance(inputs,dict):raise CalculationError(400,'Calculation inputs must be an object')
    vertical=next((v for v in ref['verticals'] if v['name']==inputs.get('vertical')),None)
    if vertical is None:raise CalculationError(400,'Choose a workbook project vertical')
    bench=number(inputs.get('bench'),'Bench loading',.05,.10)
    targets={s:number(inputs.get(s+'_cm'),s+' target CM',0,1,True) for s in ['onshore','offshore']}
    hours={s:number(inputs.get(s+'_hours'),s+' hours/month',0,10000) for s in targets}
    rows=inputs.get('resources');ip=inputs.get('ip',[])
    if not isinstance(rows,list) or not isinstance(ip,list) or len(ip)>9 or len(rows)>40:raise CalculationError(400,'Use up to 20 lines per stream and nine IP cost lines')
    rates={r['id']:r for r in ref['rates']};counts={s:0 for s in targets};costs={s:Decimal(0) for s in targets};revenue={s:Decimal(0) for s in targets};people=Decimal(0);has_pm=False;line_results=[]
    for index,row in enumerate(rows):
        if not isinstance(row,dict):raise CalculationError(400,'Invalid resource line')
        stream=row.get('stream');rate=rates.get(str(row.get('rate_id','')))
        if stream not in targets or rate is None:raise CalculationError(400,f'Line {index+1}: choose onshore/offshore and an exact workbook role/experience')
        counts[stream]+=1
        if counts[stream]>20:raise CalculationError(400,'Workbook supports 20 lines per stream')
        rate_value=rate.get(stream+'_cost')
        if rate_value is None or isinstance(rate_value,str) and rate_value.startswith('#'):raise CalculationError(422,'The selected workbook cost reference is unavailable; it cannot be treated as zero')
        cost_rate=number(rate_value,'Workbook hourly cost')
        qty=number(row.get('people'),'People',0,10000);months=number(row.get('months'),'Months',0,1200);billable=number(row.get('billability'),'Billability',0,1)
        cost=qty*months*hours[stream]*billable*cost_rate;rev=cost/(1-targets[stream]);costs[stream]+=cost;revenue[stream]+=rev;people+=qty
        has_pm=has_pm or any(x in rate['key'].lower() for x in ['manager','scrum'])
        line_results.append(dict(line=index+1,stream=stream,role=rate['key'],effective_hours=str(qty*months*hours[stream]*billable),revenue=str(rev),source_cell=f"Master File - Rate Card!{'G' if stream=='onshore' else 'K'}{rate['id']}"))
    ip_cost=Decimal(0)
    for index,row in enumerate(ip):
        if not isinstance(row,dict):raise CalculationError(400,'Invalid IP cost line')
        for field in ['product','phase','module']:
            if not isinstance(row.get(field,''),str) or len(row.get(field,''))>200:raise CalculationError(400,'Invalid IP description input')
        ip_cost+=number(row.get('unit_cost'),f'IP {index+1} unit cost',0,1000000000000)*number(row.get('quantity'),f'IP {index+1} quantity',0,1000000)
    if not rows and not ip:raise CalculationError(400,'Add at least one workbook resource or IP cost line')
    ip_revenue=number(inputs.get('ip_revenue'), 'IP deal revenue',0,1000000000000000)
    labour=costs['onshore']+costs['offshore'];bench_cost=bench*labour;total_cost=labour+bench_cost+ip_cost;total_revenue=revenue['onshore']+revenue['offshore']+ip_revenue
    cm=(total_revenue-total_cost)/total_revenue if total_revenue else None
    def gm(margin,key):return None if margin is None or vertical.get(key) is None else margin*Decimal(str(vertical[key]))
    streams={s:dict(revenue=str(revenue[s]),cm=str((revenue[s]-costs[s])/revenue[s]) if revenue[s] else None,gm=str(gm((revenue[s]-costs[s])/revenue[s],s)) if revenue[s] and vertical.get(s) is not None else None) for s in targets}
    sims=inputs.get('simulation_cm',ref['defaults']['simulation_cm'])
    if not isinstance(sims,list) or len(sims)!=2:raise CalculationError(400,'Provide exactly two simulation CM values')
    simulations=[]
    for target in sims:
        target=number(target,'Simulation CM',0,1,True);simulations.append(dict(target_cm=str(target),revenue=str(total_cost/(1-target)),gm=None,gm_note=ref['provenance']['simulation_gm']))
    result=dict(currency='USD',revenue=str(total_revenue),cm=str(cm) if cm is not None else None,gm=str(gm(cm,'total')) if cm is not None and vertical.get('total') is not None else None,streams=streams,lines=line_results,simulations=simulations,total_people=str(people),pm_role_detected=has_pm,pm_warning=bool(people>4 and not has_pm),source_sha256=ref['source_sha256'],vertical=vertical['name'])
    # Kept internally for reconciliation only; never returned by the API.
    return result,dict(total_cost=str(total_cost),bench_cost=str(bench_cost),onshore_cost=str(costs['onshore']),offshore_cost=str(costs['offshore']),ip_cost=str(ip_cost))

def calculate(inputs,ref=None):
    with localcontext() as context:
        context.prec=34
        return _calculate(inputs,ref or reference())

def read_calculation(database,case_id):
    plan=read_plan(database,case_id);ref=reference()
    with sqlite3.connect(database) as db:
        row=db.execute('SELECT revision,resource_revision,reference_hash,inputs_json,result_json,calculated_at FROM pricing_workbook_calculations WHERE case_id=?',(case_id,)).fetchone()
    if row is None:return dict(revision=0,resource_revision=plan['revision'],current_resource_revision=plan['revision'],stale=False,inputs=None,result=None,calculated_at=None)
    return dict(revision=row[0],resource_revision=row[1],current_resource_revision=plan['revision'],stale=row[1]!=plan['revision'] or row[2]!=ref['source_sha256'],inputs=json.loads(row[3]),result=json.loads(row[4]),calculated_at=row[5])

def save_calculation(database,case_id,payload):
    if not isinstance(payload,dict) or type(payload.get('expected_revision')) is not int or type(payload.get('resource_revision')) is not int:raise CalculationError(400,'Draft and resource revisions are required')
    ref=reference();result,internal=calculate(payload.get('inputs'),ref)
    with sqlite3.connect(database,timeout=10) as db:
        db.execute('PRAGMA foreign_keys=ON');db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT 1 FROM pricing_cases WHERE case_id=?',(case_id,)).fetchone():raise CalculationError(404,'Pricing case not found')
        row=db.execute('SELECT revision,inputs_json,resource_revision,reference_hash FROM pricing_workbook_calculations WHERE case_id=?',(case_id,)).fetchone()
        revision=row[0] if row else 0
        resource_row=db.execute('SELECT revision FROM pricing_resource_plans WHERE case_id=?',(case_id,)).fetchone();resource_revision=resource_row[0] if resource_row else 0
        resource_ids={r[0] for r in db.execute('SELECT row_id FROM pricing_resource_rows WHERE case_id=?',(case_id,))}
        for resource in payload['inputs'].get('resources',[]):
            selected=resource.get('resource_id','')
            if not isinstance(selected,str) or (selected and selected not in resource_ids):raise CalculationError(400,'The selected resource label is not in the saved plan. Reload and choose a valid resource or a standalone workbook line.')
        if revision!=payload['expected_revision'] or resource_revision!=payload['resource_revision']:raise CalculationError(409,'This case changed. Reload before calculating. Your current inputs have not been overwritten.')
        unchanged=row and json.loads(row[1])==payload['inputs'] and row[2]==resource_revision and row[3]==ref['source_sha256']
        if not unchanged:
            preserve_latest(db,case_id,'calculation')
            timestamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
            db.execute('''INSERT INTO pricing_workbook_calculations VALUES(?,?,?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET revision=excluded.revision,resource_revision=excluded.resource_revision,reference_hash=excluded.reference_hash,inputs_json=excluded.inputs_json,result_json=excluded.result_json,calculated_at=excluded.calculated_at''',(case_id,revision+1,resource_revision,ref['source_sha256'],json.dumps(payload['inputs']),json.dumps(result),timestamp))
            record_activity(db,case_id,'calculation:'+str(revision+1),'calculation','Calculation r'+str(revision+1)+' saved','Resource plan r'+str(resource_revision)+'.',created_at=timestamp)
        db.execute("UPDATE pricing_cases SET status='Draft' WHERE case_id=? AND status='Requested'", (case_id,))
        db.commit()
    return read_calculation(database,case_id)
