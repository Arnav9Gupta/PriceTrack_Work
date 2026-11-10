"""Read-only case summary and factual local demo review prerequisites."""
import json
import sqlite3
from margin_calculator import reference, CalculationError
from pricing_approvals import _actors, _configured


def readiness(database,case_id):
    ref=reference()
    with sqlite3.connect(database) as db:
        db.row_factory=sqlite3.Row;db.execute('BEGIN')
        found=db.execute('SELECT * FROM pricing_cases WHERE case_id=?',(case_id,)).fetchone()
        if not found:raise CalculationError(404,'Pricing case not found')
        case=dict(found)
        plan=db.execute('SELECT revision,months_json FROM pricing_resource_plans WHERE case_id=?',(case_id,)).fetchone()
        resource_revision=plan[0] if plan else 0
        resource_count=db.execute('SELECT COUNT(*) FROM pricing_resource_rows WHERE case_id=?',(case_id,)).fetchone()[0]
        calculation=db.execute('SELECT revision,resource_revision,reference_hash,result_json,calculated_at FROM pricing_workbook_calculations WHERE case_id=?',(case_id,)).fetchone()
        version=db.execute('SELECT number,calculation_revision,snapshot_json,created_at FROM pricing_versions WHERE case_id=? ORDER BY number DESC LIMIT 1',(case_id,)).fetchone()
        review=db.execute('SELECT status,step FROM pricing_demo_reviews WHERE case_id=? AND version_number=?',(case_id,version[0])).fetchone() if version else None
        stale=bool(calculation and (calculation[1]!=resource_revision or calculation[2]!=ref['source_sha256']))
        matches=bool(calculation and version and version[1]==calculation[0])
        actors=_actors(db);requester=any(actor['role']=='Pricing Analyst' for actor in actors)
        configured=_configured(db);review_status=review[0] if review else 'Not requested' if version else 'No saved version'
        waiting_on=('BU Head' if review[1]==0 else 'Finance') if review and review[0]=='Pending' else None
        checks=[]
        def check(key,label,ok,good,bad,section):
            checks.append(dict(id=key,label=label,status='passed' if ok else 'blocked',detail=good if ok else bad,section=section))
        check('calculation','Calculation saved',bool(calculation),'A saved workbook calculation exists.','Enter workbook inputs and calculate pricing.','calculator')
        check('calculation_current','Calculation uses current saved inputs',bool(calculation and not stale),'The resource revision and workbook reference match.','Recalculate after saving the resource plan or changing the reference snapshot.','calculator')
        check('version','Pricing version saved',bool(version),'A numbered snapshot exists.','Save the calculated draft as a pricing version.','versions')
        check('version_current','Latest version matches saved calculation',matches,'The latest version references this saved calculation.','Save the latest calculated draft as a new version.','versions')
        check('route','Illustrative approval route available',configured,'Imported demo route: BU Head → Finance.','The original illustrative route is missing or changed; confirm configuration.','approvals')
        check('requester','Demo requester available',requester,'An enabled synthetic Pricing Analyst is available.','The synthetic Pricing Analyst is missing or disabled.','approvals')
        check('review','Latest version has no previous review',bool(version and review is None),'A demo review can be requested for this version.','Inspect the version review; after rejection or changes requested, revise and save a new version.','approvals')
        ready=all(item['status']=='passed' for item in checks)
        notes=[dict(status='info',detail='Standalone workbook lines are allowed. A separate resource plan is optional for this calculator mode.')]
        missing=[role for role in ('BU Head','Finance') if not any(actor['role']==role for actor in actors)]
        if missing:notes.append(dict(status='warning',detail='Demo reviewer unavailable: '+', '.join(missing)+'. That review step cannot be completed while its actor is disabled or missing.'))
        result=json.loads(calculation[3]) if calculation else None
        if result and result.get('pm_warning'):notes.append(dict(status='warning',detail='Workbook PM check: more than four people and no Manager/Scrum role selected. Review this warning; no company approval threshold has been assumed.'))
        saved=json.loads(version[2]) if version else None
        def public_result(value):
            return None if value is None else {key:value.get(key) for key in ('currency','revenue','cm','gm','vertical','total_people')}
        if not calculation:next_section,next_label='calculator','Calculate pricing'
        elif stale:next_section,next_label='calculator','Recalculate outdated draft'
        elif not matches:next_section,next_label='versions','Save calculated version'
        elif review_status in ('Rejected in demo','Changes requested'):next_section,next_label='calculator','Revise pricing'
        elif review_status=='Approved in demo':next_section,next_label='negotiation','Open negotiation log'
        else:next_section,next_label='approvals','Review version' if review else 'Request demo review'
        return dict(case=case,demo_only=True,ready_for_demo_review_request=ready,production_approval_ready=False,checks=checks,notes=notes,
                    plan=dict(revision=resource_revision,resources=resource_count,months=len(json.loads(plan[1])) if plan else 0),
                    calculation=None if not calculation else dict(revision=calculation[0],stale=stale,calculated_at=calculation[4],result=public_result(result)),
                    latest_version=None if not version else dict(number=version[0],calculation_revision=version[1],created_at=version[3],matches_calculation=matches,result=public_result(saved.get('result'))),
                    review=dict(status=review_status,waiting_on=waiting_on),next_action=dict(section=next_section,label=next_label),
                    integration_note='Local imported synthetic data. Company sign-in, production approval rules, agreement/handoff and Project Tracker integration remain pending. Unsaved browser edits are not included in these checks.')
