"""Read-only overview of local source records and persisted pricing work."""
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from margin_calculator import reference


def dashboard(database,allowed=None):
    reference_hash=reference()['source_sha256']
    with sqlite3.connect(database) as db:
        db.row_factory=sqlite3.Row
        db.execute('BEGIN')
        values=tuple(sorted(allowed)) if allowed is not None else ()
        restriction=('c.opportunity_id IN ('+','.join('?' for _ in values)+')') if values else '0' if allowed is not None else '1'
        cases=[dict(row) for row in db.execute('''SELECT c.case_id,c.account_name,c.opportunity_name,
            c.opportunity_id,c.opportunity_owner,c.status,c.created_at,
            p.revision AS resource_revision,w.revision AS calculation_revision,
            w.resource_revision AS calculated_resource_revision,w.reference_hash AS calculation_reference_hash,
            v.number AS version_number,v.calculation_revision AS version_calculation_revision,v.snapshot_json,
            r.status AS review_status,r.step AS review_step
            FROM pricing_cases c
            LEFT JOIN pricing_resource_plans p ON p.case_id=c.case_id
            LEFT JOIN pricing_workbook_calculations w ON w.case_id=c.case_id
            LEFT JOIN pricing_versions v ON v.case_id=c.case_id AND v.number=(SELECT MAX(v2.number) FROM pricing_versions v2 WHERE v2.case_id=c.case_id)
            LEFT JOIN pricing_demo_reviews r ON r.case_id=c.case_id AND r.version_number=v.number
            WHERE '''+restriction+''' ORDER BY c.created_at DESC,c.case_id''',values)]
        source_count=db.execute('SELECT COUNT(*) FROM salesforce_opportunities c WHERE '+restriction,values).fetchone()[0]
        version_count=db.execute('SELECT COUNT(*) FROM pricing_versions v JOIN pricing_cases c ON c.case_id=v.case_id WHERE '+restriction,values).fetchone()[0]
        discussion_count=db.execute('SELECT COUNT(*) FROM pricing_negotiation_events n JOIN pricing_cases c ON c.case_id=n.case_id WHERE '+restriction,values).fetchone()[0]
        status_counts=Counter();review_counts=Counter();total=Decimal(0);valued=0;outdated=0;unversioned=0
        output=[]
        # Keep totals exact even when many high-precision version revenues are added.
        with localcontext() as context:
            context.prec=160
            for case in cases:
                status_counts[case['status']]+=1
                snapshot=json.loads(case.pop('snapshot_json')) if case.get('snapshot_json') else None
                result=(snapshot or {}).get('result',{})
                stale=case['calculation_revision'] is not None and (case['calculated_resource_revision']!=(case['resource_revision'] or 0) or case['calculation_reference_hash']!=reference_hash)
                changed=case['calculation_revision'] is not None and case['calculation_revision']!=case['version_calculation_revision']
                review=case['review_status'] or 'Not requested'
                waiting_on=('BU Head' if case['review_step']==0 else 'Finance') if review=='Pending' else None
                if case['version_number'] is None:
                    unversioned+=1;review='No saved version'
                else:review_counts[waiting_on or review]+=1
                if stale:outdated+=1
                currency=result.get('currency')
                revenue=result.get('revenue')
                try:amount=Decimal(str(revenue)) if revenue is not None else None
                except InvalidOperation:amount=None
                if currency=='USD' and amount is not None and amount.is_finite():total+=amount;valued+=1
                if case['calculation_revision'] is None:
                    action='calculator';action_label='Calculate pricing'
                elif stale:
                    action='calculator';action_label='Recalculate outdated draft'
                elif changed or case['version_number'] is None:
                    action='versions';action_label='Save calculated version'
                elif review in ('Rejected in demo','Changes requested'):
                    action='calculator';action_label='Revise pricing'
                elif review=='Approved in demo':
                    action='negotiation';action_label='Open negotiation log'
                else:
                    action='approvals';action_label='Review version' if review=='Pending' else 'Request demo review'
                output.append(dict(case_id=case['case_id'],account_name=case['account_name'],opportunity_name=case['opportunity_name'],opportunity_id=case['opportunity_id'],owner=case['opportunity_owner'],status=case['status'],created_at=case['created_at'],resource_revision=case['resource_revision'] or 0,calculation_revision=case['calculation_revision'],calculation_stale=stale,draft_differs_from_version=changed,latest_version=case['version_number'],review_status=review,waiting_on=waiting_on,currency=currency,revenue=revenue,cm=result.get('cm'),gm=result.get('gm'),action=action,action_label=action_label))
        return dict(generated_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),source='Local SQLite · synthetic source records',demo_approvals=True,
                    counts=dict(opportunities=source_count,cases=len(output),saved_versions=version_count,negotiation_entries=discussion_count,pending_reviews=review_counts['BU Head']+review_counts['Finance'],pending_bu=review_counts['BU Head'],pending_finance=review_counts['Finance'],latest_approved_demo=review_counts['Approved in demo'],outdated_calculations=outdated,cases_without_versions=unversioned),
                    latest_version_revenue=dict(currency='USD',amount=str(total) if valued else None,included_cases=valued,excluded_cases=len(output)-valued,basis='One latest saved version per case, across all review statuses. Not booked or approved revenue.'),
                    case_statuses=dict(status_counts),cases=output)
