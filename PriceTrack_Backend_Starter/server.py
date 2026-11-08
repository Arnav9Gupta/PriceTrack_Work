import json
import os
import sqlite3
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


def record_counts():
    return {
        name: count_rows(table)
        for name, table in TABLES.items()
    }


class PriceTrackHandler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        request = urlparse(self.path)
        path = unquote(request.path)
        params = parse_qs(request.query)

        try:
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
                        "WHERE stage IS NOT NULL ORDER BY stage"
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
                self.send_json(200, {key: query_rows(sql)})
                return

            self.send_json(404, {"error": "Endpoint not found"})

        except sqlite3.Error as error:
            self.send_json(500, {"error": "Database error", "detail": str(error)})
        except Exception as error:
            self.send_json(500, {"error": "Server error", "detail": str(error)})

    def list_opportunities(self, params):
        limit = min(max(int(params.get("limit", ["100"])[0]), 1), 200)
        offset = max(int(params.get("offset", ["0"])[0]), 0)
        stage = params.get("stage", [""])[0].strip()
        search = params.get("q", [""])[0].strip()

        conditions = []
        values = []

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

    server = ThreadingHTTPServer(("127.0.0.1", PORT), PriceTrackHandler)
    print(f"Price Track Python backend running at http://localhost:{PORT}")
    print(f"Using database: {DATABASE_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Price Track backend.")
        server.server_close()