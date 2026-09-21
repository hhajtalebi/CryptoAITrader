"""
موتور سیگنال موبایل — همان منطق دسکتاپ، بدون وابستگی سنگین.

طراحی عمداً با نسخهٔ دسکتاپ هم‌شکل است:
    * «منتظر» یک نتیجهٔ درجه‌یک است، نه شکست. اگر عامل‌ها هم‌سو نباشند،
      درست‌ترین پاسخ «فعلاً نه» است.
    * ضریب اطمینان از **هم‌سویی عامل‌ها** می‌آید، نه از یک عدد دلخواه.
    * حد ضرر بر پایهٔ ATR است تا با نوسان واقعی بازار تناسب داشته باشد.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import indicators_lite as ind

# آستانه‌ها با نسخهٔ دسکتاپ یکی هستند.
RSI_OVERSOLD = 30.0
RSI_OVERBOUGHT = 70.0
MIN_CANDLES = 60
MIN_CONFIDENCE_TO_TRADE = 45.0

# ضریب‌های حد ضرر و هدف بر حسب ATR.
STOP_ATR_MULTIPLIER = 1.5
TARGET_ATR_MULTIPLIERS = (1.5, 2.5, 4.0)


@dataclass
class MobileSignal:
    """یک سیگنال آمادهٔ نمایش روی گوشی."""

    symbol: str
    direction: str  # LONG | SHORT | WAIT
    price: float
    confidence: float
    entry_low: float = 0.0
    entry_high: float = 0.0
    stop_loss: float = 0.0
    take_profits: list[float] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    timeframe: str = ""
    valid_minutes: int = 0

    @property
    def is_tradeable(self) -> bool:
        """آیا این سیگنال ارزش اقدام دارد؟"""
        return self.direction != "WAIT" and self.confidence >= MIN_CONFIDENCE_TO_TRADE

    @property
    def risk_reward(self) -> float:
        """نسبت سود به زیان تا نخستین هدف."""
        if not self.take_profits or not self.stop_loss:
            return 0.0
        entry = (self.entry_low + self.entry_high) / 2 or self.price
        risk = abs(entry - self.stop_loss)
        if risk == 0:
            return 0.0
        return round(abs(self.take_profits[0] - entry) / risk, 2)


# مدت اعتبار هر سیگنال بر حسب تایم‌فریم — کاربر باید بداند تا کِی معتبر است.
_VALIDITY_MINUTES = {
    "1m": 15,
    "5m": 60,
    "15m": 180,
    "30m": 360,
    "1h": 720,
    "4h": 2880,
    "1d": 10080,
}


def analyse(
    symbol: str,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    timeframe: str = "1h",
) -> MobileSignal:
    """
    تحلیل کندل‌ها و تولید یک سیگنال.

    با دادهٔ ناکافی، «منتظر» با اطمینان صفر برمی‌گردد — نه استثنا و نه
    حدس. نمایش یک سیگنال ساختگی روی دادهٔ ناقص، بدترین کار ممکن است.
    """
    price = closes[-1] if closes else 0.0
    if len(closes) < MIN_CANDLES:
        return MobileSignal(
            symbol=symbol,
            direction="WAIT",
            price=price,
            confidence=0.0,
            reasons=[f"دادهٔ کافی نیست ({len(closes)} از {MIN_CANDLES} کندل)"],
            timeframe=timeframe,
        )

    rsi_series = ind.rsi(closes, 14)
    macd_data = ind.macd(closes)
    ema_fast = ind.ema(closes, 20)
    ema_slow = ind.ema(closes, 50)
    atr_series = ind.atr(highs, lows, closes, 14)
    bands = ind.bollinger(closes, 20, 2.0)

    bullish: list[str] = []
    bearish: list[str] = []

    rsi_now = rsi_series[-1]
    if rsi_now is not None:
        if rsi_now < RSI_OVERSOLD:
            bullish.append(f"RSI در ناحیهٔ اشباع فروش ({rsi_now:.1f})")
        elif rsi_now > RSI_OVERBOUGHT:
            bearish.append(f"RSI در ناحیهٔ اشباع خرید ({rsi_now:.1f})")

    hist = macd_data["histogram"][-1]
    if hist is not None:
        if hist > 0:
            bullish.append("هیستوگرام مکدی مثبت")
        elif hist < 0:
            bearish.append("هیستوگرام مکدی منفی")

    fast_now, slow_now = ema_fast[-1], ema_slow[-1]
    if fast_now is not None and slow_now is not None:
        if fast_now > slow_now:
            bullish.append("میانگین ۲۰ بالای میانگین ۵۰ (روند صعودی)")
        else:
            bearish.append("میانگین ۲۰ زیر میانگین ۵۰ (روند نزولی)")

    lower, upper = bands["lower"][-1], bands["upper"][-1]
    if lower is not None and price < lower:
        bullish.append("قیمت زیر باند پایینی بولینگر")
    if upper is not None and price > upper:
        bearish.append("قیمت بالای باند بالایی بولینگر")

    total = len(bullish) + len(bearish)
    if total == 0:
        return MobileSignal(
            symbol=symbol,
            direction="WAIT",
            price=price,
            confidence=0.0,
            reasons=["هیچ عامل روشنی دیده نشد"],
            timeframe=timeframe,
        )

    # اطمینان = میزان هم‌سویی عامل‌ها، نه صرفاً تعدادشان.
    if len(bullish) > len(bearish):
        direction, aligned, reasons = "LONG", len(bullish), bullish
    elif len(bearish) > len(bullish):
        direction, aligned, reasons = "SHORT", len(bearish), bearish
    else:
        # تساوی یعنی بازار تصمیم ندارد؛ ما هم نباید داشته باشیم.
        return MobileSignal(
            symbol=symbol,
            direction="WAIT",
            price=price,
            confidence=40.0,
            reasons=["عامل‌های صعودی و نزولی برابرند"],
            timeframe=timeframe,
        )

    confidence = round(100.0 * aligned / total, 1)
    atr_now = atr_series[-1] or (price * 0.01)
    band = atr_now * 0.15

    if direction == "LONG":
        stop = price - STOP_ATR_MULTIPLIER * atr_now
        targets = [price + m * atr_now for m in TARGET_ATR_MULTIPLIERS]
    else:
        stop = price + STOP_ATR_MULTIPLIER * atr_now
        targets = [price - m * atr_now for m in TARGET_ATR_MULTIPLIERS]

    return MobileSignal(
        symbol=symbol,
        direction=direction,
        price=price,
        confidence=confidence,
        entry_low=round(price - band, 6),
        entry_high=round(price + band, 6),
        stop_loss=round(stop, 6),
        take_profits=[round(t, 6) for t in targets],
        reasons=reasons,
        timeframe=timeframe,
        valid_minutes=_VALIDITY_MINUTES.get(timeframe, 720),
    )
