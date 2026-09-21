"""
راهبرد رژیم نوسان.

منطق:
    بازار همیشه بین دو حالت می‌چرخد: فشرده‌شدن و انبساط. نوسانِ فشرده،
    انرژی ذخیره‌شده است و معمولاً به حرکت بزرگ ختم می‌شود؛ نوسانِ
    منبسط‌شده یعنی حرکت از قبل انجام شده و ورود در انتهای آن پرخطر است.

چرا برای فیوچرز مهم است؟
    با اهرم، ورود در اوج نوسان یعنی خوردن حد ضرر به‌خاطر نوسان معمولی
    بازار — نه به‌خاطر اشتباه در جهت. کاربر گزارش کرد سیگنال‌های با
    اطمینان بالا ضرر دادند؛ ورود در اوج نوسان یکی از دلایل رایج همین
    الگوست: جهت درست بود ولی معامله پیش از رسیدن به هدف، استاپ خورد.

این راهبرد جهت را از ساختار می‌گیرد و شدت رأی را بر اساس رژیم نوسان
تعیین می‌کند؛ در نوسان بسیار بالا عمداً محتاط می‌شود.
"""

from __future__ import annotations

from app.core.constants import TrendDirection
from signals.strategies.base import BaseStrategy, StrategyContext, StrategyVote


class VolatilityRegimeStrategy(BaseStrategy):
    """راهبرد سنجش رژیم نوسان و کیفیت زمان ورود."""

    name = "volatility_regime"
    weight = 0.9
    min_candles = 60

    def evaluate(self, context: StrategyContext) -> StrategyVote:
        """صدور رأی بر پایه فشردگی یا انبساط نوسان."""
        atr = context.indicator_value("ATR", "atr")
        if atr is None or context.last_price <= 0:
            return self._not_applicable("ATR is not available")

        # ATR به درصد قیمت تبدیل می‌شود تا بین نمادها قابل مقایسه باشد.
        atr_percent = atr / context.last_price * 100

        candles = context.candles
        if len(candles) < 30:
            return self._not_applicable("Not enough history to judge the volatility regime")

        # میانگین دامنهٔ ۳۰ کندل اخیر به‌عنوان «نوسان عادی» این نماد.
        ranges = [c.high - c.low for c in candles[-30:] if c.high > c.low]
        if not ranges:
            return self._not_applicable("Candle ranges are degenerate")
        average_range = sum(ranges) / len(ranges)
        if average_range <= 0:
            return self._not_applicable("Average range is zero")

        ratio = atr / average_range

        # جهت از روند می‌آید؛ این راهبرد جهت نمی‌سازد، کیفیت ورود را
        # می‌سنجد. اگر جهتی در کار نباشد، رأیی هم در کار نیست.
        if context.trend == TrendDirection.BULLISH:
            base = 0.45
        elif context.trend == TrendDirection.BEARISH:
            base = -0.45
        else:
            return self._not_applicable("No directional trend to qualify")

        reasons: list[str] = []

        if ratio < 0.75:
            # فشردگی: بهترین حالت برای ورود، چون حد ضرر نزدیک می‌ماند.
            score = base * 1.3
            reasons.append(
                f"Volatility is compressed (ATR {atr_percent:.2f}% of price, "
                f"{ratio:.2f}x its own average) — a favourable entry with a tight stop"
            )
        elif ratio > 1.6:
            # انبساط شدید: حرکت انجام شده؛ ورود دیرهنگام است.
            score = base * 0.35
            reasons.append(
                f"Volatility is expanded ({ratio:.2f}x average) — the move is likely "
                f"mature and a normal swing could hit the stop"
            )
        else:
            score = base * 0.8
            reasons.append(
                f"Volatility is normal (ATR {atr_percent:.2f}% of price)"
            )

        # نوسان مطلقاً بالا برای معاملهٔ اهرمی خطرناک است، فارغ از نسبت.
        if atr_percent > 5.0:
            score *= 0.5
            reasons.append(
                f"ATR is {atr_percent:.2f}% of price — extreme for a leveraged position"
            )

        # تأیید باند بولینگر در صورت وجود: فشردگی باند، همان سیگنال
        # فشردگی است از منبعی مستقل.
        bandwidth = context.indicator_value("BOLLINGER", "bandwidth")
        if bandwidth is not None and bandwidth < 2.0:
            score *= 1.15
            reasons.append(f"Bollinger bandwidth {bandwidth:.2f}% confirms the squeeze")

        return self._vote(score, reasons)
