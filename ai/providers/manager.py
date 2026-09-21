"""
مدیر ارائه‌دهندگان هوش مصنوعی و زنجیره جایگزینی (Fallback).

چرا وجود دارد؟
    طبق بند ۱۹ سند پروژه، اگر ارائه‌دهنده اصلی در دسترس نباشد، سیستم باید
    خودکار سراغ گزینه بعدی برود:

        Primary AI → Failed → Fallback AI → Analysis

    ترتیب تلاش بر اساس عدد priority تعیین می‌شود (کمتر = مهم‌تر) و کاربر
    می‌تواند آن را از تنظیمات تغییر دهد.

ارتباط با ماژول‌های دیگر:
    AIProviderRepository پیکربندی را می‌دهد، SecretStore کلیدها را، و عامل
    هوش مصنوعی فقط متد generate این کلاس را صدا می‌زند.
"""

from __future__ import annotations

from collections.abc import Callable

from ai.providers.base import AIMessage, AIProvider, AIProviderConfig, AIResponse
from ai.providers.ollama_provider import OllamaProvider
from ai.providers.omniroute_provider import OmniRouteProvider
from ai.providers.openai_compatible import OpenAICompatibleProvider
from app.core.events import EventBus, EventType
from app.exceptions import AIProviderError
from app.logging import get_logger

logger = get_logger(__name__)

# نگاشت نوع ارائه‌دهنده به کلاس پیاده‌سازی (الگوی Factory)
PROVIDER_TYPES: dict[str, type[AIProvider]] = {
    "ollama": OllamaProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "omniroute": OmniRouteProvider,
    "custom": OpenAICompatibleProvider,
}


class AIProviderManager:
    """
    نگهدارنده ارائه‌دهندگان فعال و مجری زنجیره جایگزینی.

    نمونه‌سازی:
        manager = AIProviderManager(event_bus)
        manager.register(config, api_key)
        response = await manager.generate(messages)
    """

    def __init__(self, event_bus: EventBus | None = None, *, fallback_enabled: bool = True) -> None:
        self._providers: dict[str, AIProvider] = {}
        self._configs: dict[str, AIProviderConfig] = {}
        self._event_bus = event_bus
        self._fallback_enabled = fallback_enabled
        self._last_used: str | None = None
        self._last_errors: dict[str, str] = {}

    # ------------------------------------------------------------------
    # ثبت و پیکربندی
    # ------------------------------------------------------------------
    def register(self, config: AIProviderConfig, api_key: str | None = None) -> AIProvider:
        """
        ثبت یا به‌روزرسانی یک ارائه‌دهنده.

        اگر نوع ارائه‌دهنده ناشناخته باشد، به پیاده‌سازی سازگار با OpenAI
        بازمی‌گردیم، چون رایج‌ترین قرارداد است.
        """
        provider_class = PROVIDER_TYPES.get(config.extra.get("provider_type", ""), None)
        if provider_class is None:
            provider_class = PROVIDER_TYPES.get(config.name, OpenAICompatibleProvider)

        provider = provider_class(config, api_key)
        self._providers[config.name] = provider
        self._configs[config.name] = config
        logger.info("AI provider registered: %s (model=%s, priority=%d)", config.name, config.model, config.priority)
        return provider

    def register_from_type(
        self, provider_type: str, config: AIProviderConfig, api_key: str | None = None
    ) -> AIProvider:
        """ثبت با تعیین صریح نوع پیاده‌سازی."""
        provider_class = PROVIDER_TYPES.get(provider_type, OpenAICompatibleProvider)
        provider = provider_class(config, api_key)
        self._providers[config.name] = provider
        self._configs[config.name] = config
        logger.info("AI provider registered: %s (type=%s, model=%s)", config.name, provider_type, config.model)
        return provider

    def unregister(self, name: str) -> None:
        """حذف یک ارائه‌دهنده از فهرست فعال."""
        self._providers.pop(name, None)
        self._configs.pop(name, None)

    def get(self, name: str) -> AIProvider | None:
        """دریافت یک ارائه‌دهنده مشخص."""
        return self._providers.get(name)

    def set_api_key(self, name: str, api_key: str) -> None:
        """به‌روزرسانی کلید یک ارائه‌دهنده."""
        provider = self._providers.get(name)
        if provider is not None:
            provider.set_api_key(api_key)

    def set_fallback_enabled(self, enabled: bool) -> None:
        """فعال یا غیرفعال کردن زنجیره جایگزینی."""
        self._fallback_enabled = enabled

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    @property
    def has_providers(self) -> bool:
        """آیا حداقل یک ارائه‌دهنده فعال ثبت شده است؟"""
        return any(config.enabled for config in self._configs.values())

    @property
    def last_used_provider(self) -> str | None:
        """نام آخرین ارائه‌دهنده‌ای که با موفقیت پاسخ داد."""
        return self._last_used

    def ordered_providers(self, preferred: str | None = None) -> list[AIProvider]:
        """
        ساخت زنجیره تلاش.

        ارائه‌دهنده ترجیحی (انتخاب کاربر) همیشه اول قرار می‌گیرد و بقیه بر
        اساس اولویت مرتب می‌شوند.
        """
        enabled = [
            provider
            for name, provider in self._providers.items()
            if self._configs[name].enabled
        ]
        enabled.sort(key=lambda p: self._configs[p.name].priority)

        if preferred and preferred in self._providers and self._configs[preferred].enabled:
            preferred_provider = self._providers[preferred]
            enabled = [preferred_provider] + [p for p in enabled if p.name != preferred]
        return enabled

    def active_provider(self, preferred: str | None = None) -> AIProvider | None:
        """
        ارائه‌دهنده‌ای که درخواست بعدی احتمالاً به او می‌رسد.

        چرا لازم است؟
            لایهٔ تحلیل باید **پیش از ساختن پرامپت** بداند با چه مدلی
            طرف است. مدل محلی روی دستگاه کاربر پنجرهٔ متن محدودی دارد و
            پرامپت باید متناسب با آن ساخته شود؛ مدل ابری چنین
            محدودیتی ندارد. بدون این متد، تحلیل‌گر مجبور بود یک اندازهٔ
            واحد برای همه بفرستد — که برای مدل محلی بزرگ‌تر از توانش
            بود و باعث همان خطای «۵۰۰» می‌شد.

        «احتمالاً» چون اگر اولی شکست بخورد زنجیرهٔ جایگزینی سراغ بعدی
        می‌رود؛ ولی برای بودجه‌بندی، اولین گزینه معیار درستی است.
        """
        chain = self.ordered_providers(preferred)
        return chain[0] if chain else None

    async def check_all(self) -> dict[str, tuple[bool, str]]:
        """
        بررسی وضعیت همه ارائه‌دهندگان (برای صفحه تنظیمات و داشبورد).
        """
        results: dict[str, tuple[bool, str]] = {}
        for name, provider in self._providers.items():
            try:
                results[name] = await provider.is_available()
            except Exception as exc:  # noqa: BLE001 - بررسی وضعیت نباید خطا بدهد
                results[name] = (False, f"{exc.__class__.__name__}")
        return results

    # ------------------------------------------------------------------
    # تولید پاسخ
    # ------------------------------------------------------------------
    async def generate(
        self,
        messages: list[AIMessage],
        *,
        preferred: str | None = None,
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> AIResponse:
        """
        تولید پاسخ با اجرای زنجیره جایگزینی.

        ترتیب کار:
            ۱) تلاش با ارائه‌دهنده ترجیحی
            ۲) در صورت شکست و فعال بودن Fallback، تلاش با بعدی‌ها
            ۳) اگر همه شکست خوردند، خطای جامع با شرح دلیل هر شکست

        شکست یک ارائه‌دهنده لاگ و در وضعیت ثبت می‌شود تا در رابط کاربری
        قابل مشاهده باشد.
        """
        providers = self.ordered_providers(preferred)
        if not providers:
            raise AIProviderError(
                "No enabled AI provider is configured",
                details={"hint": "Enable a provider in Settings → AI"},
            )

        if not self._fallback_enabled:
            providers = providers[:1]

        errors: list[str] = []
        for provider in providers:
            try:
                logger.debug("Trying AI provider: %s", provider.name)
                response = await provider.generate(
                    messages, json_mode=json_mode, temperature=temperature
                )
                if response.is_empty:
                    raise AIProviderError(f"Provider '{provider.name}' returned an empty response")

                self._last_used = provider.name
                self._last_errors.pop(provider.name, None)
                if self._event_bus is not None and len(errors) > 0:
                    # فقط وقتی اطلاع می‌دهیم که واقعاً جابه‌جایی رخ داده باشد
                    self._event_bus.publish(
                        EventType.AI_PROVIDER_CHANGED,
                        {"provider": provider.name, "reason": "fallback"},
                        source="AIProviderManager",
                    )
                logger.info(
                    "AI response from %s (%s) in %.2fs", provider.name, response.model, response.latency_seconds
                )
                return response
            except Exception as exc:  # noqa: BLE001 - باید سراغ ارائه‌دهنده بعدی برویم
                message = getattr(exc, "message", str(exc))
                self._last_errors[provider.name] = message
                errors.append(f"{provider.name}: {exc.__class__.__name__}: {message}")
                logger.warning("AI provider '%s' failed: %s", provider.name, exc.__class__.__name__)
                if self._event_bus is not None:
                    self._event_bus.publish(
                        EventType.AI_ERROR,
                        {"provider": provider.name, "error": message},
                        source="AIProviderManager",
                    )

        # پیام باید بگوید «چه چیزی را کجا درست کنم». فهرست خام نام کلاس
        # استثناء برای کاربر بی‌معنی است، پس خلاصهٔ خوانا هم می‌سازیم.
        summary = "; ".join(
            f"{name}: {reason}" for name, reason in self._last_errors.items()
        ) or "no provider responded"
        raise AIProviderError(
            f"All AI providers failed ({summary})",
            details={"attempts": errors, "tried": [p.name for p in providers]},
        )

    async def stream(
        self,
        messages: list[AIMessage],
        on_chunk: Callable[[str], None],
        *,
        preferred: str | None = None,
        temperature: float | None = None,
    ) -> AIResponse:
        """
        تولید پاسخ جریانی با همان زنجیرهٔ جایگزینی `generate`.

        نکتهٔ ظریف: اگر سرویسی وسط جریان بشکند، ممکن است بخشی از متن را
        از قبل به رابط کاربری داده باشیم. در آن حالت پیش از تلاش با
        سرویس بعدی، `on_reset` صدا زده می‌شود تا آنچه نشان داده شده پاک
        شود؛ وگرنه پاسخ دو سرویس به هم می‌چسبد و متن بی‌معنی می‌شود.
        """
        providers = self.ordered_providers(preferred)
        if not providers:
            raise AIProviderError(
                "No enabled AI provider is configured",
                details={"hint": "Enable a provider in Settings → AI"},
            )

        if not self._fallback_enabled:
            providers = providers[:1]

        errors: list[str] = []
        for provider in providers:
            emitted: list[str] = []

            def collect(chunk: str, _sink: list[str] = emitted) -> None:
                """ثبت تکه‌ها تا در صورت شکست بدانیم چه چیزی نشان داده شده."""
                _sink.append(chunk)
                on_chunk(chunk)

            try:
                logger.debug("Trying AI provider (stream): %s", provider.name)
                response = await provider.stream(
                    messages, collect, temperature=temperature
                )
                if response.is_empty:
                    raise AIProviderError(
                        f"Provider '{provider.name}' returned an empty response"
                    )

                self._last_used = provider.name
                self._last_errors.pop(provider.name, None)
                logger.info(
                    "AI stream from %s (%s) in %.2fs",
                    provider.name,
                    response.model,
                    response.latency_seconds,
                )
                return response
            except Exception as exc:  # noqa: BLE001 - سراغ ارائه‌دهنده بعدی می‌رویم
                message = getattr(exc, "message", str(exc))
                self._last_errors[provider.name] = message
                errors.append(f"{provider.name}: {exc.__class__.__name__}: {message}")
                logger.warning(
                    "AI provider '%s' stream failed: %s", provider.name, exc.__class__.__name__
                )
                if emitted:
                    # متنی نیمه‌کاره روی صفحه مانده؛ باید پاک شود
                    self._reset_stream(on_chunk)

        summary = "; ".join(
            f"{name}: {reason}" for name, reason in self._last_errors.items()
        ) or "no provider responded"
        raise AIProviderError(
            f"All AI providers failed ({summary})",
            details={"attempts": errors, "tried": [p.name for p in providers]},
        )

    @staticmethod
    def _reset_stream(on_chunk: Callable[[str], None]) -> None:
        """
        اعلام «آنچه تا حالا فرستادم را دور بریز» به مصرف‌کننده.

        قرارداد ساده است: رشتهٔ خالی یعنی بازنشانی. مصرف‌کننده‌ای که این
        را نفهمد هم آسیبی نمی‌بیند، چون افزودن رشتهٔ خالی بی‌اثر است.
        """
        try:
            on_chunk("")
        except Exception:  # noqa: BLE001
            logger.debug("Stream reset callback failed")

    @property
    def last_errors(self) -> dict[str, str]:
        """آخرین خطای هر ارائه‌دهنده (برای نمایش در تنظیمات)."""
        return dict(self._last_errors)

    async def close(self) -> None:
        """بستن تمام کلاینت‌های شبکه."""
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception:  # noqa: BLE001
                logger.debug("Closing provider %s failed", provider.name)
