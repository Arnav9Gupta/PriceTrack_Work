## Set up all imported accounts at once

Run `py setup_all_passwords.py` from the backend folder. This creates a unique random password for every enabled supported user that does not already have credentials. Open the generated LOCAL_LOGIN_PASSWORDS CSV for user IDs and passwords. Existing passwords and opportunity scopes are retained. Disabled accounts remain disabled. Keep this local file private; do not upload or commit it. Re-running does not reset existing passwords. Use manage_users.py set-password to reset an existing account.

# Price Track: local sign-in setup

Stop both servers and back up your project. Copy **all contents** of this ZIP into `PriceTrack_Backend_Starter`, replacing matching code files. Keep the existing `data` folder and `pricetrack.sqlite`. No seed import is needed.

## 1. Set up your first account

Open a VS Code PowerShell terminal:

```powershell
cd "D:\PriceTrack_Work\PriceTrack_Backend_Starter"
py manage_users.py list
py manage_users.py set-password --user-id DEMO-Pricing-Analyst
```

Enter your own password twice when prompted. It must contain 12–128 characters. Password characters are hidden while typing. There are no default passwords. Credentials and sessions live in the local SQLite database, which should stay outside source control.

For a local demonstration in which the Pricing Analyst can work on **all currently imported opportunities**, explicitly grant that access:

```powershell
py manage_users.py grant-all --user-id DEMO-Pricing-Analyst
```

For narrower access, use a specific imported opportunity ID instead:

```powershell
py manage_users.py grant-opportunity --user-id DEMO-Pricing-Analyst --opportunity-id 006S300000HFTHe
```

Only run grants appropriate for your intended local test. Internal users initially have no automatic case access. Client Partners retain their existing seeded opportunity scopes.

## 2. Run both servers

Terminal 1:

```powershell
cd "D:\PriceTrack_Work\PriceTrack_Backend_Starter"
py server.py
```

Terminal 2:

```powershell
cd "D:\PriceTrack_Work\PriceTrack_Backend_Starter"
py run_frontend.py
```

Open `http://localhost:5500`, press Ctrl+F5, and sign in with user ID `DEMO-Pricing-Analyst` and the password you just set. The backend health endpoint only confirms connectivity; the application is on port 5500.

Seeing no opportunities/cases means this account has no relevant opportunity scope or grant. Signing in does not automatically grant access.

## 3. Configure reviewers

Set a separate password for each reviewer and grant access to the opportunity being reviewed:

```powershell
py manage_users.py set-password --user-id DEMO-BU-Head
py manage_users.py grant-opportunity --user-id DEMO-BU-Head --opportunity-id 006S300000HFTHe
py manage_users.py set-password --user-id DEMO-Finance
py manage_users.py grant-opportunity --user-id DEMO-Finance --opportunity-id 006S300000HFTHe
```

Replace that opportunity ID when reviewing another case. For a broad local demonstration, `grant-all --user-id USER_ID` explicitly grants all currently imported opportunities to that user. Future opportunities need new grants or authoritative seeded scopes.

Submit the saved version as Pricing Analyst. Click your profile → Sign out, then sign in as BU Head to review. Sign out and sign in as Finance for the next step. Decisions use the signed-in identity. There is no actor switcher.

## Local MVP permissions

Every case action also requires access to its opportunity. These defaults must be confirmed with the host team before enterprise use.

| Role | Allowed actions on accessible cases |
|---|---|
| Client Partner | Read, request pricing, record negotiation |
| Pricing Analyst | Read, request pricing, edit resources, calculate, save versions, request review, record negotiation |
| Tech COE | Read and edit resource plans |
| BU Head | Read and decide the BU Head review step |
| Finance | Read and decide the Finance review step |
| HR/MNH | Read only |
| Admin | Account directory only; no business case or approval authority |

The existing approval route remains an illustrative local policy. Password sign-in does not turn its outcomes into confirmed company approval. Scope grants are independent of workflow assignment; grant each reviewer the relevant opportunity explicitly.

## Revoke or restore access

```powershell
py manage_users.py revoke-opportunity --user-id DEMO-Finance --opportunity-id 006S300000HFTHe
py manage_users.py grant-opportunity --user-id DEMO-Finance --opportunity-id 006S300000HFTHe
py manage_users.py revoke-all --user-id DEMO-Finance
py manage_users.py disable --user-id DEMO-Finance
py manage_users.py enable --user-id DEMO-Finance
```

Revocation creates an explicit denial overriding both manual grants and existing seeded scopes, without deleting seed rows. `revoke-all` covers currently imported opportunities; disable the account to block sign-in entirely. `grant-all` clears that user's explicit denials and grants currently imported opportunities. Role permissions still apply: granting opportunities to an Admin does not give business access.

Password reset uses the same `set-password` command and revokes existing sessions. Enabling an account does not restore previously revoked grants. Disabling/enabling account status revokes sessions. These commands require trusted access to the backend filesystem/database; there is no public registration or account-management API.

## Verification

Run from the project root:

```powershell
py tests/test_auth.py
```

This creates synthetic users and records in a temporary database and exercises both HTTP servers on temporary ports. It does not change your app database. No extra Python packages are required.

Locally verify sign-in, profile identity, logout, role switching, read-only controls and access to another user's case. Chromium could not launch in the development environment, so visual/browser interaction verification remains necessary.

## Integration notes

This is local account authentication using Python's standard library. Company SSO, production approval policy, TLS hosting and Project Tracker identity integration remain separate work. No default enterprise rules are assumed.

The application binds to localhost. Cookies are HttpOnly/SameSite=Strict; session lifetime is eight hours. Standard local HTTP works with the default cookie settings. A future HTTPS deployment should set `PRICE_TRACK_SECURE_COOKIE=1` and replace the development serving/proxy setup appropriately.

Default allowed write origins are localhost/127.0.0.1 on ports 5500 and 3000. If using another frontend port, set `PRICE_TRACK_ALLOWED_ORIGINS` to the exact trusted origin(s), comma separated, in the backend terminal before starting `server.py`. Do not add untrusted origins.

An internal API script now needs a login session cookie and the returned `csrf_token` in `X-CSRF-Token` for writes. Login additionally requires `X-PriceTrack-Request: 1` and JSON content. Never paste a session cookie, password or CSRF token into a public repository.
