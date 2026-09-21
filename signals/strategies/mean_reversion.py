"""
راهبرد بازگشت به میانگین.

منطق:
    در بازار بدون روند، قیمت تمایل دارد پس از دور شدن بیش از حد از
    میانگین، به آن بازگردد. اشباع فروش در نزدیکی حمایت، و اشباع خرید در
    نزدیکی مقاومت، بهترین موقعیت‌های این راهبرد هستند.

شرط عدم کاربرد:
    اگر ADX بالای ۳۰ باشد، روند قوی است و شرط‌بندی روی بازگشت خطرناک
    است — این راهبرد کنار می‌کشد. این دقیقاً نقطه مقابل راهبرد روندی است
    و همین تضاد، جمع‌بندی را متعادل نگه می‌دارد.
"""

from __future__ import annotations

from signals.strategies.base import BaseStrategy, StrategyContext, StrategyVote


class MeanReversionStrategy(BaseStrategy):
    """راهبرد بازگشت قیمت به میانگین."""

    name = "mean_reversion"
    weight = 0.9
    min_candles = 60

    def evaluate(self, context: StrategyContext) -> StrategyVote:
        """صدور رأی بر پایه اشباع خرید/فروش و موقعیت نسبت به باندها."""
        adx = context.indicator_value("ADX", "adx")
        if adx is not None and adx > 30:
            return self._not_applicable(f"ADX {adx:.1f} shows a strong trend; reversion is unsafe")

        rsi = context.indicator_value("RSI", "rsi")
        if rsi is None:
            return self._not_applicable("RSI is not available")

        score = 0.0
        reasons: list[str] = []

        # اشباع فروش → احتمال بازگشت صعودی
        if rsi < 30:
            score += 0.35 + min((30 - rsi) / 30, 1.0) * 0.15
            reasons.append(f"RSI {rsi:.1f} is oversold")
        elif rsi > 70:
            score -= 0.35 + min((rsi - 70) / 30, 1.0) * 0.15
            reasons.append(f"RSI {rsi:.1f} is overbought")

        # موقعیت نسبت به باند بولینگر
        percent_b = context.indicator_value("BBANDS", "percent_b")
        if percent_b is not None:
            if percent_b < 0.05:
                score += 0.25
                reasons.append("Price is at or below the lower Bollinger band")
            elif percent_b > 0.95:
                score -= 0.25
                reasons.append("Price is at or above the upper Bollinger band")

        # تأیید با استوکاستیک
        stoch_signal = context.indicator_signal("STOCH")
        if stoch_signal == "OVERSOLD":
            score += 0.15
            reasons.append("Stochastic is oversold")
        elif stoch_signal == "OVERBOUGHT":
            score -= 0.15
            reasons.append("Stochastic is overbought")

        # نزدیکی به سطح کلیدی، کیفیت ستاپ را بالا می‌برد
        price = context.last_price
        for level in context.levels:
            if abs(level.distance_percent) > 1.0:
                continue
            if level.kind == "support" and level.price <= price and score > 0:
                score += 0.15
                reasons.append(f"Price is testing {level.strength} support at {level.price:.4g}")
                break
            if level.kind == "resistance" and level.price >= price and score < 0:
                score -= 0.15
                reasons.append(f"Price is testing {level.strength} resistance at {level.price:.4g}")
                break

        if not reasons:
            return self._not_applicable("No mean-reversion condition is present")
        return self._vote(score, reasons)
