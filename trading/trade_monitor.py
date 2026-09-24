"""
پایش زندهٔ معاملات باز.

چرا این پرونده ساخته شد؟
    کاربر گزارش کرد: «معامله باز می‌شود ولی تغییری با بازار نمی‌کند و
    هیچ‌وقت بسته نمی‌شود، سود و زیان معلوم نیست و دستی هم بسته نمی‌شود.»

    بررسی نشان داد کاملاً درست است: `pnl` فقط **هنگام بستن** محاسبه
    می‌شد و هیچ چیزی معاملهٔ باز را دنبال نمی‌کرد. حد ضرر و حد سود
    ذخیره می‌شدند ولی هرگز بررسی نمی‌شدند. یک معاملهٔ باز عملاً یک ردیف
    مردهٔ پایگاه داده بود.

این ماژول منطق خالص است: ورودی می‌گیرد و تصمیم برمی‌گرداند. هیچ
وابستگی‌ای به رابط کاربری یا پایگاه داده ندارد تا بتوان کامل آزمونش کرد.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# دلایل بسته‌شدن، به‌صورت کلید ترجمه تا در هر دو زبان درست نمایش یابد.
REASON_STOP_LOSS = "stop_loss"
REASON_TAKE_PROFIT = "take_profit"
REASON_MANUAL = "manual"


@dataclass(slots=True)
class LivePosition:
    """وضعیت لحظه‌ای یک معاملهٔ باز."""

    trade_id: int
    symbol: str
    side: str
    quantity: float
    entry_price: float
    leverage: float = 1.0
    stop_loss: float | None = None
    take_profit: float | None = None
    entry_fee: float = 0.0
    fee_rate: float = 0.0

    @property
    def is_long(self) -> bool:
        """آیا موقعیت خرید است؟"""
        return str(self.side).lower() in ("long", "buy")

    def unrealised(self, price: float) -> tuple[float, float]:
        """
        سود/زیان تحقق‌نیافته به دلار و درصد.

        درصد **نسبت به مارجین** حساب می‌شود نه نسبت به قیمت، چون کاربر
        با اهرم معامله می‌کند و آنچه برایش مهم است بازده سرمایه‌اش است.
        نمایش درصدِ قیمت در معاملهٔ اهرم‌دار، عدد را ۱۰ برابر کوچک‌تر از
        واقعیت نشان می‌دهد.
        """
        if price <= 0 or self.entry_price <= 0:
            return 0.0, 0.0
        difference = price - self.entry_price
        if not self.is_long:
            difference = -difference
        pnl = difference * self.quantity - self.entry_fee - self.quantity * price * self.fee_rate
        notional = self.entry_price * self.quantity
        margin = notional / self.leverage if self.leverage > 0 else notional
        percent = (pnl / margin * 100.0) if margin else 0.0
        return round(pnl, 8), round(percent, 4)

    def should_close(self, price: float) -> tuple[bool, str]:
        """
        آیا این قیمت یکی از مرزهای خروج را زده است؟

        حد ضرر **اول** بررسی می‌شود. اگر یک کندل هم حد ضرر و هم حد سود
        را در بر بگیرد، محتاطانه‌ترین فرض این است که اول ضرر خورده‌ایم؛
        فرض خوش‌بینانه باعث می‌شود آمار عملکرد دروغ بگوید.
        """
        if price <= 0:
            return False, ""
        if self.stop_loss is not None and self.stop_loss > 0:
            if self.is_long and price <= self.stop_loss:
                return True, REASON_STOP_LOSS
            if not self.is_long and price >= self.stop_loss:
                return True, REASON_STOP_LOSS
        if self.take_profit is not None and self.take_profit > 0:
            if self.is_long and price >= self.take_profit:
                return True, REASON_TAKE_PROFIT
            if not self.is_long and price <= self.take_profit:
                return True, REASON_TAKE_PROFIT
        return False, ""


def position_from_record(record: Any) -> LivePosition | None:
    """
    ساخت `LivePosition` از یک ردیف پایگاه داده یا دیکشنری.

    ردیف ناقص (بدون شناسه یا قیمت ورود) کنار گذاشته می‌شود تا یک رکورد
    خراب کل پایش را از کار نیندازد.
    """

    def _get(name: str, default: Any = None) -> Any:
        if isinstance(record, dict):
            return record.get(name, default)
        return getattr(record, name, default)

    try:
        trade_id = int(_get("id") or 0)
        entry = float(_get("entry_price") or 0.0)
        quantity = float(_get("quantity") or 0.0)
    except (TypeError, ValueError):
        return None
    if trade_id <= 0 or entry <= 0 or quantity <= 0:
        return None

    def _optional(name: str) -> float | None:
        raw = _get(name)
        if raw in (None, "", 0, 0.0):
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    leverage = 1.0
    try:
        leverage = max(1.0, float(_get("leverage") or 1.0))
    except (TypeError, ValueError):
        leverage = 1.0

    return LivePosition(
        trade_id=trade_id,
        symbol=str(_get("symbol") or ""),
        side=str(_get("side") or "long"),
        quantity=quantity,
        entry_price=entry,
        leverage=leverage,
        stop_loss=_optional("stop_loss"),
        take_profit=_optional("take_profit"),
        entry_fee=float(_get("fee", 0.0) or 0.0),
        fee_rate=float((_get("extra", {}) or {}).get("fee_rate", 0.0) or 0.0),
    )


def evaluate(
    positions: list[LivePosition], prices: dict[str, float]
) -> tuple[list[dict[str, Any]], list[tuple[int, float, str]]]:
    """
    ارزیابی همهٔ موقعیت‌های باز با قیمت‌های تازه.

    بازگشتی:
        • فهرست به‌روزرسانی‌ها برای نمایش (شناسه، سود/زیان، درصد، قیمت)
        • فهرست موقعیت‌هایی که باید بسته شوند: (شناسه، قیمت، دلیل)

    نمادی که قیمتش در دست نیست نادیده گرفته می‌شود — نه صفر در نظر
    گرفته می‌شود. نمایش «۰ دلار» برای معامله‌ای که قیمتش نرسیده،
    اطلاعات غلط است و بدتر از نبودِ عدد.
    """
    updates: list[dict[str, Any]] = []
    closures: list[tuple[int, float, str]] = []

    for position in positions:
        price = float(prices.get(position.symbol, 0.0) or 0.0)
        if price <= 0:
            continue
        pnl, percent = position.unrealised(price)
        updates.append(
            {
                "id": position.trade_id,
                "symbol": position.symbol,
                "price": price,
                "pnl": pnl,
                "pnl_percent": percent,
            }
        )
        close, reason = position.should_close(price)
        if close:
            closures.append((position.trade_id, price, reason))

    return updates, closures
