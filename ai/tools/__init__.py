"""
ابزارهای عامل هوش مصنوعی.

این ابزارها تنها راه دسترسی مدل به داده واقعی هستند. مدل هیچ‌گاه مستقیماً
به شبکه یا پایگاه داده دسترسی ندارد؛ همین معماری، ضامن جلوگیری از توهم
(Hallucination) عددی است.

دو خانواده ابزار داریم:
    * `MarketToolset`    — قیمت، کندل، اندیکاتور، روند، ساختار، ریسک
    * `OmniRouteToolset` — پرس‌وجو از دروازهٔ هوش مصنوعی OmniRoute

`CompositeToolset` آن‌ها را کنار هم می‌گذارد تا عامل‌ها یک جعبه‌ابزار
واحد ببینند و افزودن خانوادهٔ تازه نیازی به تغییر عامل‌ها نداشته باشد.
"""

from ai.tools.composite import CompositeToolset
from ai.tools.market_tools import MarketToolset, ToolDefinition, ToolResult
from ai.tools.omniroute_tools import OmniRouteToolset

__all__ = [
    "CompositeToolset",
    "MarketToolset",
    "OmniRouteToolset",
    "ToolDefinition",
    "ToolResult",
]
