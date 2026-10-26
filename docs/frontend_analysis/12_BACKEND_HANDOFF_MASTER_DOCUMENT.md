# TaxiAiBooks backend handoff master document

Analysis date: 27 October 2026 (Asia/Dhaka). Source revision: `a5a9c4456ac190c0cb4bde9b4ae043f04f9a832f`. This is an analysis/documentation handoff; no Flutter/backend code was changed or implemented. This document is the entry point to the twelve-file pack. Read the detailed contracts and business/database requirements before building.

## Executive finding

TaxiAiBooks is a Flutter UI/demo for UK taxi and private-hire driver bookkeeping and tax management. It has meaningful local navigation, receipt confirmations/undo, savings logging, search/tabs and fixture reports. It has **zero observed backend API integrations**. Dio exists only as unused configured infrastructure. Authentication, real data persistence, camera/file acquisition, OCR/PDF parsing, exports, billing and HMRC submission are not implemented. Screen needs must never be mistaken for existing backend capabilities.

The user reports a separately developed Python FastAPI/PostgreSQL/SQLAlchemy2/Alembic/Pydanticv2/JWT/Compose backend containing registration/login/expense CRUD/tests. Its source/OpenAPI was not supplied and was not contacted. Treat those capabilities as UNVERIFIED until inspected; adapt/reuse them before adding parallel endpoints/tables.

## Auditable counts

| Item | Count / definition |
| --- | --- |
| Flutter source | 107 lib Dart files, 12,682 lines; two Dart test files |
| Primary screen classes | 58 classes, one primary class per features/*/view/*.dart file |
| Named route registrations | 54; four tab children are embedded in /home |
| Additional variants/surfaces | FirstDayHome empty state plus four sheets, excluded from58 |
| Source feature modules | Six: onboarding17 screens, shell1, home7, money18, tax14, driver1 |
| Existing API integrations | Zero request operations; one configured Dio client is not an integration |
| Proposed API operations | 93 unique method/path pairs:70 screen workflows,8 foundations,15 extensions |
| Proposed priority breakdown | P0=40, P1=36, P2=14, P3=3; requirements coverage, not MVP endpoint quota |
| Proposed PostgreSQL tables | 46 including audit/jobs/identity/integration extensions; none verified existing |
| Callback evidence | 184 definition sites including shared/forwarding/gesture callbacks, not unique actions |

## Actual technology and architecture

Installed Flutter3.44.1 stable/Dart3.12.1, confirmed by flutter --version; pubspec Dart^3.12.1, lockfile Flutter>=3.41.0. Package texi_ai_books version1.0.0+1. GetX4.7.3 state/DI/navigation, Dio5.11.1, flutter_svg2.3.0, Material3/Lexend/light theme. No Firebase, persistent local store, JWT middleware, secure storage, biometric/camera/file/notification/billing plugins or API DTO/repository layers.

lib/main.dart::main -> apps/app.dart::TexiAiBooksApp -> GetMaterialApp with InitialBinding and AppPages; startup /welcome. InitialBinding permanently registers ApiClient/BooksService. OnboardingController uses lazy fenix binding. ShellView hosts Home/Money/Tax/Driver in IndexedStack; ShellController selects tabs/Snap menu. Feature bindings lazily register small controllers; BooksService holds shared mutable demo receipts/pot/counts. Detailed folder/file/class index: document01.

API_BASE_URL is compile-time public config, empty by default; ApiClient has Accept application/json,15s connect/send and30s receive timeouts. No actual calls, interceptors, token storage/refresh, pagination, file transfers or transport error handling. No secrets/credentials are documented. Language metadata has seven choices but does not localize the app/apply global RTL. Themes/layout are fixed phone design; desktop boards absent.

## User journeys and what actually happens

1. Welcome -> how-it-works -> create-account. Apple/Google directly navigate to security; SMS button navigates to code. Any six digits pass locally; no SMS/provider verification. Face ID sign-in merely opens demo Home. Email/passcode-change/legal links do nothing.
2. Security toggles -> licence/council/work pattern -> platforms -> PAYE hint -> optional tax identifiers -> static vehicle -> claim-method hold -> earnings -> trial -> reminders -> demo Home. Many fields are unbound; none persist. Claim choice does not change later mileage screens. Both reminder completion buttons open populated Ali books because demo=true.
3. Home pending tile opens next-receipt sheet; confirm updates in-memory expenses/profit/20%-tax/count; four-second Undo removes last confirmation. Full Check lists three fixtures and Bolt difference. All Change links open EE regardless of selected receipt.
4. Snap -> drawn camera -> timed EE OCR -> review. Actual camera/file/OCR absent. Share slider updates preview but Save always posts fixed EE2600p locally and ignores edited merchant/date/amount/category. Manual fare/expense Add only closes screen.
5. Upload statement displays fixed Bolt success, even from Uber instructions. No file or ledger import. Bolt resolve changes status only, no income/fee/tax mutation. Real reconciliation and import are proposed.
6. Money search/tabs filter11 fixture records; filter-sheet date/source/category choices are ignored. Receipt filter works over9 fixtures despite51-label; details/reports are fixed. Home dynamic totals diverge from static Money/Year/Tax after confirmation.
7. Tax screens show worked examples/forecast/POA/timeline/vehicle guidance; savings pot additions/Undo work locally but target fixed. HMRC hold only sets sent=true and falsely claims saved acknowledgement; MTD examples switch persona to Mohammed/property. No HMRC interaction.
8. Export selections change labels but download/share do nothing. Notifications mark-all updates a bool; calendar success a bool; no scheduling/delivery. Driver hub links existing screens. AI/accountant/billing/mileage management mostly affordances or marketing.

## Complete screen and feature index

Every row references actual Dart source/class. Full components/actions/fields/controller/models/states are in document02; document03 contains exact callback lines; document10 maps all58 to requests/responses/cache/error behavior.

| ID / screen class | Exact file | Route | Purpose / current implementation |
| --- | --- | --- | --- |
| S01 `WelcomeView` | `lib/features/onboarding/view/welcome_view.dart` | /welcome | Introduce books and enter account flow; Working navigation; decorative demo figures |
| S02 `LanguageView` | `lib/features/onboarding/view/language_view.dart` | /language | Choose app/assistant language; Partial selection; no persisted preference/app locale |
| S03 `HowItWorksView` | `lib/features/onboarding/view/how_it_works_view.dart` | /how-it-works | Explain receipts/tax/accountant/assistant; Static marketing; integrations absent |
| S04 `CreateAccountView` | `lib/features/onboarding/view/create_account_view.dart` | /create-account | Registration; Mock auth; no SMS/OAuth |
| S05 `CodeView` | `lib/features/onboarding/view/code_view.dart` | /code | Represent SMS verification; Mock verification |
| S06 `SignInView` | `lib/features/onboarding/view/sign_in_view.dart` | /sign-in | Returning access; Mock auth; code path incorrectly leads through new-user setup |
| S07 `SecureView` | `lib/features/onboarding/view/secure_view.dart` | /secure | Device lock preferences; UI-only device protection |
| S08 `DrivingView` | `lib/features/onboarding/view/driving_view.dart` | /setup/driving | Licence/council/work pattern; Working local choices, unsaved |
| S09 `PlatformsView` | `lib/features/onboarding/view/platforms_view.dart` | /setup/platforms | Income sources; Working local choice; no provider connection |
| S10 `OtherIncomeView` | `lib/features/onboarding/view/other_income_view.dart` | /setup/other-income | PAYE/rent/savings context; Partial conditional UI; no captured salary |
| S11 `TaxDetailsView` | `lib/features/onboarding/view/tax_details_view.dart` | /setup/tax-details | Optional tax identifiers; UI-only sensitive-data collection |
| S12 `VehicleView` | `lib/features/onboarding/view/vehicle_view.dart` | /setup/vehicle | Vehicle lookup/confirmation; Mock lookup; no vehicle CRUD |
| S13 `ClaimMethodView` | `lib/features/onboarding/view/claim_method_view.dart` | /setup/claim-method | Mileage versus actual costs; Local choice only; later screens always mileage |
| S14 `EarningsView` | `lib/features/onboarding/view/earnings_view.dart` | /setup/earnings | Historic earnings entry choice; Mock import entry; manual totals missing |
| S15 `ReadingView` | `lib/features/onboarding/view/reading_view.dart` | /setup/reading | Onboarding statement results; Mock timed parser results |
| S16 `TrialView` | `lib/features/onboarding/view/trial_view.dart` | /setup/trial | Subscription offer; UI-only trial; no subscription created |
| S17 `RemindersView` | `lib/features/onboarding/view/reminders_view.dart` | /setup/reminders | Reminder choices/setup finish; Local choices; both actions open demo Home |
| S18 `ShellView` | `lib/features/shell/view/shell_view.dart` | /home | Main navigation container; Working tab/menu navigation |
| S19 `HomeView` | `lib/features/home/view/home_view.dart` | /home -> AppTab.home | Profit/tax/queue/week/miles/deadline; Reactive demo profit/tax/counts; date/week/miles hardcoded |
| S20 `WeekView` | `lib/features/home/view/week_view.dart` | /week | Weekly earnings/mileage/source report; Working local switching/percent allocation; no day drilldown |
| S21 `YearView` | `lib/features/home/view/year_view.dart` | /year | Annual report; Static report; never follows confirmations |
| S22 `CheckView` | `lib/features/home/view/check_view.dart` | /check | Confirm pending receipts/check mismatch; Local confirmation; wrong fixed EE editor for other receipts |
| S23 `BoltView` | `lib/features/home/view/bolt_view.dart` | /check/bolt | Missing Bolt fare; Partial: changes flag only, no income/fees/tax mutation |
| S24 `DatesView` | `lib/features/home/view/dates_view.dart` | /dates | Deadline list/calendar action; Mock calendar success; no calendar write |
| S25 `NotificationsView` | `lib/features/home/view/notifications_view.dart` | /notifications | Notification feed; Local bulk-read; five fixture notifications/three unread |
| S26 `MoneyView` | `lib/features/money/view/money_view.dart` | /home -> AppTab.money | Money tab overview; Static totals/latest; only pending count reactive |
| S27 `AllMoneyView` | `lib/features/money/view/all_money_view.dart` | /money/all | Money list/search; Local search/tabs work; filter controls ignored |
| S28 `IncomeView` | `lib/features/money/view/income_view.dart` | /money/income | Uber gross/fee/net detail; Static payout example |
| S29 `ExpenseView` | `lib/features/money/view/expense_view.dart` | /money/expense | NCP receipt confirmation; Local NCP confirmation; incorrect editor route |
| S30 `CameraView` | `lib/features/money/view/camera_view.dart` | /money/camera | Receipt capture representation; UI-only camera drawn receipt |
| S31 `ReadReceiptView` | `lib/features/money/view/read_receipt_view.dart` | /money/read-receipt | OCR representation; Mock OCR; no image processing |
| S32 `ReviewReceiptView` | `lib/features/money/view/review_receipt_view.dart` | /money/review-receipt | Edit extraction and claim share; Preview changes; save always fixed EE GBP 26; type ignored |
| S33 `AddFareView` | `lib/features/money/view/add_fare_view.dart` | /money/add-fare | Manual income; UI-only create; nothing saved |
| S34 `AddExpenseView` | `lib/features/money/view/add_expense_view.dart` | /money/add-expense | Manual expense without receipt; UI-only create; assumes mileage even after actual-cost selection |
| S35 `UploadView` | `lib/features/money/view/upload_view.dart` | /money/upload | Statement PDF upload; Mock upload; Uber instructions lead to Bolt success |
| S36 `StatementAddedView` | `lib/features/money/view/statement_added_view.dart` | /money/statement-added | Bolt import results; Static success; no income/fees imported |
| S37 `PlatformCheckView` | `lib/features/money/view/platform_check_view.dart` | /money/platform-check | Statements versus records; Bolt flag reactive; amounts hardcoded |
| S38 `CategoriesView` | `lib/features/money/view/categories_view.dart` | /money/categories | Category expense summary; Static report; some tiles falsely interactive |
| S39 `CategoryView` | `lib/features/money/view/category_view.dart` | /money/category | Phone bills/default share; Waiting tile hides on confirmation; totals stay static |
| S40 `BusinessUseView` | `lib/features/money/view/business_use_view.dart` | /money/business-use | Default phone work share; Local preview; does not apply/persist |
| S41 `PersonalView` | `lib/features/money/view/personal_view.dart` | /money/personal | Receipts kept without claim; Static fuel/cleaning/meals report |
| S42 `ReceiptsView` | `lib/features/money/view/receipts_view.dart` | /money/receipts | Receipt grid/status filters; Local fixture filter; statuses/counts never follow confirmations |
| S43 `ExportView` | `lib/features/money/view/export_view.dart` | /money/export | Accountant export options; UI-only export/share |
| S44 `TaxView` | `lib/features/tax/view/tax_view.dart` | /home -> AppTab.tax | Tax overview; Only pot reactive; tax figures static |
| S45 `WorkingsView` | `lib/features/tax/view/workings_view.dart` | /tax/workings | Explain tax calculation; Static income/expense/profit/tax steps |
| S46 `AllowanceView` | `lib/features/tax/view/allowance_view.dart` | /tax/allowance | Salary/allowance tax bands; Static salary/allowance distribution |
| S47 `Class4View` | `lib/features/tax/view/class4_view.dart` | /tax/class-4 | NI rules/explanation; Static thresholds/rates and oversimplified Class 2 copy |
| S48 `ForecastView` | `lib/features/tax/view/forecast_view.dart` | /tax/forecast | Year projection; Static 195/365 projection/mileage threshold date |
| S49 `PoaView` | `lib/features/tax/view/poa_view.dart` | /tax/payments-on-account | Advance tax explanation; Static prior-year bill; incomplete eligibility rule |
| S50 `TimelineView` | `lib/features/tax/view/timeline_view.dart` | /tax/timeline | Expected tax payment schedule; Static payment schedule; no payment operation |
| S51 `PotView` | `lib/features/tax/view/pot_view.dart` | /tax/pot | Record savings already moved; Local log/undo; fixed target; not a money transfer |
| S52 `TradingAllowanceView` | `lib/features/tax/view/trading_allowance_view.dart` | /tax/trading-allowance | Compare expense deduction/trading allowance; Static comparison; real costs here is total expenses, separate from vehicle election |
| S53 `CarView` | `lib/features/tax/view/car_view.dart` | /tax/car | Mileage car/exclusions explanation; Static mileage regardless of onboarding actual-cost choice |
| S54 `MtdView` | `lib/features/tax/view/mtd_view.dart` | /tax/mtd | MTD eligibility guidance; Static thresholds; recognition-in-progress copy |
| S55 `MtdQuartersView` | `lib/features/tax/view/mtd_quarters_view.dart` | /tax/mtd/quarters | Illustrative quarterly schedule; Mock history/status; no property records |
| S56 `MtdSendView` | `lib/features/tax/view/mtd_send_view.dart` | /tax/mtd/send | Review/send quarterly update; Mock HMRC success; no confirmation/document persisted |
| S57 `OtherTaxView` | `lib/features/tax/view/other_tax_view.dart` | /tax/other | VAT/student-loan/marriage guidance; Static hints; monthly VAT monitor absent |
| S58 `DriverView` | `lib/features/driver/view/driver_view.dart` | /home -> AppTab.driver | Profile/car hub; Working links; static name/car/miles/language |

FirstDayHome: lib/features/home/widget/first_day_home.dart. Sheets: home/widget/add_sheet.dart::AddSheet, home/widget/check_sheet.dart::CheckSheet, money/widget/filter_sheet.dart::FilterSheet, onboarding/widget/lock_in_sheet.dart::LockInSheet. All paths relative to lib/features unless fully prefixed.

## Backend target and request/response requirements

All endpoints below are **PROPOSED**, not existing. Canonical full per-operation requirements: document06. Server models use UUID/ISO dates/UTC timestamps, integer GBP pence and decimal-string mileage/percent. Driver-profile creation must atomically create/link default taxi business and return primary_business_id so transaction forms have valid ownership context. Resource IDs, never list indices or formatted labels, must flow into detail routes.

Use owner-scoped JWT sessions, public bounded reference catalogs, cursor paging on ledger/receipt/history lists, typed validation, normalized-or-compatible existing error envelopes and optimistic expected_version. Financial/job writes use idempotency and exact mutation/reversal IDs. Receipt draft does not affect tax until confirmed. Shared response schema definitions and all nested fields are expanded in document06; no real secrets/example credentials are included.

| ID / scope / priority | Proposed operation | Request/query schema | Response/model |
| --- | --- | --- | --- |
| A01 SCREEN P0 | POST `/v1/auth/challenges` | `{phone:str,purpose:sign_up/sign_in}` | `Challenge` |
| A02 SCREEN P0 | POST `/v1/auth/challenges/{id}/verify` | `{code:str exactly 6 digits}` | `Tokens` |
| A03 SCREEN P1 | POST `/v1/auth/providers/{provider}` | `{identity_token:str,nonce:str}` | `Tokens` |
| A04 FOUNDATION P0 | POST `/v1/auth/refresh` | `{refresh_token:str}` | `Tokens` |
| A05 FOUNDATION P0 | POST `/v1/auth/logout` | `{refresh_token:str?}` | `No content` |
| A06 FOUNDATION P0 | GET `/v1/me` | `none` | `User` |
| A07 SCREEN P0 | POST `/v1/auth/challenges/{id}/resend` | `none` | `Challenge` |
| P01 SCREEN P0 | PATCH `/v1/me` | `{first_name?:str,last_name?:str?,preferences?:Patch<Preferences>,expected_version:int}` | `User` |
| P02 SCREEN P0 | GET `/v1/me/onboarding` | `none` | `Onboarding` |
| P03 SCREEN P0 | PATCH `/v1/me/onboarding` | `{current_step?:int,completed_steps?:int[],skipped_fields?:str[],complete?:bool,expected_version:int}` | `Onboarding` |
| P04 SCREEN P0 | GET `/v1/me/driver-profile` | `none` | `DriverProfile` |
| P05 SCREEN P0 | PUT `/v1/me/driver-profile` | `DriverProfile excluding server-managed primary_business_id/version plus expected_version:int?` | `DriverProfile` |
| P06 SCREEN P0 | GET `/v1/me/tax-profile` | `query tax_year:str` | `TaxProfile` |
| P07 SCREEN P0 | PUT `/v1/me/tax-profile` | `{tax_year:str,region:str,has_paye_job:bool,employments:Employment[],property_income_pence:int?,interest_pence:int?,student_loan_plan:str?,marriage_allowance_status:str?,utr:str?,ni_number:str?,expected_version:int?}` | `TaxProfile` |
| F01 SCREEN P0 | GET `/v1/reference-data` | `query locale:str=en` | `{version:str,languages:{code:str,native:str,english:str,rtl:bool}[],councils:{code:str,name:str}[],licence_types:str[],sources:IncomeSource[],categories:Category[],upload_limits:{max_bytes:int,mime_types:str[]}}` |
| V01 SCREEN P1 | POST `/v1/vehicles/lookup` | `{registration:str}` | `{registration:str,make:str?,model:str?,year:int?,colour:str?,fuel:str?,lookup_status:found/not_found/unavailable}` |
| V02 SCREEN P0 | GET `/v1/vehicles` | `query active:bool=true,limit:int=50,cursor:str?` | `Page<Vehicle>` |
| V03 SCREEN P0 | POST `/v1/vehicles` | `VehicleInput` | `Vehicle` |
| V04 SCREEN P0 | GET `/v1/vehicles/{id}` | `none` | `Vehicle plus {tax_year:str,business_miles:decimal-string,deduction_pence:int,rule_set_id:uuid}` |
| V05 SCREEN P0 | POST `/v1/vehicles/{id}/claim-method` | `{method:mileage/actual,effective_from:date,prior_capital_allowances:bool,prior_vehicle_expense_claim:bool,acknowledgement_version:str,expected_version:int}` | `Vehicle plus {election_id:uuid,mutation_id:uuid}` |
| V06 EXTENSION P1 | PATCH `/v1/vehicles/{id}` | `Patch<VehicleInput> plus expected_version:int` | `Vehicle` |
| I01 SCREEN P0 | GET `/v1/me/income-sources` | `none` | `IncomeSource[]` |
| I02 SCREEN P0 | PUT `/v1/me/income-sources` | `{source_ids:uuid[]}` | `IncomeSource[]` |
| L01 SCREEN P0 | GET `/v1/transactions` | `query tax_year?:str,from?:date,to?:date,kind?:income/expense,review_status?:str,claim_status?:str,source_ids?:uuid[],category_ids?:uuid[],q?:str,limit:int=50,cursor:str?` | `Page<Transaction>` |
| L02 SCREEN P0 | POST `/v1/transactions` | `TransactionInput` | `Transaction` |
| L03 SCREEN P0 | GET `/v1/transactions/{id}` | `none` | `Transaction plus {payout:Payout?,receipt:Receipt?}` |
| L04 FOUNDATION P0 | PATCH `/v1/transactions/{id}` | `Patch<TransactionInput> plus expected_version:int` | `Transaction` |
| L05 FOUNDATION P0 | DELETE `/v1/transactions/{id}` | `query expected_version:int,reason:str` | `No content` |
| L06 FOUNDATION P0 | POST `/v1/transactions/{id}/reversals` | `{mutation_id:uuid,reason:str,expected_version:int}` | `Transaction` |
| R01 SCREEN P0 | GET `/v1/dashboard` | `query tax_year:str` | `Dashboard` |
| R02 SCREEN P0 | GET `/v1/reports/weekly` | `query start_on:date,business_id:uuid?` | `WeeklyReport` |
| R03 SCREEN P1 | GET `/v1/reports/annual` | `query tax_year:str` | `AnnualReport` |
| R04 SCREEN P0 | GET `/v1/categories/summary` | `query tax_year:str` | `{items:CategorySummary[],total_deductible_pence:int,personal_total_pence:int}` |
| R05 SCREEN P0 | GET `/v1/categories/{id}/transactions` | `query tax_year:str,limit:int=50,cursor:str?` | `{summary:CategorySummary,policy:BusinessUsePolicy,transactions:Page<Transaction>}` |
| R06 SCREEN P1 | GET `/v1/reports/personal` | `query tax_year:str,limit:int=50,cursor:str?` | `{total_pence:int,count:int,by_category:CategorySummary[],transactions:Page<Transaction>}` |
| R07 SCREEN P0 | PUT `/v1/categories/{id}/business-use` | `BusinessUsePolicy with expected_version:int` | `BusinessUsePolicy plus {affected_count:int,mutation_id:uuid}` |
| C01 SCREEN P1 | POST `/v1/receipts` | `multipart file:binary,business_id:uuid,vehicle_id:uuid?` | `{receipt:Receipt,job:Job}` |
| C02 SCREEN P1 | GET `/v1/receipts` | `query tax_year:str,review_status?:str,claim_status?:str,limit:int=50,cursor:str?` | `{items:Receipt[],next_cursor:str?,has_more:bool,counts:{all:int,pending:int,counted:int,not_claimed:int}}` |
| C03 SCREEN P1 | GET `/v1/receipts/{id}` | `none` | `Receipt plus {job:Job?,extraction:{merchant:str?,occurred_on:date?,amount_pence:int?,vat_pence:int?,confidence:decimal-string?}?}` |
| C04 SCREEN P1 | PATCH `/v1/receipts/{id}` | `{merchant?:str,occurred_on?:date,amount_pence?:int,vat_pence?:int?,category_id?:uuid,business_use_percent?:decimal-string,claim_status?:str,expected_version:int}` | `Receipt` |
| C05 SCREEN P1 | POST `/v1/receipts/{id}/confirmations` | `{claim_status:claimable/personal/excluded,category_id:uuid,business_use_percent:decimal-string,expected_version:int}` | `{receipt:Receipt,transaction:Transaction,mutation_id:uuid,dashboard:Dashboard}` |
| C06 SCREEN P1 | POST `/v1/receipts/{id}/reversals` | `{mutation_id:uuid,reason:str,expected_version:int}` | `{receipt:Receipt,transaction:Transaction,dashboard:Dashboard}` |
| C07 SCREEN P1 | GET `/v1/receipts/{id}/content` | `none` | `Binary receipt image/PDF or short-lived authorized redirect` |
| C08 FOUNDATION P1 | POST `/v1/receipts/{id}/ocr-retries` | `{expected_version:int}` | `{receipt:Receipt,job:Job}` |
| D01 SCREEN P1 | POST `/v1/statements` | `multipart file:binary,source_id:uuid,business_id:uuid` | `{statement:Statement,job:Job}` |
| D02 SCREEN P1 | GET `/v1/statements` | `query tax_year:str,source_id?:uuid,limit:int=50,cursor:str?` | `Page<Statement>` |
| D03 SCREEN P1 | GET `/v1/statements/{id}` | `none` | `Statement` |
| D04 SCREEN P1 | POST `/v1/statements/{id}/imports` | `{expected_version:int,acknowledged_warning_codes:str[]}` | `{statement:Statement,transaction_ids:uuid[],issues:ReconciliationIssue[],mutation_id:uuid}` |
| D05 SCREEN P1 | GET `/v1/statements/{id}/content` | `none` | `Binary private PDF or short-lived authorized redirect` |
| Q01 SCREEN P1 | GET `/v1/reconciliations` | `query tax_year:str,source_id?:uuid,status?:str,limit:int=50,cursor:str?` | `{items:ReconciliationIssue[],next_cursor:str?,has_more:bool,platform_totals:{source_id:uuid,statement_gross_pence:int,recorded_gross_pence:int,difference_pence:int}[]}` |
| Q02 SCREEN P1 | GET `/v1/reconciliations/{id}` | `none` | `ReconciliationIssue` |
| Q03 SCREEN P1 | POST `/v1/reconciliations/{id}/resolutions` | `{mode:add_missing/link_existing,transaction_ids:uuid[]=[],new_transactions:TransactionInput[]=[],evidence_note:str?,expected_version:int}` | `{issue:ReconciliationIssue,transaction_ids:uuid[],resolution_id:uuid,mutation_id:uuid,dashboard:Dashboard}` |
| Q04 SCREEN P1 | POST `/v1/reconciliations/{id}/reversals` | `{resolution_id:uuid,mutation_id:uuid,reason:str,expected_version:int}` | `{issue:ReconciliationIssue,dashboard:Dashboard}` |
| M01 EXTENSION P0 | GET `/v1/mileage-logs` | `query tax_year:str,vehicle_id?:uuid,limit:int=50,cursor:str?` | `{items:MileageLog[],next_cursor:str?,has_more:bool,total_business_miles:decimal-string,deduction_pence:int,rule_set_id:uuid}` |
| M02 EXTENSION P0 | POST `/v1/mileage-logs` | `MileageLog excluding id/version` | `MileageLog plus {deduction_pence:int,mutation_id:uuid}` |
| M03 EXTENSION P0 | PATCH `/v1/mileage-logs/{id}` | `Patch<MileageLog> excluding id/version plus expected_version:int` | `MileageLog` |
| M04 EXTENSION P0 | DELETE `/v1/mileage-logs/{id}` | `query expected_version:int,reason:str` | `No content` |
| T01 SCREEN P0 | GET `/v1/tax/estimate` | `query tax_year:str,as_of?:date` | `TaxEstimate` |
| T02 SCREEN P1 | GET `/v1/tax/forecast` | `query tax_year:str,scenario:str=current_pace` | `Forecast` |
| T03 SCREEN P1 | GET `/v1/tax/deduction-comparison` | `query tax_year:str` | `{expenses:TaxEstimate,trading_allowance:TaxEstimate,recommended_method:str,saving_pence:int,warnings:str[]}` |
| T04 SCREEN P1 | GET `/v1/tax/payment-timeline` | `query tax_year:str` | `PaymentTimeline` |
| T05 SCREEN P0 | GET `/v1/tax/rules` | `query tax_year:str,region:str` | `{id:uuid,tax_year:str,region:str,version:str,rules:{code:str,value:object,effective_from:date,effective_to:date?,official_url:str,verified_at:datetime}[]}` |
| K01 SCREEN P0 | GET `/v1/tax-pot` | `query tax_year:str,limit:int=50,cursor:str?` | `PotSummary` |
| K02 SCREEN P0 | POST `/v1/tax-pot/entries` | `{amount_pence:int>0,occurred_on:date,note:str?}` | `{entry:PotEntry,summary:PotSummary}` |
| K03 SCREEN P0 | POST `/v1/tax-pot/entries/{id}/reversals` | `{mutation_id:uuid,expected_version:int,reason:str}` | `{entry:PotEntry,summary:PotSummary}` |
| N01 SCREEN P1 | GET `/v1/notifications` | `query unread_only:bool=false,limit:int=50,cursor:str?` | `{items:Notification[],next_cursor:str?,has_more:bool,unread_count:int}` |
| N02 FOUNDATION P1 | PATCH `/v1/notifications/{id}` | `{read:bool}` | `Notification` |
| N03 SCREEN P1 | POST `/v1/notifications/read-all` | `{through:datetime}` | `{updated_count:int,unread_count:int}` |
| N04 SCREEN P1 | GET `/v1/deadlines` | `query tax_year:str` | `Deadline[]` |
| E01 SCREEN P1 | POST `/v1/exports` | `{tax_year:str,format:pdf/csv,include_photos:bool}` | `ExportJob` |
| E02 SCREEN P1 | GET `/v1/exports/{id}` | `none` | `ExportJob` |
| E03 SCREEN P1 | GET `/v1/exports/{id}/download` | `none` | `Binary PDF/CSV/ZIP or short-lived authorized redirect` |
| H01 EXTENSION P2 | POST `/v1/accountant-requests` | `{kind:books_handoff/marriage_allowance/filing_question,export_id:uuid?,recipient_reference:str,message:str?,consent_version:str}` | `AccountantRequest` |
| H02 EXTENSION P2 | GET `/v1/accountant-requests/{id}` | `none` | `AccountantRequest` |
| S01 SCREEN P1 | GET `/v1/subscription-plans` | `query locale:str=en` | `Plan[]` |
| S02 SCREEN P1 | GET `/v1/me/subscription` | `none` | `Subscription or {status:none,entitlements:str[]}` |
| S03 SCREEN P1 | POST `/v1/me/subscription/trial` | `{plan_id:uuid,terms_version:str}` | `Subscription` |
| S04 EXTENSION P2 | POST `/v1/billing/webhooks/{provider}` | `Raw provider event plus signature headers; schema determined by selected provider` | `{received:bool}` |
| S05 EXTENSION P2 | POST `/v1/me/subscription/checkout` | `{plan_id:uuid,return_route:allowlisted-client-route}` | `{session_id:str,checkout_url:str?,expires_at:datetime?,provider:str}` |
| S06 EXTENSION P2 | POST `/v1/me/subscription/cancellation` | `{reason:str?}` | `Subscription` |
| U01 SCREEN P1 | GET `/v1/mtd/eligibility` | `query tax_year:str` | `MtdEligibility` |
| U02 EXTENSION P2 | POST `/v1/mtd/authorizations` | `{return_route:allowlisted-client-route}` | `{authorization_url:str,state_expires_at:datetime}` |
| U03 EXTENSION P2 | GET `/v1/mtd/oauth/callback` | `query code:str,state:str` | `Safe app redirect or {connection_status:str}` |
| U04 SCREEN P2 | GET `/v1/mtd/businesses` | `none` | `MtdBusiness[]` |
| U05 SCREEN P2 | GET `/v1/mtd/obligations` | `query tax_year:str,business_id?:uuid` | `Obligation[]` |
| U06 SCREEN P2 | POST `/v1/mtd/previews` | `{obligation_ids:str[]}` | `MtdPreview` |
| U07 SCREEN P2 | POST `/v1/mtd/updates` | `{preview_id:uuid,snapshot_hash:str,consent_version:str}` | `MtdUpdate` |
| U08 SCREEN P2 | GET `/v1/mtd/updates/{id}` | `none` | `MtdUpdate plus {business_results:{business_id:uuid,status:str,provider_reference_masked:str?,error_code:str?}[]}` |
| U09 SCREEN P2 | GET `/v1/mtd/updates/{id}/confirmation` | `none` | `Binary private acknowledgement document or {business_references:object,accepted_at:datetime}` |
| U10 SCREEN P2 | GET `/v1/mtd/updates` | `query tax_year:str,limit:int=50,cursor:str?` | `Page<MtdUpdate>` |
| B01 EXTENSION P3 | POST `/v1/assistant/conversations` | `{locale:str,context_resource_ids:uuid[]=[],consent_version:str}` | `Conversation` |
| B02 EXTENSION P3 | POST `/v1/assistant/conversations/{id}/messages` | `{content:str,client_message_id:uuid}` | `{user_message:Message,assistant_message:Message}` |
| B03 EXTENSION P3 | GET `/v1/assistant/conversations/{id}/messages` | `query limit:int=50,cursor:str?` | `Page<Message>` |

SCREEN=supports represented workflow; FOUNDATION=required supporting behavior; EXTENSION=full UI/integration absent. Fifteen extension operations cover vehicle correction, mileage log, accountant requests, paid billing, HMRC authorization and assistant conversation. Not all are MVP. Mileage evidence is P0 because estimates otherwise lack evidence, even though its form is absent. Spreadsheet CSV is a proposed review decision, not an observed contract. Provider-specific Apple/Google/billing/HMRC payloads must follow selected provider documentation and verified backend compatibility.

## Data and database requirements

Dart domain-like fixtures: ReceiptToCheck (books_service.dart), Language/ClaimMethod (onboarding_controller.dart), DayEarnings/WeekData (week_controller.dart), MoneyItem/MoneyKind (all_money_controller.dart). ReceiptsView owns separate tuples/ReceiptStatus. No fromJson/toJson serializers. MoneyItem uses display strings for amount/day and receipt identity is index; do not copy this into SQL design. Document04 gives fields/types/required/default/nullability and full controller state.

Document08 proposes46 tables with column types/PKs/FKs/uniqueness/indexes and privacy/lifecycle rules. Core groups: users/auth/profiles/onboarding/PAYE; businesses/vehicles/elections/sources/categories/work-share; transactions/mileage/receipts/extractions/files/jobs; statements/payouts/reconciliation; verified rules/estimates/payments/pot; notifications; export/consent/accountant; subscription/provider events; HMRC connection/obligations/previews/per-business updates; assistant/audit/idempotency.

Use SQLAlchemy2 typed models and per-request/task sessions, Pydanticv2 constrained request/output schemas/from_attributes, PostgreSQL UUID/BIGINT/NUMERIC/DATE/TIMESTAMPTZ, Alembic migrations. Read existing backend schemas first. Composite same-owner references, private object access, encrypted UTR/NI/provider tokens with external keys, masked outputs and redacted append-only audit are required. Core financial history is reversed/voided, not silently deleted. Provider callback/webhook security differs from user JWT. No migration/deployment performed here.

## Business rules and consistency

Book gross fare income and separate fees; net payout is never a second income posting. Derive aggregates from one confirmed ledger version. Expense claim depends on eligible category/vehicle method/effective work share; personal records retained without deduction. Receipt edit+confirm and statement import/resolution are atomic/idempotent and exactly reversible. Correcting EE75% must save3900p, not fixed2600p. Resolving Bolt must post/link actual income/fees and update totals, not merely clear a flag.

The UI55p mileage band is a 2026-27 design input checked against official guidance; eligibility/history still require review, especially Hackney/commercial-use vehicles. Published tax-rule versions/region/PAYE context and prior liabilities are mandatory; flat20% is fixture arithmetic. Forecast mileage crosses bands; do not scale current mileage deduction linearly. Trading allowance versus total expense deduction differs from vehicle mileage versus actual-cost election. Pot is savings logging only. Full extracted assumptions, official source links and acceptance examples: document07.

Subscriptions need actual cohort/terms/trial/server dates and verified provider entitlements. Accountant handoff requires verified recipient and explicit scoped consent. MTD needs recognition/OAuth/obligations, immutable validated snapshot, per-business outcomes, unknown-timeout reconciliation and actual acknowledgement retention. No success based solely on hold/timer/queue.

## Critical gaps and unresolved product decisions

Critical: fake auth; Add buttons do not save; ignored receipt edits/claim mismatch; Bolt status without ledger change; simulated HMRC acceptance; hardcoded/divergent tax reports; no vehicle eligibility gate; no persistence. Also ignored filters, wrong receipt editor, fixed dates/counts/language, missing loading/errors/caching and no native integrations. No actual API keys/passwords/secrets are included.

Missing complete features: Dart splash, mileage form/tracking, vehicle management/rental branch, assistant conversations, accountant module, purchase/manage/cancel, unified settings/logout/delete, property records, global localization/RTL and desktop layouts. Export/download/share and real capture/OCR/import are placeholders.

Resolve in feature phase: OTP/providers versus backend password/email; vehicle eligibility/history; supported tax regions/years/PAYE/loans; historic totals/prior assessed liability inputs; work-share retrospective policy/period locking; supported statement formats/refunds/tips/duplicates; CSV/XLSX/recipient consent; billing terms/provider; HMRC recognition/payloads/final-return owner; hosting/retention/address minimization and assistant privacy. Document11 links findings to exact classes, assigns severity and lists decisions without fixing code.

## Recommended implementation order and dependencies

1. Verify/reuse external auth/expense contracts/tests; establish identity, tenant ownership, API/error/idempotency conventions.
2. Save user/onboarding/driver/default taxi business, PAYE/preferences/sources/reference data; publish verified tax rules.
3. Vehicle eligibility/election, canonical manual income/expense, business-use policy and manual mileage evidence (missing form separately specified).
4. Consistent dashboard/weekly estimate and durable savings log, meaningful core ledger tests.
5. Private upload/worker pipeline, actual OCR review, parsed statement preview/import, reconciliation/reversals.
6. Annual/category/personal reports, forecast/POA/prior payments, deadlines/notifications, export and actual trial offers.
7. Verified accountant/paid billing and recognized HMRC authorization/submission, then consented assistant/localization/desktop extensions.

Document09 contains P0-P3 matrix/dependency diagram and acceptance criteria. Feature completeness, financial consistency and provider evidence determine release readiness, not number of screens built.

## Documentation pack

| File | Purpose |
| --- | --- |
| [01_PROJECT_ARCHITECTURE.md](01_PROJECT_ARCHITECTURE.md) | Stack, startup/DI/routing/config/platform and complete Dart class/file index |
| [02_SCREEN_INVENTORY.md](02_SCREEN_INVENTORY.md) | All58 screen analyses, empty variant, sheets and absent modules |
| [03_FEATURE_FUNCTIONALITY.md](03_FEATURE_FUNCTIONALITY.md) | Traced effects/statuses, no-ops and source callback evidence |
| [04_DATA_MODELS.md](04_DATA_MODELS.md) | Actual fixture models, fields/defaults/enums/state and model gaps |
| [05_EXISTING_API_INTEGRATIONS.md](05_EXISTING_API_INTEGRATIONS.md) | Zero observed operations; Dio-only infrastructure; reported backend caveat |
| [06_BACKEND_API_REQUIREMENTS.md](06_BACKEND_API_REQUIREMENTS.md) |93 proposed operations, reusable typed schemas, validation/auth/logic/errors/dependencies |
| [07_BUSINESS_RULES.md](07_BUSINESS_RULES.md) | Observed arithmetic versus requirements and official tax verification |
| [08_DATABASE_REQUIREMENTS.md](08_DATABASE_REQUIREMENTS.md) |46 proposed tables, constraints/indexes/security and relationships |
| [09_IMPLEMENTATION_ROADMAP.md](09_IMPLEMENTATION_ROADMAP.md) | P0-P3 scope/dependencies/order/acceptance |
| [10_FLUTTER_BACKEND_MAPPING.md](10_FLUTTER_BACKEND_MAPPING.md) | All58 screens to APIs, fields/models/auth/paging/errors/mocks/cache |
| [11_MISSING_FEATURES.md](11_MISSING_FEATURES.md) | Critical issues, incomplete/no-op/absent features and product decisions |
| [12_BACKEND_HANDOFF_MASTER_DOCUMENT.md](12_BACKEND_HANDOFF_MASTER_DOCUMENT.md) | This self-contained overview and handoff index |

## Review method and verification limits

Read source/config/tests and traced routes, callbacks, models/DI, in-memory mutations and network usage; searched for auth/storage/Firebase/DTO/request/file integrations and inventoried native scaffolds. Inspected both existing test files without running Flutter tests/analyzer, since this documentation task changes no code and those checks do not verify prose requirements. No emulator/backend connection/release build/runtime provider validation was performed. Local installed SDK was queried read-only. Official tax/technical references support selected requirements only, with links in documents06/07.

Validation results will be recorded below after checking documentation completeness, API/screen counts, links/source references and non-document file preservation.

## Completed documentation validation

- Twelve required Markdown filenames exist and are nonempty; internal document links and referenced literal lib Dart paths resolve.
- All58 primary screen classes appear exactly once in both screen inventory and screen/API mapping; source route registrations count54.
- API catalog has93 distinct method/path pairs with stable IDs; scopes70 screen/8 foundation/15 extension; priority counts40/36/14/3.
- All184 callback definition sites are indexed against source line numbers;46 proposed database tables documented.
- Hash comparison of266 pre-existing non-generated, non-document workspace files found no changes and no new non-document files. The pre-existing Git deletion under android/.kotlin/sessions was left as found.
- No Flutter tests/analyzer, backend tests, network endpoints or provider integrations were run. These checks validate source coverage/document structure and preservation, not production behavior or the proposed financial/tax contracts.

Final integration clarification: usable OCR results may create an unconfirmed draft transaction; C05 creates or confirms that single record. Drafts stay out of deductible aggregates. AllMoney tabs translate to kind/review filters; incomplete extractions remain in receipt queue. Document06 contains that policy and the default taxi-business ownership bootstrap, which must be implemented before forms can submit valid business IDs.

Name-collection decision: signup has no name field; proposed user names remain nullable until a specified profile step supplies them. Never seed real users with the demo persona.
