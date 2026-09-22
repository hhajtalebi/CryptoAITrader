"""
تعریف کلیدها و مقادیر پیش‌فرض تنظیمات کاربر.

چرا وجود دارد؟
    تنظیمات کاربر در جدول settings پایگاه داده به‌صورت کلید/مقدار نگهداری
    می‌شوند. برای جلوگیری از اشتباه تایپی و پراکندگی، همه کلیدها اینجا
    به‌صورت متمرکز تعریف شده‌اند.

قانون حیاتی (بند ۳۱ و ۵۶ سند پروژه):
    این مقادیر «فقط در صورت نبود کلید» در پایگاه داده نوشته می‌شوند.
    هیچ اجرای مجدد یا Migration نباید مقدار تنظیم‌شده توسط کاربر را
    بازنویسی کند.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class SettingKey(str, Enum):
    """کلیدهای معتبر تنظیمات کاربر، دسته‌بندی‌شده بر اساس بخش."""

    # --- General / عمومی ---
    LANGUAGE = "general.language"
    THEME = "general.theme"
    FIRST_RUN_COMPLETED = "general.first_run_completed"
    SCHEMA_VERSION = "general.schema_version"
    NOTIFICATIONS_ENABLED = "general.notifications_enabled"

    # --- Market / بازار ---
    DEFAULT_SYMBOL = "market.default_symbol"
    DEFAULT_TIMEFRAME = "market.default_timeframe"
    TICKER_REFRESH_SECONDS = "market.ticker_refresh_seconds"
    MAX_WATCHLIST_SUBSCRIPTIONS = "market.max_watchlist_subscriptions"
    CANDLE_CACHE_TTL_SECONDS = "market.candle_cache_ttl_seconds"
    HISTORY_CANDLES = "market.history_candles"

    # --- Exchange / صرافی ---
    ACTIVE_EXCHANGE = "exchange.active"
    EXCHANGE_ENABLED = "exchange.enabled"
    EXCHANGE_REQUEST_TIMEOUT = "exchange.request_timeout"
    EXCHANGE_MAX_RETRIES = "exchange.max_retries"
    EXCHANGE_RATE_LIMIT_PER_SECOND = "exchange.rate_limit_per_second"
    WEBSOCKET_ENABLED = "exchange.websocket_enabled"
    WEBSOCKET_RECONNECT_MAX_DELAY = "exchange.websocket_reconnect_max_delay"

    # --- Indicators / اندیکاتورها ---
    ENABLED_INDICATORS = "indicators.enabled"
    RSI_PERIOD = "indicators.rsi_period"
    EMA_FAST = "indicators.ema_fast"
    EMA_SLOW = "indicators.ema_slow"
    ATR_PERIOD = "indicators.atr_period"

    # --- AI / هوش مصنوعی ---
    AI_ENABLED = "ai.enabled"
    AI_ACTIVE_PROVIDER = "ai.active_provider"
    AI_FALLBACK_ENABLED = "ai.fallback_enabled"
    AI_TEMPERATURE = "ai.temperature"
    AI_MAX_TOKENS = "ai.max_tokens"
    AI_TIMEOUT = "ai.timeout"
    AI_MAX_REPAIR_ATTEMPTS = "ai.max_repair_attempts"
    AI_PROMPT_ANALYSIS = "ai.prompt_analysis"
    AI_PROMPT_SIGNAL = "ai.prompt_signal"
    AI_PROVIDER = "ai.provider"
    AI_MODEL = "ai.model"
    AI_BASE_URL = "ai.base_url"
    AI_MAX_AGENT_STEPS = "ai.max_agent_steps"
    AI_AGENT_TIMEOUT = "ai.agent_timeout"
    AI_FREE_MODELS_ONLY = "ai.free_models_only"
    AI_CHAT_TIMEOUT = "ai.chat_timeout"
    AI_CHAT_MAX_TOOLS = "ai.chat_max_tools"
    #: پروفایل سرعت: fast / balanced / deep. پیش‌فرض متعادل است.
    AI_SPEED_PROFILE = "ai.speed_profile"
    AI_SIGNAL_MODE = "ai.signal_mode"
    AI_NARRATIVE_ENABLED = "ai.narrative_enabled"
    AI_NARRATIVE_LANGUAGE = "ai.narrative_language"
    AI_SAVE_CHAT_HISTORY = "ai.save_chat_history"
    AI_CHAT_STREAMING = "ai.chat_streaming"
    AI_CHAT_HISTORY_LIMIT = "ai.chat_history_limit"
    #: سقف دستی پنجرهٔ متن مدل محلی؛ صفر یعنی «از حافظهٔ دستگاه تشخیص بده»
    AI_OLLAMA_MAX_CONTEXT = "ai.ollama_max_context"
    #: بازبینی خودکار سیگنال‌های بسته‌شده با هوش مصنوعی
    AI_AUTO_REVIEW = "ai.auto_review"
    #: منبع به‌روزرسانی: پوشهٔ محلی یا نشانی اینترنتی. خالی = خاموش.
    UPDATE_SOURCE = "update.source"
    #: بررسی خودکار نسخهٔ تازه هنگام اجرا
    UPDATE_AUTO_CHECK = "update.auto_check"

    # --- هشدارها (۱٫۹٫۱۸) ---
    #: روشن بودن سامانهٔ هشدار
    ALERTS_ENABLED = "alerts.enabled"
    #: فهرست هشدارهای تعریف‌شدهٔ کاربر
    ALERTS_ITEMS = "alerts.items"
    #: پخش صدا هنگام فعال‌شدن هشدار
    ALERTS_SOUND = "alerts.sound"

    # --- معاملهٔ خودکار اسکلپ (۱٫۹٫۱۴) ---
    #: روشن بودن موتور معاملهٔ خودکار
    SCALP_AUTO_ENABLED = "scalp.auto_enabled"
    #: `paper` یا `live` — پیش‌فرض همیشه کاغذی
    SCALP_MODE = "scalp.mode"
    #: عبارت تأیید معاملهٔ واقعی؛ تا دقیق وارد نشود سفارش واقعی نمی‌رود
    SCALP_LIVE_CONFIRMATION = "scalp.live_confirmation"
    #: صرافی مورد استفاده برای معاملهٔ خودکار
    SCALP_EXCHANGE = "scalp.exchange"
    #: مارجین هر معامله به دلار
    SCALP_MARGIN = "scalp.margin_per_trade"
    #: هدف سود هر معامله به دلار
    SCALP_TARGET_PROFIT = "scalp.target_profit"
    #: حداکثر زیان هر معامله به دلار
    SCALP_MAX_LOSS = "scalp.max_loss"
    #: اهرم
    SCALP_LEVERAGE = "scalp.leverage"
    #: بیشترین معاملهٔ همزمان
    SCALP_MAX_CONCURRENT = "scalp.max_concurrent"
    #: بیشترین زمان باز ماندن معامله (ثانیه)
    SCALP_MAX_HOLD = "scalp.max_hold_seconds"
    #: فاصلهٔ پایش قیمت (ثانیه)
    SCALP_POLL_SECONDS = "scalp.poll_seconds"
    #: سقف زیان روزانه به دلار
    SCALP_DAILY_LOSS_LIMIT = "scalp.daily_loss_limit"
    #: حداقل گردش ۲۴ ساعته برای واجد شرایط بودن یک نماد
    SCALP_MIN_TURNOVER = "scalp.min_turnover"
    #: بیشترین اسپرد قابل قبول (درصد)
    SCALP_MAX_SPREAD = "scalp.max_spread"
    #: تعداد نمادی که در هر دور پویش می‌شود
    SCALP_SCAN_LIMIT = "scalp.scan_limit"
    #: آیا هوش مصنوعی نامزدهای نهایی را بازبینی کند
    SCALP_AI_REVIEW = "scalp.ai_review"
    #: نرخ کارمزد گیرندهٔ هر طرف برای محاسبهٔ سود خالص
    SCALP_TAKER_FEE = "scalp.taker_fee_rate"
    #: منبع انتخاب نماد برای معاملهٔ خودکار: `scalp` یا `confidence`
    AUTOTRADE_SOURCE = "scalp.candidate_source"
    #: حداقل درصد اطمینان سیگنال برای ورود خودکار (حالت `confidence`)
    AUTOTRADE_MIN_CONFIDENCE = "scalp.min_confidence"
    #: چند نماد برتر در هر دور پویش بررسی شود
    AUTOTRADE_SCAN_SYMBOLS = "scalp.scan_symbols"
    UI_TIMEZONE = "ui.timezone"
    EXCHANGE_ACTIVE = "exchange.active"
    MARKET_MANUAL_TOMAN_RATE = "market.manual_toman_rate"
    SECURITY_STORE_SECRETS_IN_DB = "security.store_secrets_in_db"

    # --- Signals / سیگنال ---
    SIGNAL_TIMEFRAMES = "signals.timeframes"
    SIGNAL_TIMEFRAME_ROLES = "signals.timeframe_roles"
    SIGNAL_MIN_CONFIDENCE = "signals.min_confidence"
    SIGNAL_REQUIRE_AI = "signals.require_ai"
    SIGNAL_AUTO_SAVE = "signals.auto_save"
    SIGNAL_AI_TIMEOUT = "signals.ai_timeout"
    #: پنهان‌کردن سیگنال‌های سوخته از جدول‌ها
    SIGNAL_HIDE_STALE = "signals.hide_stale"

    # ---- سیگنال‌گیری خودکار و دوره‌ای ----
    SIGNAL_AUTO_SCAN_ENABLED = "signals.auto_scan_enabled"
    SIGNAL_AUTO_SCAN_INTERVAL = "signals.auto_scan_interval"
    SIGNAL_AUTO_SCAN_FULL_SWEEP = "signals.auto_scan_full_sweep"
    SIGNAL_AUTO_SCAN_FULL_INTERVAL = "signals.auto_scan_full_interval"
    SIGNAL_AUTO_SCAN_FOCUS_SIZE = "signals.auto_scan_focus_size"
    SIGNAL_AUTO_SCAN_MIN_CONFIDENCE = "signals.auto_scan_min_confidence"
    SIGNAL_AUTO_SCAN_SWEEP_LIMIT = "signals.auto_scan_sweep_limit"
    SIGNAL_AUTO_SCAN_NOTIFY = "signals.auto_scan_notify"

    # ---- پیگیری نتیجهٔ واقعی سیگنال‌ها ----
    SIGNAL_TRACK_OUTCOMES = "signals.track_outcomes"
    SIGNAL_TRACK_INTERVAL = "signals.track_interval"
    SIGNAL_TRACK_BATCH = "signals.track_batch"

    #: به‌روزرسانی ساعتی دفترچهٔ نتیجه؛ پیش‌فرض خاموش تا پهنای باند بی‌اجازه نرود
    SIGNAL_SCORECARD_AUTO = "signals.scorecard_auto"

    # --- Risk / مدیریت ریسک ---
    RISK_ACCOUNT_BALANCE = "risk.account_balance"
    RISK_PERCENT = "risk.risk_percent"
    RISK_MAX_LEVERAGE = "risk.max_leverage"
    RISK_MIN_RR = "risk.min_risk_reward"
    RISK_ATR_MULTIPLIER = "risk.atr_stop_multiplier"
    RISK_MAX_STOP_DISTANCE = "risk.max_stop_distance_percent"

    # --- Reports / گزارش‌ها ---
    REPORT_DEFAULT_FORMAT = "reports.default_format"
    REPORT_EXPORT_PATH = "reports.export_path"

    # --- Database & Backup / پایگاه داده و پشتیبان ---
    BACKUP_ENABLED = "backup.enabled"
    BACKUP_INTERVAL_HOURS = "backup.interval_hours"
    BACKUP_RETENTION = "backup.retention"
    BACKUP_PATH = "backup.path"
    BACKUP_BEFORE_MIGRATION = "backup.before_migration"

    # --- Security / امنیت ---
    SECURITY_STORAGE_BACKEND = "security.storage_backend"
    SECURITY_MASK_LOGS = "security.mask_logs"

    # ---- ایمیل (برای بازیابی رمز عبور) ----
    EMAIL_PRESET = "email.preset"
    EMAIL_SMTP_HOST = "email.smtp_host"
    EMAIL_SMTP_PORT = "email.smtp_port"
    EMAIL_SMTP_USERNAME = "email.smtp_username"
    EMAIL_SMTP_TLS = "email.smtp_tls"
    EMAIL_SENDER = "email.sender"
    EMAIL_SENDER_NAME = "email.sender_name"

    # --- UI / نمایش ---
    UI_MARKETS_SORT = "ui.markets_sort"
    UI_FONT_FAMILY = "ui.font_family"
    UI_FONT_SCALE = "ui.font_scale"
    UI_COMPACT_MODE = "ui.compact_mode"
    #: ترتیب و نمایان‌بودن بخش‌های داشبورد، به‌صورت رشتهٔ جداشده با کاما
    UI_DASHBOARD_LAYOUT = "ui.dashboard_layout"
    UI_CONFIRM_ACTIONS = "ui.confirm_actions"
    UI_SHOW_TOMAN = "ui.show_toman"
    UI_THEME = "ui.theme"
    UI_LANGUAGE = "ui.language"
    UI_TIMEZONE_KEY = "ui.timezone"
    UI_FOCUS_MODE = "ui.focus_mode"
    UI_SIDEBAR_COLLAPSED = "ui.sidebar_collapsed"

    # --- تحلیل ---
    ANALYSIS_ENABLED_INDICATORS = "analysis.enabled_indicators"
    ANALYSIS_LIVE_CHART = "analysis.live_chart"

    # --- Auth / حساب کاربری ---
    AUTH_SESSION_TOKEN = "auth.session_token"
    AUTH_LAST_USERNAME = "auth.last_username"
    AUTH_REQUIRE_LOGIN = "auth.require_login"

    # --- Performance / کارایی ---
    PERF_PARALLEL_REQUESTS = "performance.parallel_requests"
    PERF_CANDLE_CACHE_TTL = "performance.candle_cache_ttl"
    PERF_DASHBOARD_INTERVAL = "performance.dashboard_refresh_seconds"
    PERF_MARKETS_INTERVAL = "performance.markets_refresh_seconds"
    PERF_HTTP_TIMEOUT = "performance.http_timeout"
    PERF_MAX_RETRIES = "performance.max_retries"

    # --- Advanced / پیشرفته ---
    LOG_LEVEL = "advanced.log_level"
    OFFLINE_MODE_ALLOWED = "advanced.offline_mode_allowed"


# مقادیر پیش‌فرض؛ عمداً محافظه‌کارانه و سبک انتخاب شده‌اند.
DEFAULT_SETTINGS: dict[str, Any] = {
    # General
    SettingKey.LANGUAGE.value: "fa",
    SettingKey.THEME.value: "corporate_navy",
    SettingKey.FIRST_RUN_COMPLETED.value: False,
    SettingKey.SCHEMA_VERSION.value: 1,
    SettingKey.NOTIFICATIONS_ENABLED.value: True,
    # Market
    SettingKey.DEFAULT_SYMBOL.value: "BTC/USDT",
    SettingKey.DEFAULT_TIMEFRAME.value: "1h",
    SettingKey.TICKER_REFRESH_SECONDS.value: 5,
    SettingKey.MAX_WATCHLIST_SUBSCRIPTIONS.value: 12,
    SettingKey.CANDLE_CACHE_TTL_SECONDS.value: 30,
    SettingKey.HISTORY_CANDLES.value: 300,
    # Exchange
    SettingKey.ACTIVE_EXCHANGE.value: "lbank",
    SettingKey.EXCHANGE_ENABLED.value: True,
    SettingKey.EXCHANGE_REQUEST_TIMEOUT.value: 15,
    SettingKey.EXCHANGE_MAX_RETRIES.value: 3,
    SettingKey.EXCHANGE_RATE_LIMIT_PER_SECOND.value: 8,
    SettingKey.WEBSOCKET_ENABLED.value: True,
    SettingKey.WEBSOCKET_RECONNECT_MAX_DELAY.value: 60,
    # Indicators
    SettingKey.ENABLED_INDICATORS.value: [
        "EMA", "SMA", "RSI", "MACD", "ATR", "BBANDS", "ADX", "OBV", "VWAP", "STOCH",
    ],
    SettingKey.RSI_PERIOD.value: 14,
    SettingKey.EMA_FAST.value: 21,
    SettingKey.EMA_SLOW.value: 50,
    SettingKey.ATR_PERIOD.value: 14,
    # AI — کاربر خواست هوش مصنوعی به‌صورت پیش‌فرض فعال باشد. اگر سرویسی
    # پیکربندی نشده باشد، برنامه بی‌صدا به موتور تحلیل برمی‌گردد.
    SettingKey.AI_ENABLED.value: True,
    SettingKey.AI_ACTIVE_PROVIDER.value: "ollama",
    SettingKey.AI_FALLBACK_ENABLED.value: True,
    SettingKey.AI_TEMPERATURE.value: 0.2,
    SettingKey.AI_MAX_TOKENS.value: 1600,
    SettingKey.AI_TIMEOUT.value: 90,
    SettingKey.AI_MAX_REPAIR_ATTEMPTS.value: 2,
    SettingKey.AI_PROMPT_ANALYSIS.value: "technical_analysis_v1",
    SettingKey.AI_PROMPT_SIGNAL.value: "futures_signal_v1",
    SettingKey.AI_PROVIDER.value: "ollama",
    SettingKey.AI_MODEL.value: "llama3.1",
    # 127.0.0.1 عمدی است: روی برخی ویندوزها localhost به IPv6 می‌رود
    # و Ollama آنجا گوش نمی‌دهد.
    # خالی یعنی «نشانی پیش‌فرضِ همان سرویس از کاتالوگ». مقدار ثابتِ اولاما
    # باعث می‌شد انتخاب هر سرویس ابری بی‌اثر بماند و درخواست به localhost برود.
    SettingKey.AI_BASE_URL.value: "",
    SettingKey.AI_MAX_AGENT_STEPS.value: 8,
    SettingKey.AI_AGENT_TIMEOUT.value: 180,
    # کاربر خواست «اول مدل‌های رایگان»؛ پس فیلتر رایگان پیش‌فرض روشن است
    SettingKey.AI_FREE_MODELS_ONLY.value: True,
    SettingKey.AI_CHAT_TIMEOUT.value: 120,
    SettingKey.AI_CHAT_MAX_TOOLS.value: 4,
    SettingKey.AI_SPEED_PROFILE.value: "balanced",
    # پاسخ چت تکه‌تکه نمایش داده شود (مثل تایپ‌کردن) به‌جای انتظار
    # برای متن کامل. اگر سرویس جریان ندهد، خودکار به حالت عادی
    # برمی‌گردد، پس روشن‌بودنش بی‌خطر است.
    SettingKey.AI_CHAT_STREAMING.value: True,
    # حالت تولید سیگنال:
    #   hybrid  = موتور ریاضی تصمیم می‌گیرد، هوش مصنوعی بازبینی و تفسیر می‌کند
    #   ai_only = خود هوش مصنوعی تصمیم می‌گیرد (کندتر، وابسته به سرویس)
    #   engine  = فقط موتور ریاضی، بدون هوش مصنوعی (سریع‌ترین)
    SettingKey.AI_SIGNAL_MODE.value: "hybrid",
    # تحلیل نوشتاری فارسی برای هر سیگنال
    SettingKey.AI_NARRATIVE_ENABLED.value: True,
    SettingKey.AI_NARRATIVE_LANGUAGE.value: "fa",
    SettingKey.AI_SAVE_CHAT_HISTORY.value: True,
    SettingKey.AI_CHAT_HISTORY_LIMIT.value: 100,
    # صفر = تشخیص خودکار از حافظهٔ دستگاه. کاربری که کارت گرافیکش از
    # حافظهٔ سیستمش ضعیف‌تر است می‌تواند دستی پایین‌تر بیاورد.
    SettingKey.AI_OLLAMA_MAX_CONTEXT.value: 0,
    # پس از بسته‌شدن هر سیگنال، هوش مصنوعی در پس‌زمینه درسش را ثبت کند.
    # پیش‌فرض روشن است چون تنها راهی است که کاربر می‌فهمد چرا سیگنالی
    # سود نداد.
    SettingKey.AI_AUTO_REVIEW.value: True,
    # به‌روزرسانی پیش‌فرض خاموش است: برنامه نباید بدون اجازهٔ صریح
    # کاربر به جایی وصل شود. کاربر منبع را خودش تعیین می‌کند.
    SettingKey.UPDATE_SOURCE.value: "",
    # --- معاملهٔ خودکار اسکلپ ---
    # پیش‌فرض‌ها عمداً محافظه‌کارانه‌اند: خاموش، کاغذی، بدون تأیید.
    SettingKey.SCALP_AUTO_ENABLED.value: False,
    SettingKey.SCALP_MODE.value: "paper",
    SettingKey.SCALP_LIVE_CONFIRMATION.value: "",
    SettingKey.SCALP_EXCHANGE.value: "",
    SettingKey.SCALP_MARGIN.value: 10.0,
    SettingKey.SCALP_TARGET_PROFIT.value: 2.0,
    SettingKey.SCALP_MAX_LOSS.value: 3.0,
    SettingKey.SCALP_LEVERAGE.value: 10.0,
    SettingKey.SCALP_MAX_CONCURRENT.value: 3,
    SettingKey.SCALP_MAX_HOLD.value: 900,
    SettingKey.SCALP_POLL_SECONDS.value: 5.0,
    SettingKey.SCALP_DAILY_LOSS_LIMIT.value: 20.0,
    SettingKey.SCALP_MIN_TURNOVER.value: 2000000.0,
    SettingKey.SCALP_MAX_SPREAD.value: 0.25,
    SettingKey.SCALP_SCAN_LIMIT.value: 25,
    SettingKey.SCALP_AI_REVIEW.value: True,
    SettingKey.SCALP_TAKER_FEE.value: 0.0006,
    # پیش‌فرض «اطمینان»: کاربر خواست روی همهٔ ارزها تحلیل شود و هر
    # سیگنالی که اطمینانش از ۷۵٪ بالاتر رفت وارد معامله شود.
    SettingKey.AUTOTRADE_SOURCE.value: "confidence",
    SettingKey.AUTOTRADE_MIN_CONFIDENCE.value: 75,
    SettingKey.AUTOTRADE_SCAN_SYMBOLS.value: 40,
    SettingKey.UPDATE_AUTO_CHECK.value: False,
    SettingKey.ALERTS_ENABLED.value: True,
    SettingKey.ALERTS_ITEMS.value: [],
    SettingKey.ALERTS_SOUND.value: True,
    # نمایش زمان: «system» یعنی وقت محلی همین دستگاه
    SettingKey.UI_TIMEZONE.value: "system",
    SettingKey.EXCHANGE_ACTIVE.value: "lbank",
    # نرخ دستی تتر به تومان؛ صفر یعنی «خودکار از صرافی‌های ایرانی»
    SettingKey.MARKET_MANUAL_TOMAN_RATE.value: 0.0,
    SettingKey.SECURITY_STORE_SECRETS_IN_DB.value: True,
    # نمایش
    SettingKey.UI_MARKETS_SORT.value: "value",
    # قلم پیش‌فرض «ب کودک» است؛ درخواست صریح کاربر برای فارسی‌نویسی.
    SettingKey.UI_FONT_FAMILY.value: "vazirmatn",
    SettingKey.UI_FONT_SCALE.value: 100,
    SettingKey.UI_COMPACT_MODE.value: False,
    # چیدمان خالی یعنی «ترتیب پیش‌فرض صفحه»؛ به‌محض نخستین جابه‌جایی
    # کاربر پر می‌شود.
    SettingKey.UI_DASHBOARD_LAYOUT.value: "",
    SettingKey.UI_CONFIRM_ACTIONS.value: True,
    SettingKey.UI_SHOW_TOMAN.value: True,
    # پوستهٔ پیش‌فرض برنامه به خواست کاربر «شیشه‌ای تیره» است
    SettingKey.UI_THEME.value: "corporate_navy",
    SettingKey.UI_LANGUAGE.value: "fa",
    SettingKey.UI_TIMEZONE_KEY.value: "Asia/Tehran",
    SettingKey.UI_FOCUS_MODE.value: False,
    SettingKey.UI_SIDEBAR_COLLAPSED.value: False,
    # اندیکاتورهای فعال صفحهٔ تحلیل؛ فهرست خالی یعنی «پیش‌فرض برنامه»
    SettingKey.ANALYSIS_ENABLED_INDICATORS.value: [],
    # نمودار صفحهٔ تحلیل خودش تازه شود؛ خاموش‌کردنش برای اتصال‌های کند
    SettingKey.ANALYSIS_LIVE_CHART.value: True,
    # Auth — حالت مهمان پیش‌فرض است تا کاربر فعلی مجبور به ثبت‌نام نشود
    SettingKey.AUTH_SESSION_TOKEN.value: "",
    SettingKey.AUTH_LAST_USERNAME.value: "",
    SettingKey.AUTH_REQUIRE_LOGIN.value: False,
    # کارایی — این مقادیر مستقیماً روی سرعت برنامه اثر دارند
    SettingKey.PERF_PARALLEL_REQUESTS.value: 8,
    SettingKey.PERF_CANDLE_CACHE_TTL.value: 0,
    SettingKey.PERF_DASHBOARD_INTERVAL.value: 30,
    SettingKey.PERF_MARKETS_INTERVAL.value: 20,
    SettingKey.PERF_HTTP_TIMEOUT.value: 15,
    SettingKey.PERF_MAX_RETRIES.value: 3,
    # Signals
    SettingKey.SIGNAL_TIMEFRAMES.value: ["15m", "1h", "4h", "12h", "1d"],
    SettingKey.SIGNAL_TIMEFRAME_ROLES.value: {
        "15m": "entry",
        "1h": "short_trend",
        "4h": "medium_trend",
        "12h": "major_trend",
        "1d": "macro_trend",
    },
    SettingKey.SIGNAL_MIN_CONFIDENCE.value: 55,
    SettingKey.SIGNAL_REQUIRE_AI.value: False,
    SettingKey.SIGNAL_AUTO_SAVE.value: True,
    # سقف زمان انتظار برای تفسیر هوش مصنوعی؛ پس از آن سیگنال بدون تفسیر
    # نمایش داده می‌شود تا کاربر معطل نماند.
    #
    # چرا ۱۲۰ و نه ۴۵؟ مقدار قبلی ۴۵ ثانیه بود در حالی که مهلت چت ۱۲۰
    # ثانیه است. مدل محلی (اولاما) در نخستین درخواست باید وزنه‌ها را در
    # حافظه بارگذاری کند و همین کار به‌تنهایی روی یک دستگاه معمولی
    # می‌تواند بیش از یک دقیقه طول بکشد. نتیجه‌اش این بود که چت درست کار
    # می‌کرد ولی تحلیل سیگنال همیشه در ۴۵ ثانیه تسلیم می‌شد و بی‌صدا به
    # متن قالبی برمی‌گشت — کاربر این را «با هوش مصنوعی تحلیل نمی‌کند»
    # گزارش کرد. حالا هر دو مسیر یک مهلت دارند.
    SettingKey.SIGNAL_AI_TIMEOUT.value: 120,
    # پیش‌فرض خاموش: سیگنال سوخته حذف نمی‌شود بلکه برچسب می‌خورد.
    # پنهان‌کردن پیش‌فرضی، اطلاعات را از کاربر دریغ می‌کند؛ او باید
    # ببیند که سیگنالی بود و سوخت، نه اینکه ردیف بی‌صدا ناپدید شود.
    SettingKey.SIGNAL_HIDE_STALE.value: False,
    # پیش‌فرض خاموش است: پویش خودکار پهنای باند و سهمیهٔ صرافی مصرف
    # می‌کند و باید انتخاب آگاهانهٔ کاربر باشد.
    SettingKey.SIGNAL_AUTO_SCAN_ENABLED.value: False,
    SettingKey.SIGNAL_AUTO_SCAN_INTERVAL.value: 300,
    SettingKey.SIGNAL_AUTO_SCAN_FULL_SWEEP.value: True,
    SettingKey.SIGNAL_AUTO_SCAN_FULL_INTERVAL.value: 1800,
    SettingKey.SIGNAL_AUTO_SCAN_FOCUS_SIZE.value: 10,
    SettingKey.SIGNAL_AUTO_SCAN_MIN_CONFIDENCE.value: 55,
    SettingKey.SIGNAL_AUTO_SCAN_SWEEP_LIMIT.value: 120,
    SettingKey.SIGNAL_AUTO_SCAN_NOTIFY.value: True,
    # پیگیری نتیجه پیش‌فرض **روشن** است: برخلاف پویش خودکار، هزینه‌اش
    # ناچیز است (یک درخواست قیمت برای نمادهای باز) و بدون آن، آمار
    # عملکرد هرگز شکل نمی‌گیرد. کاربری که سیگنال می‌سازد باید بتواند
    # بعداً بپرسد «چقدرش درست بود؟» — پاسخ فقط وقتی هست که از روز اول
    # ثبت شده باشد.
    SettingKey.SIGNAL_TRACK_OUTCOMES.value: True,
    SettingKey.SIGNAL_TRACK_INTERVAL.value: 180,
    SettingKey.SIGNAL_TRACK_BATCH.value: 60,
    SettingKey.SIGNAL_SCORECARD_AUTO.value: False,
    # Risk
    SettingKey.RISK_ACCOUNT_BALANCE.value: 1000.0,
    SettingKey.RISK_PERCENT.value: 1.0,
    SettingKey.RISK_MAX_LEVERAGE.value: 5,
    SettingKey.RISK_MIN_RR.value: 1.5,
    SettingKey.RISK_ATR_MULTIPLIER.value: 1.5,
    SettingKey.RISK_MAX_STOP_DISTANCE.value: 5.0,
    # Reports
    SettingKey.REPORT_DEFAULT_FORMAT.value: "csv",
    SettingKey.REPORT_EXPORT_PATH.value: "",
    # Backup
    SettingKey.BACKUP_ENABLED.value: True,
    SettingKey.BACKUP_INTERVAL_HOURS.value: 24,
    SettingKey.BACKUP_RETENTION.value: 7,
    SettingKey.BACKUP_PATH.value: "",
    SettingKey.BACKUP_BEFORE_MIGRATION.value: True,
    # Security
    SettingKey.SECURITY_STORAGE_BACKEND.value: "auto",
    SettingKey.SECURITY_MASK_LOGS.value: True,
    # رمز SMTP اینجا نیست؛ در انبار رمزنگاری‌شده می‌نشیند
    SettingKey.EMAIL_PRESET.value: "gmail",
    SettingKey.EMAIL_SMTP_HOST.value: "smtp.gmail.com",
    SettingKey.EMAIL_SMTP_PORT.value: 587,
    SettingKey.EMAIL_SMTP_USERNAME.value: "",
    SettingKey.EMAIL_SMTP_TLS.value: True,
    SettingKey.EMAIL_SENDER.value: "",
    SettingKey.EMAIL_SENDER_NAME.value: "Crypto AI Trader",
    # Advanced
    SettingKey.LOG_LEVEL.value: "INFO",
    SettingKey.OFFLINE_MODE_ALLOWED.value: True,
}

# دسته‌بندی تنظیمات برای نمایش در صفحه Settings رابط کاربری.
SETTING_CATEGORIES: dict[str, list[str]] = {
    "general": [SettingKey.LANGUAGE.value, SettingKey.THEME.value, SettingKey.NOTIFICATIONS_ENABLED.value],
    "market": [
        SettingKey.DEFAULT_SYMBOL.value,
        SettingKey.DEFAULT_TIMEFRAME.value,
        SettingKey.TICKER_REFRESH_SECONDS.value,
        SettingKey.MAX_WATCHLIST_SUBSCRIPTIONS.value,
        SettingKey.HISTORY_CANDLES.value,
    ],
    "exchange": [
        SettingKey.ACTIVE_EXCHANGE.value,
        SettingKey.EXCHANGE_ENABLED.value,
        SettingKey.EXCHANGE_REQUEST_TIMEOUT.value,
        SettingKey.EXCHANGE_MAX_RETRIES.value,
        SettingKey.EXCHANGE_RATE_LIMIT_PER_SECOND.value,
        SettingKey.WEBSOCKET_ENABLED.value,
    ],
    "indicators": [
        SettingKey.ENABLED_INDICATORS.value,
        SettingKey.RSI_PERIOD.value,
        SettingKey.EMA_FAST.value,
        SettingKey.EMA_SLOW.value,
        SettingKey.ATR_PERIOD.value,
    ],
    "ai": [
        SettingKey.AI_ENABLED.value,
        SettingKey.AI_PROVIDER.value,
        SettingKey.AI_MODEL.value,
        SettingKey.AI_BASE_URL.value,
        SettingKey.AI_MAX_AGENT_STEPS.value,
        SettingKey.AI_AGENT_TIMEOUT.value,
        SettingKey.AI_FREE_MODELS_ONLY.value,
        SettingKey.AI_CHAT_TIMEOUT.value,
        SettingKey.AI_CHAT_MAX_TOOLS.value,
        SettingKey.AI_CHAT_STREAMING.value,
        SettingKey.AI_ACTIVE_PROVIDER.value,
        SettingKey.AI_FALLBACK_ENABLED.value,
        SettingKey.AI_TEMPERATURE.value,
        SettingKey.AI_MAX_TOKENS.value,
        SettingKey.AI_TIMEOUT.value,
    ],
    "signals": [
        SettingKey.SIGNAL_TIMEFRAMES.value,
        SettingKey.SIGNAL_MIN_CONFIDENCE.value,
        SettingKey.SIGNAL_REQUIRE_AI.value,
        SettingKey.SIGNAL_AUTO_SAVE.value,
        SettingKey.SIGNAL_AUTO_SCAN_ENABLED.value,
        SettingKey.SIGNAL_AUTO_SCAN_INTERVAL.value,
        SettingKey.SIGNAL_AUTO_SCAN_FULL_SWEEP.value,
        SettingKey.SIGNAL_AUTO_SCAN_FULL_INTERVAL.value,
        SettingKey.SIGNAL_AUTO_SCAN_FOCUS_SIZE.value,
        SettingKey.SIGNAL_AUTO_SCAN_MIN_CONFIDENCE.value,
        SettingKey.SIGNAL_AUTO_SCAN_SWEEP_LIMIT.value,
        SettingKey.SIGNAL_AUTO_SCAN_NOTIFY.value,
        SettingKey.SIGNAL_TRACK_OUTCOMES.value,
        SettingKey.SIGNAL_TRACK_INTERVAL.value,
        SettingKey.SIGNAL_TRACK_BATCH.value,
    ],
    "risk": [
        SettingKey.RISK_ACCOUNT_BALANCE.value,
        SettingKey.RISK_PERCENT.value,
        SettingKey.RISK_MAX_LEVERAGE.value,
        SettingKey.RISK_MIN_RR.value,
        SettingKey.RISK_ATR_MULTIPLIER.value,
        SettingKey.RISK_MAX_STOP_DISTANCE.value,
    ],
    "reports": [SettingKey.REPORT_DEFAULT_FORMAT.value, SettingKey.REPORT_EXPORT_PATH.value],
    "backup": [
        SettingKey.BACKUP_ENABLED.value,
        SettingKey.BACKUP_INTERVAL_HOURS.value,
        SettingKey.BACKUP_RETENTION.value,
        SettingKey.BACKUP_PATH.value,
    ],
    "security": [SettingKey.SECURITY_STORAGE_BACKEND.value, SettingKey.SECURITY_MASK_LOGS.value],
    "email": [
        SettingKey.EMAIL_PRESET.value,
        SettingKey.EMAIL_SMTP_HOST.value,
        SettingKey.EMAIL_SMTP_PORT.value,
        SettingKey.EMAIL_SMTP_USERNAME.value,
        SettingKey.EMAIL_SMTP_TLS.value,
        SettingKey.EMAIL_SENDER.value,
        SettingKey.EMAIL_SENDER_NAME.value,
    ],
    "auth": [
        SettingKey.AUTH_SESSION_TOKEN.value,
        SettingKey.AUTH_LAST_USERNAME.value,
        SettingKey.AUTH_REQUIRE_LOGIN.value,
    ],
    "advanced": [SettingKey.LOG_LEVEL.value, SettingKey.OFFLINE_MODE_ALLOWED.value],
}
