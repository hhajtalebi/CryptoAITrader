# کار بعدی

## وضعیت جاری ۲.۵.۴ — بسته‌شدن خودکار EXE، معاملهٔ خودکاری که باز نمی‌شد، اسکالپ فوق‌سریع

گزارش کاربر: (۱) EXE پس از چند دقیقه/ساعت خودش بسته می‌شود؛ (۲) معاملهٔ خودکار هیچ معامله‌ای باز نمی‌کند؛
(۳) «اسکالپ فوق‌سریع» با اهرم بالا، بستن در سود خالص کاربر (مثلاً ۲–۳ دلار پس از کارمزد) و ~۱۰۰ معاملهٔ هم‌زمان
با ۱۰۰۰ دلار. پاسخ‌های کاربر: فعلاً کاغذی با قیمت زنده؛ سقف هم‌زمانی تا ۲۰۰ قابل تنظیم.
- بسته‌شدن: هر `TaskHandle` فرزند Qt ‏`AsyncRunner` بود و هرگز پاک نمی‌شد (چند کار در ثانیه ← ده‌ها هزار QObject).
  حالا `_on_handle_finished` ← صف `_graveyard` ← `purge_finished` (نابودی هم‌گام با `shiboken6.delete` پس از
  `FINISHED_HANDLE_GRACE_SECONDS=2`؛ `stop()` همه را پس از join نابود می‌کند). `deleteLater` مستقیم آزمون‌ها را
  با segfault می‌کشت (GC چرخه‌ای runner/نابودی هم‌زمان با emit) — تکرار نشود. کار زمان‌بندی‌نشده (runner متوقف)
  دستهٔ بی‌والد می‌گیرد. `app/diagnostics.py`: `data/logs/app.log` (چرخشی ۵MB)، `crash.log` (faulthandler +
  excepthook نخ‌ها)، `session.json` (`SessionMonitor`: ضربان ۶۰ث، `clean`؛ نشست ناتمام قبلی ← اعلان
  `common.unclean_exit`)، پیام‌های Qt در لاگ، `MainController.health_counters/log_health`. نوشتن DB پایش معامله
  محدود شد (`PERSIST_INTERVAL_SECONDS=2`، تغییر حد ضرر فوری). رویدادهای موتور: اعلان‌ها محدود (۲٫۵ث) و تازه‌سازی
  جدول‌ها یکجا (۴۰۰ms: `_schedule_auto_refresh`/`_flush_auto_refresh`).
- باز نشدن: حد ضرر دورِ سیگنال در اهرم بالا همیشه `risk_exceeds_loss_budget` می‌داد. حالا `_open_trade_locked` هدف
  و حد ضرر را به بودجهٔ دلاری کاربر محدود می‌کند (`stop_source`/`target_source` در extra رکورد). `scan_stats()`
  (نامزد/بازشده/دلیل‌های رد) در پنل با `trades.auto.scan_summary` و `trades.auto.reject.*` هر ۳ ثانیه دیده می‌شود.
- فوق‌سریع: `trading/ultra_scalp.py` (`momentum`، `UltraScalpSource` از کش تیک کل بازار + فیلتر نقدینگی)، حالت موتور
  `ultra` (`ULTRA_MIN_SCAN_INTERVAL=1`، `ULTRA_MIN_HOLD_SECONDS=10`، بدون ابطال سیگنال)، `HARD_MAX_CONCURRENT=200`،
  دکمهٔ «⚡ اسکالپ فوق‌سریع» (`TradesPage.ULTRA_PRESET`: ۱۰$×۵۰، هدف ۲$، ضرر ۲$، ۱۰۰ هم‌زمان، ۱۸۰ث، پویش ۱ث)، فیلد
  «بیشترین زمان باز ماندن»، تنظیم‌های `scalp.ultra_*`. کش روزانهٔ سود/زیان ۱ث و یک عکس پرتفوی برای هر ورود.
  حالت سفارش (کاغذی/واقعی) با پیش‌تنظیم عوض نمی‌شود؛ درگاه واقعی همچنان کاغذی است. سوکت حداکثر ۸۰ نماد
  (`MAX_STREAMED_SYMBOLS`)، بقیه با REST هر ۳ ثانیه.
آزمون: `tests/test_v254_ultra_and_stability.py`؛ کل مجموعه 2564 پاس + 2 skip. شبیه‌سازی ۳۰۰ نماد: ۱۰۰ معامله در
کمتر از ۸ ثانیه، بستن در سود خالص ≈ ۲ دلار (دادهٔ مصنوعی؛ نشانهٔ سودآوری نیست). گزارش: `docs/RELEASE_2.5.4_FA.md`.
**commit نشده** (آخرین commit: `511d2b5` = 2.5.1+2.5.2؛ 2.5.3 هم commit نشده است).

## وضعیت قبلی ۲.۵.۳ — ربات‌های ساخت فایل نصبی ویندوز و APK

گزارش کاربر: ساخت ویندوز «پنجره‌های زیادی از بخش‌های مختلف نرم‌افزار باز می‌کند و فایل نصبی نمی‌سازد»؛ APK با
«APK ساخته نشد» (RESULT=1) تمام می‌شود. علت ویندوز: `tools/build_installer.py` کل آزمون‌ها را روی دسکتاپ واقعی
(بدون offscreen) اجرا می‌کرد و هر شکست PyInstaller را متوقف می‌کرد؛ BOM در ابتدای bat جلوی `@echo off` را می‌گرفت؛
`.iss` بدون BOM بود. رفع: `tools/build_common.py` (`run_streaming` خروجی زنده + `build_logs/*.log`، `headless_env`)،
گام «بررسی سلامت کد» (compileall + import بی‌پنجرهٔ `SMOKE_CODE`)، آزمون کامل فقط با `--with-tests`/`RUN_TESTS=1`
(بی‌پنجره)، `upx=False`، `tests/conftest.py` پیش‌فرض offscreen، `scripts/build_windows.bat` ← `build_installer.bat`.
علت APK: `mobile/assets/` (آیکون/پیش‌نمایش/قلم) نبود، پذیرش مجوز SDK، `python-bidi` بدون پین (Rust)، آزمون ریاضی
با پایتون بدون numpy/pandas، ساخت روی `/mnt/c`، `pip --user` مسدود در اوبونتو ۲۴. رفع: `mobile/assets/*`،
`android.accept_sdk_license = True`، `python-bidi==0.4.2`، `warn_on_root = 0`، `check_toolchain`/`probe_script`
(buildozer در `~/.cai-buildozer`، فرمان apt دقیق)، `build_script` (کپی به `~/cryptoaitrader-apk`، ساخت روی
فایل‌سیستم لینوکس، برگرداندن APK به `mobile/bin`)، ردکردن آزمون ریاضی در نبود بسته‌ها. موبایل 1.9.13.
آزمون: `tests/test_v253_build_tools.py`. ساخت واقعی ویندوز/APK در sandbox ممکن نیست. گزارش: `docs/RELEASE_2.5.3_FA.md`.
**commit نشده** (آخرین commit: `511d2b5` = 2.5.1+2.5.2).

## وضعیت قبلی ۲.۵.۲ — فیوچرز LBank: HTTP 403 از Cloudflare

گزارش کاربر پس از 2.5.1: اسپات ✓ (۳ دارایی)، فیوچرز ✗ `NetworkError: HTTP 403 … /cfd/openApi/v1/prv/account`.
`lbkperp.lbank.com` پشت Cloudflare است (`api.lbkex.com` نه). رفع: `BROWSER_HEADERS` در `_contract_client`،
`LBankRestClient._classify_forbidden` + `_cloudflare_code`/`CLOUDFLARE_REASONS` ← `AccessBlockedError`
(`app/exceptions/errors.py`, زیرکلاس `NetworkError`) در `no_retry_on`، شکستن حلقهٔ دارایی‌های فیوچرز پس از
مسدودی، `wallet.hint.blocked/blocked_region` در `_wallet_error_hint`. کد Cloudflare واقعی کاربر هنوز نامعلوم؛
گزارش بعدی کیف پول آن را نشان می‌دهد. گزارش: `docs/RELEASE_2.5.2_FA.md`. commit شد در `511d2b5`.

## وضعیت قبلی ۲.۵.۱ — نمایش دارایی کیف پول، واچ‌لیست، ترتیب و قیمت بازارها

خواسته‌های کاربر: کیف پول هیچ دارایی (کل/اسپات/فیوچرز) نشان نمی‌داد؛ ساخت واچ‌لیست با کلیک راست روی ردیف/نماد
بازار؛ «افزودن به واچ‌لیست» مودال کار نمی‌کرد؛ ترتیب نمادها بر پایهٔ ارزش و حجم (BTC، ETH بالا)؛ قیمت دقیق تتری.
پیاده‌سازی: `LBankRestClient.signed_headers()` (امضا در سرآیند + بدنه)، `LBankEndpoints.USER_INFO_ACCOUNT/
USER_INFO_LEGACY`، `LBankProvider._spot_rows`/`last_sync_report`/زنجیرهٔ مسیرهای اسپات، `ExchangeAccountService`
(شکست اسپات با فیوچرز سالم غیرکشنده، `details["report"]`)، `WalletPage` (`status_panel`/`set_sync_report`،
`auto_sync_checkbox`، `spot_search`/`hide_small_checkbox`)، `MainController.start_wallet_auto_sync`/`sync_wallet(silent=)`/
`_fill_wallet_report`/`_wallet_error_hint`؛ `SymbolRepository.add_to_watchlist(symbol, exchange=None)` رکورد را می‌سازد،
`is_in_watchlist`، `MainController.set_watchlist_membership`/`_sync_symbol_table`؛ `market/market_rank.py`
(`sort_by_market_value`, `price_decimals`, `quote_usdt_prices`)، `MarketsPage.build_context_menu` و حالت
`market_cap`. آزمون: `tests/test_v251_wallet_watchlist_markets.py`. گزارش: `docs/RELEASE_2.5.1_FA.md`.
**این تغییرها commit نشده‌اند** (دستور صریح کاربر)؛ آخرین commit: `982cce2` (2.5.0).

## وضعیت قبلی ۲.۵.۰ — معامله از سیگنال، کیف پول سه‌زبانه، موجودی کاغذی

خواسته‌های کاربر: اشتراک سیگنال در شبکه‌های اجتماعی؛ جست‌وجوی بالا کشیده و گرد؛ «اقدام به معامله» با
ورود/SL/TP1–3 و بستن با اهداف (پاسخ کاربر: پلکانی ⅓/⅓/باقی، SL به ورود پس از TP1)، بستن مودال و رفتن به جدول
باز؛ بازسازی جدول تاریخچه و عنوان‌ها؛ ماشین‌حساب پرشده از سیگنال؛ بی‌درنگ؛ کیف پول سه‌زبانه (نمای کلی/اسپات/
فیوچرز) با اعداد دقیق فیوچرز؛ موجودی کاغذی جعلی برابر کیف پول واقعی. پیاده‌سازی: `trading/staged_targets.py`
(`next_step`)، `trading/trade_monitor.evaluate_staged`، `PaperTradeRepository.partial_close/realized_pnl_since`،
`trading/paper_account.py`، `MainController._on_trade_requested(signal, dialog=)`/`_apply_trade_step`/
`_paper_account`/`sync_paper_balance_with_wallet`/`_fill_wallet_tabs`، `WalletPage` (سه زبانه، `MetricStrip`،
`paper_sync_requested`)، `TradesPage.HISTORY_COLUMNS` (۱۶ ستون، عنوان هنگام ساخت، به‌روزرسانی درجا)،
`PositionCalculator` (TP2/TP3، `signal_entry`, `trade_values`)، `SignalDetailDialog` (`share_to`, `trade_payload`,
`trade_opened`)، `LBankRestClient._handle_response(contract=True)` (پاسخ `success:true`/`result:""` قبلاً «LBank
error 0» می‌شد — علت نمایش‌ندادن فیوچرز)، `LBankProvider._parse_futures_details`، `wallet_details` در
`extra_config`. گزارش: `docs/RELEASE_2.5.0_FA.md`. commit/push فقط با دستور صریح.

## وضعیت قبلی ۲.۴.۲ — سبکی رابط و کپی سیگنال

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
اصلاح شدند. جزئیات: `docs/RELEASE_2.2.2_FA.md`.
آزمون ترکیبی هسته/درگاه: ۷۰۸ پاس + ۳ skip؛ تست کامل Qt/ویندوز تأیید نشده است.
صفحهٔ دانلود: `tools/serve_downloads.py` با template همراه، مستقل از دسکتاپ.
ZIP جدید: `CryptoAITrader-v2.2.2-2026-09-23.zip`؛ هیچ commit/push انجام نشده.
R4 تا R10 بررسی اولیه هنوز باز هستند؛ آن‌ها را رفع‌شده معرفی نکن.

کار بعد: تست ZIP توسط کاربر، به‌خصوص مسیر GUI/ویندوز و تنظیم‌های paper؛
سپس بررسی R4 تا R10 طبق اولویت انتخابی او. اجازهٔ رفع باگ، مجوز commit/push نیست.
بخش‌های نسخه‌های قبلی در ادامه تاریخی‌اند.


## وضعیت نسخهٔ ۲.۲٫۱ — ۲۰۲۶-۰۹-۲۴

مرحلهٔ شناخت و مستندسازی تمام شد؛ تغییر رفتاری انجام نشده است.
قبل از شروع، `AGENTS.md` و `docs/PROJECT_MEMORY_FA.md` و گزارش
`docs/REVIEW_VALIDATION_FA.md` خوانده شوند. ZIP مبنا و ZIP بررسی جدا هستند.

اولویت‌های پیشنهادی، **هنوز مجوز اجرا ندارند**:
۱. R2: انتقال کامل تنظیم‌های ریسک به AutoTradeConfig با تست مسیر UI تا موتور.
۲. R1: خطای cache گزارش یک نماد با مجموعه‌تایم‌فریم متفاوت.
۳. R3: سیاست رازهای رمزنگاری‌شده در backup و صحت manifest.
۴. تست کامل UI/ویندوز و بررسی موارد R4 تا R10 مطابق انتخاب کاربر.

تست این محیط: ۶۷۴ پاس، ۲ skip؛ مجموعهٔ کامل به علت کتابخانه‌های Qt مسدود.
هیچ commit/push انجام نشده؛ پس از بررسی ZIP منتظر انتخاب کار بعدی و دستور
صریح کاربر برای ثبت/ارسال بمان. پیشنهادهای نسخه‌های قبل در ادامه تاریخی‌اند.


## وضعیت نسخهٔ ۲.۲٫۰ (۲۰۲۶-۰۹-۲۳)

ترمینال معاملهٔ خودکار حرفه‌ای شد (دور دوم بر اساس فهرست مشکلات
کاربر): کارت‌های سرمایه با آیکون و رنگ سود/زیان؛ اندیکاتور
EMA/SMA/بولینگر و خط‌کشی و عکس‌لحظه‌ای و منوی نماد آیکون‌دار روی
نمودار (بازخوانی کندل هر ۵ ثانیه)؛ تحلیل لحظه‌ای عامل هوش مصنوعی
روی نمادِ نمودار؛ پویش پس‌زمینهٔ همیشگی فرصت‌ها (حتی با موتور
خاموش، کلیدهای `scalp.watch_*`) + تنظیمات مودال؛ دکمهٔ بستن در هر
ردیف موقعیت + مودال جزئیات؛ مودال انتخاب نمادهای مورد علاقه با
ذخیره در دیتابیس و همگامی با فهرست پیگیری. مجموع ۲٬۲۷۰ آزمون
(۲٬۲۶۹ پاس + ۱ skip مربوط به LSTM).

جزئیات کامل: `BUILD_INFO.txt`، `PROJECT_PROGRESS.md` و `AI_HANDOVER.md`.

### باز برای نسخه‌های بعدی

۱. همبستگی میان نمادهای دارای موقعیت (مکمل پنل ریسک — بند ۲.۲
   نقشهٔ راه).
۲. قالب LSTM سبک روی دادهٔ واقعی بلندمدت (مدل آماده، داده کافی
   ندارد).
۳. کالیبراسیون ایزوتونیک وقتی هر سطل ≥۵۰ نمونهٔ حل‌شده داشت.
۴. رویدادهای کلان دستی (تصمیم کاربر) — فرم ورود و اتصال به
   `events.py`.

## وضعیت نسخهٔ ۲.۰٫۰ (۲۰۲۶-۰۹-۲۲)

موتور هوش پیش‌بینی کامل و متصل است (فازهای ۲ تا ۱۵ِ سند حاکم).
کارهای این نسخه: ۱۷ ماژول زیر signals/prediction/، موتور مرکزی
engine.py، جدول predictions + مهاجرت، دو ابزار عامل، صفحهٔ یازدهم
«پیش‌بینی»، دو رفع اشکال واقعی UI (دکمهٔ له‌شده با قلم واقعی، نشت
فونت بین آزمون‌ها) و ۱۵۷ آزمون تازه (مجموع ۲۱۷۹: ۲۱۷۸ پاس + ۱ skip
LSTM بدون torch اختیاری).

جزئیات کامل: `BUILD_INFO.txt`، `PROJECT_PROGRESS.md` و `AI_HANDOVER.md`.

### باز برای نسخه‌های بعدی

۱. قالب LSTM سبک روی دادهٔ واقعی بلندمدت (مدل آماده است، داده کافی
   ندارد).
۲. کالیبراسیون ایزوتونیک وقتی هر سطل ≥۵۰ نمونهٔ حل‌شده داشت.
۳. رویدادهای کلان دستی (تصمیم کاربر) — فرم ورود و اتصال به
   `events.py`.

## وضعیت نسخهٔ ۱.۹.۲۳ (۲۰۲۶-۰۹-۲۲)

### انجام شد

۱. **پایان خط فایل‌های `.bat` درست شد** — علت واقعی پنج آزمون مردود.
   `.gitattributes` با قاعدهٔ `*.bat text eol=crlf` اضافه شد؛ مخزن LF
   می‌ماند و checkout روی هر سیستم‌عاملی CRLF می‌دهد. بلاب‌های گیت
   دست‌نخورده ماندند. این احتمالاً همان علتی است که سازنده روی ویندوز
   کاربر شکست می‌خورد: عیب‌یاب خودِ برنامه اسکریپت‌ها را «ناموفق»
   می‌زد.

۲. **دو آزمون کهنه رفتاری شدند.** در هر دو مورد کد محصول درست بود و
   آزمون دنبال یک **نام** می‌گشت نه رفتار. هر دو پس از تغییر روی کدِ
   عمدی خراب‌شده اجرا شدند تا ثابت شود رگرسیون را می‌گیرند.

۳. **`destroy_window` در `tests/conftest.py`** — `deleteLater()` +
   `processEvents()` درخت ویجت را آزاد نمی‌کرد. `test_new_pages.py` از
   رد شدن بر سقف ۶۰۰ ثانیه به ۴۶ ثانیه رسید و
   `test_exchange_login_flow.py` از ۲۱۵ ثانیه به ۵۸ ثانیه. این اشکال
   کاربر را نمی‌زند؛ `main.py` فقط یک بار پنجره می‌سازد.

۴. **مستندات هم‌راستا شد.** نسخه در شش جا نوشته می‌شود نه چهار جا
   (دو README هم هست). شمار کلیدهای تنظیمات ۱۴۲ است نه ۱۳۶.
   `PROJECT_PROGRESS.md` مدخل ۱.۹.۲۲ نداشت که از `BUILD_INFO.txt` و
   `AI_HANDOVER.md` بازسازی و نوشته شد — چیزی اختراع نشد.

**نتیجهٔ آزمون‌ها: ۲۰۵۰ قبول / ۰ مردود / ۰ خطا** (۲۰۱۹ + ۷ مردودِ
درست‌شده + ۲۴ آزمون `test_new_pages.py` که قبلاً به‌خاطر TIMEOUT شمرده
نمی‌شدند). زمان کل مجموعه از ۱۰۰۴ ثانیه به ۲۸۳ ثانیه رسید.

### هنوز باز — بدون کاربر تمام نمی‌شود

۱. **`scripts\doctor.bat` روی ویندوز اجرا شود.** علت LF درست شده است؛
   حالا باید دید عیب‌یاب سالم گزارش می‌دهد یا نه. اگر هنوز شکست
   می‌خورد، `doctor_report.txt` لازم است و بدون آن دربارهٔ سازنده حدس
   زده نمی‌شود.

۲. **اسکرین‌شات بخش تولید سیگنال نرسیده است.**

۳. **اجراکنندهٔ واقعی LBank/Toobit.** تا سند رسمی فیلدهای سفارش نرسد،
   payload ساخته نمی‌شود. اگر اندازهٔ قرارداد نبود، حجم حدس زده
   نمی‌شود و سفارش رد می‌شود.

### پیشنهادها

فهرست جدا در `ADVANCED_FEATURES_FA.md` است (۲۰ مورد). هیچ‌کدام بدون
خواست صریح کاربر ساخته نمی‌شود و هیچ‌کدام مجوز معاملهٔ واقعی یا وعدهٔ
سود نیست.

### بعد از تأیید کاربر

کامیت و پوش فقط وقتی کاربر همین نسخه را تست کرد و صریح تأیید کرد.
تا پیش از آن، تحویل فقط زیپ روی صفحهٔ دانلود است.
