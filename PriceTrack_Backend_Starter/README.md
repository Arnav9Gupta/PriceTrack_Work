# Price Track Backend Starter

A backend-only Node.js API and SQLite database starter built from the five synthetic Price Track seed workbooks. It contains no frontend and does not use the older Price Track ZIP source.

## Requirements

- Node.js 22 or later
- PowerShell on Windows: use `npm.cmd` if `npm` is blocked by script execution policy

## Install and load the supplied synthetic data

From this folder, run:

```powershell
npm.cmd install
npm.cmd run import:seed
npm.cmd start
```

The importer reads the five Excel files under `data/seed`, writes the rows to `data/pricetrack.sqlite`, and can be run again to update keyed rows without duplicating them. The importer skips the `Read_Me` sheets and excludes Salesforce rows whose stage is Closed Won or Closed Lost. It does not modify the source workbooks.

## API endpoints

- `GET /` service and endpoint list
- `GET /api/health` database status and imported row counts
- `GET /api/opportunities?limit=100&offset=0&stage=Evaluation%20of%20Options`
- `GET /api/opportunities/:opportunityId`
- `GET /api/users`
- `GET /api/mappings/business-units`
- `GET /api/mappings/capabilities`
- `GET /api/rates/client`
- `GET /api/rates/standard`
- `GET /api/workflow-config`

The server binds to `127.0.0.1` for local development. The rate and workflow data are synthetic and include illustrative or pending entries; they are not company-approved pricing policies. No authentication or production deployment is included in this starter.

## Database

The SQLite file is created at `data/pricetrack.sqlite` on first startup. Set `SQLITE_PATH` to use a different local path. The five workbooks are the source inputs; the importer maps their worksheet headers into relational tables. The separate `Margin Calculator` workbook is not included or changed.
