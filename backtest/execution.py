"""
شبیه‌سازی اجرای معامله در بک‌تست.

قواعد (محافظه‌کارانه):
    • ورود: قیمت باز کندل **بعد** از سیگنال (سیگنال روی کندل بسته‌شده
      ساخته می‌شود؛ ورود در همان قیمت بسته‌شدن look-ahead پنهان است).
    • اسپرد: نیمی از اسپرد کامل در ورود و نیمی در خروج علیه معامله‌گر.
    • لغزش: درصد ثابت علیه معامله‌گر در ورود و در خروج با حد ضرر.
    • کارمزد: taker در ورود و خروج روی ارزش اسمی.
    • درون‌کندلی بدبینانه: اگر SL و TP هر دو در یک کندل لمس شوند، SL
      فرض می‌شود.
    • خروج پلکانی مثل معاملهٔ کاغذی برنامه: ⅓ در TP1، ⅓ در TP2، باقی در
      TP3؛ پس از TP1 حد ضرر به نقطهٔ ورود می‌رود.
    • نگه‌داری حداکثر: پس از max_bars معامله با قیمت بسته‌شدن خارج می‌شود.
    • ورود معتبر فقط اگر قیمت باز کندل بعد هنوز بین SL و TP1 باشد.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.models import Candle


@dataclass(slots=True, frozen=True)
class ExecutionModel:
    """هزینه‌های اجرا (درصد)."""

    fee_percent: float = 0.06
    spread_percent: float = 0.04
    slippage_percent: float = 0.02

    def entry_price(self, direction: str, reference: float) -> float:
        adverse = (self.spread_percent / 2 + self.slippage_percent) / 100.0
        return reference * (1 + adverse) if direction == "LONG" else reference * (1 - adverse)

    def exit_price(self, direction: str, reference: float, *, stop: bool) -> float:
        adverse = (self.spread_percent / 2 + (self.slippage_percent if stop else 0.0)) / 100.0
        return reference * (1 - adverse) if direction == "LONG" else reference * (1 + adverse)


@dataclass(slots=True)
class TradeResult:
    """نتیجهٔ یک معاملهٔ شبیه‌سازی‌شده."""

    symbol: str
    direction: str
    signal_time: int
    entry_time: int
    exit_time: int
    entry: float
    stop_loss: float
    exit_reason: str
    r_multiple: float
    return_percent: float
    fees_percent: float
    bars: int
    mae_percent: float
    mfe_percent: float
    targets_hit: int
    size_multiplier: float = 1.0
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def won(self) -> bool:
        return self.r_multiple > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol, "direction": self.direction,
            "signal_time": self.signal_time, "entry_time": self.entry_time,
            "exit_time": self.exit_time, "entry": self.entry, "stop_loss": self.stop_loss,
            "exit_reason": self.exit_reason, "r_multiple": round(self.r_multiple, 4),
            "return_percent": round(self.return_percent, 4),
            "fees_percent": round(self.fees_percent, 4), "bars": self.bars,
            "mae_percent": round(self.mae_percent, 4), "mfe_percent": round(self.mfe_percent, 4),
            "targets_hit": self.targets_hit, "size_multiplier": self.size_multiplier,
            **{k: v for k, v in self.meta.items() if isinstance(v, (int, float, str, bool)) or v is None},
        }


def simulate_trade(
    *,
    symbol: str,
    direction: str,
    signal_time: int,
    stop_loss: float,
    take_profits: list[float],
    future: list[Candle],
    model: ExecutionModel,
    max_bars: int,
    size_multiplier: float = 1.0,
    meta: dict[str, Any] | None = None,
) -> TradeResult | None:
    """
    شبیه‌سازی از کندل بعد از سیگنال. `future[0]` باید اولین کندل پس از t باشد.

    بازگشت None یعنی ورود ممکن نبود (قیمت باز از SL/TP1 عبور کرده یا داده نیست).
    """
    if not future or not take_profits or direction not in ("LONG", "SHORT"):
        return None
    sign = 1.0 if direction == "LONG" else -1.0
    open_ref = future[0].open
    targets = [float(t) for t in take_profits[:3]]
    # اعتبار ورود: هنوز بین SL و TP1
    if sign * (open_ref - stop_loss) <= 0 or sign * (targets[0] - open_ref) <= 0:
        return None
    entry = model.entry_price(direction, open_ref)
    risk_per_unit = abs(entry - stop_loss)
    if risk_per_unit <= 0:
        return None

    portions = [1 / 3, 1 / 3, 1 / 3] if len(targets) >= 3 else [1.0 / len(targets)] * len(targets)
    remaining = 1.0
    stop = stop_loss
    realized = 0.0  # بازده وزن‌دار (قیمت) × جهت
    hit = 0
    mae = 0.0
    mfe = 0.0
    exit_reason = "timeout"
    exit_time = future[0].timestamp
    bars = 0
    for bars, candle in enumerate(future[:max_bars], start=1):
        adverse = (candle.low - entry) if sign > 0 else (entry - candle.high)
        favorable = (candle.high - entry) if sign > 0 else (entry - candle.low)
        mae = min(mae, adverse / entry * 100)
        mfe = max(mfe, favorable / entry * 100)
        stop_hit = (candle.low <= stop) if sign > 0 else (candle.high >= stop)
        if stop_hit:
            # بدبینانه: SL پیش از هر TP همان کندل
            price = model.exit_price(direction, stop, stop=True)
            realized += remaining * sign * (price - entry)
            remaining = 0.0
            exit_reason = "stop" if hit == 0 else "breakeven_stop"
            exit_time = candle.timestamp
            break
        while hit < len(targets):
            target = targets[hit]
            reached = (candle.high >= target) if sign > 0 else (candle.low <= target)
            if not reached:
                break
            portion = portions[hit] if hit < len(targets) - 1 else remaining
            price = model.exit_price(direction, target, stop=False)
            realized += portion * sign * (price - entry)
            remaining -= portion
            hit += 1
            if hit == 1:
                stop = entry  # حد ضرر به نقطهٔ ورود
        if remaining <= 1e-9:
            exit_reason = "target"
            exit_time = candle.timestamp
            break
    else:
        last = future[min(len(future), max_bars) - 1]
        price = model.exit_price(direction, last.close, stop=False)
        realized += remaining * sign * (price - entry)
        remaining = 0.0
        exit_time = last.timestamp
    if remaining > 1e-9:
        last = future[min(len(future), max_bars) - 1]
        price = model.exit_price(direction, last.close, stop=False)
        realized += remaining * sign * (price - entry)
        exit_time = last.timestamp

    fees = 2 * model.fee_percent  # ورود + خروج روی ارزش اسمی (درصد)
    gross_percent = realized / entry * 100.0
    net_percent = gross_percent - fees
    r_multiple = (net_percent / 100.0 * entry) / risk_per_unit
    return TradeResult(
        symbol=symbol, direction=direction, signal_time=signal_time,
        entry_time=future[0].timestamp, exit_time=exit_time, entry=entry,
        stop_loss=stop_loss, exit_reason=exit_reason, r_multiple=r_multiple,
        return_percent=net_percent, fees_percent=fees, bars=bars,
        mae_percent=mae, mfe_percent=mfe, targets_hit=hit,
        size_multiplier=size_multiplier, meta=dict(meta or {}),
    )


__all__ = ["ExecutionModel", "TradeResult", "simulate_trade"]
