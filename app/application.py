"""
هماهنگ‌کننده اصلی برنامه (Composition Root).

چرا وجود دارد؟
    تنها جایی است که همه اجزا به هم وصل می‌شوند. بقیه کلاس‌ها وابستگی‌های
    خود را از سازنده می‌گیرند و هیچ‌کدام نمونه سراسری نمی‌سازند — همان
    اصل وارونگی وابستگی که در سراسر پروژه رعایت شده است.

ترتیب راه‌اندازی:
    مسیرها → لاگ → پایگاه داده → تنظیمات → رمزها → صرافی → موتور داده
    → اندیکاتورها → راهبردها → موتور سیگنال → هوش مصنوعی (اختیاری)
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config.settings_service import SettingsService
from app.core.constants import (
    APP_NAME,
    APP_VERSION,
    MarketStructureType,
    SignalDirection,
    TrendDirection,
)
from app.core.events import EventBus, event_bus
from app.core.models import RiskParameters
from app.core.paths import AppPaths, app_paths
from app.core.auth_service import AuthService
from app.core.exchange_account_service import ExchangeAccountService
from app.database.repositories import (
    SignalReviewRepository,
    AIProviderRepository,
    BackupHistoryRepository,
    CandleRepository,
    ChatRepository,
    ExchangeAccountRepository,
    PaperTradeRepository,
    SettingsRepository,
    PredictionRepository,
    SignalOutcomeRepository,
    SignalRepository,
    SymbolRepository,
    UserRepository,
)
from app.database.session import DatabaseManager
from app.logging import get_logger
from app.core.email_service import EmailService
from app.core.password_reset import PasswordResetService
from app.security.secret_store import get_secret_store
from backup import BackupManager
from indicators import IndicatorEngine
from indicators.registry import register_builtin_indicators
from market.engine import MarketDataEngine
from market.providers.registry import exchange_registry, register_builtin_providers
from reports import ReportBuilder, ReportExporter
from signals import RiskEngine, SignalEngine
from signals.strategies.registry import register_builtin_strategies

logger = get_logger(__name__)

#: پنجرهٔ حذف ذخیرهٔ تکراری سیگنال پویش (ثانیه) — ۲.۴.۲
SCAN_DEDUP_SECONDS = 30 * 60
#: تغییر اطمینانی که با وجود تکرار، ذخیرهٔ دوباره را توجیه می‌کند
SCAN_DEDUP_CONFIDENCE = 5


def _as_float(value: Any, fallback: float | None = None) -> float | None:
    """تبدیل امن به عدد؛ مقدار نامعتبر، مقدار قبلی را دست‌نخورده می‌گذارد."""
    try:
        if value is None or value == "":
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


class Application:
    """
    ظرف وابستگی‌های برنامه.

    نمونه‌سازی:
        app = Application()
        await app.start()
        ...
        await app.stop()
    """

    def __init__(self, paths: AppPaths | None = None, bus: EventBus | None = None) -> None:
        self.paths = (paths or app_paths).ensure()
        self.events = bus or event_bus

        # ---- پایگاه داده و تنظیمات ----
        self.database = DatabaseManager(self.paths.database_url)
        self.database.create_all()

        self.settings_repository = SettingsRepository(self.database)
        self.settings = SettingsService(self.settings_repository, self.events)
        self.settings.initialize_defaults()

        self.symbol_repository = SymbolRepository(self.database)
        self.candle_repository = CandleRepository(self.database)
        self.signal_repository = SignalRepository(self.database)
        #: شناسهٔ آخرین سیگنال ذخیره‌شده (برای تحلیل دوباره از رابط کاربری)
        self._last_signal_id: int = 0
        self.outcome_repository = SignalOutcomeRepository(self.database)
        # موتور هوش پیش‌بینی (v1.11.0): رکوردهای ۱۳ افق + حل با قیمت واقعی
        self.prediction_repository = PredictionRepository(self.database)
        self.review_repository = SignalReviewRepository(self.database)
        self.chat_repository = ChatRepository(self.database)
        self.ai_provider_repository = AIProviderRepository(self.database)
        self.backup_repository = BackupHistoryRepository(self.database)
        self.user_repository = UserRepository(self.database)
        self.exchange_account_repository = ExchangeAccountRepository(self.database)
        self.trade_repository = PaperTradeRepository(self.database)

        # ---- امنیت و پشتیبان ----
        self.secrets = get_secret_store()
        # کاربر خواست کلیدهای صرافی در پایگاه داده بمانند تا با تعویض
        # صرافی خودکار بارگذاری شوند. مقدارها رمزنگاری‌شده ذخیره می‌شوند،
        # چون «روی دستگاه خودم است» دلیل نمی‌شود کلید خام روی دیسک بنشیند.
        if self.settings.get_bool("security.store_secrets_in_db", True):
            from app.security.db_backend import DatabaseBackend

            self.secrets.use_backend(DatabaseBackend(self.settings_repository))
        self.backup = BackupManager(self.paths)

        # ---- کاربران و حساب‌های صرافی ----
        # حالت مهمان پیش‌فرض است؛ اگر نشست ذخیره‌شده معتبر باشد، کاربر
        # به‌طور خودکار وارد می‌شود و ترجیحات خودش اعمال می‌گردد.
        self.auth = AuthService(self.user_repository, self.settings)
        # ایمیل و بازیابی رمز: برنامه سرور ندارد، پس از SMTP خود کاربر
        # استفاده می‌کند و اگر تنظیم نشده باشد کد را درون برنامه نشان
        # می‌دهد تا کسی از حسابش بیرون نماند.
        self.email = EmailService(self.settings, self.secrets)
        self.password_reset = PasswordResetService(self.user_repository, self.email)
        self.exchange_accounts = ExchangeAccountService(
            self.exchange_account_repository, self.secrets
        )
        try:
            self.user_repository.purge_expired_sessions()
            self.auth.restore_session()
        except Exception:  # noqa: BLE001 - خطای نشست نباید راه‌اندازی را متوقف کند
            logger.warning("Session restore skipped")

        # ---- ثبت افزونه‌ها ----
        # همه رجیستری‌ها اینجا پر می‌شوند تا هیچ ماژولی هنگام import
        # عارضه جانبی نداشته باشد.
        register_builtin_providers()
        register_builtin_indicators()
        register_builtin_strategies()

        # ---- موتورها ----
        self.indicators = IndicatorEngine()
        self.market: MarketDataEngine | None = None
        self.signals: SignalEngine | None = None
        self._compute_pool: Any = None
        self._scan_saved: dict[tuple[str, str, str], tuple[float, int]] = {}
        self.risk = RiskEngine(self.risk_parameters())

        # ---- گزارش ----
        self.report_builder = ReportBuilder(self.signal_repository)
        self.report_exporter = ReportExporter(self.paths)

        # ---- هوش مصنوعی (تنبل: فقط در صورت نیاز ساخته می‌شود) ----
        self._ai_analyst: Any = None
        self._ai_manager: Any = None
        self._ai_toolset: Any = None
        self._autonomous_agent: Any = None
        self._chat_agent: Any = None
        # موتور هوش پیش‌بینی — تنبل، مثل اجزای AI
        self._prediction_engine: Any = None

        logger.info("%s v%s composition root initialised", APP_NAME, APP_VERSION)

    # ------------------------------------------------------------------
    # تنظیمات
    # ------------------------------------------------------------------
    @property
    def prediction_engine(self) -> Any | None:
        """
        موتور هوش پیش‌بینی (تنبل) — پس از نخستین فراخوانی کش می‌شود.

        منبع کندل، موتور بازارِ «فعلی» است؛ اگر کاربر صرافی عوض کند
        `invalidate_prediction_engine` نمونه را می‌سازد تا با منبع تازه
        ساخته شود. ذخیره‌سازی روی `prediction_repository` انجام می‌شود و
        حل افق‌ها با کندل‌های واقعیِ دیتابیس، نه دادهٔ جعلی.
        """
        if self._prediction_engine is not None:
            return self._prediction_engine
        if self.market is None:
            return None

        from signals.prediction.engine import PredictiveIntelligenceEngine
        from signals.prediction.store import PredictionStore

        def lookup_price(symbol: str, at: Any) -> float | None:
            """قیمت واقعی در لحظهٔ سرآمدن افق — از کندل‌های ذخیره‌شده."""
            from datetime import timedelta  # noqa: PLC0415

            try:
                at_naive = at.replace(tzinfo=None) if at.tzinfo else at
                candidates = self.candle_repository.get_candles(
                    self.market.exchange_name, symbol, "1h", 800
                )
                # نزدیک‌ترین کندلِ «بسته‌شده قبل یا در» لحظهٔ هدف
                eligible = [c for c in candidates if c.timestamp <= at_naive.timestamp()]
                if not eligible:
                    return None
                candle = eligible[-1]
                return float(candle.close)
            except Exception:  # noqa: BLE001 - نباید حل افق را بکشد
                return None

        store = PredictionStore(self.prediction_repository, price_lookup=lookup_price)
        self._prediction_engine = PredictiveIntelligenceEngine(
            self.market.get_candles,
            store=store,
            settings=self.settings,
        )
        logger.info("Predictive intelligence engine initialised")
        return self._prediction_engine

    def invalidate_prediction_engine(self) -> None:
        """بازسازی موتور پیش‌بینی — مثلاً پس از تغییر صرافی فعال."""
        self._prediction_engine = None

    def risk_parameters(self) -> RiskParameters:
        """خواندن پارامترهای ریسک از تنظیمات کاربر."""
        try:
            return self.settings.get_risk_parameters()
        except Exception:  # noqa: BLE001 - در بدترین حالت پیش‌فرض محافظه‌کارانه
            logger.warning("Falling back to default risk parameters")
            return RiskParameters()

    def apply_risk_settings(self) -> None:
        """هم‌گام‌سازی پارامترهای ریسک در همه موتورها پس از تغییر تنظیمات."""
        parameters = self.risk_parameters()
        self.risk.set_parameters(parameters)
        if self.signals is not None:
            self.signals.set_risk_parameters(parameters)
        if self._ai_analyst is not None:
            self._ai_analyst.set_risk_parameters(parameters)

    # ------------------------------------------------------------------
    # چرخه عمر
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """راه‌اندازی موتور داده بازار و موتور سیگنال."""
        exchange_name = self.settings.active_exchange
        provider = exchange_registry.create(exchange_name)

        self.market = MarketDataEngine(
            provider,
            candle_repository=self.candle_repository,
            event_bus=self.events,
        )
        await self.market.start()

        self.signals = SignalEngine(
            self.market,
            self.indicators,
            self.risk,
            risk_parameters=self.risk_parameters(),
            calibration_source=self.outcome_repository,
        )
        self.signals.set_compute_pool(self.compute_pool())
        logger.info("Application started with exchange '%s'", exchange_name)

    async def switch_exchange(self, exchange_name: str = "") -> str:
        """
        تعویض زندهٔ صرافی فعال بدون بستن برنامه.

        چرا لازم است: کاربر در تنظیمات صرافی را عوض می‌کند و انتظار دارد
        بازارها، قیمت‌ها و کیف پول از همان صرافی بیایند. پیش از این فقط
        مقدار تنظیمات ذخیره می‌شد و موتور تا اجرای بعدی برنامه روی صرافی
        قبلی می‌ماند — یعنی انتخاب کاربر عملاً نادیده گرفته می‌شد.

        اعتبارنامهٔ همان صرافی خودکار بارگذاری می‌شود تا داده‌های خصوصی
        (موجودی، سفارش‌ها) هم در دسترس باشد.

        بازگشتی: نام صرافیِ فعال پس از تعویض. اگر ساخت صرافی تازه شکست
        بخورد، موتور قبلی دست‌نخورده می‌ماند تا برنامه بی‌داده نشود.
        """
        target = (exchange_name or self.settings.active_exchange or "").strip().lower()
        if not target:
            return self.market.exchange_name if self.market is not None else ""

        if self.market is not None and self.market.exchange_name == target:
            return target

        api_key, api_secret = self.exchange_credentials(target)
        try:
            provider = exchange_registry.create(
                target, api_key=api_key, api_secret=api_secret
            )
        except Exception:
            logger.exception("Could not build provider for '%s'; keeping current", target)
            raise

        previous = self.market
        engine = MarketDataEngine(
            provider,
            candle_repository=self.candle_repository,
            event_bus=self.events,
        )
        await engine.start()

        self.market = engine
        self.invalidate_prediction_engine()
        # موتور سیگنال به موتور بازار گره خورده است و باید دوباره ساخته
        # شود، وگرنه سیگنال‌ها از صرافی قبلی تغذیه می‌شوند.
        self.signals = SignalEngine(
            engine,
            self.indicators,
            self.risk,
            risk_parameters=self.risk_parameters(),
            calibration_source=self.outcome_repository,
        )
        self.signals.set_compute_pool(self.compute_pool())
        # عامل هوش مصنوعی هم موتور قدیمی را نگه داشته؛ دور ریخته می‌شود
        # تا با صرافی تازه بازساخته شود.
        self._ai_analyst = None

        if previous is not None:
            try:
                await previous.stop()
            except Exception:  # noqa: BLE001 - بستن قبلی نباید تعویض را خراب کند
                logger.warning("Stopping the previous exchange engine failed")

        self.settings.set("exchange.active", target)
        logger.info("Active exchange switched to '%s'", target)
        return target

    async def stop(self) -> None:
        """توقف تمیز همه اجزا."""
        if self._compute_pool is not None:
            self._compute_pool.shutdown()
        if self.market is not None:
            await self.market.stop()
        if self._ai_manager is not None:
            await self._ai_manager.close()
        logger.info("Application stopped")

    # ------------------------------------------------------------------
    # استخر محاسبه و حذف ذخیرهٔ تکراری پویش (۲.۴.۲)
    # ------------------------------------------------------------------
    def compute_pool(self) -> Any:
        """
        استخر فرایند محاسبهٔ پویش انبوه (تنبل؛ کارگرها فقط هنگام پویش بالا می‌آیند).

        با تنظیم `performance.process_pool=false` یا متغیر محیطی
        `CRYPTOAI_NO_PROCESS_POOL=1` خاموش می‌شود و همان محاسبهٔ محلی
        ۲.۴.۱ انجام می‌شود.
        """
        if os.environ.get("CRYPTOAI_NO_PROCESS_POOL", "").strip() in {"1", "true", "yes"}:
            return None
        try:
            if not self.settings.get_bool("performance.process_pool", True):
                return None
        except Exception:  # noqa: BLE001
            pass
        if self._compute_pool is None:
            from signals.compute_pool import ComputePool

            self._compute_pool = ComputePool()
        return self._compute_pool

    def _should_store_scanned(self, signal: Any, *, now: float | None = None) -> bool:
        """
        آیا این سیگنال پویش باید ذخیره شود؟

        پویش خودکار هر چند دقیقه همان نمادها را دوباره می‌بیند؛ ذخیرهٔ هر بار
        آن‌ها پایگاه داده و جدول پیگیری نتیجه را بی‌وقفه بزرگ می‌کرد و صفحهٔ
        عملکرد را کند. همان نماد/صرافی/جهت اگر در ۳۰ دقیقهٔ اخیر ذخیره شده و
        اطمینانش کمتر از ۵ واحد تغییر کرده باشد، دوباره ذخیره نمی‌شود.
        """
        moment = time.monotonic() if now is None else now
        key = (
            str(getattr(signal, "exchange", "") or ""),
            str(getattr(signal, "symbol", "") or "").upper(),
            str(getattr(getattr(signal, "direction", None), "value", "")),
        )
        confidence = int(getattr(signal, "confidence", 0) or 0)
        previous = self._scan_saved.get(key)
        if previous is not None:
            saved_at, saved_confidence = previous
            if (moment - saved_at) < SCAN_DEDUP_SECONDS and abs(
                confidence - saved_confidence
            ) < SCAN_DEDUP_CONFIDENCE:
                return False
        self._scan_saved[key] = (moment, confidence)
        if len(self._scan_saved) > 20_000:
            cutoff = moment - SCAN_DEDUP_SECONDS
            self._scan_saved = {
                k: v for k, v in self._scan_saved.items() if v[0] >= cutoff
            }
        return True

    # ------------------------------------------------------------------
    # هوش مصنوعی (اختیاری)
    # ------------------------------------------------------------------
    def ai_enabled(self) -> bool:
        """آیا کاربر هوش مصنوعی را فعال کرده است؟"""
        return bool(self.settings.get_bool("ai.enabled", False))

    def ai_analyst(self) -> Any:
        """
        ساخت تنبل عامل هوش مصنوعی.

        اگر هوش مصنوعی غیرفعال باشد یا موتور بازار آماده نباشد، None
        برمی‌گردد و فراخواننده باید بدون آن ادامه دهد.
        """
        if not self.ai_enabled() or self.market is None:
            return None
        if self._ai_analyst is not None:
            return self._ai_analyst

        from ai.agent import AIAnalyst
        from ai.providers import AIProviderConfig, AIProviderManager
        from ai.providers.catalog import get_preset
        from ai.providers.omniroute_provider import DEFAULT_BASE_URL as OMNIROUTE_DEFAULT_BASE_URL
        from ai.tools import CompositeToolset, MarketToolset, OmniRouteToolset

        manager = AIProviderManager(
            self.events, fallback_enabled=self.settings.get_bool("ai.fallback_enabled", True)
        )

        provider_type = str(self.settings.get("ai.provider", "ollama"))
        preset = get_preset(provider_type)

        # نوع پیاده‌سازی از کاتالوگ می‌آید، نه از نام سرویس. بدون این،
        # سرویس‌هایی مثل openai یا groq به کلاس اشتباه وصل می‌شدند.
        implementation = preset.provider_type if preset is not None else "openai_compatible"
        requires_key = preset.requires_key if preset is not None else provider_type != "ollama"
        default_url = preset.base_url if preset is not None else ""

        # نشانی دستی فقط وقتی معتبر است که به همین سرویس تعلق داشته باشد.
        # `ai.base_url` پیش‌فرضِ اولیه‌اش نشانی اولاما است؛ بدون این بررسی،
        # کاربر سرویس را روی openrouter می‌گذارد ولی درخواست به
        # 127.0.0.1:11434 می‌رود و خطای «Network error» می‌گیرد — دقیقاً
        # همان «با هوش مصنوعی کار نمی‌کند» که کاربر گزارش کرد.
        configured_url = str(self.settings.get("ai.base_url", "") or "").strip()
        base_url = self._resolve_base_url(configured_url, default_url, provider_type)

        config = AIProviderConfig(
            name=provider_type,
            base_url=base_url,
            model=str(self.settings.get("ai.model", "")),
            temperature=float(self.settings.get("ai.temperature", 0.2)),
            max_tokens=int(self.settings.get_int("ai.max_tokens", 1600)),
            timeout=int(self.settings.get_int("ai.timeout", 90)),
            requires_api_key=requires_key,
            extra=self._provider_extra(implementation),
        )
        # همان قاعدهٔ فهرست مدل‌ها: کلید اگر هست فرستاده می‌شود، چون
        # «کلید لازم ندارد» به معنی «کلید نمی‌پذیرد» نیست.
        api_key = self._ai_api_key(provider_type)
        manager.register_from_type(implementation, config, api_key)

        # همهٔ سرویس‌های پیکربندی‌شدهٔ دیگر هم ثبت می‌شوند تا زنجیرهٔ
        # جایگزینی واقعاً کار کند. پیش‌تر فقط سرویس فعال ثبت می‌شد، پس
        # `ai.fallback_enabled` عملاً بی‌اثر بود: با از کار افتادن همان یک
        # سرویس، چت و تحلیل کامل شکست می‌خورد.
        self._register_fallback_providers(manager, skip=provider_type)

        # موتور سیگنال به ابزارها داده می‌شود تا مدل بتواند نظر
        # قطعی‌گرای موتور را بپرسد. بدون آن، مدل‌های کوچک باید کل تحلیل
        # را از دادهٔ خام بازسازی کنند و معمولاً به «انتظار» پناه می‌برند.
        market_tools = MarketToolset(
            self.market,
            self.indicators,
            risk_parameters=self.risk_parameters(),
            signal_engine=self.signals,
            prediction_engine=self.prediction_engine,
        )
        # ابزارهای دروازه همیشه در دسترس‌اند، حتی وقتی سرویس فعال OmniRoute
        # نیست: در آن حالت ابزار صادقانه می‌گوید «پیکربندی نشده» و کاربر
        # می‌فهمد چرا. مخفی‌کردنشان فقط پرسش «چرا جواب نمی‌دهد؟» می‌سازد.
        toolset = CompositeToolset(
            market_tools,
            OmniRouteToolset(
                provider_factory=lambda: self._omniroute_provider(),
                base_url=str(
                    self.settings.get("ai.base_url", "") or OMNIROUTE_DEFAULT_BASE_URL
                ),
            ),
        )
        self._ai_manager = manager
        self._ai_toolset = toolset
        self._ai_analyst = AIAnalyst(
            manager,
            toolset,
            risk_parameters=self.risk_parameters(),
            preferred_provider=provider_type,
        )
        logger.info("AI analyst created with provider '%s'", provider_type)
        return self._ai_analyst

    def _register_fallback_providers(self, manager: Any, *, skip: str) -> None:
        """
        ثبت سرویس‌های جایگزین برای زنجیرهٔ fallback.

        فقط سرویسی ثبت می‌شود که قابل استفاده باشد: یا کلید ذخیره‌شده
        دارد، یا اصلاً کلید نمی‌خواهد (مثل Ollama محلی). اولویت‌ها طوری
        چیده می‌شوند که سرویس انتخابی کاربر همیشه اول بماند.
        """
        if not self.settings.get_bool("ai.fallback_enabled", True):
            return

        from ai.providers import AIProviderConfig
        from ai.providers.catalog import PROVIDER_PRESETS

        priority = 10
        for preset in PROVIDER_PRESETS:
            if preset.key == skip or preset.key == "custom":
                continue

            api_key = self._ai_api_key(preset.key)
            if preset.requires_key and not api_key:
                continue

            try:
                config = AIProviderConfig(
                    name=preset.key,
                    base_url=preset.base_url,
                    model=(preset.suggested_models[0] if preset.suggested_models else ""),
                    temperature=float(self.settings.get("ai.temperature", 0.2)),
                    max_tokens=int(self.settings.get_int("ai.max_tokens", 1600)),
                    timeout=int(self.settings.get_int("ai.timeout", 90)),
                    requires_api_key=preset.requires_key,
                    priority=priority,
                )
                manager.register_from_type(preset.provider_type, config, api_key)
                priority += 10
            except Exception:  # noqa: BLE001 - یک سرویس خراب نباید بقیه را ببندد
                logger.exception("Could not register fallback provider %s", preset.key)

    @staticmethod
    def _resolve_base_url(configured: str, default_url: str, provider_type: str) -> str:
        """
        انتخاب نشانی درست سرویس هوش مصنوعی.

        نشانی ذخیره‌شده ممکن است مربوط به سرویس قبلی باشد. اگر سرویس
        فعلی نشانی پیش‌فرض ابری دارد ولی مقدار ذخیره‌شده به localhost
        اشاره می‌کند (یا برعکس)، مقدار ذخیره‌شده نامربوط است و باید کنار
        گذاشته شود.
        """
        if not configured:
            return default_url
        if not default_url:
            return configured

        def _is_local(url: str) -> bool:
            lowered = url.lower()
            return any(host in lowered for host in ("127.0.0.1", "localhost", "::1", "0.0.0.0"))

        # سرویس ابری با نشانی محلی جور درنمی‌آید و بالعکس
        if _is_local(configured) != _is_local(default_url):
            logger.info(
                "Ignoring stored base URL for provider '%s'; it belongs to a different service",
                provider_type,
            )
            return default_url
        return configured

    def _omniroute_provider(self) -> Any:
        """
        ارائه‌دهندهٔ دروازهٔ OmniRoute برای ابزارهای عامل.

        اگر دروازه سرویس فعال باشد، همان نمونهٔ ثبت‌شده در مدیر برگردانده
        می‌شود تا کلاینت HTTP دوباره ساخته نشود. در غیر این صورت یک نمونهٔ
        سبک با تنظیمات ذخیره‌شده ساخته می‌شود، چون کاربر ممکن است سرویس
        دیگری را فعال کرده باشد ولی هنوز بخواهد وضعیت دروازه را بپرسد.

        بازگشتی `None` یعنی «دروازه پیکربندی نشده»؛ ابزار همین را به کاربر
        می‌گوید و چیزی از خودش نمی‌سازد.
        """
        from ai.providers.base import AIProviderConfig
        from ai.providers.omniroute_provider import DEFAULT_BASE_URL, OmniRouteProvider

        manager = self._ai_manager
        if manager is not None:
            existing = manager.get("omniroute")
            if isinstance(existing, OmniRouteProvider):
                return existing

        api_key = self._ai_api_key("omniroute")
        configured_url = str(self.settings.get("ai.omniroute.base_url", "") or "").strip()
        if not configured_url and str(self.settings.get("ai.provider", "")) == "omniroute":
            configured_url = str(self.settings.get("ai.base_url", "") or "").strip()

        config = AIProviderConfig(
            name="omniroute",
            base_url=configured_url or DEFAULT_BASE_URL,
            model=str(self.settings.get("ai.model", "") or ""),
            timeout=int(self.settings.get_int("ai.timeout", 90)),
            requires_api_key=False,
        )
        return OmniRouteProvider(config, api_key)

    def _provider_extra(self, implementation: str) -> dict[str, Any]:
        """
        تنظیمات ویژهٔ هر نوع ارائه‌دهنده.

        فعلاً فقط مدل محلی به آن نیاز دارد: کاربری که کارت گرافیکش از
        حافظهٔ سیستمش ضعیف‌تر است، می‌تواند سقف پنجرهٔ متن را دستی
        پایین بیاورد. صفر یعنی «خودت از حافظهٔ دستگاه تشخیص بده».
        """
        if implementation != "ollama":
            return {}
        ceiling = int(self.settings.get_int("ai.ollama_max_context", 0))
        return {"max_context": ceiling} if ceiling > 0 else {}

    def _ai_api_key(self, provider_type: str) -> str | None:
        """
        خواندن کلید سرویس هوش مصنوعی.

        کلید هر سرویس جداگانه ذخیره می‌شود تا کاربر بتواند چند سرویس را
        هم‌زمان پیکربندی کند و با تعویض سرویس، کلید درست خودکار بیاید.
        قالب قدیمی (`ai.api_key`) هم پشتیبانی می‌شود تا تنظیمات کاربران
        فعلی از بین نرود.
        """
        for key in (f"ai.{provider_type}.api_key", "ai.api_key"):
            value = self.secrets.get(key)
            if value:
                return value
        return None

    def exchange_credentials(self, exchange: str | None = None) -> tuple[str | None, str | None]:
        """
        خواندن کلید و رمز صرافی از حافظه.

        با تعویض صرافی، کلید همان صرافی خودکار برگردانده می‌شود.
        """
        name = exchange or self.settings.active_exchange
        api_key = self.secrets.get(f"exchange.{name}.api_key") or self.secrets.get("exchange.api_key")
        api_secret = (
            self.secrets.get(f"exchange.{name}.api_secret")
            or self.secrets.get("exchange.api_secret")
        )
        return api_key, api_secret


    def ai_speed_limits(self) -> Any:
        """سقف سرعت هوش مصنوعی. متعادل عددهای ذخیره‌شده را بازنویسی نمی‌کند."""
        from ai.speed_profile import limits_for

        return limits_for(self.settings)

    def signal_ai_timeout(self) -> float:
        """مهلت سیگنال، با رعایت پروفایل سرعت."""
        from ai.speed_profile import signal_timeout_seconds

        return signal_timeout_seconds(self.settings)

    def autonomous_agent(self) -> Any:
        """
        ساخت تنبل عامل خودمختار.

        عامل روی همان مدیر ارائه‌دهنده و مجموعه ابزار تحلیل‌گر سوار
        می‌شود؛ تفاوتش این است که خودش تصمیم می‌گیرد چه داده‌ای لازم
        دارد و چند مرحله جلو برود.
        """
        if not self.ai_enabled() or self.market is None:
            return None
        if self._autonomous_agent is not None:
            return self._autonomous_agent

        # ساخت تحلیل‌گر، مدیر ارائه‌دهنده و ابزارها را هم آماده می‌کند
        if self.ai_analyst() is None:
            return None

        from ai.agent import AutonomousAgent

        # سرویس انتخابی کاربر باید اول زنجیره باشد؛ وگرنه تولید سیگنال
        # هر بار اول سراغ سرویس‌های محلیِ خاموش می‌رود و کاربر معطل
        # شکست آن‌ها می‌ماند (همان «سیگنال با هوش مصنوعی خیلی کند است»).
        limits = self.ai_speed_limits()
        self._autonomous_agent = AutonomousAgent(
            self._ai_manager,
            self._ai_toolset,
            self.risk_parameters(),
            max_iterations=limits.agent_steps,
            timeout_seconds=float(limits.agent_timeout),
            preferred_provider=str(self.settings.get("ai.provider", "") or "") or None,
        )
        logger.info("Autonomous agent created")
        return self._autonomous_agent

    def chat_agent(self) -> Any:
        """
        ساخت تنبل دستیار گفتگو.

        همان مدیر ارائه‌دهنده و ابزارهای تحلیل‌گر را به اشتراک می‌گذارد، پس
        هر تنظیمی که برای تحلیل اعمال شود، برای چت هم اعمال می‌شود.

        برخلاف عامل خودمختار، این شیء **حافظه گفتگو** دارد؛ به همین دلیل
        باید یک نمونه پایدار بماند و با هر پیام دوباره ساخته نشود.
        """
        if not self.ai_enabled() or self.market is None:
            return None
        if self._chat_agent is not None:
            return self._chat_agent

        # ساخت تحلیل‌گر، مدیر ارائه‌دهنده و ابزارها را هم آماده می‌کند
        if self.ai_analyst() is None:
            return None

        from ai.agent import ChatAgent

        # سرویس انتخابی کاربر باید **اول** زنجیره باشد. بدون این، چت
        # هر بار از سرویس‌های محلی خاموش شروع می‌کرد و کاربر چند ثانیه
        # منتظر شکست آن‌ها می‌ماند تا نوبت به سرویس واقعی برسد.
        limits = self.ai_speed_limits()
        self._chat_agent = ChatAgent(
            self._ai_manager,
            self._ai_toolset,
            self.risk_parameters(),
            max_tool_calls=limits.chat_tools,
            timeout_seconds=float(limits.chat_timeout),
            preferred_provider=str(self.settings.get("ai.provider", "") or "") or None,
        )
        logger.info("Chat agent created")
        return self._chat_agent

    def reset_ai(self) -> None:
        """
        دور انداختن نمونه‌های هوش مصنوعی پس از تغییر تنظیمات.

        بدون این، تغییر سرویس یا مدل در تنظیمات تا اجرای بعدی برنامه
        اثری نداشت.

        نکته: حافظه گفتگوی چت هم پاک می‌شود، چون ادامه دادن یک گفتگو با
        مدلی که وسط راه عوض شده، پاسخ‌های ناسازگار می‌دهد.
        """
        self._ai_analyst = None
        self._ai_manager = None
        self._ai_toolset = None
        self._autonomous_agent = None
        self._chat_agent = None
        logger.info("AI components reset; they will be rebuilt on next use")

    async def list_ai_models(self, provider_type: str | None = None) -> list[str]:
        """
        پرسیدن فهرست زندهٔ مدل‌ها از سرویس انتخاب‌شده.

        اگر سرویس پاسخ ندهد، فهرست خالی برمی‌گردد و فراخواننده باید به
        مدل‌های پیشنهادی کاتالوگ بازگردد — نه اینکه خطا نشان دهد.
        """
        from ai.providers import AIProviderConfig, AIProviderManager
        from ai.providers.catalog import get_preset

        name = provider_type or str(self.settings.get("ai.provider", "ollama"))
        preset = get_preset(name)
        implementation = preset.provider_type if preset is not None else "openai_compatible"
        requires_key = preset.requires_key if preset is not None else True

        config = AIProviderConfig(
            name=name,
            base_url=str(self.settings.get("ai.base_url", "") or (preset.base_url if preset else "")),
            model=str(self.settings.get("ai.model", "")),
            requires_api_key=requires_key,
        )
        manager = AIProviderManager(self.events, fallback_enabled=False)
        # کلید ذخیره‌شده همیشه فرستاده می‌شود، حتی وقتی سرویس آن را
        # «لازم» ندارد: دروازه‌هایی مثل OmniRoute کلید را اختیاری می‌گیرند
        # ولی اگر کاربر احراز هویت را روشن کرده باشد بدون کلید ۴۰۱ می‌دهند.
        provider = manager.register_from_type(implementation, config, self._ai_api_key(name))
        try:
            return await provider.list_models()
        finally:
            await provider.close()

    # ------------------------------------------------------------------
    # عملیات سطح بالا
    # ------------------------------------------------------------------
    async def generate_signal(self, symbol: str, timeframes: list[str] | None = None) -> Any:
        """
        تولید سیگنال و ذخیره آن.

        حالت تولید از تنظیم `ai.signal_mode` خوانده می‌شود:

            hybrid  — موتور ریاضی تصمیم می‌گیرد و هوش مصنوعی تفسیر
                      می‌نویسد. پیش‌فرض و سریع‌ترین حالتِ همراهِ هوش مصنوعی.
            ai_only — هوش مصنوعی خودش جهت را تعیین می‌کند. اگر نتواند،
                      به‌جای دست خالی، نتیجهٔ موتور ریاضی برگردانده می‌شود.
            engine  — بدون هوش مصنوعی؛ سریع‌ترین حالت.

        **تضمین اصلی:** این متد همیشه یک سیگنال برمی‌گرداند. کاربر گزارش
        داده بود «سیگنال تولید نمی‌شود»؛ علتش وابستگی کامل به سرویس هوش
        مصنوعی بود. حالا نبود یا کندی هوش مصنوعی، تولید سیگنال را متوقف
        نمی‌کند.
        """
        if self.signals is None:
            raise RuntimeError("Application.start() must be called before generating signals")

        frames = timeframes or self.settings.analysis_timeframes
        mode = str(self.settings.get("ai.signal_mode", "hybrid") or "hybrid").lower()
        ai_ready = self.ai_enabled() and mode != "engine"

        signal = await self.signals.generate(symbol, frames)

        ai_decided = False
        if ai_ready and mode == "ai_only":
            signal = await self._apply_ai_decision(signal, frames)
            # `TradingSignal` صفت `source` ندارد و `__slots__` دارد، پس
            # نوشتن روی آن استثنا می‌دهد. نشانهٔ درستِ «مدل تصمیم گرفت»
            # پرشدن `ai_model` است که فقط در همان مسیر مقدار می‌گیرد.
            ai_decided = bool(signal.ai_model)

        # در حالت «کاملاً هوش مصنوعی»، تصمیم خودش «دلیل» دارد و یک
        # درخواست دومِ روایت، فقط همان را با کلمات دیگر تکرار می‌کند.
        #
        # کاربر از کندی سیگنال‌گیری دستی شکایت کرد. علتش همین بود: در
        # این حالت تا **چهار** درخواست پشت سر هم به مدل می‌رفت (یک
        # تصمیم + تا دو ترمیم + یک روایت)، هر کدام با سقف زمان جدا. روی
        # یک مدل محلی که هر پاسخش ده‌ها ثانیه طول می‌کشد، انتظار کاربر
        # چند برابر می‌شد بی‌آنکه اطلاعات تازه‌ای به دست بیاورد.
        #
        # حالا وقتی هوش مصنوعی خودش تصمیم گرفته، از `reason` او متن
        # می‌سازیم و درخواست اضافه نمی‌فرستیم.
        narrative_wanted = ai_ready and bool(self.settings.get("ai.narrative_enabled", True))
        if narrative_wanted and not ai_decided:
            signal = await self._write_narrative(signal)
        elif ai_decided and not signal.analysis_text:
            from ai.agent.narrative import NarrativeWriter

            text, _ = await NarrativeWriter(None).write(signal, {}, prefer_ai=False)
            # دلیل خودِ مدل مقدم است؛ متن قالبی فقط جزئیات را تکمیل می‌کند.
            signal.analysis_text = f"{signal.reason}\n\n{text}".strip() if signal.reason else text
            signal.analysis_source = "ai"
        elif not signal.analysis_text:
            # حتی بدون هوش مصنوعی، سیگنال بدون تحلیل نوشتاری نمی‌ماند
            from ai.agent.narrative import NarrativeWriter

            text, source = await NarrativeWriter(None).write(signal, {}, prefer_ai=False)
            signal.analysis_text = text
            signal.analysis_source = source

        signal_id = self.signal_repository.save_signal(signal, source="app")
        self._track_outcome(signal_id)
        # شناسهٔ ذخیره‌شده را نگه می‌داریم تا رابط کاربری بتواند بعداً
        # روی همین سیگنال تحلیل دوباره بگیرد. `TradingSignal` اسلات‌محور
        # است، پس مقدار را کنار نمونه نگه می‌داریم نه روی خودش.
        self._last_signal_id = int(signal_id or 0)
        return signal

    async def scan_market(
        self,
        symbols: list[str] | None = None,
        timeframes: list[str] | None = None,
        *,
        limit: int | None = None,
        min_confidence: int = 0,
        include_wait: bool = False,
        on_progress: Any = None,
        universe: str = "top",
        min_turnover: float = 0.0,
        smart_filter: bool | None = None,
        on_signal: Any = None,
        cpu_duty: float | None = None,
    ) -> Any:
        """
        پویش کل بازار و بازگرداندن سیگنال‌ها به ترتیب ضریب اطمینان.

        نسخهٔ ۲.۴.۰: `universe="all"` همهٔ نمادهای صرافی را (با پالایش هوشمند
        اختیاری و ترتیب نقدشوندگی/نوسان) پویش می‌کند؛ `on_signal` هر سیگنال را
        همان لحظه برای نمایش زنده گزارش می‌دهد.

        این متد **عمداً هوش مصنوعی را صدا نمی‌زند**؛ فقط موتور ریاضی.
        کاربر خواست پویش گروهی توکن نسوزاند و تحلیل هوش مصنوعی بعداً و
        فقط روی نماد انتخابی اجرا شود (`generate_signal` یا
        `analyze_scanned_signal`).

        سیگنال‌های یافته‌شده در پایگاه داده ذخیره می‌شوند تا در سابقه
        بمانند و بعداً بشود جزئیاتشان را باز کرد.
        """
        if self.signals is None or self.market is None:
            raise RuntimeError("Application.start() must be called before scanning")

        from signals.scanner import MarketScanner

        scanner = MarketScanner(
            self.market,
            self.signals,
            concurrency=self.settings.get_int("performance.parallel_requests", 4) or 4,
        )
        filters = None
        if universe == "all" or smart_filter is not None or min_turnover:
            from signals.scan_universe import UniverseFilter

            filters = UniverseFilter.create(
                min_turnover=min_turnover,
                smart=True if smart_filter is None else bool(smart_filter),
            )
        result = await scanner.scan(
            symbols,
            timeframes or self.settings.analysis_timeframes,
            limit=limit,
            min_confidence=min_confidence,
            include_wait=include_wait,
            on_progress=on_progress,
            universe=universe,
            filters=filters,
            on_signal=on_signal,
            **({"cpu_duty": cpu_duty} if cpu_duty is not None else {}),
        )

        # ذخیرهٔ سیگنال‌های جهت‌دار. «انتظار» ذخیره نمی‌شود وگرنه سابقه
        # با ده‌ها ردیف بی‌اثر پر می‌شود و پیداکردن سیگنال واقعی سخت
        # می‌شود.
        for index, signal in enumerate(result.signals):
            if signal.direction is SignalDirection.WAIT:
                continue
            if index and index % 20 == 0:
                # ذخیرهٔ صدها سیگنال پویش کل بازار نباید حلقهٔ شبکه را
                # (وب‌سوکت، معاملهٔ خودکار) یک‌نفس قفل کند (۲.۴.۱).
                await asyncio.sleep(0)
            if not self._should_store_scanned(signal):
                continue
            try:
                signal_id = self.signal_repository.save_signal(signal, source="scan")
                self._track_outcome(signal_id)
            except Exception:  # noqa: BLE001 - ذخیره‌نشدن یکی، بقیه را نکشد
                logger.debug("Could not store scanned signal for %s", signal.symbol,
                             exc_info=True)
        return result

    # ------------------------------------------------------------------
    # پیگیری نتیجهٔ سیگنال‌ها
    # ------------------------------------------------------------------
    async def score_forecasts(self, *, days: int = 14, limit: int = 300) -> dict[str, Any]:
        """
        دفترچهٔ نتیجهٔ پیش‌بینی‌ها: بازه‌های اعلام‌شده چقدر درست بودند؟

        چرا لازم است: بازه‌ها با اطمینان ۸۰٪ ساخته می‌شوند. اگر هرگز
        سنجیده نشوند، این عدد فقط یک ادعاست. کاربر صریح گفت «اگر
        می‌گویی ۹۰٪، نباید ضرر بدهد» — تنها راه اثباتش همین است.

        قیمت واقعیِ هر افق از کندل‌های تاریخی گرفته می‌شود، نه از قیمت
        فعلی: پیش‌بینیِ «یک ساعت بعد» باید با قیمت همان یک ساعت بعد
        سنجیده شود، نه با قیمت امروز.

        بازگشتی: خروجی `ScorecardReport.as_dict()`.
        """
        from signals.scorecard import HORIZON_SECONDS, build_report, horizon_is_due

        since = datetime.now(UTC) - timedelta(days=int(days))
        records = self.signal_repository.search(limit=int(limit))

        signals: list[dict[str, Any]] = []
        for record in records:
            created = getattr(record, "created_at", None)
            if not isinstance(created, datetime):
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if created < since:
                continue
            horizons = getattr(record, "forecast", None) or []
            if not horizons:
                continue
            signals.append(
                {
                    "symbol": record.symbol,
                    "created_at": created,
                    "forecast": horizons,
                }
            )

        if not signals:
            return build_report([], {}, ).as_dict()

        # قیمت واقعیِ هر (نماد، افق) از کندل‌های تاریخی.
        #
        # برای هر نماد یک بار کندل می‌گیریم و همهٔ افق‌هایش را از همان
        # مجموعه می‌خوانیم؛ گرفتن جداگانه برای هر افق یعنی ده‌ها درخواست
        # اضافه و برخورد با محدودیت نرخ صرافی.
        price_lookup: dict[tuple[str, str], float] = {}
        now = datetime.now(UTC)
        for symbol in {item["symbol"] for item in signals}:
            try:
                candles = await self.market.get_candles(symbol, "1h", limit=720)
            except Exception:  # noqa: BLE001
                logger.debug("Scorecard: no candles for %s", symbol, exc_info=True)
                continue
            if not candles:
                continue
            series = sorted(
                ((float(c.timestamp), float(c.close)) for c in candles),
                key=lambda pair: pair[0],
            )
            for item in signals:
                if item["symbol"] != symbol:
                    continue
                created = item["created_at"]
                for horizon, seconds in HORIZON_SECONDS.items():
                    if not horizon_is_due(created, horizon, now=now):
                        continue
                    target = created.timestamp() + seconds
                    # نزدیک‌ترین کندلِ **بعد از** لحظهٔ هدف
                    match = next((price for ts, price in series if ts >= target), None)
                    if match is not None:
                        price_lookup[(symbol, horizon)] = match

        return build_report(signals, price_lookup, now=now).as_dict()

    def _track_outcome(self, signal_id: int) -> None:
        """
        ثبت سیگنال تازه برای پیگیری نتیجه.

        خطا اینجا هرگز نباید تولید سیگنال را بشکند؛ پیگیری یک قابلیت
        جانبی است و سیگنال ارزش خودش را دارد.
        """
        if not signal_id:
            return
        if not bool(self.settings.get("signals.track_outcomes", True)):
            return
        try:
            self.outcome_repository.track_signal(int(signal_id))
        except Exception:  # noqa: BLE001
            logger.debug("Could not start outcome tracking for signal %s", signal_id,
                         exc_info=True)

    async def refresh_outcomes(self, *, limit: int | None = None) -> dict[str, Any]:
        """
        یک دور بررسی قیمت برای همهٔ سیگنال‌های باز.

        قیمت‌ها **یک‌جا** گرفته می‌شوند (`get_all_tickers`) نه نماد به
        نماد: سی سیگنال باز یعنی سی درخواست جدا و برخورد با محدودیت نرخ
        صرافی. یک درخواست برای همه، هم سریع‌تر است هم مؤدبانه‌تر.

        بازگشتی: شمارش `checked/closed/wins/losses/expired`.
        """
        from signals.outcome_tracker import (
            CLOSED_STATUSES,
            STATUS_EXPIRED,
            STATUS_STOP,
            STATUS_TARGET,
            update_outcome,
        )

        report = {"checked": 0, "closed": 0, "wins": 0, "losses": 0, "expired": 0}
        if self.market is None:
            return report

        batch = limit or self.settings.get_int("signals.track_batch", 60) or 60
        records = self.outcome_repository.open_outcomes(limit=batch)
        if not records:
            return report

        prices = await self._outcome_prices({record.symbol for record in records})
        if not prices:
            return report

        for record in records:
            window = prices.get(record.symbol)
            if window is None:
                continue
            state = self.outcome_repository.to_state(record)
            update_outcome(state, window)
            self.outcome_repository.apply_state(int(record.id), state)
            report["checked"] += 1
            if state.status in CLOSED_STATUSES:
                report["closed"] += 1
                if state.status == STATUS_TARGET:
                    report["wins"] += 1
                elif state.status == STATUS_STOP:
                    report["losses"] += 1
                elif state.status == STATUS_EXPIRED:
                    report["expired"] += 1

        if report["closed"]:
            logger.info(
                "Outcome tracking closed %s signal(s): %s win / %s loss",
                report["closed"], report["wins"], report["losses"],
            )
        return report

    async def review_closed_signals(self, *, limit: int = 3) -> dict[str, Any]:
        """
        بازبینی هوش مصنوعی روی سیگنال‌های بسته‌شدهٔ بازبینی‌نشده.

        چرا در لایهٔ برنامه و نه در کنترلر؟
            چون این یک قابلیت دامنه است نه یک رفتار رابط کاربری: هم
            زمان‌بند پس‌زمینه به آن نیاز دارد و هم دکمهٔ «بازبینی
            دوباره» در صفحهٔ سابقه.

        دسته‌ای کوچک (پیش‌فرض سه‌تا) عمدی است: مدل محلی روی همان دستگاه
        کاربر اجرا می‌شود و بازبینی بیست سیگنال پشت سر هم، برنامه را
        برای دقایقی کند می‌کند. کار عجله‌ای ندارد.

        هرگز استثنا پرتاب نمی‌کند؛ نبود هوش مصنوعی حالتی کاملاً عادی است.
        """
        report: dict[str, Any] = {"reviewed": 0, "failed": 0, "skipped": 0}

        if not self.settings.get_bool("ai.auto_review", True):
            report["skipped"] = 1
            return report

        analyst = self.ai_analyst()
        if analyst is None or self._ai_manager is None:
            report["skipped"] = 1
            return report

        pairs = self.review_repository.pending_reviews(limit=int(limit))
        if not pairs:
            return report

        from ai.agent.reviewer import SignalReviewer
        from ai.prompts import PromptManager

        reviewer = SignalReviewer(
            self._ai_manager,
            PromptManager(),
            language=str(self.settings.get("ai.narrative_language", "fa")),
            preferred_provider=str(self.settings.get("ai.provider", "") or ""),
        )

        for result in await reviewer.review_batch(pairs, limit=int(limit)):
            if not result.ok:
                report["failed"] += 1
                continue
            outcome_status = next(
                (
                    str(outcome.status)
                    for signal, outcome in pairs
                    if int(signal.id) == result.signal_id
                ),
                "",
            )
            self.review_repository.save(
                result.signal_id,
                outcome_status=outcome_status,
                verdict=result.verdict,
                lesson=result.lesson,
                review_text=result.review,
                ai_provider=result.provider,
                ai_model=result.model,
            )
            report["reviewed"] += 1

        if report["reviewed"]:
            logger.info("AI reviewed %s closed signal(s)", report["reviewed"])
        return report

    async def _outcome_prices(self, symbols: set[str]) -> dict[str, Any]:
        """
        گرفتن بازهٔ قیمتی نمادهای تحت پیگیری.

        ترجیح با فهرست یک‌جای تیکرهاست چون `high_24h`/`low_24h` را هم
        می‌دهد و همان چیزی است که برای تشخیص «آیا در این فاصله حد ضرر
        لمس شد؟» لازم داریم. اگر آن درخواست شکست خورد، به قیمت لحظه‌ای
        تک‌تک نمادها برمی‌گردیم — دقتش کمتر است ولی پیگیری متوقف نمی‌شود.
        """
        from signals.outcome_tracker import PriceWindow

        windows: dict[str, Any] = {}
        try:
            tickers = await self.market.get_all_tickers()
        except Exception:  # noqa: BLE001
            logger.debug("Bulk ticker fetch failed during outcome tracking", exc_info=True)
            tickers = []

        for ticker in tickers:
            if ticker.symbol in symbols and ticker.last_price > 0:
                windows[ticker.symbol] = PriceWindow(
                    last=float(ticker.last_price),
                    high=float(ticker.high_24h or 0),
                    low=float(ticker.low_24h or 0),
                )

        missing = symbols - set(windows)
        for symbol in list(missing)[:20]:
            try:
                price = await self.market.get_current_price(symbol)
            except Exception:  # noqa: BLE001
                continue
            if price > 0:
                windows[symbol] = PriceWindow(last=float(price))
        return windows

    async def analyze_scanned_signal(self, signal: Any) -> Any:
        """
        تحلیل نوشتاری هوش مصنوعی روی **یک** سیگنالِ از پیش پویش‌شده.

        مکمل `scan_market` است: پویش ارزان و بی‌هوش‌مصنوعی انجام می‌شود،
        بعد کاربر هر نمادی را که خواست برای تحلیل عمیق انتخاب می‌کند.
        اگر هوش مصنوعی در دسترس نباشد، متن الگویی نوشته می‌شود تا کاربر
        دست خالی نماند.
        """
        if not self.ai_enabled():
            from ai.agent.narrative import NarrativeWriter

            text, source = await NarrativeWriter(None).write(signal, {}, prefer_ai=False)
            signal.analysis_text = text
            signal.analysis_source = source
            return signal

        signal = await self._write_narrative(signal)
        try:
            self.signal_repository.save_signal(signal, source="scan-ai")
        except Exception:  # noqa: BLE001
            logger.debug("Could not store AI analysis for %s", signal.symbol, exc_info=True)
        return signal

    async def _apply_ai_decision(self, signal: Any, frames: list[str]) -> Any:
        """
        حالت «کاملاً هوش مصنوعی»: تصمیم جهت را به ایجنت می‌سپارد.

        اگر ایجنت پاسخ معتبری ندهد یا از سقف زمان بگذرد، سیگنال موتور
        ریاضی دست‌نخورده برمی‌گردد. این عمدی است تا کاربر هیچ‌وقت بدون
        سیگنال نماند.
        """
        analyst = self.ai_analyst()
        if analyst is None:
            return signal
        timeout = self.signal_ai_timeout()
        try:
            from ai.agent.analyst import AnalysisRequest

            decision = await asyncio.wait_for(
                analyst.generate_signal(AnalysisRequest(symbol=signal.symbol, timeframes=list(frames))),
                timeout=timeout,
            )
        except TimeoutError:
            logger.warning("AI-only signal timed out for %s; engine result kept", signal.symbol)
            return signal
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI-only signal failed for %s: %s", signal.symbol, exc.__class__.__name__)
            return signal

        if decision is None:
            return signal

        # خروجی تحلیل‌گر در `structured` است، نه روی خود شیء.
        #
        # اشکالی که کاربر گزارش کرد («با هوش مصنوعی فعال، همیشه انتظار»)
        # دقیقاً همین‌جا بود: کد قبلی `decision.direction` را می‌خواند،
        # ولی `AnalysisResult` اصلاً چنین صفتی ندارد. `getattr(..., None)`
        # همیشه `None` برمی‌گرداند، شرط هرگز برقرار نمی‌شد و **کل پاسخ
        # هوش مصنوعی دور ریخته می‌شد**. نتیجه: هرچه مدل می‌گفت، کاربر
        # همان WAIT موتور ریاضی را می‌دید — و چون تحلیل متنی درست نوشته
        # می‌شد، هیچ نشانه‌ای از خرابی دیده نمی‌شد.
        #
        # `getattr` با مقدار پیش‌فرض، خطا را بی‌صدا می‌کند. اینجا عمداً
        # از کلید صریح استفاده می‌شود تا اگر روزی قرارداد عوض شد،
        # آزمون‌ها بشکنند نه رفتار کاربر.
        data = getattr(decision, "structured", None) or {}
        raw_direction = str(data.get("signal", "")).upper().strip()
        if raw_direction not in {d.value for d in SignalDirection}:
            logger.warning(
                "AI-only mode: no usable direction for %s (status=%s); engine result kept",
                signal.symbol,
                getattr(getattr(decision, "status", None), "value", "?"),
            )
            return signal

        signal.direction = SignalDirection(raw_direction)
        signal.ai_provider = str(getattr(decision, "provider", "") or "")
        signal.ai_model = str(getattr(decision, "model", "") or "")

        entry = data.get("entry_zone") or []
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            signal.entry_min = _as_float(entry[0], signal.entry_min)
            signal.entry_max = _as_float(entry[1], signal.entry_max)

        signal.stop_loss = _as_float(data.get("stop_loss"), signal.stop_loss)

        targets = data.get("take_profits")
        if isinstance(targets, (list, tuple)) and targets:
            converted = [_as_float(t, None) for t in targets]
            signal.take_profits = [t for t in converted if t is not None]

        # `confidence` می‌تواند صفر باشد و صفر مقدار معتبری است؛ پس
        # بررسی «اگر مقدار درست بود» (که صفر را رد می‌کند) اشتباه است.
        confidence = data.get("confidence")
        if confidence is not None:
            try:
                signal.confidence = max(0, min(100, int(round(float(confidence)))))
            except (TypeError, ValueError):
                pass

        leverage = data.get("leverage")
        if leverage is not None:
            try:
                signal.leverage = max(1, int(float(leverage)))
            except (TypeError, ValueError):
                pass

        for key in ("reason", "invalidation"):
            value = str(data.get(key, "") or "").strip()
            if value:
                setattr(signal, key, value)

        for key, enum_type in (("trend", TrendDirection), ("market_structure", MarketStructureType)):
            raw = str(data.get(key, "") or "").upper().strip()
            if raw:
                try:
                    setattr(signal, key, enum_type(raw))
                except ValueError:
                    pass

        logger.info(
            "AI-only mode: %s decided %s (confidence %s) for %s",
            signal.ai_provider or "ai",
            signal.direction.value,
            signal.confidence,
            signal.symbol,
        )
        return signal

    async def _write_narrative(self, signal: Any) -> Any:
        """افزودن تحلیل نوشتاری فارسی به سیگنال."""
        from ai.agent.narrative import NarrativeWriter

        timeout = self.signal_ai_timeout()
        # ساخت تحلیل‌گر، مدیر ارائه‌دهنده‌ها را هم می‌سازد
        if self._ai_manager is None:
            self.ai_analyst()
        writer = NarrativeWriter(
            self._ai_manager,
            timeout_seconds=timeout,
            preferred_provider=str(self.settings.get("ai.provider", "") or "") or None,
        )
        market_data: dict[str, Any] = {}
        text, source = await writer.write(signal, market_data, prefer_ai=True)
        signal.analysis_text = text
        signal.analysis_source = source
        if source == "ai":
            signal.ai_provider = str(self.settings.get("ai.provider", "") or "")
            signal.ai_model = str(self.settings.get("ai.model", "") or "")
        return signal

    def create_backup(self, note: str = "") -> Any:
        """ساخت پشتیبان و ثبت آن در سابقه."""
        info = self.backup.create(backup_type="manual", note=note)
        self.backup_repository.record_backup(
            str(info.path), info.size_bytes, backup_type=info.backup_type, note=note
        )
        return info
