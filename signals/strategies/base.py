"""
قرارداد راهبردهای معاملاتی.

چرا وجود دارد؟
    هر راهبرد یک «رأی» مستقل درباره جهت بازار می‌دهد و موتور سیگنال
    رأی‌ها را وزن‌دهی و جمع‌بندی می‌کند. این طراحی باعث می‌شود:
        • افزودن راهبرد جدید نیازی به تغییر موتور نداشته باشد
        • هیچ راهبردی به‌تنهایی تصمیم‌گیر نباشد
        • دلیل هر رأی برای کاربر قابل مشاهده باشد
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.constants import SignalDirection, TrendDirection
from app.core.models import Candle, MarketStructure, SupportResistanceLevel


@dataclass(slots=True)
class StrategyContext:
    """
    داده‌های در دسترس یک راهبرد برای تصمیم‌گیری.

    همه مقادیر از داده واقعی بازار می‌آیند؛ راهبرد حق ساختن داده ندارد.
    """

    symbol: str
    timeframe: str
    candles: list[Candle]
    indicators: dict[str, Any]
    structure: MarketStructure | None = None
    levels: list[SupportResistanceLevel] = field(default_factory=list)
    trend: TrendDirection = TrendDirection.NEUTRAL
    higher_timeframe_trend: TrendDirection = TrendDirection.NEUTRAL

    @property
    def last_price(self) -> float:
        """آخرین قیمت بسته‌شدن."""
        return self.candles[-1].close if self.candles else 0.0

    def indicator_value(self, name: str, key: str) -> float | None:
        """
        خواندن امن یک مقدار اندیکاتور.

        اگر اندیکاتور محاسبه نشده باشد، None برمی‌گردد و راهبرد باید آن را
        مدیریت کند — نه اینکه مقدار فرضی جایگزین کند.
        """
        payload = self.indicators.get(name.upper())
        if not payload:
            return None
        latest = payload.get("latest") if isinstance(payload, dict) else None
        if not isinstance(latest, dict):
            return None
        value = latest.get(key)
        return float(value) if isinstance(value, (int, float)) else None

    def indicator_signal(self, name: str) -> str:
        """خواندن تفسیر متنی یک اندیکاتور (مثلاً OVERSOLD)."""
        payload = self.indicators.get(name.upper())
        if isinstance(payload, dict):
            return str(payload.get("signal", ""))
        return ""


@dataclass(slots=True)
class StrategyVote:
    """
    رأی یک راهبرد.

    score در بازه ۱- تا ۱+ است: مثبت یعنی صعودی، منفی یعنی نزولی، صفر
    یعنی این راهبرد در شرایط فعلی نظری ندارد (که کاملاً معتبر است).
    """

    strategy: str
    direction: SignalDirection
    score: float
    weight: float = 1.0
    reasons: list[str] = field(default_factory=list)
    applicable: bool = True

    @property
    def weighted_score(self) -> float:
        """امتیاز وزن‌دار برای جمع‌بندی."""
        return self.score * self.weight if self.applicable else 0.0

    def to_dict(self) -> dict[str, Any]:
        """تبدیل برای نمایش در رابط کاربری و ثبت در سابقه."""
        return {
            "strategy": self.strategy,
            "direction": self.direction.value,
            "score": round(self.score, 3),
            "weight": self.weight,
            "applicable": self.applicable,
            "reasons": list(self.reasons),
        }


class BaseStrategy(ABC):
    """
    کلاس پایه همه راهبردها.

    برای ساخت راهبرد جدید کافی است `name`، `weight` و `evaluate` را
    پیاده‌سازی و آن را در رجیستری ثبت کنید.
    """

    #: نام یکتای راهبرد
    name: str = "base"
    #: وزن پیش‌فرض در جمع‌بندی
    weight: float = 1.0
    #: حداقل کندل موردنیاز
    min_candles: int = 60

    @abstractmethod
    def evaluate(self, context: StrategyContext) -> StrategyVote:
        """
        بررسی شرایط بازار و صدور رأی.

        اگر شرایط این راهبرد برقرار نیست، رأیی با `applicable=False`
        برگردانید — نه یک رأی ضعیف الکی.
        """

    def _vote(
        self,
        score: float,
        reasons: list[str],
        *,
        applicable: bool = True,
    ) -> StrategyVote:
        """ساخت رأی با تعیین خودکار جهت از روی امتیاز."""
        score = max(-1.0, min(1.0, score))
        if score > 0.15:
            direction = SignalDirection.LONG
        elif score < -0.15:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.WAIT
        return StrategyVote(
            strategy=self.name,
            direction=direction,
            score=score,
            weight=self.weight,
            reasons=reasons,
            applicable=applicable,
        )

    def _not_applicable(self, reason: str) -> StrategyVote:
        """رأی «این راهبرد در شرایط فعلی کاربرد ندارد»."""
        return StrategyVote(
            strategy=self.name,
            direction=SignalDirection.WAIT,
            score=0.0,
            weight=self.weight,
            reasons=[reason],
            applicable=False,
        )
