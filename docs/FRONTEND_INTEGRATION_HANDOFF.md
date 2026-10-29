# Flutter integration handoff

29 October addendum: the [separate accountant React panel](../accountant-panel/README.md) now implements requested screens 1–4 through [additive staff contracts](ACCOUNTANT_PANEL_CONTRACTS.md). Flutter remains unchanged. `POST /accountant-requests` additionally accepts an optional `tax_year`; an attached export must match it. New owner-scoped `POST /me/accountant-messages/search` and `POST /me/accountant-messages` expose the human accountant thread. Internal notes/tickets never appear in that driver thread. Staff handoff status is operational review state and does not imply actual HMRC delivery.

Implementation date: 27 October 2026 (Asia/Dhaka). Flutter code was not changed. The backend uses `/api/v1`, not the proposed `/v1`. All 93 proposed IDs are mapped to actual methods/paths and explicit dependencies in [ACTUAL_API_CONTRACTS.md](ACTUAL_API_CONTRACTS.md). [openapi.json](openapi.json) is the generated schema; [operation_coverage.json](operation_coverage.json) is the machine-readable coverage inventory. Endpoint registration does not mean an external provider is operational.

## Authentication and startup

Existing password registration is `POST /api/v1/auth/register` with JSON `email` and `password`. Login is `POST /api/v1/auth/login` with **form data**, `username` containing the email and `password`. Token responses contain `access_token`, `refresh_token`, `token_type`, `expires_in`, `refresh_expires_in` and `session_id`; fetch `GET /api/v1/me` separately for the frontend profile. Never ship example credentials or store tokens in ordinary query caches.

All private calls use `Authorization: Bearer <access_token>`. Rotate through `POST /api/v1/auth/refresh` with `{"refresh_token":"<refresh_token>"}`. Refresh credentials are single-use; detected replay revokes the device session. Serialize refresh attempts on the client. `POST /api/v1/auth/logout` revokes the authenticated session and returns 204; it takes no refresh-token body. Other session/password/recovery endpoints remain documented in [AUTH_API.md](AUTH_API.md).

Phone signup/sign-in uses A01/A02/A07 alongside password login. A01 accepts `{"phone":"07700 900123","purpose":"sign_up"}`; response shape is `{"challenge_id":"<uuid>","destination_masked":"*******0123","expires_at":"<UTC timestamp>","resend_after_seconds":60}`. Submit the actual six ASCII digits to `/auth/challenges/{id}/verify`. Resend creates a new challenge and invalidates the old one. No OTP is returned. Missing SMS/encryption/hash configuration returns 503. Authenticated `/auth/otp/send` and `/auth/otp/verify` remain delivery-verification endpoints; they do not replace phone login.

Apple/Google retain the existing secure exchange: first `POST /auth/provider-challenge` with `{"provider":"google"}`, send the returned nonce to the native provider, then exchange `id_token` and `challenge_id` at `/auth/providers/{provider}`. This deliberately differs from the proposed `identity_token`/client-supplied nonce. Never link an existing account solely by a matching email. Native Face ID unlock is client work.

After authentication, load `/me`, `/me/onboarding`, `/reference-data` and `/capabilities`. Preferences support the actual frontend languages `en`, `ur`, `pa`, `pl`, `ro`, `bn`, `ar`. Names remain null until supplied; no driver, car, salary or opening balance is fabricated. Phone-only users have nullable email. Council codes currently use manual entry and are not an official validation catalog.

## Writes, errors and paging

New profile, financial, job and consent writes require a UUID `Idempotency-Key`. Persist one key for each logical action and reuse it after a network timeout. The owner-global key binds method, concrete path, query and body digest. Changed input or another path with the same key returns 409. Auth credentials have their own replay rules and are not cached in this table. Legacy `/expenses` keeps its existing write contract and offset paging; new clients should use `/transactions` for versions and idempotency.

Updates use the returned `version` as `expected_version`. A 409 means refetch and review the conflict. Keep the exact returned `mutation_id` for Undo; a later change can prevent reversal. There is no global remove-last action. DELETE transaction returns 204; fetch that record to obtain the void mutation before reversing it.

The established error envelope stays `{"detail":"message"}`. Validation is `{"detail":[{"loc":["body","amount_pence"],"msg":"…","type":"…"}]}`; raw input is redacted. Handle 401, 403, 404, 409, 410 expired export, 413 upload limit, 422, 429 with `Retry-After`, and 503 dependency unavailable. Another owner's resource returns 404. Preserve drafts after failed requests; do not navigate to success on timeout.

Lists use `{"items":[],"next_cursor":null,"has_more":false}` and `limit=1..100` (default 50). Cursors are signed and bound to owner, resource and filters. Reset the cursor when filters change. Use repeated `source_ids`/`category_ids` query arguments. L01 supports `tax_year`, inclusive `from`/`to`, `kind`, `review_status`, `claim_status` and escaped case-insensitive description search `q`. A reversed record remains readable for audit.

## Profile and bookkeeping examples

These examples use synthetic data. Create or update driver context first:

```json
{
  "licence_type": "private_hire",
  "council_code": "manual-council-reference",
  "work_pattern": "full_time"
}
```

`PUT /me/driver-profile` atomically creates/links the default taxi business and returns `primary_business_id` plus `version`. Later PUTs require `expected_version`. Onboarding completion checks saved driver/tax context and a vehicle with an election. Optional encrypted identifiers require an external key ring; responses expose masks only. Tax-profile employments are annual real inputs; `property_income_pence` means user-supplied taxable property profit, not platform gross or unreviewed rental turnover.

Resolve `source_id` and `category_id` from reference data, then `POST /transactions`:

```json
{
  "kind": "income",
  "amount_pence": 25000,
  "currency": "GBP",
  "occurred_on": "2026-10-20",
  "business_id": "<primary_business_id>",
  "source_id": "<uber_source_id>",
  "payment_method": "card_bank",
  "description": "Synthetic gross fares"
}
```

Response fields include `id`, the submitted values, `review_status:"confirmed"`, server-derived `claim_status`, `deductible_pence`, `business_use_percent:"100.00"`, `version:1`, `mutation_id` and UTC `created_at`. Post fees separately as expenses in `platform_fees`; net payout is never another income record. A manual expense requires `category_id`; omit the share to inherit its effective default or supply a decimal string for an explicit override. Unknown/specialist-review categories and ineligible vehicle costs are retained with zero deduction and reason codes.

`PATCH /transactions/{id}` example: `{"expected_version":1,"amount_pence":26000}`. Reverse its exact correction with `{"expected_version":2,"mutation_id":"<correction_mutation_id>","reason":"Correct this edit"}` at `/transactions/{id}/reversals`. Receipt/import-backed records require their originating workflow. Existing expense IDs are preserved in canonical transactions, and legacy writes synchronize the same ledger instead of being counted twice.

Amounts are integer GBP pence. Percentages and miles are decimal strings with at most two decimal places. Vehicle eligibility/elections use actual ownership/class/history; Hackney simplified mileage is rejected. Nonowned mileage remains conservatively disabled pending an approved rental/lease policy. Vehicle identity/class/ownership corrections after an election require a replacement vehicle, preserving prior history. Mileage logs require purpose and dates; paired odometers must reconcile, remain monotonic and not overlap. The deduction splits the tax-year threshold per vehicle. Read the claim acknowledgement version from reference data. An unused mileage election can change with ordered history; recorded simplified-mileage use locks the method and a mistaken-use correction requires review.

## Uploads, jobs and receipts

1. Acquire real bytes through a native camera/file picker. `POST /receipts` is multipart `file`, `business_id`, optional `vehicle_id`, with the idempotency header. It returns 202 with `receipt` and `job`.
2. Poll `/jobs/{id}` or `/receipts/{id}`. Jobs are persisted; the worker must actually run. No timer implies success. Missing scanner/OCR produces an explicit failed job. Attachments remain quarantined until scanning succeeds.
3. OCR preserves extraction separately from `reviewed`; usable extracted money/date can create an unconfirmed draft in L01. Drafts do not affect tax. Correct actual fields at `PATCH /receipts/{id}`; manual review works when OCR is unavailable.
4. Example review: `{"expected_version":2,"merchant":"Synthetic supplier","occurred_on":"2026-10-21","amount_pence":8000}`. Then confirm with `{"expected_version":3,"category_id":"<phone_data_category_id>","claim_status":"claimable","business_use_percent":"75.00"}`. The atomic result includes a transaction with **6000p deductible**, the actual 8000p bill, mutation ID and canonical dashboard. It does not post a fixed demo amount.
5. Reverse at `/receipts/{id}/reversals` with that receipt confirmation's mutation ID, expected version and reason. A second confirmation/reversal cannot create duplicate postings. Server eligibility can turn a requested claim into `excluded`; use canonical response states.
6. `/receipts` returns server counts independent of page length. Unknown-date evidence is retained in the review queue for the selected year. `/content` requires bearer ownership and a clean scan. Retry failed, retryable OCR with C08 or `/jobs/{id}/retries`; at most five processing attempts.

JPEG/PNG/PDF receipts and canonical CSV/PDF statement uploads are size/signature checked. Request bodies are bounded before multipart spooling. Original filenames are not retained. File bytes live privately in PostgreSQL, not at public URLs. No UK hosting or fixed retention-date guarantee is implied.

## Statements and reconciliation

The supported built-in parser is **canonical-csv-v1**. Native Uber/Bolt PDF layouts are not implemented or claimed to work; representative documents and format specifications are required. Unsupported PDFs fail with `unsupported_statement_format`. The built-in parser accepts at most 10,000 rows. The CSV header is exactly:

```csv
period_start,period_end,occurred_on,gross_pence,fee_pence,net_pence,adjustment_pence,external_id
2026-10-01,2026-10-07,2026-10-05,10000,1000,9000,0,synthetic-payout-1
```

Upload via D01 with `source_id` and `business_id`, poll the real parser job, inspect D03 and explicitly D04-confirm with `expected_version` and `acknowledged_warning_codes`. Supported rows require positive gross, nonnegative fee, zero adjustment, exact gross-fee=net, a date in the declared period and unique external IDs. Refunds/nonzero adjustments require an approved parser/accounting policy and fail explicitly.

An empty matching ledger imports separate gross and fee postings. Existing income in the period creates a reconciliation issue instead of a second copy. Duplicate files/rows and overlapping imported periods are rejected. Q02 returns actual gross **and fee** differences. Q03 supports the proposed `mode`, `transaction_ids`, `new_transactions`, `evidence_note`, `expected_version`; the result must reconcile both gross and fees. Linking existing money does not create another transaction. Exact Q04 reversal restores links and reverses only the newly created postings. `/statements/{id}/reversals` additionally reverses an exact import, requiring resolution reversal first where applicable.

## Reports, estimates and supporting workflows

Reports share confirmed ledger/mileage data and owner serialization. Current reports exclude future-dated money through the UK as-of date; historical reports use their year end. Annual `months` uses calendar-month buckets, including partial April buckets at both ends of the tax year. Category summary share is the effective default; `has_mixed_shares` signals per-record overrides. R04 non-deductible total includes private portions; R06 lists fully nonclaimed records and its grouped totals reconcile.

Business-use policies support prospective defaults and reasoned corrections to inherited defaults in a selected open tax year. Explicit shares stay authoritative. Queued, uncertain or accepted MTD periods reject retrospective ledger changes; no unsupported filed-period correction is implied.

Tax rules support 2025–26 and 2026–27 for England/Wales/NI and Scotland. Estimates combine trade profit, PAYE tax paid, supplied taxable property profit, savings bands/allowances, Class 4 and declared Marriage Allowance. A single student-loan plan is supported for verified 2026–27 thresholds, with supplied payroll repayments. Estimates disclose rounding, working-age assumptions, omitted pension/Gift Aid/loss/capital reliefs and PAYE/NI annual-maximum limitations. They are not assessments or a complete tax return. Forecasts show observation/scaling assumptions and project mileage bands separately. Trading-allowance comparison requires an explicit eligibility declaration and never combines allowance with expense/mileage deductions.

`PUT /tax/prior-assessment?tax_year=2026-27` supplies prior assessed liability, tax outside SA, advances and adjustments; without these T04 returns unknown amounts rather than UI fixtures. Payments-on-account guidance includes the outside-SA exception. Tax-pot entries record reported savings only, with exact reversals and no bank transfer.

In-app notifications have per-item and bulk read state. The worker schedules weekly/deadline feed reminders from preferences, with deduplication. Push delivery, after-shift sensing and device calendar writes require client/provider integration; neither is reported as completed by the backend.

Exports are immutable confirmed-book snapshots with separate labelled derived mileage deductions. E01 queues CSV/PDF generation; poll E02, then authenticated E03-download before expiry. Photo inclusion produces a ZIP and requires clean owner-owned attachments. CSV descriptions are protected from spreadsheet formula injection. Basic PDFs contain an accounting table; no richly formatted accountant template is claimed.

Subscription catalogs start empty until approved offers/terms are configured. Trials use server dates and cannot repeat. Expired trials return `status:"trial_expired"` with no entitlements; this adds an explicit state to the proposed status enum. Entitlements and optional configured feature gates are server-enforced; verified provider events control paid states. Accountant requests require a configured verified recipient and explicit consent; `requested`/`delivered:false` is not a sent email or a filed return.

HMRC authorization, obligations, previews and durable per-business update outcomes are implemented as disabled provider boundaries. A real adapter, encrypted connection, verified obligations, qualifying context, recognition, fraud headers and integration worker are required. Accepted acknowledgement is stored only from an actual adapter result with a provider reference. Timeout/crash outcomes remain uncertain, never automatically resent. Fetch the update version and use `/mtd/updates/{id}/reconciliation` with `expected_version` and an idempotency key for a configured provider status query; this never resubmits the original send. Partial outcomes remain per-business. Assistant conversations require opt-in, owner-validated transaction context IDs and consent; only selected amounts/dates/IDs enter provider context, without descriptions or tax identifiers. Unavailable providers fail explicitly and have no ledger-write tools. B02 returns a user/assistant message pair; B03 pages those atomic pairs (Page<MessagePair>), deliberately differing from the proposed flat Page<Message> so a failed completion stays attached to its user action. Each message carries status/timestamp and validated HTTPS source references.

## Screen mapping

The complete 58-screen source mapping is [frontend_analysis/10_FLUTTER_BACKEND_MAPPING.md](frontend_analysis/10_FLUTTER_BACKEND_MAPPING.md). Resolve every operation ID through the actual contract inventory; do not copy proposed paths verbatim. Practical groups:

| Frontend screens | Backend IDs / integration |
| --- | --- |
| Welcome/language/create/code/sign-in/security (S01–S07) | A01–A07, P01, F01; native security/token storage separately |
| Driving/platforms/PAYE/tax/vehicle/claim/earnings/trial/reminders (S08–S17) | P01–P07, I01–I02, V01–V06, D01–D04, S01–S03 |
| Shell/Home/week/year/check/Bolt/dates/notifications (S18–S25) | A06, R01–R03, C02–C06, Q01–Q04, N01–N04, T04 |
| Money/list/income/expense/manual forms (S26–S29, S33–S34) | L01–L06, R01/R04, receipt detail; route by actual UUID |
| Camera/read/review/receipt grid (S30–S32, S42) | C01–C08; genuine native file acquisition and job polling |
| Statement upload/result/platform check (S35–S37) | D01–D05, Q01–Q04; supported CSV workflow, native PDF dependency |
| Categories/work share/personal (S38–S41) | R04–R07, L01 |
| Export (S43) | E01–E03, H01–H02, S02 |
| Tax/workings/allowance/NI/forecast/POA/timeline/pot (S44–S52) | T01–T05, K01–K03, N04, P06/P07 |
| Car/MTD/other tax/driver (S53–S58) | V02/V04, M01–M04, U01–U10, H01/H02, A06/S02 |

Missing forms remain frontend work: names/profile editing, manual mileage, complete PAYE/NI/loan/relief/prior-assessment inputs, vehicle replacement, import/refund corrections, recipient/consent, plan management and assistant conversations. Bind actual receipt edits and pass resource/mutation/version IDs. Replace all fixtures and timer-based successes. Clear owner-scoped caches on logout and invalidate all affected reports/queues after bookkeeping mutations.
