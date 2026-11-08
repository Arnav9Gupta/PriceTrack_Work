"use strict";

const express = require("express");
const { connectDatabase, queryRows } = require("./database");

const app = express();
const port = Number(process.env.PORT || 3000);
app.use(express.json());

function count(table) {
  const allowed = new Set([
    "users", "user_opportunity_scope", "business_unit_mapping", "capability_mapping",
    "client_rates", "standard_rates", "workflow_config", "salesforce_opportunities"
  ]);
  if (!allowed.has(table)) throw new Error("Unknown table");
  return queryRows(`SELECT COUNT(*) AS count FROM ${table}`)[0].count;
}

app.get("/", (req, res) => {
  res.json({
    service: "Price Track backend",
    status: "running",
    endpoints: ["/api/health", "/api/opportunities", "/api/users", "/api/mappings/business-units", "/api/mappings/capabilities", "/api/rates/client", "/api/rates/standard", "/api/workflow-config"]
  });
});

app.get("/api/health", (req, res) => {
  res.json({
    status: "ok",
    database: "connected",
    records: {
      users: count("users"),
      opportunities: count("salesforce_opportunities"),
      userOpportunityScopes: count("user_opportunity_scope"),
      businessUnitMappings: count("business_unit_mapping"),
      capabilities: count("capability_mapping"),
      clientRates: count("client_rates"),
      standardRates: count("standard_rates"),
      workflowSettings: count("workflow_config")
    }
  });
});

app.get("/api/opportunities", (req, res) => {
  const limit = Math.min(Math.max(Number.parseInt(req.query.limit, 10) || 100, 1), 200);
  const offset = Math.max(Number.parseInt(req.query.offset, 10) || 0, 0);
  const stage = req.query.stage;
  const sql = stage
    ? "SELECT * FROM salesforce_opportunities WHERE stage = ? ORDER BY opportunity_name LIMIT ? OFFSET ?"
    : "SELECT * FROM salesforce_opportunities ORDER BY opportunity_name LIMIT ? OFFSET ?";
  const params = stage ? [stage, limit, offset] : [limit, offset];
  const opportunities = queryRows(sql, params);
  res.json({ count: opportunities.length, limit, offset, opportunities });
});

app.get("/api/opportunities/:opportunityId", (req, res) => {
  const rows = queryRows(
    "SELECT * FROM salesforce_opportunities WHERE opportunity_id = ?",
    [req.params.opportunityId]
  );
  if (!rows.length) return res.status(404).json({ error: "Opportunity not found" });
  res.json(rows[0]);
});

app.get("/api/users", (req, res) => {
  res.json({ users: queryRows("SELECT * FROM users ORDER BY display_name") });
});
app.get("/api/mappings/business-units", (req, res) => {
  res.json({ mappings: queryRows("SELECT * FROM business_unit_mapping ORDER BY source_vertical, source_sub_vertical") });
});
app.get("/api/mappings/capabilities", (req, res) => {
  res.json({ capabilities: queryRows("SELECT * FROM capability_mapping ORDER BY source_capability") });
});
app.get("/api/rates/client", (req, res) => {
  res.json({ rates: queryRows("SELECT * FROM client_rates ORDER BY account_id, role") });
});
app.get("/api/rates/standard", (req, res) => {
  res.json({ rates: queryRows("SELECT * FROM standard_rates ORDER BY role, experience") });
});
app.get("/api/workflow-config", (req, res) => {
  res.json({ settings: queryRows("SELECT * FROM workflow_config ORDER BY setting_group, config_id") });
});

connectDatabase()
  .then(() => app.listen(port, "127.0.0.1", () => {
    console.log(`Price Track backend running at http://localhost:${port}`);
  }))
  .catch((error) => {
    console.error("Could not start the Price Track backend:", error);
    process.exitCode = 1;
  });
