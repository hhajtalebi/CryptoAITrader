"""
راهبرد دنبال‌کننده روند.

منطق:
    در بازار روندی، هم‌سو شدن با روند بالاترین احتمال موفقیت را دارد.
    این راهبرد وقتی فعال می‌شود که ADX قدرت روند را تأیید کند و ساختار
    بازار با جهت میانگین‌های متحرک هم‌سو باشد.

شرط عدم کاربرد:
    اگر ADX زیر ۲۰ باشد، بازار رِنج است و این راهبرد رأی نمی‌دهد.
"""

from __future__ import annotations

from app.core.constants import MarketStructureType, TrendDirection
from signals.strategies.base import BaseStrategy, StrategyContext, StrategyVote


class TrendFollowingStrategy(BaseStrategy):
    """راهبرد هم‌سویی با روند غالب."""

    name = "trend_following"
    weight = 1.2
    min_candles = 60

    def evaluate(self, context: StrategyContext) -> StrategyVote:
        """صدور رأی بر پایه قدرت و جهت روند."""
        adx = context.indicator_value("ADX", "adx")
        if adx is None:
            return self._not_applicable("ADX is not available")
        if adx < 20:
            return self._not_applicable(f"ADX {adx:.1f} indicates a ranging market")

        score = 0.0
        reasons: list[str] = []

        # قدرت روند: هرچه ADX بالاتر، اطمینان بیشتر (سقف ۰٫۴)
        strength = min((adx - 20) / 30, 1.0) * 0.4

        # جهت از میانگین‌های متحرک
        ema = context.indicator_value("EMA", "ema")
        sma = context.indicator_value("SMA", "sma")
        price = context.last_price
        if ema and price:
            if price > ema:
                score += strength
                reasons.append(f"Price is above EMA ({price:.4g} > {ema:.4g}) with ADX {adx:.1f}")
            else:
                score -= strength
                reasons.append(f"Price is below EMA ({price:.4g} < {ema:.4g}) with ADX {adx:.1f}")
        if ema and sma:
            # فاصله معنادار لازم است؛ تقاطع‌های بسیار نزدیک نویز هستند
            separation = abs(ema - sma) / sma * 100 if sma else 0.0
            if separation < 0.1:
                reasons.append("Moving averages are entangled — no directional edge")
            elif ema > sma:
                score += 0.15
                reasons.append(f"EMA(21) is above SMA(50) by {separation:.2f}%")
            else:
                score -= 0.15
                reasons.append(f"EMA(21) is below SMA(50) by {separation:.2f}%")

        # هم‌سویی با تایم‌فریم بالاتر — مهم‌ترین فیلتر
        if context.higher_timeframe_trend == TrendDirection.BULLISH:
            score += 0.25
            reasons.append("Higher timeframe trend is bullish")
        elif context.higher_timeframe_trend == TrendDirection.BEARISH:
            score -= 0.25
            reasons.append("Higher timeframe trend is bearish")

        # تأیید ساختار
        if context.structure is not None:
            if context.structure.structure in (MarketStructureType.BULLISH, MarketStructureType.BREAKOUT):
                score += 0.2
                reasons.append(f"Market structure is {context.structure.structure.value}")
            elif context.structure.structure in (
                MarketStructureType.BEARISH,
                MarketStructureType.BREAKDOWN,
            ):
                score -= 0.2
                reasons.append(f"Market structure is {context.structure.structure.value}")

        return self._vote(score, reasons)
