# Proposed backend API requirements

Analysis: 27 October 2026. **Every operation/schema below is PROPOSED, not an observed or verified backend contract.** No frontend request exists. Reconcile this catalog with the external backend OpenAPI before building. Counts are unique HTTP method + path pairs, including explicitly marked extensions for visible affordances whose complete screens do not exist.

## Contract conventions

Base prefix `/v1` is a proposal. UUID identifiers; ISO date `YYYY-MM-DD`; UTC RFC3339 timestamps; UK tax-year identifier `2026-27` on the wire (display 2026/27); timezone Europe/London for UK business dates/deadlines and DST. GBP money is integer pence with signedness by field, never localized strings/floats. Mileage is decimal string miles to 2 places, computed using Decimal; no binary float tax calculations. Version all rule sets and estimates.

Notation: `?` nullable; `=value` optional with default; `[]` list; fields without defaults required. `Patch<T>` means each writable create-field optional/omittable, but nullable only if T permits it; reject unknown fields, disallow edits to owner/IDs/server totals. Empty patch -> 422. `Page<T>` = {items:T[],next_cursor:str?,has_more:bool}; limit 1-100, default 50, opaque cursor; descending occurred_on,id for records, created_at,id for jobs. List filters inclusive from/to; validate from<=to; use owner and stable ordering in cursor. Reference lists are small bounded arrays, not paginated.

Successful GET/PATCH/PUT normally 200; POST resource 201; queued job/submission 202; DELETE/logout 204. OAuth callback returns a validated application redirect or JSON when appropriate; do not expose provider tokens. No browser redirect directly to arbitrary return_url. Every owner resource access is scoped using JWT subject, never a client-supplied owner ID. Return 404 for another user's record. References public; unauthenticated auth operations rate limited. Bearer access JWT for all other app endpoints. Provider/HMRC callbacks and billing webhook use verified callback/provider security, not app JWT.

Proposed normalized errors: `{error:{code:str,message:str,field_errors:{field:str,messages:str[]}[],request_id:uuid}}`. Standard 401 invalid/expired access, 403 missing permission/entitlement, 404 absent/not owned, 409 stale version/duplicate/invalid transition, 422 validation, 429 limit, 503 dependency unavailable. FastAPI default validation returns a different detail array: preserve the existing backend envelope if established or add a deliberate compatibility adapter; do not silently assume normalization. Network timeouts with unknown outcomes must be reconciled via idempotency and status reads.

Mutating financial/job operations require an Idempotency-Key header (UUID); bind to user+method+path+request digest, persist original result, reject key reuse with a different body (409). Responses include mutation_id for reversible bookkeeping; reverse that exact action with expected_version and reason. Return canonical updated data; clients invalidate summary/report/queue caches. No global remove-last undo. Use version/expected_version optimistic locking. API rate limits and upload limits are server config and published reference metadata, not fabricated frontend limits.

## Reusable wire schema dictionary (PROPOSED)

The endpoint catalog supplies additional per-operation fields and constraints. Shared nested schemas are expanded here so names are not empty placeholders.

| Schema | Typed fields / semantics |
| --- | --- |
| User | id:uuid, first_name:str?, last_name:str?, phone_masked:str?, email_masked:str?, locale:str, timezone:str, onboarding_complete:bool, preferences:Preferences, version:int, created_at:datetime |
| Preferences | reminder_after_shift:bool, reminder_weekly:bool, reminder_deadlines:bool, preferred_weekday:int?, locale:str, timezone:str; face_id/backup passcode are device settings and biometric/passcode secrets must never sync |
| Tokens | access_token:str, refresh_token:str, token_type:literal bearer, expires_in:int, user:User; conceptual contract only, never document real token values |
| Challenge | challenge_id:uuid, destination_masked:str, expires_at:datetime, resend_after_seconds:int; no OTP returned |
| Onboarding | current_step:int 1..9, completed_steps:int[], completed_at:datetime?, skipped_fields:str[], version:int; progress references actual saved entities |
| DriverProfile | primary_business_id:uuid, licence_type:private_hire/hackney, council_code:str, work_pattern:alongside_job/full_time, first_name:str?, last_name:str?, version:int |
| TaxProfile | tax_year:str, region:england_wales_ni/scotland, has_paye_job:bool, employments:Employment[], property_income_pence:int?, interest_pence:int?, student_loan_plan:str?, marriage_allowance_status:str?, utr_masked:str?, ni_masked:str?, identifiers_complete:bool, version:int |
| Employment | id:uuid?, employer_name:str, gross_annual_pay_pence:int>=0, tax_paid_pence:int>=0, tax_code:str?; amounts are actual inputs, not UI employer/salary fixtures |
| VehicleInput / Vehicle | registration:str, ownership:owned/rented/leased, licence_class:str, make:str?, model:str?, year:int?, colour:str?, fuel:str?, business_start_on:date; output adds id:uuid, claim_method:mileage/actual/unset, method_locked:bool, eligible_methods:str[], eligibility_reasons:str[], version:int |
| IncomeSource | id:uuid, code:str, name:str, kind:platform/operator/cash/other, active:bool; source selection does not authorize provider access |
| Category | id:uuid, code:str, label_key:str, allowed_kinds:str[], requires_vehicle:bool, eligibility_reason_codes:str[], default_business_use_percent:decimal-string, version:int |
| TransactionInput | kind:income/expense, amount_pence:int>0, currency:literal GBP, occurred_on:date, business_id:uuid, source_id:uuid?, category_id:uuid?, vehicle_id:uuid?, receipt_id:uuid?, payment_method:cash/card_bank/other, description:str?, no_receipt_reason:str?, business_use_percent:decimal-string 0..100=100; expense needs category, income needs source |
| Transaction | id:uuid plus input; review_status:draft/confirmed/reversed, claim_status:claimable/personal/excluded, deductible_pence:int>=0, eligibility_reason_codes:str[], import_origin_id:uuid?, version:int, created_at:datetime, mutation_id:uuid?; owner not writable |
| Payout | id:uuid, source_id:uuid, period_start:date, period_end:date, gross_pence:int, fee_pence:int, net_pence:int, adjustment_pence:int, trip_count:int?, statement_id:uuid?, transactions:Transaction[]; net reconciles gross-fee+adjustments |
| Receipt | id:uuid, processing_status:uploaded/queued/processing/ready/failed, review_status:pending/confirmed/reversed, claim_status:claimable/personal/excluded/unknown, merchant:str?, occurred_on:date?, amount_pence:int?, vat_pence:int?, currency:str?, suggested_category_id:uuid?, corrected_category_id:uuid?, business_use_percent:decimal-string?, deductible_pence:int?, confidence:decimal-string?, warnings:str[], transaction_id:uuid?, job_id:uuid?, version:int, retained_until:date?; raw extraction kept separately |
| Job | id:uuid, status:queued/processing/succeeded/failed, progress_percent:int?, resource_id:uuid?, error_code:str?, retryable:bool, created_at:datetime, finished_at:datetime? |
| Statement | id:uuid, source_id:uuid, processing_status:str, import_status:preview/imported/failed, period_start:date?, period_end:date?, payouts:Payout[], gross_pence:int?, fee_pence:int?, net_pence:int?, duplicate:bool, warnings:str[], job:Job, version:int |
| ReconciliationIssue | id:uuid, source_id:uuid, statement_id:uuid, business_id:uuid, period_start:date, period_end:date, statement_gross_pence:int, recorded_gross_pence:int, difference_pence:int, candidate_transactions:Transaction[], status:open/resolved, resolution_id:uuid?, version:int |
| MileageLog | id:uuid, business_id:uuid, vehicle_id:uuid, occurred_on:date, start_odometer:decimal-string?, end_odometer:decimal-string?, business_miles:decimal-string, private_miles:decimal-string?, purpose:str, version:int; never infer GPS data from this UI |
| Dashboard | tax_year:str, as_of:datetime, income_pence:int, deductible_expenses_pence:int, profit_pence:int, estimated_tax_pence:int, has_data:bool, pending_receipts:int, unresolved_issues:int, unread_notifications:int, week_total_pence:int, business_miles:decimal-string, mileage_threshold_remaining:decimal-string?, next_deadline:Deadline?, version:str |
| WeeklyReport | start_on:date,end_on:date,total_income_pence:int,business_miles:decimal-string,days:{date:date,income_pence:int?,business_miles:decimal-string,is_future:bool}[],sources:{source_id:uuid,label:str,amount_pence:int}[],previous_week_total_pence:int; percentages derived or supplied with zero-total policy |
| AnnualReport | tax_year:str,as_of:datetime,income_pence:int,expenses_pence:int,profit_pence:int,months:{month:str,income_pence:int}[],sources:{source_id:uuid,amount_pence:int}[],categories:CategorySummary[],tax_estimate:TaxEstimate |
| CategorySummary | category_id:uuid,label:str,total_pence:int,deductible_pence:int,business_use_percent:decimal-string,count:int,pending_count:int; detail adds policy:BusinessUsePolicy and Page<Transaction> |
| BusinessUsePolicy | category_id:uuid,percent:decimal-string 0..100,effective_from:date,apply_to:future_only/selected_open_period,reason:str?,version:int; locked/filed periods reject retrospective edits |
| TaxEstimate | id:uuid,tax_year:str,as_of:datetime,rule_set_id:uuid,profile_version:int,ledger_version:str,income_pence:int,expense_deduction_pence:int,profit_pence:int,personal_allowance_pence:int,allowance_used_elsewhere_pence:int,income_tax_pence:int,class4_pence:int,total_pence:int,bands:{label:str,base_pence:int,rate:decimal-string,tax_pence:int}[],warnings:str[],assumptions:str[],estimate_only:bool |
| Forecast | estimate:TaxEstimate,observed_days:int,projected_days:int,projected_income_pence:int,projected_miles:decimal-string,projected_mileage_deduction_pence:int,projected_other_expenses_pence:int,threshold_date:date?,weekly_saving_pence:int,scenario:str,assumptions:str[] |
| Deadline / PaymentTimeline | Deadline={id:str,label_key:str,due_on:date,tax_year:str,type:str,estimated:bool,amount_pence:int?}; PaymentTimeline={items:Deadline[],prior_year_liability_pence:int,advance_payments_pence:int,adjustments_pence:int,warnings:str[]} |
| PotEntry / PotSummary | entry={id:uuid,amount_pence:int>0,occurred_on:date,note:str?,reversal_of:uuid?,version:int,mutation_id:uuid}; summary={balance_pence:int,target_pence:int,gap_pence:int,entries:Page<PotEntry>}; logging savings only |
| Notification | id:uuid,type:str,title_key:str,body_key:str,params:object,resource_type:str?,resource_id:uuid?,created_at:datetime,read_at:datetime?; server resource IDs mapped to known routes on client |
| ExportJob | id:uuid,tax_year:str,format:pdf/csv,include_photos:bool,status:str,job:Job,expires_at:datetime?,download_ready:bool; signed download generated on demand, not permanent public URL |
| AccountantRequest | id:uuid,export_id:uuid?,kind:books_handoff/marriage_allowance/filing_question,message:str?,consent_version:str,status:requested/accepted/completed/cancelled,created_at:datetime; no assumed TaxAssist integration |
| Plan / Subscription | plan={id:uuid,code:str,price_pence:int,currency:GBP,interval:month,trial_days:int,cohort_label:str,terms_version:str}; subscription={id:uuid,plan:Plan,status:trialing/active/past_due/cancelled,trial_start:datetime?,trial_end:datetime?,price_locked_pence:int?,renew_at:datetime?,entitlements:str[]} |
| MtdEligibility | status:eligible/not_required/unknown/exempt,qualifying_tax_year:str,qualifying_income_pence:int?,start_on:date?,reasons:str[],rule_set_id:uuid,connection_status:disconnected/connected/expired,recognition_enabled:bool |
| MtdBusiness / Obligation | business={id:uuid,type:self_employment/uk_property,name:str,provider_business_id_masked:str?}; obligation={id:str,business_id:uuid,period_start:date,period_end:date,due_on:date,status:open/fulfilled,received_on:date?,update_id:uuid?} |
| MtdPreview / MtdUpdate | preview={id:uuid,obligation_ids:str[],businesses:{business_id:uuid,quarter_income_pence:int,quarter_expenses_pence:int,ytd_income_pence:int,ytd_expenses_pence:int}[],snapshot_hash:str,ledger_version:str,warnings:str[],can_submit:bool}; update={id:uuid,preview_id:uuid,status:queued/submitting/accepted/rejected/partial/unknown,submitted_at:datetime?,accepted_at:datetime?,provider_reference_masked:str?,errors:{code:str,message:str}[],confirmation_available:bool} |
| Conversation / Message | conversation={id:uuid,locale:str,created_at:datetime}; message={id:uuid,conversation_id:uuid,role:user/assistant,content:str,created_at:datetime,sources:{title:str,url:str}[],status:complete/failed}; never give assistant implicit ledger-write rights |

## Framework compatibility (requirements, not implementation)

Use Pydantic v2 request/output models, explicit field constraints and `model_config=ConfigDict(from_attributes=True)` for ORM-backed output; partial updates distinguish omitted fields via model_dump(exclude_unset=True). Do not serialize secrets/ORM relationships accidentally. This follows the [Pydantic model documentation](https://docs.pydantic.dev/latest/concepts/models/).

Use SQLAlchemy 2 typed mappings/select queries, one session per request/task and transaction boundaries around confirmation/import/resolution/reversal. Never share one AsyncSession between concurrent jobs. See [SQLAlchemy 2 session documentation](https://docs.sqlalchemy.org/en/20/orm/session_basics.html). Supply sessions using a yield dependency with cleanup, following [FastAPI dependency documentation](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/). Pin compatible actual backend versions after inspecting its lock/config; no migration to SQLAlchemy 2.1 is required here.

Alembic owns proposed schema changes. PostgreSQL BIGINT pence, NUMERIC percentages/miles, UUID IDs, DATE business days, TIMESTAMPTZ instants, indexed owner IDs and constraints. Document 08 details tables. Docker Compose should isolate app/database/worker and persist DB/private file volumes; secrets come from server environment/secret management. Existing Compose/backend wiring remains unverified. No deployment files are created in this task.

## Operation catalog

Each entry specifies module/screens, action/method/path, request/response, auth, validation/logic, tables, errors, external dependencies and priority. Shared conventions above apply to every entry. Scope EXTENSION means a visible affordance/claim exists but a full screen or integration is absent; it is not part of the MVP unless explicitly prioritized.

### A01 - POST /v1/auth/challenges

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Identity: CreateAccountView, CodeView, SignInView |
| User action / scope / priority | Request SMS code; SCREEN; P0 |
| Request schema | `{phone:str,purpose:sign_up/sign_in}` |
| Response schema | `Challenge` |
| Authentication | No access JWT; verified challenge/provider/refresh credential and strict rate limits |
| Validation / business logic | Normalize UK phone to E.164; bind challenge to purpose/destination; expire/limit attempts; hash OTP and refresh tokens; verify OAuth issuer/audience/nonce; no client-generated identity. Shared conventions and schema constraints apply. |
| Database entities | users, auth_challenges, auth_sessions, provider_identities |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | SMS provider / Apple or Google for provider login; no biometric server API |

### A02 - POST /v1/auth/challenges/{id}/verify

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Identity: CreateAccountView, CodeView, SignInView |
| User action / scope / priority | Verify and create/restore authenticated account according to challenge purpose; SCREEN; P0 |
| Request schema | `{code:str exactly 6 digits}` |
| Response schema | `Tokens` |
| Authentication | No access JWT; verified challenge/provider/refresh credential and strict rate limits |
| Validation / business logic | Normalize UK phone to E.164; bind challenge to purpose/destination; expire/limit attempts; hash OTP and refresh tokens; verify OAuth issuer/audience/nonce; no client-generated identity. Shared conventions and schema constraints apply. |
| Database entities | users, auth_challenges, auth_sessions, provider_identities |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | SMS provider / Apple or Google for provider login; no biometric server API |

### A03 - POST /v1/auth/providers/{provider}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Identity: CreateAccountView, CodeView, SignInView |
| User action / scope / priority | Exchange verified Apple/Google identity, provider enum apple/google; SCREEN; P1 |
| Request schema | `{identity_token:str,nonce:str}` |
| Response schema | `Tokens` |
| Authentication | No access JWT; verified challenge/provider/refresh credential and strict rate limits |
| Validation / business logic | Normalize UK phone to E.164; bind challenge to purpose/destination; expire/limit attempts; hash OTP and refresh tokens; verify OAuth issuer/audience/nonce; no client-generated identity. Shared conventions and schema constraints apply. |
| Database entities | users, auth_challenges, auth_sessions, provider_identities |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | SMS provider / Apple or Google for provider login; no biometric server API |

### A04 - POST /v1/auth/refresh

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Identity: CreateAccountView, CodeView, SignInView |
| User action / scope / priority | Rotate refresh token, revoke reused session family; FOUNDATION; P0 |
| Request schema | `{refresh_token:str}` |
| Response schema | `Tokens` |
| Authentication | No access JWT; verified challenge/provider/refresh credential and strict rate limits |
| Validation / business logic | Normalize UK phone to E.164; bind challenge to purpose/destination; expire/limit attempts; hash OTP and refresh tokens; verify OAuth issuer/audience/nonce; no client-generated identity. Shared conventions and schema constraints apply. |
| Database entities | users, auth_challenges, auth_sessions, provider_identities |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | SMS provider / Apple or Google for provider login; no biometric server API |

### A05 - POST /v1/auth/logout

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Identity: CreateAccountView, CodeView, SignInView |
| User action / scope / priority | Revoke current session; clear client secure store later; FOUNDATION; P0 |
| Request schema | `{refresh_token:str?}` |
| Response schema | `No content` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Normalize UK phone to E.164; bind challenge to purpose/destination; expire/limit attempts; hash OTP and refresh tokens; verify OAuth issuer/audience/nonce; no client-generated identity. Shared conventions and schema constraints apply. |
| Database entities | users, auth_challenges, auth_sessions, provider_identities |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | SMS provider / Apple or Google for provider login; no biometric server API |

### A06 - GET /v1/me

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Identity: CreateAccountView, CodeView, SignInView |
| User action / scope / priority | Restore authenticated identity/preferences; FOUNDATION; P0 |
| Request schema | `none` |
| Response schema | `User` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Normalize UK phone to E.164; bind challenge to purpose/destination; expire/limit attempts; hash OTP and refresh tokens; verify OAuth issuer/audience/nonce; no client-generated identity. Shared conventions and schema constraints apply. |
| Database entities | users, auth_challenges, auth_sessions, provider_identities |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | SMS provider / Apple or Google for provider login; no biometric server API |

### A07 - POST /v1/auth/challenges/{id}/resend

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Identity: CreateAccountView, CodeView, SignInView |
| User action / scope / priority | Resend with cooldown and invalidate prior code; SCREEN; P0 |
| Request schema | `none` |
| Response schema | `Challenge` |
| Authentication | No access JWT; verified challenge/provider/refresh credential and strict rate limits |
| Validation / business logic | Normalize UK phone to E.164; bind challenge to purpose/destination; expire/limit attempts; hash OTP and refresh tokens; verify OAuth issuer/audience/nonce; no client-generated identity. Shared conventions and schema constraints apply. |
| Database entities | users, auth_challenges, auth_sessions, provider_identities |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | SMS provider / Apple or Google for provider login; no biometric server API |

### P01 - PATCH /v1/me

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Profile/onboarding: LanguageView, SecureView, DrivingView, PlatformsView, OtherIncomeView, TaxDetailsView, RemindersView, DriverView |
| User action / scope / priority | Save user/language/reminder preferences; no biometric secrets; SCREEN; P0 |
| Request schema | `{first_name?:str,last_name?:str?,preferences?:Patch<Preferences>,expected_version:int}` |
| Response schema | `User` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate language/council/licence enums and profile dependencies; optional tax identifiers format-checked then encrypted/masked; completion must reflect saved profile, not force demo data. Shared conventions and schema constraints apply. |
| Database entities | users, businesses, driver_profiles, onboarding_progress, tax_profiles, employments |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None; device biometric/notification permission remains native |

### P02 - GET /v1/me/onboarding

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Profile/onboarding: LanguageView, SecureView, DrivingView, PlatformsView, OtherIncomeView, TaxDetailsView, RemindersView, DriverView |
| User action / scope / priority | Resume setup progress; SCREEN; P0 |
| Request schema | `none` |
| Response schema | `Onboarding` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate language/council/licence enums and profile dependencies; optional tax identifiers format-checked then encrypted/masked; completion must reflect saved profile, not force demo data. Shared conventions and schema constraints apply. |
| Database entities | users, businesses, driver_profiles, onboarding_progress, tax_profiles, employments |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None; device biometric/notification permission remains native |

### P03 - PATCH /v1/me/onboarding

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Profile/onboarding: LanguageView, SecureView, DrivingView, PlatformsView, OtherIncomeView, TaxDetailsView, RemindersView, DriverView |
| User action / scope / priority | Save progress/complete after required entities pass validation; SCREEN; P0 |
| Request schema | `{current_step?:int,completed_steps?:int[],skipped_fields?:str[],complete?:bool,expected_version:int}` |
| Response schema | `Onboarding` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate language/council/licence enums and profile dependencies; optional tax identifiers format-checked then encrypted/masked; completion must reflect saved profile, not force demo data. Shared conventions and schema constraints apply. |
| Database entities | users, businesses, driver_profiles, onboarding_progress, tax_profiles, employments |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None; device biometric/notification permission remains native |

### P04 - GET /v1/me/driver-profile

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Profile/onboarding: LanguageView, SecureView, DrivingView, PlatformsView, OtherIncomeView, TaxDetailsView, RemindersView, DriverView |
| User action / scope / priority | Read driver setup/hub; SCREEN; P0 |
| Request schema | `none` |
| Response schema | `DriverProfile` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate language/council/licence enums and profile dependencies; optional tax identifiers format-checked then encrypted/masked; completion must reflect saved profile, not force demo data. Shared conventions and schema constraints apply. |
| Database entities | users, businesses, driver_profiles, onboarding_progress, tax_profiles, employments |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None; device biometric/notification permission remains native |

### P05 - PUT /v1/me/driver-profile

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Profile/onboarding: LanguageView, SecureView, DrivingView, PlatformsView, OtherIncomeView, TaxDetailsView, RemindersView, DriverView |
| User action / scope / priority | Save licence/council/work pattern and create/link default taxi business atomically; SCREEN; P0 |
| Request schema | `DriverProfile excluding server-managed primary_business_id/version plus expected_version:int?` |
| Response schema | `DriverProfile` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate language/council/licence enums and profile dependencies; optional tax identifiers format-checked then encrypted/masked; completion must reflect saved profile, not force demo data. Shared conventions and schema constraints apply. |
| Database entities | users, businesses, driver_profiles, onboarding_progress, tax_profiles, employments |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None; device biometric/notification permission remains native |

### P06 - GET /v1/me/tax-profile

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Profile/onboarding: LanguageView, SecureView, DrivingView, PlatformsView, OtherIncomeView, TaxDetailsView, RemindersView, DriverView |
| User action / scope / priority | Read year-specific PAYE/other-tax context, mask identifiers; SCREEN; P0 |
| Request schema | `query tax_year:str` |
| Response schema | `TaxProfile` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate language/council/licence enums and profile dependencies; optional tax identifiers format-checked then encrypted/masked; completion must reflect saved profile, not force demo data. Shared conventions and schema constraints apply. |
| Database entities | users, businesses, driver_profiles, onboarding_progress, tax_profiles, employments |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None; device biometric/notification permission remains native |

### P07 - PUT /v1/me/tax-profile

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Profile/onboarding: LanguageView, SecureView, DrivingView, PlatformsView, OtherIncomeView, TaxDetailsView, RemindersView, DriverView |
| User action / scope / priority | Save optional identifiers and tax inputs; never echo raw identifiers; SCREEN; P0 |
| Request schema | `{tax_year:str,region:str,has_paye_job:bool,employments:Employment[],property_income_pence:int?,interest_pence:int?,student_loan_plan:str?,marriage_allowance_status:str?,utr:str?,ni_number:str?,expected_version:int?}` |
| Response schema | `TaxProfile` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate language/council/licence enums and profile dependencies; optional tax identifiers format-checked then encrypted/masked; completion must reflect saved profile, not force demo data. Shared conventions and schema constraints apply. |
| Database entities | users, businesses, driver_profiles, onboarding_progress, tax_profiles, employments |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None; device biometric/notification permission remains native |

### F01 - GET /v1/reference-data

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Reference/configuration: LanguageView, DrivingView, PlatformsView, AddExpenseView, AllMoneyView |
| User action / scope / priority | Load dropdown/choice catalogs; SCREEN; P0 |
| Request schema | `query locale:str=en` |
| Response schema | `{version:str,languages:{code:str,native:str,english:str,rtl:bool}[],councils:{code:str,name:str}[],licence_types:str[],sources:IncomeSource[],categories:Category[],upload_limits:{max_bytes:int,mime_types:str[]}}` |
| Authentication | Public reference data; no personal values |
| Validation / business logic | Version reference data, serve stable codes not display indices; publish upload limits and allowed formats; use cache validators. Shared conventions and schema constraints apply. |
| Database entities | categories, tax_rule_sets; static locale/council/source catalogs |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None |

### V01 - POST /v1/vehicles/lookup

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Vehicle: VehicleView, ClaimMethodView, LockInSheet, CarView, DriverView |
| User action / scope / priority | Look up plate without silently creating vehicle; SCREEN; P1 |
| Request schema | `{registration:str}` |
| Response schema | `{registration:str,make:str?,model:str?,year:int?,colour:str?,fuel:str?,lookup_status:found/not_found/unavailable}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Normalize registration; enforce ownership/licence/vehicle-class and prior-claim eligibility before method election; lock only under verified rule; reject incompatible or stale changes. Shared conventions and schema constraints apply. |
| Database entities | vehicles, vehicle_claim_elections, mileage_logs |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Licensed vehicle lookup provider; manual fallback required |

### V02 - GET /v1/vehicles

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Vehicle: VehicleView, ClaimMethodView, LockInSheet, CarView, DriverView |
| User action / scope / priority | Load driver vehicles; SCREEN; P0 |
| Request schema | `query active:bool=true,limit:int=50,cursor:str?` |
| Response schema | `Page<Vehicle>` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Normalize registration; enforce ownership/licence/vehicle-class and prior-claim eligibility before method election; lock only under verified rule; reject incompatible or stale changes. Shared conventions and schema constraints apply. |
| Database entities | vehicles, vehicle_claim_elections, mileage_logs |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Licensed vehicle lookup provider; manual fallback required |

### V03 - POST /v1/vehicles

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Vehicle: VehicleView, ClaimMethodView, LockInSheet, CarView, DriverView |
| User action / scope / priority | Confirm/add owned/rented/leased vehicle; SCREEN; P0 |
| Request schema | `VehicleInput` |
| Response schema | `Vehicle` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Normalize registration; enforce ownership/licence/vehicle-class and prior-claim eligibility before method election; lock only under verified rule; reject incompatible or stale changes. Shared conventions and schema constraints apply. |
| Database entities | vehicles, vehicle_claim_elections, mileage_logs |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Licensed vehicle lookup provider; manual fallback required |

### V04 - GET /v1/vehicles/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Vehicle: VehicleView, ClaimMethodView, LockInSheet, CarView, DriverView |
| User action / scope / priority | Read car and claim/mileage totals; SCREEN; P0 |
| Request schema | `none` |
| Response schema | `Vehicle plus {tax_year:str,business_miles:decimal-string,deduction_pence:int,rule_set_id:uuid}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Normalize registration; enforce ownership/licence/vehicle-class and prior-claim eligibility before method election; lock only under verified rule; reject incompatible or stale changes. Shared conventions and schema constraints apply. |
| Database entities | vehicles, vehicle_claim_elections, mileage_logs |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Licensed vehicle lookup provider; manual fallback required |

### V05 - POST /v1/vehicles/{id}/claim-method

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Vehicle: VehicleView, ClaimMethodView, LockInSheet, CarView, DriverView |
| User action / scope / priority | Hold-to-lock election after eligibility checks; SCREEN; P0 |
| Request schema | `{method:mileage/actual,effective_from:date,prior_capital_allowances:bool,prior_vehicle_expense_claim:bool,acknowledgement_version:str,expected_version:int}` |
| Response schema | `Vehicle plus {election_id:uuid,mutation_id:uuid}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Normalize registration; enforce ownership/licence/vehicle-class and prior-claim eligibility before method election; lock only under verified rule; reject incompatible or stale changes. Shared conventions and schema constraints apply. |
| Database entities | vehicles, vehicle_claim_elections, mileage_logs |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Licensed vehicle lookup provider; manual fallback required |

### V06 - PATCH /v1/vehicles/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Vehicle: VehicleView, ClaimMethodView, LockInSheet, CarView, DriverView |
| User action / scope / priority | Correct vehicle facts; cannot bypass locked method; EXTENSION; P1 |
| Request schema | `Patch<VehicleInput> plus expected_version:int` |
| Response schema | `Vehicle` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Normalize registration; enforce ownership/licence/vehicle-class and prior-claim eligibility before method election; lock only under verified rule; reject incompatible or stale changes. Shared conventions and schema constraints apply. |
| Database entities | vehicles, vehicle_claim_elections, mileage_logs |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Licensed vehicle lookup provider; manual fallback required |

### I01 - GET /v1/me/income-sources

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Income sources: PlatformsView, AddFareView, PlatformCheckView |
| User action / scope / priority | Load selected work sources; SCREEN; P0 |
| Request schema | `none` |
| Response schema | `IncomeSource[]` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Deduplicate stable source IDs; require ownership for custom source; deactivate rather than erase history. Shared conventions and schema constraints apply. |
| Database entities | income_sources, driver_platforms |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None; selecting Uber/Bolt is not OAuth |

### I02 - PUT /v1/me/income-sources

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Income sources: PlatformsView, AddFareView, PlatformCheckView |
| User action / scope / priority | Save multi-selection including empty set; SCREEN; P0 |
| Request schema | `{source_ids:uuid[]}` |
| Response schema | `IncomeSource[]` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Deduplicate stable source IDs; require ownership for custom source; deactivate rather than erase history. Shared conventions and schema constraints apply. |
| Database entities | income_sources, driver_platforms |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None; selecting Uber/Bolt is not OAuth |

### L01 - GET /v1/transactions

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Ledger: AddFareView, AddExpenseView, AllMoneyView, MoneyView, IncomeView, ExpenseView |
| User action / scope / priority | Search/filter money list, all active filter dimensions applied; SCREEN; P0 |
| Request schema | `query tax_year?:str,from?:date,to?:date,kind?:income/expense,review_status?:str,claim_status?:str,source_ids?:uuid[],category_ids?:uuid[],q?:str,limit:int=50,cursor:str?` |
| Response schema | `Page<Transaction>` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate kind/source/category/date/positive GBP amount; derive claim on server, exclude draft/personal/reversed as appropriate; enforce vehicle policy; every write updates consistent aggregate version. Deletion means auditable void for confirmed/imported data, not silent erasure. Shared conventions and schema constraints apply. |
| Database entities | businesses, transactions, categories, income_sources, receipts, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None |

### L02 - POST /v1/transactions

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Ledger: AddFareView, AddExpenseView, AllMoneyView, MoneyView, IncomeView, ExpenseView |
| User action / scope / priority | Create fare/expense/personal record from captured form; SCREEN; P0 |
| Request schema | `TransactionInput` |
| Response schema | `Transaction` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate kind/source/category/date/positive GBP amount; derive claim on server, exclude draft/personal/reversed as appropriate; enforce vehicle policy; every write updates consistent aggregate version. Deletion means auditable void for confirmed/imported data, not silent erasure. Shared conventions and schema constraints apply. |
| Database entities | businesses, transactions, categories, income_sources, receipts, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None |

### L03 - GET /v1/transactions/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Ledger: AddFareView, AddExpenseView, AllMoneyView, MoneyView, IncomeView, ExpenseView |
| User action / scope / priority | Read actual income/expense detail by ID; SCREEN; P0 |
| Request schema | `none` |
| Response schema | `Transaction plus {payout:Payout?,receipt:Receipt?}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate kind/source/category/date/positive GBP amount; derive claim on server, exclude draft/personal/reversed as appropriate; enforce vehicle policy; every write updates consistent aggregate version. Deletion means auditable void for confirmed/imported data, not silent erasure. Shared conventions and schema constraints apply. |
| Database entities | businesses, transactions, categories, income_sources, receipts, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None |

### L04 - PATCH /v1/transactions/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Ledger: AddFareView, AddExpenseView, AllMoneyView, MoneyView, IncomeView, ExpenseView |
| User action / scope / priority | Correct editable transaction and recompute deduction; FOUNDATION; P0 |
| Request schema | `Patch<TransactionInput> plus expected_version:int` |
| Response schema | `Transaction` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate kind/source/category/date/positive GBP amount; derive claim on server, exclude draft/personal/reversed as appropriate; enforce vehicle policy; every write updates consistent aggregate version. Deletion means auditable void for confirmed/imported data, not silent erasure. Shared conventions and schema constraints apply. |
| Database entities | businesses, transactions, categories, income_sources, receipts, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None |

### L05 - DELETE /v1/transactions/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Ledger: AddFareView, AddExpenseView, AllMoneyView, MoneyView, IncomeView, ExpenseView |
| User action / scope / priority | Void record respecting closed-period policy; FOUNDATION; P0 |
| Request schema | `query expected_version:int,reason:str` |
| Response schema | `No content` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate kind/source/category/date/positive GBP amount; derive claim on server, exclude draft/personal/reversed as appropriate; enforce vehicle policy; every write updates consistent aggregate version. Deletion means auditable void for confirmed/imported data, not silent erasure. Shared conventions and schema constraints apply. |
| Database entities | businesses, transactions, categories, income_sources, receipts, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None |

### L06 - POST /v1/transactions/{id}/reversals

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Ledger: AddFareView, AddExpenseView, AllMoneyView, MoneyView, IncomeView, ExpenseView |
| User action / scope / priority | Reverse identified mutation, not globally last item; FOUNDATION; P0 |
| Request schema | `{mutation_id:uuid,reason:str,expected_version:int}` |
| Response schema | `Transaction` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate kind/source/category/date/positive GBP amount; derive claim on server, exclude draft/personal/reversed as appropriate; enforce vehicle policy; every write updates consistent aggregate version. Deletion means auditable void for confirmed/imported data, not silent erasure. Shared conventions and schema constraints apply. |
| Database entities | businesses, transactions, categories, income_sources, receipts, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | None |

### R01 - GET /v1/dashboard

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Reporting/category policy: HomeView, WeekView, YearView, MoneyView, CategoriesView, CategoryView, PersonalView, BusinessUseView |
| User action / scope / priority | Load shared Home/Money overview; SCREEN; P0 |
| Request schema | `query tax_year:str` |
| Response schema | `Dashboard` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | All report totals derive from the same confirmed ledger snapshot; stable date boundaries; amount sums reconcile; no persisted chart heights; default percent changes need explicit effective date and locked-period rules. Shared conventions and schema constraints apply. |
| Database entities | transactions, mileage_logs, business_use_policies, categories, tax_rule_sets |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Tax calculation service, internal |

### R02 - GET /v1/reports/weekly

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Reporting/category policy: HomeView, WeekView, YearView, MoneyView, CategoriesView, CategoryView, PersonalView, BusinessUseView |
| User action / scope / priority | Load arbitrary calendar week and comparison; SCREEN; P0 |
| Request schema | `query start_on:date,business_id:uuid?` |
| Response schema | `WeeklyReport` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | All report totals derive from the same confirmed ledger snapshot; stable date boundaries; amount sums reconcile; no persisted chart heights; default percent changes need explicit effective date and locked-period rules. Shared conventions and schema constraints apply. |
| Database entities | transactions, mileage_logs, business_use_policies, categories, tax_rule_sets |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Tax calculation service, internal |

### R03 - GET /v1/reports/annual

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Reporting/category policy: HomeView, WeekView, YearView, MoneyView, CategoriesView, CategoryView, PersonalView, BusinessUseView |
| User action / scope / priority | Load annual/money/category/tax aggregates; SCREEN; P1 |
| Request schema | `query tax_year:str` |
| Response schema | `AnnualReport` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | All report totals derive from the same confirmed ledger snapshot; stable date boundaries; amount sums reconcile; no persisted chart heights; default percent changes need explicit effective date and locked-period rules. Shared conventions and schema constraints apply. |
| Database entities | transactions, mileage_logs, business_use_policies, categories, tax_rule_sets |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Tax calculation service, internal |

### R04 - GET /v1/categories/summary

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Reporting/category policy: HomeView, WeekView, YearView, MoneyView, CategoriesView, CategoryView, PersonalView, BusinessUseView |
| User action / scope / priority | Load category totals including non-claim totals; SCREEN; P0 |
| Request schema | `query tax_year:str` |
| Response schema | `{items:CategorySummary[],total_deductible_pence:int,personal_total_pence:int}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | All report totals derive from the same confirmed ledger snapshot; stable date boundaries; amount sums reconcile; no persisted chart heights; default percent changes need explicit effective date and locked-period rules. Shared conventions and schema constraints apply. |
| Database entities | transactions, mileage_logs, business_use_policies, categories, tax_rule_sets |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Tax calculation service, internal |

### R05 - GET /v1/categories/{id}/transactions

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Reporting/category policy: HomeView, WeekView, YearView, MoneyView, CategoriesView, CategoryView, PersonalView, BusinessUseView |
| User action / scope / priority | Load selected category detail; SCREEN; P0 |
| Request schema | `query tax_year:str,limit:int=50,cursor:str?` |
| Response schema | `{summary:CategorySummary,policy:BusinessUsePolicy,transactions:Page<Transaction>}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | All report totals derive from the same confirmed ledger snapshot; stable date boundaries; amount sums reconcile; no persisted chart heights; default percent changes need explicit effective date and locked-period rules. Shared conventions and schema constraints apply. |
| Database entities | transactions, mileage_logs, business_use_policies, categories, tax_rule_sets |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Tax calculation service, internal |

### R06 - GET /v1/reports/personal

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Reporting/category policy: HomeView, WeekView, YearView, MoneyView, CategoriesView, CategoryView, PersonalView, BusinessUseView |
| User action / scope / priority | Read records excluded from deduction; SCREEN; P1 |
| Request schema | `query tax_year:str,limit:int=50,cursor:str?` |
| Response schema | `{total_pence:int,count:int,by_category:CategorySummary[],transactions:Page<Transaction>}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | All report totals derive from the same confirmed ledger snapshot; stable date boundaries; amount sums reconcile; no persisted chart heights; default percent changes need explicit effective date and locked-period rules. Shared conventions and schema constraints apply. |
| Database entities | transactions, mileage_logs, business_use_policies, categories, tax_rule_sets |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Tax calculation service, internal |

### R07 - PUT /v1/categories/{id}/business-use

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Reporting/category policy: HomeView, WeekView, YearView, MoneyView, CategoriesView, CategoryView, PersonalView, BusinessUseView |
| User action / scope / priority | Save effective-dated work share and explicit recalculation scope; SCREEN; P0 |
| Request schema | `BusinessUsePolicy with expected_version:int` |
| Response schema | `BusinessUsePolicy plus {affected_count:int,mutation_id:uuid}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | All report totals derive from the same confirmed ledger snapshot; stable date boundaries; amount sums reconcile; no persisted chart heights; default percent changes need explicit effective date and locked-period rules. Shared conventions and schema constraints apply. |
| Database entities | transactions, mileage_logs, business_use_policies, categories, tax_rule_sets |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Tax calculation service, internal |

### C01 - POST /v1/receipts

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Receipts/OCR: CameraView, ReadReceiptView, ReviewReceiptView, CheckView, ExpenseView, ReceiptsView, CheckSheet |
| User action / scope / priority | Upload actual receipt and queue OCR (202); SCREEN; P1 |
| Request schema | `multipart file:binary,business_id:uuid,vehicle_id:uuid?` |
| Response schema | `{receipt:Receipt,job:Job}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate MIME signature/size/hash; malware scan; tenant-private objects; preserve raw suggestion vs correction. Confirm personal records without a deduction; confirm/reverse idempotently using version; never count OCR draft before driver confirmation. Shared conventions and schema constraints apply. |
| Database entities | receipts, private_files, processing_jobs, receipt_extractions, transactions, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Private object storage; OCR provider/worker; native camera/gallery |

### C02 - GET /v1/receipts

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Receipts/OCR: CameraView, ReadReceiptView, ReviewReceiptView, CheckView, ExpenseView, ReceiptsView, CheckSheet |
| User action / scope / priority | Load true receipt grid/counts; SCREEN; P1 |
| Request schema | `query tax_year:str,review_status?:str,claim_status?:str,limit:int=50,cursor:str?` |
| Response schema | `{items:Receipt[],next_cursor:str?,has_more:bool,counts:{all:int,pending:int,counted:int,not_claimed:int}}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate MIME signature/size/hash; malware scan; tenant-private objects; preserve raw suggestion vs correction. Confirm personal records without a deduction; confirm/reverse idempotently using version; never count OCR draft before driver confirmation. Shared conventions and schema constraints apply. |
| Database entities | receipts, private_files, processing_jobs, receipt_extractions, transactions, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Private object storage; OCR provider/worker; native camera/gallery |

### C03 - GET /v1/receipts/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Receipts/OCR: CameraView, ReadReceiptView, ReviewReceiptView, CheckView, ExpenseView, ReceiptsView, CheckSheet |
| User action / scope / priority | Poll OCR and load receipt detail; SCREEN; P1 |
| Request schema | `none` |
| Response schema | `Receipt plus {job:Job?,extraction:{merchant:str?,occurred_on:date?,amount_pence:int?,vat_pence:int?,confidence:decimal-string?}?}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate MIME signature/size/hash; malware scan; tenant-private objects; preserve raw suggestion vs correction. Confirm personal records without a deduction; confirm/reverse idempotently using version; never count OCR draft before driver confirmation. Shared conventions and schema constraints apply. |
| Database entities | receipts, private_files, processing_jobs, receipt_extractions, transactions, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Private object storage; OCR provider/worker; native camera/gallery |

### C04 - PATCH /v1/receipts/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Receipts/OCR: CameraView, ReadReceiptView, ReviewReceiptView, CheckView, ExpenseView, ReceiptsView, CheckSheet |
| User action / scope / priority | Save actual reviewed fields/category/share; not yet confirmed; SCREEN; P1 |
| Request schema | `{merchant?:str,occurred_on?:date,amount_pence?:int,vat_pence?:int?,category_id?:uuid,business_use_percent?:decimal-string,claim_status?:str,expected_version:int}` |
| Response schema | `Receipt` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate MIME signature/size/hash; malware scan; tenant-private objects; preserve raw suggestion vs correction. Confirm personal records without a deduction; confirm/reverse idempotently using version; never count OCR draft before driver confirmation. Shared conventions and schema constraints apply. |
| Database entities | receipts, private_files, processing_jobs, receipt_extractions, transactions, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Private object storage; OCR provider/worker; native camera/gallery |

### C05 - POST /v1/receipts/{id}/confirmations

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Receipts/OCR: CameraView, ReadReceiptView, ReviewReceiptView, CheckView, ExpenseView, ReceiptsView, CheckSheet |
| User action / scope / priority | Confirm final reviewed snapshot and create one ledger record; SCREEN; P1 |
| Request schema | `{claim_status:claimable/personal/excluded,category_id:uuid,business_use_percent:decimal-string,expected_version:int}` |
| Response schema | `{receipt:Receipt,transaction:Transaction,mutation_id:uuid,dashboard:Dashboard}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate MIME signature/size/hash; malware scan; tenant-private objects; preserve raw suggestion vs correction. Confirm personal records without a deduction; confirm/reverse idempotently using version; never count OCR draft before driver confirmation. Shared conventions and schema constraints apply. |
| Database entities | receipts, private_files, processing_jobs, receipt_extractions, transactions, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Private object storage; OCR provider/worker; native camera/gallery |

### C06 - POST /v1/receipts/{id}/reversals

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Receipts/OCR: CameraView, ReadReceiptView, ReviewReceiptView, CheckView, ExpenseView, ReceiptsView, CheckSheet |
| User action / scope / priority | Undo exact confirmation atomically; SCREEN; P1 |
| Request schema | `{mutation_id:uuid,reason:str,expected_version:int}` |
| Response schema | `{receipt:Receipt,transaction:Transaction,dashboard:Dashboard}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate MIME signature/size/hash; malware scan; tenant-private objects; preserve raw suggestion vs correction. Confirm personal records without a deduction; confirm/reverse idempotently using version; never count OCR draft before driver confirmation. Shared conventions and schema constraints apply. |
| Database entities | receipts, private_files, processing_jobs, receipt_extractions, transactions, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Private object storage; OCR provider/worker; native camera/gallery |

### C07 - GET /v1/receipts/{id}/content

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Receipts/OCR: CameraView, ReadReceiptView, ReviewReceiptView, CheckView, ExpenseView, ReceiptsView, CheckSheet |
| User action / scope / priority | Open real private image/file; SCREEN; P1 |
| Request schema | `none` |
| Response schema | `Binary receipt image/PDF or short-lived authorized redirect` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate MIME signature/size/hash; malware scan; tenant-private objects; preserve raw suggestion vs correction. Confirm personal records without a deduction; confirm/reverse idempotently using version; never count OCR draft before driver confirmation. Shared conventions and schema constraints apply. |
| Database entities | receipts, private_files, processing_jobs, receipt_extractions, transactions, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Private object storage; OCR provider/worker; native camera/gallery |

### C08 - POST /v1/receipts/{id}/ocr-retries

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Receipts/OCR: CameraView, ReadReceiptView, ReviewReceiptView, CheckView, ExpenseView, ReceiptsView, CheckSheet |
| User action / scope / priority | Retry failed/retryable extraction without duplicate ledger entry; FOUNDATION; P1 |
| Request schema | `{expected_version:int}` |
| Response schema | `{receipt:Receipt,job:Job}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Validate MIME signature/size/hash; malware scan; tenant-private objects; preserve raw suggestion vs correction. Confirm personal records without a deduction; confirm/reverse idempotently using version; never count OCR draft before driver confirmation. Shared conventions and schema constraints apply. |
| Database entities | receipts, private_files, processing_jobs, receipt_extractions, transactions, audit_events |
| Errors | Standard errors above; 409 on stale/duplicate/invalid state, 422 on invalid fields; 503 for external dependency failure. Auth verification also returns generic invalid/expired challenge without revealing account existence. |
| External dependencies | Private object storage; OCR provider/worker; native camera/gallery |

### D01 - POST /v1/statements

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Statements/import: EarningsView, ReadingView, UploadView, StatementAddedView, IncomeView |
| User action / scope / priority | Upload selected PDF and queue parse (202); SCREEN; P1 |
| Request schema | `multipart file:binary,source_id:uuid,business_id:uuid` |
| Response schema | `{statement:Statement,job:Job}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Verify uploaded source/format/period and hashes; extraction yields preview, explicit import creates gross income plus separate fee expense exactly once; net is explanatory and never second income. Matching/overlap detection includes partial period imports. Shared conventions and schema constraints apply. |
| Database entities | statements, statement_payouts, private_files, processing_jobs, transactions, income_sources |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Private storage and format-specific PDF parser/worker |

### D02 - GET /v1/statements

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Statements/import: EarningsView, ReadingView, UploadView, StatementAddedView, IncomeView |
| User action / scope / priority | Load statement history; SCREEN; P1 |
| Request schema | `query tax_year:str,source_id?:uuid,limit:int=50,cursor:str?` |
| Response schema | `Page<Statement>` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Verify uploaded source/format/period and hashes; extraction yields preview, explicit import creates gross income plus separate fee expense exactly once; net is explanatory and never second income. Matching/overlap detection includes partial period imports. Shared conventions and schema constraints apply. |
| Database entities | statements, statement_payouts, private_files, processing_jobs, transactions, income_sources |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Private storage and format-specific PDF parser/worker |

### D03 - GET /v1/statements/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Statements/import: EarningsView, ReadingView, UploadView, StatementAddedView, IncomeView |
| User action / scope / priority | Poll import extraction/job and read gross/fees/net preview; SCREEN; P1 |
| Request schema | `none` |
| Response schema | `Statement` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Verify uploaded source/format/period and hashes; extraction yields preview, explicit import creates gross income plus separate fee expense exactly once; net is explanatory and never second income. Matching/overlap detection includes partial period imports. Shared conventions and schema constraints apply. |
| Database entities | statements, statement_payouts, private_files, processing_jobs, transactions, income_sources |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Private storage and format-specific PDF parser/worker |

### D04 - POST /v1/statements/{id}/imports

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Statements/import: EarningsView, ReadingView, UploadView, StatementAddedView, IncomeView |
| User action / scope / priority | Confirm deduplicated import; atomic or explicit queued job (202 if large); SCREEN; P1 |
| Request schema | `{expected_version:int,acknowledged_warning_codes:str[]}` |
| Response schema | `{statement:Statement,transaction_ids:uuid[],issues:ReconciliationIssue[],mutation_id:uuid}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Verify uploaded source/format/period and hashes; extraction yields preview, explicit import creates gross income plus separate fee expense exactly once; net is explanatory and never second income. Matching/overlap detection includes partial period imports. Shared conventions and schema constraints apply. |
| Database entities | statements, statement_payouts, private_files, processing_jobs, transactions, income_sources |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Private storage and format-specific PDF parser/worker |

### D05 - GET /v1/statements/{id}/content

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Statements/import: EarningsView, ReadingView, UploadView, StatementAddedView, IncomeView |
| User action / scope / priority | Open source statement; SCREEN; P1 |
| Request schema | `none` |
| Response schema | `Binary private PDF or short-lived authorized redirect` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Verify uploaded source/format/period and hashes; extraction yields preview, explicit import creates gross income plus separate fee expense exactly once; net is explanatory and never second income. Matching/overlap detection includes partial period imports. Shared conventions and schema constraints apply. |
| Database entities | statements, statement_payouts, private_files, processing_jobs, transactions, income_sources |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Private storage and format-specific PDF parser/worker |

### Q01 - GET /v1/reconciliations

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Reconciliation: PlatformCheckView, BoltView, StatementAddedView, CheckView |
| User action / scope / priority | Load platform summaries and review queue; SCREEN; P1 |
| Request schema | `query tax_year:str,source_id?:uuid,status?:str,limit:int=50,cursor:str?` |
| Response schema | `{items:ReconciliationIssue[],next_cursor:str?,has_more:bool,platform_totals:{source_id:uuid,statement_gross_pence:int,recorded_gross_pence:int,difference_pence:int}[]}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Compare like-for-like gross period totals and fee/net components separately. An equal total alone is not proof of correctness. Resolution either creates missing ledger rows or links existing ones with evidence; exact resolution reversal restores prior state and aggregates. Shared conventions and schema constraints apply. |
| Database entities | reconciliation_issues, reconciliation_resolutions, statements, statement_payouts, transactions, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Imported platform files, not assumed direct Uber/Bolt API |

### Q02 - GET /v1/reconciliations/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Reconciliation: PlatformCheckView, BoltView, StatementAddedView, CheckView |
| User action / scope / priority | Read week-level difference and candidate records; SCREEN; P1 |
| Request schema | `none` |
| Response schema | `ReconciliationIssue` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Compare like-for-like gross period totals and fee/net components separately. An equal total alone is not proof of correctness. Resolution either creates missing ledger rows or links existing ones with evidence; exact resolution reversal restores prior state and aggregates. Shared conventions and schema constraints apply. |
| Database entities | reconciliation_issues, reconciliation_resolutions, statements, statement_payouts, transactions, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Imported platform files, not assumed direct Uber/Bolt API |

### Q03 - POST /v1/reconciliations/{id}/resolutions

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Reconciliation: PlatformCheckView, BoltView, StatementAddedView, CheckView |
| User action / scope / priority | Add missing trip or record existing evidence without duplicate income; SCREEN; P1 |
| Request schema | `{mode:add_missing/link_existing,transaction_ids:uuid[]=[],new_transactions:TransactionInput[]=[],evidence_note:str?,expected_version:int}` |
| Response schema | `{issue:ReconciliationIssue,transaction_ids:uuid[],resolution_id:uuid,mutation_id:uuid,dashboard:Dashboard}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Compare like-for-like gross period totals and fee/net components separately. An equal total alone is not proof of correctness. Resolution either creates missing ledger rows or links existing ones with evidence; exact resolution reversal restores prior state and aggregates. Shared conventions and schema constraints apply. |
| Database entities | reconciliation_issues, reconciliation_resolutions, statements, statement_payouts, transactions, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Imported platform files, not assumed direct Uber/Bolt API |

### Q04 - POST /v1/reconciliations/{id}/reversals

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Reconciliation: PlatformCheckView, BoltView, StatementAddedView, CheckView |
| User action / scope / priority | Undo specified resolution and linked ledger mutation; SCREEN; P1 |
| Request schema | `{resolution_id:uuid,mutation_id:uuid,reason:str,expected_version:int}` |
| Response schema | `{issue:ReconciliationIssue,dashboard:Dashboard}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Compare like-for-like gross period totals and fee/net components separately. An equal total alone is not proof of correctness. Resolution either creates missing ledger rows or links existing ones with evidence; exact resolution reversal restores prior state and aggregates. Shared conventions and schema constraints apply. |
| Database entities | reconciliation_issues, reconciliation_resolutions, statements, statement_payouts, transactions, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Imported platform files, not assumed direct Uber/Bolt API |

### M01 - GET /v1/mileage-logs

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Mileage: AddSheet Log miles affordance; CarView, DriverView and report figures (log form absent) |
| User action / scope / priority | Load mileage evidence/summary; EXTENSION; P0 |
| Request schema | `query tax_year:str,vehicle_id?:uuid,limit:int=50,cursor:str?` |
| Response schema | `{items:MileageLog[],next_cursor:str?,has_more:bool,total_business_miles:decimal-string,deduction_pence:int,rule_set_id:uuid}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Require eligible active vehicle and dates; business miles nonnegative, odometers monotonic and totals consistent; split bands across tax-year mileage, avoid duplicate logs and preserve corrections. Client log form remains future work. Shared conventions and schema constraints apply. |
| Database entities | mileage_logs, vehicles, vehicle_claim_elections, tax_rule_sets |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | None for manual logging; GPS is not implied |

### M02 - POST /v1/mileage-logs

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Mileage: AddSheet Log miles affordance; CarView, DriverView and report figures (log form absent) |
| User action / scope / priority | Create validated manual shift/business mileage; EXTENSION; P0 |
| Request schema | `MileageLog excluding id/version` |
| Response schema | `MileageLog plus {deduction_pence:int,mutation_id:uuid}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Require eligible active vehicle and dates; business miles nonnegative, odometers monotonic and totals consistent; split bands across tax-year mileage, avoid duplicate logs and preserve corrections. Client log form remains future work. Shared conventions and schema constraints apply. |
| Database entities | mileage_logs, vehicles, vehicle_claim_elections, tax_rule_sets |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | None for manual logging; GPS is not implied |

### M03 - PATCH /v1/mileage-logs/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Mileage: AddSheet Log miles affordance; CarView, DriverView and report figures (log form absent) |
| User action / scope / priority | Correct mileage with downstream recalculation; EXTENSION; P0 |
| Request schema | `Patch<MileageLog> excluding id/version plus expected_version:int` |
| Response schema | `MileageLog` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Require eligible active vehicle and dates; business miles nonnegative, odometers monotonic and totals consistent; split bands across tax-year mileage, avoid duplicate logs and preserve corrections. Client log form remains future work. Shared conventions and schema constraints apply. |
| Database entities | mileage_logs, vehicles, vehicle_claim_elections, tax_rule_sets |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | None for manual logging; GPS is not implied |

### M04 - DELETE /v1/mileage-logs/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Mileage: AddSheet Log miles affordance; CarView, DriverView and report figures (log form absent) |
| User action / scope / priority | Void mileage evidence without bypassing locked periods; EXTENSION; P0 |
| Request schema | `query expected_version:int,reason:str` |
| Response schema | `No content` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Require eligible active vehicle and dates; business miles nonnegative, odometers monotonic and totals consistent; split bands across tax-year mileage, avoid duplicate logs and preserve corrections. Client log form remains future work. Shared conventions and schema constraints apply. |
| Database entities | mileage_logs, vehicles, vehicle_claim_elections, tax_rule_sets |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | None for manual logging; GPS is not implied |

### T01 - GET /v1/tax/estimate

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Tax engine: TaxView, WorkingsView, AllowanceView, Class4View, ForecastView, PoaView, TimelineView, TradingAllowanceView, OtherTaxView |
| User action / scope / priority | Load current estimate and allowance/NI breakdown; SCREEN; P0 |
| Request schema | `query tax_year:str,as_of?:date` |
| Response schema | `TaxEstimate` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Version rules by year/region/vehicle eligibility. Tax from combined user context, never globally 20%. Forecast mileage tier-by-tier and disclose inputs/as_of. Prior-year payments/eligibility must be real; estimates are not filed liability. Do not use visible fixtures as law. Shared conventions and schema constraints apply. |
| Database entities | tax_rule_sets, tax_profiles, employments, transactions, mileage_logs, tax_estimate_snapshots, tax_payments |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Verified HMRC guidance; accountant review; no HMRC filing from these read operations |

### T02 - GET /v1/tax/forecast

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Tax engine: TaxView, WorkingsView, AllowanceView, Class4View, ForecastView, PoaView, TimelineView, TradingAllowanceView, OtherTaxView |
| User action / scope / priority | Project year with explicit assumptions and mileage threshold crossing; SCREEN; P1 |
| Request schema | `query tax_year:str,scenario:str=current_pace` |
| Response schema | `Forecast` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Version rules by year/region/vehicle eligibility. Tax from combined user context, never globally 20%. Forecast mileage tier-by-tier and disclose inputs/as_of. Prior-year payments/eligibility must be real; estimates are not filed liability. Do not use visible fixtures as law. Shared conventions and schema constraints apply. |
| Database entities | tax_rule_sets, tax_profiles, employments, transactions, mileage_logs, tax_estimate_snapshots, tax_payments |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Verified HMRC guidance; accountant review; no HMRC filing from these read operations |

### T03 - GET /v1/tax/deduction-comparison

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Tax engine: TaxView, WorkingsView, AllowanceView, Class4View, ForecastView, PoaView, TimelineView, TradingAllowanceView, OtherTaxView |
| User action / scope / priority | Compare lawful expense/trading-allowance alternatives; SCREEN; P1 |
| Request schema | `query tax_year:str` |
| Response schema | `{expenses:TaxEstimate,trading_allowance:TaxEstimate,recommended_method:str,saving_pence:int,warnings:str[]}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Version rules by year/region/vehicle eligibility. Tax from combined user context, never globally 20%. Forecast mileage tier-by-tier and disclose inputs/as_of. Prior-year payments/eligibility must be real; estimates are not filed liability. Do not use visible fixtures as law. Shared conventions and schema constraints apply. |
| Database entities | tax_rule_sets, tax_profiles, employments, transactions, mileage_logs, tax_estimate_snapshots, tax_payments |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Verified HMRC guidance; accountant review; no HMRC filing from these read operations |

### T04 - GET /v1/tax/payment-timeline

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Tax engine: TaxView, WorkingsView, AllowanceView, Class4View, ForecastView, PoaView, TimelineView, TradingAllowanceView, OtherTaxView |
| User action / scope / priority | Calculate POA and balancing dates from real prior-year liability/payments; SCREEN; P1 |
| Request schema | `query tax_year:str` |
| Response schema | `PaymentTimeline` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Version rules by year/region/vehicle eligibility. Tax from combined user context, never globally 20%. Forecast mileage tier-by-tier and disclose inputs/as_of. Prior-year payments/eligibility must be real; estimates are not filed liability. Do not use visible fixtures as law. Shared conventions and schema constraints apply. |
| Database entities | tax_rule_sets, tax_profiles, employments, transactions, mileage_logs, tax_estimate_snapshots, tax_payments |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Verified HMRC guidance; accountant review; no HMRC filing from these read operations |

### T05 - GET /v1/tax/rules

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Tax engine: TaxView, WorkingsView, AllowanceView, Class4View, ForecastView, PoaView, TimelineView, TradingAllowanceView, OtherTaxView |
| User action / scope / priority | Read published versioned rules/explanations; SCREEN; P0 |
| Request schema | `query tax_year:str,region:str` |
| Response schema | `{id:uuid,tax_year:str,region:str,version:str,rules:{code:str,value:object,effective_from:date,effective_to:date?,official_url:str,verified_at:datetime}[]}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Version rules by year/region/vehicle eligibility. Tax from combined user context, never globally 20%. Forecast mileage tier-by-tier and disclose inputs/as_of. Prior-year payments/eligibility must be real; estimates are not filed liability. Do not use visible fixtures as law. Shared conventions and schema constraints apply. |
| Database entities | tax_rule_sets, tax_profiles, employments, transactions, mileage_logs, tax_estimate_snapshots, tax_payments |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Verified HMRC guidance; accountant review; no HMRC filing from these read operations |

### K01 - GET /v1/tax-pot

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Tax pot: PotView, TaxView |
| User action / scope / priority | Load savings log and current target; SCREEN; P0 |
| Request schema | `query tax_year:str,limit:int=50,cursor:str?` |
| Response schema | `PotSummary` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Only logs user-reported savings; derive balance from additions/reversals, target from current estimate. Reject zero/negative additions; reverse specific entry once; preserve initial balance provenance. Shared conventions and schema constraints apply. |
| Database entities | tax_pot_entries, tax_estimate_snapshots, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | None; not a payment/banking integration |

### K02 - POST /v1/tax-pot/entries

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Tax pot: PotView, TaxView |
| User action / scope / priority | Log money already moved externally; SCREEN; P0 |
| Request schema | `{amount_pence:int>0,occurred_on:date,note:str?}` |
| Response schema | `{entry:PotEntry,summary:PotSummary}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Only logs user-reported savings; derive balance from additions/reversals, target from current estimate. Reject zero/negative additions; reverse specific entry once; preserve initial balance provenance. Shared conventions and schema constraints apply. |
| Database entities | tax_pot_entries, tax_estimate_snapshots, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | None; not a payment/banking integration |

### K03 - POST /v1/tax-pot/entries/{id}/reversals

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Tax pot: PotView, TaxView |
| User action / scope / priority | Undo exact savings log entry; SCREEN; P0 |
| Request schema | `{mutation_id:uuid,expected_version:int,reason:str}` |
| Response schema | `{entry:PotEntry,summary:PotSummary}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Only logs user-reported savings; derive balance from additions/reversals, target from current estimate. Reject zero/negative additions; reverse specific entry once; preserve initial balance provenance. Shared conventions and schema constraints apply. |
| Database entities | tax_pot_entries, tax_estimate_snapshots, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | None; not a payment/banking integration |

### N01 - GET /v1/notifications

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Notifications/deadlines: NotificationsView, HomeView, RemindersView, DatesView |
| User action / scope / priority | Load feed/badge; SCREEN; P1 |
| Request schema | `query unread_only:bool=false,limit:int=50,cursor:str?` |
| Response schema | `{items:Notification[],next_cursor:str?,has_more:bool,unread_count:int}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Owner-scoped read timestamps, no arbitrary server routes; schedules use Europe/London and preferences. Calendar success only after device API succeeds; backend supplies dates, not fictitious device writes. Shared conventions and schema constraints apply. |
| Database entities | notifications, users.preferences, tax_rule_sets |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Optional notification delivery provider/worker and native permission/calendar adapter |

### N02 - PATCH /v1/notifications/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Notifications/deadlines: NotificationsView, HomeView, RemindersView, DatesView |
| User action / scope / priority | Mark selected notification read/unread; FOUNDATION; P1 |
| Request schema | `{read:bool}` |
| Response schema | `Notification` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Owner-scoped read timestamps, no arbitrary server routes; schedules use Europe/London and preferences. Calendar success only after device API succeeds; backend supplies dates, not fictitious device writes. Shared conventions and schema constraints apply. |
| Database entities | notifications, users.preferences, tax_rule_sets |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Optional notification delivery provider/worker and native permission/calendar adapter |

### N03 - POST /v1/notifications/read-all

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Notifications/deadlines: NotificationsView, HomeView, RemindersView, DatesView |
| User action / scope / priority | Mark currently seen notifications read without racing new arrivals; SCREEN; P1 |
| Request schema | `{through:datetime}` |
| Response schema | `{updated_count:int,unread_count:int}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Owner-scoped read timestamps, no arbitrary server routes; schedules use Europe/London and preferences. Calendar success only after device API succeeds; backend supplies dates, not fictitious device writes. Shared conventions and schema constraints apply. |
| Database entities | notifications, users.preferences, tax_rule_sets |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Optional notification delivery provider/worker and native permission/calendar adapter |

### N04 - GET /v1/deadlines

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Notifications/deadlines: NotificationsView, HomeView, RemindersView, DatesView |
| User action / scope / priority | Load authoritative deadlines; client can add to device calendar; SCREEN; P1 |
| Request schema | `query tax_year:str` |
| Response schema | `Deadline[]` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Owner-scoped read timestamps, no arbitrary server routes; schedules use Europe/London and preferences. Calendar success only after device API succeeds; backend supplies dates, not fictitious device writes. Shared conventions and schema constraints apply. |
| Database entities | notifications, users.preferences, tax_rule_sets |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Optional notification delivery provider/worker and native permission/calendar adapter |

### E01 - POST /v1/exports

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Exports: ExportView, DriverView, accountant handoff |
| User action / scope / priority | Queue export for selected options (202); SCREEN; P1 |
| Request schema | `{tax_year:str,format:pdf/csv,include_photos:bool}` |
| Response schema | `ExportJob` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Snapshot chosen tax year and confirmed books; include personal records explicitly labelled; CSV escaping/formula injection protection, photo package authorization, expiring files. Export does not submit a return. Shared conventions and schema constraints apply. |
| Database entities | export_jobs, private_files, processing_jobs, transactions, receipts |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | PDF/CSV renderer, private storage, native share/download adapter |

### E02 - GET /v1/exports/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Exports: ExportView, DriverView, accountant handoff |
| User action / scope / priority | Poll readiness/failure; SCREEN; P1 |
| Request schema | `none` |
| Response schema | `ExportJob` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Snapshot chosen tax year and confirmed books; include personal records explicitly labelled; CSV escaping/formula injection protection, photo package authorization, expiring files. Export does not submit a return. Shared conventions and schema constraints apply. |
| Database entities | export_jobs, private_files, processing_jobs, transactions, receipts |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | PDF/CSV renderer, private storage, native share/download adapter |

### E03 - GET /v1/exports/{id}/download

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Exports: ExportView, DriverView, accountant handoff |
| User action / scope / priority | Download generated books/photo package; SCREEN; P1 |
| Request schema | `none` |
| Response schema | `Binary PDF/CSV/ZIP or short-lived authorized redirect` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Snapshot chosen tax year and confirmed books; include personal records explicitly labelled; CSV escaping/formula injection protection, photo package authorization, expiring files. Export does not submit a return. Shared conventions and schema constraints apply. |
| Database entities | export_jobs, private_files, processing_jobs, transactions, receipts |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | PDF/CSV renderer, private storage, native share/download adapter |

### H01 - POST /v1/accountant-requests

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Accountant: ExportView share; OtherTaxView ask; marketing only (dedicated module absent) |
| User action / scope / priority | Create consented handoff/question request; EXTENSION; P2 |
| Request schema | `{kind:books_handoff/marriage_allowance/filing_question,export_id:uuid?,recipient_reference:str,message:str?,consent_version:str}` |
| Response schema | `AccountantRequest` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Require explicit recipient choice/consent and a ready export for books_handoff; do not auto-send to a brand named in marketing. Audit/revoke access; distinguish request creation from delivery/filing. Shared conventions and schema constraints apply. |
| Database entities | accountant_requests, export_jobs, consent_records, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Partner/accountant delivery integration not verified |

### H02 - GET /v1/accountant-requests/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Accountant: ExportView share; OtherTaxView ask; marketing only (dedicated module absent) |
| User action / scope / priority | Track request and actual delivery status; EXTENSION; P2 |
| Request schema | `none` |
| Response schema | `AccountantRequest` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Require explicit recipient choice/consent and a ready export for books_handoff; do not auto-send to a brand named in marketing. Audit/revoke access; distinguish request creation from delivery/filing. Shared conventions and schema constraints apply. |
| Database entities | accountant_requests, export_jobs, consent_records, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Partner/accountant delivery integration not verified |

### S01 - GET /v1/subscription-plans

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Subscription: TrialView; management/purchase screens absent |
| User action / scope / priority | Load actual offer/terms instead of fixed price/date; SCREEN; P1 |
| Request schema | `query locale:str=en` |
| Response schema | `Plan[]` |
| Authentication | Public plans only; current user eligibility determined on trial request |
| Validation / business logic | Server computes trial/cohort price from policy; prevent repeated trials; validate signed receipt/events; deduplicate webhook event IDs and enforce entitlement transitions. Lifetime pricing/tax/renewal terms need product approval. Shared conventions and schema constraints apply. |
| Database entities | subscription_plans, subscriptions, billing_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Billing provider or app-store billing chosen by product; not assumed Stripe |

### S02 - GET /v1/me/subscription

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Subscription: TrialView; management/purchase screens absent |
| User action / scope / priority | Read trial/paid entitlement; SCREEN; P1 |
| Request schema | `none` |
| Response schema | `Subscription or {status:none,entitlements:str[]}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server computes trial/cohort price from policy; prevent repeated trials; validate signed receipt/events; deduplicate webhook event IDs and enforce entitlement transitions. Lifetime pricing/tax/renewal terms need product approval. Shared conventions and schema constraints apply. |
| Database entities | subscription_plans, subscriptions, billing_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Billing provider or app-store billing chosen by product; not assumed Stripe |

### S03 - POST /v1/me/subscription/trial

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Subscription: TrialView; management/purchase screens absent |
| User action / scope / priority | Start one eligible trial with server dates; SCREEN; P1 |
| Request schema | `{plan_id:uuid,terms_version:str}` |
| Response schema | `Subscription` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server computes trial/cohort price from policy; prevent repeated trials; validate signed receipt/events; deduplicate webhook event IDs and enforce entitlement transitions. Lifetime pricing/tax/renewal terms need product approval. Shared conventions and schema constraints apply. |
| Database entities | subscription_plans, subscriptions, billing_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Billing provider or app-store billing chosen by product; not assumed Stripe |

### S04 - POST /v1/billing/webhooks/{provider}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Subscription: TrialView; management/purchase screens absent |
| User action / scope / priority | Process verified billing event idempotently; EXTENSION; P2 |
| Request schema | `Raw provider event plus signature headers; schema determined by selected provider` |
| Response schema | `{received:bool}` |
| Authentication | Verified provider signature and replay protection; no app JWT |
| Validation / business logic | Server computes trial/cohort price from policy; prevent repeated trials; validate signed receipt/events; deduplicate webhook event IDs and enforce entitlement transitions. Lifetime pricing/tax/renewal terms need product approval. Shared conventions and schema constraints apply. |
| Database entities | subscription_plans, subscriptions, billing_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Billing provider or app-store billing chosen by product; not assumed Stripe |

### S05 - POST /v1/me/subscription/checkout

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Subscription: TrialView; management/purchase screens absent |
| User action / scope / priority | Begin provider payment; native store alternative contract TBD; EXTENSION; P2 |
| Request schema | `{plan_id:uuid,return_route:allowlisted-client-route}` |
| Response schema | `{session_id:str,checkout_url:str?,expires_at:datetime?,provider:str}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server computes trial/cohort price from policy; prevent repeated trials; validate signed receipt/events; deduplicate webhook event IDs and enforce entitlement transitions. Lifetime pricing/tax/renewal terms need product approval. Shared conventions and schema constraints apply. |
| Database entities | subscription_plans, subscriptions, billing_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Billing provider or app-store billing chosen by product; not assumed Stripe |

### S06 - POST /v1/me/subscription/cancellation

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Subscription: TrialView; management/purchase screens absent |
| User action / scope / priority | Request cancellation under chosen billing provider policy; EXTENSION; P2 |
| Request schema | `{reason:str?}` |
| Response schema | `Subscription` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server computes trial/cohort price from policy; prevent repeated trials; validate signed receipt/events; deduplicate webhook event IDs and enforce entitlement transitions. Lifetime pricing/tax/renewal terms need product approval. Shared conventions and schema constraints apply. |
| Database entities | subscription_plans, subscriptions, billing_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Billing provider or app-store billing chosen by product; not assumed Stripe |

### U01 - GET /v1/mtd/eligibility

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | HMRC MTD: MtdView, MtdQuartersView, MtdSendView; actual connection UI absent |
| User action / scope / priority | Read eligibility/connection/recognition capability; SCREEN; P1 |
| Request schema | `query tax_year:str` |
| Response schema | `MtdEligibility` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server checks verified eligibility/exemptions and connection. Retrieve obligations/businesses; immutable validated preview has ledger version/hash. Send once per authorized snapshot; persist remote acknowledgement per business; timeouts unknown until reconciled. A combined taxi/property page may require distinct submissions and partial success handling. Shared conventions and schema constraints apply. |
| Database entities | hmrc_connections, businesses, mtd_obligations, mtd_previews, mtd_updates, mtd_update_businesses, private_files, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Recognized HMRC application, OAuth/scopes, sandbox/production API, secure token vault and fraud-prevention requirements |

### U02 - POST /v1/mtd/authorizations

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | HMRC MTD: MtdView, MtdQuartersView, MtdSendView; actual connection UI absent |
| User action / scope / priority | Begin HMRC consent with server nonce/state; EXTENSION; P2 |
| Request schema | `{return_route:allowlisted-client-route}` |
| Response schema | `{authorization_url:str,state_expires_at:datetime}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server checks verified eligibility/exemptions and connection. Retrieve obligations/businesses; immutable validated preview has ledger version/hash. Send once per authorized snapshot; persist remote acknowledgement per business; timeouts unknown until reconciled. A combined taxi/property page may require distinct submissions and partial success handling. Shared conventions and schema constraints apply. |
| Database entities | hmrc_connections, businesses, mtd_obligations, mtd_previews, mtd_updates, mtd_update_businesses, private_files, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Recognized HMRC application, OAuth/scopes, sandbox/production API, secure token vault and fraud-prevention requirements |

### U03 - GET /v1/mtd/oauth/callback

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | HMRC MTD: MtdView, MtdQuartersView, MtdSendView; actual connection UI absent |
| User action / scope / priority | Verify callback, store encrypted provider tokens, never expose them; EXTENSION; P2 |
| Request schema | `query code:str,state:str` |
| Response schema | `Safe app redirect or {connection_status:str}` |
| Authentication | Verified expiring one-use OAuth state tied to initiating user; no app JWT in URL |
| Validation / business logic | Server checks verified eligibility/exemptions and connection. Retrieve obligations/businesses; immutable validated preview has ledger version/hash. Send once per authorized snapshot; persist remote acknowledgement per business; timeouts unknown until reconciled. A combined taxi/property page may require distinct submissions and partial success handling. Shared conventions and schema constraints apply. |
| Database entities | hmrc_connections, businesses, mtd_obligations, mtd_previews, mtd_updates, mtd_update_businesses, private_files, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Recognized HMRC application, OAuth/scopes, sandbox/production API, secure token vault and fraud-prevention requirements |

### U04 - GET /v1/mtd/businesses

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | HMRC MTD: MtdView, MtdQuartersView, MtdSendView; actual connection UI absent |
| User action / scope / priority | Load user's real taxi/property businesses; SCREEN; P2 |
| Request schema | `none` |
| Response schema | `MtdBusiness[]` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server checks verified eligibility/exemptions and connection. Retrieve obligations/businesses; immutable validated preview has ledger version/hash. Send once per authorized snapshot; persist remote acknowledgement per business; timeouts unknown until reconciled. A combined taxi/property page may require distinct submissions and partial success handling. Shared conventions and schema constraints apply. |
| Database entities | hmrc_connections, businesses, mtd_obligations, mtd_previews, mtd_updates, mtd_update_businesses, private_files, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Recognized HMRC application, OAuth/scopes, sandbox/production API, secure token vault and fraud-prevention requirements |

### U05 - GET /v1/mtd/obligations

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | HMRC MTD: MtdView, MtdQuartersView, MtdSendView; actual connection UI absent |
| User action / scope / priority | Load deadlines/status/history from authoritative obligations; SCREEN; P2 |
| Request schema | `query tax_year:str,business_id?:uuid` |
| Response schema | `Obligation[]` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server checks verified eligibility/exemptions and connection. Retrieve obligations/businesses; immutable validated preview has ledger version/hash. Send once per authorized snapshot; persist remote acknowledgement per business; timeouts unknown until reconciled. A combined taxi/property page may require distinct submissions and partial success handling. Shared conventions and schema constraints apply. |
| Database entities | hmrc_connections, businesses, mtd_obligations, mtd_previews, mtd_updates, mtd_update_businesses, private_files, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Recognized HMRC application, OAuth/scopes, sandbox/production API, secure token vault and fraud-prevention requirements |

### U06 - POST /v1/mtd/previews

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | HMRC MTD: MtdView, MtdQuartersView, MtdSendView; actual connection UI absent |
| User action / scope / priority | Validate/freeze reviewed quarter and year-to-date figures; SCREEN; P2 |
| Request schema | `{obligation_ids:str[]}` |
| Response schema | `MtdPreview` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server checks verified eligibility/exemptions and connection. Retrieve obligations/businesses; immutable validated preview has ledger version/hash. Send once per authorized snapshot; persist remote acknowledgement per business; timeouts unknown until reconciled. A combined taxi/property page may require distinct submissions and partial success handling. Shared conventions and schema constraints apply. |
| Database entities | hmrc_connections, businesses, mtd_obligations, mtd_previews, mtd_updates, mtd_update_businesses, private_files, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Recognized HMRC application, OAuth/scopes, sandbox/production API, secure token vault and fraud-prevention requirements |

### U07 - POST /v1/mtd/updates

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | HMRC MTD: MtdView, MtdQuartersView, MtdSendView; actual connection UI absent |
| User action / scope / priority | Queue authorized hold-to-send snapshot (202); no pretend success; SCREEN; P2 |
| Request schema | `{preview_id:uuid,snapshot_hash:str,consent_version:str}` |
| Response schema | `MtdUpdate` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server checks verified eligibility/exemptions and connection. Retrieve obligations/businesses; immutable validated preview has ledger version/hash. Send once per authorized snapshot; persist remote acknowledgement per business; timeouts unknown until reconciled. A combined taxi/property page may require distinct submissions and partial success handling. Shared conventions and schema constraints apply. |
| Database entities | hmrc_connections, businesses, mtd_obligations, mtd_previews, mtd_updates, mtd_update_businesses, private_files, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Recognized HMRC application, OAuth/scopes, sandbox/production API, secure token vault and fraud-prevention requirements |

### U08 - GET /v1/mtd/updates/{id}

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | HMRC MTD: MtdView, MtdQuartersView, MtdSendView; actual connection UI absent |
| User action / scope / priority | Poll accepted/rejected/partial/unknown outcomes; SCREEN; P2 |
| Request schema | `none` |
| Response schema | `MtdUpdate plus {business_results:{business_id:uuid,status:str,provider_reference_masked:str?,error_code:str?}[]}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server checks verified eligibility/exemptions and connection. Retrieve obligations/businesses; immutable validated preview has ledger version/hash. Send once per authorized snapshot; persist remote acknowledgement per business; timeouts unknown until reconciled. A combined taxi/property page may require distinct submissions and partial success handling. Shared conventions and schema constraints apply. |
| Database entities | hmrc_connections, businesses, mtd_obligations, mtd_previews, mtd_updates, mtd_update_businesses, private_files, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Recognized HMRC application, OAuth/scopes, sandbox/production API, secure token vault and fraud-prevention requirements |

### U09 - GET /v1/mtd/updates/{id}/confirmation

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | HMRC MTD: MtdView, MtdQuartersView, MtdSendView; actual connection UI absent |
| User action / scope / priority | Open saved actual HMRC confirmation, only when accepted; SCREEN; P2 |
| Request schema | `none` |
| Response schema | `Binary private acknowledgement document or {business_references:object,accepted_at:datetime}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server checks verified eligibility/exemptions and connection. Retrieve obligations/businesses; immutable validated preview has ledger version/hash. Send once per authorized snapshot; persist remote acknowledgement per business; timeouts unknown until reconciled. A combined taxi/property page may require distinct submissions and partial success handling. Shared conventions and schema constraints apply. |
| Database entities | hmrc_connections, businesses, mtd_obligations, mtd_previews, mtd_updates, mtd_update_businesses, private_files, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Recognized HMRC application, OAuth/scopes, sandbox/production API, secure token vault and fraud-prevention requirements |

### U10 - GET /v1/mtd/updates

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | HMRC MTD: MtdView, MtdQuartersView, MtdSendView; actual connection UI absent |
| User action / scope / priority | Load real update history; SCREEN; P2 |
| Request schema | `query tax_year:str,limit:int=50,cursor:str?` |
| Response schema | `Page<MtdUpdate>` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Server checks verified eligibility/exemptions and connection. Retrieve obligations/businesses; immutable validated preview has ledger version/hash. Send once per authorized snapshot; persist remote acknowledgement per business; timeouts unknown until reconciled. A combined taxi/property page may require distinct submissions and partial success handling. Shared conventions and schema constraints apply. |
| Database entities | hmrc_connections, businesses, mtd_obligations, mtd_previews, mtd_updates, mtd_update_businesses, private_files, audit_events |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Recognized HMRC application, OAuth/scopes, sandbox/production API, secure token vault and fraud-prevention requirements |

### B01 - POST /v1/assistant/conversations

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Assistant: Ask affordances across Home/Driver/AddSheet/Personal; no conversation screen |
| User action / scope / priority | Start explicitly consented conversation; EXTENSION; P3 |
| Request schema | `{locale:str,context_resource_ids:uuid[]=[],consent_version:str}` |
| Response schema | `Conversation` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Opt-in minimum necessary context; enforce tenant ownership/rate limits; no implicit tax filing or ledger mutation; clearly distinguish guidance from verified tax calculation. Conversation UI remains absent. Shared conventions and schema constraints apply. |
| Database entities | assistant_conversations, assistant_messages, consent_records |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Chosen language/LLM provider; data processing policy |

### B02 - POST /v1/assistant/conversations/{id}/messages

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Assistant: Ask affordances across Home/Driver/AddSheet/Personal; no conversation screen |
| User action / scope / priority | Ask in preferred language with allowed context; EXTENSION; P3 |
| Request schema | `{content:str,client_message_id:uuid}` |
| Response schema | `{user_message:Message,assistant_message:Message}` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Opt-in minimum necessary context; enforce tenant ownership/rate limits; no implicit tax filing or ledger mutation; clearly distinguish guidance from verified tax calculation. Conversation UI remains absent. Shared conventions and schema constraints apply. |
| Database entities | assistant_conversations, assistant_messages, consent_records |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Chosen language/LLM provider; data processing policy |

### B03 - GET /v1/assistant/conversations/{id}/messages

| Requirement | PROPOSED specification |
| --- | --- |
| Module / related screens | Assistant: Ask affordances across Home/Driver/AddSheet/Personal; no conversation screen |
| User action / scope / priority | Resume conversation/history; EXTENSION; P3 |
| Request schema | `query limit:int=50,cursor:str?` |
| Response schema | `Page<Message>` |
| Authentication | Bearer access JWT; owner-scoped |
| Validation / business logic | Opt-in minimum necessary context; enforce tenant ownership/rate limits; no implicit tax filing or ledger mutation; clearly distinguish guidance from verified tax calculation. Conversation UI remains absent. Shared conventions and schema constraints apply. |
| Database entities | assistant_conversations, assistant_messages, consent_records |
| Errors | Standard errors above; 409 stale/duplicate/invalid transition, 422 inconsistent fields, 413 size, 415 file type for uploads; 503 external unavailability. Processing rejection stored on Job/MtdUpdate; never report accepted from queue status. |
| External dependencies | Chosen language/LLM provider; data processing policy |

## Catalog totals and scope

**93 unique proposed HTTP operations:** 15 extension, 8 foundation, 70 screen. Priorities: P0=40, P1=36, P2=14, P3=3. These are proposals, not existing integrations. SCREEN means represented workflow, FOUNDATION means required supporting behavior, EXTENSION means full UI/integration absent. P0 mileage extensions identify an essential evidence gap, not an implemented form.

| ID | Method | Proposed endpoint |
| --- | --- | --- |
| A01 | POST | `/v1/auth/challenges` |
| A02 | POST | `/v1/auth/challenges/{id}/verify` |
| A03 | POST | `/v1/auth/providers/{provider}` |
| A04 | POST | `/v1/auth/refresh` |
| A05 | POST | `/v1/auth/logout` |
| A06 | GET | `/v1/me` |
| A07 | POST | `/v1/auth/challenges/{id}/resend` |
| P01 | PATCH | `/v1/me` |
| P02 | GET | `/v1/me/onboarding` |
| P03 | PATCH | `/v1/me/onboarding` |
| P04 | GET | `/v1/me/driver-profile` |
| P05 | PUT | `/v1/me/driver-profile` |
| P06 | GET | `/v1/me/tax-profile` |
| P07 | PUT | `/v1/me/tax-profile` |
| F01 | GET | `/v1/reference-data` |
| V01 | POST | `/v1/vehicles/lookup` |
| V02 | GET | `/v1/vehicles` |
| V03 | POST | `/v1/vehicles` |
| V04 | GET | `/v1/vehicles/{id}` |
| V05 | POST | `/v1/vehicles/{id}/claim-method` |
| V06 | PATCH | `/v1/vehicles/{id}` |
| I01 | GET | `/v1/me/income-sources` |
| I02 | PUT | `/v1/me/income-sources` |
| L01 | GET | `/v1/transactions` |
| L02 | POST | `/v1/transactions` |
| L03 | GET | `/v1/transactions/{id}` |
| L04 | PATCH | `/v1/transactions/{id}` |
| L05 | DELETE | `/v1/transactions/{id}` |
| L06 | POST | `/v1/transactions/{id}/reversals` |
| R01 | GET | `/v1/dashboard` |
| R02 | GET | `/v1/reports/weekly` |
| R03 | GET | `/v1/reports/annual` |
| R04 | GET | `/v1/categories/summary` |
| R05 | GET | `/v1/categories/{id}/transactions` |
| R06 | GET | `/v1/reports/personal` |
| R07 | PUT | `/v1/categories/{id}/business-use` |
| C01 | POST | `/v1/receipts` |
| C02 | GET | `/v1/receipts` |
| C03 | GET | `/v1/receipts/{id}` |
| C04 | PATCH | `/v1/receipts/{id}` |
| C05 | POST | `/v1/receipts/{id}/confirmations` |
| C06 | POST | `/v1/receipts/{id}/reversals` |
| C07 | GET | `/v1/receipts/{id}/content` |
| C08 | POST | `/v1/receipts/{id}/ocr-retries` |
| D01 | POST | `/v1/statements` |
| D02 | GET | `/v1/statements` |
| D03 | GET | `/v1/statements/{id}` |
| D04 | POST | `/v1/statements/{id}/imports` |
| D05 | GET | `/v1/statements/{id}/content` |
| Q01 | GET | `/v1/reconciliations` |
| Q02 | GET | `/v1/reconciliations/{id}` |
| Q03 | POST | `/v1/reconciliations/{id}/resolutions` |
| Q04 | POST | `/v1/reconciliations/{id}/reversals` |
| M01 | GET | `/v1/mileage-logs` |
| M02 | POST | `/v1/mileage-logs` |
| M03 | PATCH | `/v1/mileage-logs/{id}` |
| M04 | DELETE | `/v1/mileage-logs/{id}` |
| T01 | GET | `/v1/tax/estimate` |
| T02 | GET | `/v1/tax/forecast` |
| T03 | GET | `/v1/tax/deduction-comparison` |
| T04 | GET | `/v1/tax/payment-timeline` |
| T05 | GET | `/v1/tax/rules` |
| K01 | GET | `/v1/tax-pot` |
| K02 | POST | `/v1/tax-pot/entries` |
| K03 | POST | `/v1/tax-pot/entries/{id}/reversals` |
| N01 | GET | `/v1/notifications` |
| N02 | PATCH | `/v1/notifications/{id}` |
| N03 | POST | `/v1/notifications/read-all` |
| N04 | GET | `/v1/deadlines` |
| E01 | POST | `/v1/exports` |
| E02 | GET | `/v1/exports/{id}` |
| E03 | GET | `/v1/exports/{id}/download` |
| H01 | POST | `/v1/accountant-requests` |
| H02 | GET | `/v1/accountant-requests/{id}` |
| S01 | GET | `/v1/subscription-plans` |
| S02 | GET | `/v1/me/subscription` |
| S03 | POST | `/v1/me/subscription/trial` |
| S04 | POST | `/v1/billing/webhooks/{provider}` |
| S05 | POST | `/v1/me/subscription/checkout` |
| S06 | POST | `/v1/me/subscription/cancellation` |
| U01 | GET | `/v1/mtd/eligibility` |
| U02 | POST | `/v1/mtd/authorizations` |
| U03 | GET | `/v1/mtd/oauth/callback` |
| U04 | GET | `/v1/mtd/businesses` |
| U05 | GET | `/v1/mtd/obligations` |
| U06 | POST | `/v1/mtd/previews` |
| U07 | POST | `/v1/mtd/updates` |
| U08 | GET | `/v1/mtd/updates/{id}` |
| U09 | GET | `/v1/mtd/updates/{id}/confirmation` |
| U10 | GET | `/v1/mtd/updates` |
| B01 | POST | `/v1/assistant/conversations` |
| B02 | POST | `/v1/assistant/conversations/{id}/messages` |
| B03 | GET | `/v1/assistant/conversations/{id}/messages` |

## Contract decisions

The UI expects OTP/provider identity. If the reported backend only supports password/email, choose an adapter or separately authorized frontend changes; no password form was observed. Native biometric unlock protects local session credentials; no Face ID success API.

Historical totals has no implemented form: decide between explicit opening transactions marked estimated and statement imports. Spreadsheet format is proposed CSV, not an observed format contract; confirm CSV versus XLSX. No bank transfer, direct Uber/Bolt API, property CRUD or final-return filing contract is inferred. Billing/HMRC provider payloads must come from verified selected provider schemas. The app cannot claim recognition/accepted submission merely because a job is queued.

## Ledger drafts, reference data and workflow details

AllMoney tabs need both confirmed money and typed pending expenses. Proposed policy: once OCR has usable amount/date/business context, create one owner-scoped draft transaction linked to the receipt (category may remain unset while draft). Confirmation fills/validates all required fields and posts that existing draft exactly once; if no draft exists it creates the single posting atomically. C05's create-ledger wording includes this create-or-confirm behavior. Unknown/incomplete extractions stay only in the receipt queue until usable; never fabricate an amount/date/category. Draft/personal/reversed items are excluded from deductible aggregates as appropriate. Final transaction category/source constraints apply on confirmation, not to an incomplete OCR draft.

Client tab translation: All uses unfiltered L01; Money in filters kind=income; Expenses filters kind=expense (including drafts where shown); To check filters review_status=draft. Date/source/category/query apply together. Receipt processing failures and incomplete extractions are available through C02/C03, rather than invented MoneyItems. Pending count comes from C02/dashboard, not page length. Ledger detail resolves linked receipt/payout; receipt editor always requires receipt ID. Manual create sends a complete validated TransactionInput; raw OCR suggestions never become a confirmed claim by themselves.

P05 creates/links the default taxi business in the same transaction and projects primary_business_id in DriverProfile; it also projects the canonical user's name rather than duplicating it in driver_profiles. Server-managed primary_business_id is not accepted from arbitrary driver-profile updates. U04 maps only provider-verified businesses to the same authenticated owner; it does not authorize client-created property businesses. F01 catalogs provide stable UUID/code mappings; categories/default shares are projected through R05/R07, not copied into shared reference data as private values.

Idempotency digest includes method, concrete resource path (including UUIDs), and canonical request body. Auth/challenge/provider and callback token operations use their own credential replay rules, not plaintext token response caching. Same idempotency key with a changed payload/path must not silently return another resource's result.

Registration has no actual name input. User.first_name and projected DriverProfile.first_name are nullable until a separately specified profile step captures them; never assign the Ali fixture to a real account. For tax identifier input, proposed UTR validation is ten digits after whitespace normalization; NI input normalizes uppercase/spacing and must use the verified official prefix/suffix validity rules, not keyboard hints alone. Raw identifiers never return in ordinary profile responses.
