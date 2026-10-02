# نسخهٔ ۲.۶.۰ — سیستم لاگ و تشخیص معاملات (2026-10-01)

**هدف این مرحله فقط دیدن است، نه تغییر رفتار.** هیچ استراتژی، آستانه یا فیلتری عوض نشده.
از این به بعد برای هر فرصت معلوم است چه شد و چرا، تا اصلاح اسکالپ در ۲.۶.۱ روی دادهٔ واقعی انجام شود.

## ۱) فایل‌های ایجادشده / تغییرکرده

**جدید**
| فایل | نقش |
|---|---|
| `app/logging/categories.py` | ۱۲ دستهٔ لاگ (APPLICATION … AUDIT) و نگاشت نام لاگر به دسته |
| `app/logging/structured.py` | رکورد ساختاریافته، صف غیرمسدودکننده، فایل روزانه/حجمی، بافر زنده، خواندن تاریخچه |
| `app/logging/audit.py` | کدهای استاندارد رد، خلاصهٔ پویش (`ScanDiagnostics`)، رویدادهای signal/candidate/reject/entry/exit |
| `app/logging/audit_store.py` | نوشتن دسته‌ای رویدادهای ممیزی در SQLite از رشتهٔ پس‌زمینه |
| `app/logging/query.py` | فیلتر (`LogFilter`)، مراحل خط زمانی، جمع خلاصهٔ پویش، خروجی CSV/JSONL/TXT |
| `app/database/repositories/audit_repository.py` | جست‌وجو، خط زمانی معامله، خلاصه‌های پویش، پاک‌سازی |
| `ui/pages/log_center_page.py` | صفحهٔ «مرکز لاگ» |
| `localization/{fa,en}/logs.json` | متن‌های مرکز لاگ |
| `tests/test_v260_logging.py` | ۵۴ آزمون |

**تغییرکرده (فقط ثبت؛ هیچ شرطی عوض نشده)**
| فایل | تغییر |
|---|---|
| `app/database/models.py` | مدل `AuditEventRecord` (جدول `audit_events`؛ با `create_all` ساخته می‌شود، مهاجرت لازم نیست) |
| `app/logging/logger.py`، `main.py` | `configure_logging(structured_dir=...)` لایهٔ ساختاریافته را روشن می‌کند؛ `app.log` مثل قبل می‌ماند |
| `app/application.py` | `audit_repository` و وصل‌شدن ذخیرهٔ ممیزی؛ جداشدن در `stop()` |
| `app/database/repositories/trade_repository.py` | ممیزی ورود، بستن جزئی و خروج پس از commit (همهٔ مسیرها: خودکار، سیگنال، دستی) |
| `trading/auto_trader.py` | شناسهٔ همبستگی `audit_id`، مرحلهٔ جاری دروازه‌ها، رویداد رد با عکس کامل، سیگنال/نامزد/اعتبارسنجی، تصمیم خروج، خلاصهٔ پویش |
| `trading/scalp_scanner.py` | پارامتر اختیاری `on_reject` در `score_candidate` (خروجی و آستانه‌ها همان) |
| `trading/scalp_service.py`، `trading/ultra_scalp.py`، `trading/confidence_source.py` | گزارش شمارش‌ها به خلاصهٔ پویش با `note_scan` |
| `ui/controllers/main_controller.py` | گزارش حذف‌های `feasibility` (`target_infeasible`)؛ وصل کردن مرکز لاگ؛ Ctrl+R |
| `ui/windows/main_window.py`، `ui/pages/__init__.py`، `ui/icons/paths.py`، `localization/*/nav.json` | ثبت صفحه، آیکون `logs` |
| `tests/test_new_pages.py` | ۱۲ صفحه به‌جای ۱۱ |

## ۲) ساختار لاگ

هر رکورد یک خط JSON است:

```json
{"ts": "2026-10-01T14:03:07.412+03:30", "epoch": 1790000000.41, "level": "INFO", "category": "scalp",
 "module": "audit", "message": "Rejected BTC/USDT: spread_eats_stop", "event": "reject",
 "symbol": "BTC/USDT", "reason_code": "spread_eats_stop", "correlation_id": "4f1c…", "scan_id": "…",
 "context": {"reason_detail": "spread_eats_stop:0.200%", "bucket": "spread", "stage": "risk_levels",
             "filters": {"precheck": "pass", "market_guards": "pass", "orderbook": "pass", "sizing": "pass",
                         "pricing": "pass", "risk_levels": "fail", "revalidation": "not_run"},
             "bid": 99.9, "ask": 100.1, "spread_percent": 0.2, "liquidity_24h": 5000000,
             "technical_confidence": 80, "round_trip_cost_percent": 0.36, "decision": "skip"}}
```

- **دسته‌ها:** APPLICATION, TRADING, SCALP, SIGNALS, ORDERS, EXCHANGE, MARKET, RISK, AI, ERROR, PERFORMANCE, AUDIT.
  دسته از نام لاگر تعیین می‌شود (`trading.scalp*`/`trading.ultra*` → SCALP، `market.providers.*` → EXCHANGE و …).
- **سطح‌ها:** DEBUG / INFO / WARNING / ERROR / CRITICAL.
- **مسیر داغ:** `logger.log()` فقط رکورد را در صف می‌گذارد (`put_nowait`). اگر صف پر باشد، رکورد دور ریخته و شمرده می‌شود و
  هیچ‌وقت منتظر نمی‌ماند. فایل و SQLite در رشتهٔ پس‌زمینه نوشته می‌شوند. همهٔ توابع ممیزی خطا را می‌بلعند.
- **کم‌حجم:** رد تکراری همان نماد با همان کد در ۳۰ ثانیه فقط در نمای زنده می‌آید و تعداد تکرارهای حذف‌شده ثبت می‌شود.
  خلاصهٔ پویش هر ۱۰ ثانیه یک‌بار تجمیعی ذخیره می‌شود و هر بار که معامله‌ای باز شود هم ذخیره می‌شود.
  مقدارهای حساس (کلید و رمز) پیش از نوشتن پوشانده می‌شوند.

### کدهای استاندارد رد (سطل خلاصه)
`stale_data, stale_candidate, no_price, data_error, invalid_candidate` (data) ·
`low_volatility, high_volatility, low_momentum` (volatility) ·
`cost_too_high, negative_expectancy, fees_exceed_budget` (cost) ·
`wide_spread, spread_eats_stop` (spread) ·
`trend_conflict, no_direction` (trend) ·
`low_confidence, ai_rejected` (confidence) ·
`low_liquidity` (liquidity) ·
`negative_edge` (edge) ·
`risk_exceeded, daily_loss_limit, insufficient_margin, invalid_risk, poor_reward_risk, max_concurrent, symbol_already_open, symbol_not_selected, invalid_config` (risk) ·
`target_unreachable, target_infeasible` (target) ·
`no_orderbook` (orderbook) ·
`exchange_error, live_not_enabled` (other).

دلیل خام موتور با عددش در `reason_detail` می‌ماند، مثلاً `target_unreachable:0.010%<0.300%`.

## ۳) رویدادهایی که ثبت می‌شوند

| رویداد | محتوا |
|---|---|
| `reject` | نماد، جهت، کد و جزئیات، مرحله، نقشهٔ pass/fail/not_run فیلترها، قیمت، Bid/Ask/Last، اسپرد، نقدینگی، نوسان ثانیه‌ای، روند، اطمینان فنی، احتمال، اطمینان AI، MTF، orderflow، استراتژی، هزینهٔ رفت‌وبرگشت |
| `signal` → `candidate` → `validation` | برای نامزدی که از همهٔ دروازه‌ها گذشت: عکس هوش سیگنال، عکس بازار، و برنامهٔ ورود (ورود، SL، TP، حجم، مارجین، اهرم، Bid/Ask) |
| `entry` | trade_id، جهت، قیمت ورود، Bid/Ask، اسپرد، حجم، notional، مارجین، اهرم، SL، TP، اهداف، RR مورد انتظار، کارمزد تخمینی، لغزش تخمینی، عکس سیگنال/اطمینان، منبع (خودکار/دستی/سیگنال) |
| `partial_exit` | هدف (TP1/TP2)، حجم، قیمت، حد ضرر جدید |
| `exit_decision` | دلیل خروج، قیمت تصمیم، Bid/Ask و اسپرد، جهت سیگنال در لحظهٔ خروج |
| `exit` | قیمت و زمان خروج، مدت نگه‌داری، دلیل، سود ناخالص، کارمزد، لغزش، سود خالص، درصد، نتیجه (win/loss/breakeven) |
| `scan_summary` | Scanned, Raw, Rejected by Volatility/Cost/Spread/Trend/Confidence/Liquidity/Edge/Risk/Target/OrderBook/Data/Other, Source, Final, Opened و دلایل به تفکیک کد |
| `performance` | زمان منبع نامزد؛ فقط وقتی کند باشد (بیش از ۲ ثانیه) ذخیره می‌شود |
| خطاها | هر ERROR یا CRITICAL از هر ماژول (با traceback) |

رویدادهای یک تلاش ورود با `correlation_id` به هم و به `trade_id` وصل‌اند.

## ۴) محل ذخیره

- **فایل‌ها:** `data/logs/<دسته>/<دسته>-YYYY-MM-DD.jsonl`، برای این پوشه‌ها:
  `application, trading, scalp, signals, orders, exchange, market, risk, ai, errors, performance, audit`.
  - هر روز فایل تازه باز می‌شود.
  - هر فایل حداکثر ۱۰ مگابایت است و بعد `…-YYYY-MM-DD.N.jsonl` ساخته می‌شود.
  - فایل‌ها ۱۴ روز نگه داشته می‌شوند و هر دسته حداکثر ۶۰ فایل دارد.
  - هر ERROR+ در `errors/` هم نوشته می‌شود و هر رویداد ممیزی در `audit/` هم.
- **SQLite:** همان پایگاه دادهٔ برنامه، جدول `audit_events`، با نمایه روی زمان، نماد، trade_id، کد دلیل، پویش و همبستگی.
  رکوردها ۳۰ روز یا حداکثر ۵۰۰٬۰۰۰ ردیف نگه داشته می‌شوند. فایل جداگانه‌ای ساخته نشد.
- `data/logs/app.log` و `crash.log` مثل قبل سر جایشان هستند.

## ۵) مرکز لاگ (منوی کناری، پس از «گزارش‌ها»)

- **لاگ زنده:** هر ۰٫۷ ثانیه به‌روز می‌شود و فقط وقتی صفحه باز است.
  - فیلترها: دسته، حداقل سطح، نماد، شناسهٔ معامله، بازهٔ تاریخ و ساعت، و جست‌وجو در پیام و جزئیات.
  - دکمه‌ها: پاک کردن (فقط نمای صفحه)، تازه‌سازی، خروجی (CSV/JSONL/TXT)، کپی (ردیف‌های انتخابی یا همهٔ ردیف‌های دیده‌شده).
  - گزینه‌ها: پیمایش خودکار و توقف نمایش.
  - با کلیک روی هر ردیف، JSON کامل آن نمایش داده می‌شود.
  - با تیک «تاریخچه»، همین فیلترها روی فایل‌ها و پایگاه داده اجرا می‌شوند.
- **تشخیص پویش:** جدول آخرین پویش در برابر جمع خلاصه‌های ذخیره‌شده (هر موتور جدا: ultra/scan/selected/ai) و پرتکرارترین دلایل رد.
- **خط زمانی معامله:** شناسهٔ معامله را انتخاب یا وارد کنید تا مراحل Signal → Candidate → Validation → Entry → Monitoring → Exit
  با وضعیت هر مرحله، زمان آن و همهٔ رویدادها و جزئیاتشان نمایش داده شوند.

## ۶) آزمون‌ها

`tests/test_v260_logging.py` شامل ۵۴ آزمون است:
- دسته‌ها و کدهای استاندارد؛
- رد با عکس بازار و نقشهٔ فیلترها، و حذف تکرار؛
- سیگنال، نامزد، اعتبارسنجی و ورود؛
- خروج؛
- مسیر دستی و بستن جزئی؛
- خطاها؛
- پوشاندن کلیدها؛
- خط زمانی از SQLite؛
- جست‌وجو و پاک‌سازی؛
- خلاصهٔ پویش؛
- آمار اولترا؛
- `on_reject` بدون تغییر خروجی؛
- چرخش روزانه و حجمی، نگه‌داری و سقف تعداد فایل؛
- فیلتر و خروجی؛
- ادامهٔ معامله با لاگر خراب، با همهٔ توابع ممیزی خراب، با هندلر خراب و با پایگاه داده قفل؛
- صف پر بدون انتظار؛
- هزینهٔ هر رویداد کمتر از ۱ میلی‌ثانیه؛
- صفحهٔ مرکز لاگ.

همهٔ آزمون‌های قبلی هم اجرا شدند. نتیجه در گزارش تحویل آمده است.

## یادداشت صادقانه

- این نسخه هیچ معامله‌ای را بیشتر یا کمتر نمی‌کند. فقط نشان می‌دهد هر نامزد کجا می‌افتد.
- رویداد `signal` برای نامزدهایی ثبت می‌شود که به ورود رسیدند. سیگنال‌های عمومی صفحهٔ سیگنال‌ها از طریق لاگرهای ماژول
  `signals.*` در دستهٔ SIGNALS هستند، نه به‌صورت رویداد ممیزی جدا برای هر سیگنال.
- منبع اطمینان (`confidence`) فقط سیگنال‌های بالای حد را برمی‌گرداند. پس رد «زیر حد اطمینان» و «بدون جهت» در آن منبع
  با هم زیر `low_confidence` شمرده می‌شوند.
