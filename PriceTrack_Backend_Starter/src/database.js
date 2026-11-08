"use strict";

const fs = require("node:fs");
const path = require("node:path");
const initSqlJs = require("sql.js");

const databasePath = path.resolve(process.env.SQLITE_PATH || "./data/pricetrack.sqlite");
let db;

const schema = `
  CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    source TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    cost_access INTEGER NOT NULL DEFAULT 0
  );

  CREATE TABLE IF NOT EXISTS salesforce_opportunities (
    opportunity_id TEXT PRIMARY KEY,
    proposal_number TEXT,
    parent_account_id TEXT,
    account_id TEXT,
    account_name TEXT,
    opportunity_owner TEXT,
    opportunity_name TEXT,
    stage TEXT,
    fiscal_period TEXT,
    amount TEXT,
    probability REAL,
    age INTEGER,
    close_date TEXT,
    created_date TEXT,
    next_step TEXT,
    lead_source TEXT,
    type TEXT,
    historical_ct_proposal_number TEXT,
    pe_proposal_number TEXT,
    proposal_date TEXT,
    proposal_submission_date TEXT,
    project_start_date TEXT,
    project_end_date TEXT,
    q1_accrued_value TEXT,
    q2_accrued_value TEXT,
    q3_accrued_value TEXT,
    q4_accrued_value TEXT,
    parent_account TEXT,
    opportunity_type TEXT,
    solutions_services TEXT,
    last_modified_date TEXT,
    products TEXT,
    vertical TEXT,
    sub_vertical TEXT,
    primary_capability TEXT,
    primary_functionality TEXT,
    source_of_lead TEXT,
    contact_role TEXT
  );

  CREATE TABLE IF NOT EXISTS user_opportunity_scope (
    user_id TEXT NOT NULL,
    opportunity_id TEXT NOT NULL,
    account_id TEXT,
    scope_type TEXT,
    PRIMARY KEY (user_id, opportunity_id)
  );

  CREATE TABLE IF NOT EXISTS business_unit_mapping (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_vertical TEXT,
    source_sub_vertical TEXT,
    child_bu TEXT,
    bu_head_user_id TEXT,
    mapping_status TEXT
  );

  CREATE TABLE IF NOT EXISTS capability_mapping (
    capability_id TEXT PRIMARY KEY,
    source_capability TEXT,
    reviewer_user_id TEXT,
    status TEXT
  );

  CREATE TABLE IF NOT EXISTS client_rates (
    rate_id TEXT PRIMARY KEY,
    scope TEXT,
    account_id TEXT,
    role_experience_key TEXT,
    role TEXT,
    experience TEXT,
    delivery_location TEXT,
    currency TEXT,
    unit TEXT,
    selling_rate REAL,
    effective_from TEXT,
    effective_to TEXT,
    status TEXT,
    basis TEXT
  );

  CREATE TABLE IF NOT EXISTS standard_rates (
    rate_id TEXT PRIMARY KEY,
    scope TEXT,
    account_id TEXT,
    role_experience_key TEXT,
    role TEXT,
    experience TEXT,
    delivery_location TEXT,
    currency TEXT,
    unit TEXT,
    selling_rate REAL,
    effective_from TEXT,
    effective_to TEXT,
    status TEXT,
    basis TEXT
  );

  CREATE TABLE IF NOT EXISTS workflow_config (
    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_group TEXT,
    source_value TEXT,
    application_value TEXT,
    status TEXT,
    note TEXT
  );

  CREATE INDEX IF NOT EXISTS idx_opportunities_owner ON salesforce_opportunities(opportunity_owner);
  CREATE INDEX IF NOT EXISTS idx_opportunities_account ON salesforce_opportunities(account_id);
  CREATE INDEX IF NOT EXISTS idx_opportunities_stage ON salesforce_opportunities(stage);
  CREATE INDEX IF NOT EXISTS idx_scope_opportunity ON user_opportunity_scope(opportunity_id);
  CREATE INDEX IF NOT EXISTS idx_client_rates_account ON client_rates(account_id);
  CREATE INDEX IF NOT EXISTS idx_workflow_group ON workflow_config(setting_group);
`;

async function connectDatabase() {
  if (db) return db;

  const SQL = await initSqlJs();
  fs.mkdirSync(path.dirname(databasePath), { recursive: true });
  db = fs.existsSync(databasePath)
    ? new SQL.Database(fs.readFileSync(databasePath))
    : new SQL.Database();

  db.run("PRAGMA foreign_keys = ON");
  db.run(schema);
  saveDatabase();
  return db;
}

function getDatabase() {
  if (!db) throw new Error("Database is not connected. Call connectDatabase() first.");
  return db;
}

function saveDatabase() {
  if (!db) throw new Error("Database is not connected. Call connectDatabase() first.");
  fs.writeFileSync(databasePath, Buffer.from(db.export()));
}

function queryRows(sql, params = []) {
  const result = getDatabase().exec(sql, params);
  if (!result.length) return [];
  return result[0].values.map((values) =>
    Object.fromEntries(result[0].columns.map((column, index) => [column, values[index]]))
  );
}

module.exports = { connectDatabase, getDatabase, queryRows, saveDatabase, databasePath };
