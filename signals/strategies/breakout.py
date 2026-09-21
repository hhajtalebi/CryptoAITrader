"""
راهبرد شکست سطوح.

منطق:
    شکست معتبر، سه نشانه دارد: عبور قیمت از کانال/سطح، افزایش حجم، و
    گسترش نوسان. شکست بدون حجم معمولاً تله است، بنابراین حجم در این
    راهبرد نقش تأییدکننده اجباری دارد.

شرط عدم کاربرد:
    اگر هیچ نشانه شکستی در اندیکاتورها نباشد، رأی داده نمی‌شود.
"""

from __future__ import annotations

from app.core.constants import MarketStructureType
from signals.strategies.base import BaseStrategy, StrategyContext, StrategyVote


class BreakoutStrategy(BaseStrategy):
    """راهبرد معامله بر پایه شکست سطوح و کانال‌ها."""

    name = "breakout"
    weight = 1.0
    min_candles = 60

    def evaluate(self, context: StrategyContext) -> StrategyVote:
        """صدور رأی بر پایه شکست کانال دانچیان/کِلتنر و تأیید حجم."""
        score = 0.0
        reasons: list[str] = []

        for indicator in ("DONCHIAN", "KELTNER"):
            signal = context.indicator_signal(indicator)
            if signal == "BREAKOUT_UP":
                score += 0.3
                reasons.append(f"{indicator} breakout to the upside")
            elif signal == "BREAKOUT_DOWN":
                score -= 0.3
                reasons.append(f"{indicator} breakdown to the downside")

        # ساختار: شکست ساختاری تأیید قوی است
        if context.structure is not None:
            if context.structure.structure == MarketStructureType.BREAKOUT:
                score += 0.25
                reasons.append("Market structure confirms a breakout")
            elif context.structure.structure == MarketStructureType.BREAKDOWN:
                score -= 0.25
                reasons.append("Market structure confirms a breakdown")

        if not reasons:
            return self._not_applicable("No breakout condition is present")

        # تأیید حجم — بدون آن، امتیاز به‌شدت کاهش می‌یابد
        volume_signal = context.indicator_signal("VOLUME_SMA")
        volume_ratio = context.indicator_value("VOLUME_SMA", "volume_ratio")
        if volume_signal == "VOLUME_SPIKE":
            score *= 1.25
            reasons.append(f"Volume spike confirms the move (ratio {volume_ratio:.2f}x)" if volume_ratio else "Volume spike confirms the move")
        elif volume_signal == "LOW_VOLUME":
            score *= 0.4
            reasons.append("Low volume — the breakout is unconfirmed and may be a trap")

        # فشردگی پیش از شکست، اعتبار را بالا می‌برد
        if context.indicator_signal("BBANDS") == "SQUEEZE":
            score *= 1.15
            reasons.append("Bollinger squeeze preceded the move")

        return self._vote(score, reasons)
