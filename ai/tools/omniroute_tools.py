"""
ابزارهای دروازهٔ OmniRoute برای عامل هوش مصنوعی.

چرا این ابزارها؟
    وقتی هوش مصنوعی از پشت یک دروازه می‌آید، پرتکرارترین پرسش کاربر این
    است: «الان به چه چیزی وصلم و چه مدل‌هایی دارم؟» بدون ابزار، مدل مجبور
    است از حافظه‌اش جواب بدهد و همان‌جا شروع به ساختن اسم مدل می‌کند. با
    این دو ابزار، پاسخ از خودِ دروازه خوانده می‌شود.

    همچنین وقتی چت کار نمی‌کند، کاربر می‌تواند در خود گفتگو بپرسد «وضعیت
    دروازه چیست؟» و پاسخ واقعی بگیرد — به‌جای آنکه در تنظیمات دنبال دکمهٔ
    «آزمایش اتصال» بگردد.

قاعدهٔ مشترک با بقیهٔ ابزارها: هیچ داده‌ای ساخته نمی‌شود. اگر دروازه در
دسترس نباشد، ابزار صریحاً شکست را گزارش می‌دهد تا مدل بگوید «نمی‌دانم»،
نه اینکه فهرستی از خودش دربیاورد.

نکتهٔ امنیتی: کلید دروازه در خروجی ابزار نمی‌آید. خروجی فقط می‌گوید کلیدی
تنظیم شده یا نه.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from ai.providers.omniroute_provider import (
    AUTO_MODEL,
    DEFAULT_BASE_URL,
    OmniRouteProvider,
    model_vendor,
)
from ai.tools.market_tools import ToolDefinition, ToolResult
from app.logging import get_logger

logger = get_logger(__name__)

#: بیشترین تعداد مدلی که در پاسخ ابزار برمی‌گردد.
#: فهرست کامل یک دروازهٔ پرمصرف صدها ردیف است و Context مدل را پر می‌کند.
MAX_MODELS_IN_RESULT = 60


class OmniRouteToolset:
    """
    ابزارهای پرس‌وجو از دروازهٔ OmniRoute.

    نمونه‌سازی:
        tools = OmniRouteToolset(provider_factory=lambda: provider)
        result = await tools.execute("omniroute_status")

    `provider_factory` تنبل است تا وقتی کاربر اصلاً از OmniRoute استفاده
    نمی‌کند هیچ کلاینت شبکه‌ای ساخته نشود.
    """

    def __init__(
        self,
        provider_factory: Callable[[], OmniRouteProvider | None] | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._provider_factory = provider_factory
        self._base_url = base_url or DEFAULT_BASE_URL
        self._handlers: dict[str, Callable[..., Awaitable[Any]]] = {
            "omniroute_status": self.gateway_status,
            "omniroute_models": self.list_gateway_models,
        }

    # ------------------------------------------------------------------
    # اجرا
    # ------------------------------------------------------------------
    @property
    def tool_names(self) -> list[str]:
        """فهرست نام ابزارهای این مجموعه."""
        return sorted(self._handlers)

    async def execute(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        """اجرای امن یک ابزار؛ هر خطا به نتیجهٔ ناموفق تبدیل می‌شود."""
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(tool=name, ok=False, error=f"Unknown tool: {name}")
        try:
            data = await handler(**(arguments or {}))
            return ToolResult(tool=name, ok=True, data=data, source="omniroute:gateway")
        except TypeError as exc:
            return ToolResult(tool=name, ok=False, error=f"Invalid arguments for {name}: {exc}")
        except httpx.HTTPError as exc:
            return ToolResult(
                tool=name,
                ok=False,
                error=f"OmniRoute gateway is unreachable ({exc.__class__.__name__})",
            )
        except Exception as exc:  # noqa: BLE001 - یک ابزار نباید کل گفتگو را بشکند
            logger.exception("Unexpected error in OmniRoute tool %s", name)
            return ToolResult(tool=name, ok=False, error=f"{exc.__class__.__name__}")

    # ------------------------------------------------------------------
    # ابزارها
    # ------------------------------------------------------------------
    def _provider(self) -> OmniRouteProvider | None:
        """ارائه‌دهندهٔ فعال دروازه، در صورت پیکربندی."""
        if self._provider_factory is None:
            return None
        return self._provider_factory()

    async def gateway_status(self) -> dict[str, Any]:
        """
        وضعیت زندهٔ دروازه: در دسترس بودن، نشانی، و تعداد مدل‌ها.

        هیچ‌گاه استثنا پرتاب نمی‌کند مگر خطای شبکه؛ «در دسترس نیست» هم یک
        پاسخ معتبر است که مدل باید بتواند به کاربر بگوید.
        """
        provider = self._provider()
        if provider is None:
            return {
                "configured": False,
                "reachable": False,
                "base_url": self._base_url,
                "hint": "Select OmniRoute in Settings → AI to use the gateway.",
            }

        reachable, message = await provider.is_available()
        payload: dict[str, Any] = {
            "configured": True,
            "reachable": bool(reachable),
            "base_url": provider.config.base_url,
            "message": message,
            "active_model": provider.model or AUTO_MODEL,
            # کلید هرگز برنمی‌گردد؛ فقط وجود یا نبودش
            "api_key_configured": provider.has_api_key,
        }
        if reachable:
            models = await provider.list_models()
            payload["model_count"] = len(models)
            payload["vendors"] = sorted({v for v in map(model_vendor, models) if v})
        return payload

    async def list_gateway_models(self, vendor: str = "", limit: int = 0) -> dict[str, Any]:
        """
        فهرست مدل‌های در دسترس دروازه، گروه‌بندی‌شده بر پایهٔ سرویس.

        `vendor` فهرست را به یک سرویس محدود می‌کند (مثلاً «Gemini»). فیلتر
        روی هم نام خوانا و هم پیشوند خام کار می‌کند، چون کاربر ممکن است
        هر کدام را بنویسد.
        """
        provider = self._provider()
        if provider is None:
            return {
                "configured": False,
                "models": [],
                "hint": "Select OmniRoute in Settings → AI to use the gateway.",
            }

        models = await provider.list_models()
        if not models and not getattr(provider, "last_listing_ok", True):
            # دروازه پاسخ نداد. «فهرست خالی» را به کاربر نشان نمی‌دهیم چون
            # با «دروازه هیچ مدلی ندارد» اشتباه می‌شود.
            raise httpx.ConnectError("OmniRoute gateway did not answer")

        wanted = str(vendor or "").strip().lower()
        if wanted:
            models = [
                name
                for name in models
                if wanted in model_vendor(name).lower()
                or name.lower().startswith(f"{wanted}/")
            ]

        cap = int(limit) if int(limit or 0) > 0 else MAX_MODELS_IN_RESULT
        shown = models[:cap]

        grouped: dict[str, list[str]] = {}
        for name in shown:
            grouped.setdefault(model_vendor(name) or "other", []).append(name)

        return {
            "configured": True,
            "base_url": provider.config.base_url,
            "total": len(models),
            "returned": len(shown),
            "truncated": len(models) > len(shown),
            "models": shown,
            "by_vendor": grouped,
        }

    # ------------------------------------------------------------------
    # تعریف ابزارها برای مدل
    # ------------------------------------------------------------------
    @staticmethod
    def get_definitions() -> list[ToolDefinition]:
        """توصیف ابزارها به قالب Function Calling."""
        return [
            ToolDefinition(
                "omniroute_status",
                "Check the OmniRoute AI gateway: whether it is reachable, "
                "which model is active, and how many models it exposes.",
                {},
            ),
            ToolDefinition(
                "omniroute_models",
                "List the AI models available through the OmniRoute gateway, "
                "grouped by the upstream service that serves them.",
                {
                    "vendor": {
                        "type": "string",
                        "description": "Optional filter, e.g. 'Gemini' or 'gg'",
                    },
                    "limit": {"type": "integer", "description": "Maximum models to return"},
                },
            ),
        ]


__all__ = ["MAX_MODELS_IN_RESULT", "OmniRouteToolset"]
