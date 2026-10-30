# TaxiAiBooks admin UI debugging report

The existing theme and application routes are preserved. The changes address layout stability, recoverable data states, validated responses and visible business rules. Financial calculation results and filing policy are unchanged.

## 1. Findings before fixes

Full investigation and original file/line references: [Phase 1 findings](ADMIN_PANEL_UI_DIAGNOSIS.md).

| Symptom | Screen | Root cause and original location | Fix |
| --- | --- | --- | --- |
| Table shrinks by about 184 px after loading | Handoff queue | Generic skeleton and data table have different sizes; `DataTable.tsx:326` | Shared states in a fixed table viewport |
| Content moves during sidebar/navigation changes | Workspace | Width/margin transitions and entrance transform around sticky elements; `styles.css:186,346,401` | Remove layout animation, stable scrollbar gutter |
| Selection clears on unrelated renders | Tables | Query object identity effect; `DataTable.tsx:137` | Content-hashed view scope, including reordered filter keys |
| Blank or crashed content on unexpected responses | All data panels | Unvalidated JSON, incomplete fallback states, unguarded dates; `client.ts:100`, `States.tsx:4`, `format.ts:2` | Runtime resource contracts, shared states and panel/route boundaries |
| Populated payment timeline can crash | Driver → Tax | UI reads `label_key`; backend prior-assessment rows use `type`; `DriverProfile.tsx:149` | Normalize both variants once at the API boundary |
| Review/status/financial meaning unclear | Profile, queue, tax, receipts | Existing bands and adjustments omitted; workflow/reviewer metadata unavailable in read projection | Explain figures, glossary, next action, audit-backed metadata and checks |

No confirmed infinite render loop, random row keys, competing theme providers, incorrect table resource/accessor, or response naming mismatch was found in the measured normal journeys. An empty development driver database is legitimate; the UI now explains access scope and empty results. Further checks and limits are in the diagnosis document.

## 2. Fixes grouped by root cause, with diffs

| Root cause | Changes | Review diff |
| --- | --- | --- |
| Layout, motion and render instability | Shared loading/empty/error/data frames; matching panel skeletons; fixed 360 px table viewport and density rows; stable gutter; bounded media; visible row actions; remove width/margin and route entrance animations; adjusted font fallback/preload; stable theme context and HMR root; route and major-panel boundaries | [Layout/states/motion diff](../artifacts/ui-debug/diffs/01-layout-states-motion.diff) |
| Unchecked or ambiguous API data | Zod schemas for all consumed resources, centralized response mappers, payment variant normalization, explicit unknown versus zero, guarded dates, visible request IDs and expired-session notice | [Validation/error diff](../artifacts/ui-debug/diffs/02-api-validation-errors.diff) |
| Missing business context and provenance | Status tooltips; workflow timestamps without invented dates; record history and scoped audit drawers; next actions; formula/input/rate/year/source drawers; actual reviewer attribution; OCR confidence and notes; enforced filing requirements separated from review advisories; concrete reassignment/exclusion/filing confirmations | [Workflow/explanation/audit diff](../artifacts/ui-debug/diffs/03-workflow-explanations-audit.diff) |
| Missing regression evidence | Component-state tests, real synthetic API fixtures for 19 response paths, equivalent-query selection regression, populated payment/band variants, slow-API CLS/console smoke, explicit filing-confirmation test, React profiling, reproducible Chrome/Lighthouse captures, README merge checklist | [Verification/tooling diff](../artifacts/ui-debug/diffs/04-verification-and-tooling.diff) |
| Dependency reproducibility | Runtime Zod and opt-in render diagnostics; optional Lighthouse/Puppeteer tools isolated under `tools/ui-audit` with their own lockfile | [Lockfile diff](../artifacts/ui-debug/diffs/05-dependency-lockfiles.diff) |

Existing ledger column names remain compatible. New snake_case metadata maps to camelCase UI fields (`workflowEvents`, `reviewerName`, `reviewedAt`, `calculationContext`) in the resource mappers. Dynamic rule keys are preserved. Application code does not guess response aliases in individual cells.

### Explicit API additions

These additions were necessary to explain recorded workflow and calculations accurately. No application endpoint or route was added, and no migration is required.

- Handoff responses add `workflow_events` from existing staff audit records, limited to the most recent 50 events; full driver activity remains paginated.
- Overview adds scoped, selected-year/missing-year `handoffs`.
- Ledger/receipt reads add actual `reviewed_by` and `reviewed_at`, when the latest relevant audit is a review. Reversal/correction clears old attribution; legacy missing actors stay explicit.
- Activity accepts optional `filters.resource_id` and returns `resource_id`, allowing a drawer to show that record's staff and canonical mutation history.
- Tax adds a whitelisted `calculation_context`, excluding identifiers and employer names. The existing student-loan rule entry now exposes the same thresholds/rates used by the calculator, with its verified tax year. Existing loan constants were centralized without changing amounts or formulas.
- HTTP responses echo a validated/generated `X-Request-ID`. Client errors show the corresponding ID.

The danger-button foreground uses the existing accessible expense token after WCAG verification exposed a low-contrast generated hover color. No palette token changed.

## 3. Business glossary and formulas to confirm

[Complete status glossary, all 21 figure definitions, action effects and permissions](ADMIN_PANEL_BUSINESS_GLOSSARY.md). The UI uses those same definitions.

The filing workflow is Requested → In review → Waiting on driver → Ready to file → Filed. This is an intended sequence; the existing backend permits other non-filed transitions. Each badge explains the next owner/trigger, and only recorded transitions receive timestamps. Requested uses the original request creation time.

Key formulas, using server-returned amounts:

- Income = confirmed income postings in the selected year through the server as-of date.
- Deductible expenses = confirmed expense deductions + eligible mileage deduction.
- Profit = income − deductible expenses.
- Estimated liability = max(0, income tax + Class 4 NI − PAYE tax paid) + student loan repayment. Savings tax is already included in income tax.
- Mileage deduction = sum of each eligible vehicle's miles in each band × the applicable API rate, subject to its effective claim election and vehicle eligibility.
- Payment amounts use the supplied prior assessment and current-pace projection; absent assessments stay unknown.

Rates, thresholds, official source links, verification dates and rule-set versions are displayed from the API. This change does not independently certify statutory correctness.

## 4. Proof, limits and questions

Measurements use production preview, Chromium, 1440×900, normal motion, 800 ms API latency and the same disposable synthetic-data scenario. Full-page screenshots are taken after measurement windows. The original source is rebuilt from the saved source-only snapshot for the baseline.

| Screen | Before Lighthouse CLS | After Lighthouse CLS | Before / after screenshots |
| --- | ---: | ---: | --- |
| Dashboard | 0.011308 | 0.014083 | [Before](../artifacts/ui-debug/before/dashboard.png) / [After](../artifacts/ui-debug/after/dashboard.png) |
| Handoff queue | 0.005100 | 0.014092 | [Before](../artifacts/ui-debug/before/handoffs.png) / [After](../artifacts/ui-debug/after/handoffs.png) |
| Driver profile | 0.001688 | 0.014045 | [Before](../artifacts/ui-debug/before/driver-profile.png) / [After](../artifacts/ui-debug/after/driver-profile.png) |
| Tax workspace | 0.006546 | 0.000029 | [Before](../artifacts/ui-debug/before/tax-workspace.png) / [After](../artifacts/ui-debug/after/tax-workspace.png) |

All measured values are below 0.1. These small-fixture values do not show a universal CLS improvement; they establish the acceptance threshold and a separately measured geometry correction. Queue height changed from **426 → 242.27 px** while loading before the fix, and stays **496 → 496 px** afterward. Loading screenshots and exact bounding boxes are saved alongside each screen.

The initial 0.403 handoff reading was invalidated because full-page screenshot resizing occurred inside its measurement window. The original source was rerun with that contamination removed; only corrected measurements are reported above.

Evidence:

- [Before Lighthouse flow](../artifacts/ui-debug/before/lighthouse.html) / [After Lighthouse flow](../artifacts/ui-debug/after/lighthouse.html).
- [Before Chrome layout events](../artifacts/ui-debug/before/chrome-layout.json) / [After Chrome layout events](../artifacts/ui-debug/after/chrome-layout.json), including loading/loaded geometry.
- Load the four `chrome-*.trace.json` files in either evidence directory into Chrome DevTools Performance. CPU profiles are also included.
- [React Profiler / why-did-you-render evidence](../artifacts/ui-debug/after/react-profiler.json): **zero idle commits** in the observed 1.5 second quiet window; no console errors. This uses React's Profiler API and the render diagnostic package; the browser-extension profiler UI was not automated.
- [Synthetic API response fixtures](../accountant-panel/src/api/__fixtures__/staff.json): 19 response paths; auth token redacted. No development records or saved credentials were used.
- Verification: 68 frontend tests; 17 staff backend checks; 4 focused tax/workflow checks; normal browser suite, separate before/after Lighthouse runs and development React profiling. [Browser execution log](../artifacts/ui-debug/validation/browser-suite.txt).
- [Panel dependency audit](../artifacts/ui-debug/panel-dependency-audit.json): zero reported vulnerabilities. Optional isolated audit tooling has 10 upstream high-severity advisories recorded in [its separate audit](../artifacts/ui-debug/audit-tool-dependencies.json); dependency-security sign-off for that optional toolchain remains outstanding.

Limits and exact questions:

1. Severe production shaking was not reproduced with the small synthetic dataset. **Which screen, driver ID, role, browser and approximate record count reproduce it with your real data?** The traces and regression checks make a subsequent reproduction comparable.
2. No separate tax-return record/route exists yet; this work uses the existing Driver → Tax workspace and handoff filing record. No new lifecycle was inferred.
3. Pending receipts and reconciliation issues are advisories under the current server policy. **Should they become mandatory server-enforced filing blockers, or remain review advisories?**
4. Real HMRC submission, provider delivery and independent statutory-rate verification were not part of these checks. They remain existing integration/policy scope.

The README contains the requested merge checklist and exact reproduction commands. The normal development app uses its existing database and email/password login; synthetic test data stays isolated.
