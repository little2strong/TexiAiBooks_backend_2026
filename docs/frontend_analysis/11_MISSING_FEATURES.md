# Quality, gaps and product decisions

Analysis: 27 October 2026. Findings are source-based unless labelled proposed. No fixes implemented. Severity indicates impact if current demo behavior were treated as a production bookkeeping application.

## Critical findings

| ID / severity | Evidence: exact file/class | Observed issue / impact | Required decision or future fix |
| --- | --- | --- | --- |
| G01 Critical | onboarding/controller/onboarding_controller.dart::OnboardingController.signIn/finish; onboarding/view/code_view.dart::CodeView | No identity verification; any six digits proceed, Face ID tile simply navigates; every user sees demo Ali | Real backend auth/session, native biometric policy, auth guards; reconcile existing backend auth contract |
| G02 Critical | money/view/add_fare_view.dart::AddFareView; add_expense_view.dart::AddExpenseView | Add only Get.back; amount/date/note/reason not captured; false impression of saving | Bind/validate real forms then persist transaction; not done in this task |
| G03 Critical | money/controller/receipt_controllers.dart::ReviewReceiptController.save | Slider/category preview differs from books: always fixed EE2600p; shop/date/amount edits ignored | Confirm typed reviewed values atomically and return canonical claim/totals |
| G04 Critical | home/controller/bolt_controller.dart::BoltController.addTrip | Resolved flag/success text without adding4260p income or fees; tax preview never applied | Resolve through canonical ledger and exact reversal |
| G05 Critical | tax/view/mtd_send_view.dart::MtdSendView; tax/controller/tax_controllers.dart::MtdSendController | Holding sets sent=true; says HMRC confirmation saved despite no network or file store | Gate real authorized send by recognition/connection/preview; display accepted only on actual acknowledgement |
| G06 Critical | core/services/books_service.dart::BooksService; tax/view/*.dart | Flat20% demo arithmetic, fixed tax target and independent static tax reports | Verified year/region tax engine and consistent snapshot; figures not universal legal rules |
| G07 Critical | onboarding/view/driving_view.dart::DrivingView; claim_method_view.dart::ClaimMethodView | Hackney choice still allows unscreened mileage election | HMRC vehicle eligibility/history gate; official vehicle restrictions checked in document07 |
| G08 High | core/services/books_service.dart::BooksService.demo/hasData | demo=true forces populated books after signup; no persistence | True owner data/empty state; demo isolation; no cross-user memory leakage after future auth |

## Functional and data consistency gaps

| ID | Evidence | Finding |
| --- | --- | --- |
| G09 | home/view/check_view.dart::CheckView; home/widget/check_sheet.dart::CheckSheet; money/view/expense_view.dart::ExpenseView | Every Change opens ReviewReceiptView's EE fixture without receipt ID, including NCP/Shell |
| G10 | money/controller/all_money_controller.dart::AllMoneyController.groups; money/widget/filter_sheet.dart::FilterSheet | Date/source/category filters ignored; Pick dates opens no date picker; Show results only dismisses |
| G11 | money/view/money_view.dart::MoneyView; home/view/year_view.dart::YearView; tax/view/tax_view.dart::TaxView | Hardcoded totals diverge from reactive Home after confirms; category historical totals and grid statuses remain unchanged |
| G12 | money/view/business_use_view.dart::BusinessUseView; receipt_controllers.dart::BusinessUseController | Save goes back; percent isolated from receipt/category/defaults; 20% saving only fixture |
| G13 | onboarding/controller/onboarding_controller.dart::OnboardingController.claimMethod; money/controller/entry_controllers.dart::AddExpenseController.isFuel; tax/view/car_view.dart::CarView | Actual-cost choice never changes later mileage/fuel behavior; locked bool is not durable/enforced election |
| G14 | money/view/upload_view.dart::UploadView; onboarding/view/earnings_view.dart::EarningsView | Upload uses no picker; onboarding directly opens reading; Uber pick leads to Bolt result; platform selection not stored |
| G15 | money/view/camera_view.dart::CameraView; read_receipt_view.dart::ReadReceiptView; onboarding/view/reading_view.dart::ReadingView | Drawn receipts/timer results, no camera/image/OCR/PDF parser; loading success not tied to work |
| G16 | home/controller/week_controller.dart::WeekController | Only two weeks; percents divides by zero for zero totals; no empty list guard/general no-data report |
| G17 | home/view/week_view.dart::WeekView | Mileage always week.miles*55, ignoring prior accumulated threshold crossing |
| G18 | core/services/books_service.dart::BooksService.undoConfirm/undoPot; core/widgets/feedback.dart::UndoToastMixin | Remove-last global undo can target a newer action; multiple screens/toasts share mutable state, no operation/version IDs |
| G19 | money/view/receipts_view.dart::ReceiptsView | Nine fixture thumbnails advertised as51; filter counts21/27/3 don't update with confirmation; several thumbnails no-op |
| G20 | tax/view/mtd_quarters_view.dart::MtdQuartersView/MohammedAvatar; mtd_send_view.dart::MtdSendView | Persona silently changes Ali to Mohammed/property; no identity/business switch or property ledger |
| G21 | home/view/dates_view.dart::DatesView | Calendar success just bool; static17Oct date/countdowns obsolete as clock moves |
| G22 | home/view/notifications_view.dart::NotificationsView; onboarding/view/reminders_view.dart::RemindersView | Feed/read flags local; no permission/delivery/scheduler; Turn on/Not now same finish path |
| G23 | onboarding/view/other_income_view.dart::OtherIncomeView; tax_details_view.dart::TaxDetailsView | PAYE/employer/pay/UTR/NI fields not bound; rent/interest static; no tax-profile capture |
| G24 | onboarding/view/vehicle_view.dart::VehicleView | Plate changes don't look up anything; result fixed; owned/rented answer static; incorrect result empty |
| G25 | onboarding/view/sign_in_view.dart::SignInView; code_view.dart::CodeView | SMS login goes to signup security/setup; static displayed phone unrelated to typed phone |
| G26 | tax/view/pot_view.dart::PotView; core/services/books_service.dart::BooksService.potTargetPence | Target remains122450p after confirmed deductions; initial savings90000p not represented in log |
| G27 | core/widgets/fields.dart::AppTextField and form views | No Form/validator/onSaved; numeric keyboard not validation; dates amount strings not parsed; NI uppercase keyboard not validation |
| G28 | all controller/view data | No stable record IDs, typed date/currency schemas, pagination, cancellation, async failures/retries, offline/cache policy or session expiry handling |

## Unimplemented actions and missing modules

No-op callback source index is in document03. Important no-ops: Ask/assistant everywhere; Log miles; Type historic totals; Add Bolt onboarding import; email recovery; Change passcode; Terms/Privacy links; camera flash/photos; statement open; export/download/accountant share; payment guidance; student loan; accountant question. Some rows look navigable but have no callback or return null.

No Dart splash; no actual mileage log/tracking form; no full vehicle CRUD/rental branch; no AI conversation; no accountant portal/filing; no subscription manage/purchase/cancel; no unified settings/profile edit/logout/account deletion; no property records; no app-wide localization/RTL/Urdu Home; no designed desktop layouts. Some capabilities are represented by links/marketing, not complete modules.

## Security/privacy and integration risks

- No auth middleware or token store; route entry does not establish identity. Future logout must reset permanent BooksService and caches, not leave prior user's data.
- No persistent encrypted identifiers or actual protection. TaxDetailsView's UK-only/selected-accountant text, UploadView's address non-storage promise, ReceiptsView's fixed retention promise and MtdSendView's saved-confirmation statement are unsupported by implementation. Decide hosting/data-processing/retention/access policies before repeating claims in production.
- Android only has Internet permission; iOS lacks camera/photo/Face ID usage descriptions; no device camera/biometric/push/calendar/share/billing plugins. Platform scaffold is not release readiness evidence.
- No owner authorization, file access, upload scanning, consent/recipient verification or provider token handling exists yet; these are requirements of proposed backend, not proof of present data exposure. No API credentials/secrets were included in documentation.
- Partial OnboardingController fenix lifecycle can recreate defaults; no persistent resume. Hardcoded English labels and language promises differ. Shared widget AskBar/TextLink/OutlineLink fallback callbacks hide missing integrations.
- Duplicate displays/data sources (Home/Year/Money/Tax, shared receipt list vs grid, EE editor vs NCP detail) require one canonical model after integration. Shared controller state alone does not synchronize static literals.

## Product decisions needing answers before corresponding implementation

1. Is production login OTP/providers or existing backend email/password? What account recovery/provider-linking behavior is intended? Biometric local unlock and app passcode enrollment/recovery need a native security design.
2. Who may use simplified mileage (including Hackney/rental/lease/prior capital allowance cases)? How is election history/correction reviewed? Which regions/tax years/student loans/losses are supported?
3. How are historic opening totals, missing period evidence, PAYE tax paid and prior assessed liabilities/payments collected? No relevant complete forms exist.
4. Does a business-use default apply prospectively or retrospectively to selected open periods? How are filed periods locked/corrected?
5. Which PDF formats/platforms are supported? When are fees and payout dates recognized? How are refunds/tips/adjustments/overlapping statements handled? Marketing report-to-HMRC wording is not a schema.
6. CSV versus XLSX, PDF/photo packaging, export expiry, accountant recipient/provider and consent/delivery/file-return scope?
7. Billing provider/store model, cohort eligibility, price guarantee, VAT/terms, renewal/trial length and cancellation/refund policy?
8. HMRC recognition status, scopes, business types, actual quarter/cumulative payload requirements, final-declaration ownership and unknown/partial submission handling?
9. UK-only storage/retention/address minimization commitments, assistant consent/context/languages, notification/calendar delivery behavior, and account deletion/legal hold requirements?

These decisions can be deferred until their feature phase; they do not block documenting or implementing the verified basic ledger foundation.

Additional profile gap: there is no actual first/last-name entry form. Real accounts must not inherit Ali Khan. Keep names nullable until the product specifies collection and a safe unnamed-user display.
