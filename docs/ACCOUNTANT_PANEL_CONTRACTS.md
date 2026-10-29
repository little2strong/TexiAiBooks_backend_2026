# Accountant panel: additive contracts (listed before implementation)

29 October 2026. Existing driver contracts remain unchanged. Staff cannot use driver JWTs to cross account boundaries. The panel reuses the existing user password hashes, revocable device sessions, reset delivery, encryption key ring, rate limits, canonical ledger, receipt confirmation, tax rules and private file scanning. Staff JWTs have a separate audience and token type. Staff membership is provisioned explicitly; driver signup never grants a staff role.

The user requested implementation following backend logic after being asked about missing staff models. Additive models: teams; staff membership referencing the existing authentication identity; one current driver assignment; handoff state linked to an actual consented accountant request; human communications; staff audit events; per-staff saved table views. Authenticator TOTP seeds are encrypted and counters prevent replay. No sample staff, passwords, drivers or financial data are installed.

## New staff endpoints

All paths below start `/api/v1/staff`. JSON unless stated. Protected methods require a staff bearer token. Accounting/collaboration commands and saving views require `Idempotency-Key`; auth/session, reveal, query/export and saved-view deletion do not. Queries containing search/identifiers are POST bodies to avoid URL logs. `TableQuery = {page:1,page_size:25,sort:"created_at",order:"desc",search:"",filters:{}}`; `Page<T> = {items:T[],total:number,page:number,page_size:number}`. Sort/filter fields are allowlisted by resource. Saved views are server-side and private to the staff member. IDs in paths are opaque UUIDs.

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| POST | `/auth/login` | `{email,password}` | `{challenge_id,expires_in}`; no JWT until MFA |
| POST | `/auth/verify` | `{challenge_id,code}` | `{access_token,expires_in,staff}` |
| POST | `/auth/logout` | none | 204, session revoked |
| GET | `/me` | none | `{id,name,email,role,team_id}` |
| GET | `/config` | none | supported tax years, current year, upload limits, idle timeout |
| POST | `/dashboard` | `{tax_year}` | scoped counts, workload, actual configured deadline and countdown |
| POST | `/drivers/search` | `TableQuery` | `Page<DriverSummary>` |
| POST | `/handoffs/search` | `TableQuery` | `Page<Handoff>` |
| POST | `/accountants/search` | `TableQuery` | scoped `Page<StaffSummary>` |
| POST | `/handoffs/assign` | `{ids,accountant_id,versions,reason}` | atomic scoped assignment results |
| PATCH | `/handoffs/{id}` | `{expected_version,status,reason,filing_reference?}` | versioned handoff; Filed requires senior/admin and an actual external reference |
| POST | `/drivers/{id}/overview` | `{tax_year}` | masked identity, driver profile, subscription, canonical totals |
| POST | `/drivers/{id}/{resource}/search` | `TableQuery` with `filters.tax_year` | `Page<T>` for income, expenses, mileage, documents, messages, notes, activity |
| POST | `/drivers/{id}/tax` | `{tax_year}` | backend estimate, payment timeline and verified rules; unsupported contexts disclosed |
| POST | `/drivers/{id}/identifiers/reveal` | `{tax_year,field,reason}` | `{value,expires_in:30}` after committed reveal audit; support forbidden |
| PATCH | `/drivers/{id}/expenses/{expense_id}` | existing `TransactionPatch` | canonical transaction; provenance/period/version restrictions retained |
| GET | `/drivers/{id}/receipts/{receipt_id}` | none | existing receipt projection plus scanned file access metadata |
| POST | `/drivers/{id}/receipts/{receipt_id}/review` | `{expected_version,decision,category_id,business_use_percent,reason}` | existing receipt confirmation result; reject records excluded evidence with zero deduction |
| POST | `/drivers/{id}/documents` | multipart file | private, quarantined driver evidence metadata |
| GET | `/drivers/{id}/documents/{file_id}/content` | none | audited bytes; only clean/generated files |
| POST | `/drivers/{id}/messages` | `{body}` | durable human message |
| POST | `/drivers/{id}/notes` | `{body,kind:"note"\|"ticket"}` | durable internal note/ticket, support allowed |
| POST | `/views/search` | `{resource}` | saved view list |
| POST | `/views` | `{resource,name,query}` | saved view |
| DELETE | `/views/{id}` | none | 204 |
| POST | `/exports` | `{resource,driver_id?,query}` | audited CSV of the complete filtered result (bounded 10,000 rows; reject over limit) |

Recovery uses the existing `/api/v1/auth/forgot-password` and `/api/v1/auth/reset-password`. The panel accepts the reset token as pasted input; it never places secrets in URLs. SMTP remains required. New `/api/v1/me/accountant-messages/search` and `/api/v1/me/accountant-messages` provide the driver's side of the human thread without changing Flutter code.

Compatibility addition identified during source review: existing `POST /accountant-requests` has no tax-year input. Add optional `tax_year` (`YYYY-YY`); existing callers remain valid. An attached export supplies its authoritative year and conflicting years reject. Old requests without an export/year display **Year not supplied** and are excluded from deadline assertions. Add `POST /drivers/{id}/receipts/{receipt_id}/reversals` with the existing `Reversal` request for exact corrections before re-review. Add `/drivers/{id}/documents/{file_id}/scan-retries` to retry failed, bounded private document scanning.

Receipt review also needs unconfirmed evidence with no ledger draft. Add `receipts` to driver table resources and `PATCH /drivers/{id}/receipts/{receipt_id}` using the existing `ReceiptPatch` body/response. This reuses driver review validation and draft synchronization, so correcting the extracted amount/date never posts money implicitly.

## Access rules

Accountants: assigned drivers. Senior accountants: their team's drivers and same-team reassignment. Admin: all non-staff driver identities, reassignment across teams. Support: all non-staff drivers read-only plus notes/tickets; cannot reveal identifiers, export financial rows, upload, message or alter books. An assignment grants access; merely requesting help does not assign a driver. Admin must initially assign unassigned handoffs. Staff roles are fetched from the database on every request, never accepted from client claims.

Staff reads and writes are audited on the server. Financial mutation audit and canonical effects commit together. Identifier values never enter audit payloads. Reads, downloads, searches and CSV exports record scope, actor and time without saving raw search text. No UI action marks a return filed without an actual reference; no HMRC submission is introduced.

UTR searches cannot be persisted in saved views. Staff OpenAPI uses a separate `StaffBearer` scheme: complete the two-step staff login and paste its resulting bearer token when using Swagger. The driver OAuth password scheme is unchanged. Existing accountant-request idempotency fingerprints remain replayable when the new optional year is absent.

## Explicit delivery boundary

Screens 1–4 only. Tax-return workspace, dedicated AI-review screen and admin configuration/GDPR workflows (screens 5–7) remain subsequent work. Existing backend categories/rules remain authoritative; no category or tax-rate editor is introduced. AI confidence is displayed only if stored extraction supplied it; a missing confidence is shown as unavailable. No synthetic rows appear in the application.
