from pricing_handoff import initialize as initialize_handoff, handoff as case_handoff
import pricing_auth as auth
from pricing_readiness import readiness as case_readiness
from pricing_activity import record as record_activity, timeline as case_activity, ActivityError
from pricing_dashboard import dashboard as pricing_dashboard
from pricing_negotiation import initialize as initialize_negotiation, negotiation as case_negotiation
from pricing_approvals import initialize as initialize_approvals, approvals as case_approvals, inbox as approval_inbox
from pricing_versions import initialize as initialize_versions, versions as saved_versions
import json
import os
import sqlite3
import uuid
import re
from resource_plan import initialize as initialize_resources, read_plan, save_plan, PlanError
from margin_calculator import initialize as initialize_calculator, public_reference, read_calculation, save_calculation, CalculationError
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
DATABASE_PATH = ROOT / "data" / "pricetrack.sqlite"
PORT = int(os.getenv("PORT", "3000"))

TABLES = {
    "users": "users",
    "opportunities": "salesforce_opportunities",
    "userOpportunityScopes": "user_opportunity_scope",
    "businessUnitMappings": "business_unit_mapping",
    "capabilities": "capability_mapping",
    "clientRates": "client_rates",
    "standardRates": "standard_rates",
    "workflowSettings": "workflow_config",
    "pricingCases": "pricing_cases",
}


def query_rows(sql, params=()):
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]
    finally:
        connection.close()


def count_rows(table):
    # Table names come only from the fixed TABLES mapping above.
    return query_rows(f"SELECT COUNT(*) AS count FROM {table}")[0]["count"]


def initialize_pricing_cases():
    """Create the MVP case table without changing any seeded source table."""
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS pricing_cases (
                case_id TEXT PRIMARY KEY,
                opportunity_id TEXT NOT NULL UNIQUE,
                account_id TEXT,
                account_name TEXT,
                opportunity_name TEXT,
                opportunity_stage TEXT,
                opportunity_type TEXT,
                opportunity_owner TEXT,
                opportunity_amount TEXT,
                status TEXT NOT NULL DEFAULT 'Requested'
                    CHECK (status IN ('Requested', 'Draft', 'Submitted', 'Closed')),
                created_at TEXT NOT NULL,
                FOREIGN KEY (opportunity_id)
                    REFERENCES salesforce_opportunities(opportunity_id)
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_pricing_cases_status "
            "ON pricing_cases(status, created_at DESC)"
        )
        connection.commit()
    finally:
        connection.close()


def record_counts():
    return {
        name: count_rows(table)
        for name, table in TABLES.items()
    }


class PriceTrackHandler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        if status < 300 and getattr(self,"user",None):data=self.personalize(data)
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if getattr(self,'auth_cookie',None):self.send_header('Set-Cookie',self.auth_cookie)
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(body)

    def scope_sql(self,column):
        values=sorted(self.allowed)
        return (column+' IN ('+','.join('?' for _ in values)+')',values) if values else ('0',[])

    def visible_inbox(self):
        result=approval_inbox(DATABASE_PATH)
        ids={r['case_id'] for r in query_rows('SELECT case_id FROM pricing_cases WHERE '+self.scope_sql('opportunity_id')[0],self.scope_sql('opportunity_id')[1])}
        result['items']=[item for item in result['items'] if item['case_id'] in ids]
        return result

    def personalize(self,data):
        path=unquote(urlparse(self.path).path)
        if isinstance(data,dict) and path.endswith(('/approvals','/negotiation')):
            data=dict(data);data['actors']=[a for a in data.get('actors',[]) if a['user_id']==self.user['user_id']]
            data['current_user']=self.user
        if isinstance(data,dict) and path.endswith('/readiness'):
            data['integration_note']='Signed-in local account. These checks use saved inputs. Company production approval rules, enterprise SSO and Project Tracker integration remain pending.'
            if 'submit' not in self.user['permissions']:
                data['ready_for_demo_review_request']=False
                for check in data['checks']:
                    if check['id']=='requester':check.update(status='blocked',detail='Your role cannot submit pricing versions for review.')
        return data

    def authenticate(self,write=False):
        auth.check_request(self.headers)
        state=auth.session(DATABASE_PATH,self.headers)
        if write:auth.check_request(self.headers,True,state['csrf_token'])
        self.user=state['user'];self.allowed=auth.scope(DATABASE_PATH,self.user)
        return auth.CURRENT_ACTOR.set(self.user)

    def do_GET(self):
        self.user=None;self.auth_cookie=None;token=None
        path=unquote(urlparse(self.path).path)
        try:
            auth.check_request(self.headers)
            if path in ('/','/api/health'):
                with sqlite3.connect(DATABASE_PATH) as db:db.execute('SELECT 1')
                return self.send_json(200,{'status':'ok','database':'connected','service':'Price Track'})
            token=self.authenticate()
            if path=='/api/auth/me':return self.send_json(200,auth.public_user(DATABASE_PATH,self.headers))
            if path=='/api/users':auth.require(self.user,'directory')
            else:auth.require(self.user,'read')
            match=re.fullmatch(r'/api/pricing-cases/([A-Za-z0-9-]+)/[^/]+',path)
            if match:auth.require_case(DATABASE_PATH,self.user,match[1])
            if path.startswith('/api/opportunities/') and path!='/api/opportunities/stages':
                auth.require_opportunity(DATABASE_PATH,self.user,unquote(path.rsplit('/',1)[-1]))
            if path=='/api/overview':return self.send_json(404,{'error':{'message':'Use /api/dashboard for scoped overview data.'}})
            return self.domain_GET()
        except auth.AuthError as error:self.send_json(error.status,{'error':{'message':error.message}})
        except sqlite3.Error:self.send_json(500,{'error':{'message':'Could not read account or application data.'}})
        finally:
            if token is not None:auth.CURRENT_ACTOR.reset(token)

    def do_PUT(self):
        self.user=None;self.auth_cookie=None;token=None
        try:
            token=self.authenticate(True)
            path=unquote(urlparse(self.path).path)
            match=re.fullmatch(r'/api/pricing-cases/([A-Za-z0-9-]+)/(resources|workbook-calculation|versions|approvals|negotiation|handoff)',path)
            if not match:return self.send_json(404,{'error':{'message':'Endpoint not found'}})
            auth.require_case(DATABASE_PATH,self.user,match[1])
            right={'resources':'resources','workbook-calculation':'calculate','versions':'version','negotiation':'negotiate','handoff':'negotiate'}.get(match[2])
            if right:auth.require(self.user,right)
            return self.domain_PUT()
        except auth.AuthError as error:self.send_json(error.status,{'error':{'message':error.message}})
        finally:
            if token is not None:auth.CURRENT_ACTOR.reset(token)

    def do_POST(self):
        self.user=None;self.auth_cookie=None;token=None
        path=unquote(urlparse(self.path).path)
        try:
            if path=='/api/auth/login':
                auth.check_request(self.headers,True,login_request=True)
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise auth.AuthError(415,'Send application/json.')
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=4096:raise ValueError()
                    payload=json.loads(self.rfile.read(length))
                    if not isinstance(payload,dict):raise ValueError()
                except (ValueError,UnicodeDecodeError):raise auth.AuthError(400,'Invalid sign-in request.')
                session_token,result=auth.login(DATABASE_PATH,payload.get('user_id'),payload.get('password'),self.client_address[0])
                self.auth_cookie=auth.cookie(session_token)
                return self.send_json(200,result)
            token=self.authenticate(True)
            if path=='/api/auth/logout':
                state=auth.session(DATABASE_PATH,self.headers)
                with sqlite3.connect(DATABASE_PATH) as db:db.execute('DELETE FROM auth_sessions WHERE token_hash=?',(state['token_hash'],))
                self.auth_cookie=auth.cookie(clear=True)
                return self.send_json(200,{'status':'signed_out'})
            auth.require(self.user,'create')
            return self.domain_POST()
        except auth.AuthError as error:self.send_json(error.status,{'error':{'message':error.message}})
        except sqlite3.Error:self.send_json(500,{'error':{'message':'Could not complete authentication.'}})
        finally:
            if token is not None:auth.CURRENT_ACTOR.reset(token)

    def domain_GET(self):
        request = urlparse(self.path)
        path = unquote(request.path)
        params = parse_qs(request.query)

        try:
            handoff_match = re.fullmatch(r"/api/pricing-cases/([A-Za-z0-9-]+)/handoff", path)
            if handoff_match:
                return self.send_json(200, case_handoff(DATABASE_PATH, handoff_match[1]))
            if path == "/":
                self.send_json(200, {
                    "service": "Price Track backend",
                    "status": "running",
                    "database": str(DATABASE_PATH),
                })
                return

            if path == "/api/health":
                self.send_json(200, {
                    "status": "ok",
                    "database": "connected",
                    "records": record_counts(),
                })
                return

            if path == "/api/workbook-reference":
                self.send_json(200, public_reference())
                return
            if path == "/api/approval-inbox":
                self.send_json(200, self.visible_inbox())
                return
            readiness_match = re.fullmatch(r"/api/pricing-cases/([A-Za-z0-9-]+)/readiness", path)
            if readiness_match:
                try:
                    self.send_json(200, case_readiness(DATABASE_PATH, readiness_match[1]))
                except CalculationError as error:
                    self.send_json(error.status, {"error": {"message": error.message}})
                return
            activity_match = re.fullmatch(r"/api/pricing-cases/([A-Za-z0-9-]+)/activity", path)
            if activity_match:
                try:
                    self.send_json(200, case_activity(DATABASE_PATH, activity_match[1]))
                except ActivityError as error:
                    self.send_json(error.status, {"error": {"message": error.message}})
                return
            negotiation_match = re.fullmatch(r"/api/pricing-cases/([A-Za-z0-9-]+)/negotiation", path)
            if negotiation_match:
                try:
                    self.send_json(200, case_negotiation(DATABASE_PATH, negotiation_match[1]))
                except CalculationError as error:
                    self.send_json(error.status, {"error": {"message": error.message}})
                return
            approval_match = re.fullmatch(r"/api/pricing-cases/([A-Za-z0-9-]+)/approvals", path)
            if approval_match:
                try:
                    self.send_json(200, case_approvals(DATABASE_PATH, approval_match[1]))
                except CalculationError as error:
                    self.send_json(error.status, {"error": {"message": error.message}})
                return
            version_match = re.fullmatch(r"/api/pricing-cases/([A-Za-z0-9-]+)/versions", path)
            if version_match:
                try:
                    self.send_json(200, saved_versions(DATABASE_PATH, version_match[1]))
                except CalculationError as error:
                    self.send_json(error.status, {"error": {"message": error.message}})
                return
            calculation_match = re.fullmatch(r"/api/pricing-cases/([A-Za-z0-9-]+)/workbook-calculation", path)
            if calculation_match:
                try:
                    self.send_json(200, read_calculation(DATABASE_PATH, calculation_match[1]))
                except (CalculationError, PlanError) as error:
                    self.send_json(error.status, {"error": {"message": error.message}})
                return

            resource_match = re.fullmatch(r"/api/pricing-cases/([A-Za-z0-9-]+)/resources", path)
            if resource_match:
                try:
                    self.send_json(200, read_plan(DATABASE_PATH, resource_match[1]))
                except PlanError as error:
                    self.send_json(error.status, {"error": {"message": error.message}})
                return

            if path == "/api/pricing-cases":
                self.list_pricing_cases(params)
                return

            if path == "/api/dashboard":
                self.send_json(200, pricing_dashboard(DATABASE_PATH,self.allowed))
                return

            if path == "/api/overview":
                self.send_json(200, {
                    "records": record_counts(),
                    "stages": query_rows(
                        "SELECT stage, COUNT(*) AS count "
                        "FROM salesforce_opportunities "
                        "GROUP BY stage ORDER BY count DESC, stage"
                    ),
                    "recentOpportunities": query_rows(
                        "SELECT opportunity_id, opportunity_name, account_name, "
                        "opportunity_owner, stage, amount "
                        "FROM salesforce_opportunities "
                        "ORDER BY opportunity_name LIMIT 6"
                    ),
                })
                return

            if path == "/api/opportunities/stages":
                self.send_json(200, {
                    "stages": query_rows(
                        "SELECT DISTINCT stage FROM salesforce_opportunities "
                        "WHERE stage IS NOT NULL AND "+self.scope_sql("opportunity_id")[0]+" ORDER BY stage", self.scope_sql("opportunity_id")[1]
                    )
                })
                return

            if path == "/api/opportunities":
                self.list_opportunities(params)
                return

            if path.startswith("/api/opportunities/"):
                opportunity_id = path.rsplit("/", 1)[-1]
                rows = query_rows(
                    "SELECT * FROM salesforce_opportunities WHERE opportunity_id = ?",
                    (opportunity_id,),
                )
                if not rows:
                    self.send_json(404, {"error": "Opportunity not found"})
                else:
                    self.send_json(200, rows[0])
                return

            routes = {
                "/api/users": (
                    "users",
                    "SELECT * FROM users ORDER BY display_name",
                ),
                "/api/mappings/business-units": (
                    "mappings",
                    "SELECT * FROM business_unit_mapping "
                    "ORDER BY source_vertical, source_sub_vertical",
                ),
                "/api/mappings/capabilities": (
                    "capabilities",
                    "SELECT * FROM capability_mapping ORDER BY source_capability",
                ),
                "/api/rates/client": (
                    "rates",
                    "SELECT * FROM client_rates ORDER BY account_id, role",
                ),
                "/api/rates/standard": (
                    "rates",
                    "SELECT * FROM standard_rates ORDER BY role, experience",
                ),
                "/api/workflow-config": (
                    "settings",
                    "SELECT * FROM workflow_config ORDER BY setting_group, config_id",
                ),
            }

            if path in routes:
                key, sql = routes[path]
                if path=='/api/rates/client':
                    restriction,values=self.scope_sql('opportunity_id')
                    sql='SELECT * FROM client_rates WHERE account_id IN (SELECT account_id FROM salesforce_opportunities WHERE '+restriction+') ORDER BY account_id,role'
                    self.send_json(200,{key:query_rows(sql,values)})
                else:self.send_json(200, {key: query_rows(sql)})
                return

            self.send_json(404, {"error": "Endpoint not found"})

        except sqlite3.Error as error:
            self.send_json(500, {"error": "Database error", "detail": str(error)})
        except Exception as error:
            self.send_json(500, {"error": "Server error", "detail": str(error)})

    def send_error(self, status, code, message):
        self.send_json(status, {"error": {"code": code, "message": message}})

    def list_pricing_cases(self, params):
        restriction,values=self.scope_sql('opportunity_id')
        clauses=[restriction]
        for key in ('opportunity_id','case_id'):
            value=params.get(key,[''])[0].strip()
            if value:clauses.append(key+'=?');values.append(value)
        cases=query_rows('SELECT * FROM pricing_cases WHERE '+' AND '.join(clauses)+' ORDER BY created_at DESC LIMIT 200',values)
        self.send_json(200,{'total':len(cases),'pricing_cases':cases})

    def domain_PUT(self):
        path = unquote(urlparse(self.path).path)
        match = re.fullmatch(r"/api/pricing-cases/([A-Za-z0-9-]+)/(resources|workbook-calculation|versions|approvals|negotiation|handoff)", path)
        if not match:
            return self.send_json(404, {"error": {"message": "Endpoint not found"}})
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self.send_json(415, {"error": {"message": "Send application/json"}})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 262144:
                return self.send_json(413, {"error": {"message": "Resource draft is too large or empty"}})
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                return self.send_json(400, {"error": {"message": "Send a JSON object"}})
            if match[2]=='approvals':
                action=payload.get('action')
                auth.require(self.user,'submit' if action=='submit' else 'review_bu' if self.user['role']=='BU Head' else 'review_finance')
            if match[2] in ('approvals','negotiation'):
                if 'actor_id' in payload and payload['actor_id']!=self.user['user_id']:
                    return self.send_json(403,{'error':{'message':'Actor identity must match your signed-in account.'}})
                payload['actor_id']=self.user['user_id']
            result = (save_plan if match[2] == "resources" else saved_versions if match[2] == "versions" else case_approvals if match[2] == "approvals" else case_handoff if match[2] == "handoff" else case_negotiation if match[2] == "negotiation" else save_calculation)(DATABASE_PATH, match[1], payload)
            self.send_json(200, result)
        except (PlanError, CalculationError, auth.AuthError) as error:
            self.send_json(error.status, {"error": {"message": error.message}})
        except (ValueError, UnicodeDecodeError):
            self.send_json(400, {"error": {"message": "Invalid JSON or request length"}})
        except sqlite3.Error:
            self.send_json(500, {"error": {"message": "Could not save the resource draft"}})

    def domain_POST(self):
        request = urlparse(self.path)
        path = unquote(request.path)
        if path != "/api/pricing-cases":
            self.send_error(404, "NOT_FOUND", "Endpoint not found")
            return

        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self.send_error(415, "UNSUPPORTED_MEDIA_TYPE", "Send the request as application/json")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "INVALID_CONTENT_LENGTH", "Invalid request length")
            return
        if content_length < 1 or content_length > 16_384:
            self.send_error(413, "INVALID_REQUEST_SIZE", "Request body must be between 1 byte and 16 KB")
            return

        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_error(400, "INVALID_JSON", "Request body must contain valid JSON")
            return
        if not isinstance(payload, dict):
            self.send_error(400, "INVALID_BODY", "Request body must be a JSON object")
            return

        opportunity_id = payload.get("opportunity_id")
        if not isinstance(opportunity_id, str) or not opportunity_id.strip():
            self.send_error(400, "OPPORTUNITY_ID_REQUIRED", "opportunity_id is required")
            return
        opportunity_id = opportunity_id.strip()
        if len(opportunity_id) > 200:
            self.send_error(400, "INVALID_OPPORTUNITY_ID", "opportunity_id is too long")
            return

        try:auth.require_opportunity(DATABASE_PATH,self.user,opportunity_id)
        except auth.AuthError as error:return self.send_json(error.status,{'error':{'message':error.message}})
        connection = sqlite3.connect(DATABASE_PATH, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM pricing_cases WHERE opportunity_id = ?",
                (opportunity_id,),
            ).fetchone()
            if existing:
                connection.commit()
                self.send_json(200, {"pricing_case": dict(existing), "existing": True})
                return

            opportunity = connection.execute(
                """SELECT opportunity_id, account_id, account_name,
                          opportunity_name, stage, opportunity_type, type,
                          opportunity_owner, amount
                   FROM salesforce_opportunities WHERE opportunity_id = ?""",
                (opportunity_id,),
            ).fetchone()
            if not opportunity:
                connection.rollback()
                self.send_error(404, "OPPORTUNITY_NOT_FOUND", "No imported opportunity matches that ID")
                return

            case = {
                "case_id": str(uuid.uuid4()),
                "opportunity_id": opportunity["opportunity_id"],
                "account_id": opportunity["account_id"],
                "account_name": opportunity["account_name"],
                "opportunity_name": opportunity["opportunity_name"],
                "opportunity_stage": opportunity["stage"],
                "opportunity_type": opportunity["opportunity_type"] or opportunity["type"],
                "opportunity_owner": opportunity["opportunity_owner"],
                "opportunity_amount": opportunity["amount"],
                "status": "Requested",
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            connection.execute(
                """INSERT INTO pricing_cases (
                    case_id, opportunity_id, account_id, account_name,
                    opportunity_name, opportunity_stage, opportunity_type,
                    opportunity_owner, opportunity_amount, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(case[key] for key in case),
            )
            record_activity(connection,case['case_id'],'case-created','case','Pricing case created','Created from imported opportunity '+opportunity_id+'.',created_at=case['created_at'])
            connection.commit()
            self.send_json(201, {"pricing_case": case, "existing": False})
        except sqlite3.IntegrityError as error:
            connection.rollback()
            self.send_error(409, "CASE_CONFLICT", "A pricing case already exists for this opportunity")
        except sqlite3.Error as error:
            connection.rollback()
            self.send_error(500, "DATABASE_ERROR", "Could not create the pricing case")
        finally:
            connection.close()

    def list_opportunities(self, params):
        limit = min(max(int(params.get("limit", ["100"])[0]), 1), 200)
        offset = max(int(params.get("offset", ["0"])[0]), 0)
        stage = params.get("stage", [""])[0].strip()
        search = params.get("q", [""])[0].strip()

        conditions = []
        values = []
        restriction,scope_values=self.scope_sql("opportunity_id")
        conditions.append(restriction);values.extend(scope_values)

        if stage:
            conditions.append("stage = ?")
            values.append(stage)

        if search:
            conditions.append(
                "(opportunity_name LIKE ? OR account_name LIKE ? "
                "OR opportunity_owner LIKE ? OR opportunity_id LIKE ?)"
            )
            pattern = f"%{search}%"
            values.extend([pattern, pattern, pattern, pattern])

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        total = query_rows(
            f"SELECT COUNT(*) AS total FROM salesforce_opportunities {where}",
            values,
        )[0]["total"]

        opportunities = query_rows(
            f"SELECT * FROM salesforce_opportunities {where} "
            "ORDER BY opportunity_name LIMIT ? OFFSET ?",
            [*values, limit, offset],
        )

        self.send_json(200, {
            "total": total,
            "returned": len(opportunities),
            "limit": limit,
            "offset": offset,
            "opportunities": opportunities,
        })


if __name__ == "__main__":
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH}. "
            "Make sure server.py is in the project root."
        )

    auth.initialize(DATABASE_PATH)
    initialize_pricing_cases()
    initialize_resources(DATABASE_PATH)
    initialize_calculator(DATABASE_PATH)
    initialize_versions(DATABASE_PATH)
    initialize_approvals(DATABASE_PATH)
    initialize_negotiation(DATABASE_PATH)
    initialize_handoff(DATABASE_PATH)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), PriceTrackHandler)
    print(f"Price Track Python backend running at http://localhost:{PORT}")
    print(f"Using database: {DATABASE_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Price Track backend.")
        server.server_close()