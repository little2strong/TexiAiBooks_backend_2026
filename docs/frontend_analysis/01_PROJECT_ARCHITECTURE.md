# Project architecture

Analysis date: 27 October 2026 (Asia/Dhaka). Source commit: `a5a9c4456ac190c0cb4bde9b4ae043f04f9a832f`. Documentation only.

**Evidence:** OBSERVED = source behavior; PROPOSED = future requirement; UNVERIFIED = external backend report or unresolved decision. No backend source/contract supplied.

## Scope and counting

Reviewed all 107 Dart files under lib (12,682 lines), both Dart tests, dependencies, routes/bindings, shared widgets, assets, native configuration and existing guides. Generated build output is not application source. There are 58 primary classes in features/*/view/: onboarding 17, shell 1, home 7, money 18, tax 14, driver 1. There are 54 named page registrations: the four tab children have no separate route. FirstDayHome is another Home state. AddSheet, CheckSheet, FilterSheet and LockInSheet are four modal surfaces excluded from 58. Design/artboard numbers are not screen counts.

Six implemented source modules: onboarding, shell, home, money, tax, driver. Business capabilities cross these folders; absent features are not working modules.

## Actual stack

| Item | Observed value / evidence |
| --- | --- |
| Installed Flutter | 3.44.1 stable, framework revision 924134a44c, from flutter --version |
| Installed Dart | 3.12.1; SDK folder name contains 3.32.0 but does not identify its current version |
| Package/application | texi_ai_books, version 1.0.0+1; app title TaxiAiBooks |
| SDK constraints | pubspec ^3.12.1; lockfile Dart >=3.12.1 <4.0.0, Flutter >=3.41.0; no single exact Flutter release pinned |
| State/navigation/DI | GetX 4.7.3; Rx, Obx, GetView, GetMaterialApp, GetPage, Bindings |
| HTTP | Dio 5.11.1 configured, no requests issued |
| UI | Material 3 light; bundled Lexend 400/500/600/700; flutter_svg 2.3.0; cupertino_icons 1.0.9 resolved (^1.0.8 constraint) |
| Lints/tests | flutter_lints 6.0.0, flutter_test; no generated DTO dependencies |
| Persistence/auth/Firebase | Not implemented; no token store, database, biometric plugin, Firebase dependency/config or repository layers |

## Startup and state

lib/main.dart::main initializes Flutter bindings and runs lib/apps/app.dart::TexiAiBooksApp. GetMaterialApp starts at /welcome and uses AppPages.pages, InitialBinding and AppTheme.light. No auth middleware, session restoration, unknown-route page or explicit deep-link policy.

InitialBinding permanently registers ApiClient and BooksService. BooksService is shared in-memory demo state, not a repository. OnboardingBinding lazily registers OnboardingController with fenix:true; recreation restores defaults, not persisted choices. ShellBinding registers ShellController and HomeController. ShellView uses IndexedStack for HomeView, MoneyView, TaxView and DriverView; ShellController.tab selects the child, optionally initialized by an AppTab route argument. Snap opens AddSheet.

home/binding/home_binding.dart contains WeekBinding, CheckBinding and BoltBinding. money/binding/money_binding.dart contains AllMoneyBinding, ExpenseBinding (always receipt index 1), ReviewReceiptBinding, BusinessUseBinding, AddFareBinding, AddExpenseBinding, ExportBinding and ReceiptsBinding. tax/binding/tax_binding.dart contains PotBinding and MtdSendBinding. Get.find and cross-feature controller/view imports are observed; clean architecture/data/domain repositories are recommendations in PROJECT_STRUCTURE.md, not implemented layers.

## Navigation and authentication

AppRoutes defines constants; AppPages registers views/bindings. Get.toNamed, Get.offNamed, Get.offAllNamed and Get.back drive navigation. Camera/manual entry use fullscreen-dialog transitions. OnboardingController.signIn sets hasData=true and clears the stack into /home without authentication. finish assigns BooksService.demo=true and opens demo Home. CodeView accepts any six digits and navigates to SecureView, including when reached from SignInView. Apple/Google buttons directly navigate to SecureView. Face ID, passcode dots and auto-lock choices do not invoke OS security.

## Network/environment/error handling

AppConfig.apiBaseUrl reads compile-time API_BASE_URL, empty by default. ApiClient constructs Dio BaseOptions with Accept:application/json, 15s connect/send and 30s receive timeouts; accepts an optional Dio instance. No endpoint calls, DTOs, interceptors, Authorization, refresh/retry, pagination, upload/download or transport-error mapping exists. TimedReveal simulates progress with timers. UndoToastMixin shows four-second local feedback. No global application error reporting.

Only API_BASE_URL is configured. Compile-time values are public client configuration, not a place for server secrets. The external backend's registration/login/JWT/expense CRUD/tests are user-reported and unverified: no backend sources or OpenAPI in this repository.

## Platform/storage/localization/theme

Android main manifest requests INTERNET. iOS Info.plist lacks camera/photo/Face ID usage descriptions. macOS debug/profile and release entitlements permit network clients. Platform scaffolds do not establish camera, sharing, billing, notification or calendar support. No persistent local store/cache; restarting loses confirmations, pot logs, read flags and selections.

Language metadata supports en, ur, pa, pl, ro, bn, ar. Only language-card text direction and Continue label use it. No app translations delegate, locale application or global RTL; language pills and Driver subtitle stay English. AppTheme.light/AppColors/AppText/AppMotion define the sole light theme. DesignScale uses a 390-wide grid with 0.8-1.15 scaling; FitScroll shrinks moderate overflow to 0.88 or scrolls. Desktop designs are absent.

## Folder responsibilities

| Path | Responsibility |
| --- | --- |
| lib/apps | Root app, routes, global binding and theme tokens |
| lib/core/config; network | Public URL/timeouts; unused Dio plumbing |
| lib/core/services/books_service.dart | ReceiptToCheck and shared reactive demo books |
| lib/core/utils/money.dart::money | Integer pence to GBP text; not a parser |
| lib/core/widgets | Buttons, fields, choices, cards/charts, wrappers, sheets/undo/hold/timers, SVG icons and fit renderer |
| lib/features/onboarding | Welcome/access, language, nine-step local setup |
| lib/features/shell | Four tabs and Snap menu |
| lib/features/home | Dashboard, week/year, review queue, Bolt, deadlines, notifications |
| lib/features/money | Fixture list/search, entry forms, receipt/statement simulations, reports, export controls |
| lib/features/tax | Explanations/forecast/MTD fixtures; local tax-pot logging |
| lib/features/driver | Static DriverView profile/car hub |
| assets/fonts | Lexend fonts and license; receipt pictures are drawn widgets |
| android, ios, web, windows, linux, macos | Native launch/build scaffolds; no backend |
| test/money_test.dart | Formatting/sign tests and positive fixture percentage aggregation |
| test/widget_test.dart | Six scenarios: demo sign-in, receipt Undo, demo signup finish, forced empty Home, week switch, tabs |
| pubspec.yaml/pubspec.lock/.metadata | Dependency constraints/resolution and framework metadata |
| analysis_options.yaml | flutter_lints configuration |
| README.md/PROJECT_STRUCTURE.md | Existing guides; source takes precedence |

## Complete Dart file/class index
| Exact Dart path | Declared classes / enums / mixins |
| --- | --- |
| `lib/apps/app.dart` | `TexiAiBooksApp` |
| `lib/apps/binding/initial_binding.dart` | `InitialBinding` |
| `lib/apps/routes/app_pages.dart` | `AppPages` |
| `lib/apps/routes/app_routes.dart` | `AppRoutes` |
| `lib/apps/theme/app_colors.dart` | `AppColors` |
| `lib/apps/theme/app_motion.dart` | `AppMotion` |
| `lib/apps/theme/app_text.dart` | `AppText` |
| `lib/apps/theme/app_theme.dart` | `AppTheme` |
| `lib/core/config/app_config.dart` | `AppConfig` |
| `lib/core/network/api_client.dart` | `ApiClient` |
| `lib/core/services/books_service.dart` | `ReceiptToCheck`, `BooksService` |
| `lib/core/utils/money.dart` | `exports/functions only` |
| `lib/core/widgets/app_icon.dart` | `AppIcons`, `AppIcon`, `AppleLogo` |
| `lib/core/widgets/buttons.dart` | `ButtonKind`, `AppButton`, `RoundIconButton`, `AskBar`, `TextLink` |
| `lib/core/widgets/charts.dart` | `ColumnBar`, `ColumnChart`, `BarSegment`, `StackedBar`, `LegendRow`, `ProgressTrack`, `StepProgress` |
| `lib/core/widgets/choices.dart` | `ChoiceChipButton`, `ChoiceRow`, `ChipWrap`, `SelectCard`, `SelectedTick`, `CheckMark`, `AppSwitch`, `SegmentedTabs` |
| `lib/core/widgets/dashed_border.dart` | `DashedBorder`, `_DashedPainter` |
| `lib/core/widgets/feedback.dart` | `UndoToastMixin`, `UndoToast`, `ObxUndoToast`, `AppSheet`, `HoldToConfirmButton`, `_HoldToConfirmButtonState`, `_LeftClipper`, `Spinner`, `_SpinnerState`, `TimedReveal`, `_TimedRevealState`, `Collapsible`, `RevealRow` |
| `lib/core/widgets/fields.dart` | `AppTextField`, `AppDropdown` |
| `lib/core/widgets/fit.dart` | `DesignScale`, `FitScroll`, `ShrinkToFit`, `RenderShrinkToFit`, `FitList` |
| `lib/core/widgets/pressable.dart` | `Pressable`, `_PressableState` |
| `lib/core/widgets/rows.dart` | `GroupCard`, `KvRow`, `TotalRule`, `LinkRow`, `SectionLabel`, `Note`, `InfoBox` |
| `lib/core/widgets/screens.dart` | `ScreenHeader`, `BottomActionBar`, `SubScreen`, `SetupScreen` |
| `lib/core/widgets/tile.dart` | `Tile`, `IconCircle`, `Pill`, `NumberPlate`, `TwoUp`, `EqualGrid` |
| `lib/core/widgets/widgets.dart` | `exports/functions only` |
| `lib/features/driver/view/driver_view.dart` | `DriverView` |
| `lib/features/home/binding/home_binding.dart` | `WeekBinding`, `CheckBinding`, `BoltBinding` |
| `lib/features/home/controller/bolt_controller.dart` | `BoltController` |
| `lib/features/home/controller/check_controller.dart` | `CheckController` |
| `lib/features/home/controller/home_controller.dart` | `HomeController` |
| `lib/features/home/controller/week_controller.dart` | `DayEarnings`, `WeekData`, `WeekController` |
| `lib/features/home/view/bolt_view.dart` | `BoltView` |
| `lib/features/home/view/check_view.dart` | `CheckView`, `_ReceiptCard` |
| `lib/features/home/view/dates_view.dart` | `DatesView` |
| `lib/features/home/view/home_view.dart` | `HomeView`, `_Home` |
| `lib/features/home/view/notifications_view.dart` | `NotificationsView` |
| `lib/features/home/view/week_view.dart` | `WeekView` |
| `lib/features/home/view/year_view.dart` | `YearView`, `ExpenseBar` |
| `lib/features/home/widget/add_sheet.dart` | `AddSheet` |
| `lib/features/home/widget/check_sheet.dart` | `CheckSheet` |
| `lib/features/home/widget/first_day_home.dart` | `FirstDayHome` |
| `lib/features/money/binding/money_binding.dart` | `AllMoneyBinding`, `ExpenseBinding`, `ReviewReceiptBinding`, `BusinessUseBinding`, `AddFareBinding`, `AddExpenseBinding`, `ExportBinding`, `ReceiptsBinding` |
| `lib/features/money/controller/all_money_controller.dart` | `MoneyKind`, `MoneyItem`, `AllMoneyController` |
| `lib/features/money/controller/entry_controllers.dart` | `AddFareController`, `AddExpenseController`, `ExportController`, `ReceiptsController` |
| `lib/features/money/controller/receipt_controllers.dart` | `ExpenseController`, `ReviewReceiptController`, `BusinessUseController` |
| `lib/features/money/view/add_expense_view.dart` | `AddExpenseView` |
| `lib/features/money/view/add_fare_view.dart` | `AddFareView` |
| `lib/features/money/view/all_money_view.dart` | `AllMoneyView` |
| `lib/features/money/view/business_use_view.dart` | `BusinessUseView` |
| `lib/features/money/view/camera_view.dart` | `CameraView`, `_Brackets` |
| `lib/features/money/view/categories_view.dart` | `CategoriesView` |
| `lib/features/money/view/category_view.dart` | `CategoryView` |
| `lib/features/money/view/expense_view.dart` | `ExpenseView` |
| `lib/features/money/view/export_view.dart` | `ExportView` |
| `lib/features/money/view/income_view.dart` | `IncomeView`, `OutlineLink` |
| `lib/features/money/view/money_view.dart` | `MoneyView` |
| `lib/features/money/view/personal_view.dart` | `PersonalView` |
| `lib/features/money/view/platform_check_view.dart` | `PlatformCheckView` |
| `lib/features/money/view/read_receipt_view.dart` | `ReadReceiptView`, `_ScanLine`, `_ScanLineState` |
| `lib/features/money/view/receipts_view.dart` | `ReceiptStatus`, `ReceiptsView`, `_ReceiptThumb` |
| `lib/features/money/view/review_receipt_view.dart` | `ReviewReceiptView`, `PercentHeader`, `WorkShareSlider` |
| `lib/features/money/view/statement_added_view.dart` | `StatementAddedView` |
| `lib/features/money/view/upload_view.dart` | `UploadView` |
| `lib/features/money/widget/filter_sheet.dart` | `FilterSheet` |
| `lib/features/money/widget/paper_receipt.dart` | `PaperReceipt`, `DashedLine`, `_TearPainter` |
| `lib/features/onboarding/binding/onboarding_binding.dart` | `OnboardingBinding` |
| `lib/features/onboarding/controller/onboarding_controller.dart` | `Language`, `ClaimMethod`, `OnboardingController` |
| `lib/features/onboarding/view/claim_method_view.dart` | `ClaimMethodView` |
| `lib/features/onboarding/view/code_view.dart` | `CodeView`, `_CodeBoxes`, `_CodeBoxesState` |
| `lib/features/onboarding/view/create_account_view.dart` | `CreateAccountView`, `OrDivider` |
| `lib/features/onboarding/view/driving_view.dart` | `DrivingView` |
| `lib/features/onboarding/view/earnings_view.dart` | `EarningsView` |
| `lib/features/onboarding/view/how_it_works_view.dart` | `HowItWorksView` |
| `lib/features/onboarding/view/language_view.dart` | `LanguageView`, `_LanguageCard` |
| `lib/features/onboarding/view/other_income_view.dart` | `OtherIncomeView` |
| `lib/features/onboarding/view/platforms_view.dart` | `PlatformsView` |
| `lib/features/onboarding/view/reading_view.dart` | `ReadingView`, `ReadingHeader` |
| `lib/features/onboarding/view/reminders_view.dart` | `RemindersView` |
| `lib/features/onboarding/view/secure_view.dart` | `SecureView` |
| `lib/features/onboarding/view/sign_in_view.dart` | `SignInView` |
| `lib/features/onboarding/view/tax_details_view.dart` | `TaxDetailsView` |
| `lib/features/onboarding/view/trial_view.dart` | `TrialView` |
| `lib/features/onboarding/view/vehicle_view.dart` | `VehicleView`, `UpperCaseFormatter` |
| `lib/features/onboarding/view/welcome_view.dart` | `WelcomeView`, `_TileCollage`, `_DropIn`, `_DropInState` |
| `lib/features/onboarding/widget/language_pill.dart` | `LanguagePill` |
| `lib/features/onboarding/widget/lock_in_sheet.dart` | `LockInSheet` |
| `lib/features/shell/binding/shell_binding.dart` | `ShellBinding` |
| `lib/features/shell/controller/shell_controller.dart` | `AppTab`, `ShellController` |
| `lib/features/shell/view/shell_view.dart` | `ShellView` |
| `lib/features/shell/widget/app_tab_bar.dart` | `AppTabBar` |
| `lib/features/tax/binding/tax_binding.dart` | `PotBinding`, `MtdSendBinding` |
| `lib/features/tax/controller/tax_controllers.dart` | `PotController`, `MtdSendController` |
| `lib/features/tax/view/allowance_view.dart` | `AllowanceView` |
| `lib/features/tax/view/car_view.dart` | `CarView` |
| `lib/features/tax/view/class4_view.dart` | `Class4View` |
| `lib/features/tax/view/forecast_view.dart` | `ForecastView` |
| `lib/features/tax/view/mtd_quarters_view.dart` | `MtdQuartersView`, `MohammedAvatar` |
| `lib/features/tax/view/mtd_send_view.dart` | `MtdSendView` |
| `lib/features/tax/view/mtd_view.dart` | `MtdView` |
| `lib/features/tax/view/other_tax_view.dart` | `OtherTaxView` |
| `lib/features/tax/view/poa_view.dart` | `PoaView` |
| `lib/features/tax/view/pot_view.dart` | `PotView` |
| `lib/features/tax/view/tax_view.dart` | `TaxView` |
| `lib/features/tax/view/timeline_view.dart` | `TimelineView` |
| `lib/features/tax/view/trading_allowance_view.dart` | `TradingAllowanceView` |
| `lib/features/tax/view/workings_view.dart` | `WorkingsView` |
| `lib/main.dart` | `exports/functions only` |
