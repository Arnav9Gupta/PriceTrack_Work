"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { readSheet: readExcelSheet } = require("read-excel-file/node");
const { connectDatabase, getDatabase, saveDatabase } = require("../src/database");

const seedDir = path.resolve("./data/seed");

function normalizeHeader(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function normalizeValue(value) {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === "boolean") return value ? 1 : 0;
  return value === undefined ? null : value;
}

async function readSheet(fileName, sheetName) {
  const filePath = path.join(seedDir, fileName);
  if (!fs.existsSync(filePath)) throw new Error(`Missing seed workbook: ${filePath}`);
  const rows = await readExcelSheet(filePath, sheetName);
  if (!rows.length) return [];
  const headers = rows[0].map(normalizeHeader);
  return rows.slice(1)
    .filter((row) => row.some((value) => value !== null && value !== ""))
    .map((row) => Object.fromEntries(headers.map((header, index) => [header, normalizeValue(row[index])])))
    .filter((record) => Object.keys(record).some((key) => record[key] !== null && record[key] !== ""));
}

function upsertRows(table, rows, primaryKey, mapRecord = (record) => record) {
  if (!rows.length) return 0;
  const db = getDatabase();
  let written = 0;

  for (const input of rows) {
    const record = mapRecord(input);
    const columns = Object.keys(record);
    const values = columns.map((column) => record[column]);
    const placeholders = columns.map(() => "?").join(", ");
    const conflictKeys = Array.isArray(primaryKey) ? primaryKey : [primaryKey];
    const updates = columns.filter((column) => !conflictKeys.includes(column))
      .map((column) => `${column}=excluded.${column}`).join(", ");
    const sql = `INSERT INTO ${table} (${columns.join(", ")}) VALUES (${placeholders}) ` +
      `ON CONFLICT(${conflictKeys.join(", ")}) DO UPDATE SET ${updates}`;
    db.run(sql, values);
    written += 1;
  }
  return written;
}

function asInteger(value) {
  if (value === true || value === 1 || String(value).toLowerCase() === "true") return 1;
  if (value === false || value === 0 || String(value).toLowerCase() === "false") return 0;
  return value === null || value === "" ? 0 : Number(value);
}

async function main() {
  await connectDatabase();
  const db = getDatabase();
  const counts = {};
  db.run("BEGIN TRANSACTION");

  try {
    let rows = await readSheet("05_Salesforce_Synthetic_Open_Opportunities.xlsx", "Sheet1");
    rows = rows.filter((row) => !["closed won", "closed lost"].includes(String(row.stage || "").trim().toLowerCase()));
    counts.opportunities = upsertRows("salesforce_opportunities", rows, "opportunity_id");

    rows = await readSheet("01_Users_and_Role_Mapping.xlsx", "Users");
    counts.users = upsertRows("users", rows, "user_id", (r) => ({ ...r, enabled: asInteger(r.enabled), cost_access: asInteger(r.cost_access) }));
    rows = await readSheet("01_Users_and_Role_Mapping.xlsx", "User_Opportunity_Scope");
    counts.userOpportunityScopes = upsertRows("user_opportunity_scope", rows, ["user_id", "opportunity_id"]);

    rows = await readSheet("02_Business_Unit_and_Capability_Mapping.xlsx", "BU_Mapping");
    counts.businessUnitMappings = rows.length;
    db.run("DELETE FROM business_unit_mapping");
    for (const r of rows) {
      db.run("INSERT INTO business_unit_mapping(source_vertical, source_sub_vertical, child_bu, bu_head_user_id, mapping_status) VALUES(?,?,?,?,?)", [r.source_vertical, r.source_sub_vertical, r.child_bu, r.bu_head_user_id, r.mapping_status]);
    }
    rows = await readSheet("02_Business_Unit_and_Capability_Mapping.xlsx", "Capability_Mapping");
    counts.capabilities = upsertRows("capability_mapping", rows, "capability_id");

    rows = await readSheet("03_Client_and_Standard_Selling_Rates.xlsx", "Client_Rates");
    counts.clientRates = upsertRows("client_rates", rows, "rate_id");
    rows = await readSheet("03_Client_and_Standard_Selling_Rates.xlsx", "Standard_Rates");
    counts.standardRates = upsertRows("standard_rates", rows, "rate_id");

    rows = await readSheet("04_Pricing_Workflow_Configuration.xlsx", "Workflow_Config");
    db.run("DELETE FROM workflow_config");
    counts.workflowSettings = rows.length;
    for (const r of rows) {
      db.run("INSERT INTO workflow_config(setting_group, source_value, application_value, status, note) VALUES(?,?,?,?,?)", [r.setting_group, r.source_value, r.application_value, r.status, r.note]);
    }

    db.run("COMMIT");
    saveDatabase();
    console.log("Seed import complete:");
    console.log(JSON.stringify(counts, null, 2));
  } catch (error) {
    db.run("ROLLBACK");
    throw error;
  }
}

main().catch((error) => {
  console.error("Seed import failed:", error.message);
  process.exitCode = 1;
});
