# موتور هوش پیش‌بینی CryptoAITrader — سند معماری و نقشهٔ راه

> این سند حاکمِ پروژهٔ «CryptoAITrader Predictive Intelligence Engine» است.
> فاز صفر (بررسی کامل موجودی) در تاریخ ۲۰۲۶-۰۹-۲۲ انجام شد.
> قاعدهٔ طلایی: **هر قابلیت موجود ارتقا داده می‌شود، نسخهٔ دومش ساخته نمی‌شود.**

---

## ۰. اصول حاکم (ترجمهٔ فنی قوانین حیاتی)

| قانون | اجرای فنی در این پروژه |
|---|---|
| ۱. پیش‌بینی قطعی ممنوع | همهٔ خروجی‌ها احتمالی/بازه‌ای‌اند؛ سقف احتمال ۸۰٪ در `forecast.py` باقی می‌ماند |
| ۲. جعل داده ممنوع | هر ماژول بدون دادهٔ کافی خروجی `disabled/insufficient_data` می‌دهد، هرگز عدد نمی‌سازد (الگوی موجود در `AIAnalyst`) |
| ۳. Look-ahead bias ممنوع | Feature Store فقط از کندل‌های **بسته‌شده** می‌سازد؛ walk-forward جداکنندهٔ آموزش/آزمون را تضمین می‌کند |
| ۴. Data leakage ممنوع | تقسیم زمانی (نه تصادفی) در همهٔ ارزیابی‌ها؛ فیچرها timestamp دقیق دارند |
| ۵. ذخیرهٔ پیش‌بینی و مقایسه با واقعیت | جدول `PredictionRecord` + سرویس امتیازدهی |
| ۶. دقت به تفکیک Asset/TF/Regime/Model | کلید امتیازدهی ۴بخشی |
| ۷. Uncertain صریح | لایهٔ Uncertainty با آستانهٔ اطمینان؛ خروجی «نمی‌دانم» مجاز و تشویق می‌شود |
| ۸. اعتبارسنجی با دادهٔ واقعی | هیچ مدلی بدون walk-forward وارد production نمی‌شود |
| ۹. LLM قیمت اختراع نمی‌کند | LLM فقط Reasoning/Explanation/Orchestration؛ عدد از Quant/ML می‌آید |
| ۱۰. ادغام در معماری موجود | همهٔ ماژول‌های جدید زیرپکیج‌های همین ساختارند؛ هیچ پروژهٔ موازی ساخته نمی‌شود |

---

## ۱. موجودی Phase 0 — چه چیزی هست و چه چیزی نیست

### ۱.۱. آنچه از قبل وجود دارد (و باید ارتقا یابد نه دوباره‌سازی)

| موضوع | فایل فعلی | وضعیت | کار لازم |
|---|---|---|---|
| پیش‌بینی چندافقه | `signals/forecast.py` (۳۳۵ خط) | بازهٔ ATR برای ۳ افق به‌ازای هر تایم‌فریم پایه، احتمال سقف ۸۰٪ | ارتقا به نردبان کامل ۱۳ افق + چندک‌ها |
| امتیازدهی پیش‌بینی | `signals/scorecard.py` + `app/application.py::score_forecasts` | نرخ اصابت بازه در برابر هدف ۸۰٪ | تفکیک Asset/TF/Regime/Model |
| ردگیری خروجی | `signals/outcome_tracker.py` (۳۹۷ خط) + `SignalOutcomeRecord` | پنجرهٔ قیمت، توقف، اهداف، `confidence_buckets` | افزودن سطح «پیش‌بینی» جدا از «سیگنال» |
| تحلیل چندتایم‌فریمی | `signals/engine.py` — پیش‌فرض `[1d, 4h, 1h, 15m]` | تحلیل مستقل هر تایم‌فریم + ساختار بازار | موتور Fusion جدید روی همین خروجی |
| ساختار بازار | `MarketStructureType` (۵ حالت) + `analyze_market_structure` | HH/HL/LH/LL → BULLISH/BEARISH/RANGING/BREAKOUT/BREAKDOWN | ورودی رژیم‌موتور |
| استراتژی رژیم نوسان | `signals/strategies/volatility_regime.py` | ATR نسبت به میانگین (فشرده/منتشر) | ورودی رژیم‌موتور |
| اعتبار/پنجرهٔ ورود | `signals/validity.py` (۴۴۶ خط) | Freshness، سوختن سیگنال، کسر مصرف‌شده | الگوی confidence decay |
| تفکیک اطمینان | `signals/confidence.py` — `ConfidenceBreakdown` با ضرایب | عوامل موجه/منفی درصدی | پایهٔ Explainability |
| هشدارها | `signals/alerts.py` | زیرساخت هشدار | اتصال به Early Warning |
| اسکنر بازار | `signals/scanner.py` + `auto_scanner.py` (۳۷۲ خط) | اسکن نمادها | افزودن دلیل به‌ازای هر مورد + آنومالی |
| عامل تحلیل AI | `ai/agent/analyst.py` + `autonomous_agent.py` + `chat_agent.py` | چرخهٔ ابزار→پرامپت→اعتبارسنجی؛ «مدل هرگز داده نمی‌سازد» | اتصال ابزارهای جدید به عامل |
| ابزارهای LLM | `ai/tools/market_tools.py` — شامل `forecast_next_timeframe` | tool-call از چت | افزودن ابزارهای موتور پیش‌بینی |
| کندل‌ها در DB | `CandleRecord` + `CandleRepository` (prune=1000) + `MarketDataSnapshot` | ذخیرهٔ خام | پایهٔ Feature Store |
| تایم‌فریم‌ها | `market/timeframes.py` — ۱m تا 1M **با تجمیع تایم‌فریم‌های غایب** (LBank 3m/2h/6h/8h/12h نمی‌دهد) | کامل | افق‌های 3d/7d از تجمیع 1d |
| فید زنده | `market/live_feed.py` — poll با backoff نمایی سقف ۶۰ث + WS + `is_fresh` | پایهٔ خوب | Phase آنلاین: watchdog/خودترمیمی |
| وضعیت اتصال | `MarketDataEngine.connection_status/is_online/websocket_status` | نمایش وضعیت | لایهٔ تابلو/بازاتصال خودکار |
| اردربوک | `parse_orderbook` در providerها + WS depth | دادهٔ خام | ورودی Order Flow/Liquidity Map |
| صرافی‌ها | `market/providers/` — lbank، toobit، bitpin | REST + WS | ورودی Exchange Consensus |

### ۱.۲. آنچه وجود ندارد (ساخته می‌شود)

توزیع احتمال چندک (P10–P90) · موتور سناریو · موتور رژیم ۱۴حالته به‌ازای هر تایم‌فریم · تشخیص گذار رژیم · ماشین حالت بازار · احتمال شکست/شکست کاذب سطح · پیش‌بینی نوسان آینده · نقشهٔ نقدینگی · پیش‌بینی لیکوییداسیون · هوش Order Flow (CVD) · کراس-asset · Lead-lag · آنومالی ML · فیوژن وزن‌دار تطبیقی · آنسامبل مدل · Online learning منضبط · Timeline پیش‌بینی و What-Changed · Explainability کامل · تقویم رویداد و پیش‌بینی رویدادآگاه · Uncertainty صریح · Conflict detector · اسکنر فرصت با دلیل · Walk-forward backtest · Feature Store · موتور کیفیت داده · اجماع صرافی‌ها · داشبورد پیش‌بینی/درخت سناریو/سلامت مدل · موتور امتیاز نهایی · لایهٔ «همیشه آنلاین».

### ۱.۳. محدودیت‌های دادهٔ واقعی (صادقانه)

- **OI / Funding / Liquidation**: providerهای فعلی (LBank/Toobit/Bitpin) اسپات‌اند. تا وقتی endpoint مشتقات اضافه نشود، این فیچرها «در صورت وجود داده» فعال و در غیر این صورت صریحاً `disabled` می‌شوند — **عدد ساختنی نیست**.
- **BTC.D / TOTAL**: از فهرست نمادهای خود صرافی قابل محاسبهٔ تقریبی است؛ DXY/Gold/Nasdaq منبع خارجی می‌خواهد (تصمیم کاربر).
- **جعبهٔ شنی توسعه**: فقط PyPI در دسترس است؛ هر کد شبکه‌ای با fake قابل‌آزمون نوشته می‌شود و روی ویندوزِ کاربر واقعی اجرا می‌شود.

---

## ۲. معماری هدف

```
market/providers  ──►  market/quality.py (جدید: کیفیت داده #44)
        │                        │
        ▼                        ▼
   CandleRepository  ──►  signals/prediction/features.py (جدید: Feature Store #43)
                                 │  (فیچر timestampدار، فقط کندل بسته‌شده)
        ┌────────────────────────┼───────────────────────────┐
        ▼                        ▼                           ▼
  regime.py (#5,6,7)      distribution.py (#1,2)      models/ (#20,21,27)
  رژیم/گذار/حالتماشین     نردبان افق + چندک            آنسامبل + انتخاب مدل
        │                        │                           │
        └──────────► fusion.py (#4,19,36) ◄──────────────────┘
   وزن‌دار·تطبیقی·تشخیص تعارض
        │
        ▼
  scenarios.py (#3) + volatility.py (#11,12) + breakout.py (#9,10)
        │
        ▼
  engine.py — موتور امتیاز نهایی (#50) + uncertainty.py (#33,34) + warning.py (#8)
        │
        ├──► store.py → PredictionRecord در DB (#23) → scoring.py (#24,25,26)
        ├──► timeline.py (#28,29)  ├──► explain.py (#30)
        ▼
  UI: ui/pages/prediction_page.py (#46,47,48) — ریسپانسیو، RTL، localization
        ▼
  ai/agent + ai/tools — LLM فقط توضیح/پژوهش/ارکستراسیون (#37,38,49)
```

### ماژول‌های جدید (همه با docstring فارسی «چرا» + آزمون بدون PySide6 مگر UI)

```
signals/prediction/   horizons, features, quality(نمایش), regime, transitions,
                      distribution, scenarios, fusion, volatility, breakout,
                      liquidity, anomaly, warning, uncertainty, timeline,
                      explain, engine, store, scoring
signals/prediction/models/  registry, ensemble, walkforward, drift, selection
market/quality.py     موتور کیفیت داده (کندل‌های تکراری/پرشی/خارج از قانون)
market/resilience.py  نظارت‌چی اتصال، بازاتصال خودکار، خودترمیمی
ui/pages/prediction_page.py + ورودی‌های localization + کلیدهای settings جدید
```

### تغییر دیتابیس

جدول جدید `PredictionRecord` (از طریق migration موجود) — **هیچ کلید/جدول موجود تغییر یا حذف نمی‌شود**؛ تنظیمات جدید فقط کلید پیش‌فرض اضافه می‌کنند.

---

## ۳. فازبندی اجرا (۱۵ فاز + یک جریان موازی)

| فاز | عنوان | تحویل قابل‌آزمون | موارد خواسته |
|---|---|---|---|
| **آنلاین (موازی، زودتر)** | همیشه‌آنلاین | `market/resilience.py`: watchdog + بازاتصال نمایی + jitter + تشخیص دادهٔ کهنه + banner وضعیت در UI | خواستهٔ حیاتی کاربر |
| ۱ | کیفیت داده + Feature Store | `market/quality.py` + `features.py` با timestamp و فقط کندل بسته | #43, #44 |
| ۲ | موتور فیچر چندتایم‌فریمی | نردبان ۱۳ افق با فعال/غیرفعال شدن خودکار بر اساس کفایت داده | #1 (بخش افق‌ها) |
| ۳ | موتور رژیم | ۱۴ رژیم به‌ازای هر TF + گذار + ماشین حالت | #5, #6, #7 |
| ۴ | موتور پیش‌بینی | توزیع چندک P10–P90 + نوسان آینده | #1, #2, #11 |
| ۵ | آنسامبل | رجیستری مدل (آماری پایه همیشه‌در دسترس + GBM اختیاری) + انتخاب تطبیقی | #20, #21, #27 |
| ۶ | احتمال + سناریو | سناریوی گاو/خنثی/خرس از مدل + درخت سناریو (داده) | #3, #47 (داده) |
| ۷ | نوسان/نقدینگی/Order Flow | نقشهٔ نقدینگی از اردربوک + CVD + شکست کاذب | #10, #12, #13, #14(در صورت داده), #15 |
| ۸ | هشدار زودهنگام + آنومالی | تشخیص آنومالی + هشدار ریسک | #8, #18, #40 |
| ۹ | ردگیری + دقت + کالیبراسیون | `PredictionRecord` + امتیاز ۴بخشی + Brier/Reliability | #23, #24, #25 |
| ۱۰ | مدل تطبیقی + Drift | تشخیص drift + پیشنهاد بازآموزش منضبط | #22, #26 |
| ۱۱ | عامل پژوهش AI | فرمان «BTC را برای ۴ ساعت تحلیل کن» → گزارش ۱۰مرحله‌ای | #37, #38, #49 |
| ۱۲ | داشبورد | صفحهٔ پیش‌بینی + درخت سناریو + سلامت مدل + What-Changed + Timeline | #28, #29, #46, #47, #48 |
| ۱۳ | Walk-forward | اعتبارسنجی غلتان + جلوگیری از leakage | #41, #42 |
| ۱۴ | بهینه‌سازی | پروفایل عملکرد، کش، debounce بازمحاسبه | #35, کارایی |
| ۱۵ | سخت‌سازی Production | خطاها، لاگ، مستندات، نسخه‌بندی، zip نهایی | #45, پایداری |

**گزارش پایان هر فاز** (قالب خواستهٔ کاربر): Implemented · Modified Files · New Files · Database Changes · Dependencies · Tests · Performance · Known Issues · Next Phase — در همین سند ثبت می‌شود.

---

## ۴. گزارش‌های فازها

_(با پایان هر فاز اینجا اضافه می‌شود)_

### Phase 0 — بررسی کامل پروژه (۲۰۲۶-۰۹-۲۲)

- **Implemented**: بازبینی کامل ۱۸۰+ فایل؛ نگاشت ۵۰ خواسته به موجودی؛ تعیین «ارتقا/جدید» به‌ازای هر مورد؛ سند معماری بالا؛ تعریف بستهٔ `signals/prediction/`.
- **Modified Files**: فقط همین سند (فایل جدید).
- **New Files**: `docs/PREDICTIVE_ENGINE_FA.md`.
- **Database Changes**: ندارد.
- **Dependencies**: ندارد (تصمیم ML/ماکرو از کاربر باقی است).
- **Tests**: مجموعهٔ کامل پیش از شروع: **۲۰۵۰ قبول / ۰ مردود / ۰ خطا · ۷۷ فایل · ۲۵۷ ثانیه** (پس از بازسازی محیط: venv، استاب‌های گرافیکی ۴گانه با ۲۳۴ سمبل، اصلاح CRLF بازگردانی‌شده).
- **Performance**: بدون تغییر محصول.
- **Known Issues**: OI/Funding/Liquidation بدون endpoint مشتقات فعال نمی‌شوند؛ جعبهٔ شنی فقط PyPI دارد.
- **Next Phase**: ۱ — کیفیت داده + Feature Store (و جریان موازی همیشه‌آنلاین).
