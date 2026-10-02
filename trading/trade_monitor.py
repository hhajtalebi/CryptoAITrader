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
    #: v2.5.0 — اهداف پلکانی (TP1..TP3) و پیشرفت آن‌ها
    targets: tuple[float, ...] = ()
    targets_hit: int = 0
    original_quantity: float = 0.0
    #: سود ناخالص تحقق‌یافته از بستن‌های جزئی (کارمزدشان در entry_fee است)
    realized_gross: float = 0.0

    @property
    def is_staged(self) -> bool:
        """آیا این موقعیت اهداف پلکانی دارد؟"""
        return len(self.targets) > 0

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
        pnl = (
            difference * self.quantity
            + self.realized_gross
            - self.entry_fee
            - self.quantity * price * self.fee_rate
        )
        # درصد نسبت به مارجین **اولیه**؛ پس از بستن جزئی، حجم باقی‌مانده
        # کوچک‌تر است و تقسیم بر آن درصد را غلط بزرگ نشان می‌دهد.
        base_quantity = max(self.quantity, self.original_quantity or 0.0)
        notional = self.entry_price * base_quantity
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

    extra = _get("extra", {}) or {}
    if not isinstance(extra, dict):
        extra = {}
    targets: tuple[float, ...] = ()
    try:
        targets = tuple(float(v) for v in (extra.get("targets") or []) if float(v) > 0)
    except (TypeError, ValueError):
        targets = ()
    try:
        targets_hit = max(0, int(extra.get("targets_hit") or 0))
        original_quantity = float(extra.get("original_quantity") or quantity)
        realized_gross = float(extra.get("realized_gross") or 0.0)
    except (TypeError, ValueError):
        targets_hit, original_quantity, realized_gross = 0, quantity, 0.0

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
        fee_rate=float(extra.get("fee_rate", 0.0) or 0.0),
        targets=targets,
        targets_hit=targets_hit,
        original_quantity=original_quantity,
        realized_gross=realized_gross,
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


def evaluate_staged(
    positions: list[LivePosition], prices: dict[str, float]
) -> tuple[list[dict[str, Any]], list[tuple[int, float, dict[str, Any]]]]:
    """
    ارزیابی با مدیریت پلکانی اهداف (v2.5.0).

    بازگشتی: (به‌روزرسانی‌های نمایش، گام‌ها). هر گام `(شناسه، قیمت، اقدام)`
    است و اقدام همان خروجی `staged_targets.next_step` است. موقعیت بدون
    اهداف پلکانی با همان قاعدهٔ قدیمی `should_close` ارزیابی می‌شود و
    گامش `{"action": "final"|"stop", "reason": ...}` است.
    """
    from trading.staged_targets import next_step  # noqa: PLC0415

    updates: list[dict[str, Any]] = []
    steps: list[tuple[int, float, dict[str, Any]]] = []
    for position in positions:
        price = float(prices.get(position.symbol, 0.0) or 0.0)
        if price <= 0:
            continue
        pnl, percent = position.unrealised(price)
        updates.append(
            {"id": position.trade_id, "symbol": position.symbol, "price": price,
             "pnl": pnl, "pnl_percent": percent}
        )
        if position.is_staged:
            step = next_step(
                price=price,
                side=position.side,
                stop_loss=position.stop_loss,
                targets=position.targets,
                targets_hit=position.targets_hit,
                original_quantity=position.original_quantity or position.quantity,
                remaining_quantity=position.quantity,
                entry=position.entry_price,
            )
            if step is not None:
                steps.append((position.trade_id, price, step))
            continue
        close, reason = position.should_close(price)
        if close:
            action = "stop" if reason == REASON_STOP_LOSS else "final"
            steps.append((position.trade_id, price, {"action": action, "reason": reason}))
    return updates, steps
