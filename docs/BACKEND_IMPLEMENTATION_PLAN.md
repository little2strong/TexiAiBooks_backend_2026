# Backend implementation plan

29 October addendum: the accountant panel’s first delivery implements screens 1–4 (login/2FA, dashboard, handoffs, Driver 360) with additive, role-scoped staff APIs. Stop before screens 5–7 as requested. Contracts, setup and the deferred endpoint table are in [the panel README](../accountant-panel/README.md) and [staff contracts](ACCOUNTANT_PANEL_CONTRACTS.md). The phase plan below remains the original driver-backend plan.

Proceed through phases 0?10 in order, without routine approval stops. Existing password and provider contracts stay usable. New contracts use /api/v1 and operation IDs from the proposal. Migrations are additive and validated on disposable PostgreSQL only.

1. Audit source, generated OpenAPI, existing tests and all twelve analysis documents. Record each operation and dependency.
2. Foundation: shared atomic ownership/idempotency/version/history primitives; phone challenge adapter alongside existing password sessions; external encryption key ring.
3. Profiles/onboarding/source catalogs/default taxi business and encrypted optional tax identifiers.
4. Vehicles/elections/manual mileage with verified year-specific HMRC rules.
5. Canonical typed ledger; backfill legacy expenses and synchronize legacy writes, then shared reports/policies/reversals.
6. Private uploads, durable worker jobs, scanner/OCR interfaces, manual reviewed receipt posting.
7. Versioned statement parsers, preview/import deduplication, overlap checks and ledger-backed reconciliation.
8. Tax rules, combined income/PAYE estimates, regional bands, projections, prior-assessment inputs, savings entries.
9. Reports, private exports/photo packages, notifications/deadlines, approved plans/trials and consented accountant requests.
10. Disabled-by-default external integration interfaces, immutable MTD snapshots/per-business outcomes and consented assistant context. Explicitly reject unavailable providers; never invent remote success.
11. Run full PostgreSQL tests, upgrade/downgrade preservation checks, OpenAPI inventory and contract documentation. Update all 93 coverage rows and list exact remaining external/product requirements.

Validation covers tenant isolation, integer money/Decimal mileage, draft exclusion, edited receipt persistence, duplicate postings, stale versions, owner-global idempotency, exact reversals, import accounting and external failure. Controlled adapters are test-only. Real SMS/OCR/billing/HMRC/assistant success requires configured real providers. New frontend forms and native permissions remain separately documented frontend work.

## Execution outcome

Phases 0?10 were executed for the implementable internal scope. Three additive migrations and the actual contract/handoff/runbook artifacts are delivered. The final per-phase table, verification evidence, supported formats/tax scope and exact remaining provider/product decisions are in [BACKEND_IMPLEMENTATION_STATUS.md](BACKEND_IMPLEMENTATION_STATUS.md); no disabled provider route is treated as live completion.
