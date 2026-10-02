"""
موجودی جعلی معاملهٔ کاغذی — نسخهٔ ۲.۵.۰.

خواستهٔ کاربر: «موجودی برنامه باید از کیف پول خوانده شود؛ برای معاملهٔ
کاغذی موجودی جعلی داشته باشیم.» و در پاسخ پرسش ۲.۵.۰: موجودی کاغذی
**برابر موجودی واقعی کیف پول** باشد تا تمرین شبیه معاملهٔ واقعی شود.

مدل:
    شروع (start)        — عدد ثابتی که هنگام «همگام‌سازی با کیف پول» از کل
                          ارزش تتری کیف پول واقعی گرفته می‌شود. اگر حسابی
                          متصل نباشد، `risk.account_balance` تنظیمات.
    سود تحقق‌یافته      — جمع سود/زیان خالص معاملات کاغذی بسته‌شده **از
                          لحظهٔ شروع** (با همگام‌سازی دوباره صفر می‌شود).
    سود شناور           — سود/زیان معاملات کاغذی باز.
    ارزش حساب (equity)  = شروع + تحقق‌یافته + شناور
    مارجین درگیر        — جمع مارجین معاملات باز.
    آزاد (available)    = شروع + تحقق‌یافته − مارجین درگیر

هیچ پولی جابه‌جا نمی‌شود؛ این فقط دفترداری تمرینی است. منطق خالص است
(بدون Qt و پایگاه داده) تا کامل آزمون شود.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

#: کلیدهای تنظیمات
KEY_START = "paper.start_balance"
KEY_START_AT = "paper.start_at"
KEY_SOURCE = "paper.source"

SOURCE_WALLET = "wallet"
SOURCE_SETTINGS = "settings"


@dataclass(slots=True)
class PaperAccount:
    """خلاصهٔ حساب کاغذی."""

    start: float
    realized: float
    unrealized: float
    used_margin: float
    source: str = SOURCE_SETTINGS
    start_at: str = ""

    @property
    def equity(self) -> float:
        """ارزش لحظه‌ای حساب کاغذی."""
        return self.start + self.realized + self.unrealized

    @property
    def available(self) -> float:
        """موجودی آزاد برای معاملهٔ تازه (هرگز منفی نمایش داده نمی‌شود)."""
        return max(0.0, self.start + self.realized - self.used_margin)

    @property
    def balance(self) -> float:
        """موجودی دفتری (بدون سود شناور) — مبنای اندازهٔ پوزیشن."""
        return max(0.0, self.start + self.realized)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.update(equity=self.equity, available=self.available, balance=self.balance)
        return data


def open_trade_margin(record: dict[str, Any]) -> float:
    """مارجین یک معاملهٔ باز: قیمت ورود × حجم باز ÷ اهرم."""
    try:
        entry = float(record.get("entry_price") or 0.0)
        quantity = float(record.get("quantity") or 0.0)
        leverage = max(1.0, float(record.get("leverage") or 1.0))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, entry * quantity / leverage)


def build_account(
    *,
    start: float,
    realized: float,
    open_trades: list[dict[str, Any]],
    source: str = SOURCE_SETTINGS,
    start_at: str = "",
) -> PaperAccount:
    """ساخت خلاصهٔ حساب از عدد شروع، سود تحقق‌یافته و معاملات باز."""
    used = 0.0
    floating = 0.0
    for record in open_trades or []:
        used += open_trade_margin(record)
        try:
            floating += float(record.get("pnl") or 0.0)
        except (TypeError, ValueError):
            continue
    return PaperAccount(
        start=max(0.0, float(start or 0.0)),
        realized=float(realized or 0.0),
        unrealized=floating,
        used_margin=used,
        source=source,
        start_at=start_at,
    )


def parse_start_at(text: Any) -> datetime | None:
    """خواندن لحظهٔ شروع (UTC بدون منطقه) از تنظیمات."""
    if isinstance(text, datetime):
        return text.replace(tzinfo=None)
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def utc_now_text() -> str:
    """لحظهٔ جاری UTC برای ذخیره در تنظیمات."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


__all__ = [
    "KEY_SOURCE",
    "KEY_START",
    "KEY_START_AT",
    "PaperAccount",
    "SOURCE_SETTINGS",
    "SOURCE_WALLET",
    "build_account",
    "open_trade_margin",
    "parse_start_at",
    "utc_now_text",
]
