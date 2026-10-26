# Complete Flutter to backend mapping

Analysis: 27 October 2026. Every operation is PROPOSED. IDs refer to document06, the canonical method/path/request/response catalog. No current screen makes a request. Each primary view is mapped below with initial loads, writes, schemas, authentication, pagination, error handling, mock replacement and caching. A read endpoint listed under actions (job polling/download) is an action-time dependency, not a write.

## Shared integration requirements

Load/authenticate A06 before private routes; refresh via A04 only under verified session rules; 401 reauthenticate after preserving appropriate drafts, 403 entitlement/permission, 404 inaccessible record, 409 refetch version and explain conflict, 422 field-level validation, 429 retry-after, 503/offline preserve draft and offer retry. Confirm/bookkeeping mutations need idempotency and canonical success response, not navigation-based success. Every screen that gains async data needs loading/empty/error/retry states: those are requirements, not present behavior.

No raw JWT/refresh token/UTR/NI or public receipt URLs in ordinary caches. Secure device token storage and native biometric unlock are separate frontend work. Query caches are owner-scoped and cleared on logout. Mutation invalidation includes Dashboard, TaxEstimate, annual/weekly/category/personal reports, receipt status counts and reconciliations as applicable. Cursor paging for Page responses, no infinite-scroll assumption for current fixture lists. Bounded reference/summary/period reports do not need paging. Client receives stable UUIDs and sends them via route arguments; current static routes do not carry IDs.

## S01 - WelcomeView

- **Exact Flutter file/class:** `lib/features/onboarding/view/welcome_view.dart::WelcomeView`.
- **Current route:** /welcome.
- **Initial data-loading API IDs:** none.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.
  No backend operation needed for static content/navigation.
- **Authentication:** Public content or transient challenge/provider auth only; authenticated session established by successful verification.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** No remote state for this static page.
- **Mock replacement:** Working navigation; decorative demo figures.
- **Local caching/native needs:** No private cache; static marketing.

## S02 - LanguageView

- **Exact Flutter file/class:** `lib/features/onboarding/view/language_view.dart::LanguageView`.
- **Current route:** /language.
- **Initial data-loading API IDs:** A06 F01.
- **Create/update/delete or action-time IDs:** P01.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| A06: GET `/v1/me` | `none` | `User` |
| F01: GET `/v1/reference-data` | `query locale:str=en` | `{version:str,languages:{code:str,native:str,english:str,rtl:bool}[],councils:{code:str,name:str}[],licence_types:str[],sources:IncomeSource[],categories:Category[],upload_limits:{max_bytes:int,mime_types:str[]}}` |
| P01: PATCH `/v1/me` | `{first_name?:str,last_name?:str?,preferences?:Patch<Preferences>,expected_version:int}` | `User` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Partial selection; no persisted preference/app locale.
- **Local caching/native needs:** Cache locale choice/reference catalogs; local translations required.

## S03 - HowItWorksView

- **Exact Flutter file/class:** `lib/features/onboarding/view/how_it_works_view.dart::HowItWorksView`.
- **Current route:** /how-it-works.
- **Initial data-loading API IDs:** none.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.
  No backend operation needed for static content/navigation.
- **Authentication:** Public content or transient challenge/provider auth only; authenticated session established by successful verification.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** No remote state for this static page.
- **Mock replacement:** Static marketing; integrations absent.
- **Local caching/native needs:** Static content only.

## S04 - CreateAccountView

- **Exact Flutter file/class:** `lib/features/onboarding/view/create_account_view.dart::CreateAccountView`.
- **Current route:** /create-account.
- **Initial data-loading API IDs:** F01.
- **Create/update/delete or action-time IDs:** A01 A03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| F01: GET `/v1/reference-data` | `query locale:str=en` | `{version:str,languages:{code:str,native:str,english:str,rtl:bool}[],councils:{code:str,name:str}[],licence_types:str[],sources:IncomeSource[],categories:Category[],upload_limits:{max_bytes:int,mime_types:str[]}}` |
| A01: POST `/v1/auth/challenges` | `{phone:str,purpose:sign_up/sign_in}` | `Challenge` |
| A03: POST `/v1/auth/providers/{provider}` | `{identity_token:str,nonce:str}` | `Tokens` |

- **Authentication:** Public content or transient challenge/provider auth only; authenticated session established by successful verification.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Mock auth; no SMS/OAuth.
- **Local caching/native needs:** Persist challenge handle briefly, never OTP/provider secrets.

## S05 - CodeView

- **Exact Flutter file/class:** `lib/features/onboarding/view/code_view.dart::CodeView`.
- **Current route:** /code.
- **Initial data-loading API IDs:** none.
- **Create/update/delete or action-time IDs:** A02 A07.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| A02: POST `/v1/auth/challenges/{id}/verify` | `{code:str exactly 6 digits}` | `Tokens` |
| A07: POST `/v1/auth/challenges/{id}/resend` | `none` | `Challenge` |

- **Authentication:** Public content or transient challenge/provider auth only; authenticated session established by successful verification.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Mock verification.
- **Local caching/native needs:** Challenge handle/expiry in transient state; no cached code.

## S06 - SignInView

- **Exact Flutter file/class:** `lib/features/onboarding/view/sign_in_view.dart::SignInView`.
- **Current route:** /sign-in.
- **Initial data-loading API IDs:** none.
- **Create/update/delete or action-time IDs:** A01 A03 A04.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| A01: POST `/v1/auth/challenges` | `{phone:str,purpose:sign_up/sign_in}` | `Challenge` |
| A03: POST `/v1/auth/providers/{provider}` | `{identity_token:str,nonce:str}` | `Tokens` |
| A04: POST `/v1/auth/refresh` | `{refresh_token:str}` | `Tokens` |

- **Authentication:** Public content or transient challenge/provider auth only; authenticated session established by successful verification.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Mock auth; code path incorrectly leads through new-user setup.
- **Local caching/native needs:** Native biometric unlock of secure session separate; never trust current tile.

## S07 - SecureView

- **Exact Flutter file/class:** `lib/features/onboarding/view/secure_view.dart::SecureView`.
- **Current route:** /secure.
- **Initial data-loading API IDs:** A06.
- **Create/update/delete or action-time IDs:** P01.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| A06: GET `/v1/me` | `none` | `User` |
| P01: PATCH `/v1/me` | `{first_name?:str,last_name?:str?,preferences?:Patch<Preferences>,expected_version:int}` | `User` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** UI-only device protection.
- **Local caching/native needs:** Device lock/passcode stays local secure settings; no biometric secret sync.

## S08 - DrivingView

- **Exact Flutter file/class:** `lib/features/onboarding/view/driving_view.dart::DrivingView`.
- **Current route:** /setup/driving.
- **Initial data-loading API IDs:** P04 F01.
- **Create/update/delete or action-time IDs:** P05 P03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| P04: GET `/v1/me/driver-profile` | `none` | `DriverProfile` |
| F01: GET `/v1/reference-data` | `query locale:str=en` | `{version:str,languages:{code:str,native:str,english:str,rtl:bool}[],councils:{code:str,name:str}[],licence_types:str[],sources:IncomeSource[],categories:Category[],upload_limits:{max_bytes:int,mime_types:str[]}}` |
| P05: PUT `/v1/me/driver-profile` | `DriverProfile excluding server-managed primary_business_id/version plus expected_version:int?` | `DriverProfile` |
| P03: PATCH `/v1/me/onboarding` | `{current_step?:int,completed_steps?:int[],skipped_fields?:str[],complete?:bool,expected_version:int}` | `Onboarding` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Working local choices, unsaved.
- **Local caching/native needs:** Cache setup draft per owner until saved.

## S09 - PlatformsView

- **Exact Flutter file/class:** `lib/features/onboarding/view/platforms_view.dart::PlatformsView`.
- **Current route:** /setup/platforms.
- **Initial data-loading API IDs:** F01 I01.
- **Create/update/delete or action-time IDs:** I02 P03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| F01: GET `/v1/reference-data` | `query locale:str=en` | `{version:str,languages:{code:str,native:str,english:str,rtl:bool}[],councils:{code:str,name:str}[],licence_types:str[],sources:IncomeSource[],categories:Category[],upload_limits:{max_bytes:int,mime_types:str[]}}` |
| I01: GET `/v1/me/income-sources` | `none` | `IncomeSource[]` |
| I02: PUT `/v1/me/income-sources` | `{source_ids:uuid[]}` | `IncomeSource[]` |
| P03: PATCH `/v1/me/onboarding` | `{current_step?:int,completed_steps?:int[],skipped_fields?:str[],complete?:bool,expected_version:int}` | `Onboarding` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Working local choice; no provider connection.
- **Local caching/native needs:** Reference catalog cached; selected source IDs persist.

## S10 - OtherIncomeView

- **Exact Flutter file/class:** `lib/features/onboarding/view/other_income_view.dart::OtherIncomeView`.
- **Current route:** /setup/other-income.
- **Initial data-loading API IDs:** P06.
- **Create/update/delete or action-time IDs:** P07 P03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| P06: GET `/v1/me/tax-profile` | `query tax_year:str` | `TaxProfile` |
| P07: PUT `/v1/me/tax-profile` | `{tax_year:str,region:str,has_paye_job:bool,employments:Employment[],property_income_pence:int?,interest_pence:int?,student_loan_plan:str?,marriage_allowance_status:str?,utr:str?,ni_number:str?,expected_version:int?}` | `TaxProfile` |
| P03: PATCH `/v1/me/onboarding` | `{current_step?:int,completed_steps?:int[],skipped_fields?:str[],complete?:bool,expected_version:int}` | `Onboarding` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Partial conditional UI; no captured salary.
- **Local caching/native needs:** Sensitive draft memory only; masked saved context.

## S11 - TaxDetailsView

- **Exact Flutter file/class:** `lib/features/onboarding/view/tax_details_view.dart::TaxDetailsView`.
- **Current route:** /setup/tax-details.
- **Initial data-loading API IDs:** P06.
- **Create/update/delete or action-time IDs:** P07 P03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| P06: GET `/v1/me/tax-profile` | `query tax_year:str` | `TaxProfile` |
| P07: PUT `/v1/me/tax-profile` | `{tax_year:str,region:str,has_paye_job:bool,employments:Employment[],property_income_pence:int?,interest_pence:int?,student_loan_plan:str?,marriage_allowance_status:str?,utr:str?,ni_number:str?,expected_version:int?}` | `TaxProfile` |
| P03: PATCH `/v1/me/onboarding` | `{current_step?:int,completed_steps?:int[],skipped_fields?:str[],complete?:bool,expected_version:int}` | `Onboarding` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** UI-only sensitive-data collection.
- **Local caching/native needs:** No raw UTR/NI ordinary cache/logging.

## S12 - VehicleView

- **Exact Flutter file/class:** `lib/features/onboarding/view/vehicle_view.dart::VehicleView`.
- **Current route:** /setup/vehicle.
- **Initial data-loading API IDs:** V02.
- **Create/update/delete or action-time IDs:** V01 V03 V06 P03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| V02: GET `/v1/vehicles` | `query active:bool=true,limit:int=50,cursor:str?` | `Page<Vehicle>` |
| V01: POST `/v1/vehicles/lookup` | `{registration:str}` | `{registration:str,make:str?,model:str?,year:int?,colour:str?,fuel:str?,lookup_status:found/not_found/unavailable}` |
| V03: POST `/v1/vehicles` | `VehicleInput` | `Vehicle` |
| V06: PATCH `/v1/vehicles/{id}` | `Patch<VehicleInput> plus expected_version:int` | `Vehicle` |
| P03: PATCH `/v1/me/onboarding` | `{current_step?:int,completed_steps?:int[],skipped_fields?:str[],complete?:bool,expected_version:int}` | `Onboarding` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Mock lookup; no vehicle CRUD.
- **Local caching/native needs:** Cache active vehicle metadata scoped to user.

## S13 - ClaimMethodView

- **Exact Flutter file/class:** `lib/features/onboarding/view/claim_method_view.dart::ClaimMethodView`.
- **Current route:** /setup/claim-method.
- **Initial data-loading API IDs:** V04 T05.
- **Create/update/delete or action-time IDs:** V05 P03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| V04: GET `/v1/vehicles/{id}` | `none` | `Vehicle plus {tax_year:str,business_miles:decimal-string,deduction_pence:int,rule_set_id:uuid}` |
| T05: GET `/v1/tax/rules` | `query tax_year:str,region:str` | `{id:uuid,tax_year:str,region:str,version:str,rules:{code:str,value:object,effective_from:date,effective_to:date?,official_url:str,verified_at:datetime}[]}` |
| V05: POST `/v1/vehicles/{id}/claim-method` | `{method:mileage/actual,effective_from:date,prior_capital_allowances:bool,prior_vehicle_expense_claim:bool,acknowledgement_version:str,expected_version:int}` | `Vehicle plus {election_id:uuid,mutation_id:uuid}` |
| P03: PATCH `/v1/me/onboarding` | `{current_step?:int,completed_steps?:int[],skipped_fields?:str[],complete?:bool,expected_version:int}` | `Onboarding` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Local choice only; later screens always mileage.
- **Local caching/native needs:** No optimistic lock-in success before server election.

## S14 - EarningsView

- **Exact Flutter file/class:** `lib/features/onboarding/view/earnings_view.dart::EarningsView`.
- **Current route:** /setup/earnings.
- **Initial data-loading API IDs:** I01 D02.
- **Create/update/delete or action-time IDs:** D01 D04 P03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| I01: GET `/v1/me/income-sources` | `none` | `IncomeSource[]` |
| D02: GET `/v1/statements` | `query tax_year:str,source_id?:uuid,limit:int=50,cursor:str?` | `Page<Statement>` |
| D01: POST `/v1/statements` | `multipart file:binary,source_id:uuid,business_id:uuid` | `{statement:Statement,job:Job}` |
| D04: POST `/v1/statements/{id}/imports` | `{expected_version:int,acknowledged_warning_codes:str[]}` | `{statement:Statement,transaction_ids:uuid[],issues:ReconciliationIssue[],mutation_id:uuid}` |
| P03: PATCH `/v1/me/onboarding` | `{current_step?:int,completed_steps?:int[],skipped_fields?:str[],complete?:bool,expected_version:int}` | `Onboarding` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Mock import entry; manual totals missing.
- **Local caching/native needs:** Selected file/job reference transient; manual totals contract undecided.

## S15 - ReadingView

- **Exact Flutter file/class:** `lib/features/onboarding/view/reading_view.dart::ReadingView`.
- **Current route:** /setup/reading.
- **Initial data-loading API IDs:** D03.
- **Create/update/delete or action-time IDs:** D04.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| D03: GET `/v1/statements/{id}` | `none` | `Statement` |
| D04: POST `/v1/statements/{id}/imports` | `{expected_version:int,acknowledged_warning_codes:str[]}` | `{statement:Statement,transaction_ids:uuid[],issues:ReconciliationIssue[],mutation_id:uuid}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Mock timed parser results.
- **Local caching/native needs:** Poll actual job with bounded backoff; invalidate ledger/report caches after import.

## S16 - TrialView

- **Exact Flutter file/class:** `lib/features/onboarding/view/trial_view.dart::TrialView`.
- **Current route:** /setup/trial.
- **Initial data-loading API IDs:** S01 S02.
- **Create/update/delete or action-time IDs:** S03 P03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| S01: GET `/v1/subscription-plans` | `query locale:str=en` | `Plan[]` |
| S02: GET `/v1/me/subscription` | `none` | `Subscription or {status:none,entitlements:str[]}` |
| S03: POST `/v1/me/subscription/trial` | `{plan_id:uuid,terms_version:str}` | `Subscription` |
| P03: PATCH `/v1/me/onboarding` | `{current_step?:int,completed_steps?:int[],skipped_fields?:str[],complete?:bool,expected_version:int}` | `Onboarding` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** UI-only trial; no subscription created.
- **Local caching/native needs:** Cache offer version briefly; dates/entitlement server-owned.

## S17 - RemindersView

- **Exact Flutter file/class:** `lib/features/onboarding/view/reminders_view.dart::RemindersView`.
- **Current route:** /setup/reminders.
- **Initial data-loading API IDs:** A06 P02.
- **Create/update/delete or action-time IDs:** P01 P03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| A06: GET `/v1/me` | `none` | `User` |
| P02: GET `/v1/me/onboarding` | `none` | `Onboarding` |
| P01: PATCH `/v1/me` | `{first_name?:str,last_name?:str?,preferences?:Patch<Preferences>,expected_version:int}` | `User` |
| P03: PATCH `/v1/me/onboarding` | `{current_step?:int,completed_steps?:int[],skipped_fields?:str[],complete?:bool,expected_version:int}` | `Onboarding` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Local choices; both actions open demo Home.
- **Local caching/native needs:** Preferences owner-scoped; actual OS permission required.

## S18 - ShellView

- **Exact Flutter file/class:** `lib/features/shell/view/shell_view.dart::ShellView`.
- **Current route:** /home.
- **Initial data-loading API IDs:** A06 P02 P04 V02 S02.
- **Create/update/delete or action-time IDs:** A05.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| A06: GET `/v1/me` | `none` | `User` |
| P02: GET `/v1/me/onboarding` | `none` | `Onboarding` |
| P04: GET `/v1/me/driver-profile` | `none` | `DriverProfile` |
| V02: GET `/v1/vehicles` | `query active:bool=true,limit:int=50,cursor:str?` | `Page<Vehicle>` |
| S02: GET `/v1/me/subscription` | `none` | `Subscription or {status:none,entitlements:str[]}` |
| A05: POST `/v1/auth/logout` | `{refresh_token:str?}` | `No content` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Working tab/menu navigation.
- **Local caching/native needs:** Bootstrap authenticated state; clear per-user state on logout; no current logout control.

## S19 - HomeView

- **Exact Flutter file/class:** `lib/features/home/view/home_view.dart::HomeView`.
- **Current route:** /home -> AppTab.home.
- **Initial data-loading API IDs:** R01 N01 N04.
- **Create/update/delete or action-time IDs:** C05 C06.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| R01: GET `/v1/dashboard` | `query tax_year:str` | `Dashboard` |
| N01: GET `/v1/notifications` | `query unread_only:bool=false,limit:int=50,cursor:str?` | `{items:Notification[],next_cursor:str?,has_more:bool,unread_count:int}` |
| N04: GET `/v1/deadlines` | `query tax_year:str` | `Deadline[]` |
| C05: POST `/v1/receipts/{id}/confirmations` | `{claim_status:claimable/personal/excluded,category_id:uuid,business_use_percent:decimal-string,expected_version:int}` | `{receipt:Receipt,transaction:Transaction,mutation_id:uuid,dashboard:Dashboard}` |
| C06: POST `/v1/receipts/{id}/reversals` | `{mutation_id:uuid,reason:str,expected_version:int}` | `{receipt:Receipt,transaction:Transaction,dashboard:Dashboard}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Reactive demo profit/tax/counts; date/week/miles hardcoded.
- **Local caching/native needs:** Short-lived shared summary; invalidate after all financial/review/mileage changes.

## S20 - WeekView

- **Exact Flutter file/class:** `lib/features/home/view/week_view.dart::WeekView`.
- **Current route:** /week.
- **Initial data-loading API IDs:** R02 M01.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| R02: GET `/v1/reports/weekly` | `query start_on:date,business_id:uuid?` | `WeeklyReport` |
| M01: GET `/v1/mileage-logs` | `query tax_year:str,vehicle_id?:uuid,limit:int=50,cursor:str?` | `{items:MileageLog[],next_cursor:str?,has_more:bool,total_business_miles:decimal-string,deduction_pence:int,rule_set_id:uuid}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Working local switching/percent allocation; no day drilldown.
- **Local caching/native needs:** Cache by owner/business/week and ledger version.

## S21 - YearView

- **Exact Flutter file/class:** `lib/features/home/view/year_view.dart::YearView`.
- **Current route:** /year.
- **Initial data-loading API IDs:** R03 T01.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| R03: GET `/v1/reports/annual` | `query tax_year:str` | `AnnualReport` |
| T01: GET `/v1/tax/estimate` | `query tax_year:str,as_of?:date` | `TaxEstimate` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static report; never follows confirmations.
- **Local caching/native needs:** Cache by tax year/ledger/profile/rule version.

## S22 - CheckView

- **Exact Flutter file/class:** `lib/features/home/view/check_view.dart::CheckView`.
- **Current route:** /check.
- **Initial data-loading API IDs:** C02 Q01.
- **Create/update/delete or action-time IDs:** C04 C05 C06.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| C02: GET `/v1/receipts` | `query tax_year:str,review_status?:str,claim_status?:str,limit:int=50,cursor:str?` | `{items:Receipt[],next_cursor:str?,has_more:bool,counts:{all:int,pending:int,counted:int,not_claimed:int}}` |
| Q01: GET `/v1/reconciliations` | `query tax_year:str,source_id?:uuid,status?:str,limit:int=50,cursor:str?` | `{items:ReconciliationIssue[],next_cursor:str?,has_more:bool,platform_totals:{source_id:uuid,statement_gross_pence:int,recorded_gross_pence:int,difference_pence:int}[]}` |
| C04: PATCH `/v1/receipts/{id}` | `{merchant?:str,occurred_on?:date,amount_pence?:int,vat_pence?:int?,category_id?:uuid,business_use_percent?:decimal-string,claim_status?:str,expected_version:int}` | `Receipt` |
| C05: POST `/v1/receipts/{id}/confirmations` | `{claim_status:claimable/personal/excluded,category_id:uuid,business_use_percent:decimal-string,expected_version:int}` | `{receipt:Receipt,transaction:Transaction,mutation_id:uuid,dashboard:Dashboard}` |
| C06: POST `/v1/receipts/{id}/reversals` | `{mutation_id:uuid,reason:str,expected_version:int}` | `{receipt:Receipt,transaction:Transaction,dashboard:Dashboard}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Local confirmation; wrong fixed EE editor for other receipts.
- **Local caching/native needs:** Queue keyed by real receipt/issue IDs; fresh count after mutation.

## S23 - BoltView

- **Exact Flutter file/class:** `lib/features/home/view/bolt_view.dart::BoltView`.
- **Current route:** /check/bolt.
- **Initial data-loading API IDs:** Q02.
- **Create/update/delete or action-time IDs:** Q03 Q04.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| Q02: GET `/v1/reconciliations/{id}` | `none` | `ReconciliationIssue` |
| Q03: POST `/v1/reconciliations/{id}/resolutions` | `{mode:add_missing/link_existing,transaction_ids:uuid[]=[],new_transactions:TransactionInput[]=[],evidence_note:str?,expected_version:int}` | `{issue:ReconciliationIssue,transaction_ids:uuid[],resolution_id:uuid,mutation_id:uuid,dashboard:Dashboard}` |
| Q04: POST `/v1/reconciliations/{id}/reversals` | `{resolution_id:uuid,mutation_id:uuid,reason:str,expected_version:int}` | `{issue:ReconciliationIssue,dashboard:Dashboard}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Partial: changes flag only, no income/fees/tax mutation.
- **Local caching/native needs:** Keep exact resolution/action ID for Undo; refresh income/fees/tax summary.

## S24 - DatesView

- **Exact Flutter file/class:** `lib/features/home/view/dates_view.dart::DatesView`.
- **Current route:** /dates.
- **Initial data-loading API IDs:** N04 T04 U01.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| N04: GET `/v1/deadlines` | `query tax_year:str` | `Deadline[]` |
| T04: GET `/v1/tax/payment-timeline` | `query tax_year:str` | `PaymentTimeline` |
| U01: GET `/v1/mtd/eligibility` | `query tax_year:str` | `MtdEligibility` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Mock calendar success; no calendar write.
- **Local caching/native needs:** Deadlines cached by year/rule/as_of; device calendar write separate.

## S25 - NotificationsView

- **Exact Flutter file/class:** `lib/features/home/view/notifications_view.dart::NotificationsView`.
- **Current route:** /notifications.
- **Initial data-loading API IDs:** N01.
- **Create/update/delete or action-time IDs:** N02 N03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| N01: GET `/v1/notifications` | `query unread_only:bool=false,limit:int=50,cursor:str?` | `{items:Notification[],next_cursor:str?,has_more:bool,unread_count:int}` |
| N02: PATCH `/v1/notifications/{id}` | `{read:bool}` | `Notification` |
| N03: POST `/v1/notifications/read-all` | `{through:datetime}` | `{updated_count:int,unread_count:int}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Local bulk-read; five fixture notifications/three unread.
- **Local caching/native needs:** Paginated owner feed; unread count refreshed on read operations.

## S26 - MoneyView

- **Exact Flutter file/class:** `lib/features/money/view/money_view.dart::MoneyView`.
- **Current route:** /home -> AppTab.money.
- **Initial data-loading API IDs:** R01 L01 R04.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| R01: GET `/v1/dashboard` | `query tax_year:str` | `Dashboard` |
| L01: GET `/v1/transactions` | `query tax_year?:str,from?:date,to?:date,kind?:income/expense,review_status?:str,claim_status?:str,source_ids?:uuid[],category_ids?:uuid[],q?:str,limit:int=50,cursor:str?` | `Page<Transaction>` |
| R04: GET `/v1/categories/summary` | `query tax_year:str` | `{items:CategorySummary[],total_deductible_pence:int,personal_total_pence:int}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static totals/latest; only pending count reactive.
- **Local caching/native needs:** Same canonical summary as Home; latest list not static duplicate.

## S27 - AllMoneyView

- **Exact Flutter file/class:** `lib/features/money/view/all_money_view.dart::AllMoneyView`.
- **Current route:** /money/all.
- **Initial data-loading API IDs:** L01 F01 I01.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| L01: GET `/v1/transactions` | `query tax_year?:str,from?:date,to?:date,kind?:income/expense,review_status?:str,claim_status?:str,source_ids?:uuid[],category_ids?:uuid[],q?:str,limit:int=50,cursor:str?` | `Page<Transaction>` |
| F01: GET `/v1/reference-data` | `query locale:str=en` | `{version:str,languages:{code:str,native:str,english:str,rtl:bool}[],councils:{code:str,name:str}[],licence_types:str[],sources:IncomeSource[],categories:Category[],upload_limits:{max_bytes:int,mime_types:str[]}}` |
| I01: GET `/v1/me/income-sources` | `none` | `IncomeSource[]` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Local search/tabs work; filter controls ignored.
- **Local caching/native needs:** Query includes tab/date/source/category/q; cursor resets on every filter change.

## S28 - IncomeView

- **Exact Flutter file/class:** `lib/features/money/view/income_view.dart::IncomeView`.
- **Current route:** /money/income.
- **Initial data-loading API IDs:** L03.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| L03: GET `/v1/transactions/{id}` | `none` | `Transaction plus {payout:Payout?,receipt:Receipt?}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static payout example.
- **Local caching/native needs:** Actual transaction/payout ID required; D05 source PDF on demand.

## S29 - ExpenseView

- **Exact Flutter file/class:** `lib/features/money/view/expense_view.dart::ExpenseView`.
- **Current route:** /money/expense.
- **Initial data-loading API IDs:** L03 C03.
- **Create/update/delete or action-time IDs:** C04 C05 C06.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| L03: GET `/v1/transactions/{id}` | `none` | `Transaction plus {payout:Payout?,receipt:Receipt?}` |
| C03: GET `/v1/receipts/{id}` | `none` | `Receipt plus {job:Job?,extraction:{merchant:str?,occurred_on:date?,amount_pence:int?,vat_pence:int?,confidence:decimal-string?}?}` |
| C04: PATCH `/v1/receipts/{id}` | `{merchant?:str,occurred_on?:date,amount_pence?:int,vat_pence?:int?,category_id?:uuid,business_use_percent?:decimal-string,claim_status?:str,expected_version:int}` | `Receipt` |
| C05: POST `/v1/receipts/{id}/confirmations` | `{claim_status:claimable/personal/excluded,category_id:uuid,business_use_percent:decimal-string,expected_version:int}` | `{receipt:Receipt,transaction:Transaction,mutation_id:uuid,dashboard:Dashboard}` |
| C06: POST `/v1/receipts/{id}/reversals` | `{mutation_id:uuid,reason:str,expected_version:int}` | `{receipt:Receipt,transaction:Transaction,dashboard:Dashboard}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Local NCP confirmation; incorrect editor route.
- **Local caching/native needs:** Actual receipt/transaction ID, not fixed NCP index.

## S30 - CameraView

- **Exact Flutter file/class:** `lib/features/money/view/camera_view.dart::CameraView`.
- **Current route:** /money/camera.
- **Initial data-loading API IDs:** none.
- **Create/update/delete or action-time IDs:** C01.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| C01: POST `/v1/receipts` | `multipart file:binary,business_id:uuid,vehicle_id:uuid?` | `{receipt:Receipt,job:Job}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** UI-only camera drawn receipt.
- **Local caching/native needs:** Capture actual image locally; upload then navigate with receipt ID; no photo stored by backend before upload.

## S31 - ReadReceiptView

- **Exact Flutter file/class:** `lib/features/money/view/read_receipt_view.dart::ReadReceiptView`.
- **Current route:** /money/read-receipt.
- **Initial data-loading API IDs:** C03.
- **Create/update/delete or action-time IDs:** C08.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| C03: GET `/v1/receipts/{id}` | `none` | `Receipt plus {job:Job?,extraction:{merchant:str?,occurred_on:date?,amount_pence:int?,vat_pence:int?,confidence:decimal-string?}?}` |
| C08: POST `/v1/receipts/{id}/ocr-retries` | `{expected_version:int}` | `{receipt:Receipt,job:Job}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Mock OCR; no image processing.
- **Local caching/native needs:** Poll real processing/failed states; no timer implies success.

## S32 - ReviewReceiptView

- **Exact Flutter file/class:** `lib/features/money/view/review_receipt_view.dart::ReviewReceiptView`.
- **Current route:** /money/review-receipt.
- **Initial data-loading API IDs:** C03 F01.
- **Create/update/delete or action-time IDs:** C04 C05 C06.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| C03: GET `/v1/receipts/{id}` | `none` | `Receipt plus {job:Job?,extraction:{merchant:str?,occurred_on:date?,amount_pence:int?,vat_pence:int?,confidence:decimal-string?}?}` |
| F01: GET `/v1/reference-data` | `query locale:str=en` | `{version:str,languages:{code:str,native:str,english:str,rtl:bool}[],councils:{code:str,name:str}[],licence_types:str[],sources:IncomeSource[],categories:Category[],upload_limits:{max_bytes:int,mime_types:str[]}}` |
| C04: PATCH `/v1/receipts/{id}` | `{merchant?:str,occurred_on?:date,amount_pence?:int,vat_pence?:int?,category_id?:uuid,business_use_percent?:decimal-string,claim_status?:str,expected_version:int}` | `Receipt` |
| C05: POST `/v1/receipts/{id}/confirmations` | `{claim_status:claimable/personal/excluded,category_id:uuid,business_use_percent:decimal-string,expected_version:int}` | `{receipt:Receipt,transaction:Transaction,mutation_id:uuid,dashboard:Dashboard}` |
| C06: POST `/v1/receipts/{id}/reversals` | `{mutation_id:uuid,reason:str,expected_version:int}` | `{receipt:Receipt,transaction:Transaction,dashboard:Dashboard}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Preview changes; save always fixed EE GBP 26; type ignored.
- **Local caching/native needs:** Bound form draft; exact reviewed snapshot saved; invalidate all totals/grid/category.

## S33 - AddFareView

- **Exact Flutter file/class:** `lib/features/money/view/add_fare_view.dart::AddFareView`.
- **Current route:** /money/add-fare.
- **Initial data-loading API IDs:** I01.
- **Create/update/delete or action-time IDs:** L02.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| I01: GET `/v1/me/income-sources` | `none` | `IncomeSource[]` |
| L02: POST `/v1/transactions` | `TransactionInput` | `Transaction` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** UI-only create; nothing saved.
- **Local caching/native needs:** Bind amount/date/source/payment/note; preserve failed draft; no success on dismiss.

## S34 - AddExpenseView

- **Exact Flutter file/class:** `lib/features/money/view/add_expense_view.dart::AddExpenseView`.
- **Current route:** /money/add-expense.
- **Initial data-loading API IDs:** F01 V02 V04.
- **Create/update/delete or action-time IDs:** L02.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| F01: GET `/v1/reference-data` | `query locale:str=en` | `{version:str,languages:{code:str,native:str,english:str,rtl:bool}[],councils:{code:str,name:str}[],licence_types:str[],sources:IncomeSource[],categories:Category[],upload_limits:{max_bytes:int,mime_types:str[]}}` |
| V02: GET `/v1/vehicles` | `query active:bool=true,limit:int=50,cursor:str?` | `Page<Vehicle>` |
| V04: GET `/v1/vehicles/{id}` | `none` | `Vehicle plus {tax_year:str,business_miles:decimal-string,deduction_pence:int,rule_set_id:uuid}` |
| L02: POST `/v1/transactions` | `TransactionInput` | `Transaction` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** UI-only create; assumes mileage even after actual-cost selection.
- **Local caching/native needs:** Bind category/amount/date/reason/share; evaluate vehicle policy.

## S35 - UploadView

- **Exact Flutter file/class:** `lib/features/money/view/upload_view.dart::UploadView`.
- **Current route:** /money/upload.
- **Initial data-loading API IDs:** I01 D02.
- **Create/update/delete or action-time IDs:** D01.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| I01: GET `/v1/me/income-sources` | `none` | `IncomeSource[]` |
| D02: GET `/v1/statements` | `query tax_year:str,source_id?:uuid,limit:int=50,cursor:str?` | `Page<Statement>` |
| D01: POST `/v1/statements` | `multipart file:binary,source_id:uuid,business_id:uuid` | `{statement:Statement,job:Job}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Mock upload; Uber instructions lead to Bolt success.
- **Local caching/native needs:** Actual PDF picker + source; file/job ID survives navigation; D03 polling.

## S36 - StatementAddedView

- **Exact Flutter file/class:** `lib/features/money/view/statement_added_view.dart::StatementAddedView`.
- **Current route:** /money/statement-added.
- **Initial data-loading API IDs:** D03 Q01.
- **Create/update/delete or action-time IDs:** D04.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| D03: GET `/v1/statements/{id}` | `none` | `Statement` |
| Q01: GET `/v1/reconciliations` | `query tax_year:str,source_id?:uuid,status?:str,limit:int=50,cursor:str?` | `{items:ReconciliationIssue[],next_cursor:str?,has_more:bool,platform_totals:{source_id:uuid,statement_gross_pence:int,recorded_gross_pence:int,difference_pence:int}[]}` |
| D04: POST `/v1/statements/{id}/imports` | `{expected_version:int,acknowledged_warning_codes:str[]}` | `{statement:Statement,transaction_ids:uuid[],issues:ReconciliationIssue[],mutation_id:uuid}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static success; no income/fees imported.
- **Local caching/native needs:** Read actual selected platform result; confirm import rather than claim success automatically.

## S37 - PlatformCheckView

- **Exact Flutter file/class:** `lib/features/money/view/platform_check_view.dart::PlatformCheckView`.
- **Current route:** /money/platform-check.
- **Initial data-loading API IDs:** Q01.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| Q01: GET `/v1/reconciliations` | `query tax_year:str,source_id?:uuid,status?:str,limit:int=50,cursor:str?` | `{items:ReconciliationIssue[],next_cursor:str?,has_more:bool,platform_totals:{source_id:uuid,statement_gross_pence:int,recorded_gross_pence:int,difference_pence:int}[]}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Bolt flag reactive; amounts hardcoded.
- **Local caching/native needs:** Consistent gross basis; cache invalidated after import/resolution.

## S38 - CategoriesView

- **Exact Flutter file/class:** `lib/features/money/view/categories_view.dart::CategoriesView`.
- **Current route:** /money/categories.
- **Initial data-loading API IDs:** R04.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| R04: GET `/v1/categories/summary` | `query tax_year:str` | `{items:CategorySummary[],total_deductible_pence:int,personal_total_pence:int}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static report; some tiles falsely interactive.
- **Local caching/native needs:** One ledger category summary, dynamic counts/amounts.

## S39 - CategoryView

- **Exact Flutter file/class:** `lib/features/money/view/category_view.dart::CategoryView`.
- **Current route:** /money/category.
- **Initial data-loading API IDs:** R05.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| R05: GET `/v1/categories/{id}/transactions` | `query tax_year:str,limit:int=50,cursor:str?` | `{summary:CategorySummary,policy:BusinessUsePolicy,transactions:Page<Transaction>}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Waiting tile hides on confirmation; totals stay static.
- **Local caching/native needs:** Real category ID; page transactions; policy from server, no EE-only page assumption.

## S40 - BusinessUseView

- **Exact Flutter file/class:** `lib/features/money/view/business_use_view.dart::BusinessUseView`.
- **Current route:** /money/business-use.
- **Initial data-loading API IDs:** R05.
- **Create/update/delete or action-time IDs:** R07.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| R05: GET `/v1/categories/{id}/transactions` | `query tax_year:str,limit:int=50,cursor:str?` | `{summary:CategorySummary,policy:BusinessUsePolicy,transactions:Page<Transaction>}` |
| R07: PUT `/v1/categories/{id}/business-use` | `BusinessUsePolicy with expected_version:int` | `BusinessUsePolicy plus {affected_count:int,mutation_id:uuid}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Local preview; does not apply/persist.
- **Local caching/native needs:** Need category ID/version; preview from saved scope; refresh affected reports after save.

## S41 - PersonalView

- **Exact Flutter file/class:** `lib/features/money/view/personal_view.dart::PersonalView`.
- **Current route:** /money/personal.
- **Initial data-loading API IDs:** R06.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| R06: GET `/v1/reports/personal` | `query tax_year:str,limit:int=50,cursor:str?` | `{total_pence:int,count:int,by_category:CategorySummary[],transactions:Page<Transaction>}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static fuel/cleaning/meals report.
- **Local caching/native needs:** Page actual non-claim records and reason codes.

## S42 - ReceiptsView

- **Exact Flutter file/class:** `lib/features/money/view/receipts_view.dart::ReceiptsView`.
- **Current route:** /money/receipts.
- **Initial data-loading API IDs:** C02.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| C02: GET `/v1/receipts` | `query tax_year:str,review_status?:str,claim_status?:str,limit:int=50,cursor:str?` | `{items:Receipt[],next_cursor:str?,has_more:bool,counts:{all:int,pending:int,counted:int,not_claimed:int}}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Local fixture filter; statuses/counts never follow confirmations.
- **Local caching/native needs:** True status counts/thumbnails; update after confirmation/reversal; C07 content on demand.

## S43 - ExportView

- **Exact Flutter file/class:** `lib/features/money/view/export_view.dart::ExportView`.
- **Current route:** /money/export.
- **Initial data-loading API IDs:** S02.
- **Create/update/delete or action-time IDs:** E01 E02 E03 H01 H02.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| S02: GET `/v1/me/subscription` | `none` | `Subscription or {status:none,entitlements:str[]}` |
| E01: POST `/v1/exports` | `{tax_year:str,format:pdf/csv,include_photos:bool}` | `ExportJob` |
| E02: GET `/v1/exports/{id}` | `none` | `ExportJob` |
| E03: GET `/v1/exports/{id}/download` | `none` | `Binary PDF/CSV/ZIP or short-lived authorized redirect` |
| H01: POST `/v1/accountant-requests` | `{kind:books_handoff/marriage_allowance/filing_question,export_id:uuid?,recipient_reference:str,message:str?,consent_version:str}` | `AccountantRequest` |
| H02: GET `/v1/accountant-requests/{id}` | `none` | `AccountantRequest` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** UI-only export/share.
- **Local caching/native needs:** Selections local draft; poll job/download privately; accountant consent/recipient needed.

## S44 - TaxView

- **Exact Flutter file/class:** `lib/features/tax/view/tax_view.dart::TaxView`.
- **Current route:** /home -> AppTab.tax.
- **Initial data-loading API IDs:** T01 T02 T04 K01 U01.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| T01: GET `/v1/tax/estimate` | `query tax_year:str,as_of?:date` | `TaxEstimate` |
| T02: GET `/v1/tax/forecast` | `query tax_year:str,scenario:str=current_pace` | `Forecast` |
| T04: GET `/v1/tax/payment-timeline` | `query tax_year:str` | `PaymentTimeline` |
| K01: GET `/v1/tax-pot` | `query tax_year:str,limit:int=50,cursor:str?` | `PotSummary` |
| U01: GET `/v1/mtd/eligibility` | `query tax_year:str` | `MtdEligibility` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Only pot reactive; tax figures static.
- **Local caching/native needs:** Common tax snapshot; invalidate on ledger/profile/mileage/rule changes.

## S45 - WorkingsView

- **Exact Flutter file/class:** `lib/features/tax/view/workings_view.dart::WorkingsView`.
- **Current route:** /tax/workings.
- **Initial data-loading API IDs:** T01.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| T01: GET `/v1/tax/estimate` | `query tax_year:str,as_of?:date` | `TaxEstimate` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static income/expense/profit/tax steps.
- **Local caching/native needs:** Render server calculation breakdown, not independently recompute.

## S46 - AllowanceView

- **Exact Flutter file/class:** `lib/features/tax/view/allowance_view.dart::AllowanceView`.
- **Current route:** /tax/allowance.
- **Initial data-loading API IDs:** T01 P06.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| T01: GET `/v1/tax/estimate` | `query tax_year:str,as_of?:date` | `TaxEstimate` |
| P06: GET `/v1/me/tax-profile` | `query tax_year:str` | `TaxProfile` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static salary/allowance distribution.
- **Local caching/native needs:** Same combined-income/allowance snapshot; masked PAYE context.

## S47 - Class4View

- **Exact Flutter file/class:** `lib/features/tax/view/class4_view.dart::Class4View`.
- **Current route:** /tax/class-4.
- **Initial data-loading API IDs:** T01 T02 T05.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| T01: GET `/v1/tax/estimate` | `query tax_year:str,as_of?:date` | `TaxEstimate` |
| T02: GET `/v1/tax/forecast` | `query tax_year:str,scenario:str=current_pace` | `Forecast` |
| T05: GET `/v1/tax/rules` | `query tax_year:str,region:str` | `{id:uuid,tax_year:str,region:str,version:str,rules:{code:str,value:object,effective_from:date,effective_to:date?,official_url:str,verified_at:datetime}[]}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static thresholds/rates and oversimplified Class 2 copy.
- **Local caching/native needs:** Year/region-specific rates and NI eligibility.

## S48 - ForecastView

- **Exact Flutter file/class:** `lib/features/tax/view/forecast_view.dart::ForecastView`.
- **Current route:** /tax/forecast.
- **Initial data-loading API IDs:** T02.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| T02: GET `/v1/tax/forecast` | `query tax_year:str,scenario:str=current_pace` | `Forecast` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static 195/365 projection/mileage threshold date.
- **Local caching/native needs:** Cache by ledger/profile/rule/scenario/as_of; assumptions visible.

## S49 - PoaView

- **Exact Flutter file/class:** `lib/features/tax/view/poa_view.dart::PoaView`.
- **Current route:** /tax/payments-on-account.
- **Initial data-loading API IDs:** T04.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| T04: GET `/v1/tax/payment-timeline` | `query tax_year:str` | `PaymentTimeline` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static prior-year bill; incomplete eligibility rule.
- **Local caching/native needs:** Prior-year assessed liability/payment source required; estimate clearly marked.

## S50 - TimelineView

- **Exact Flutter file/class:** `lib/features/tax/view/timeline_view.dart::TimelineView`.
- **Current route:** /tax/timeline.
- **Initial data-loading API IDs:** T04 N04.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| T04: GET `/v1/tax/payment-timeline` | `query tax_year:str` | `PaymentTimeline` |
| N04: GET `/v1/deadlines` | `query tax_year:str` | `Deadline[]` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static payment schedule; no payment operation.
- **Local caching/native needs:** Canonical dates/payment estimates; How to pay link requires verified guidance/native URL handling.

## S51 - PotView

- **Exact Flutter file/class:** `lib/features/tax/view/pot_view.dart::PotView`.
- **Current route:** /tax/pot.
- **Initial data-loading API IDs:** K01 T01.
- **Create/update/delete or action-time IDs:** K02 K03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| K01: GET `/v1/tax-pot` | `query tax_year:str,limit:int=50,cursor:str?` | `PotSummary` |
| T01: GET `/v1/tax/estimate` | `query tax_year:str,as_of?:date` | `TaxEstimate` |
| K02: POST `/v1/tax-pot/entries` | `{amount_pence:int>0,occurred_on:date,note:str?}` | `{entry:PotEntry,summary:PotSummary}` |
| K03: POST `/v1/tax-pot/entries/{id}/reversals` | `{mutation_id:uuid,expected_version:int,reason:str}` | `{entry:PotEntry,summary:PotSummary}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Local log/undo; fixed target; not a money transfer.
- **Local caching/native needs:** Savings log owner/year cache; reverse exact entry and refresh target.

## S52 - TradingAllowanceView

- **Exact Flutter file/class:** `lib/features/tax/view/trading_allowance_view.dart::TradingAllowanceView`.
- **Current route:** /tax/trading-allowance.
- **Initial data-loading API IDs:** T03.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| T03: GET `/v1/tax/deduction-comparison` | `query tax_year:str` | `{expenses:TaxEstimate,trading_allowance:TaxEstimate,recommended_method:str,saving_pence:int,warnings:str[]}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static comparison; real costs here is total expenses, separate from vehicle election.
- **Local caching/native needs:** Render comparison with lawful alternative, not switch vehicle method.

## S53 - CarView

- **Exact Flutter file/class:** `lib/features/tax/view/car_view.dart::CarView`.
- **Current route:** /tax/car.
- **Initial data-loading API IDs:** V04 M01 T05.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| V04: GET `/v1/vehicles/{id}` | `none` | `Vehicle plus {tax_year:str,business_miles:decimal-string,deduction_pence:int,rule_set_id:uuid}` |
| M01: GET `/v1/mileage-logs` | `query tax_year:str,vehicle_id?:uuid,limit:int=50,cursor:str?` | `{items:MileageLog[],next_cursor:str?,has_more:bool,total_business_miles:decimal-string,deduction_pence:int,rule_set_id:uuid}` |
| T05: GET `/v1/tax/rules` | `query tax_year:str,region:str` | `{id:uuid,tax_year:str,region:str,version:str,rules:{code:str,value:object,effective_from:date,effective_to:date?,official_url:str,verified_at:datetime}[]}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static mileage regardless of onboarding actual-cost choice.
- **Local caching/native needs:** Actual selected vehicle/method; mileage summary shared with Driver/Home.

## S54 - MtdView

- **Exact Flutter file/class:** `lib/features/tax/view/mtd_view.dart::MtdView`.
- **Current route:** /tax/mtd.
- **Initial data-loading API IDs:** U01.
- **Create/update/delete or action-time IDs:** U02 U03.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| U01: GET `/v1/mtd/eligibility` | `query tax_year:str` | `MtdEligibility` |
| U02: POST `/v1/mtd/authorizations` | `{return_route:allowlisted-client-route}` | `{authorization_url:str,state_expires_at:datetime}` |
| U03: GET `/v1/mtd/oauth/callback` | `query code:str,state:str` | `Safe app redirect or {connection_status:str}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static thresholds; recognition-in-progress copy.
- **Local caching/native needs:** Connection setup extension; cache expiry/status, no provider tokens in client.

## S55 - MtdQuartersView

- **Exact Flutter file/class:** `lib/features/tax/view/mtd_quarters_view.dart::MtdQuartersView`.
- **Current route:** /tax/mtd/quarters.
- **Initial data-loading API IDs:** U04 U05 U10.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| U04: GET `/v1/mtd/businesses` | `none` | `MtdBusiness[]` |
| U05: GET `/v1/mtd/obligations` | `query tax_year:str,business_id?:uuid` | `Obligation[]` |
| U10: GET `/v1/mtd/updates` | `query tax_year:str,limit:int=50,cursor:str?` | `Page<MtdUpdate>` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Mock history/status; no property records.
- **Local caching/native needs:** Real identity/business IDs, no silent Mohammed switch.

## S56 - MtdSendView

- **Exact Flutter file/class:** `lib/features/tax/view/mtd_send_view.dart::MtdSendView`.
- **Current route:** /tax/mtd/send.
- **Initial data-loading API IDs:** U05 U06.
- **Create/update/delete or action-time IDs:** U07 U08 U09.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| U05: GET `/v1/mtd/obligations` | `query tax_year:str,business_id?:uuid` | `Obligation[]` |
| U06: POST `/v1/mtd/previews` | `{obligation_ids:str[]}` | `MtdPreview` |
| U07: POST `/v1/mtd/updates` | `{preview_id:uuid,snapshot_hash:str,consent_version:str}` | `MtdUpdate` |
| U08: GET `/v1/mtd/updates/{id}` | `none` | `MtdUpdate plus {business_results:{business_id:uuid,status:str,provider_reference_masked:str?,error_code:str?}[]}` |
| U09: GET `/v1/mtd/updates/{id}/confirmation` | `none` | `Binary private acknowledgement document or {business_references:object,accepted_at:datetime}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Mock HMRC success; no confirmation/document persisted.
- **Local caching/native needs:** Freeze preview/hash; poll per-business accepted/partial/unknown; confirmation private.

## S57 - OtherTaxView

- **Exact Flutter file/class:** `lib/features/tax/view/other_tax_view.dart::OtherTaxView`.
- **Current route:** /tax/other.
- **Initial data-loading API IDs:** P06 T01 T05.
- **Create/update/delete or action-time IDs:** P07 H01 H02.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| P06: GET `/v1/me/tax-profile` | `query tax_year:str` | `TaxProfile` |
| T01: GET `/v1/tax/estimate` | `query tax_year:str,as_of?:date` | `TaxEstimate` |
| T05: GET `/v1/tax/rules` | `query tax_year:str,region:str` | `{id:uuid,tax_year:str,region:str,version:str,rules:{code:str,value:object,effective_from:date,effective_to:date?,official_url:str,verified_at:datetime}[]}` |
| P07: PUT `/v1/me/tax-profile` | `{tax_year:str,region:str,has_paye_job:bool,employments:Employment[],property_income_pence:int?,interest_pence:int?,student_loan_plan:str?,marriage_allowance_status:str?,utr:str?,ni_number:str?,expected_version:int?}` | `TaxProfile` |
| H01: POST `/v1/accountant-requests` | `{kind:books_handoff/marriage_allowance/filing_question,export_id:uuid?,recipient_reference:str,message:str?,consent_version:str}` | `AccountantRequest` |
| H02: GET `/v1/accountant-requests/{id}` | `none` | `AccountantRequest` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** No list pagination needed for these static/detail/summary responses; do not fabricate pages.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Static hints; monthly VAT monitor absent.
- **Local caching/native needs:** Student-loan inputs/recipient consent require missing UI; tax context invalidates estimates.

## S58 - DriverView

- **Exact Flutter file/class:** `lib/features/driver/view/driver_view.dart::DriverView`.
- **Current route:** /home -> AppTab.driver.
- **Initial data-loading API IDs:** P04 V02 V04 M01 A06 S02.
- **Create/update/delete or action-time IDs:** none.
- **Required request/response fields and data models:** expanded per operation below; nested schemas/constraints in document06.

| ID / proposed method and endpoint | Required request/query/body | Required response/model |
| --- | --- | --- |
| P04: GET `/v1/me/driver-profile` | `none` | `DriverProfile` |
| V02: GET `/v1/vehicles` | `query active:bool=true,limit:int=50,cursor:str?` | `Page<Vehicle>` |
| V04: GET `/v1/vehicles/{id}` | `none` | `Vehicle plus {tax_year:str,business_miles:decimal-string,deduction_pence:int,rule_set_id:uuid}` |
| M01: GET `/v1/mileage-logs` | `query tax_year:str,vehicle_id?:uuid,limit:int=50,cursor:str?` | `{items:MileageLog[],next_cursor:str?,has_more:bool,total_business_miles:decimal-string,deduction_pence:int,rule_set_id:uuid}` |
| A06: GET `/v1/me` | `none` | `User` |
| S02: GET `/v1/me/subscription` | `none` | `Subscription or {status:none,entitlements:str[]}` |

- **Authentication:** Bearer owner session for private operations; F01/S01 public catalogs. U03 callback verifies server OAuth state instead of app JWT.
- **Pagination:** Use next_cursor/limit on listed Page/list operations; reset cursor when filters or year changes; summary/reference/detail responses bounded.
- **Errors/loading/empty:** Apply shared error handling above; show genuine loading/no-data/failure states. Keep pending uploads/submissions distinct from accepted/saved. Never convert a timeout into success.
- **Mock replacement:** Working links; static name/car/miles/language.
- **Local caching/native needs:** Static profile/plate/miles/language replaced with owner data.

## Modal/variant mapping

| Exact surface | Initial reads / writes | Data / cache / errors |
| --- | --- | --- |
| home/widget/first_day_home.dart::FirstDayHome | R01 has_data=false, P02/P04/V02; then vehicle/upload/receipt routes | Genuine empty ledger, not merely boolean while other tabs show fixture money; same owner bootstrap |
| home/widget/add_sheet.dart::AddSheet | Navigation only; opens C01/D01/L02/M02 flows | No API required to open menu. Log miles is an extension with missing form, not a working log action |
| home/widget/check_sheet.dart::CheckSheet | C02 pending receipt; C05 confirm/C06 reverse; Q01 mismatch queue | Preserve receipt/action ID; failures leave item pending; update dashboard counts/amounts atomically |
| onboarding/widget/lock_in_sheet.dart::LockInSheet | V04 eligibility; V05 election | Server validates/locks; hold alone is not success; 409 refetch/cannot-elect reason visible |
| money/widget/filter_sheet.dart::FilterSheet | F01/I01 options; L01 filtered list on submit | date range/source/category predicates all applied; clear resets query/cache key/cursor |

## Operations not mapped to an existing complete screen

M01-M04 support the visible Log miles gap and mileage figures but need a new form; V06 needs a complete correction flow; S04-S06 need provider and subscription management; H01/H02 need recipient/consent/request UX; U02/U03 need HMRC authorization; B01-B03 need a conversation screen. Foundations L04-L06/A05 and notification read-state behavior also require appropriate future edit/logout interactions. These are documented requirements, not implemented UI additions. Delete APIs never justify adding delete controls during this analysis task.

## Money tab predicate and draft mapping

L01 All has no kind predicate; Money in uses income; Expenses uses expense including known draft expenses; To check uses review_status=draft. C02/C03 cover incomplete/failed extractions that lack typed money values. Backend draft transactions are excluded from tax aggregates until confirmation. C05 creates or confirms the one linked draft; repeated confirms cannot create duplicate postings. Receipt/category/source IDs replace current fixture indices/display labels. See document06's ledger-draft policy for the proposed processing boundary.
