"""
موتور مدیریت ریسک.

چرا وجود دارد؟
    بند ۲۷ سند پروژه: حد ضرر باید بر پایه ساختار واقعی بازار و نوسان
    (ATR) محاسبه شود، نه یک درصد دلخواه. این موتور تنها مرجع تصمیم‌گیری
    درباره «آیا این ستاپ قابل قبول است؟» است.

فلسفه محافظه‌کارانه:
    حفظ سرمایه بر سود مقدم است. اگر ستاپی شرایط را نداشته باشد، موتور آن
    را رد می‌کند و موتور سیگنال به WAIT تبدیلش می‌کند. هرگز برای «داشتن
    سیگنال» شرایط را شل نمی‌کنیم.
"""

from __future__ import annotations

from app.core.constants import SignalDirection
from app.core.models import RiskAssessment, RiskParameters, SupportResistanceLevel
from app.logging import get_logger

logger = get_logger(__name__)

#: رواداری مقایسه اعداد اعشاری.
#: اهداف سود از ضرب در ضریب ریسک ساخته و سپس گرد می‌شوند؛ همین گرد کردن
#: می‌تواند نسبتی مثل ۱٫۵ را به ۱٫۴۹۹۹۹۹۹۹ تبدیل کند. بدون این رواداری،
#: ستاپی که دقیقاً حداقل کاربر را برآورده می‌کند به‌اشتباه رد می‌شود.
FLOAT_TOLERANCE = 1e-6


class RiskEngine:
    """
    محاسبه‌گر و داور ریسک.

    نمونه‌سازی با تزریق پارامترهای کاربر:
        engine = RiskEngine(RiskParameters(account_balance=1000, risk_percent=1))
    """

    def __init__(self, parameters: RiskParameters | None = None) -> None:
        self._params = parameters or RiskParameters()

    @property
    def parameters(self) -> RiskParameters:
        """پارامترهای ریسک فعلی."""
        return self._params

    def set_parameters(self, parameters: RiskParameters) -> None:
        """به‌روزرسانی پارامترها از تنظیمات کاربر."""
        self._params = parameters

    # ------------------------------------------------------------------
    # محاسبه حد ضرر
    # ------------------------------------------------------------------
    def calculate_stop_loss(
        self,
        direction: SignalDirection,
        entry: float,
        atr: float | None,
        levels: list[SupportResistanceLevel] | None = None,
        swing_high: float | None = None,
        swing_low: float | None = None,
    ) -> tuple[float, str]:
        """
        محاسبه حد ضرر بر پایه ساختار بازار و نوسان.

        راهبرد دو لایه:
            ۱) اگر کف/سقف نوسانی معتبری وجود دارد، حد ضرر کمی آن‌سوتر
               قرار می‌گیرد (شکست ساختار = ابطال تحلیل).
            ۲) در غیر این صورت، فاصله ATR × ضریب استفاده می‌شود.

        همیشه سخت‌گیرانه‌ترین (دورترِ منطقی) گزینه انتخاب می‌شود تا حد ضرر
        در نوسان معمولی بازار فعال نشود.

        بازگشتی: (قیمت حد ضرر، توضیح روش)
        """
        atr_value = atr if atr and atr > 0 else entry * 0.01
        atr_distance = atr_value * self._params.atr_stop_multiplier

        atr_stop = entry - atr_distance if direction == SignalDirection.LONG else entry + atr_distance
        structural_stop: float | None = None

        # لایه ۱: ساختار
        if direction == SignalDirection.LONG:
            candidates = [swing_low] if swing_low else []
            candidates += [
                lvl.price for lvl in (levels or []) if lvl.kind == "support" and lvl.price < entry
            ]
            valid = [c for c in candidates if c and c < entry]
            if valid:
                # نزدیک‌ترین حمایت زیر ورود، با کمی حاشیه امن
                structural_stop = max(valid) - atr_value * 0.25
        else:
            candidates = [swing_high] if swing_high else []
            candidates += [
                lvl.price for lvl in (levels or []) if lvl.kind == "resistance" and lvl.price > entry
            ]
            valid = [c for c in candidates if c and c > entry]
            if valid:
                structural_stop = min(valid) + atr_value * 0.25

        if structural_stop is None:
            chosen = atr_stop
            method = "ATR-based (no valid structural level found)"
        else:
            # انتخاب دورتر تا حد ضرر خیلی تنگ نشود
            if direction == SignalDirection.LONG:
                chosen = min(structural_stop, atr_stop)
            else:
                chosen = max(structural_stop, atr_stop)
            method = (
                "structural" if chosen == structural_stop else "ATR-based (structure was too tight)"
            )

        # محافظ: حد ضرر نباید بیش از سقف مجاز کاربر فاصله بگیرد
        max_distance = entry * (self._params.max_stop_distance_percent / 100)
        if abs(entry - chosen) > max_distance:
            chosen = entry - max_distance if direction == SignalDirection.LONG else entry + max_distance
            method = f"clamped to max {self._params.max_stop_distance_percent:g}% distance"

        return round(chosen, 8), method

    # ------------------------------------------------------------------
    # محاسبه اهداف سود
    # ------------------------------------------------------------------
    def calculate_take_profits(
        self,
        direction: SignalDirection,
        entry: float,
        stop_loss: float,
        levels: list[SupportResistanceLevel] | None = None,
    ) -> list[float]:
        """
        محاسبه سه هدف سود.

        ابتدا سطوح واقعی بازار (مقاومت برای خرید، حمایت برای فروش) بررسی
        می‌شوند؛ اگر سطح کافی نبود، مضارب ریسک (۱٫۵R، ۲٫۵R، ۴R) به کار
        می‌روند تا اهداف همیشه سه‌تایی و منطقی باشند.
        """
        risk = abs(entry - stop_loss)
        if risk <= 0:
            return []

        wanted_kind = "resistance" if direction == SignalDirection.LONG else "support"
        structural: list[float] = []
        for level in levels or []:
            if level.kind != wanted_kind:
                continue
            if direction == SignalDirection.LONG and level.price > entry:
                structural.append(level.price)
            elif direction == SignalDirection.SHORT and level.price < entry:
                structural.append(level.price)

        structural.sort(reverse=direction == SignalDirection.SHORT)
        # فقط اهدافی که دست‌کم ۱ برابر ریسک فاصله دارند ارزش دارند
        structural = [p for p in structural if abs(p - entry) >= risk * 1.0][:3]

        multipliers = [1.5, 2.5, 4.0]
        targets: list[float] = list(structural)
        for multiplier in multipliers:
            if len(targets) >= 3:
                break
            target = (
                entry + risk * multiplier
                if direction == SignalDirection.LONG
                else entry - risk * multiplier
            )
            # از هدف‌های خیلی نزدیک به اهداف ساختاری پرهیز می‌کنیم
            if all(abs(target - existing) > risk * 0.3 for existing in targets):
                targets.append(target)

        targets = sorted(targets, reverse=direction == SignalDirection.SHORT)[:3]
        return [round(t, 8) for t in targets]

    # ------------------------------------------------------------------
    # ارزیابی کامل
    # ------------------------------------------------------------------
    def assess(
        self,
        direction: SignalDirection,
        entry: float,
        stop_loss: float,
        take_profits: list[float],
        atr: float | None = None,
        *,
        confidence: int = 50,
    ) -> RiskAssessment:
        """
        ارزیابی نهایی یک ستاپ.

        شرایط رد شدن:
            • حد ضرر در جهت اشتباه
            • نسبت ریسک به ریوارد کمتر از حداقل کاربر
            • فاصله حد ضرر بیش از سقف مجاز
            • حد ضرر تنگ‌تر از یک ATR (احتمال فعال شدن با نوسان معمولی)
        """
        stop_distance = abs(entry - stop_loss)
        if entry <= 0 or stop_distance <= 0:
            return RiskAssessment(
                stop_distance_percent=0.0,
                risk_reward=0.0,
                suggested_leverage=1,
                position_size=0.0,
                risk_amount=0.0,
                atr_value=atr,
                volatility_note="",
                approved=False,
                rejection_reason="Invalid entry or stop loss",
            )

        stop_distance_percent = stop_distance / entry * 100
        risk_reward = abs(take_profits[0] - entry) / stop_distance if take_profits else 0.0
        risk_amount = self._params.account_balance * (self._params.risk_percent / 100)
        position_size = risk_amount / stop_distance

        leverage = self._suggest_leverage(stop_distance_percent)
        volatility_note = self._volatility_note(atr, entry, stop_distance)

        approved = True
        rejection: list[str] = []

        wrong_side = (direction == SignalDirection.LONG and stop_loss >= entry) or (
            direction == SignalDirection.SHORT and stop_loss <= entry
        )
        if wrong_side:
            approved = False
            rejection.append("Stop loss is on the wrong side of entry")

        if risk_reward < self._params.min_risk_reward - FLOAT_TOLERANCE:
            approved = False
            rejection.append(
                f"Risk/reward {risk_reward:.2f} is below the minimum {self._params.min_risk_reward:g}"
            )

        if stop_distance_percent > self._params.max_stop_distance_percent + FLOAT_TOLERANCE:
            approved = False
            rejection.append(
                f"Stop distance {stop_distance_percent:.2f}% exceeds the maximum "
                f"{self._params.max_stop_distance_percent:g}%"
            )

        if atr and atr > 0 and stop_distance < atr - FLOAT_TOLERANCE:
            approved = False
            rejection.append("Stop loss is tighter than one ATR — likely to be hit by normal noise")

        return RiskAssessment(
            stop_distance_percent=round(stop_distance_percent, 3),
            risk_reward=round(risk_reward, 2),
            suggested_leverage=leverage,
            position_size=round(position_size, 8),
            risk_amount=round(risk_amount, 4),
            atr_value=round(atr, 8) if atr else None,
            volatility_note=volatility_note,
            approved=approved,
            rejection_reason="; ".join(rejection),
        )

    # ------------------------------------------------------------------
    # کمکی‌ها
    # ------------------------------------------------------------------
    def _suggest_leverage(self, stop_distance_percent: float) -> int:
        """
        اهرم پیشنهادی محافظه‌کارانه.

        منطق: اهرم طوری انتخاب می‌شود که فعال شدن حد ضرر، حداکثر حدود ۱۰
        درصد از مارجین پوزیشن را از بین ببرد. هرچه حد ضرر دورتر باشد، اهرم
        کمتر می‌شود. سقف نهایی همیشه محدودیت کاربر است.
        """
        if stop_distance_percent <= 0:
            return 1
        raw = 10.0 / stop_distance_percent
        return max(1, min(int(raw), self._params.max_leverage))

    @staticmethod
    def _volatility_note(atr: float | None, entry: float, stop_distance: float) -> str:
        """توضیح کوتاه درباره وضعیت نوسان، برای نمایش به کاربر."""
        if not atr or atr <= 0 or entry <= 0:
            return "ATR unavailable; volatility could not be assessed"
        atr_percent = atr / entry * 100
        ratio = stop_distance / atr
        if atr_percent > 3:
            level = "very high"
        elif atr_percent > 1.5:
            level = "high"
        elif atr_percent > 0.7:
            level = "moderate"
        else:
            level = "low"
        return f"ATR is {atr_percent:.2f}% of price ({level} volatility); stop is {ratio:.2f}x ATR"
