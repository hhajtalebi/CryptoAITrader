"""محاسبهٔ سود خالص اسکالپ خیلی کوتاه، بعد از کارمزد.

مثال کاربر: ۱۰ دلار مارجین با اهرم ۲۰۰ یعنی حجم ۲۰۰۰ دلار. کارمزد
گیرندهٔ ۰٫۰۶٪ در هر طرف، رفت‌وبرگشت ۲٫۴۰ دلار است. اگر هدف سود خالص
۳ دلار باشد، معامله باید وقتی بسته شود که حرکت قیمت ۵٫۴۰ دلار سود
ناخالص ساخته باشد.

این ماژول هیچ سفارشی نمی‌فرستد. فقط عدد هدف و حد ضرر را حساب می‌کند.
"""

from __future__ import annotations

from dataclasses import dataclass

#: کارمزد گیرندهٔ هر طرف. ۰٫۰۶٪ یعنی ۰٫۱۲٪ رفت‌وبرگشت.
DEFAULT_TAKER_FEE_RATE = 0.0006

#: پروفایل صریحی که کاربر برای معاملهٔ خیلی کوتاه خواست.
MICRO_MARGIN = 10.0
MICRO_LEVERAGE = 200.0
MICRO_TARGETS = (3.0, 4.0, 5.0)
MICRO_HOLD_SECONDS = 90
MICRO_POLL_SECONDS = 0.4


@dataclass(frozen=True)
class MicroPlan:
    """نتیجهٔ محاسبهٔ یک معاملهٔ کوتاه."""

    margin: float
    leverage: float
    net_target: float
    max_loss: float
    fee_rate: float
    notional: float
    round_trip_fee: float
    gross_target: float
    stop_distance: float

    @property
    def entry_fee(self) -> float:
        """کارمزد ورود. هنگام باز شدن روی رکورد ذخیره می‌شود."""
        return self.round_trip_fee / 2.0

    @property
    def exit_fee(self) -> float:
        """کارمزد خروج. فقط همین مقدار به `close_trade` داده می‌شود."""
        return self.round_trip_fee / 2.0

    # ------------------------------------------------------------------
    # نسخهٔ ۲.۵.۶ — اقتصاد صادقانهٔ معامله
    # ------------------------------------------------------------------
    @property
    def target_move_percent(self) -> float:
        """حرکت قیمت لازم تا حد سود (درصد، شامل کارمزد)."""
        return self.gross_target / self.notional * 100.0 if self.notional > 0 else 0.0

    @property
    def stop_move_percent(self) -> float:
        """حرکت مخالف تا حد ضرر (درصد)."""
        return self.stop_distance / self.notional * 100.0 if self.notional > 0 else 0.0

    @property
    def breakeven_win_rate(self) -> float:
        """درصد برد لازم برای سربه‌سر: ضرر / (سود + ضرر)."""
        total = self.net_target + self.max_loss
        return self.max_loss / total * 100.0 if total > 0 else 100.0

    @property
    def random_win_rate(self) -> float:
        """
        درصد برد یک جهت بی‌برتری (قدم‌زدن تصادفی بدون رانش).

        احتمال رسیدن به +a پیش از −b برابر b/(a+b) است. چون کارمزد حد سود
        را دورتر و حد ضرر را نزدیک‌تر می‌کند، این عدد زیر حد سربه‌سر است.
        """
        total = self.gross_target + self.stop_distance
        return self.stop_distance / total * 100.0 if total > 0 else 0.0

    @property
    def no_edge_expectancy(self) -> float:
        """
        امید ریاضی دلاری هر معامله با جهت بی‌برتری ≈ −کارمزد رفت‌وبرگشت.

        این ریشهٔ ریاضی «همهٔ اسکالپ‌ها منفی‌اند» است: بدون برتری واقعی در
        جهت، هر معامله به‌طور میانگین همان کارمزد را از دست می‌دهد.
        """
        p = self.random_win_rate / 100.0
        return p * self.net_target - (1.0 - p) * self.max_loss

    def economics(self) -> dict[str, float]:
        """خلاصهٔ قابل نمایش/ثبت."""
        return {
            "target_move_percent": round(self.target_move_percent, 4),
            "stop_move_percent": round(self.stop_move_percent, 4),
            "breakeven_win_rate": round(self.breakeven_win_rate, 1),
            "random_win_rate": round(self.random_win_rate, 1),
            "no_edge_expectancy": round(self.no_edge_expectancy, 4),
            "round_trip_fee": round(self.round_trip_fee, 4),
        }


def plan_levels(
    margin: float,
    leverage: float,
    net_target: float,
    max_loss: float,
    fee_rate: float = DEFAULT_TAKER_FEE_RATE,
) -> MicroPlan:
    """
    تبدیل هدف خالص دلاری به فاصلهٔ قیمتی ناخالص.

    اگر کارمزد از حد ضرر بزرگ‌تر باشد، یک حد ضرر خیلی کوچک می‌ماند تا
    یک تیک مخالف معامله را ببندد و موقعیت بی‌سقف نماند.
    """
    margin = max(0.0, float(margin or 0.0))
    leverage = max(1.0, float(leverage or 1.0))
    fee_rate = max(0.0, float(fee_rate or 0.0))
    notional = margin * leverage
    round_trip = notional * fee_rate * 2.0
    target = max(0.0, float(net_target or 0.0))
    loss = max(0.0, float(max_loss or 0.0))
    adverse = loss - round_trip
    if adverse > 0:
        stop_distance = adverse
    else:
        stop_distance = 0.05
    return MicroPlan(
        margin=margin,
        leverage=leverage,
        net_target=target,
        max_loss=loss,
        fee_rate=fee_rate,
        notional=notional,
        round_trip_fee=round_trip,
        gross_target=target + round_trip,
        stop_distance=stop_distance,
    )


def exit_fee_from_notional(
    notional: float,
    fee_rate: float = DEFAULT_TAKER_FEE_RATE,
) -> float:
    """کارمزد یک طرف، از روی ارزش موقعیت. برای بستن دستی و پایش."""
    return max(0.0, float(notional or 0.0)) * max(0.0, float(fee_rate or 0.0))
