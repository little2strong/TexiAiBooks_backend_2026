# Feature functionality and interaction audit

Analysis: 27 October 2026. Existing API calls: zero. Document 02 describes every screen; this file traces controller effects and indexes every callback definition. WORKING LOCAL does not imply a persisted/backend feature. PARTIAL changes only part of the workflow; MOCK simulates a real service; UI ONLY has no effective business operation.

## Controller traces

| Trigger / exact method | Actual processing and data | Status / backend need |
| --- | --- | --- |
| Code field -> OnboardingController.setCode | Strip non-digits, truncate six; codeComplete length only | MOCK; challenge-bound verification/rate limits |
| Language cards/Continue -> continueFromLanguage | Code in memory; previousRoute chooses forward or back | PARTIAL; preferences and device translations |
| Driving/platform/other-income/security/reminder controls | licence/fullTime/claimMethod indices, council/language strings, platform/reminder bool lists, faceId/hasJob bools | WORKING LOCAL choices; persist profile/preferences; OS security separate |
| Claim Continue -> openLockIn -> lockIn -> continueAfterLockIn | Reset locked, open modal, locked=true, close/navigate earnings | PARTIAL; validate/elect vehicle method durably |
| signIn / finish | Set hasData=true or demo=true; Get.offAllNamed home | MOCK; no token/identity/session |
| ShellController.select / openAddSheet | Set AppTab or present menu | WORKING LOCAL navigation |
| HomeController.confirmNext / CheckController.confirm(index) | BooksService.confirm adds fixture index once; expense += fixed claimPence, profit and tax derive; toast | WORKING LOCAL; atomic confirmation/ledger and refreshed summary |
| Home/Check undo -> BooksService.undoConfirm | Removes globally most recent confirmation, not a captured action ID | PARTIAL across controllers/devices; address server reversal to exact action |
| ExpenseController.add / undo | Add/remove fixed NCP index 1; added is membership | WORKING LOCAL; real receipt IDs/reversal |
| ReviewReceiptController.save / undo | saved=true; confirms EE index 0; toast uses round(5200*percent/100), books always adds 2600; type ignored; undo removes EE | PARTIAL/financial mismatch; persist edits and compute actual claim atomically |
| BusinessUseController percent | claim=round(31200*percent/100); saving=round(claim*0.2); Save only back | PARTIAL; effective-dated default policy with explicit historical treatment |
| BoltController.addTrip / undo | boltResolved true/false; incomePence constant never changes; fees/profit/tax unchanged | PARTIAL; gross/fee resolution must update ledger |
| WeekController.previous / next | index 1/0 between two fixtures | WORKING LOCAL; date-parametrized report |
| WeekController.percents | Largest-remainder whole percentages, sum 100 for positive fixtures; no zero-total guard | PARTIAL generalization; no-data percentage policy |
| AllMoneyController.groups | Filter fixture items by money tab and trimmed lower-case name/sub/amount search; group adjacent day strings | WORKING LOCAL search/tabs; real date/currency/query/pagination |
| toggleSource / toggleCategory / clearFilters | Change bool lists/date index only; groups ignores all | UI ONLY filtering; actual predicates required |
| AddFareController.source/payment; AddExpenseController.category | Selection state only; isFuel category index 4; Add buttons back only | UI ONLY create; bind inputs, validate and persist |
| ReceiptsController.filter | Four status choices over nine fixed tuples; not BooksService state | WORKING LOCAL fixture filtering; real counts/statuses |
| ExportController selections | year/format/photos affect downloadLabel; actions _noop | UI ONLY generation/share |
| PotController.add / undo -> BooksService.addToPot/undoPot | Preset integer-pence add, log stack, remove-last undo; four-second toast | WORKING LOCAL; durable savings log, not bank transfer |
| MtdSendView hold -> MtdSendController.sent=true | One bool changes success display, no network | MOCK; authorized frozen submission and HMRC acknowledgement |
| DatesView calendar toggle | Boolean swaps success label, no native call | MOCK; backend deadlines plus OS calendar adapter |
| NotificationsView read-all | Global bool changes unread from 3 to 0 and first three rows' styling | WORKING LOCAL; persisted read timestamps |

Controller exact files/classes are indexed in document 01. AllMoneyController/MoneyItem in money/controller/all_money_controller.dart; entry controllers in entry_controllers.dart; receipt controllers in receipt_controllers.dart; tax controllers in tax/controller/tax_controllers.dart; onboarding in onboarding/controller/onboarding_controller.dart; Home/Week/Check/Bolt each in their matching home/controller file.

## Shared controls and inherited behavior

core/widgets/buttons.dart::AppButton disables only when callback is null; empty closures remain enabled. AskBar/TextLink fall back to empty closures. money/view/income_view.dart::OutlineLink does the same. Tile is noninteractive only with onTap=null; closures returning null remain tappable. LinkRow uses a supplied callback, otherwise renders information. AppTextField wraps TextFormField without validator/onSaved; most callers bind neither controller nor onChanged. AppDropdown forwards non-null strings. ChoiceRow/ChipWrap/SegmentedTabs forward indices; AppSwitch negates the value.

feedback.dart::HoldToConfirmButton uses AppMotion.hold=1500ms for pointer holds; early release reverses progress. Accessibility onLongPress calls onConfirmed directly. A UI gesture is not authentication or server submission consent. UndoToastMixin replaces the previous timer/toast; hides after four seconds and disposes onClose. Rapid mutations expose only the latest toast, so durable undo must use an action identifier. TimedReveal schedules fixed reveals and cancels timers on dispose, with no job/error data. pressable.dart::Pressable adds keyboard Enter/Space, scale feedback and semantics, not business behavior. screens.dart headers default to Get.back.

## Missing/decorative actions

Home Ask; AddSheet Log miles/Ask; Earnings Type totals; Reading Add Bolt; Secure Change passcode; SignIn email; Vehicle incorrect-result; Camera flash/photos; Income statement; Export download/share; Timeline payment help; OtherTax loan/accountant; Personal/Driver Ask are no-ops. Terms/Privacy spans have no links. Rent/savings/ownership pills and day rows cannot edit. Some category tiles/thumbnails accept presses but return null. Upload picks no file and shows Bolt after Uber instructions. All Change receipt actions open EE without an identifier. SMS sign-in leads to new-user security/setup.

## Exact callback evidence index

All callback definition sites, including forwarded onConfirm and keyboard onInvoke, are indexed. Loops/helpers reuse definitions; counts are not distinct end-user actions.

### `lib/core/widgets/buttons.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 66 | return Pressable( | `onTap: onPressed,` |
| 129 | Widget build(BuildContext context) => Pressable( | `onTap: onTap,` |
| 150 | Widget build(BuildContext context) => Pressable( | `onTap: onTap ?? () {},` |
| 187 | child: Pressable( | `onTap: onTap ?? () {},` |

### `lib/core/widgets/choices.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 37 | Widget build(BuildContext context) => Pressable( | `onTap: onTap,` |
| 101 |  | `onTap: () => onSelect(i),` |
| 143 |  | `onTap: () => onTap(i),` |
| 180 | Widget build(BuildContext context) => Pressable( | `onTap: onTap,` |
| 272 | Widget build(BuildContext context) => Pressable( | `onTap: () => onChanged(!value),` |
| 355 | child: Pressable( | `onTap: () => onSelect(i),` |

### `lib/core/widgets/feedback.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 90 | Pressable( | `onTap: onUndo,` |
| 126 |  | `onUndo: onUndo,` |
| 253 | label: widget.label, | `onLongPress: widget.onConfirmed,` |
| 256 | label: widget.label, | `onTapDown: (_) => _start(),` |
| 257 | label: widget.label, | `onTapUp: (_) => _stop(),` |
| 258 | label: widget.label, | `onTapCancel: _stop,` |

### `lib/core/widgets/fields.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 64 |  | `onChanged: onChanged,` |
| 169 |  | `onChanged: (v) => v == null ? null : onChanged(v),` |

### `lib/core/widgets/pressable.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 62 | ActivateIntent: CallbackAction<ActivateIntent>( | `onInvoke: (_) { widget.onTap?.call(); return null; },` |
| 70 |  | `onTapDown: enabled ? (_) => _set(true) : null,` |
| 71 |  | `onTapUp: enabled ? (_) => _set(false) : null,` |
| 72 |  | `onTapCancel: enabled ? () => _set(false) : null,` |
| 73 |  | `onTap: widget.onTap,` |

### `lib/core/widgets/rows.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 153 | Widget build(BuildContext context) => Pressable( | `onTap: onTap ?? () {},` |

### `lib/core/widgets/screens.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 38 | RoundIconButton( label: backLabel, | `onTap: onBack ?? Get.back,` |
| 133 | title: title, subtitle: subtitle, | `onBack: onBack,` |
| 211 | RoundIconButton( label: 'Back', | `onTap: onBack ?? Get.back,` |

### `lib/core/widgets/tile.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 51 |  | `return Pressable(onTap: onTap, semanticLabel: semanticLabel, child: box);` |

### `lib/features/driver/view/driver_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 37 | Tile( | `onTap: () => _go(AppRoutes.car),` |
| 74 | title: 'Receipts', subtitle: '51 this tax year', | `onTap: () => _go(AppRoutes.receipts),` |
| 79 | title: 'Receipts', subtitle: '51 this tax year', title: 'Export your books', subtitle: 'For your accountant', | `onTap: () => _go(AppRoutes.export),` |
| 84 | title: 'Export your books', subtitle: 'For your accountant', title: 'Platform check', subtitle: 'Uber and Bolt against your records', | `onTap: () => _go(AppRoutes.platformCheck),` |
| 88 | title: 'Platform check', subtitle: 'Uber and Bolt against your records', title: 'Notifications', | `onTap: () => _go(AppRoutes.notifications),` |
| 93 | title: 'Notifications', title: 'Language', subtitle: 'English', | `onTap: () => _go(AppRoutes.language),` |

### `lib/features/home/view/bolt_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 15 | title: 'Bolt income check', | `toast: ObxUndoToast(controller: controller, onUndo: controller.undo),` |
| 17 | title: 'Bolt income check', | `? [AppButton('Back to things to check', onPressed: Get.back<void>)]` |
| 19 | title: 'Bolt income check', ? [AppButton('Back to things to check', onPressed: Get.back<void>)] | `AppButton('Add the £42.60 trip', onPressed: controller.addTrip),` |
| 23 | ? [AppButton('Back to things to check', onPressed: Get.back<void>)] AppButton('Add the £42.60 trip', onPressed: controller.addTrip), const AppButton( | `onPressed: _noop,` |

### `lib/features/home/view/check_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 16 | title: 'Things to check', subtitle: 'Nothing counts until you confirm it', | `toast: ObxUndoToast(controller: controller, onUndo: controller.undo),` |
| 53 | child: _ReceiptCard( | `onConfirm: () => controller.confirm(i),` |
| 101 | : Pressable( | `onTap: () => Get.toNamed<void>(AppRoutes.boltCheck),` |
| 192 | child: AppButton( | `onPressed: onConfirm,` |
| 205 | AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.reviewReceipt),` |

### `lib/features/home/view/dates_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 20 | title: 'Key dates', return Pressable( | `onTap: () => books.datesInCalendar.toggle(),` |
| 135 | TextLink( | `onTap: () => Get.toNamed<void>(AppRoutes.mtd),` |

### `lib/features/home/view/home_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 38 |  | `child: ObxUndoToast(controller: controller, onUndo: controller.undo),` |
| 66 | Pressable( | `onTap: () {},` |
| 95 | Widget _bell(int unread) => Pressable( | `onTap: controller.openNotifications,` |
| 132 | return Tile( | `onTap: () => Get.toNamed<void>(AppRoutes.year),` |
| 189 | Widget _check() => Tile( | `onTap: controller.openCheckSheet,` |
| 210 | Widget _week() => Tile( | `onTap: () => Get.toNamed<void>(AppRoutes.week),` |
| 250 | Widget _miles() => Tile( | `onTap: () => Get.toNamed<void>(AppRoutes.car),` |
| 276 | Widget _keyDate() => Pressable( | `onTap: () => Get.toNamed<void>(AppRoutes.dates),` |

### `lib/features/home/view/notifications_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 22 | title: 'Notifications', child: Pressable( | `onTap: read ? null : () => books.notificationsRead.value = true,` |
| 163 | return Pressable( | `onTap: () => Get.toNamed<void>(route),` |

### `lib/features/home/view/week_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 163 | child: RoundIconButton( label: label, | `onTap: onTap,` |

### `lib/features/home/widget/add_sheet.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 33 | RoundIconButton( label: 'Close', | `onTap: Get.back<void>,` |
| 41 | Tile( | `onTap: () => _go(AppRoutes.camera),` |
| 118 | return Tile( | `onTap: onTap,` |

### `lib/features/home/widget/check_sheet.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 30 |  | `AppButton('Done', onPressed: Get.back<void>),` |
| 50 | TextLink( | `onTap: () { Get.back<void>(); Get.toNamed<void>(AppRoutes.check); },` |
| 92 |  | `child: AppButton(r.action, onPressed: controller.confirmNext),` |
| 99 | child: AppButton(r.action, onPressed: controller.confirmNext), AppButton( | `onPressed: () { Get.back<void>(); Get.toNamed<void>(AppRoutes.reviewReceipt); },` |

### `lib/features/home/widget/first_day_home.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 30 | Pressable( | `onTap: () => Get.toNamed<void>(AppRoutes.language),` |
| 117 | }) => Tile( | `onTap: onTap,` |

### `lib/features/money/view/add_expense_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 19 | title: 'Type an expense', () => AppButton( | `onPressed: Get.back<void>,` |
| 32 | SelectCard( | `onTap: () => controller.category.value = i,` |

### `lib/features/money/view/add_fare_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 15 | title: 'Add a fare', | `bottom: [AppButton('Add £18.00', onPressed: Get.back<void>)],` |
| 50 | return ChipWrap( | `onTap: controller.source.call,` |
| 63 | () => ChoiceRow( label: 'How you were paid', | `onSelect: controller.payment.call,` |

### `lib/features/money/view/all_money_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 23 | title: 'All money in and out', trailing: RoundIconButton( label: 'Filter', | `onTap: controller.openFilter,` |
| 27 | trailing: RoundIconButton( label: 'Filter', TextField( | `onChanged: controller.query.call,` |
| 53 |  | `onSelect: controller.tab.call,` |
| 101 | title: r.name, subtitle: r.sub, | `onTap: r.route == null ? null : () => Get.toNamed<void>(r.route!),` |

### `lib/features/money/view/business_use_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 17 | title: 'How much is for work?', () => AppButton( | `onPressed: Get.back<void>,` |
| 35 | label: 'Phone used for driving', WorkShareSlider( | `onChanged: controller.percent.call,` |
| 45 |  | `onTap: () => controller.percent.value = v.toDouble(),` |

### `lib/features/money/view/camera_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 42 | RoundIconButton( label: 'Close camera', | `onTap: Get.back<void>,` |
| 57 | RoundIconButton( label: 'Flash off', | `onTap: () {},` |
| 127 | Pressable( | `onTap: () => Get.offNamed<void>(AppRoutes.readReceipt),` |
| 167 | Widget _square(Widget child, String label, VoidCallback onTap) => Pressable( | `onTap: onTap,` |

### `lib/features/money/view/categories_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 82 | Tile( | `onTap: () => Get.toNamed<void>(AppRoutes.personal),` |
| 120 | return Tile( | `onTap: () => route == null ? null : Get.toNamed<void>(route),` |

### `lib/features/money/view/category_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 52 | Tile( | `onTap: () => Get.toNamed<void>(AppRoutes.businessUse),` |
| 81 | : Tile( | `onTap: () => Get.toNamed<void>(AppRoutes.check),` |

### `lib/features/money/view/expense_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 23 | title: 'NCP car park', subtitle: 'Fri 16 Oct at 14:22', | `toast: ObxUndoToast(controller: controller, onUndo: controller.undo),` |
| 30 | child: AppButton( | `onPressed: added ? null : controller.add,` |
| 40 | AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.reviewReceipt),` |

### `lib/features/money/view/export_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 14 | title: 'Export your books', | `const AppButton('Share with my accountant', onPressed: _noop),` |
| 19 | title: 'Export your books', const AppButton('Share with my accountant', onPressed: _noop), () => AppButton( | `onPressed: _noop,` |
| 31 | () => ChoiceRow( label: 'Tax year', | `onSelect: controller.year.call,` |
| 46 | SelectCard( | `onTap: () => controller.format.value = i,` |
| 82 | () => AppSwitch( | `onChanged: controller.photos.call,` |

### `lib/features/money/view/income_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 80 | Widget build(BuildContext context) => Pressable( | `onTap: onTap ?? () {},` |

### `lib/features/money/view/money_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 42 | RoundIconButton( label: 'Search your money', | `onTap: () => _go(AppRoutes.allMoney),` |
| 83 | Tile( | `onTap: () => _go(AppRoutes.check),` |
| 105 | Tile( | `onTap: () => _go(AppRoutes.platformCheck),` |
| 144 |  | `TextLink('See all', onTap: () => _go(AppRoutes.allMoney)),` |
| 193 | return Tile( | `onTap: () => _go(route),` |
| 211 | child: Tile( | `onTap: () => _go(route),` |
| 236 | title: name, subtitle: sub, | `onTap: route == null ? null : () => _go(route),` |

### `lib/features/money/view/platform_check_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 37 |  | `onTap: () => Get.toNamed<void>(AppRoutes.boltCheck),` |
| 68 | }) => Tile( | `onTap: onTap,` |

### `lib/features/money/view/read_receipt_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 26 | title: done ? 'Here’s what we read' : 'Reading your receipt', | `onBack: () => Get.offNamed<void>(AppRoutes.camera),` |
| 36 | child: AppButton( | `onPressed: done` |

### `lib/features/money/view/receipts_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 54 |  | `onTap: () => controller.filter.value = i,` |
| 120 | child: Tile( semanticLabel: '$name, $detail, $label', | `onTap: () => route == null ? null : Get.toNamed<void>(route!),` |

### `lib/features/money/view/review_receipt_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 12 | title: 'Check what we read', | `toast: ObxUndoToast(controller: controller, onUndo: controller.undo),` |
| 18 | title: 'Check what we read', return AppButton( | `onPressed: saved ? null : controller.save,` |
| 76 | () => AppDropdown( label: 'Type', | `onChanged: controller.type.call,` |
| 96 | label: 'Used for work', WorkShareSlider( | `onChanged: controller.percent.call,` |
| 185 |  | `onChanged: onChanged,` |

### `lib/features/money/view/statement_added_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 18 | title: 'Bolt statement added', subtitle: 'Week of 5 to 11 October', AppButton( | `onPressed: () => Get.offNamed<void>(AppRoutes.platformCheck),` |
| 69 | AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.boltCheck),` |

### `lib/features/money/view/upload_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 17 | title: 'Upload a statement', AppButton( | `onPressed: () => Get.offNamed<void>(AppRoutes.statementAdded),` |
| 32 |  | `onTap: () => Get.offNamed<void>(AppRoutes.statementAdded),` |
| 97 | child: Tile( | `onTap: onTap ?? () {},` |

### `lib/features/money/widget/filter_sheet.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 21 | Pressable( | `onTap: controller.clearFilters,` |
| 44 | ChipWrap( | `onTap: controller.when.call,` |
| 51 | ChipWrap( | `onTap: controller.toggleSource,` |
| 58 | ChipWrap( | `onTap: controller.toggleCategory,` |
| 61 | ChipWrap( | `AppButton('Show results', onPressed: Get.back<void>),` |

### `lib/features/onboarding/view/claim_method_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 20 | title: 'How will you claim for LM72 KPF?', AppButton( | `onPressed: controller.openLockIn,` |
| 28 | SelectCard( | `onTap: () => controller.claimMethod.value = i,` |

### `lib/features/onboarding/view/code_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 20 | title: 'Enter the 6-digit code', AppButton( | `onPressed: ok ? () => Get.toNamed<void>(AppRoutes.secure) : null,` |
| 37 | Pressable( | `onTap: Get.back<void>,` |
| 142 |  | `onChanged: _controller.setCode,` |

### `lib/features/onboarding/view/create_account_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 18 | title: 'Create your account', subtitle: 'Free for 3 months. No card needed.', AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.code),` |
| 52 | AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.secure),` |
| 69 |  | `onPressed: () => Get.toNamed<void>(AppRoutes.secure),` |

### `lib/features/onboarding/view/driving_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 23 | title: 'How do you drive?', AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.platforms),` |
| 32 | SelectCard( | `onTap: () => controller.licence.value = i,` |
| 54 | AppDropdown( label: 'Which council licenses you?', | `onChanged: controller.council.call,` |
| 63 | ChoiceRow( label: 'When do you drive?', | `onSelect: controller.fullTime.call,` |

### `lib/features/onboarding/view/earnings_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 52 | }) => Tile( | `onTap: onTap,` |

### `lib/features/onboarding/view/how_it_works_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 15 | title: "Here's how it works", AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.createAccount),` |

### `lib/features/onboarding/view/language_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 18 | title: 'Choose your language', subtitle: AppButton( | `onPressed: controller.continueFromLanguage,` |
| 28 |  | `onTap: () => controller.language.value = l.code,` |
| 51 | Widget build(BuildContext context) => SelectCard( | `onTap: onTap,` |

### `lib/features/onboarding/view/other_income_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 19 | title: 'Any other income?', subtitle: 'It changes how much tax your driving profit pays.', AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.taxDetails),` |
| 39 | ChoiceRow( label: 'A job where tax comes off your pay', | `onSelect: (i) => controller.hasJob.value = i == 0,` |

### `lib/features/onboarding/view/platforms_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 23 | title: 'Where do you get work?', subtitle: 'Pick all that apply.', AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.otherIncome),` |
| 32 | SelectCard( | `onTap: () => controller.togglePlatform(i),` |

### `lib/features/onboarding/view/reading_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 34 | AppButton( | `onPressed: done ? () {} : null,` |
| 39 | AppButton( AppButton( | `onPressed: done` |

### `lib/features/onboarding/view/reminders_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 16 | title: 'Want a nudge now and then?', subtitle: | `AppButton('Turn on reminders', onPressed: controller.finish),` |
| 20 | title: 'Want a nudge now and then?', subtitle: AppButton('Turn on reminders', onPressed: controller.finish), AppButton( | `onPressed: controller.finish,` |
| 57 | AppSwitch( | `onChanged: (_) => controller.toggleReminder(i),` |

### `lib/features/onboarding/view/secure_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 19 | title: 'Keep your books private', subtitle: AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.driving),` |
| 52 | AppSwitch( | `onChanged: controller.faceId.call,` |
| 108 | () => ChoiceRow( label: 'Lock the app after', | `onSelect: controller.lockAfter.call,` |

### `lib/features/onboarding/view/sign_in_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 37 | const TextLink('Use my email instead'), Tile( | `onTap: controller.signIn,` |
| 75 | label: 'Mobile number', AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.code),` |

### `lib/features/onboarding/view/tax_details_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 18 | title: 'Your tax details', subtitle: AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.vehicle),` |
| 23 | AppButton( AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.vehicle),` |

### `lib/features/onboarding/view/trial_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 18 | title: '3 months free, then £1.99 a month', subtitle: AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.reminders),` |

### `lib/features/onboarding/view/vehicle_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 18 | title: 'Add your car', subtitle: "Type the number plate. We'll find the rest.", AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.claimMethod),` |
| 23 | AppButton( const AppButton( | `onPressed: _noop,` |

### `lib/features/onboarding/view/welcome_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 25 | AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.howItWorks),` |
| 31 | AppButton( AppButton( | `onPressed: () => Get.toNamed<void>(AppRoutes.signIn),` |

### `lib/features/onboarding/widget/language_pill.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 14 | Widget build(BuildContext context) => Pressable( | `onTap: () => Get.toNamed<void>(AppRoutes.language),` |

### `lib/features/onboarding/widget/lock_in_sheet.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 50 |  | `AppButton('Continue', onPressed: controller.continueAfterLockIn),` |
| 92 | HoldToConfirmButton( label: 'Hold to lock in', | `onConfirmed: controller.lockIn,` |
| 105 | AppButton( | `onPressed: Get.back<void>,` |

### `lib/features/shell/view/shell_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 29 |  | `onSelect: controller.select,` |
| 30 |  | `onSnap: controller.openAddSheet,` |

### `lib/features/shell/widget/app_tab_bar.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 51 | child: Pressable( | `onTap: () => onSelect(tab),` |
| 92 | Widget _snap() => Pressable( | `onTap: onSnap,` |

### `lib/features/tax/view/class4_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 36 | Tile( | `onTap: () => Get.toNamed<void>(AppRoutes.forecast),` |

### `lib/features/tax/view/mtd_quarters_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 53 |  | `onTap: () => Get.toNamed<void>(AppRoutes.mtdSend),` |
| 103 | }) => Tile( | `onTap: onTap,` |

### `lib/features/tax/view/mtd_send_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 62 | HoldToConfirmButton( label: 'Hold to send to HMRC', | `onConfirmed: () => controller.sent.value = true,` |

### `lib/features/tax/view/mtd_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 104 | label: 'See what quarterly updates look like', | `onTap: () => Get.toNamed<void>(AppRoutes.mtdQuarters),` |

### `lib/features/tax/view/other_tax_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 41 | const AppButton( | `onPressed: _noop,` |
| 57 | const AppButton( | `onPressed: _noop,` |

### `lib/features/tax/view/poa_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 85 | label: "See everything you'll pay, and when", | `onTap: () => Get.toNamed<void>(AppRoutes.timeline),` |

### `lib/features/tax/view/pot_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 14 | title: 'Your tax pot', subtitle: "Money you've moved to savings for tax", | `toast: ObxUndoToast(controller: controller, onUndo: controller.undo),` |
| 73 | child: AppButton( | `onPressed: () => controller.add(p),` |

### `lib/features/tax/view/tax_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 38 | Tile( | `onTap: () => _go(AppRoutes.workings),` |
| 65 | Tile( | `onTap: () => _go(AppRoutes.pot),` |
| 152 | Widget _lilac(String label, String amount, String sub, String route) => Tile( | `onTap: () => _go(route),` |
| 166 |  | `LinkRow(title: title, subtitle: sub, onTap: () => _go(route));` |

### `lib/features/tax/view/timeline_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 47 |  | `const AppButton('How to pay HMRC', onPressed: _noop),` |

### `lib/features/tax/view/workings_view.dart`

| Line | Trigger/context | Callback source |
| --- | --- | --- |
| 89 | Pressable( | `onTap: () => Get.toNamed<void>(route),` |

Definition-site count: 184. ColorScheme onPrimary/onSurface are color properties, not callbacks.
