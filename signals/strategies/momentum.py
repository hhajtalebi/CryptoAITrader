"""
راهبرد مومنتوم.

منطق:
    مومنتوم یعنی «سرعت» حرکت قیمت، نه جهت آن. یک روند صعودی که سرعتش
    کم می‌شود، هنوز صعودی است ولی دیگر جای ورود نیست. این راهبرد از
    MACD، RSI و Stochastic استفاده می‌کند — سه سنجهٔ سرعت با پنجره‌های
    زمانی متفاوت.

چرا جداست؟
    کاربر گزارش کرد سیگنال‌های با اطمینان بالا ضرر دادند. ریشهٔ عددی
    ماجرا این بود که از سه راهبرد موجود، در بازار روندی عملاً فقط
    «دنبال‌کنندهٔ روند» رأی می‌داد و «بازگشت به میانگین» کنار می‌کشید.
    یک رأی، هرقدر قوی، شاهد مستقل کافی نیست. این راهبرد شاهد مستقل
    اضافه می‌کند تا اعداد بالا واقعاً پشتوانه داشته باشند.

شرط عدم کاربرد:
    اگر هیچ‌کدام از سه اندیکاتور محاسبه نشده باشند، رأی داده نمی‌شود.
"""

from __future__ import annotations

from signals.strategies.base import BaseStrategy, StrategyContext, StrategyVote


class MomentumStrategy(BaseStrategy):
    """راهبرد معامله بر پایه شتاب حرکت قیمت."""

    name = "momentum"
    weight = 1.0
    min_candles = 60

    def evaluate(self, context: StrategyContext) -> StrategyVote:
        """صدور رأی بر پایه هم‌سویی سنجه‌های شتاب."""
        score = 0.0
        reasons: list[str] = []
        seen = 0

        # --- MACD: تفاضل دو میانگین، سنجهٔ اصلی شتاب ---
        histogram = context.indicator_value("MACD", "histogram")
        if histogram is not None:
            seen += 1
            # هیستوگرام نسبت به قیمت نرمال می‌شود تا آستانه برای همهٔ
            # نمادها یکسان بماند؛ ۵۰ دلار روی بیت‌کوین و روی دوج‌کوین
            # دو معنای کاملاً متفاوت دارد.
            price = context.last_price or 1.0
            normalised = histogram / price * 100
            if normalised > 0.05:
                score += min(normalised / 0.5, 1.0) * 0.4
                reasons.append("MACD histogram is positive and expanding")
            elif normalised < -0.05:
                score -= min(abs(normalised) / 0.5, 1.0) * 0.4
                reasons.append("MACD histogram is negative and expanding")

        # --- RSI: شتاب میان‌مدت ---
        # اینجا RSI به‌عنوان «سنجهٔ شتاب» خوانده می‌شود نه اشباع، پس
        # منطقش عمداً با راهبرد بازگشت به میانگین فرق دارد.
        rsi = context.indicator_value("RSI", "rsi")
        if rsi is not None:
            seen += 1
            if rsi > 55:
                score += min((rsi - 55) / 25, 1.0) * 0.3
                reasons.append(f"RSI {rsi:.1f} confirms upward momentum")
            elif rsi < 45:
                score -= min((45 - rsi) / 25, 1.0) * 0.3
                reasons.append(f"RSI {rsi:.1f} confirms downward momentum")

        # --- Stochastic: شتاب کوتاه‌مدت ---
        stoch_k = context.indicator_value("STOCHASTIC", "k")
        stoch_d = context.indicator_value("STOCHASTIC", "d")
        if stoch_k is not None and stoch_d is not None:
            seen += 1
            if stoch_k > stoch_d and stoch_k < 80:
                score += 0.2
                reasons.append("Stochastic %K crossed above %D with room to run")
            elif stoch_k < stoch_d and stoch_k > 20:
                score -= 0.2
                reasons.append("Stochastic %K crossed below %D with room to fall")

        if seen == 0:
            return self._not_applicable("No momentum indicator is available")
        if not reasons:
            return self._not_applicable("Momentum is flat; no directional edge")

        # واگرایی: قیمت سقف تازه می‌زند ولی شتاب همراهی نمی‌کند.
        # این کلاسیک‌ترین هشدار پیش از برگشت است و باید امتیاز را
        # تضعیف کند، نه اینکه نادیده گرفته شود.
        if len(context.candles) >= 20:
            recent = context.candles[-20:]
            highest = max(candle.high for candle in recent)
            lowest = min(candle.low for candle in recent)
            last = context.candles[-1].close
            if rsi is not None:
                if last >= highest * 0.999 and rsi < 60:
                    score *= 0.5
                    reasons.append(
                        "Price is at a 20-bar high but RSI is not confirming — "
                        "possible bearish divergence"
                    )
                elif last <= lowest * 1.001 and rsi > 40:
                    score *= 0.5
                    reasons.append(
                        "Price is at a 20-bar low but RSI is not confirming — "
                        "possible bullish divergence"
                    )

        return self._vote(score, reasons)
