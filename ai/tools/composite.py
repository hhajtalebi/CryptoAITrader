"""
ترکیب چند مجموعه‌ابزار در یک واسط واحد.

چرا لازم شد؟
    عامل‌های برنامه (چت، تحلیلگر، عامل خودگردان) یک شیء «جعبه‌ابزار» می‌گیرند
    و سه چیز از آن می‌خواهند: `tool_names`، `get_definitions()` و
    `execute()`. تا وقتی فقط ابزار بازار داشتیم، `MarketToolset` مستقیم
    پاس داده می‌شد. حالا که ابزارهای دروازهٔ OmniRoute هم اضافه شده‌اند،
    یا باید همهٔ عامل‌ها را تغییر می‌دادیم (و هر بار با هر ابزار تازه
    دوباره)، یا یک لایهٔ ترکیب می‌ساختیم. دومی انتخاب شد.

قاعدهٔ حل تداخل: اولین مجموعه‌ای که ابزاری به آن نام داشته باشد برنده است.
ترتیب ثبت یعنی اولویت. این رفتار عمدی و قابل پیش‌بینی است تا یک افزونهٔ
تازه نتواند بی‌سروصدا رفتار ابزار اصلی بازار را عوض کند.

نکتهٔ مهم: این کلاس متدهای اختصاصی مجموعه‌های زیرین را هم پاس می‌دهد
(مثل `set_risk_parameters`)، وگرنه کدی که امروز روی `MarketToolset` حساب
می‌کند می‌شکست.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ai.tools.market_tools import ToolDefinition, ToolResult
from app.logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class Toolset(Protocol):
    """قرارداد کمینه‌ای که هر مجموعه‌ابزار باید داشته باشد."""

    @property
    def tool_names(self) -> list[str]:
        """نام ابزارهای این مجموعه."""
        ...

    async def execute(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        """اجرای یک ابزار."""
        ...

    @staticmethod
    def get_definitions() -> list[ToolDefinition]:
        """توصیف ابزارها برای مدل."""
        ...


class CompositeToolset:
    """
    چند مجموعه‌ابزار که بیرون مثل یکی دیده می‌شوند.

    نمونه‌سازی:
        tools = CompositeToolset(market_toolset, omniroute_toolset)
        result = await tools.execute("get_current_price", {"symbol": "BTC/USDT"})
    """

    def __init__(self, *toolsets: Any) -> None:
        self._toolsets: list[Any] = [toolset for toolset in toolsets if toolset is not None]

    # ------------------------------------------------------------------
    # ترکیب
    # ------------------------------------------------------------------
    def add(self, toolset: Any) -> None:
        """افزودن یک مجموعهٔ تازه با کمترین اولویت."""
        if toolset is not None:
            self._toolsets.append(toolset)

    @property
    def toolsets(self) -> list[Any]:
        """مجموعه‌های زیرین، به ترتیب اولویت."""
        return list(self._toolsets)

    @property
    def tool_names(self) -> list[str]:
        """نام همهٔ ابزارها، بدون تکرار."""
        names: list[str] = []
        for toolset in self._toolsets:
            for name in getattr(toolset, "tool_names", []):
                if name not in names:
                    names.append(name)
        return sorted(names)

    def _owner(self, name: str) -> Any | None:
        """نخستین مجموعه‌ای که این ابزار را دارد."""
        for toolset in self._toolsets:
            if name in getattr(toolset, "tool_names", []):
                return toolset
        return None

    # ------------------------------------------------------------------
    # قرارداد جعبه‌ابزار
    # ------------------------------------------------------------------
    def get_definitions(self) -> list[ToolDefinition]:
        """
        توصیف همهٔ ابزارها.

        `get_definitions` در مجموعه‌های موجود یک متد ایستا است، پس هم
        فراخوانی روی نمونه و هم روی کلاس باید کار کند؛ هر دو حالت اینجا
        پوشش داده شده‌اند.
        """
        seen: set[str] = set()
        definitions: list[ToolDefinition] = []
        for toolset in self._toolsets:
            getter = getattr(toolset, "get_definitions", None)
            if getter is None:
                continue
            try:
                items = getter()
            except TypeError:  # متد ایستا که به‌صورت نامتعارف تعریف شده
                items = getter(toolset)  # type: ignore[call-arg]
            for definition in items or []:
                if definition.name in seen:
                    continue
                seen.add(definition.name)
                definitions.append(definition)
        return definitions

    async def execute(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        """اجرای ابزار توسط مجموعه‌ای که صاحب آن است."""
        owner = self._owner(name)
        if owner is None:
            return ToolResult(tool=name, ok=False, error=f"Unknown tool: {name}")
        return await owner.execute(name, arguments)

    # ------------------------------------------------------------------
    # پاس‌دادن متدهای اختصاصی
    # ------------------------------------------------------------------
    def set_risk_parameters(self, parameters: Any) -> None:
        """
        انتقال پارامترهای ریسک به هر مجموعه‌ای که آن را می‌پذیرد.

        عامل‌ها این متد را بی‌قید‌وشرط صدا می‌زنند؛ اگر اینجا نبود،
        `AttributeError` می‌گرفتند.
        """
        for toolset in self._toolsets:
            setter = getattr(toolset, "set_risk_parameters", None)
            if callable(setter):
                setter(parameters)

    def __getattr__(self, item: str) -> Any:
        """
        دسترسی به ویژگی‌های مجموعه‌های زیرین.

        بعضی کدها مستقیم سراغ `_market` می‌روند (مثلاً برای خواندن نام
        صرافی). این پل باعث می‌شود ترکیب‌کردن ابزارها چیزی را نشکند.
        """
        for toolset in self.__dict__.get("_toolsets", []):
            if hasattr(toolset, item):
                return getattr(toolset, item)
        raise AttributeError(item)


__all__ = ["CompositeToolset", "Toolset"]
