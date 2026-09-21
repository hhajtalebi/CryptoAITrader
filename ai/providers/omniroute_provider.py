"""
ارائه‌دهنده OmniRoute — دروازهٔ چندسرویسی هوش مصنوعی.

OmniRoute چیست؟
    یک «دروازه» (Gateway) است که ده‌ها سرویس هوش مصنوعی را پشت یک نشانی
    سازگار با OpenAI جمع می‌کند. کاربر کلیدهای سرویس‌های مختلفش را یک بار
    داخل OmniRoute می‌گذارد و از آن پس فقط یک نشانی و یک کلید به برنامه
    می‌دهد؛ خود دروازه تصمیم می‌گیرد درخواست به کدام سرویس برود، و اگر
    سهمیهٔ یکی تمام شد خودکار سراغ بعدی می‌رود.

چرا کلاس جدا، وقتی قرارداد همان OpenAI است؟
    قرارداد پایه یکی است ولی چهار تفاوت عملی وجود دارد که بدون آن‌ها
    تجربهٔ کاربر خراب می‌شود:

    ۱. **مدل‌ها پیشوند سرویس دارند** (`if/kimi-k2`, `cc/claude-opus`,
       `gg/gemini-3-pro`). برای نمایش در تنظیمات باید بدانیم پیشوند یعنی
       چه، وگرنه کاربر فهرستی از رشته‌های نامفهوم می‌بیند.
    ۲. **مدل ویژهٔ `auto`** وجود دارد که خود دروازه بهترین گزینهٔ در
       دسترس را انتخاب می‌کند. این گزینه همیشه باید بالای فهرست باشد.
    ۳. **معمولاً روی همین دستگاه اجرا می‌شود** (پیش‌فرض
       `http://localhost:20128/v1`). پس مهلت اتصال باید کوتاه باشد و
       پیام خطا باید بگوید «دروازه را اجرا کنید»، نه «شبکه قطع است».
    ۴. **کلید می‌تواند اختیاری باشد**: تا وقتی `REQUIRE_API_KEY` در
       OmniRoute روشن نشده، نصب تازه بدون هیچ کلیدی جواب می‌دهد.

    سرآیندهای اختصاصی دروازه (`X-Title` و شناسهٔ نشست) هم اینجا افزوده
    می‌شوند تا مصرف این برنامه در داشبورد OmniRoute قابل تفکیک باشد.

نکتهٔ امنیتی: کلید فقط در سرآیند `Authorization` می‌رود، در پایگاه‌داده
رمزنگاری‌شده ذخیره می‌شود و هرگز لاگ یا نمایش داده نمی‌شود.
"""

from __future__ import annotations

from typing import Any

import httpx

from ai.providers.base import AIProviderConfig
from ai.providers.openai_compatible import OpenAICompatibleProvider
from app.logging import get_logger

logger = get_logger(__name__)

#: نشانی پیش‌فرض دروازه روی دستگاه کاربر
DEFAULT_BASE_URL = "http://localhost:20128/v1"

#: مدل ویژه‌ای که انتخاب سرویس را به خود دروازه می‌سپارد
AUTO_MODEL = "auto"

#: نگاشت پیشوند مدل به نام سرویس اصلی.
#: OmniRoute هر سرویس را با یک پیشوند کوتاه صدا می‌زند؛ این جدول فقط برای
#: **نمایش** است و اگر پیشوند تازه‌ای بیاید، همان پیشوند خام نشان داده
#: می‌شود (هیچ مدلی به‌خاطر ناشناس بودن پیشوند حذف نمی‌شود).
PROVIDER_PREFIXES: dict[str, str] = {
    "auto": "خودکار",
    "cc": "Claude Code",
    "cx": "Codex",
    "cxa": "Codex App",
    "gg": "Gemini",
    "gh": "GitHub Copilot",
    "if": "iFlow",
    "qw": "Qwen",
    "glm": "GLM / Zhipu",
    "kimi": "Kimi",
    "minimax": "MiniMax",
    "groq": "Groq",
    "nvidia": "NVIDIA NIM",
    "cerebras": "Cerebras",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "openrouter": "OpenRouter",
    "deepseek": "DeepSeek",
    "mistral": "Mistral",
    "xai": "xAI Grok",
    "ollama": "Ollama",
    "lmstudio": "LM Studio",
    "pollinations": "Pollinations",
    "scaleway": "Scaleway",
    "together": "Together AI",
    "fireworks": "Fireworks",
    "nebius": "Nebius",
    "qianfan": "Baidu Qianfan",
}


def model_vendor(model_id: str) -> str:
    """
    نام خوانای سرویسِ پشت یک شناسهٔ مدل OmniRoute.

    مثال: ``if/kimi-k2-thinking`` ⇒ ``iFlow``. برای پیشوند ناشناخته خودِ
    پیشوند برگردانده می‌شود تا اطلاعات از دست نرود.
    """
    name = str(model_id or "").strip()
    if not name:
        return ""
    if "/" not in name:
        return PROVIDER_PREFIXES.get(name.lower(), "")
    prefix = name.split("/", 1)[0].lower()
    return PROVIDER_PREFIXES.get(prefix, prefix)


class OmniRouteProvider(OpenAICompatibleProvider):
    """
    کلاینت دروازهٔ OmniRoute.

    مسیرها (همان قرارداد OpenAI):
        POST {base_url}/chat/completions
        GET  {base_url}/models

    نمونه‌سازی:
        provider = OmniRouteProvider(config, api_key)
        ok, message = await provider.is_available()
    """

    provider_type = "omniroute"

    def __init__(self, config: AIProviderConfig, api_key: str | None = None) -> None:
        # نشانی خالی یعنی «پیش‌فرض»؛ بدون این، یک پیکربندی ناقص باعث خطای
        # «Base URL is not configured» می‌شد در حالی که مقدار درست معلوم است.
        if not (config.base_url or "").strip():
            config.base_url = DEFAULT_BASE_URL
        super().__init__(config, api_key)
        #: آیا آخرین تلاش برای گرفتن فهرست مدل‌ها موفق بود؟
        self._last_listing_ok = False

    @property
    def last_listing_ok(self) -> bool:
        """
        آیا آخرین فهرست مدل واقعاً از دروازه آمد؟

        لازم است چون کلاس پایه خطای شبکه را می‌بلعد و فهرست خالی برمی‌گرداند.
        بدون این پرچم، «دروازه خاموش است» از «دروازه هیچ مدلی ندارد» قابل
        تشخیص نبود و ابزار به کاربر می‌گفت همه‌چیز مرتب است.
        """
        return self._last_listing_ok

    # ------------------------------------------------------------------
    # سرآیندها
    # ------------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        """
        سرآیندهای درخواست، به‌علاوهٔ شناسهٔ برنامه برای داشبورد OmniRoute.

        `X-Title` باعث می‌شود مصرف این برنامه در گزارش‌های دروازه جدا
        دیده شود. `X-OmniRoute-Session-Id` هم مصرف را به یک نشست نسبت
        می‌دهد تا هزینه‌یابی دقیق‌تر باشد.
        """
        headers = super()._headers()
        headers.setdefault("X-Title", "Crypto AI Trader")
        headers.setdefault("HTTP-Referer", "https://github.com/crypto-ai-trader")
        session_id = str(self._config.extra.get("session_id") or "").strip()
        if session_id:
            headers["X-OmniRoute-Session-Id"] = session_id
        return headers

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    async def is_available(self) -> tuple[bool, str]:
        """
        بررسی در دسترس بودن دروازه.

        تفاوت با کلاس پایه: نبودِ کلید خطا نیست. نصب تازهٔ OmniRoute تا
        وقتی `REQUIRE_API_KEY` روشن نشده بدون کلید پاسخ می‌دهد، پس اول
        واقعاً درخواست می‌زنیم و فقط اگر دروازه ۴۰۱ داد می‌گوییم کلید لازم
        است. همچنین وقتی دروازه اجرا نشده باشد، پیام باید همین را بگوید
        نه «خطای شبکه».
        """
        base_url = (self._config.base_url or "").strip()
        if not base_url:
            return False, "OmniRoute base URL is not configured"

        try:
            client = await self._get_client()
            response = await client.get("/models", headers=self._headers(), timeout=20.0)
        except httpx.ConnectError:
            return False, (
                "OmniRoute gateway is not reachable at "
                f"{base_url} — start it with 'omniroute' and try again"
            )
        except httpx.TimeoutException:
            return False, "OmniRoute gateway timed out"
        except httpx.HTTPError as exc:
            return False, f"Connection error: {exc.__class__.__name__}"

        if response.status_code in (401, 403):
            return False, (
                "OmniRoute rejected the API key — create an endpoint key in "
                "Dashboard → Endpoints and paste it here"
            )
        if response.status_code >= 400:
            return False, f"HTTP {response.status_code}: {self._error_text(response)}"
        return True, "OmniRoute gateway is reachable"

    # ------------------------------------------------------------------
    # فهرست مدل‌ها
    # ------------------------------------------------------------------
    async def list_models(self) -> list[str]:
        """
        فهرست مدل‌های در دسترس دروازه.

        مدل ویژهٔ `auto` همیشه اول فهرست می‌آید: برای کاربری که تازه وصل
        شده، «بگذار خود دروازه انتخاب کند» همیشه امن‌ترین گزینه است و
        نیازی به دانستن پیشوندها ندارد. بقیهٔ مدل‌ها با همان رتبه‌بندی
        مشترک برنامه مرتب می‌شوند.
        """
        models = await super().list_models()
        # فهرست خالی یعنی درخواست شکست خورده (کلاس پایه خطا را می‌بلعد).
        # در آن حالت نباید `auto` را بچسبانیم، وگرنه دروازهٔ خاموش هم
        # «یک مدل دارد» به‌نظر می‌رسد.
        self._last_listing_ok = bool(models)
        if not models:
            return []
        ordered = [name for name in models if name.strip().lower() != AUTO_MODEL]
        return [AUTO_MODEL, *ordered]

    async def list_models_detailed(self) -> list[dict[str, Any]]:
        """
        فهرست مدل‌ها همراه با نام سرویسِ پشت هرکدام.

        صفحهٔ تنظیمات می‌تواند با این خروجی نشان دهد هر مدل در عمل از کجا
        می‌آید — چیزی که در فهرست تخت گم می‌شود.
        """
        return [
            {"id": name, "vendor": model_vendor(name)}
            for name in await self.list_models()
        ]


__all__ = [
    "AUTO_MODEL",
    "DEFAULT_BASE_URL",
    "PROVIDER_PREFIXES",
    "OmniRouteProvider",
    "model_vendor",
]
