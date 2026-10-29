# TaxiAiBooks accountant workspace

Separate React + TypeScript + Vite application using headless Refine, Ant Design and TanStack Table. Implements the requested **screens 1–4**: password/TOTP login and recovery, scoped dashboard, handoff queue with bulk assignment, driver directory and Driver 360 with all requested tabs. Screens 5–7 intentionally stop at this delivery boundary.

## Run locally

Requires Node **22.12+**, the existing Python environment, PostgreSQL and backend configuration. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts/provision_staff.py --email you@yourpractice.co.uk --name "Your Name" --role admin
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Run migrations against the intended database after reviewing migration `0006`. Provisioning asks for the password privately and shows a one-time authenticator enrollment URI. Use the same CLI with `--role accountant --team "Your team"` or `--role senior_accountant --team "Your team"`. Staff identities must be new; existing driver identities are never implicitly promoted. There are no default credentials or demo records. An existing `IDENTIFIER_ENCRYPTION_KEYS` ring is required for enrollment and identifier access. Back up this key ring securely.

In a second terminal:

```powershell
cd accountant-panel
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open **http://127.0.0.1:5173**. Sign in with the provisioned staff email, password and authenticator code. A driver’s existing consented accountant request appears in the handoff queue; an admin can assign it to an accountant. Empty databases show empty states.

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `/api/v1` | Public API base. Same-origin deployment is recommended; HTTPS required for an absolute URL. Never place secrets in Vite variables. |
| `API_PROXY_TARGET` | `http://127.0.0.1:8000` | Local Vite dev/preview proxy destination; not exposed to browser code. |
| Backend `IDENTIFIER_ENCRYPTION_KEYS` | Existing backend setting | Encrypts staff TOTP seeds and driver tax identifiers. |
| Backend SMTP/reset settings | Existing backend settings | Real password recovery delivery. An unconfigured service reports unavailable. |
| Backend `CLAMAV_HOST` / `CLAMAV_PORT` | Existing backend settings | Private document scanning by `python -m app.worker`. Uploaded evidence stays quarantined until clean. |

Recovery uses the existing FastAPI forgot/reset-password contracts. Paste the token from the recovery email into **I have a token**; do not navigate with the token in a URL. Staff sessions last the backend access-token lifetime (15 minutes by default), with a 15-minute inactivity limit enforced in the UI and API. Expiry, logout and a full page reload require sign-in again. Credentials and revealed identifiers are held only in memory. Light mode is the default. The appearance menu offers Light, Dark and System; only this preference is stored locally, separately for each staff ID and for the signed-out screen. System mode follows live device changes.

## Production / Docker

```powershell
npm run build
# Or from the repository root:
docker compose --profile panel build accountant-panel
docker compose --profile panel up -d
```

The optional panel container serves **http://127.0.0.1:8080** and proxies `/api/` to the `api` service, keeping browser requests on one origin. Use a TLS reverse proxy for actual hosting. `nginx.conf` supplies no-store, CSP, no-referrer and framing restrictions; access logs are disabled. The API/image and panel image are separate. Do not serve `dist` with a public caching policy or persist the query cache. The supplied CSP permits inline styles because Ant Design generates them; scripts remain restricted to the same origin.

## Code map

```text
src/api/          Typed DTOs, fetch client, Refine data/auth providers
src/auth/         In-memory session, permissions, workspace/idle handling
src/components/   DataTable, StatusBadge, ReceiptViewer, AuditTimeline, RoleGuard
src/pages/        Login, Dashboard, Handoffs, Drivers, DriverProfile
src/lib/          GBP/date formatting only; no tax arithmetic
e2e/              Live browser checks against disposable PostgreSQL
../app/api/staff.py       Staff API over the canonical backend
../scripts/provision_staff.py  Explicit operator enrollment
```

Every table sends pagination, allowlisted sort and search/filter state to the API, supports private server-side saved views and exports the entire filtered CSV (up to 10,000 records; narrow larger exports). UTR searches cannot be saved. Support cannot export financial records. CSV formulas are escaped. Global name/email/UTR search uses POST bodies. URLs contain only opaque resource IDs. Refine telemetry is disabled. There is no service worker or persistent financial/session cache. Local storage contains only explicitly chosen appearance preferences.

Receipt review supports a private image/PDF viewer, editable extracted fields, category/business-share review, confirmation and exact reversal before corrections. Shortcuts **A**, **R**, **N** operate only outside text fields; reasons and required values still validate. Save extracted-field edits before confirming. Server eligibility remains authoritative. AI suggestions/confidence are displayed only when OCR supplied them; OCR warnings are shown without inventing an explanation. Unknown-date evidence is explicitly visible in the receipt queue.

Human messages are stored in a separate accountant thread; notes/tickets are internal. Flutter chat screens and push/email delivery remain separate integrations. Activity combines staff events and existing canonical mutation history. Legacy events explicitly disclose that the original backend did not record an individual actor. Tax rules, mileage rates, deductions and deadlines are read from the backend; unsupported contexts remain disclosed as estimates.

## Contracts and remaining scope

The additive endpoint table, exact requests/responses and role rules were listed before implementation in [ACCOUNTANT_PANEL_CONTRACTS.md](../docs/ACCOUNTANT_PANEL_CONTRACTS.md). Exact schemas are in [openapi.json](../docs/openapi.json). Existing driver APIs stay compatible; `tax_year` is an optional addition to accountant requests, and two human-message endpoints are additive. Old requests with no export/year show **Year not supplied** and do not imply a filing deadline.

| Deferred endpoint group | Example method/path | Request | Expected response | Status |
| --- | --- | --- | --- | --- |
| Tax workspace/checklist | `GET /staff/returns/{id}` | Return ID | Checklist, immutable review version, adjustments, sign-off | Screen 5, model to agree |
| AI review/feedback | `POST /staff/ai-reviews/{id}/feedback` | Review version, correction, reason | Audited feedback | Screen 6, model to agree |
| Staff/users/roles | `PATCH /staff/users/{id}` | Expected version, approved role/team changes | Updated membership | Screen 7 |
| Admin configuration | `PATCH /staff/settings/{key}` | Versioned approved configuration | Audited settings | Screen 7; rates/catalog currently existing backend registry |
| GDPR requests | `POST /staff/privacy-requests` | Driver ID, export/deletion kind, reason | Retention/legal-hold-aware request | Screen 7, policy to agree |

No final tax filing or billing action is introduced. Marking a handoff Filed records an actual external reference and requires senior/admin review; it does not send anything to HMRC. Production provider setup, retention/deletion policy and broader tax limitations remain as documented by the existing backend.

## Verify

```powershell
npm test
npm run build
npx playwright install chromium
# Repository root; Docker Desktop required, never uses the development DB:
.\.venv\Scripts\python.exe -m pytest tests/test_staff_panel.py -q
$env:RUN_PANEL_BROWSER='1'
.\.venv\Scripts\python.exe -m pytest tests/test_panel_browser.py -q
```

The live browser harness builds the panel, starts its own temporary PostgreSQL/API, provisions synthetic identities, runs Playwright and cleans up its server/container. It checks the real staff API, receipt corrections, support permissions, private notes, saved views, CSV and tablet/light/dark WCAG scans. Running `npm run test:e2e` directly without this harness skips the authenticated tests rather than using saved credentials.

Validated 29 October 2026: 230-test backend suite checkpoint, six frontend unit tests, all four live browser scenarios, production/Docker builds, Compose validation and Nginx syntax. Detailed evidence and scope boundaries: [implementation status](../docs/BACKEND_IMPLEMENTATION_STATUS.md#accountant-panel-verification--29-october-2026).

## Visual system

The workspace uses taxi amber, navy and neutral surfaces from the supplied TaxiAiBooks design brief. All runtime colors, spacing, radii and motion durations come from `src/theme/tokens.css`; `src/theme/antd-theme.ts` maps those variables into Ant Design. Accessible semantic foreground tokens accompany the supplied chart/fill colors where the defaults would fail AA contrast on tinted surfaces. Inter and JetBrains Mono are bundled locally; no font CDN is used. Lucide supplies interface icons.

The `/login` front page pairs a branded receipt-to-review illustration with a focused sign-in card, visible two-step progress and a responsive mobile layout. Its styles live in `src/pages/login.css`, and `LoginShowcase` draws the workflow using HTML and icons without loading account data. Password recovery, reset and authenticator verification share the same design.

Open `/styleguide` without signing in to inspect illustrative component examples in both modes: buttons, financial values, status badges, forms, table density/selection, AI confidence, Recharts, empty/loading/error states, modal/drawer motion and toast Undo. No real driver data is loaded there. This route is loaded separately from the workspace bundle. `src/theme/motion.ts` provides shared motion references, a reduced-motion hook and first-load KPI counting. CSS and chart animations respect the device's reduced-motion setting.

The top bar supports Ctrl/Cmd+K driver search. Tables offer compact rows, sticky headers/filter bars, amber selection, numeric alignment and keyboard-accessible row actions. Receipt images support zoom and drag/scroll panning. AI provenance is purple and reviewed values show a green check. Receipt approve/exclude notifications offer a four-second Undo using the existing exact-mutation reversal endpoint; normal audit, version and period-lock rules still apply.

To verify the appearance independently of PostgreSQL:

```powershell
npm.cmd run build
npm.cmd test
npm.cmd run test:e2e -- e2e/theme.spec.ts
```

These browser checks cover appearance persistence, live System mode, both themes' WCAG scans, overlays, density, reduced motion, mobile/tablet overflow, the workspace/search shell and receipt Undo. Workspace/receipt tests intercept requests with synthetic responses confined to the test process. They do not replace the live PostgreSQL integration suite above.
