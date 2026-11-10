## MVP screen scope

Navigation exposes persisted local workflows only. The MVP scope page lists available features and dependencies. Notifications, renewals, exceptions, separate reports, rate imports, prototype wizard and case integrations screens are excluded and their direct routes are blocked. Client and standard selling-rate references and their comparison remain read-only. Admin sees the account directory and scope page. Company approvals and live integration remain pending; demo approvals and local handoff are labelled accordingly. Archived prototype functions remain in source for later refactoring but are not routed into this release.

## Agreement and handoff

Open a persisted case → Agreement & Handoff. Client Partners and Pricing Analysts with case access can record reported client acceptance for the latest saved version, withdraw with a reason, and prepare a local delivery handoff. All case readers can inspect its append-only history. No external project or client message is created. Company approval rules remain unconfirmed, so preparation is not authorization to release a project. A newer saved version invalidates the earlier agreement for further preparation. Evidence is a text reference, not verified document storage. Delivery owner is a routing note, not a confirmed recipient assignment. Existing data is preserved.

# Current setup: sign-in is required

The latest package enables local password sign-in and backend role/opportunity access checks. Earlier unauthenticated examples below are superseded. Follow **AUTH_SETUP.md** before starting. There are no default passwords. Keep your existing data/ folder and SQLite database when installing.

# Price Track frontend for the Python backend

This is an editable HTML, CSS and JavaScript frontend for the existing Price Track Python / SQLite backend. It uses the attached Price_Track_Google_Stitch_UI_Brief(1).txt as its screen specification and navigation source. It follows the brief's restrained ProjectTrack shell, Segoe UI typography, violet accents, light panels, case context and horizontal tab navigation.

The supplied Lovable preview URL could not be accessed during implementation. Its actual screen designs and runtime page connections have NOT been verified. The connected flow here follows the attached brief. The original ProjectTrack screenshots were not attached to this request, so exact visual matching requires a later review against those screenshots.

## Put the files in your existing project

Copy `server.py`, `resource_plan.py`, `margin_calculator.py`, `run_frontend.py`, the **references folder**, and the **public folder** into your existing project:

`D:\PriceTrack_Work\PriceTrack_Backend_Starter`

| File | Destination / purpose |
| --- | --- |
| `server.py` | Updated Python backend; case requests and resource-draft endpoints |
| `resource_plan.py` | Resource validation, revisions and database persistence; beside server.py |
| `margin_calculator.py` | Workbook calculation strategy and saved calculation drafts; beside server.py |
| `references/margin_workbook.json` | Private read-only cached reference export; keep outside public |
| `public/workbook-calculator.js` | Workbook input and backend-result UI |
| `public/resource-plan.js` | Resource editor for cases saved in SQLite |
| `run_frontend.py` | Beside `server.py`; frontend server and local API proxy for the required routes |
| `public/index.html` | Application shell and asset loading |
| `public/styles.css` | Shared layout, typography, cards, navigation, responsive tables |
| `public/app.js` | All screens, routes, API calls and browser draft behavior |
| `public/assets/c5i-logo.png` | Supplied approved C5i artwork; kept as an external image asset |

If you already have frontend files in `public`, keep a copy before placing these files there. This download includes an updated `server.py`. Back up your current `server.py`, then replace it with the included version. It keeps the same SQLite path and existing API routes, and creates the new `pricing_cases` table on startup without changing any seeded source table or Excel workbook.

To copy and paste manually, create those files in VS Code and paste the corresponding source file contents. Copy the PNG into the assets folder; binary image data is not pasted into JavaScript.

## Run on Windows

Open a PowerShell terminal in VS Code:

```powershell
cd "D:\PriceTrack_Work\PriceTrack_Backend_Starter"
py server.py
```

Keep that backend terminal running. Open a **second** terminal in VS Code:

```powershell
cd "D:\PriceTrack_Work\PriceTrack_Backend_Starter"
py run_frontend.py
```

Open **http://localhost:5500** in your browser. Do not double-click index.html, use the file:// protocol, or use a separate Live Server; this frontend launcher also forwards `/api` to your existing backend on port 3000.

No npm installation, Node server, Python package installation or build step is required. The launcher uses only the Python standard library. Python 3.10+ is required; it is compatible with your Python 3.15 environment.

If a port is in use:

```powershell
py run_frontend.py --port 5501
```

Then open http://localhost:5501. If your backend is on another port:

```powershell
py run_frontend.py --backend http://127.0.0.1:3001
```

The frontend runs on its own local port. The included `server.py` preserves your existing backend endpoints and adds case creation. For eventual production integration, serve these assets and API routes from the host application instead of deploying this development launcher.

## What uses your database

These pages fetch your existing read-only API data. No replacement sample rows are substituted if a request fails.

| UI | Endpoint | Expected JSON |
| --- | --- | --- |
| Header connection status | GET `/api/health` | `{ "status": "ok", "database": "connected", "records": { ... } }` |
| Salesforce Opportunities | GET `/api/opportunities?q=&stage=&limit=12&offset=0` | `{ "total": 532, "opportunities": [ ... ] }` |
| Client Cards | GET `/api/rates/client` | `{ "rates": [ ... ] }` |
| Standard Cards | GET `/api/rates/standard` | `{ "rates": [ ... ] }` |
| BU mappings | GET `/api/mappings/business-units` | `{ "mappings": [ ... ] }` |
| Tech COE mappings | GET `/api/mappings/capabilities` | `{ "capabilities": [ ... ] }` |
| Users / access references | GET `/api/users` | `{ "users": [ ... ] }` |
| Workflow references | GET `/api/workflow-config` | `{ "settings": [ ... ] }` |
| Saved pricing cases | GET `/api/pricing-cases` | `{ "pricing_cases": [ ... ] }` |
| Create / reuse a case | POST `/api/pricing-cases` with `{ "opportunity_id": "..." }` | `{ "pricing_case": { ... }, "existing": false }` |

Field names match the starter database schema: `opportunity_id`, `opportunity_name`, `account_name`, `stage`, `role`, `experience`, `delivery_location`, `selling_rate`, `currency`, `effective_from`, etc. Collection endpoints also accept a top-level array. If your current Python server uses different field names or wrappers, adapt the relevant function in app.js.

Opportunity amounts are displayed as supplied. The starter's opportunity schema does not provide a separate currency field, so the UI explicitly says currency is unavailable instead of assuming USD. Financial fixture cases are explicitly USD and are separate from those database records.

This slice supports local source-linked case creation. It reads the opportunity from the seeded SQLite table, snapshots its source fields, saves a `Requested` case, prevents duplicates for the same opportunity, and shows the saved case in Pricing Cases. It does not contact Salesforce, use a Salesforce deep link, enforce account scope through authentication, or write changes back to Salesforce. The one-case-per-opportunity rule is a simple MVP idempotency choice; confirm it with the project owner before broader use.

## Third MVP feature: workbook Margin Calculator

This feature follows the source workbook's onshore/offshore model. It does not use the synthetic contractual selling-rate cards. The source workbook has not been modified. Its exact cached hourly cost references and vertical factors have been exported to the private `references/margin_workbook.json` file so no additional Python package or Excel installation is required to run the app. This is a dated reference snapshot, not live FX or a claim of approved company policy. Keep the references folder outside public; raw employee CTC and reference hourly costs are not sent to the browser.

**Install:** stop both servers, back up the project/database, and copy the updated bundle contents into `PriceTrack_Backend_Starter`. Include the new `margin_calculator.py`, `references/margin_workbook.json` and `public/workbook-calculator.js`, as well as the updated index.html, app.js, server.py and run_frontend.py. Keep your existing data folder. Restart `py server.py` and `py run_frontend.py` in separate terminals and use Ctrl+F5 at http://localhost:5500.

**Use:** open a source-linked case under Created from opportunities, then choose Open workbook calculator. Select a vertical and add onshore/offshore lines. Choose an exact workbook role/experience, enter people, months and billability percent. Hours/month and target CM per stream start from the workbook defaults. Add IP/license cost lines and IP deal revenue if applicable. Click Calculate & save draft. Reloading the app retains its inputs/results in SQLite.

Optional saved-resource labels link the calculation lines to your saved plan. These labels do not convert monthly planned hours to headcount/months or auto-apply billability. Calculator quantities are explicitly entered using the workbook's inputs, so the calculation does not accidentally multiply both entered monthly hours and workbook capacity. Manual standalone workbook lines are also supported. The saved plan revision is captured; later resource edits mark the prior calculation stale. Recalculate deliberately after reviewing the new plan.

### Calculation behavior

- Each resource cost follows `people × months × stream hours/month × billability × source hourly cost`.
- Stream revenue follows `resource cost / (1 - stream target CM)`.
- Bench loading is added to labour cost, not revenue, exactly as Margin_Summary!C8. Default 5%; the workbook label allows 5–10%.
- IP cost follows `unit cost × quantity`, summed separately; IP deal revenue is an explicit input.
- Overall contribution margin follows `(total revenue - total cost) / total revenue` including bench and IP effects. Projected GM uses the workbook's normalized vertical factors, independently for each stream and overall.
- Zero revenue produces unavailable CM/GM rather than a division error. Missing roles or required values block calculation instead of creating zero-cost resources. Explicit zero quantities remain valid.
- Source row overrides are retained. Some offshore cells divide by a fixed 93 and others use cached FX 95.66 through B1; they are not silently standardized. Source values are cached workbook values, not a live exchange-rate lookup.
- The PM check uses the workbook's summed headcount and Manager/Scrum role-name check. It is not a newly inferred FTE rule.
- Two target-CM revenue simulations use unchanged total cost. Their GM outputs remain unavailable: source Margin_Summary!F18:F19 refer to empty Vertical-Based GM Calculation!A15:C21. No substitute formula is invented.
- The local Pricing Operations view shows revenue, CM and projected GM. Raw reference cost rates, salaries/CTC and confidential total-cost detail are omitted. Authentication and permission enforcement must be implemented before shared deployment.

The new `pricing_workbook_calculations` table stores the calculation draft, its resource revision, reference SHA256, inputs, outputs and timestamp. Saving identical inputs against the same resource/reference revision does not create a new calculation revision. A conflicting save returns HTTP 409. Calculation saves create no formal pricing version, review task, approval, agreement, or Salesforce update.

GET `/api/workbook-reference` returns role labels, verticals and provenance without hourly costs. GET/PUT `/api/pricing-cases/{case_id}/workbook-calculation` load/calculate/save the case's calculator draft. The source reference JSON is private server data; the frontend server serves public only.

### Workbook parity example

Choose RCM; add Data Engineer / Data Modeler 1 | 2-3 Years in each stream. Set people=1 and months=1 for both, onshore billability=50%, offshore billability=100%, both hours/month=160, both target CM=50%, bench=5%, no IP cost and IP revenue=0. The saved reference example produces total revenue approximately **USD 9,103.50**, CM **47.50%**, projected GM **37.25%**. This was checked against the original workbook's cached summary and stream outputs; it is not a company-approved quote.

## Second MVP feature: persistent resource estimates

1. Stop both running servers using Ctrl+C.
2. Back up your current project files and SQLite database. Copy the updated package files into the same project root. Keep the existing data folder and seed workbooks in place.
3. Keep `resource_plan.py` beside `server.py` and `resource-plan.js` inside public. They are required new files.
4. Restart `py server.py` and `py run_frontend.py` in separate terminals, then open http://localhost:5500 and press Ctrl+F5.
5. Open Pricing Cases and select a case in **Created from opportunities · Saved in SQLite**, or open it through Salesforce Opportunities → Open pricing case.
6. Choose **Edit resource estimates** or the Resource Ask / Estimate tab. Choose the start month and month count, then click Apply months.
7. Add a resource, enter its dimensions and monthly hours, then click **Save resource draft**. Refresh to confirm that the saved rows reopen.

Startup adds `pricing_resource_plans` and `pricing_resource_rows` tables without replacing existing source tables. Resource saves change the case status from Requested to Draft. Saving an unchanged plan does not increment its revision; changing inputs increments only the resource draft revision, not a formal pricing version. Each case has an independent plan.

GET `/api/pricing-cases/{case_id}/resources` returns the saved draft. PUT to the same route accepts `{expected_revision, months, resources}`. A stale revision returns HTTP 409, preserving the database draft and the user's unsaved edits. Reload saved requires explicit confirmation before discarding unsaved edits. The editor supports 1–24 explicit planning months and up to 100 resource rows. Blank hours are stored as null, distinct from numeric zero. Missing dimensions can be saved as incomplete drafts; no Tech COE or BU approval is implied.

This release also fixes the missing closing quote on the Request pricing confirmation button's opportunity-ID attribute. That defect could send the wrong ID even though direct PowerShell requests worked.

No rate or cost calculation, automatic FTE conversion, source workbook edit, formal submission, or approval is performed by this feature. Authentication and account scope are still required before use beyond the local synthetic demo.

## What is a browser prototype

The six fictional pricing cases in the brief are shared across Overview, Cases, case details, workflow, reports, renewals, exceptions, notifications and approvals. They are **not** silently matched to the 532 Salesforce rows. Pricing-case linkage needs a future backend data model and endpoint.

Source-linked cases and their resource drafts persist in SQLite and can be reopened after refresh. The six fictional DEMO-PC cases continue to use the older browser-only resource editor. Negotiation and later pricing workflows remain illustrative.

Working interactions include:

- Page navigation, case tabs, notifications and the optional eight-step guided flow.
- Case search, path / stage / owner filters, My cases, Team and table / card views.
- Database opportunity search, stage filtering, pagination and read-only detail drawers.
- Rate-card search, currency filtering and provenance drawers.
- Rate comparison by exact dimensions, currency, unit and effective date. Missing or ambiguous references are labeled not comparable. This is not a Finance-approved rate-resolution engine.
- Source-linked case resource editor: saved planning months, resource dimensions, monthly hours, row removal and SQLite draft revisions.
- Demo-case resource-hour edits, optional details, blank-input handling and CSV export remain browser-only.
- Explicit browser Save Draft; edits invalidate the current financial fixture and review readiness. Saving increments a draft revision only when inputs changed and does not create V2.
- Browser negotiation notes, notification read state and reset through the demo profile.
- Global fixture-case search, help, modal focus management and keyboard Escape.

Browser drafts, notes and notification state are stored in `localStorage` under `pricetrack-ui-v1`, keyed by case. They are not stored in SQLite, shared across users, or backed by authentication. Use the demo profile's reset action to clear them.

The Northstar resource fixture starts with 360 + 160 = 520 planned hours. A blank input is missing data; explicit zero is 0. No utilization, FTE, available-hours or employee-cost conversion is inferred.

Northstar's 48,000 USD / 40% approved V1 and 45,600 USD / 36.8% candidate are illustrative values from the brief. They are not computed from hours or the seeded rate cards. Changing financial inputs makes the current financial preview unavailable; the historical fixture remains distinguishable. No hidden cost is reverse-calculated.

Approval actions, formal submission, rate publication, HR request sending, handoff retry and agreement closure are unavailable until the necessary authenticated backend features exist. Disabled buttons explain the dependency; readiness and detail views are still navigable. Finance and administration screens are view previews, not real role changes or authorization grants. Technical administration does not give Finance authority.

The Margin Calculator source workbook is unchanged. A private cached reference export supports its explicit-input strategy. No COLA percentage, universal project-month conversion, or approval threshold is added.

## Screen map

URLs use the hash after the frontend address, e.g. `http://localhost:5500/#/cases`.

| Brief ID | View | Route after `#/` |
| --- | --- | --- |
| 01 | Overview | `overview` |
| 02 | Pricing Cases | `cases` |
| 03 | Case Summary | `cases/DEMO-PC-1042/summary` |
| 04 | Resource Estimates | `cases/DEMO-PC-1042/estimates` |
| 05 | Rates & Costs | `cases/DEMO-PC-1042/rates` |
| 06 | Renewals | `renewals` |
| 07 | Pricing Calculator | `cases/DEMO-PC-1042/calculator` |
| 08 | Pricing Versions | `cases/DEMO-PC-1042/versions` |
| 09 | Negotiation | `cases/DEMO-PC-1042/negotiation` |
| 10 | Approval Inbox | `approvals` |
| 11 | My Work / Workflow | `work` |
| 12 | Exceptions / Health | `exceptions` / `exceptions/health` |
| 13 | Client Rate Cards | `rates/client` |
| 14 | Reports & Insights | `reports/portfolio` |
| 15 | Administration Overview | `admin/overview` |
| 16 | Activity & Audit | `cases/DEMO-PC-1042/activity` |
| 17 | Resource Monthly Planning | `cases/DEMO-PC-1042/planning` |
| 18 | Version Comparison | `cases/DEMO-PC-1042/compare` |
| 19 | Case Approvals | `cases/DEMO-PC-1044/approvals` |
| 20 | Integrations / Source Data | `cases/DEMO-PC-1047/integrations` |
| 21 | Notifications | `notifications` |
| 22 | Salesforce Opportunities | `opportunities` |
| 23 | Standard Rate Cards | `rates/standard` |
| 24 | Client vs Standard | `rates/compare` |
| 25 | Rate Import History | `rates/imports` |
| 26 | Finance Policies | `admin/policies` |
| 27 | Approval Routes | `admin/routes` |
| 28 | Routing & Access | `admin/routing` |
| 29–36 | Eight guided steps | `cases/DEMO-PC-1042/wizard?step=1` through `step=8` |

Some screens use honest unavailable / read-only states where the brief describes future backend features. They are not complete operational implementations of those future features.

The connected journey is: case list → summary → estimates / monthly planning → rates → calculator → submission readiness → version review → exact-version approvals → agreement / source reconciliation. Blocked actions do not pretend to advance a business workflow. Navigation links let you preview later screens without marking steps complete.

## Troubleshooting

- **Demo pages work but reference pages fail:** confirm `http://localhost:3000/api/health` still returns your database record counts, then click Refresh. Keep both terminals running.
- **404 for an API route:** compare the endpoint table above with your Python routes. A successful health endpoint alone does not guarantee every collection route is implemented.
- **Files not found:** `public` must be beside `run_frontend.py`, and app.js and styles.css must be directly inside public.
- **Cannot GET /** on port 3000:** open the frontend at port 5500. Your existing backend need not serve `/`.
- **Old CSS / JS:** use Ctrl+F5. The launcher sends no-store headers.
- **Unexpected local draft:** open the demo profile and reset browser demo data.
- **Copy / paste editing:** there are no external JS or CSS dependencies. Keep the filenames / asset path as supplied.

## Validation performed

JavaScript syntax and Python compilation passed. The first MVP API was checked against a temporary SQLite database for create, duplicate reuse, unknown opportunities, invalid JSON and persistence. The second feature was checked over actual HTTP GET/PUT through the frontend proxy, including persisted hours, a 520-hour fixture, blank/zero distinctions, invalid input rejection, no-op saves, stale revision conflicts, row removal, case isolation and status changes. The confirmation button attribute and resource-editor markup were also checked. The third feature matched source cached cost, revenue, CM and GM outputs; all 160 cached rate pairs were reconciled. GET/PUT through the frontend proxy, calculation persistence, resource-stale detection, conflict checks, IP aggregation, validation, no-op saves and confidential-rate omission passed. Source SHA256 was unchanged. The frontend request flow, saved-case list/detail, existing read-only pages, and proxy GET/POST behavior were checked with representative API data. No source workbook rows were modified.

Full Chromium layout testing was blocked by the execution environment. The actual Python backend on your Windows computer was not accessible for integration testing here. After copying the included server file and restarting both processes, create one case from a synthetic opportunity and verify the case remains after a refresh.

## Further integration work

The host team must confirm its frontend framework, component library, authentication, database and permissions before final integration. The CSS tokens are at the start of styles.css, and screen render functions are grouped in app.js for later migration. Replace the prototype shell with the host shell, browser drafts with authenticated persistence, and fixture workflows with server-owned case/version/task data. Never rely on hiding controls as an authorization mechanism.


Pricing version history: copy pricing_versions.py and public/pricing-versions.js along with the updated server, proxy, index and app files. Restart both servers. Open a saved case > Pricing Versions. Calculate first, then explicitly save a numbered immutable draft snapshot. Duplicate saves reuse the same calculation version. Stale calculations are blocked. Versions are not approval submissions.


## Local demo version approvals (latest feature)

This section supersedes earlier statements that all approval controls are unavailable. Source-linked cases now have a local demonstration of the imported illustrative route, BU Head > Finance. Production approval policy and authenticated identity remain pending.

Install: stop both servers, back up your project, copy this ZIP's contents into PriceTrack_Backend_Starter, replacing code files. Include pricing_approvals.py, pricing_versions.py, margin_calculator.py, resource_plan.py, server.py, run_frontend.py, references/ and public/. Keep the existing data/ folder and pricetrack.sqlite. The ZIP does not include a replacement database. Restart both servers and refresh the browser with Ctrl+F5. New tables are created automatically on startup; no seed reimport is needed.

Use a source-linked saved case, not one of the six static design fixture cases:
1. Calculate and save the workbook draft.
2. Open Pricing Versions and save a version.
3. Open the case Approvals tab. Select Maya Demo (Pricing Analyst) and click Request demo review of Vn.
4. Select Evan Demo (BU Head), enter a decision reason, and approve the step, request changes, or reject.
5. After BU approval, select Priya Demo (Finance), enter a decision reason, and record the next decision.
6. Review the case Activity & Audit tab or the global Approval Inbox for persisted review records.

Actor selection is an explicit simulation, not login or authorization. The endpoint accepts the selected synthetic actor ID and validates enabled status and the expected role. An authenticated actor, account scope, confirmed approval thresholds/assignment rules, and protected audit storage must replace this mechanism before company use. The UI labels all outcomes as demo; the case's overall status is not marked approved or closed. No email, Teams message, Salesforce writeback or external notification is sent.

The exact seed route must be present with its original Illustrative demo only status. Missing or changed configuration blocks actions instead of inventing policy. Only the current, latest calculated snapshot may be submitted. A review progresses sequentially and requires comments for all decisions. A newer saved version supersedes a pending review; approved historical versions remain historical. A draft change never copies an approval onto the draft or another saved version. Changes requested or rejected reviews are closed; edit, recalculate and save a new version to request review again. A completed or duplicate action cannot silently create another event. Conflicting review writes return HTTP 409.

New tables: pricing_demo_reviews and pricing_demo_review_events. GET/PUT /api/pricing-cases/{case_id}/approvals load or act on a review. PUT body: expected_revision, version_number, actor_id, action (submit/approve/reject/request_changes), comment. GET /api/approval-inbox lists saved requests across cases. Activity lists only these review events; it is not a complete audit of all application edits.

Validation: HTTP tests through the frontend proxy cover role sequencing, invalid actor, mandatory reasons, conflicting updates, closed review protection, changes/rejection, new-version separation, superseded reviews, route gating, persistence, inbox, and unchanged snapshots. Workbook parity and saved-version checks pass in the same suite. Browser visual validation and the user's Windows database were not available in this environment.


## Saved negotiation log (latest feature)

Source-linked cases now have a persisted Negotiation tab. This supersedes earlier browser-only negotiation guidance for those cases. The six static DEMO-PC fixture cases continue to use browser prototype notes.

Install the full updated code package into PriceTrack_Backend_Starter after stopping both servers and backing up your project. Include new pricing_negotiation.py and public/pricing-negotiation.js along with the updated server.py, run_frontend.py, public/index.html and public/app.js. Keep your existing data/ folder and pricetrack.sqlite. Restart both servers and press Ctrl+F5; the new table is created automatically and no seed reimport is needed.

Open a saved source-linked case, calculate pricing and save a numbered version if needed, then select Negotiation. Choose the saved version, demo recorder and discussion type. Enter an optional discussed total USD amount for Client Ask or Company Offer, and a required note. Save negotiation entry writes to SQLite and adds a timestamped history entry. Filter the history by version. Reload saved history keeps an unsaved note. Unsaved form drafts remain in memory while navigating within the current tab session; closing/reloading the browser discards them after a browser warning.

Types: Client Ask, Company Offer, Internal Note, Clarification, Approval Feedback. Amounts are optional, nonnegative USD totals with at most two decimal places. Zero is distinct from a missing amount. These amounts describe the discussion and never overwrite calculator results, recalculate margins, create a pricing version, grant approval, record final agreement, or update Salesforce. To revise pricing, edit the calculator, recalculate and save a new version for review. Historical versions may have additional discussion notes; the UI identifies historical selections.

The recorder selector contains the enabled synthetic Pricing Analyst and imported Client Partner matching the case opportunity owner. It is an explicit local simulation, not authenticated identity or production access control. No external notification or client message is sent. Company sign-in, scope enforcement and a confirmed negotiation/final-agreement policy remain future integration work.

Table: pricing_negotiation_events. Entries are append-only through the supported API; there is no edit/delete action. Corrections can be recorded as another note. The history is local application data, not a tamper-proof compliance archive. GET/PUT /api/pricing-cases/{case_id}/negotiation load or append. PUT accepts expected_revision, version_number, actor_id, kind, amount_usd (decimal string or null), currency ('USD'), and note (1-4000 characters). Conflicting saves return HTTP 409. Reload saved history, inspect existing entries and retry deliberately. There is no automatic replay of a failed write.

Checks passed: HTTP calls through the frontend proxy for saved-version/case linkage, seeded actor eligibility, disabled actors, input validation, decimal/zero/null handling, rollback, conflicting writes and SQLite persistence. Calculator results, version snapshots and approval records remain unchanged after negotiation writes. Existing workbook parity, version and demo approval checks passed in the same suite. UI rendering checks cover escaped history, empty state, zero-dollar amounts and clear demo labels. Browser visual testing and the user's Windows database were not available here.


## Saved pricing version comparison (latest feature)

The source-linked case Pricing Versions screen now includes Compare saved versions. Save at least two versions, open that link, choose a baseline and comparison version, and optionally swap them. The screen reads persisted snapshots from the existing GET /api/pricing-cases/{case_id}/versions endpoint. It does not read unsaved browser edits, recalculate the workbook, create a version, or write to the database.

Install the full package as before: stop both servers, back up the project, copy extracted contents into PriceTrack_Backend_Starter and replace matching code files. Keep the existing data/ folder and pricetrack.sqlite. Include public/pricing-comparison.js plus updated public/index.html, public/app.js and public/pricing-versions.js. Restart both servers and refresh with Ctrl+F5. This feature requires no new tables or seed import.

Financial comparison shows total and stream revenue, contribution margin, projected GM, workbook headcount and simulation revenue. Change means comparison minus baseline; CM/GM changes are percentage points (e.g. 40% to 45% = +5 pp). Missing margins remain unavailable. Deltas are calculated using decimal coefficients and integer arithmetic for presentation, then rounded to two decimals; they are not new pricing-engine outputs. Raw hourly costs and employee CTC are not displayed.

Input changes cover vertical, bench loading, stream target CM, hours/month, simulation targets, IP deal revenue, workbook line role/people/months/billability/resource link, and IP descriptions/quantities. An IP unit-cost change is indicated without displaying its value. Workbook lines are matched by position within their stream, and IP lines by position; insertion can therefore shift later line comparisons. Saved resources are matched by row_id and planning hours by month, preserving blank versus zero. Added/removed lines or resources are identified, with their complete snapshots available in Pricing Versions. The screen warns when the cached workbook reference changed between versions.

This read-only comparison carries no approval status. Review a version's approval in the Approvals tab. Earlier demo approvals remain specific to their saved versions.

Checks passed: exact two-decimal differences beyond binary floating-point precision, percentage-point deltas, unavailable margins, zero/null distinctions, numeric string equivalence, month alignment, reverse comparison, unchanged source snapshots, escaped labels, empty state, and no write requests. JavaScript syntax checks passed for all changed scripts. Browser visual validation was not available here.


## Database overview dashboard (latest feature)

The default Price Track Overview now loads actual local SQLite pricing records. It supersedes the six-case illustrative overview described in earlier sections. Other unfinished screens may still show explicitly labelled design fixtures; they are not counted in this dashboard.

Install the full package into PriceTrack_Backend_Starter after stopping both servers and backing up your project. Include new pricing_dashboard.py and public/pricing-dashboard.js plus updated server.py, run_frontend.py, public/index.html, public/app.js, public/pricing-comparison.js and public/styles.css. Keep the existing data/ folder and pricetrack.sqlite. Restart both servers and press Ctrl+F5. No new table or seed import is required.

Open Overview or click Refresh there. The dashboard shows saved pricing cases, pending demo reviews by current BU Head/Finance step, all saved version snapshots, negotiation entries, cases without versions, outdated calculation drafts, and latest-version demo approvals. Counts use database rows rather than fictional browser fixtures. Pending review counts include only the latest version of each case, so a superseded pending historical version is excluded. A historical approval does not mark a newer version approved.

Latest saved version revenue is a USD estimate total taking at most one saved version per case, across all approval states. It is not a total of all historical versions, Salesforce opportunity budgets, approved revenue, or actual sales. Cases without a usable saved USD result are excluded and the count is shown. With no saved revenue results, the value is Unavailable rather than an invented zero. There is no aggregate margin because a margin aggregation policy has not been confirmed.

The saved case table provides a next-action link and shows the latest snapshot's revenue/CM alongside its review status. Working draft revision/outdated flags are separately identified. Outdated means that the saved calculation references an earlier resource-plan revision or cached workbook snapshot. A changed calculation draft requires saving a new version before requesting its review. Search by account, opportunity, case, owner or opportunity ID; filter by owner, actual case status or version review. Pagination displays ten matching cases per page. Filters apply to the table while dashboard totals remain for all cases. All data is local imported synthetic data, and demo review actors remain unauthenticated.

GET /api/dashboard is read-only. It uses a consistent SQLite read transaction and exposes counts and case summaries, not calculator input JSON, raw hourly costs or employee CTC. The existing /api/overview reference endpoint remains available. Refresh rereads the database; it does not contact Salesforce. This dashboard has no background refresh timer.

Validation passed through the frontend proxy for database counts, latest-only revenue aggregation, pending-step transitions, historical approval separation, superseded review exclusion, outdated calculations, new-draft indicators, unchanged saved snapshots and empty portfolios. Workbook parity, version history, approvals and negotiation checks passed in the same suite. UI rendering checks cover exact decimal revenue display, filters, escaping and an error state without sample fallback. JavaScript/Python syntax checks passed. Browser visual validation and the user's Windows database were not available here.


## Export a saved pricing version (latest feature)

On a source-linked case, open Pricing Versions, expand Vn and choose Download printable summary or Download CSV. These buttons read the selected saved snapshot and the case's stored source context. No calculator, write endpoint or live Salesforce request is used, and unsaved browser inputs and negotiation amounts are not substituted.

Install the full updated package into PriceTrack_Backend_Starter, keeping the existing data/ folder and pricetrack.sqlite. The changed files for this feature are public/index.html, public/pricing-versions.js and the new public/pricing-export.js. Restart both servers and press Ctrl+F5. No new table, dependency or seed import is required.

The printable summary downloads as a self-contained HTML file. Open it in Chrome/Edge and use Ctrl+P > Save as PDF to create a PDF locally. There is no direct server-generated PDF file in this feature. The summary contains case/source identifiers, version timestamp, saved calculation/resource revisions, workbook reference hash, financial and stream results, explicit calculator settings, workbook team quantities/billability, IP descriptions/quantities, simulations, and saved resource dimensions/monthly hours. Empty values are labelled; blank hours remain distinct from zero. Financial display values are rounded to two decimals. Raw hourly reference rates, employee CTC and IP unit costs are omitted. The report has no external assets or scripts.

CSV contains the same curated sections with UTF-8 BOM for spreadsheet opening, quoted cells and escaped quotes/newlines. Cells beginning with spreadsheet formula markers receive a protective apostrophe. File names identify case ID and version. An export is a local synthetic-data review snapshot, not approval evidence, a final quote or client acceptance; every export includes that notice. Current approval status and negotiation history are not certified by it. Company authentication, production export permissions and an approved client-quotation format remain future work.

Checks passed for selected-version reads, no write calls, exact financial display beyond floating-point precision, HTML escaping, null/zero preservation, omission of private raw costs, CSV BOM/quoting/formula protection, export file naming and failure recovery. Syntax checks passed. The download interaction was checked with a DOM stub; browser download behavior and visual PDF print layout were not available for verification here.


## Saved Pricing Cases and Work Queue (latest feature)

Pricing Cases and the renamed Work Queue now use actual saved SQLite cases from GET /api/dashboard. They replace the old mixed fixture/saved case list and static My Work screen. All saved cases returned by this endpoint are searchable; these pages no longer rely on the older 200-row pricing-case list limit. Other unfinished screens may still display their labelled design fixtures.

Install the updated package into PriceTrack_Backend_Starter after stopping both servers and backing up the project. Keep the existing data/ folder and pricetrack.sqlite. This feature adds public/pricing-workspace.js and updates public/index.html and public/app.js. Restart both servers and press Ctrl+F5. No new tables, dependencies or seed import are needed.

Use Pricing Cases to find saved requests, or Work Queue for suggested next steps based on saved draft/version/review state. Search account, opportunity, opportunity ID, case ID or owner. Filter owner, case status, latest-version review and suggested next action. Table and Cards display ten matches per page. Filters reset pagination to a valid page. Clear filters restores defaults; UI choices persist during navigation in the current tab session. Global search now routes into this saved-case list. The old static approval navigation badge has been removed.

Pricing Cases includes closed records by default. Work Queue initially excludes them; Include closed cases changes visibility. Selecting Closed status automatically enables that checkbox. Queue figures cover all open saved cases; list filters do not change these global figures. There is no newly invented due date, priority policy, closure rule or assignment process. Next steps are navigation suggestions, not formal assigned tasks. Owner filters are local demo navigation, not login, account scope or user authorization.

The list distinguishes latest saved version/review from a newer or outdated working calculation. Links open the actual saved case, calculator, version list, approvals or negotiation tab. It never substitutes a fictional case when an API request fails. The legacy sample overview/case/work render functions were removed; direct design-fixture detail routes remain only for unfinished preview screens. No database write is performed by either list.

Checks passed for saved-only rows, exact case/next-action routes, search and all filters, global-search URL input, closed visibility, pagination and reset, table/cards toggle, clear filters, escaping, API failure state and no write requests. Changed script syntax passed. Interactions were checked with a DOM stub; browser visual validation was not available here.


## Combined case activity timeline (latest feature)

The Activity & Audit tab of a saved source-linked case now combines case creation, resource-plan saves, workbook calculations, saved versions, demo review actions and negotiation entries. It replaces the review-only activity view. Filter by event type or an explicitly linked version, choose newest/oldest first, page through twenty events at a time and reload. Resource/calculation draft events have no saved-version label. Links open the relevant case tab.

Install the full updated package after stopping both servers and backing up the project. Copy all code files into PriceTrack_Backend_Starter, including new pricing_activity.py and public/pricing-activity.js and the updated server.py, resource_plan.py, margin_calculator.py, pricing_versions.py, pricing_approvals.py, pricing_negotiation.py, run_frontend.py, public/index.html and public/app.js. Keep the existing data/ folder and pricetrack.sqlite. Restart both servers and press Ctrl+F5. A new pricing_activity_events table is created automatically; do not reimport the seed.

Future changed saves record an event inside the same SQLite transaction as their data mutation. Failure to record the event rolls back that save. Identical resource/calculation/version saves and rejected requests do not add duplicate events. Events include a timestamp, category, revision or version reference, description and the available demo recorder identity. Resource/calculation/case/version saves have no authenticated actor and are labelled accordingly. Demo review and negotiation actor selections remain explicitly unauthenticated.

Older case/version/review/negotiation records are projected into the timeline and labelled Existing record. Only retained resource/calculation states and calculation snapshots preserved in versions can be recovered. Earlier overwritten draft edits are not invented. A retained old draft is captured with its original stored timestamp before a later save replaces it, labelled Retained state before save. Viewing the timeline itself does not modify the database. Deduplication keys avoid showing a record twice when it also has a new activity event.

GET /api/pricing-cases/{case_id}/activity is read-only. There is no UI/API action to edit or delete activity. This is local application history, not a tamper-proof compliance archive. Raw reference rates, employee CTC and calculator input JSON are not automatically copied into events; discussion/review notes remain user-entered text. Company authentication and protected audit infrastructure remain integration work.

Validation passed through the frontend proxy for all event categories, case isolation, unique event keys, exact-version references, exclusion of no-op saves, resource/event atomic rollback, read-only legacy projection and retention of old draft state before replacement. Existing workbook parity, version, approval, negotiation, dashboard and resource tests passed. UI checks cover labels, filters, ordering, links, escaped notes and unavailable API state. Changed Python/JS syntax checks passed. Browser visual validation was not available here.


## Live case summary and demo readiness (latest feature)

A saved source-linked case now opens a live Summary with the saved calculation, latest version, exact-version demo review, resource-plan counts and the next suggested step. Draft and version financial results are displayed separately. Outdated calculations are labelled rather than silently refreshed. The tab also includes the source opportunity snapshot and links to estimates, calculator, versions/comparison, approvals, negotiation and activity.

Install the full updated ZIP into PriceTrack_Backend_Starter after stopping both servers and backing up the project. Include pricing_readiness.py and public/pricing-summary.js, updated server.py, run_frontend.py, public/index.html, public/app.js and public/styles.css. Keep the existing data/ folder and pricetrack.sqlite. Restart both servers and press Ctrl+F5. No new table, dependency or seed import is required.

GET /api/pricing-cases/{case_id}/readiness reads a consistent SQLite transaction and reports saved technical prerequisites for a new local demo review request: a saved/current calculation, a matching latest saved version, the original illustrative approval route, an enabled synthetic requester, and no previous review of that version. These checks do not approve a version or change submission enforcement. The resource plan remains optional because standalone workbook lines are explicitly supported. The workbook PM warning is advisory. Missing demo reviewers are reported as warnings, because the existing request endpoint allows submission before those actors become available. All results refer to saved backend inputs; unsaved browser edits are excluded.

Company policy, authenticated identity/permissions, final client agreement and production integration are not certified by readiness. production_approval_ready remains false. Review results remain local demo outcomes and apply only to their saved version. No Salesforce data is fetched or updated when the summary reloads.

After this feature, the proposed internal MVP has six remaining workstreams: (1) authentication and server-enforced permissions/scopes; (2) company-confirmed approval policy and reviewer assignment; (3) agreement/acceptance and Project Tracker handoff; (4) host integration and agreed source data refresh; (5) complete or explicitly remove remaining unfinished screens from MVP scope; (6) end-to-end/UAT, deployment and operational checks. This is a planning breakdown, not a precise count of small code features. Integration, identity and production policy depend on the host project's team. The current package is still a local synthetic-data demonstration.

Checks passed through the frontend proxy for stale calculations, latest-version matching, ready/not-ready states, existing review/change requests, missing route/actors, optional resource plans, read-only behavior and no production approval claim. Existing activity, dashboard, negotiation, approvals, versions and workbook parity tests passed in the same suite. UI checks cover separate draft/version amounts, formatting, unavailable GM, status/links, escaping and API failure state. Python/JS syntax checks passed. Browser visual validation and the user's local Windows database were not available here.


## Sign-in and backend role/access permissions (latest feature)

See AUTH_SETUP.md for commands and the role matrix. All business APIs now require an enabled account with a configured password and a valid session. The basic health endpoint remains public but returns no record counts or database path. The frontend proxy forwards session cookies and request security headers; calling port 3000 directly does not bypass access checks.

Role actions are enforced on the backend independently of the UI. A user's existing user_opportunity_scope rows and explicit auth_opportunity_grants determine opportunity/case visibility; auth_opportunity_denials override both. Internal users receive no implicit global opportunity access. Counts, source search/stages, saved case lists, latest-version dashboard totals, client selling-rate references and approval inbox entries are scoped. Client selling-rate references use accessible accounts. Standard selling-rate and mapping/workflow references require a signed-in read-capable role. Admin can read the account directory but cannot read cases, edit pricing or grant approvals through the API.

Passwords use PBKDF2-HMAC-SHA256 with 600,000 iterations and unique random salts. Random session secrets are stored only as hashes; the browser receives an HttpOnly, SameSite=Strict cookie scoped to /api. Sessions expire after eight hours. State-changing requests require the session's CSRF nonce and allowed local origins. Login attempts are throttled. Disabling an account, resetting its password or signing out revokes sessions; role and scope changes are checked again on each request. No password/token is stored in browser localStorage and no shared initial credentials are included.

Approval and negotiation writes derive the actor from the signed-in session. A conflicting submitted actor_id is rejected; changing browser controls cannot impersonate another reviewer. Review actor selectors have been removed. The existing review sequence remains illustrative BU Head then Finance, with company policy still pending. Future activity events identify the signed-in local account; old demo history is not retroactively authenticated. No raw employee CTC or hourly reference cost endpoint is exposed; cost_access does not grant a new private workbook-download route. Case-granted users can read the case's saved calculation inputs, including user-entered business/IP inputs; company rules for additional field-level restrictions remain to be confirmed.

The sign-in page gates app startup, profile shows the actual user, read-only roles have editing controls disabled, and the backend remains authoritative. Signing out or changing accounts reloads the page to clear in-memory case caches. Unfinished design-fixture areas are removed from the signed-in navigation, and archived DEMO-PC detail routes do not display fictional cases as live records. Enterprise SSO and host identity integration are separate remaining work; this server continues to bind only to localhost.

New tables: auth_credentials, auth_sessions, auth_throttle, auth_opportunity_grants and auth_opportunity_denials. Initialization is automatic. No seed workbook or Margin Calculator workbook is changed, and no seed reimport is required. Local operator manage_users.py manages credentials and access in the existing database; it never prints passwords. Permission defaults are the explicit local MVP policy in pricing_auth.py, not confirmed company policy.

Validation: run `py tests/test_auth.py` from the backend project root for a standard-library HTTP smoke test against a temporary database. It checks login/cookies/CSRF, roles, source/case/dashboard/client-rate/inbox scopes, direct-backend/encoded URL access, actor spoofing, signed-in review and negotiation, revocation/expiry/logout/password reset/disable, rate limiting and trusted CLI grants/denials. Scripted JS tests checked auth gate/CSRF behavior. Original workbook cached-result parity passed separately. Chromium could not launch due to the environment's socket restrictions; full browser sign-in/role-switching needs local verification. The user's Windows database was not accessed during development tests.
