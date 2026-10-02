"""
دسته‌های لاگ سراسری — نسخهٔ ۲.۶.۰.

هر رکورد لاگ دقیقاً یک دسته دارد. دسته یا صریحاً با `extra={"category": ...}`
داده می‌شود، یا از نام لاگر (یعنی `__name__` ماژول) استخراج می‌شود؛ بنابراین
همهٔ `logger = get_logger(__name__)`های موجود بدون هیچ تغییری دسته‌بندی می‌شوند.
"""

from __future__ import annotations

from enum import Enum


class LogCategory(str, Enum):
    """دسته‌های لاگ؛ مقدار = نام پوشهٔ لاگ."""

    APPLICATION = "application"
    TRADING = "trading"
    SCALP = "scalp"
    SIGNALS = "signals"
    ORDERS = "orders"
    EXCHANGE = "exchange"
    MARKET = "market"
    RISK = "risk"
    AI = "ai"
    ERROR = "errors"
    PERFORMANCE = "performance"
    AUDIT = "audit"


#: ترتیب نمایش در مرکز لاگ
CATEGORY_ORDER: tuple[LogCategory, ...] = tuple(LogCategory)

#: (پیشوند نام لاگر، دسته) — اولین تطابق برنده است؛ پس خاص‌ها اول‌اند.
_PREFIX_RULES: tuple[tuple[str, LogCategory], ...] = (
    ("audit", LogCategory.AUDIT),
    ("performance", LogCategory.PERFORMANCE),
    ("trading.ultra_scalp", LogCategory.SCALP),
    ("trading.scalp", LogCategory.SCALP),
    ("trading.micro_plan", LogCategory.SCALP),
    ("trading.execution", LogCategory.ORDERS),
    ("trading.paper_execution", LogCategory.ORDERS),
    ("trading.validation_gate", LogCategory.RISK),
    ("trading.risk", LogCategory.RISK),
    ("trading", LogCategory.TRADING),
    ("app.database.repositories.trade_repository", LogCategory.ORDERS),
    ("signals.risk_engine", LogCategory.RISK),
    ("signals.position_sizing", LogCategory.RISK),
    ("signals.paper_trader", LogCategory.TRADING),
    ("signals", LogCategory.SIGNALS),
    ("backtest", LogCategory.SIGNALS),
    ("prediction", LogCategory.SIGNALS),
    ("market.providers", LogCategory.EXCHANGE),
    ("market.exchange", LogCategory.EXCHANGE),
    ("app.core.exchange_account_service", LogCategory.EXCHANGE),
    ("exchange", LogCategory.EXCHANGE),
    ("market", LogCategory.MARKET),
    ("ai", LogCategory.AI),
)


def parse_category(value: object) -> LogCategory | None:
    """متن/عضو enum → دسته؛ نامعتبر → None."""
    if isinstance(value, LogCategory):
        return value
    text = str(value or "").strip().lower()
    if not text:
        return None
    for category in LogCategory:
        if text in (category.value, category.name.lower()):
            return category
    if text == "error":
        return LogCategory.ERROR
    return None


def category_for_logger(name: str) -> LogCategory:
    """دسته از روی نام لاگر (`trading.auto_trader` → TRADING)."""
    lowered = (name or "").lower()
    for prefix, category in _PREFIX_RULES:
        if lowered == prefix or lowered.startswith(prefix + ".") or lowered.startswith(prefix + "_"):
            return category
    return LogCategory.APPLICATION


__all__ = ["CATEGORY_ORDER", "LogCategory", "category_for_logger", "parse_category"]
