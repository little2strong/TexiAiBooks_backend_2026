# Backend gap analysis

29 October addendum: accountant web screens 1–4 and their staff access APIs are covered by [ACCOUNTANT_PANEL_CONTRACTS.md](ACCOUNTANT_PANEL_CONTRACTS.md) and [the panel README](../accountant-panel/README.md). Dedicated return review, AI feedback and admin/GDPR screens remain subsequent delivery. Earlier gap findings below describe the original driver-app audit.

Audit date: 27 October 2026 (Asia/Dhaka). Baseline working tree clean. No applicable AGENTS.md found in repository or parents. All twelve imported documents inspected; operation inventory preserved in proposed_operations.json. Requirements remain proposals, not existing contracts.

Existing stack: Python 3.12 virtual environment; FastAPI 0.162.0, SQLAlchemy 2.0.55, Pydantic 2.14.1, Alembic 1.20.1, PostgreSQL 16 via Docker. Two existing migrations. Per-request sessions close/rollback on error. Existing expense soft deletion/owner isolation and password auth retained. Current error envelope is detail, including redacted validation arrays; preserve it.

Baseline: 54 tests passed; 126 PostgreSQL fixture errors while Docker stopped. Docker subsequently started through docker desktop start. An isolated copy of original HEAD then passed all 180 tests on disposable PostgreSQL. No development database accessed or reset.

| ID | Proposed method/path | Initial classification | Evidence / dependency |
| --- | --- | --- | --- |
| A01 | POST `/v1/auth/challenges` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| A02 | POST `/v1/auth/challenges/{id}/verify` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| A03 | POST `/v1/auth/providers/{provider}` | Existing but needs changes | POST /api/v1/auth/providers/{provider}; single-use provider challenge required |
| A04 | POST `/v1/auth/refresh` | Existing but needs changes | POST /api/v1/auth/refresh; rotation/replay revocation |
| A05 | POST `/v1/auth/logout` | Existing but needs changes | POST /api/v1/auth/logout; bearer session revocation |
| A06 | GET `/v1/me` | Existing but needs changes | GET /api/v1/users/me; needs frontend profile projection |
| A07 | POST `/v1/auth/challenges/{id}/resend` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| P01 | PATCH `/v1/me` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| P02 | GET `/v1/me/onboarding` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| P03 | PATCH `/v1/me/onboarding` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| P04 | GET `/v1/me/driver-profile` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| P05 | PUT `/v1/me/driver-profile` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| P06 | GET `/v1/me/tax-profile` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| P07 | PUT `/v1/me/tax-profile` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| F01 | GET `/v1/reference-data` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| V01 | POST `/v1/vehicles/lookup` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| V02 | GET `/v1/vehicles` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| V03 | POST `/v1/vehicles` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| V04 | GET `/v1/vehicles/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| V05 | POST `/v1/vehicles/{id}/claim-method` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| V06 | PATCH `/v1/vehicles/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| I01 | GET `/v1/me/income-sources` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| I02 | PUT `/v1/me/income-sources` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| L01 | GET `/v1/transactions` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| L02 | POST `/v1/transactions` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| L03 | GET `/v1/transactions/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| L04 | PATCH `/v1/transactions/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| L05 | DELETE `/v1/transactions/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| L06 | POST `/v1/transactions/{id}/reversals` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| R01 | GET `/v1/dashboard` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| R02 | GET `/v1/reports/weekly` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| R03 | GET `/v1/reports/annual` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| R04 | GET `/v1/categories/summary` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| R05 | GET `/v1/categories/{id}/transactions` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| R06 | GET `/v1/reports/personal` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| R07 | PUT `/v1/categories/{id}/business-use` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| C01 | POST `/v1/receipts` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| C02 | GET `/v1/receipts` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| C03 | GET `/v1/receipts/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| C04 | PATCH `/v1/receipts/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| C05 | POST `/v1/receipts/{id}/confirmations` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| C06 | POST `/v1/receipts/{id}/reversals` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| C07 | GET `/v1/receipts/{id}/content` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| C08 | POST `/v1/receipts/{id}/ocr-retries` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| D01 | POST `/v1/statements` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| D02 | GET `/v1/statements` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| D03 | GET `/v1/statements/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| D04 | POST `/v1/statements/{id}/imports` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| D05 | GET `/v1/statements/{id}/content` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| Q01 | GET `/v1/reconciliations` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| Q02 | GET `/v1/reconciliations/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| Q03 | POST `/v1/reconciliations/{id}/resolutions` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| Q04 | POST `/v1/reconciliations/{id}/reversals` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| M01 | GET `/v1/mileage-logs` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| M02 | POST `/v1/mileage-logs` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| M03 | PATCH `/v1/mileage-logs/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| M04 | DELETE `/v1/mileage-logs/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| T01 | GET `/v1/tax/estimate` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| T02 | GET `/v1/tax/forecast` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| T03 | GET `/v1/tax/deduction-comparison` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| T04 | GET `/v1/tax/payment-timeline` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| T05 | GET `/v1/tax/rules` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| K01 | GET `/v1/tax-pot` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| K02 | POST `/v1/tax-pot/entries` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| K03 | POST `/v1/tax-pot/entries/{id}/reversals` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| N01 | GET `/v1/notifications` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| N02 | PATCH `/v1/notifications/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| N03 | POST `/v1/notifications/read-all` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| N04 | GET `/v1/deadlines` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| E01 | POST `/v1/exports` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| E02 | GET `/v1/exports/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| E03 | GET `/v1/exports/{id}/download` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| H01 | POST `/v1/accountant-requests` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| H02 | GET `/v1/accountant-requests/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| S01 | GET `/v1/subscription-plans` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| S02 | GET `/v1/me/subscription` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| S03 | POST `/v1/me/subscription/trial` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| S04 | POST `/v1/billing/webhooks/{provider}` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| S05 | POST `/v1/me/subscription/checkout` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| S06 | POST `/v1/me/subscription/cancellation` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| U01 | GET `/v1/mtd/eligibility` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| U02 | POST `/v1/mtd/authorizations` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| U03 | GET `/v1/mtd/oauth/callback` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| U04 | GET `/v1/mtd/businesses` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| U05 | GET `/v1/mtd/obligations` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| U06 | POST `/v1/mtd/previews` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| U07 | POST `/v1/mtd/updates` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| U08 | GET `/v1/mtd/updates/{id}` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| U09 | GET `/v1/mtd/updates/{id}/confirmation` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| U10 | GET `/v1/mtd/updates` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| B01 | POST `/v1/assistant/conversations` | Missing | No matching route or persisted entity in baseline source/OpenAPI |
| B02 | POST `/v1/assistant/conversations/{id}/messages` | External dependency required | Provider/terms/evidence required; internal architecture can proceed |
| B03 | GET `/v1/assistant/conversations/{id}/messages` | Missing | No matching route or persisted entity in baseline source/OpenAPI |

## Reconciled outcome

The table above preserves the initial audit classification. Final per-ID status, actual paths, evidence and limitations are maintained in [operation_coverage.json](operation_coverage.json) and [ACTUAL_API_CONTRACTS.md](ACTUAL_API_CONTRACTS.md). All 93 IDs are accounted for. The implementation has 73 verified internal contracts and 20 explicitly provider/configuration-dependent contracts; a disabled integration route is not counted as a completed live integration.

Three additive migrations reuse the original eight tables and add twenty tables, rather than duplicating all 46 proposals. Existing expense IDs/values remain and synchronize a single canonical ledger. Profile aggregates and integration envelopes are consolidated deliberately; core financial money/date/ownership fields remain typed. Private blobs use PostgreSQL rather than public file storage. Catalogs/rules have stable versioned code IDs. Full differences and native/provider/product dependencies are recorded in the implementation status and frontend handoff.

The audit found no Flutter integration contract to preserve. Compatibility choices preserve the established backend /api/v1 prefix, password form login, provider nonce challenge, detail error envelope and old expense paging. New clients use canonical transactions and documented owner-global idempotency/version/reversal contracts. Native platform PDF parsing, advanced tax contexts and live providers remain explicit limitations, not claimed successes.
