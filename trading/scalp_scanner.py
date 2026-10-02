"""
پویشگر اسکلپ — یافتن ارزهایی که همین حالا فرصت کوتاه‌مدت دارند.

این ماژول **ریاضی خالص** است و هیچ تماسی با هوش مصنوعی ندارد. دلیلش
ساده است: چرخیدن روی هزار ارز با هوش مصنوعی هم کند است و هم توکن
می‌سوزاند. پویشگر فهرست را به چند نامزد کاهش می‌دهد و **بعد** می‌توان
آن چند تا را به هوش مصنوعی داد.

### درس مهمی که از دادهٔ زنده گرفتیم

نخستین اجرای آزمایشی روی دادهٔ واقعی، این‌ها را به‌عنوان «بهترین
فرصت» برگرداند:

    EXBT/USDT   +315%   حجم ۲۴ ساعته: ۶۷ دلار
    MYTH/USDT    -59%   حجم ۲۴ ساعته:  ۴ دلار

این‌ها فرصت نیستند، **تله‌اند**. با حجم چهار دلار در روز، شما می‌توانید
وارد شوید ولی هرگز نمی‌توانید خارج شوید — و اسکلپ یعنی خروج سریع.
نوسان بدون نقدینگی برای اسکلپ بی‌ارزش است.

به همین دلیل `min_turnover` یک فیلتر **سخت** است و پیش از هر محاسبهٔ
دیگری اعمال می‌شود. این تنها مهم‌ترین محافظ این فایل است.
"""

from __future__ import annotations

import math

from collections.abc import Callable
from dataclasses import dataclass, field

from typing import Any

from app.core.models import Candle, Ticker

# حداقل گردش مالی ۲۴ ساعته به دلار. زیر این عدد، خروج سریع ممکن نیست.
DEFAULT_MIN_TURNOVER = 2_000_000.0

# کف و سقف نوسان ۵ دقیقه‌ای (درصد). خیلی آرام یعنی فرصتی نیست؛ خیلی
# دیوانه یعنی حد ضرر بی‌معنا می‌شود.
DEFAULT_MIN_VOLATILITY = 0.15
DEFAULT_MAX_VOLATILITY = 3.0

# سقف فاصلهٔ خرید و فروش (درصد). اسپرد پهن، سود اسکلپ را می‌بلعد.
# عدد ۰٫۲۵ از اندازه‌گیری واقعی آمده: جفت‌های نقدشوندهٔ سالم بین ۰٫۰۳
# تا ۰٫۳۵ درصد‌اند. سقف ۰٫۱۲ قبلی حتی AVAX را هم رد می‌کرد.
DEFAULT_MAX_SPREAD = 0.25

#: کارمزد رفت‌وبرگشت تقریبی در صرافی‌های معمول (درصد).
#: هدف سود باید از این بیشتر باشد وگرنه معامله از پیش بازنده است.
ROUND_TRIP_FEE_PERCENT = 0.12

#: نسخهٔ ۲.۵.۶ — نوسان ۵ دقیقه‌ای باید دست‌کم این چند برابر هزینهٔ
#: رفت‌وبرگشت (کارمزد + اسپرد) باشد. تشخیص ۲.۵.۶ روی ۱۳٬۳۵۱ معاملهٔ
#: شبیه‌سازی‌شده نشان داد جهت اسکالپ عملاً شیرِ یا خط است و هزینه زیان را
#: می‌سازد؛ هرچه نوسان نسبت به هزینه بزرگ‌تر، سهم هزینه در هر معامله کمتر
#: (k=0: −۰٫۳۹R، k=4: −۰٫۲۲R، k=6: −۰٫۱۵R). ۰ = غیرفعال.
DEFAULT_MIN_COST_MULTIPLE = 3.0


@dataclass
class ScalpCandidate:
    """یک نامزد معاملهٔ کوتاه‌مدت."""

    symbol: str
    price: float
    score: float
    direction: str  # LONG | SHORT
    volatility_5m: float
    turnover_24h: float
    spread_percent: float
    momentum: float
    reasons: list[str] = field(default_factory=list)

    #: سود خالص **اگر جهت درست باشد** (۰٫۶ × نوسان − کارمزد − اسپرد)، درصد.
    #: این «سقف» است، نه امید ریاضی: بدون برتری جهت، امید ریاضی هر معامله
    #: تقریباً منفیِ هزینهٔ رفت‌وبرگشت است (نگاه کنید به no_edge_expectancy_percent).
    expected_net_percent: float = 0.0
    #: نسخهٔ ۲.۵.۶ — هزینهٔ رفت‌وبرگشت (کارمزد + اسپرد)، درصد
    cost_percent: float = 0.0
    #: نسخهٔ ۲.۵.۵ — جهت از کجا آمده: "momentum" (فقط اسکنر) یا
    #: "evidence" (حل‌کنندهٔ چندتایم‌فریمی). اسکنر نامزد پیدا می‌کند؛
    #: جهت نهایی با شواهد ۱m/۵m/۱۵m/۱h/۴h + جریان سفارش تعیین می‌شود.
    direction_source: str = "momentum"
    #: قدرت شواهد جهت ∈ [0, 1] (۰ = نامعلوم)
    conviction: float = 0.0
    #: سوگیری هر شاهد ∈ [-1, 1] (مثبت = خرید) برای نمایش و یادگیری
    evidence: dict[str, float] = field(default_factory=dict)

    @property
    def volatility_per_second(self) -> float:
        """
        برآورد نوسان ثانیه‌ای (درصد) از میانگین دامنهٔ کندل ۵ دقیقه‌ای — ۲.۵.۷.

        دامنهٔ یک بازهٔ براونی به‌طور میانگین ≈ ۱٫۶σ√T است؛ پس σ ≈ دامنه ÷
        (۱٫۶×√۳۰۰). موتور خودکار با آن دسترس‌پذیری هدف را می‌سنجد.
        """
        if self.volatility_5m <= 0:
            return 0.0
        return self.volatility_5m / (1.6 * math.sqrt(300.0))

    @property
    def breakeven_win_rate(self) -> float:
        """
        درصد بردی که لازم است تا با حد سود/ضرر متقارن ±۰٫۶ نوسان سر به سر شود.

        بالای ۵۰٪ یعنی هزینه باید با برتری جهت جبران شود؛ یک جهت تصادفی
        (۵۰٪) در این حالت به‌طور میانگین زیان می‌دهد.
        """
        move = self.volatility_5m * 0.6
        if move <= 0:
            return 100.0
        return max(0.0, min(100.0, (move + self.cost_percent) / (2.0 * move) * 100.0))

    @property
    def no_edge_expectancy_percent(self) -> float:
        """امید ریاضی خالص هر معامله با جهت بی‌برتری (۵۰/۵۰) = −هزینه."""
        return -self.cost_percent

    def projected_profit(self, margin: float, leverage: float) -> float:
        """
        سود تخمینی به دلار برای مارجین و اهرم داده‌شده.

        عمداً **خالص** است: کارمزد رفت‌وبرگشت کم شده. نمایش سود ناخالص
        به کاربر، عددی می‌دهد که هرگز به آن نمی‌رسد.
        """
        return margin * leverage * (self.expected_net_percent / 100.0)

    def required_move_percent(self, target_profit: float, margin: float, leverage: float) -> float:
        """
        بازار چند درصد باید حرکت کند تا این مقدار سود خالص بدهد؟

        این تابع جایی است که انتظارهای غیرواقعی آشکار می‌شوند.
        """
        notional = margin * leverage
        if notional <= 0:
            return float("inf")
        return (target_profit / notional) * 100.0 + ROUND_TRIP_FEE_PERCENT


def _percentile(values: list[float], fraction: float) -> float:
    """صدک ساده بدون numpy (نسخهٔ موبایل هم بتواند استفاده کند)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction)))
    return ordered[index]


def recent_volatility(candles: list[Candle]) -> float:
    """
    میانگین دامنهٔ هر کندل بر حسب درصد.

    این «نوسان قابل بهره‌برداری» است: اگر هر کندل ۵ دقیقه‌ای به‌طور
    میانگین ۰٫۴٪ دامنه دارد، هدف ۰٫۳٪ منطقی است و هدف ۳٪ خیال.
    """
    if not candles:
        return 0.0
    ranges = [
        (candle.high - candle.low) / candle.low * 100.0
        for candle in candles
        if candle.low > 0
    ]
    return sum(ranges) / len(ranges) if ranges else 0.0


def momentum_percent(candles: list[Candle], lookback: int = 6) -> float:
    """تغییر قیمت در چند کندل اخیر — جهت حرکت کوتاه‌مدت."""
    if len(candles) < lookback + 1:
        return 0.0
    old = candles[-lookback - 1].close
    new = candles[-1].close
    return (new - old) / old * 100.0 if old else 0.0


def passes_liquidity(ticker: Ticker, min_turnover: float = DEFAULT_MIN_TURNOVER) -> bool:
    """
    آیا این نماد به‌اندازهٔ کافی نقد هست که بتوان سریع خارج شد؟

    مهم‌ترین فیلتر کل ماژول. دادهٔ زنده نشان داد بیشترین نوسان‌گرها
    حجمی در حد چند دلار در روز دارند.
    """
    return float(ticker.turnover_24h or 0.0) >= min_turnover


def spread_from_orderbook(orderbook: Any) -> float:
    """
    اسپرد واقعی از دفتر سفارش — تنها منبع درست.

    چرا تخمین از دامنهٔ ۲۴ ساعته کنار گذاشته شد؟
        اندازه‌گیری روی دادهٔ زنده نشان داد آن تخمین تا **۱۱ برابر**
        خطا دارد. برای `INJ/USDT` عدد ۰٫۱۹٪ می‌داد در حالی که اسپرد
        واقعی ۰٫۰۳٪ بود — یعنی یک نماد کاملاً سالم را رد می‌کرد. و
        برعکس، برای `OAI/USDT` عدد ۱٫۸٪ می‌داد در حالی که اسپرد واقعی
        **۱۱٫۸٪** بود؛ یعنی یک تلهٔ واقعی را سالم نشان می‌داد.

        هر دو خطا خطرناک‌اند، ولی دومی پول می‌سوزاند.
    """
    bids = getattr(orderbook, "bids", None) or []
    asks = getattr(orderbook, "asks", None) or []
    if not bids or not asks:
        # دفتر خالی یعنی نقدینگی نیست؛ بدترین حالت فرض می‌شود.
        return 100.0
    bid = float(getattr(bids[0], "price", 0.0) or 0.0)
    ask = float(getattr(asks[0], "price", 0.0) or 0.0)
    if bid <= 0 or ask <= 0:
        return 100.0
    mid = (ask + bid) / 2.0
    return ((ask - bid) / mid * 100.0) if mid > 0 else 100.0


def score_candidate(
    ticker: Ticker,
    candles: list[Candle],
    *,
    spread: float,
    min_volatility: float = DEFAULT_MIN_VOLATILITY,
    max_volatility: float = DEFAULT_MAX_VOLATILITY,
    max_spread: float = DEFAULT_MAX_SPREAD,
    min_cost_multiple: float = DEFAULT_MIN_COST_MULTIPLE,
    on_reject: Callable[[str], None] | None = None,
) -> ScalpCandidate | None:
    """
    امتیازدهی یک نماد. `None` یعنی برای اسکلپ مناسب نیست.

    رد کردن یک نماد یک نتیجهٔ درست است، نه شکست — درست مثل «منتظر» در
    موتور سیگنال اصلی.

    `on_reject` (نسخهٔ ۲.۶.۰، اختیاری): کد استاندارد دلیل رد را می‌گیرد تا
    خلاصهٔ پویش بداند هر نماد کجا افتاد. منطق و آستانه‌ها تغییری نکرده‌اند.
    """
    def rejected(code: str) -> None:
        if on_reject is not None:
            try:
                on_reject(code)
            except Exception:  # noqa: BLE001 - شمارش نباید امتیازدهی را بشکند
                pass
        return None

    volatility = recent_volatility(candles)
    if volatility < min_volatility:
        return rejected("low_volatility")  # آرام‌تر از آن است که سودی بدهد
    if volatility > max_volatility:
        return rejected("high_volatility")  # آشفته‌تر از آن است که حد ضرر معنا داشته باشد

    if spread > max_spread:
        return rejected("wide_spread")  # اسپرد سود را می‌بلعد

    cost = ROUND_TRIP_FEE_PERCENT + spread
    if min_cost_multiple > 0 and volatility < min_cost_multiple * cost:
        return rejected("cost_too_high")  # نوسان نسبت به هزینه کوچک است؛ هزینه بر نتیجه غالب می‌شود

    move = momentum_percent(candles)
    if abs(move) < 0.05:
        return rejected("no_direction")  # بدون جهت روشن

    direction = "LONG" if move > 0 else "SHORT"

    # سود خالص مورد انتظار: بخشی از نوسان معمول، منهای کارمزد.
    # ضریب ۰٫۶ محافظه‌کارانه است — هرگز کل دامنهٔ کندل گرفته نمی‌شود.
    # اسپرد هم یک هزینهٔ واقعی است: ورود روی ask و خروج روی bid.
    # نادیده گرفتنش سود را خوش‌بینانه‌تر از واقعیت نشان می‌داد.
    expected_net = volatility * 0.6 - ROUND_TRIP_FEE_PERCENT - spread

    reasons: list[str] = [
        f"نوسان ۵ دقیقه‌ای: {volatility:.2f}٪",
        f"حرکت اخیر: {move:+.2f}٪",
        f"گردش ۲۴ ساعته: {ticker.turnover_24h:,.0f} دلار",
    ]

    if expected_net <= 0:
        reasons.append("پس از کارمزد سودی نمی‌ماند")
        return rejected("negative_expectancy")
    breakeven = (volatility * 0.6 + cost) / (2.0 * volatility * 0.6) * 100.0
    reasons.append(f"هزینهٔ رفت‌وبرگشت {cost:.2f}٪ — برد لازم برای سربه‌سر: {breakeven:.0f}٪")

    # امتیاز: نوسان و شتاب خوب‌اند، اسپرد بد است. نقدینگی به‌صورت
    # لگاریتمی وارد می‌شود تا یک نماد غول‌پیکر بقیه را له نکند.
    liquidity_bonus = min(2.0, (float(ticker.turnover_24h or 0.0) / 10_000_000.0) ** 0.5)
    score = (volatility * 10.0) + (abs(move) * 5.0) + liquidity_bonus - (spread * 50.0)

    return ScalpCandidate(
        symbol=ticker.symbol,
        price=float(ticker.last_price or 0.0),
        score=round(score, 3),
        direction=direction,
        volatility_5m=round(volatility, 4),
        turnover_24h=float(ticker.turnover_24h or 0.0),
        spread_percent=round(spread, 4),
        momentum=round(move, 4),
        expected_net_percent=round(expected_net, 4),
        cost_percent=round(cost, 4),
        reasons=reasons,
    )


#: وزن شواهد جهت اسکالپ. تایم‌فریم بالاتر مخالف فقط قدرت را کم می‌کند؛
#: هیچ شاهدی به‌تنهایی مسدودکننده نیست.
SCALP_EVIDENCE_WEIGHTS: dict[str, float] = {
    "momentum_1m": 0.6,
    "momentum_5m": 1.0,
    "trend_5m": 0.8,
    "trend_15m": 1.0,
    "trend_1h": 0.8,
    "trend_4h": 0.6,
    "cvd_5m": 0.6,
    "orderbook": 0.8,
}


def _ema_value(values: list[float], period: int) -> float:
    k = 2.0 / (period + 1.0)
    ema = values[0]
    for value in values[1:]:
        ema = value * k + ema * (1.0 - k)
    return ema


def trend_bias(candles: list[Candle]) -> float | None:
    """سوگیری روند ∈ [-1, 1] از EMA9/EMA21 و شیب؛ داده ناکافی → None."""
    closes = [float(c.close) for c in candles or []]
    if len(closes) < 25:
        return None
    fast = _ema_value(closes, 9)
    slow = _ema_value(closes, 21)
    if slow <= 0:
        return None
    gap = (fast - slow) / slow * 100.0
    vol = recent_volatility(candles[-20:]) or 0.1
    return max(-1.0, min(1.0, gap / max(vol, 0.05)))


def momentum_bias(candles: list[Candle], lookback: int = 6) -> float | None:
    """مومنتوم نرمال‌شده با نوسان ∈ [-1, 1]."""
    if len(candles or []) < lookback + 1:
        return None
    move = momentum_percent(candles, lookback)
    vol = recent_volatility(candles[-20:]) or 0.1
    return max(-1.0, min(1.0, move / (2.0 * max(vol, 0.05))))


def resolve_scalp_direction(
    frames: dict[str, list[Candle]],
    *,
    orderbook_imbalance: float | None = None,
    min_margin: float = 0.12,
) -> tuple[str, float, dict[str, float]]:
    """
    حل جهت اسکالپ از شواهد چندتایم‌فریمی — نسخهٔ ۲.۵.۵.

    frames: {"1m": [...], "5m": [...], "15m": [...], "1h": [...], "4h": [...]}
    (هر کدام اختیاری). بازگشت (جهت LONG/SHORT/WAIT، قدرت ∈ [-1,1]، شواهد).
    """
    from signals.intelligent_decision import resolve_direction
    from signals.orderflow import cvd_slope

    evidence: dict[str, float] = {}
    if frames.get("1m"):
        value = momentum_bias(frames["1m"], 5)
        if value is not None:
            evidence["momentum_1m"] = value
    if frames.get("5m"):
        value = momentum_bias(frames["5m"], 6)
        if value is not None:
            evidence["momentum_5m"] = value
        value = trend_bias(frames["5m"])
        if value is not None:
            evidence["trend_5m"] = value
        slope = cvd_slope(frames["5m"], 20)
        if slope is not None:
            evidence["cvd_5m"] = max(-1.0, min(1.0, slope * 2.0))
    for timeframe in ("15m", "1h", "4h"):
        value = trend_bias(frames.get(timeframe) or [])
        if value is not None:
            evidence[f"trend_{timeframe}"] = value
    if orderbook_imbalance is not None:
        evidence["orderbook"] = max(-1.0, min(1.0, float(orderbook_imbalance)))
    direction, strength = resolve_direction(
        evidence, weights=SCALP_EVIDENCE_WEIGHTS, min_margin=min_margin
    )
    return direction.value, strength, {k: round(v, 3) for k, v in evidence.items()}


def apply_direction_evidence(
    candidate: ScalpCandidate,
    frames: dict[str, list[Candle]],
    *,
    orderbook_imbalance: float | None = None,
) -> ScalpCandidate:
    """
    بازتعیین جهت نامزد با شواهد. نامزد هرگز حذف نمی‌شود:
      • شواهد روشن و هم‌جهت → جهت می‌ماند، conviction بالا.
      • شواهد روشن و مخالف مومنتوم → جهت برمی‌گردد (با دلیل صریح).
      • شواهد نامعلوم (WAIT) → جهت مومنتوم با برچسب «کم‌اطمینان» و
        امتیاز ×۰٫۷؛ کاربر/معامله‌گر خودکار این را می‌بیند.
    """
    direction, strength, evidence = resolve_scalp_direction(
        frames, orderbook_imbalance=orderbook_imbalance
    )
    candidate.evidence = evidence
    candidate.conviction = round(abs(strength), 3)
    if direction == "WAIT":
        candidate.direction_source = "momentum_low_conviction"
        candidate.score = round(candidate.score * 0.7, 3)
        candidate.reasons.append(f"شواهد چندتایم‌فریمی جهت روشنی نمی‌دهد (قدرت {strength:+.2f})")
        return candidate
    if direction != candidate.direction:
        candidate.reasons.append(
            f"جهت با شواهد چندتایم‌فریمی از {candidate.direction} به {direction} اصلاح شد (قدرت {strength:+.2f})"
        )
        candidate.direction = direction
    else:
        candidate.reasons.append(f"شواهد چندتایم‌فریمی جهت را تأیید می‌کند (قدرت {strength:+.2f})")
    candidate.direction_source = "evidence"
    candidate.score = round(candidate.score * (0.85 + 0.3 * abs(strength)), 3)
    return candidate


def rank_candidates(candidates: list[ScalpCandidate], limit: int = 10) -> list[ScalpCandidate]:
    """مرتب‌سازی نامزدها از بهترین به بدترین."""
    return sorted(candidates, key=lambda c: c.score, reverse=True)[:limit]


def prefilter_symbols(
    tickers: list[Ticker],
    *,
    min_turnover: float = DEFAULT_MIN_TURNOVER,
    quote: str = "USDT",
    limit: int = 40,
) -> list[Ticker]:
    """
    کاهش هزار نماد به چند ده نماد، **پیش از** گرفتن کندل.

    این کار از نظر سرعت حیاتی است: گرفتن کندل برای هزار نماد هم کند
    است و هم صرافی را عصبانی می‌کند. اینجا فقط از دادهٔ تیکر که همین
    حالا داریم استفاده می‌شود.
    """
    eligible = [
        ticker
        for ticker in tickers
        if ticker.symbol.upper().endswith(f"/{quote.upper()}")
        and passes_liquidity(ticker, min_turnover)
        and float(ticker.last_price or 0.0) > 0
    ]
    # نامزدها آن‌هایی‌اند که امروز واقعاً حرکت کرده‌اند.
    eligible.sort(key=lambda t: abs(float(t.change_percent or 0.0)), reverse=True)
    return eligible[:limit]


def feasibility_note(
    target_profit: float, margin: float, leverage: float, volatility_5m: float
) -> tuple[bool, str]:
    """
    آیا هدف سود کاربر در یک معاملهٔ کوتاه واقع‌بینانه است؟

    این تابع برای صداقت است. اگر کسی از ۱۰ دلار انتظار ۳ دلار سود در
    پنج دقیقه داشته باشد، باید **پیش از** ریختن پول بداند که این یعنی
    حرکت ۳۰ درصدی بازار.
    """
    notional = margin * max(leverage, 1.0)
    if notional <= 0:
        return False, "مبلغ معامله صفر است"

    needed = (target_profit / notional) * 100.0 + ROUND_TRIP_FEE_PERCENT
    if volatility_5m <= 0:
        return False, "نوسانی اندازه‌گیری نشده است"

    # یک کندل معمولاً کل دامنه‌اش را در یک جهت نمی‌دهد.
    realistic_per_candle = volatility_5m * 0.6
    candles_needed = needed / realistic_per_candle if realistic_per_candle > 0 else 999.0

    if candles_needed <= 3:
        return True, f"واقع‌بینانه: حدود {candles_needed:.1f} کندل ۵ دقیقه‌ای"
    if candles_needed <= 12:
        return True, f"شدنی ولی کند: حدود {candles_needed:.0f} کندل ۵ دقیقه‌ای"
    return False, (
        f"غیرواقع‌بینانه: بازار باید {needed:.2f}٪ حرکت کند که با نوسان "
        f"فعلی حدود {candles_needed:.0f} کندل ۵ دقیقه‌ای طول می‌کشد. "
        f"اهرم را بالا ببرید یا هدف سود را کم کنید."
    )
