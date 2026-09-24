# حافظهٔ پروژه و نقشهٔ اتصال اجزا

تاریخ به‌روزرسانی: **۲۰۲۶-۰۹-۲۴** · نسخهٔ جاری: **2.4.2**

## وضعیت جاری ۲.۴.۲ — سبکی رابط و کپی سیگنال

گزارش کاربر پس از 2.4.1: «هنوز خیلی سنگین است و هنگ می‌کند» + «امکان کپی نام و اطلاعات
سیگنال در جدول یا مودال». علت‌های یافته: (۱) کاروان GIL — محاسبهٔ pandas پویش روی نخ
پس‌زمینه نخ رابط را پس از هر فراخوانی Qt معطل می‌کرد (پروفایل: ~۹۵٪ زمان هر نماد در
`compute_timeframe_analysis`)؛ (۲) تایمر ۳۰ ثانیه‌ای پیگیری نتیجه روی نخ رابط
`outcome_repository.performance()` (تا ۵۰۰۰ ردیف) را اجرا می‌کرد، حتی وقتی صفحه پنهان بود؛
(۳) پویش‌های پیاپی همان سیگنال را بی‌وقفه ذخیره و پیگیری می‌کردند (رشد پایگاه داده)؛
(۴) ترمینال معاملات هر ثانیه حتی پنهان رسم می‌شد. اصلاح: `signals/compute_pool.py`
(`ComputePool` با spawn، ≤۲ کارگر، اولویت پایین، fallback محلی، بستن در بیکاری) فقط در
`is_bulk_fetch()`؛ `SignalEngine.set_compute_pool`؛ `Application.compute_pool()`
(`performance.process_pool`، متغیر `CRYPTOAI_NO_PROCESS_POOL` که conftest روشن می‌کند)؛
`Application._should_store_scanned` (۳۰ دقیقه/۵ واحد)؛ `_refresh_outcome_view` تنبل با
`run_blocking` و `ShowWatcher`؛ `_terminal_timer_tick`؛ `UiStallWatchdog`؛
`multiprocessing.freeze_support()` در main.py. کپی: `ui/signal_share.py`، دکمه‌های
`SignalDetailDialog.copy_symbol/copy_info`، منوی راست‌کلیک و Ctrl+C در `SignalsPage`
(`copy_notice` → toast). آزمون: `tests/test_v242_lightweight_and_copy.py`. گزارش:
`docs/RELEASE_2.4.2_FA.md`. 2.4.0، 2.4.1 و 2.4.2 هنوز commit نشده‌اند.

## تحویل قبلی ۲.۴.۱ — سبک‌سازی پویش کل بازار

گزارش کاربر پس از 2.4.0: «بخش سیگنال خوب شد ولی سیستم خیلی سنگین است، هنگ می‌کند
و کل سیستم را درگیر می‌کند.» علت‌ها: (۱) هر کندلِ پویش (~۴۰۰۰ درخواست برای کل صرافی)
با ORM در SQLite نوشته می‌شد (دیسک و CPU)؛ (۲) کندل‌های پویش حافظهٔ نهان ۵۰۰تایی را پر
و تیکر/قیمت داغ را بیرون می‌انداختند؛ (۳) محاسبهٔ هم‌گام اندیکاتورها روی تنها حلقهٔ
asyncio تا ۴۰۰ms قفل می‌ساخت و با GIL رابط را کند می‌کرد؛ (۴) هر اندیکاتور DataFrame را
از نو می‌ساخت (~۳۵٪ CPU)؛ (۵) جدول پویش با صدها ردیف و ستون «به اندازهٔ محتوا» هر ۸۰۰ms
از نو رسم می‌شد. اصلاح: `market.engine.bulk_fetch()` (ContextVar)، `signals.scanner.CpuGovernor`
(دستی ۰٫۶، خودکار ۰٫۳۵)، انتظار در مکث نرخ، دروازهٔ محاسبه در `SignalEngine`،
`IndicatorEngine._calculate(frame_holder)`، numpy در `BaseIndicator.calculate`، سقف ۲۰۰ ردیف
و تازه‌سازی تطبیقی. آزمون: `tests/test_v241_performance.py`. گزارش: `docs/RELEASE_2.4.1_FA.md`.
2.4.0 و 2.4.1 هنوز commit نشده‌اند.

## تحویل قبلی ۲.۴.۰ — پویش کل بازار و منبع سیگنال‌گیری خودکار

درخواست کاربر: پویش سیگنال‌ها فقط روی تعداد محدودی نماد (پیش‌فرض ۶۰) اجرا می‌شد؛
تعداد دستی بماند ولی گزینه‌ای برای پویش همهٔ نمادهای صرافی باشد. سیگنال‌گیری
خودکار باید «چرخش کامل» را روی همهٔ نمادها انجام دهد و منبعش بین سیگنال‌های
پیداشده و کل بازار قابل‌انتخاب باشد. پیاده‌سازی: `signals/scan_universe.py` (جهان
پویش، پالایش هوشمند، اولویت نقدشوندگی/نوسان)، `MarketScanner.scan(universe, filters,
on_signal)`، `Application.scan_market(universe, min_turnover, smart_filter, on_signal)`،
`AutoScanConfig.source/universe/min_turnover/smart_filter` + `seed_focus`، کنترل‌های
تازه در `ui/pages/signals_page.py` و نتیجهٔ زنده/پیشرفت در `MainController`. کلیدهای
تازه: `signals.auto_scan_{source,universe,min_turnover,smart_filter}` و
`signals.scan_{universe,limit,min_turnover,smart_filter}`. آزمون:
`tests/test_v240_scan_universe.py`. گزارش: `docs/RELEASE_2.4.0_FA.md`. 2.3.2 با دستور
کاربر commit/push شد (`80ce0ab`)؛ 2.4.0 هنوز commit نشده است.

## تحویل تاریخی ۲.۳.۲ — اتصال LBank

گزارش کاربر: روی LBank حدود ۲۰ ثانیه آنلاین و بعد آفلاین؛ وب‌سوکت LBank هرگز وصل
نمی‌شد (صرافی‌های دیگر سالم). علت‌ها: جدول خطای LBank جابه‌جا بود و 10004
(«Request too frequent») خطای احراز هویت شمرده می‌شد → REST «مرده» و بدون مکث؛
provider.ping هم خطا را می‌بلعید؛ وب‌سوکت فقط `www.lbkex.net` (نشانی قدیمی) را
می‌شناخت. اصلاح: `market/providers/lbank/{constants,rest_client,provider,websocket_client}.py`،
`retry_async(no_retry_on=...)`، آمار عیب‌یابی در `RedundantStream.stats()`؛ تست
`tests/test_v232_lbank.py`. گزارش: `docs/RELEASE_2.3.2_FA.md`. stubهای Qt اکنون در
`.cache/qtstub` داخل مخزن (نادیده در snapshot) ساخته می‌شوند. با دستور کاربر commit/push شد (`80ce0ab`).

## تحویل تاریخی ۲.۳.۱ — اتصال پایدار و داشبورد

رگرسیون 2.3.0 (خواندن بدون کش همهٔ تیکرها هر ۲ ثانیه و کش مشترک ۰٫۱ ثانیه‌ای)
باعث محدودیت نرخ صرافی و «چند ثانیه آنلاین، بعد قطع» می‌شد. اصلاح: کش مشترک،
مکث سراسری 429/418، آنلاین از REST یا WS، snapshot هر ۳۰ ثانیه. داشبورد مرکز
فرمان گرفت (`ui/widgets/dashboard_widgets.py`، `summarise_market` در کنترلر).
گزارش: `docs/RELEASE_2.3.1_FA.md`. Qt در محیط لینوکس بدون libGL با stubهای
ساخته‌شده در `/home/user/qtstub` (خارج مخزن) اجرا شد. هیچ commit/push انجام نشده.

## تحویل تاریخی ۲.۳.۰ — معامله، اتصال افزونه و تاریخچه

به درخواست کاربر، ورود/خروج هم‌زمان و پایش اسکن از هم جدا شدند؛ محاسبات
خالص کارمزد و سر‌به‌سر، محافظ هزینه/ریسک و سقف زیان روزانهٔ پایدار اصلاح شد.
دو client مستقل از همان صرافی، watchdog، REST تازه و حفظ اشتراک نمودار اضافه شد.
ورود دستی از فرصت‌ها پس از موفقیت به تاریخچهٔ Open می‌رود؛ جدول کامل‌تر،
مودال جزئیات و خروج مشترک دارد. انتخاب قبل از تحلیل و چرخش بازار/علاقه‌مندی‌ها
اصلاح شد. هیچ سود، زیان صفر یا اتصال همیشگی تضمین نمی‌شود.

گزارش دقیق: `docs/RELEASE_2.3.0_FA.md`. آزمون انتخابی **۷۵۸ پاس + ۴ skip**؛
۵۰ رگرسیون تازه. ۳۳ آزمون قدیمی غیرنمایشی جداگانه نیز پاس شدند. full suite
هنوز ۳۰ خطای collection کتابخانهٔ Qt دارد؛ native GUI/ویندوز تأیید نشده است.
بسته: `CryptoAITrader-v2.3.0-2026-09-23.zip`؛ درگاه `tools/serve_downloads.py`.
هیچ commit/push/Release انجام نشده؛ پس از تست ZIP منتظر دستور صریح کاربر بمان.
R6 (feed/tick/trading) و R10 (دامنهٔ چرخش) فقط بخشی رفع شدند؛ agentها و
استقلال آستانهٔ watch هنوز بررسی می‌خواهند. R4/R5/R7/R8/R9 دست‌نخورده‌اند.
بخش‌های نسخه‌های قدیمی پایین، **تاریخی** هستند.

## تحویل تاریخی ۲.۲٫۲ — رفع سه ایراد و درگاه دانلود

به درخواست کاربر، R1 (کش پیش‌بینی)، R2 (انتقال کامل تنظیم‌های معامله و
سن مجاز دادهٔ کش متصل) و R3 (برچسب درست حساسیت backup بدون حذف ciphertext)
اصلاح شدند. جزئیات: [گزارش 2.2.2](RELEASE_2.2.2_FA.md).
آزمون ترکیبی هسته/درگاه: ۷۰۸ پاس + ۳ skip؛ تست کامل Qt/ویندوز تأیید نشده است.
صفحهٔ دانلود: `tools/serve_downloads.py` با template همراه، مستقل از دسکتاپ.
ZIP جدید: `CryptoAITrader-v2.2.2-2026-09-23.zip`؛ هیچ commit/push انجام نشده.
R4 تا R10 بررسی اولیه هنوز باز هستند؛ آن‌ها را رفع‌شده معرفی نکن.



> این فایل نقطهٔ شروع ادامهٔ کار است، نه ادعای حافظهٔ دائمیِ گفتگو یا تضمین بی‌اشکال بودن برنامه. در هر مرحله باید دوباره خوانده و مطابق کد همان مرحله به‌روز شود. قواعد کار در `AGENTS.md`، نمایهٔ فایل‌ها و نمادها در [CODE_MAP.md](CODE_MAP.md) و شواهد آزمون/ایرادها در [REVIEW_VALIDATION_FA.md](REVIEW_VALIDATION_FA.md) هستند.

## ۱. هویت نسخه و دامنهٔ بررسی

- مخزن: `hhajtalebi/CryptoAITrader`.
- نسخهٔ اولیه: `2.2.0`، کامیت `a66e61a2d45721aff46d1d08a804012e3c907084`؛ هنگام شروع با HEAD شاخهٔ `main` گیت‌هاب یکسان بود.
- شاخهٔ این جلسه: `arena/01a0cf53-cryptoaitrader`؛ هیچ commit/push انجام نشده است.
- ۴۸۲ فایل ثبت‌شده در مبنا؛ ۳۴۷ فایل پایتون با ۱۰۶٬۲۸۹ خط، ۸۴ فایل `test_*.py`، ۶۰ فایل ترجمهٔ JSON، ۶ فونت TTF و یک ZIP انتشار قبلی.
- تمام فایل‌های مبنا فهرست و هش شدند؛ تمام فایل‌های پایتون به AST تبدیل شدند و تمام JSONها parse شدند. کلاس‌ها، توابع/متدها، importها و اتصال‌های صریح Qt نمایه شدند.
- مسیرهای اصلی اجرا، بازار، سیگنال، عامل، پیش‌بینی، معامله، ذخیره‌سازی و بسته‌بندی به‌صورت هدفمند از روی کد بررسی شدند. **این بررسی معادل ممیزی خط‌به‌خط همهٔ بدنه‌های ۱۰۶ هزار خطی، پوشش صددرصدی تست یا تست عملی ویندوز نیست.** قبل از تغییر هر بخش، بدنهٔ همان بخش و مصرف‌کننده‌هایش دوباره خوانده شوند.
- مرحلهٔ 2.2.1 صرفاً بررسی بود؛ سپس با درخواست کاربر سه یافتهٔ R1/R2/R3 در 2.2.2 اصلاح شدند. بررسی اولیه و شمار فایل‌های مبنا در این سند تاریخی‌اند؛ وضعیت جاری در سرآغاز و گزارش نسخه است.

## ۲. محصول چیست؟

برنامهٔ دسکتاپ تحلیل رمزارز با Python 3.11+، رابط PySide6 و نمودار pyqtgraph؛ رابط فارسی/انگلیسی و RTL/LTR. وب‌اپ نیست و سرور وب جزو مسیر اصلی اجرا ندارد. SQLite/SQLAlchemy داده‌های محلی را نگه می‌دارد؛ REST/WebSocket دادهٔ بازار را می‌آورند؛ AI از Ollama یا API سازگار با OpenAI/OmniRoute قابل اتصال است.

قابلیت‌های موجود در سورس:

- بازار زنده، جست‌وجوی نماد، جزئیات ارز، چند فهرست پیگیری و نرخ تتر/تومان.
- ۲۴ اندیکاتور، ۵ استراتژی، سیگنال LONG/SHORT/WAIT، حدضرر/اهداف، ریسک و اعتبار زمانی.
- تحلیل اختیاری AI، عامل چندمرحله‌ای دارای ابزار، چت جریانی با تاریخچه و بازبینی نتایج سیگنال.
- پیش‌بینی چندافقی با چندک‌ها، رژیم بازار، مدل آماری و مدل‌های ML اختیاری، سناریو و آمار دقت ثبت‌شده.
- ترمینال معاملهٔ خودکار/کاغذی، قیمت تیک‌محور، پویش فرصت، موقعیت‌ها و مدیریت ریسک.
- کاربران/نشست‌های محلی، حساب‌های صرافی، خواندن موجودی، کیف پول، ایمیل SMTP و بازیابی رمز.
- گزارش CSV/XLSX/JSON/PDF/HTML؛ پشتیبان‌گیری SQLite؛ ابزار ساخت EXE و نصب‌کننده و بررسی به‌روزرسانی.
- زیرپروژهٔ جداگانهٔ اندروید با Kivy و موتور سبک؛ **هم‌ارز کامل دسکتاپ نیست**.

«وجود قابلیت در سورس» با «تأیید کارکرد در اتصال زنده یا روی ویندوز کاربر» یکی نیست. این مرحله هیچ سفارش واقعی، کلید خصوصی، سرویس AI پولی یا اتصال حساب واقعی را آزمایش نکرد.

## ۳. نمای سیم‌کشی

```text
main.py
 ├─ --check / --signal → asyncio.run → Application
 └─ GUI → QApplication + Application + Translator + ThemeManager
           → FirstRunWizard → MainWindow (۱۱ صفحه)
           → MainController → AsyncRunner (asyncio روی نخ جدا)

Application (app/application.py)
 ├─ AppPaths → DatabaseManager → ۲۲ جدول SQLite
 ├─ SettingsRepository → SettingsService → ۱۶۴ مقدار پیش‌فرض
 ├─ SecretStore / DatabaseBackend → Auth / ExchangeAccounts / Email
 ├─ ExchangeRegistry → ExchangeProvider → MarketDataEngine
 ├─ IndicatorRegistry → IndicatorEngine
 ├─ StrategyRegistry + RiskEngine + MarketDataEngine → SignalEngine
 ├─ AIProviderManager + MarketToolset [+ OmniRouteToolset]
 │    → AIAnalyst / AutonomousAgent / ChatAgent / NarrativeWriter
 ├─ PredictiveIntelligenceEngine → PredictionStore → PredictionRepository
 └─ ReportBuilder / ReportExporter / BackupManager

MainController علاوه بر Application اجزای اجرایی دیگری می‌سازد:
 ├─ LivePriceFeed + ConnectionSupervisor + QTimerها
 ├─ TickEngine ← ticker listener + orderbook refresh
 ├─ ScalpService / ConfidenceCandidateSource / AI candidate scan
 └─ AutoTrader → LiveOrderGateway (executor=None) + PaperTradeRepository
```

**مرز مهم:** برخلاف عبارت «تنها نقطهٔ ساخت همهٔ اجزا» در بعضی docstringها، `Application` همهٔ اشیا را نمی‌سازد. خوراک زنده، کش تیک، موتور معامله و چند سرویس دیگر در کنترلر ساخته می‌شوند. برای اصلاح اتصال یا چرخهٔ عمر باید هر دو محل بررسی شوند.

## ۴. بوت و چرخهٔ عمر

### `main.py`

- `main()` آرگومان‌ها را می‌خواند و لاگ را تنظیم می‌کند.
- `run_gui()` ابتدا QApplication، سپس Application و ظاهر/زبان را می‌سازد؛ ویزارد اولین اجرا پیش از کنترلر است. پنجره نمایش داده می‌شود و `controller.start()` آغاز می‌شود؛ `aboutToQuit` به `shutdown()` متصل است.
- `run_check()` **آفلاین نیست**: موتور را شروع می‌کند و نمادها و قیمت BTC/USDT را از بازار می‌خواهد. در بررسی اولیه برای جلوگیری از ادعای تست زنده اجرا نشد.
- `run_signal()` بعد از `start()` از `Application.generate_signal()` استفاده می‌کند و در finally موتور را متوقف می‌کند.

### `Application`

- سازنده: مسیرها، `create_all()` و تطبیق افزودنی ستون‌ها، repositoryها، پیش‌فرض تنظیمات، انبار رازها، سرویس‌های حساب/ایمیل/نشست، رجیستری‌ها و موتورها.
- `start()`: صرافی از تنظیم `exchange.active` → provider → `MarketDataEngine.start()` → ساخت `SignalEngine` با منبع نتایج واقعی برای کالیبراسیون.
- `switch_exchange()`: موتور جدید را می‌سازد، موتور پیش‌بینی را invalidate می‌کند، SignalEngine را عوض می‌کند، `_ai_analyst` را خالی و موتور قدیمی را متوقف می‌کند. این متد به‌تنهایی همهٔ cache/listenerهای کنترلر و agentها را تعویض نمی‌کند؛ یافتهٔ باز R6 را ببین.
- `stop()`: توقف موتور بازار و manager هوش مصنوعی؛ خاموشی UI/runner در کنترلر انجام می‌شود.

### نخ‌ها و رویدادها

- `AsyncRunner.submit(name, coroutine, ...)` کار شبکه را روی asyncio جدا اجرا می‌کند. `TaskHandle` نتیجه/خطا/پایان را با سیگنال Qt برمی‌گرداند؛ coalesce بر اساس نام مانع انباشت درخواست هم‌نام می‌شود.
- `EventBus.publish()` همگام است؛ listener در نخ منتشرکننده اجرا می‌شود، نه لزوماً نخ GUI.
- `MainController._connect()` نقشهٔ اصلی دکمه/سیگنال → handler است؛ نمایهٔ اتصال‌ها در CODE_MAP موجود است.
- `MainController` حدود ۷۴۱۰ خط دارد؛ بازآرایی وسیع آن نباید با رفع اشکال محدود مخلوط شود.

## ۵. دادهٔ بازار

مسیر: `ExchangeRegistry.create()` → provider صرافی → REST client/parser → مدل‌های `Candle/Ticker/OrderBook/SymbolInfo` → `MarketDataEngine`.

| صرافی ثبت‌شده | مسیر | وضعیت پیاده‌سازی داده |
|---|---|---|
| LBank | `market/providers/lbank/` | REST، WebSocket، API خصوصی خواندن حساب؛ endpointهای spot/contract را تفکیک کن |
| Toobit | `market/providers/toobit/` | REST و WebSocket اختصاصی، امضای درخواست خصوصی |
| Bitpin | `market/providers/bitpin/` | REST، توکن دسترسی/refresh؛ WebSocket ندارد؛ کندل از معاملات اخیر ساخته می‌شود و تاریخچهٔ بلند تضمین نشده است |

نام‌های بیشتری در `market/exchange_catalog.py` هستند، ولی ثبت provider واقعی فقط همین سه مورد است. فهرست نمایشی را با پشتیبانی اجرایی یکی نگیر.

`MarketDataEngine` کش، تجمیع تایم‌فریم‌های غیر بومی، اشتراک سوکت، ادغام کندل زنده، ذخیرهٔ کندل و fallback به دادهٔ ذخیره‌شده را مدیریت می‌کند. `LivePriceFeed` از ticker listener و polling استفاده می‌کند؛ `ConnectionSupervisor` وظیفهٔ مراقبت از خوراک/اتصال را دارد. نرخ درخواست و retry در `market/rate_limiter.py` است.

`market/timeframes.py` **۱۴ کد** دارد، از `1m` تا `1w` به‌علاوهٔ `1M`. `1M` ماهانه است و نباید با `lower()` به دقیقه تبدیل شود. دسترسی هر صرافی متفاوت است؛ ۱۳ افق پیش‌بینی مفهوم جداگانه‌ای است.

`market/quality.py` و `signals/prediction/features.py` پاک‌سازی، کیفیت و زمان بسته‌شدن فیچرها را کنترل می‌کنند؛ در توسعه نباید شکاف داده با کندل ساختگی پر شود.

## ۶. اندیکاتور، استراتژی، سیگنال و ریسک

- قرارداد اندیکاتور: `BaseIndicator` و Registry؛ `IndicatorEngine` خروجی را به قالب مشترک می‌برد.
- گروه‌ها: trend، momentum، volatility، volume و support_resistance.
- ۲۴ نام ثبت‌شده: ADX، ATR، BBANDS، CCI، CMF، DONCHIAN، EMA، FIBONACCI، HMA، ICHIMOKU، KELTNER، MACD، MFI، OBV، PIVOT، PSAR، ROC، RSI، SMA، STOCH، VOLUME_SMA، VWAP، WILLIAMS_R، WMA.
- ۵ استراتژی: `TrendFollowingStrategy`، `MeanReversionStrategy`، `BreakoutStrategy`، `MomentumStrategy` و `VolatilityRegimeStrategy`.

مسیر `SignalEngine.generate()`:

1. تحلیل موازی تایم‌فریم‌ها با `asyncio.gather`؛ کمبود داده → WAIT/INSUFFICIENT_DATA.
2. اندیکاتورها و ساختار بازار → `StrategyContext` → رأی هر استراتژی.
3. جمع وزن‌دار رأی‌ها و تایم‌فریم‌ها؛ آستانهٔ تصمیم `0.22`؛ هم‌سویی کم → WAIT.
4. قیمت ورود از کندل تایم‌فریم اصلی؛ SL و TP از `RiskEngine` با ATR/ساختار؛ ریسک نامناسب حق وتو دارد.
5. خروجی `TradingSignal` شامل جهت/سطوح/ریسک/دلیل/زمان؛ پنجرهٔ ورود و انقضا در `signals/validity.py`؛ پیش‌بینی کوتاه در `signals/forecast.py`.
6. لایهٔ Application/Controller ذخیره در SignalRepository و پیگیری outcome را انجام می‌دهد.

**سه مسیر تصمیم را مخلوط نکن:**

- موتور `SignalEngine` مستقل از LLM است.
- `Application.generate_signal()` تنظیم `ai.signal_mode` را می‌خواند: engine، hybrid (روایت)، ai_only (`AIAnalyst.generate_signal` + `_apply_ai_decision`). در ai_only جهت و entry/SL/TP نیز قابل جایگزینی است، نه فقط متن.
- دکمهٔ GUI با تیک AI مسیر دیگری دارد: `MainController._generate_ai_signal()` ابتدا baseline از Application می‌گیرد، سپس `AutonomousAgent.run()`؛ اعتبارسنجی/ذخیره و fallback در کنترلر است. خاموش بودن تیک GUI لزوماً تنظیم سراسری `ai.signal_mode` را خاموش نمی‌کند. برای هر اصلاح سیگنال، UI و CLI هر دو آزموده شوند.

`MarketScanner` برای پویش گروهی موتور ریاضی را اجرا می‌کند؛ `AutoScanner` زمان‌بندی را انجام می‌دهد. این‌ها با اسکنر ترمینال معامله و `signals/forecast.py` با موتور `signals/prediction/` یکی نیستند.

نتایج سیگنال در `SignalOutcomeRepository`/`outcome_tracker.py` و بازبینی در `SignalReviewer`/`SignalReviewRepository` ثبت می‌شوند. `scorecard.py` دفترچهٔ پیش‌بینی کوتاه است؛ آمار موتور جدید در PredictionRepository قرار دارد. confidence را نرخ برد یا تضمین سود معرفی نکن.

## ۷. هوش مصنوعی

- قرارداد provider: `ai/providers/base.py`؛ manager ترتیب/ترجیح/fallback و stream را مدیریت می‌کند.
- پیاده‌سازی‌ها: Ollama، OpenAI-compatible و OmniRoute؛ presetهای سرویس‌ها از این قراردادها استفاده می‌کنند.
- `MarketToolset` دسترسی محدود به قیمت، کندل، اندیکاتور، روند، دفتر سفارش، ریسک، سیگنال و گزارش/دقت پیش‌بینی دارد. `CompositeToolset` چند مجموعه را ترکیب می‌کند.
- `AIAnalyst`: جمع‌آوری داده، بودجه‌بندی prompt، قالب نسخه‌دار، JSON و تلاش محدود ترمیم.
- `AutonomousAgent`: حلقهٔ چندمرحله‌ای ابزار/مشاهده/تصمیم، timeout و validator.
- `ChatAgent`: تاریخچهٔ مکالمه، tool calls، پیشنهاد action و streaming؛ رکورد مکالمات جدا در DB ذخیره می‌شود.
- `ResponseValidator`: نوع/جهت/اهرم/ترتیب سطوح/ریسک پاسخ را بررسی می‌کند. قالب JSON و نام فیلدهای `structured`، `signal` و `entry_zone` را با نام‌های مدل دامنه یکی فرض نکن.
- `NarrativeWriter` در نبود مدل متن قالبی تولید می‌کند؛ `SignalReviewer` نتایج بسته‌شده را بازبینی می‌کند.
- `prompt_budget.py`، `local_model_fit.py`، `speed_profile.py` و `ollama_doctor.py` محدودیت حافظه/توکن/سرعت و عیب‌یابی را پوشش می‌دهند.
- `MarketToolset.tool_names` یک property است، اما در CompositeToolset متد است؛ استفادهٔ یکسان بدون بررسی خطاساز است.

## ۸. موتور پیش‌بینی

`Application.prediction_engine` تنبل ساخته می‌شود و `market.get_candles` و `PredictionStore` را تزریق می‌کند. صفحهٔ Prediction، ابزار AI و ترمینال معامله از همین موتور استفاده می‌کنند.

`PredictiveIntelligenceEngine.assess()`:

```text
کندل → کیفیت → FeatureStore → تشخیص رژیم/مرحله
 → plan_horizons → توزیع تجربی یا ATR fallback
 → آنسامبل آماری / GBM / LSTM اختیاری
 → fusion توزیع+مدل+رژیم+مومنتوم → عدم‌قطعیت/رویداد
 → سناریو/نوسان/شکست/آنومالی/هشدار
 → توضیح/تایم‌لاین/چه عوض شد → PredictionStore → SQLite
```

- افق‌ها: 1m، 3m، 5m، 15m، 30m، 1h، 2h، 4h، 6h، 12h، 24h، 3d، 7d.
- خروجی‌ها: P10/P25/P50/P75/P90، جهت/احتمال/اطمینان مؤثر، رژیم‌ها، سناریو، کیفیت، دقت و سلامت مدل. افق بدون داده با دلیل غیرفعال می‌شود.
- مدل آماری همیشه موجود؛ torch/xgboost/lightgbm در گروه اختیاری `ml`. نصب requirements به‌تنهایی آن‌ها را نصب نمی‌کند.
- crossasset فقط با ورودی peers فعال است؛ وجود ماژول به‌معنی تغذیهٔ خودکار همهٔ داده‌های لازم از UI نیست. رویدادهای کلان از تنظیمات دستی خوانده می‌شوند؛ فرم کامل رویدادها جزو کار باز بوده است.
- کش گزارش بر اساس `(symbol, timeframes)` و TTL؛ کش آنسامبل فعلاً بر اساس `(symbol, timeframe)` است، نه horizon/steps. هنگام اصلاح پیش‌بینی به استقلال افق‌ها توجه شود.
- `PredictionStore.resolve_due()` افق سررسیدشده را با price_lookup می‌سنجد. اتصال فعلی Application از کندل‌های 1h و صرافی فعلی می‌خواند؛ دقت timestamp بسته‌شدن، افق دقیقه‌ای و تفکیک صرافی نیازمند بررسی است (R7).
- **R1 در 2.2.2 رفع شد:** نتیجهٔ assess با timestamp مشترک در cache گزارش و latest ثبت می‌شود؛ وابستگی به cached قبلی حذف شد. تست تایم‌فریم متفاوت، force و TTL موجود است.

## ۹. ترمینال معامله و محافظ‌ها

اجزای اصلی:

- `trading/scalp_scanner.py`: امتیاز نوسان/مومنتوم/نقدینگی/اسپرد.
- `ScalpService`: اتصال بازار و بازبینی AI و ساخت `AutoTradeConfig`.
- `ConfidenceCandidateSource`: نامزد بر پایهٔ اطمینان سیگنال.
- `_ai_candidate_scan()` در کنترلر: پیش‌بینی → `TrendLadder` → `ai_decider.decide()` → `AICandidate`. نام AI Auto الزاماً به‌معنی فراخوانی LLM نیست؛ تصمیم‌ساز این مسیر کمی است.
- `TickEngine`/`TickQuote`: Last/Bid/Ask، زمان صرافی/دریافت/پردازش، freshness و listener.
- `AutoTrader`: candidate_source، price_source، repository، gateway و portfolio/invalidation_source را می‌گیرد. ورود/خروج و محدودیت‌ها از این لایه می‌گذرند؛ UI صرفاً نمایش نیست ولی نباید دروازه‌ها را دور بزند.
- `ManagedTrade`: محاسبه سود، TP/SL، break-even، trailing و زمان نگهداری.
- `micro_plan.py`: notional = margin × leverage؛ هدف خالص و دو طرف کارمزد. quantity از notional/entry می‌آید؛ PnL را دوباره در leverage ضرب نکن.
- خروج با listener تیک و fallback polling؛ ورودی کهنه و سقف زیان/مارجین/همزمانی کنترل می‌شوند. سقف سخت اهرم ۲۰۰ است، نه توصیهٔ معاملاتی.
- `LiveOrderGateway` با executor پیش‌فرض None صریحاً خطا می‌دهد؛ `is_live` به mode و عبارت تأیید دقیق وابسته است. به هیچ وجه به‌عنوان اجرای واقعی آمادهٔ استفاده معرفی نشود.

**R2 در 2.2.2 رفع شد:** `ScalpService.build_trader_config()` هر ۲۸ فیلد را منتقل می‌کند، از جمله trailing، max_spread_percent و سقف مجموع مارجین. صفر کارمزد/لغزش و False حفظ می‌شوند. attach/apply_config سن مجاز TickEngine متصل را هم همگام می‌کنند. سقف‌های سخت قبلی و محافظ live حذف نشده‌اند.

`_run_watch_scan` مستقل از روشن بودن موتور جدول را تغذیه می‌کند؛ ولی مسیر فعلی `_ai_candidate_scan` فهرست selected/watchlist را تا scan_limit می‌خواند، نه بی‌قید تمام نمادهای صرافی. «actionable» جدول watch فقط شرط نمایشی اطمینان/اسپرد است؛ مجوز قطعی معامله نیست.

دو دفتر کاغذی وجود دارد: `signals.paper_trader.PaperTrader` در JSON تنظیمات و `PaperTradeRepository` در جدول `paper_trades`. `_on_trade_requested()` این دو مسیر را به هم وصل می‌کند تا معامله در تاریخچه دیده شود. تغییر یکی بدون دیگری خطر ناهماهنگی دارد.

## ۱۰. UI، زبان و ظاهر

۱۱ صفحهٔ ثبت‌شده در `MainWindow.PAGES`:

| صفحه | کلاس | اتصال اصلی در کنترلر |
|---|---|---|
| داشبورد | DashboardPage | refresh_dashboard / قیمت زنده / جزئیات سیگنال |
| بازارها | MarketsPage | refresh_markets / watchlist / coin detail |
| تحلیل | AnalysisPage | run_analysis / نمودار زنده / عامل |
| سیگنال‌ها | SignalsPage | generate_signal / scan_market / auto scan |
| پیش‌بینی | PredictionPage | run_prediction_report |
| چت | ChatPage | send_chat_message / ابزارها / مکالمات |
| معامله | TradesPage | AutoTrader / terminal / record/close |
| کیف پول | WalletPage | sync_wallet / refresh_wallet |
| گزارش‌ها | ReportsPage | generate_report / outcomes / scorecard |
| تنظیمات | SettingsPage | save_settings / accounts / themes / backup |
| راهنما | HelpPage | آموزش و مستندات |

- `ui/charts/` نمودار مشترک تحلیل و ترمینال؛ موتور دومِ اندیکاتور یا پیش‌بینی برای UI نساز.
- ترمینال: ۹ کارت، فرصت‌های ۱۷ستونه، موقعیت‌های ۱۹ستونه، پنل ریسک، مودال تنظیم اسکن و انتخاب نماد.
- جدول مرتب‌شونده باید شناسه/نگاشت واقعی ردیف را از UserRole بخواند؛ شمارهٔ ظاهری سطر هویت داده نیست.
- `Translator` از JSONهای fa/en می‌خواند؛ هر رشتهٔ جدید باید هر دو زبان را داشته باشد. نماد/عدد در RTL باید خوانا بماند.
- ظاهر از ThemeTokens/ThemeManager؛ نام‌های قدیمی پوسته برای تنظیم‌های قبلی حفظ شوند. فونت‌ها روی اندازه‌گیری UI و آزمون ابعاد اثر دارند.
- ارتفاع کمینهٔ پنجره ۶۶۰ است. برای کنترل جدید صفحهٔ معامله را بی‌دلیل بلند/اسکرول سراسری نکن؛ الگوی پنل جمع‌شونده/مودال را حفظ کن.

## ۱۱. داده، تنظیمات و امنیت

- `app/core/models.py` مدل دامنه است؛ `app/database/models.py` ORM است. `TradingSignal` اسلات دارد؛ ویژگی دلخواه مثل source/id را روی آن ننویس.
- ۲۲ جدول: settings، exchange_providers، ai_providers، symbols، watchlists، candles، market_data، indicators، signals، signal_outcomes، signal_analysis، signal_reviews، chat_conversations، chat_messages، reports، backup_history، application_logs، users، user_sessions، exchange_accounts، paper_trades، predictions.
- Repositoryها نشست/تراکنش را از DatabaseManager می‌گیرند؛ WAL و timeout برای SQLite برقرار است.
- راه‌اندازی `create_all()` به‌علاوهٔ `_add_missing_columns()` دارد؛ مسیر رسمی Alembic نیز وجود دارد و پیش از migration پشتیبان می‌گیرد. این‌ها دو مسیر متفاوت‌اند؛ افزودن ستون/قید فقط با تغییر مدل کافی نیست.
- SettingsService کش و تبدیل نوع دارد. `ensure_defaults` فقط کلید غایب را می‌نویسد، اما استثنای `_repair_stale_defaults()` مقدار ۴۵ را به ۱۲۰ تغییر می‌دهد و به user_modified نگاه نمی‌کند. ادعای مطلق «هیچ مقدار ذخیره‌شده‌ای تغییر نمی‌کند» دقیق نیست.
- **مسیر واقعی پیش‌فرض داده:** `<project-or-executable-dir>/data` در `get_data_dir()`؛ `CAT_DATA_DIR` اولویت دارد. مسیر LOCALAPPDATA مندرج در README با کد مبنا یکی نیست.
- AuthService محلی است؛ PBKDF2-HMAC-SHA256 و salt تصادفی برای رمز و نشست‌های قابل ابطال وجود دارد. این برنامه سرویس احراز هویت وب نیست.
- `SecretStore` دارای keyring/file backend است؛ Application با پیش‌فرض `security.store_secrets_in_db=True` آن را به **DatabaseBackend رمزنگاری‌شده** تغییر می‌دهد. کلید رمزنگاری از مشخصات محیط مشتق می‌شود، نه از یک کلید تصادفیِ محفوظ سیستم‌عامل؛ این طراحی نباید هم‌سطح DPAPI معرفی شود.
- **R3 در 2.2.2 رفع شد (برچسب، نه حذف کلید):** snapshot همچنان ciphertext را برای restore نگه می‌دارد و manifest وجود آن را true اعلام می‌کند. settings.json قدیمیِ بررسی‌نشده نیز حساس فرض می‌شود. backup شخصی را عمومی منتشر نکن؛ طراحی مشتق‌سازی کلید R4 هنوز باز است.

## ۱۲. گزارش، پشتیبان، نصب و موبایل

- ReportBuilder دادهٔ سیگنال‌ها را جمع می‌کند؛ ReportExporter خروجی می‌نویسد؛ persian_pdf حروف فارسی/RTL و فونت را آماده می‌کند.
- BackupManager از `sqlite3.backup` و manifest/hash استفاده می‌کند؛ restore حفاظ‌های صحت DB و WAL دارد. ZIP سورس این تحویل با backup دادهٔ کاربر متفاوت است.
- PyInstaller: `CryptoAITrader.spec`؛ اسکریپت ویندوز requirements و تست را اجرا می‌کند، بعد EXE می‌سازد. Inno Setup و `tools/build_installer.py` نصب‌کننده/latest.json را می‌سازند.
- `UpdateChecker` manifest محلی/اینترنتی را می‌خواند؛ checksumِ غایب فعلاً پذیرفته می‌شود. این مرحله updater را اجرا نکرد و نصب‌کننده‌ای تولید نکرد.
- `pyproject.toml` packages را دستی فهرست کرده و `main:main` entry point دارد. پوشش subpackageها، trading و main در wheel نیاز به آزمون نصب تمیز دارد؛ اجرای سورس اثبات صحت wheel نیست.
- `mobile/`: Kivy + stdlib network + indicators_lite + signal_lite؛ نسخهٔ مستقل `1.9.12`. سازندهٔ APK/دارایی‌های ارجاع‌شده باید جدا بررسی شود؛ موتور موبایل عین pipeline پنج‌استراتژی دسکتاپ نیست. این مرحله نسخه یا کد موبایل را تغییر نداده است.

## ۱۳. نقشهٔ تغییر امن برای مراحل بعد

| درخواست | محل‌های اصلی | آزمون‌های مرتبط |
|---|---|---|
| صرافی/تایم‌فریم | provider + parser + registry + engine + timeframe | timeframes، toobit_bitpin، exchange_switching، market_resilience |
| اندیکاتور/استراتژی | indicators/registry، signals/strategies، engine | indicators، signal_engine، risk_engine |
| سیگنال AI | Application + controller + analyst/agent/validator | ai_validator، autonomous_agent، v1911_ai_signal_mode، v1916_ai_wait |
| پیش‌بینی | prediction/engine/features/models/store + repository | predictive_phase1، predictive_phase2_5، prediction_lifecycle، prediction_ui_and_tools |
| معامله و محافظ | config builder + AutoTrader + TickEngine + controller/UI | v1914_scalp، v1922_micro_speed، v200_event_driven_trading، v22_terminal_pro |
| داده/امنیت | models + repositories + migration + backup + secrets | backup، auth، v154_security_money، trades_and_wallet |
| UI | page/dialog/chart + handler + ترجمه/پوسته | ui_wiring، themes، localization، v22_terminal_pro |
| نصب/نسخه | constants + pyproject + build files + docs | v154_packaging، v1911_build_and_update، v1912_mobile |

روال هر مرحله: تعیین محدوده → خواندن مسیر و مصرف‌کننده‌ها → تست بازتولید → تغییر محدود → آزمون مرتبط/کاملِ ممکن → افزایش نسخه و ثبت نتیجه → ساخت ZIP با فایل‌های جدید → تحویل برای تست کاربر → **انتظار برای دستور صریح commit/push**.

## ۱۴. وضعیت فعلی و پیشنهاد مرحلهٔ بعد

- ZIP دست‌نخوردهٔ اولیه تحویل شده است؛ SHA256 آن در گزارش بررسی آمده است.
- آزمون هستهٔ مبنا: **۶۷۴ قبول، ۲ skip، صفر شکست** در ۳۳ فایل منتخب؛ مجموعهٔ کامل به علت نبود کتابخانه‌های سیستمی Qt جمع‌آوری نشد. عدد تاریخی ۲۲۶۹ پاس README، نتیجهٔ این محیط نیست.
- سه ایراد R1/R2/R3 در 2.2.2 اصلاح شدند؛ اجرای ترکیبی هسته/درگاه ۷۰۸ پاس و ۳ skip داشت. سایر موارد R4 تا R10 نیازمند بررسی هدفمندند. UI/ویندوز هنوز باید توسط کاربر/محیط مناسب آزمایش شود.
- اولویت بعدی: تست ZIP 2.2.2 توسط کاربر و بررسی R4 تا R10 مطابق انتخاب او؛ اصلاح سه ایراد به معنی مجوز commit/push یا تأیید معاملهٔ واقعی نیست.
