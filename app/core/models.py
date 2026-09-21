"""
مدل‌های داده‌ای پایه و مستقل از پایگاه داده (Domain Models).

چرا وجود دارد؟
    لایه‌های بازار، اندیکاتور، هوش مصنوعی و سیگنال باید با یک «زبان
    مشترک» داده تبادل کنند، بدون اینکه به SQLAlchemy یا به ساختار پاسخ یک
    صرافی خاص وابسته شوند. این جداسازی، افزودن صرافی جدید را ساده می‌کند.

ارتباط با ماژول‌های دیگر:
    market -> این مدل‌ها را تولید می‌کند.
    indicators / signals / ai -> این مدل‌ها را مصرف می‌کنند.
    database -> این مدل‌ها را به رکورد تبدیل می‌کند (نه برعکس).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.constants import (
    AnalysisStatus,
    MarketStructureType,
    SignalDirection,
    TrendDirection,
)


def utc_now() -> datetime:
    """زمان جاری با منطقه زمانی UTC (برای ثبت یکنواخت زمان‌ها)."""
    return datetime.now(timezone.utc)


@dataclass(slots=True, frozen=True)
class Candle:
    """
    یک کندل (شمع) قیمتی.

    فیلد timestamp همیشه «زمان باز شدن کندل» بر حسب ثانیه UTC است تا در
    تجمیع تایم‌فریم‌ها رفتار قابل پیش‌بینی داشته باشیم.
    """

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def datetime_utc(self) -> datetime:
        """زمان کندل به‌صورت شیء datetime با منطقه زمانی UTC."""
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc)

    @property
    def is_bullish(self) -> bool:
        """آیا کندل صعودی است (بسته‌شدن بالاتر از باز شدن)؟"""
        return self.close >= self.open

    def to_dict(self) -> dict[str, Any]:
        """تبدیل به دیکشنری برای ذخیره‌سازی یا ارسال به هوش مصنوعی."""
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass(slots=True, frozen=True)
class Ticker:
    """
    خلاصه وضعیت لحظه‌ای یک نماد در ۲۴ ساعت گذشته.

    change_percent درصد تغییر قیمت در ۲۴ ساعت اخیر است (مثلاً 1.5- یعنی
    یک‌ونیم درصد افت).
    """

    symbol: str
    last_price: float
    high_24h: float
    low_24h: float
    volume_24h: float
    turnover_24h: float
    change_percent: float
    timestamp: int

    def to_dict(self) -> dict[str, Any]:
        """تبدیل به دیکشنری قابل استفاده در UI و ابزارهای هوش مصنوعی."""
        return {
            "symbol": self.symbol,
            "last_price": self.last_price,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "volume_24h": self.volume_24h,
            "turnover_24h": self.turnover_24h,
            "change_percent": self.change_percent,
            "timestamp": self.timestamp,
        }


@dataclass(slots=True, frozen=True)
class OrderBookLevel:
    """یک سطح از دفتر سفارش‌ها (قیمت و حجم)."""

    price: float
    quantity: float


@dataclass(slots=True, frozen=True)
class OrderBook:
    """
    دفتر سفارش‌ها.

    bids به‌صورت نزولی (بهترین خرید در ابتدا) و asks به‌صورت صعودی
    (بهترین فروش در ابتدا) مرتب می‌شوند.
    """

    symbol: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    timestamp: int

    @property
    def best_bid(self) -> float | None:
        """بهترین قیمت خرید موجود."""
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> float | None:
        """بهترین قیمت فروش موجود."""
        return self.asks[0].price if self.asks else None

    @property
    def spread(self) -> float | None:
        """اختلاف بهترین خرید و فروش؛ معیاری از نقدشوندگی."""
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid


@dataclass(slots=True, frozen=True)
class SymbolInfo:
    """
    اطلاعات پایه یک نماد معاملاتی.

    symbol شکل استاندارد داخلی (مثل BTC/USDT) و exchange_symbol شکل مورد
    نیاز صرافی (مثل btc_usdt) است. این تفکیک باعث می‌شود هسته برنامه به
    قرارداد نام‌گذاری یک صرافی خاص وابسته نشود.
    """

    symbol: str
    exchange_symbol: str
    base_asset: str
    quote_asset: str
    price_precision: int = 8
    quantity_precision: int = 8
    min_order_amount: float = 0.0


@dataclass(slots=True)
class IndicatorResult:
    """
    خروجی یک اندیکاتور.

    values : مقادیر سری‌زمانی (برای رسم روی نمودار).
    latest : آخرین مقدار(های) عددی برای تصمیم‌گیری سریع.
    signal : تفسیر متنی کوتاه، مثلاً «اشباع خرید» یا «تقاطع صعودی».
    """

    name: str
    timeframe: str
    values: dict[str, list[float | None]] = field(default_factory=dict)
    latest: dict[str, float | None] = field(default_factory=dict)
    signal: str = "NEUTRAL"
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_summary(self) -> dict[str, Any]:
        """
        خلاصه سبک (بدون سری‌های بلند) برای ارسال به مدل هوش مصنوعی.

        ارسال کل سری‌ها به مدل، هم پرهزینه است و هم باعث خطای Context
        می‌شود؛ بنابراین فقط مقادیر آخر و تفسیر ارسال می‌گردد.
        """
        return {
            "name": self.name,
            "timeframe": self.timeframe,
            "latest": {k: (round(v, 8) if isinstance(v, float) else v) for k, v in self.latest.items()},
            "signal": self.signal,
            "parameters": self.parameters,
        }


@dataclass(slots=True)
class SupportResistanceLevel:
    """یک سطح حمایت یا مقاومت شناسایی‌شده."""

    price: float
    kind: str  # support | resistance
    strength: str  # major | minor
    source: str  # pivot | fibonacci | swing | dynamic
    distance_percent: float = 0.0


@dataclass(slots=True)
class MarketStructure:
    """
    نتیجه تحلیل ساختار بازار در یک تایم‌فریم.

    swings دنباله‌ای از برچسب‌های HH/HL/LH/LL است که ترتیب سقف‌ها و کف‌ها
    را نشان می‌دهد.
    """

    timeframe: str
    structure: MarketStructureType = MarketStructureType.UNDEFINED
    trend: TrendDirection = TrendDirection.NEUTRAL
    swings: list[str] = field(default_factory=list)
    last_swing_high: float | None = None
    last_swing_low: float | None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """تبدیل به دیکشنری برای ذخیره یا ارسال به هوش مصنوعی."""
        return {
            "timeframe": self.timeframe,
            "structure": self.structure.value,
            "trend": self.trend.value,
            "swings": self.swings[-8:],
            "last_swing_high": self.last_swing_high,
            "last_swing_low": self.last_swing_low,
            "note": self.note,
        }


@dataclass(slots=True)
class TimeframeAnalysis:
    """تحلیل کامل یک تایم‌فریم: روند، اندیکاتورها، ساختار و سطوح کلیدی."""

    timeframe: str
    role: str = ""
    candles_count: int = 0
    last_price: float | None = None
    trend: TrendDirection = TrendDirection.NEUTRAL
    indicators: dict[str, IndicatorResult] = field(default_factory=dict)
    market_structure: MarketStructure | None = None
    levels: list[SupportResistanceLevel] = field(default_factory=list)
    volume_note: str = ""

    def to_summary(self) -> dict[str, Any]:
        """خلاصه سبک این تایم‌فریم برای استفاده در Prompt هوش مصنوعی."""
        return {
            "timeframe": self.timeframe,
            "role": self.role,
            "candles": self.candles_count,
            "last_price": self.last_price,
            "trend": self.trend.value,
            "indicators": {k: v.to_summary() for k, v in self.indicators.items()},
            "market_structure": (self.market_structure.to_dict() if self.market_structure else None),
            "levels": [
                {
                    "price": lvl.price,
                    "kind": lvl.kind,
                    "strength": lvl.strength,
                    "source": lvl.source,
                    "distance_percent": round(lvl.distance_percent, 3),
                }
                for lvl in self.levels[:12]
            ],
            "volume_note": self.volume_note,
        }


@dataclass(slots=True)
class MarketSnapshot:
    """
    عکس لحظه‌ای کامل از وضعیت یک نماد در چند تایم‌فریم.

    این ساختار «تنها منبع حقیقت» برای موتور سیگنال و عامل هوش مصنوعی است؛
    مدل هوش مصنوعی اجازه ندارد داده‌ای خارج از این ساختار فرض کند.
    """

    symbol: str
    exchange: str
    ticker: Ticker | None = None
    timeframes: dict[str, TimeframeAnalysis] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    status: AnalysisStatus = AnalysisStatus.OK
    notes: list[str] = field(default_factory=list)

    @property
    def current_price(self) -> float | None:
        """قیمت لحظه‌ای بر اساس Ticker یا آخرین کندل موجود."""
        if self.ticker is not None:
            return self.ticker.last_price
        for analysis in self.timeframes.values():
            if analysis.last_price is not None:
                return analysis.last_price
        return None

    def to_payload(self) -> dict[str, Any]:
        """
        ساخت داده ورودی استاندارد برای مدل هوش مصنوعی.

        همه فیلدهای الزامی مستندسازی (زمان داده، صرافی، نماد، تایم‌فریم‌ها)
        در این خروجی حضور دارند تا شرط «تحلیل بدون داده ممنوع» رعایت شود.
        """
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "data_timestamp": self.created_at.isoformat(),
            "status": self.status.value,
            "current_price": self.current_price,
            "ticker": self.ticker.to_dict() if self.ticker else None,
            "timeframes": {tf: analysis.to_summary() for tf, analysis in self.timeframes.items()},
            "notes": self.notes,
        }


@dataclass(slots=True)
class RiskParameters:
    """
    پارامترهای مدیریت ریسک که موتور سیگنال از آن‌ها استفاده می‌کند.

    مقادیر پیش‌فرض عمداً محافظه‌کارانه انتخاب شده‌اند.
    """

    account_balance: float = 1000.0
    risk_percent: float = 1.0
    max_leverage: int = 5
    min_risk_reward: float = 1.5
    atr_stop_multiplier: float = 1.5
    max_stop_distance_percent: float = 5.0


@dataclass(slots=True)
class RiskAssessment:
    """نتیجه محاسبات مدیریت ریسک برای یک سیگنال مشخص."""

    stop_distance_percent: float
    risk_reward: float
    suggested_leverage: int
    position_size: float
    risk_amount: float
    atr_value: float | None = None
    volatility_note: str = ""
    approved: bool = True
    rejection_reason: str = ""


@dataclass(slots=True)
class TradingSignal:
    """
    سیگنال معاملاتی نهایی.

    هشدار مهم: confidence «احتمال قطعی موفقیت» نیست، بلکه میزان هم‌راستایی
    عوامل تحلیلی سیستم است و هیچ تضمینی ایجاد نمی‌کند.
    """

    symbol: str
    exchange: str
    direction: SignalDirection
    entry_min: float | None = None
    entry_max: float | None = None
    stop_loss: float | None = None
    take_profits: list[float] = field(default_factory=list)
    risk_reward: float | None = None
    leverage: int = 1
    confidence: int = 0
    trend: TrendDirection = TrendDirection.NEUTRAL
    market_structure: MarketStructureType = MarketStructureType.UNDEFINED
    reason: str = ""
    invalidation: str = ""
    timeframes: list[str] = field(default_factory=list)
    indicators_used: list[str] = field(default_factory=list)
    ai_provider: str | None = None
    ai_model: str | None = None
    analysis_text: str = ""
    #: منبع تحلیل نوشتاری: "ai" یا "template" (خالی یعنی تحلیلی نوشته نشده)
    analysis_source: str = ""
    status: AnalysisStatus = AnalysisStatus.OK
    created_at: datetime = field(default_factory=utc_now)
    risk: RiskAssessment | None = None
    #: تایم‌فریمی که سرعت کهنه‌شدن سیگنال را تعیین می‌کند (کوچک‌ترین).
    primary_timeframe: str = ""
    #: تا این لحظه ورود منطقی است؛ پس از آن سیگنال «سوخته» است.
    #: بدون این فیلد، کاربر سیگنال دو‌ساعته را تازه می‌پنداشت و وارد
    #: معامله‌ای می‌شد که شرایطش دیگر وجود نداشت.
    enter_before: datetime | None = None
    #: پس از این لحظه سیگنال هیچ اعتباری ندارد.
    expires_at: datetime | None = None
    #: پیش‌بینی بازهٔ محتمل قیمت برای تایم‌فریم‌های بعدی.
    #: کاربر خواست بداند «۱۵ دقیقه، یک ساعت و چهار ساعت بعد چه می‌شود».
    #: هر عضو یک دیکشنری از signals.forecast.HorizonForecast است.
    forecast: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """تبدیل کامل سیگنال به دیکشنری برای ذخیره در پایگاه داده و گزارش."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "direction": self.direction.value,
            "entry_min": self.entry_min,
            "entry_max": self.entry_max,
            "stop_loss": self.stop_loss,
            "take_profits": list(self.take_profits),
            "risk_reward": self.risk_reward,
            "leverage": self.leverage,
            "confidence": self.confidence,
            "trend": self.trend.value,
            "market_structure": self.market_structure.value,
            "reason": self.reason,
            "invalidation": self.invalidation,
            "timeframes": list(self.timeframes),
            "indicators_used": list(self.indicators_used),
            "ai_provider": self.ai_provider,
            "ai_model": self.ai_model,
            "analysis_text": self.analysis_text,
            "analysis_source": self.analysis_source,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "primary_timeframe": self.primary_timeframe,
            "forecast": list(self.forecast),
            "enter_before": self.enter_before.isoformat() if self.enter_before else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
