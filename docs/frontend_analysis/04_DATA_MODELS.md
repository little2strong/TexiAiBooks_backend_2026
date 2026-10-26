# Data models and state

Analysis: 27 October 2026. OBSERVED Dart objects below are fixture/presentation structures, not API DTOs. No model/domain/data directories, fromJson/toJson, generated serializers, ORM models or persistent entities exist. Constructor-required values are distinguished from nullable values. Widget configuration classes are UI props, not backend entities; complete class index is in document 01.

## Domain-like and report fixture classes

| Class and exact path | Fields and Dart types | Required/null/defaults | Relationships/mock usage | PROPOSED backend entity |
| --- | --- | --- | --- | --- |
| ReceiptToCheck; lib/core/services/books_service.dart | name:String; what:String; amount:String; note:String; action:String; claimPence:int; toast:String | All required named constructor args, non-null, no defaults | BooksService.receipts contains EE (claim 2600), NCP (650), Shell (0); Home/Check/Expense use fixture index | receipts + transactions + claim decisions; replace formatted amount/note/action with typed values/status/reason codes |
| Language; lib/features/onboarding/controller/onboarding_controller.dart | code:String; native:String; english:String; rtl:bool; cta:String | Five required positional args | Seven static languages; LanguageView; selectedLanguage finds by code | Static language reference plus user preference; no mandatory DB table |
| ClaimMethod; same onboarding controller file | title:String; tag:String; what:String; best:String; short:String | Five required positional args | Two static mileage/actual-cost cards; ClaimMethodView/LockInSheet | vehicle_claim_elections; explanatory strings stay translated presentation content |
| DayEarnings; lib/features/home/controller/week_controller.dart | dow:String; label:String; pence:int?; miles:int | Four required positional args, pence allows null | WeekData.days; null future day, zero actual no-trip day | Aggregation over transactions/mileage_logs, no table needed |
| WeekData; same week controller file | title:String; range:String; miles:int; compare:String; days:List<DayEarnings>; sources:List<(String,int)>; computed totalPence:int | All six named fields required; total sums pence ?? 0 | Two WeekController.weeks fixtures; source records label+pence; WeekView | Report DTO with ISO dates and raw integer values, not persisted totals |
| MoneyItem; lib/features/money/controller/all_money_controller.dart | day:String; name:String; sub:String; amount:String; kind:MoneyKind; route:String? | First five required positional args; optional route default null | Eleven static list records; AllMoney search/tab/group; amount/date are display strings | transactions with UUID/date/amount/category/source; route remains frontend concern |

## Presentation value models

| Class / path | Fields / defaults / relationships |
| --- | --- |
| ColumnBar; lib/core/widgets/charts.dart | required named label:String and height:double; value:String='', color:Color=AppColors.ink, border:Border?=null, dashed:bool=false, bold:bool=false. Used by home/week/year charts; no JSON/DB equivalent. |
| BarSegment; same charts.dart | fraction:double and color:Color required positional; border:Color? optional named=null. Used for stacked bars; no JSON/DB equivalent. |
| UpperCaseFormatter; lib/features/onboarding/view/vehicle_view.dart | No data fields; formats TextEditingValue text to upper case, not a vehicle model. |
| ApiClient; lib/core/network/api_client.dart | final dio:Dio; optional injected Dio or constructed config. Infrastructure, not DTO. |

## Enums

| Exact class/file | Values | Meaning / backend caution |
| --- | --- | --- |
| AppTab; lib/features/shell/controller/shell_controller.dart | home, money, tax, driver | Client navigation only |
| MoneyKind; lib/features/money/controller/all_money_controller.dart | moneyIn, out, check | Mixes direction and review status; backend must keep kind and status independent |
| ReceiptStatus; lib/features/money/view/receipts_view.dart | toCheck, counted, notClaimed | Static grid presentation status; backend needs separate processing/review/claim status |
| ButtonKind; lib/core/widgets/buttons.dart | primary, secondary, ghost, outline | UI style only |
| AppIcons; lib/core/widgets/app_icon.dart | Embedded SVG icon identifiers, with markup:String, stroke:double | UI asset enum; not a server entity |

## Shared BooksService state and derived values

Exact file: lib/core/services/books_service.dart::BooksService extends GetxService. No serialization.

| Member | Type/default | Rule / limitation |
| --- | --- | --- |
| firstName | static const String Ali | Persona fixture, not authenticated identity |
| incomePence | static const int 1245000 | GBP 12,450, immutable |
| baseExpensesPence | static const int 632750 | GBP 6,327.50, fixture base |
| potTargetPence | static const int 122450 | Fixed tax target, independent of changed profit |
| receipts | static const List<ReceiptToCheck> (3) | Receipt identity is list index, no UUID/date/category/currency/image |
| demo | static const bool true | finish opens demo books |
| hasData | RxBool true | Controls empty Home only, does not clear fixture books |
| confirmed | RxList<int> [] | Receipt indices in confirmation order |
| boltResolved/notificationsRead/datesInCalendar | RxBool false each | Global boolean, no per-item records |
| potPence | RxInt 90000 | Savings fixture GBP 900 |
| potLog | RxList<int> [] | New positive additions only; starting balance not logged |
| expensesPence | computed int | base plus confirmed receipt claimPence |
| profitPence/taxPence | computed int | income minus expenses; round(profit*0.2) |
| receiptsLeft/thingsToCheck/unread | computed int | 3 minus confirms; plus unresolved Bolt; unread 3 or 0 |
| nextReceipt | computed int? | First unconfirmed index, otherwise null |

## Controller state/defaults

| Class / path | State and defaults | Mock/relationship |
| --- | --- | --- |
| OnboardingController; onboarding/controller/onboarding_controller.dart | language RxString en; code RxString empty; faceId RxBool true; lockAfter RxInt 1; licence RxInt 0; council RxString first council; fullTime RxInt 0; platforms RxList<bool> [true,true,false,true,true]; hasJob RxBool true; claimMethod RxInt 0; locked RxBool false; reminders RxList<bool> [true,true,true] | No captured phone/employer/pay/UTR/NI/vehicle fields; static phone used for all OTP displays |
| ShellController; shell/controller/shell_controller.dart | tab Rx<AppTab> home; optional typed route argument | Navigation only |
| HomeController/CheckController/BoltController; home/controller/*_controller.dart | BooksService reference + UndoToastMixin state | No own transaction model; shared fixture flags |
| WeekController; home/controller/week_controller.dart | index RxInt 0; two static weeks | Current 37200p/214 miles; last 41820p/236; sources as records |
| AllMoneyController; money/controller/all_money_controller.dart | tab RxInt 0; query RxString empty; when RxInt 0; source bool list all false; category bool list only parking index1 true | Only query/tab affect groups; default visible filter has no effect |
| AddFareController; money/controller/entry_controllers.dart | source RxInt 0; payment RxInt 0 | No amount/date/note state |
| AddExpenseController; same entry file | category RxInt 0; static fuel index 4; computed isFuel | No amount/date/evidence state |
| ExportController; same entry file | year RxInt 0; format RxInt 0; photos RxBool true; computed downloadLabel | Years 2026/27 and 2025/26; PDF/spreadsheet; no job |
| ReceiptsController; same entry file | filter RxInt 0 | Grid tuples live in view, independent of shared receipts |
| ExpenseController; money/controller/receipt_controllers.dart | receiptIndex:int required constructor; BooksService; computed added | Binding always passes 1 |
| ReviewReceiptController; same receipt file | percent RxDouble 50; type RxString Phone and data; saved RxBool false; static billPence 5200; claimPence computed | Save confirms fixed index0; other edits not captured |
| BusinessUseController; same receipt file | percent RxDouble 50; billsPence static 31200; computed claim/saving | Not linked to ReviewReceiptController/category totals |
| PotController; tax/controller/tax_controllers.dart | BooksService; static amounts List<int> [2500,5000,10000]; computed gap/ratio/status | Fixed target; ratio clamps 0-1 |
| MtdSendController; same tax file | sent RxBool false | No submission/business/period IDs |
| UndoToastMixin; lib/core/widgets/feedback.dart | toastText RxString empty; toastVisible RxBool false; private Timer? null | Ephemeral presentation, four-second stay; not durable action history |

## Anonymous records, arrays and fixed reports

ReceiptsView._receipts is nine (String,String,ReceiptStatus,String?) records; labels advertise 51/21/27/3. YearView monthly/source/expense tuples are independent literals. ReadingView._found and ReadReceiptView._read are (String,String) labels/values. Notification/deadline/platform/tax/MTD rows are embedded literals with formatted GBP/dates. ReadingHeader, PaperReceipt, PercentHeader, MohammedAvatar, cards and other widgets accept constructor props rather than DTOs. Do not persist UI colors, route strings, explanatory sentences or chart heights.

## Model gaps and target serialization (PROPOSED)

Introduce UUID identities, ISO dates, currency GBP and amount_pence integer values; separate gross income, fees and net payout. Separate transaction direction, processing status, review status and tax eligibility. Store raw OCR suggestions separately from driver corrections/confirmed decisions. Carry business_id/vehicle_id/source_id/category_id, rule version, owner and version for concurrency. Document 06 specifies typed wire schemas; document 08 proposes SQL entities. There is no existing JSON compatibility to preserve, but the externally reported expense API must be inspected before selecting field names/adapters.
