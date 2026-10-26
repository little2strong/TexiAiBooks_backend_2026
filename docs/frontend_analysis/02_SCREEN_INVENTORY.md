# Complete screen inventory

Analysis: 27 October 2026. OBSERVED behavior unless explicitly called PROPOSED. 58 primary view classes, 54 named routes, six source modules; four tab children share /home. FirstDayHome and four sheets are additional surfaces, not included in 58.

**Existing API calls: NONE on every screen.** All data comes from view literals or in-memory controllers/BooksService. No data is fetched or persisted. Local interactions may work even where the underlying business operation is mocked. Shared SetupScreen/SubScreen headers use Get.back unless overridden. Exact callback evidence is in document 03; typed proposed API schemas in document 06; per-screen API mapping in document 10.

## S01 - WelcomeView

- **File/class:** `lib/features/onboarding/view/welcome_view.dart::WelcomeView`.
- **Route:** /welcome.
- **Purpose:** Introduce books and enter account flow.
- **UI:** AppButton, LanguagePill, Tile.
- **Buttons/actions:** Get started -> how-it-works; existing account -> sign-in; LanguagePill -> language.
- **Fields/validation:** No form.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Public content only.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Working navigation; decorative demo figures.

## S02 - LanguageView

- **File/class:** `lib/features/onboarding/view/language_view.dart::LanguageView`.
- **Route:** /language.
- **Purpose:** Choose app/assistant language.
- **UI:** AppButton, SelectCard.
- **Buttons/actions:** Cards set language; Continue -> continueFromLanguage (welcome -> how-it-works, otherwise back).
- **Fields/validation:** Seven static choices; local RTL card text only.
- **Exact field/control labels and defaults:** None.
- **Controller:** `lib/features/onboarding/controller/onboarding_controller.dart::OnboardingController`.
- **Models/data:** Language.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** User preferences; device translations.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Partial selection; no persisted preference/app locale.

## S03 - HowItWorksView

- **File/class:** `lib/features/onboarding/view/how_it_works_view.dart::HowItWorksView`.
- **Route:** /how-it-works.
- **Purpose:** Explain receipts/tax/accountant/assistant.
- **UI:** AppButton, Tile.
- **Buttons/actions:** Create account -> create-account.
- **Fields/validation:** No form.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Public content only.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Static marketing; integrations absent.

## S04 - CreateAccountView

- **File/class:** `lib/features/onboarding/view/create_account_view.dart::CreateAccountView`.
- **Route:** /create-account.
- **Purpose:** Registration.
- **UI:** AppButton, AppTextField.
- **Buttons/actions:** Apple/Google -> secure; SMS button -> code; Terms/Privacy styled text have no recognizers.
- **Fields/validation:** Mobile editable but unbound; no validation.
- **Exact field/control labels and defaults:** Mobile number.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** OTP/provider authentication.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Mock auth; no SMS/OAuth.

## S05 - CodeView

- **File/class:** `lib/features/onboarding/view/code_view.dart::CodeView`.
- **Route:** /code.
- **Purpose:** Represent SMS verification.
- **UI:** AppButton, TextField.
- **Buttons/actions:** Invisible TextField -> setCode; Continue -> secure; Change number -> back.
- **Fields/validation:** Digits only/max six; any six accepted; resend countdown static, no resend action.
- **Exact field/control labels and defaults:** None.
- **Controller:** `lib/features/onboarding/controller/onboarding_controller.dart::OnboardingController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** OTP challenge/verify/resend.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Mock verification.

## S06 - SignInView

- **File/class:** `lib/features/onboarding/view/sign_in_view.dart::SignInView`.
- **Route:** /sign-in.
- **Purpose:** Returning access.
- **UI:** AppButton, AppTextField, TextLink, Tile.
- **Buttons/actions:** Face ID -> signIn -> home; SMS -> code; email TextLink fallback no-op.
- **Fields/validation:** Phone edits unbound; no phone validation.
- **Exact field/control labels and defaults:** Mobile number; 07700 900000.
- **Controller:** `lib/features/onboarding/controller/onboarding_controller.dart::OnboardingController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Authentication/session restoration.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Mock auth; code path incorrectly leads through new-user setup.

## S07 - SecureView

- **File/class:** `lib/features/onboarding/view/secure_view.dart::SecureView`.
- **Route:** /secure.
- **Purpose:** Device lock preferences.
- **UI:** AppButton, AppSwitch, ChoiceRow, TextLink, Tile.
- **Buttons/actions:** Face ID switch -> faceId; timeout choice -> lockAfter; Continue -> driving; Change passcode fallback no-op.
- **Fields/validation:** Six decorative passcode dots; no passcode input.
- **Exact field/control labels and defaults:** Unlock with Face ID; Passcode set; Lock the app after.
- **Controller:** `lib/features/onboarding/controller/onboarding_controller.dart::OnboardingController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Preference sync only; device security implementation.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** UI-only device protection.

## S08 - DrivingView

- **File/class:** `lib/features/onboarding/view/driving_view.dart::DrivingView`.
- **Route:** /setup/driving.
- **Purpose:** Licence/council/work pattern.
- **UI:** AppButton, AppDropdown, ChoiceRow, SelectCard.
- **Buttons/actions:** SelectCards -> licence; dropdown -> council; choice row -> fullTime; Continue -> platforms.
- **Fields/validation:** Static councils/defaults; no licence validation.
- **Exact field/control labels and defaults:** Which council licenses you?; When do you drive?.
- **Controller:** `lib/features/onboarding/controller/onboarding_controller.dart::OnboardingController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Driver profile.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Working local choices, unsaved.

## S09 - PlatformsView

- **File/class:** `lib/features/onboarding/view/platforms_view.dart::PlatformsView`.
- **Route:** /setup/platforms.
- **Purpose:** Income sources.
- **UI:** AppButton, SelectCard.
- **Buttons/actions:** Multi-select -> togglePlatform; Continue/Skip -> other-income.
- **Fields/validation:** Zero choices allowed; dynamic count.
- **Exact field/control labels and defaults:** None.
- **Controller:** `lib/features/onboarding/controller/onboarding_controller.dart::OnboardingController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Driver platforms/income sources.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Working local choice; no provider connection.

## S10 - OtherIncomeView

- **File/class:** `lib/features/onboarding/view/other_income_view.dart::OtherIncomeView`.
- **Route:** /setup/other-income.
- **Purpose:** PAYE/rent/savings context.
- **UI:** AppButton, AppTextField, ChoiceRow, Tile.
- **Buttons/actions:** Yes/No -> hasJob; Continue -> tax-details; rent/interest pills inert.
- **Fields/validation:** Employer/yearly-pay fields unbound; rent No/interest Not sure static.
- **Exact field/control labels and defaults:** A job where tax comes off your pay; Employer; ABC Ltd; Yearly pay before tax; £20,000.
- **Controller:** `lib/features/onboarding/controller/onboarding_controller.dart::OnboardingController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Other-income tax profile.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Partial conditional UI; no captured salary.

## S11 - TaxDetailsView

- **File/class:** `lib/features/onboarding/view/tax_details_view.dart::TaxDetailsView`.
- **Route:** /setup/tax-details.
- **Purpose:** Optional tax identifiers.
- **UI:** AppButton, AppTextField.
- **Buttons/actions:** Continue/Add later -> vehicle.
- **Fields/validation:** UTR/NI fields unbound; keyboard hints only, no validation.
- **Exact field/control labels and defaults:** Unique Taxpayer Reference (UTR); 12345 67890; National Insurance number; QQ 12 34 56 C.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Encrypted tax profile.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** UI-only sensitive-data collection.

## S12 - VehicleView

- **File/class:** `lib/features/onboarding/view/vehicle_view.dart::VehicleView`.
- **Route:** /setup/vehicle.
- **Purpose:** Vehicle lookup/confirmation.
- **UI:** AppButton, TextFormField, Tile.
- **Buttons/actions:** UpperCaseFormatter uppercases plate; Yes -> claim-method; incorrect result -> _noop; ownership pill inert.
- **Fields/validation:** Editable plate unbound; result always Toyota Prius.
- **Exact field/control labels and defaults:** Number plate; LM72 KPF.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Vehicle lookup/vehicle create.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Mock lookup; no vehicle CRUD.

## S13 - ClaimMethodView

- **File/class:** `lib/features/onboarding/view/claim_method_view.dart::ClaimMethodView`.
- **Route:** /setup/claim-method.
- **Purpose:** Mileage versus actual costs.
- **UI:** AppButton, SelectCard.
- **Buttons/actions:** SelectCards -> claimMethod; Continue -> openLockIn sheet.
- **Fields/validation:** No eligibility/history check.
- **Exact field/control labels and defaults:** None.
- **Controller:** `lib/features/onboarding/controller/onboarding_controller.dart::OnboardingController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Vehicle election/policy.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Local choice only; later screens always mileage.

## S14 - EarningsView

- **File/class:** `lib/features/onboarding/view/earnings_view.dart::EarningsView`.
- **Route:** /setup/earnings.
- **Purpose:** Historic earnings entry choice.
- **UI:** Tile.
- **Buttons/actions:** Upload -> reading directly; Type totals -> empty closure; Start today -> trial.
- **Fields/validation:** No file/totals input.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Statement upload/import; totals decision.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Mock import entry; manual totals missing.

## S15 - ReadingView

- **File/class:** `lib/features/onboarding/view/reading_view.dart::ReadingView`.
- **Route:** /setup/reading.
- **Purpose:** Onboarding statement results.
- **UI:** AppButton, GroupCard, Tile.
- **Buttons/actions:** TimedReveal; Continue -> trial; Add Bolt -> empty closure after done.
- **Fields/validation:** Fixed file/27 payouts/amounts; no actual PDF.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Statement job/result.
- **States:** Timers simulate loading; actions disabled until complete. No failure/empty/retry..
- **Status:** Mock timed parser results.

## S16 - TrialView

- **File/class:** `lib/features/onboarding/view/trial_view.dart::TrialView`.
- **Route:** /setup/trial.
- **Purpose:** Subscription offer.
- **UI:** AppButton, GroupCard, Tile.
- **Buttons/actions:** Start trial -> reminders.
- **Fields/validation:** No purchase/entitlement; dates fixed.
- **Exact field/control labels and defaults:** Price for each group of drivers: you pay £1.99, later joiners pay £3.99, £5.99 and £7.99.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Plans/trial/subscription.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** UI-only trial; no subscription created.

## S17 - RemindersView

- **File/class:** `lib/features/onboarding/view/reminders_view.dart::RemindersView`.
- **Route:** /setup/reminders.
- **Purpose:** Reminder choices/setup finish.
- **UI:** AppButton, AppSwitch, Tile.
- **Buttons/actions:** Switches -> toggleReminder; Turn on and Not now both -> finish.
- **Fields/validation:** No permission/scheduler.
- **Exact field/control labels and defaults:** None.
- **Controller:** `lib/features/onboarding/controller/onboarding_controller.dart::OnboardingController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Onboarding completion/preferences.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Local choices; both actions open demo Home.

## S18 - ShellView

- **File/class:** `lib/features/shell/view/shell_view.dart::ShellView`.
- **Route:** /home.
- **Purpose:** Main navigation container.
- **UI:** AppTabBar, IndexedStack.
- **Buttons/actions:** AppTabBar -> select; Snap -> openAddSheet.
- **Fields/validation:** Optional AppTab argument in controller init.
- **Exact field/control labels and defaults:** None.
- **Controller:** `lib/features/shell/controller/shell_controller.dart::ShellController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Future authenticated bootstrap.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Working tab/menu navigation.

## S19 - HomeView

- **File/class:** `lib/features/home/view/home_view.dart::HomeView`.
- **Route:** /home -> AppTab.home.
- **Purpose:** Profit/tax/queue/week/miles/deadline.
- **UI:** ColumnChart, ProgressTrack, Tile.
- **Buttons/actions:** Profit -> year; queue -> openCheckSheet; week -> week; miles -> car; deadline -> dates; bell -> notifications; Ask empty.
- **Fields/validation:** No forms.
- **Exact field/control labels and defaults:** None.
- **Controller:** `lib/features/home/controller/home_controller.dart::HomeController`.
- **Models/data:** BooksService.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Dashboard/review queue.
- **States:** FirstDayHome when hasData=false; signup finish assigns demo=true. No network states.
- **Status:** Reactive demo profit/tax/counts; date/week/miles hardcoded.

## S20 - WeekView

- **File/class:** `lib/features/home/view/week_view.dart::WeekView`.
- **Route:** /week.
- **Purpose:** Weekly earnings/mileage/source report.
- **UI:** ColumnChart, GroupCard, StackedBar, Tile.
- **Buttons/actions:** Previous -> previous(index 1); Next -> next(index 0); day rows no callback.
- **Fields/validation:** Only two fixture weeks.
- **Exact field/control labels and defaults:** None.
- **Controller:** `lib/features/home/controller/week_controller.dart::WeekController`.
- **Models/data:** DayEarnings.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Weekly report/mileage.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Working local switching/percent allocation; no day drilldown.

## S21 - YearView

- **File/class:** `lib/features/home/view/year_view.dart::YearView`.
- **Route:** /year.
- **Purpose:** Annual report.
- **UI:** ColumnChart, StackedBar, Tile.
- **Buttons/actions:** Shared back only.
- **Fields/validation:** No form.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Annual aggregates/tax estimate.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Static report; never follows confirmations.

## S22 - CheckView

- **File/class:** `lib/features/home/view/check_view.dart::CheckView`.
- **Route:** /check.
- **Purpose:** Confirm pending receipts/check mismatch.
- **UI:** AppButton, Tile.
- **Buttons/actions:** Actions -> confirm(index); Undo -> undo; all Change -> review-receipt without ID; Bolt -> bolt-check.
- **Fields/validation:** No editable fields.
- **Exact field/control labels and defaults:** None.
- **Controller:** `lib/features/home/controller/check_controller.dart::CheckController`.
- **Models/data:** BooksService, ReceiptToCheck.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Receipt confirmation/reversal/reconciliation.
- **States:** Confirmed cards collapse; all-receipts-checked/resolved states; Undo toast. No loading/error/retry..
- **Status:** Local confirmation; wrong fixed EE editor for other receipts.

## S23 - BoltView

- **File/class:** `lib/features/home/view/bolt_view.dart::BoltView`.
- **Route:** /check/bolt.
- **Purpose:** Missing Bolt fare.
- **UI:** AppButton, GroupCard, Tile.
- **Buttons/actions:** Add -> addTrip; Undo -> undo; recorded another way -> _noop; done -> back.
- **Fields/validation:** No trip input.
- **Exact field/control labels and defaults:** None.
- **Controller:** `lib/features/home/controller/bolt_controller.dart::BoltController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Reconciliation resolution/reversal.
- **States:** Flag swaps resolved text/actions; Undo toast. No actual request/loading/error..
- **Status:** Partial: changes flag only, no income/fees/tax mutation.

## S24 - DatesView

- **File/class:** `lib/features/home/view/dates_view.dart::DatesView`.
- **Route:** /dates.
- **Purpose:** Deadline list/calendar action.
- **UI:** TextLink, Tile.
- **Buttons/actions:** Calendar button toggles datesInCalendar; What changes -> mtd.
- **Fields/validation:** Static dates/countdowns.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** BooksService.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Deadlines; native calendar adapter.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Mock calendar success; no calendar write.

## S25 - NotificationsView

- **File/class:** `lib/features/home/view/notifications_view.dart::NotificationsView`.
- **Route:** /notifications.
- **Purpose:** Notification feed.
- **UI:** GroupCard.
- **Buttons/actions:** Mark all read -> notificationsRead=true; three actionable items -> check/bolt-check.
- **Fields/validation:** No individual read updates.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** BooksService.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Notification list/read/preferences.
- **States:** No loading/error/retry or explicit empty state.
- **Status:** Local bulk-read; five fixture notifications/three unread.

## S26 - MoneyView

- **File/class:** `lib/features/money/view/money_view.dart::MoneyView`.
- **Route:** /home -> AppTab.money.
- **Purpose:** Money tab overview.
- **UI:** GroupCard, TextLink, Tile.
- **Buttons/actions:** Search/income/See all -> allMoney; expenses -> categories; queue -> check; platform check/upload/addFare/addExpense links; selected Latest rows navigate.
- **Fields/validation:** Some latest rows lack destinations.
- **Exact field/control labels and defaults:** Search your money.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** BooksService.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Dashboard/transactions/categories.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static totals/latest; only pending count reactive.

## S27 - AllMoneyView

- **File/class:** `lib/features/money/view/all_money_view.dart::AllMoneyView`.
- **Route:** /money/all.
- **Purpose:** Money list/search.
- **UI:** GroupCard, SegmentedTabs, TextField, Tile.
- **Buttons/actions:** Search -> query; tabs -> tab; filter -> openFilter; rows navigate when route supplied.
- **Fields/validation:** Trimmed case-insensitive name/sub/amount search; tab predicate; no date parsing.
- **Exact field/control labels and defaults:** Filter.
- **Controller:** `lib/features/money/controller/all_money_controller.dart::AllMoneyController`.
- **Models/data:** MoneyItem, MoneyKind.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Transaction list/search/filter/detail.
- **States:** No-match message present; no network loading/error/retry/paging..
- **Status:** Local search/tabs work; filter controls ignored.

## S28 - IncomeView

- **File/class:** `lib/features/money/view/income_view.dart::IncomeView`.
- **Route:** /money/income.
- **Purpose:** Uber gross/fee/net detail.
- **UI:** GroupCard, OutlineLink, Tile.
- **Buttons/actions:** Statement OutlineLink defaults to no-op.
- **Fields/validation:** No form or ID.
- **Exact field/control labels and defaults:** See the Uber statement.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Transaction/payout detail; statement file.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static payout example.

## S29 - ExpenseView

- **File/class:** `lib/features/money/view/expense_view.dart::ExpenseView`.
- **Route:** /money/expense.
- **Purpose:** NCP receipt confirmation.
- **UI:** AppButton, GroupCard, PaperReceipt, Tile.
- **Buttons/actions:** Add -> add; Undo -> undo; Change -> fixed EE review.
- **Fields/validation:** Always receipt index 1; no ID argument.
- **Exact field/control labels and defaults:** Photo of the parking receipt.
- **Controller:** `lib/features/money/controller/receipt_controllers.dart::ExpenseController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Expense/receipt detail/confirmation/reversal.
- **States:** Added state disables action, with Undo toast; no saving/error/conflict states.
- **Status:** Local NCP confirmation; incorrect editor route.

## S30 - CameraView

- **File/class:** `lib/features/money/view/camera_view.dart::CameraView`.
- **Route:** /money/camera.
- **Purpose:** Receipt capture representation.
- **UI:** PaperReceipt.
- **Buttons/actions:** Close -> back; shutter -> readReceipt; PDF -> upload; flash/photos empty.
- **Fields/validation:** No hardware/file acquisition.
- **Exact field/control labels and defaults:** Close camera; Flash off; Camera view with a receipt inside the frame.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Native capture; receipt upload.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** UI-only camera drawn receipt.

## S31 - ReadReceiptView

- **File/class:** `lib/features/money/view/read_receipt_view.dart::ReadReceiptView`.
- **Route:** /money/read-receipt.
- **Purpose:** OCR representation.
- **UI:** AppButton, GroupCard, PaperReceipt, Tile.
- **Buttons/actions:** TimedReveal; retake -> camera; check -> reviewReceipt after timers.
- **Fields/validation:** Fixed EE/date/total/VAT/category.
- **Exact field/control labels and defaults:** Your photo of the EE bill.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Receipt job/result.
- **States:** TimedReveal simulates loading and gates review button; no failed/empty/retry state.
- **Status:** Mock OCR; no image processing.

## S32 - ReviewReceiptView

- **File/class:** `lib/features/money/view/review_receipt_view.dart::ReviewReceiptView`.
- **Route:** /money/review-receipt.
- **Purpose:** Edit extraction and claim share.
- **UI:** AppButton, AppDropdown, AppTextField, Tile, WorkShareSlider.
- **Buttons/actions:** Type -> type; slider -> percent; Add -> save; Undo -> undo.
- **Fields/validation:** Slider 0-100 steps 5; shop/date/total unbound; no validators.
- **Exact field/control labels and defaults:** Shop; EE; Date; 15 Oct 2026; Total; £52.00; Type; Used for work.
- **Controller:** `lib/features/money/controller/receipt_controllers.dart::ReviewReceiptController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Receipt edit/confirm/reverse.
- **States:** Added state disables action, with Undo toast; no saving/error/conflict states.
- **Status:** Preview changes; save always fixed EE GBP 26; type ignored.

## S33 - AddFareView

- **File/class:** `lib/features/money/view/add_fare_view.dart::AddFareView`.
- **Route:** /money/add-fare.
- **Purpose:** Manual income.
- **UI:** AppButton, ChoiceRow, GroupCard, TextField, TextFormField, Tile.
- **Buttons/actions:** Source chips -> source; payment -> payment; Add GBP 18 -> Get.back only.
- **Fields/validation:** Amount/note unbound; date static; no validators.
- **Exact field/control labels and defaults:** £18.00; How you were paid.
- **Controller:** `lib/features/money/controller/entry_controllers.dart::AddFareController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Create income transaction.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** UI-only create; nothing saved.

## S34 - AddExpenseView

- **File/class:** `lib/features/money/view/add_expense_view.dart::AddExpenseView`.
- **Route:** /money/add-expense.
- **Purpose:** Manual expense without receipt.
- **UI:** AppButton, AppTextField, SelectCard.
- **Buttons/actions:** Category -> category; fuel explanatory state; Add/Keep personal -> back only.
- **Fields/validation:** Amount/date/reason unbound; fixed amount; no validators.
- **Exact field/control labels and defaults:** Amount; £12.00; Date; Today; Like: pay and display machine, no receipt.
- **Controller:** `lib/features/money/controller/entry_controllers.dart::AddExpenseController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Create expense/personal transaction.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** UI-only create; assumes mileage even after actual-cost selection.

## S35 - UploadView

- **File/class:** `lib/features/money/view/upload_view.dart::UploadView`.
- **Route:** /money/upload.
- **Purpose:** Statement PDF upload.
- **UI:** AppButton, Tile.
- **Buttons/actions:** Pick PDF/Bolt -> statementAdded; Uber/operator empty closures.
- **Fields/validation:** No picker/MIME/size/platform input.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Statement upload/parser/import.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Mock upload; Uber instructions lead to Bolt success.

## S36 - StatementAddedView

- **File/class:** `lib/features/money/view/statement_added_view.dart::StatementAddedView`.
- **Route:** /money/statement-added.
- **Purpose:** Bolt import results.
- **UI:** AppButton, GroupCard, Tile.
- **Buttons/actions:** See platforms -> platformCheck; difference -> boltCheck.
- **Fields/validation:** No file/job/statement ID.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Statement result/reconciliation.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static success; no income/fees imported.

## S37 - PlatformCheckView

- **File/class:** `lib/features/money/view/platform_check_view.dart::PlatformCheckView`.
- **Route:** /money/platform-check.
- **Purpose:** Statements versus records.
- **UI:** GroupCard, Tile.
- **Buttons/actions:** Bolt tile -> boltCheck.
- **Fields/validation:** No reconciliation algorithm.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** BooksService.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Reconciliation summaries/issues.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Bolt flag reactive; amounts hardcoded.

## S38 - CategoriesView

- **File/class:** `lib/features/money/view/categories_view.dart::CategoriesView`.
- **Route:** /money/categories.
- **Purpose:** Category expense summary.
- **UI:** Tile.
- **Buttons/actions:** Mileage -> car; phone -> category; non-claim -> personal; other callbacks return null.
- **Fields/validation:** No category ID.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Category summaries/non-claim totals.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static report; some tiles falsely interactive.

## S39 - CategoryView

- **File/class:** `lib/features/money/view/category_view.dart::CategoryView`.
- **Route:** /money/category.
- **Purpose:** Phone bills/default share.
- **UI:** GroupCard, Tile.
- **Buttons/actions:** Change -> businessUse; pending EE -> check.
- **Fields/validation:** Phone only, fixed historical bills.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** BooksService.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Category detail/business-use policy.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Waiting tile hides on confirmation; totals stay static.

## S40 - BusinessUseView

- **File/class:** `lib/features/money/view/business_use_view.dart::BusinessUseView`.
- **Route:** /money/business-use.
- **Purpose:** Default phone work share.
- **UI:** AppButton, ChoiceChipButton, GroupCard, Tile, WorkShareSlider.
- **Buttons/actions:** Slider/presets 25/50/75 -> percent; Save -> back only.
- **Fields/validation:** 0-100 in steps 5.
- **Exact field/control labels and defaults:** Phone used for driving.
- **Controller:** `lib/features/money/controller/receipt_controllers.dart::BusinessUseController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Effective-dated category business-use policy.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Local preview; does not apply/persist.

## S41 - PersonalView

- **File/class:** `lib/features/money/view/personal_view.dart::PersonalView`.
- **Route:** /money/personal.
- **Purpose:** Receipts kept without claim.
- **UI:** OutlineLink, Tile.
- **Buttons/actions:** Ask OutlineLink defaults to no-op.
- **Fields/validation:** No item edit/drilldown.
- **Exact field/control labels and defaults:** Think one of these should count? Ask.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Non-claim report/reclassification decision.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static fuel/cleaning/meals report.

## S42 - ReceiptsView

- **File/class:** `lib/features/money/view/receipts_view.dart::ReceiptsView`.
- **Route:** /money/receipts.
- **Purpose:** Receipt grid/status filters.
- **UI:** ChoiceChipButton, Tile.
- **Buttons/actions:** Filter chips -> filter; thumbs -> route or closure returning null.
- **Fields/validation:** Four filters over nine tuples, labels claim 51.
- **Exact field/control labels and defaults:** None.
- **Controller:** `lib/features/money/controller/entry_controllers.dart::ReceiptsController`.
- **Models/data:** ReceiptStatus.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Receipt pagination/status counts.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Local fixture filter; statuses/counts never follow confirmations.

## S43 - ExportView

- **File/class:** `lib/features/money/view/export_view.dart::ExportView`.
- **Route:** /money/export.
- **Purpose:** Accountant export options.
- **UI:** AppButton, AppSwitch, ChoiceRow, SelectCard, Tile.
- **Buttons/actions:** Year/format/photos set state; download/share -> _noop.
- **Fields/validation:** Two years/PDF or spreadsheet/photos; no generation.
- **Exact field/control labels and defaults:** Tax year; Include receipt photos.
- **Controller:** `lib/features/money/controller/entry_controllers.dart::ExportController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Export jobs/download/accountant handoff.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** UI-only export/share.

## S44 - TaxView

- **File/class:** `lib/features/tax/view/tax_view.dart::TaxView`.
- **Route:** /home -> AppTab.tax.
- **Purpose:** Tax overview.
- **UI:** GroupCard, ProgressTrack, Tile.
- **Buttons/actions:** Workings/pot/forecast/timeline/POA/MTD/allowance/car/other links.
- **Fields/validation:** No form.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** BooksService.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Tax estimate/forecast/pot/deadlines.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Only pot reactive; tax figures static.

## S45 - WorkingsView

- **File/class:** `lib/features/tax/view/workings_view.dart::WorkingsView`.
- **Route:** /tax/workings.
- **Purpose:** Explain tax calculation.
- **UI:** Tile.
- **Buttons/actions:** Why -> allowance; More -> class4.
- **Fields/validation:** No form.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Tax estimate breakdown.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static income/expense/profit/tax steps.

## S46 - AllowanceView

- **File/class:** `lib/features/tax/view/allowance_view.dart::AllowanceView`.
- **Route:** /tax/allowance.
- **Purpose:** Salary/allowance tax bands.
- **UI:** GroupCard, Tile.
- **Buttons/actions:** Shared back only.
- **Fields/validation:** No form.
- **Exact field/control labels and defaults:** Tax-free allowance £12,570 used by your job, then £7,430 of your job taxed at 20 percent, .
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Tax profile/allowance breakdown.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static salary/allowance distribution.

## S47 - Class4View

- **File/class:** `lib/features/tax/view/class4_view.dart::Class4View`.
- **Route:** /tax/class-4.
- **Purpose:** NI rules/explanation.
- **UI:** GroupCard, Tile.
- **Buttons/actions:** Forecast tile -> forecast.
- **Fields/validation:** No form.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Tax rules and NI breakdown.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static thresholds/rates and oversimplified Class 2 copy.

## S48 - ForecastView

- **File/class:** `lib/features/tax/view/forecast_view.dart::ForecastView`.
- **Route:** /tax/forecast.
- **Purpose:** Year projection.
- **UI:** GroupCard, Tile.
- **Buttons/actions:** Shared back only.
- **Fields/validation:** No form.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Tax forecast/assumptions.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static 195/365 projection/mileage threshold date.

## S49 - PoaView

- **File/class:** `lib/features/tax/view/poa_view.dart::PoaView`.
- **Route:** /tax/payments-on-account.
- **Purpose:** Advance tax explanation.
- **UI:** GroupCard, OutlineLink, Tile.
- **Buttons/actions:** OutlineLink -> timeline.
- **Fields/validation:** No form.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Payments on account calculation.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static prior-year bill; incomplete eligibility rule.

## S50 - TimelineView

- **File/class:** `lib/features/tax/view/timeline_view.dart::TimelineView`.
- **Route:** /tax/timeline.
- **Purpose:** Expected tax payment schedule.
- **UI:** AppButton, GroupCard, Tile.
- **Buttons/actions:** How to pay HMRC -> _noop.
- **Fields/validation:** No form.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Tax timeline/guidance.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static payment schedule; no payment operation.

## S51 - PotView

- **File/class:** `lib/features/tax/view/pot_view.dart::PotView`.
- **Route:** /tax/pot.
- **Purpose:** Record savings already moved.
- **UI:** AppButton, ProgressTrack, Tile.
- **Buttons/actions:** +25/+50/+100 -> add(pence); Undo -> undo.
- **Fields/validation:** Fixed positive presets, no custom field.
- **Exact field/control labels and defaults:** None.
- **Controller:** `lib/features/tax/controller/tax_controllers.dart::PotController`.
- **Models/data:** BooksService.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Tax-pot entries/reversal.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Local log/undo; fixed target; not a money transfer.

## S52 - TradingAllowanceView

- **File/class:** `lib/features/tax/view/trading_allowance_view.dart::TradingAllowanceView`.
- **Route:** /tax/trading-allowance.
- **Purpose:** Compare expense deduction/trading allowance.
- **UI:** Tile.
- **Buttons/actions:** Shared back only.
- **Fields/validation:** No election control.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Allowance comparison.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static comparison; real costs here is total expenses, separate from vehicle election.

## S53 - CarView

- **File/class:** `lib/features/tax/view/car_view.dart::CarView`.
- **Route:** /tax/car.
- **Purpose:** Mileage car/exclusions explanation.
- **UI:** Tile.
- **Buttons/actions:** Shared back only; pills informational.
- **Fields/validation:** No miles form/vehicle edit.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Vehicle policy/mileage summary.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static mileage regardless of onboarding actual-cost choice.

## S54 - MtdView

- **File/class:** `lib/features/tax/view/mtd_view.dart::MtdView`.
- **Route:** /tax/mtd.
- **Purpose:** MTD eligibility guidance.
- **UI:** OutlineLink, Tile.
- **Buttons/actions:** Quarterly preview -> mtdQuarters.
- **Fields/validation:** No HMRC connection/authorization.
- **Exact field/control labels and defaults:** See what quarterly updates look like.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Eligibility/connection/obligations.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static thresholds; recognition-in-progress copy.

## S55 - MtdQuartersView

- **File/class:** `lib/features/tax/view/mtd_quarters_view.dart::MtdQuartersView`.
- **Route:** /tax/mtd/quarters.
- **Purpose:** Illustrative quarterly schedule.
- **UI:** Tile.
- **Buttons/actions:** Ready quarter -> mtdSend; other rows no callback.
- **Fields/validation:** Different persona Mohammed and rental flat.
- **Exact field/control labels and defaults:** Signed in as Mohammed Rahman.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** MTD businesses/obligations/update history.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Mock history/status; no property records.

## S56 - MtdSendView

- **File/class:** `lib/features/tax/view/mtd_send_view.dart::MtdSendView`.
- **Route:** /tax/mtd/send.
- **Purpose:** Review/send quarterly update.
- **UI:** HoldToConfirmButton, Tile.
- **Buttons/actions:** Hold -> sent=true.
- **Fields/validation:** 1.5s pointer hold; no real authorization/checks.
- **Exact field/control labels and defaults:** Hold to send to HMRC.
- **Controller:** `lib/features/tax/controller/tax_controllers.dart::MtdSendController`.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** MTD preview/submit/status/acknowledgement.
- **States:** Local sent flag shows success; no sending/rejected/unknown-outcome state.
- **Status:** Mock HMRC success; no confirmation/document persisted.

## S57 - OtherTaxView

- **File/class:** `lib/features/tax/view/other_tax_view.dart::OtherTaxView`.
- **Route:** /tax/other.
- **Purpose:** VAT/student-loan/marriage guidance.
- **UI:** AppButton, ProgressTrack, Tile.
- **Buttons/actions:** Loan/accountant buttons -> _noop.
- **Fields/validation:** No profile input.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** Presentation primitives/controller fixtures.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Other-tax profile/accountant request.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Static hints; monthly VAT monitor absent.

## S58 - DriverView

- **File/class:** `lib/features/driver/view/driver_view.dart::DriverView`.
- **Route:** /home -> AppTab.driver.
- **Purpose:** Profile/car hub.
- **UI:** AskBar, GroupCard, ProgressTrack, Tile.
- **Buttons/actions:** Car/receipts/export/platformCheck/notifications/language links; AskBar no-op.
- **Fields/validation:** No editable profile/vehicle or logout.
- **Exact field/control labels and defaults:** None.
- **Controller:** No dedicated controller; shared service where referenced.
- **Models/data:** BooksService, Language.
- **Source/API:** Local literals/reactive memory only; zero API calls.
- **Missing backend (PROPOSED):** Driver profile/vehicle/preferences.
- **States:** No async loading/error/retry or explicit empty state.
- **Status:** Working links; static name/car/miles/language.

## Extra surfaces, excluded from primary screen count

| Surface / exact file / class | Traced behavior |
| --- | --- |
| lib/features/home/widget/first_day_home.dart::FirstDayHome | HomeView conditional empty state; language/vehicle/upload links and ShellController.openAddSheet. Ask no-op. Demo finish forces populated Home. |
| lib/features/home/widget/add_sheet.dart::AddSheet | Snap opens sheet; close; camera/upload/fare/expense close then navigate. Log miles and Ask no-op. |
| lib/features/home/widget/check_sheet.dart::CheckSheet | Next receipt from BooksService; confirmNext closes then toast; See all -> check; Change always EE review. All-checked variant has Done and Bolt text, no Bolt link. |
| lib/features/onboarding/widget/lock_in_sheet.dart::LockInSheet | Hold -> locked=true; Continue closes/goes earnings; Go back closes. No persisted election. |
| lib/features/money/widget/filter_sheet.dart::FilterSheet | When/source/category choices and Clear all update local state; Show results closes; groups ignores all these filters. |

## Requested capabilities absent as complete modules

- Splash: no Dart splash; platform launch scaffold only.
- Mileage: figures and car information present, but no log screen, trip model, GPS or odometer form; Log miles empty.
- AI: Ask affordances only; no conversation screen/controller/service.
- Accountant: marketing and disabled-by-no-op handoff/request actions; no directory/booking/portal.
- Subscriptions: trial offer only; no purchase/manage/cancel screen.
- Settings: partial language/security/reminder screens; no unified settings/profile edit/logout/account deletion.
- Export: selectors only, no output/share. Reports are static except local Home/Week behavior.
- Firebase/push: absent. Notifications are fixtures; reminders do not request permission.
- HMRC: guidance/preview only; no OAuth, registration, obligations retrieval or submissions.
- Vehicle management: setup and tax explanation only; no vehicle list/edit/delete, rental branch or eligibility check.
- Property: only a Mohammed MTD fixture, no property business bookkeeping.
- Full Urdu/Arabic RTL, localization and desktop boards: absent.
