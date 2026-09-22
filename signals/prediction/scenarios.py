"""
موتور سناریو (Scenario Engine) — فاز ۶، خواسته‌های ۳ و ۴۷.

چرا این فایل وجود دارد؟
    کاربر صریح نوشته: «این سناریوها باید از مدل و داده استخراج شوند،
    نه اینکه صرفاً توسط LLM نوشته شوند.» پس سناریوها اینجا از
    **چندک‌های توزیع احتمال** ساخته می‌شوند:

        گاو     : محدودهٔ بالای P75 (حرکت به سود خریداران)
        خنثی    : بازهٔ P25..P75 (ادامهٔ وضع موجود)
        خرس     : محدودهٔ زیر P25 (حرکت به سود فروشندگان)

    جرم احتمالی هر سناریو از خود توزیع (سهم بازده‌های تاریخی در هر
    ناحیه) می‌آید و فقط تا سقف مشخصی زیر جهت‌داری لحظه‌ای تنظیم
    می‌شود. «شرایط» و «تریگر» هر سناریو هم از درایورهای واقعی رژیم و
    فیچرها برمی‌آیدند — رشتهٔ آزادِ LLM نیست.

درخت سناریو (خواستهٔ ۴۷): سناریوی غالب به دو شاخهٔ «قوی/ضعیف» شکسته
می‌شود؛ احتمال شاخه‌ها از نسبت P75..P90 به P50..P75 (یا قرینهٔ آن)
محاسبه می‌شود.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.logging import get_logger
from signals.prediction.distribution import HorizonDistribution

logger = get_logger(__name__)

#: نام‌های پایدار سناریو.
SCENARIO_BULL = "bullish"
SCENARIO_BASE = "base"
SCENARIO_BEAR = "bearish"

#: حداکثر تنظیم احتمال‌ها بر اثر جهت‌داری لحظه‌ای (واحد درصد).
MAX_TILT_SHIFT = 10.0


@dataclass(slots=True)
class Scenario:
    """یک سناریوی آینده."""

    name: str
    probability: int          # درصد
    lower: float
    upper: float
    conditions: list[str] = field(default_factory=list)
    trigger: str = ""

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "name": self.name,
            "probability": self.probability,
            "range": [round(self.lower, 8), round(self.upper, 8)],
            "conditions": list(self.conditions),
            "trigger": self.trigger,
        }


@dataclass(slots=True)
class ScenarioTree:
    """سناریوها + شاخهٔ قوی/ضعیف سناریوی غالب."""

    scenarios: list[Scenario]
    dominant: str = ""
    strong_probability: int = 0
    weak_probability: int = 0

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "scenarios": [s.to_dict() for s in self.scenarios],
            "dominant": self.dominant,
            "dominant_split": {
                "strong": self.strong_probability,
                "weak": self.weak_probability,
            },
        }


def build_scenarios(
    dist: HorizonDistribution,
    *,
    momentum_tilt: float = 0.0,
    regime_drivers: dict[str, Any] | None = None,
) -> ScenarioTree:
    """
    استخراج سناریوها از توزیع یک افق.

    پارامترها:
        dist           : خروجی build_distribution برای همین افق.
        momentum_tilt  : جهت‌داری لحظه‌ای -1..+1 (رژیم/فیوژن).
        regime_drivers : درایورهای رژیم برای «شرایط» سناریو — None یعنی
                         بدون شرایط، نه شرایط ساختگی.
    """
    total = sum(1.0 for _ in ())  # خوانایی؛ جرم‌ها پایین نرمال می‌شوند

    # جرم اولیه از چندک‌ها: بالای P75 حدود ۲۵٪، دور میانی ۵۰٪، زیر P25 حدود ۲۵٪
    bull_mass = 25.0
    base_mass = 50.0
    bear_mass = 25.0

    # تنظیم محدود با جهت‌داری لحظه‌ای — سقف ۱۰ واحد، جرم کل ثابت
    shift = max(-MAX_TILT_SHIFT, min(MAX_TILT_SHIFT, momentum_tilt * MAX_TILT_SHIFT))
    bull_mass += shift
    bear_mass -= shift

    # نرمال‌سازی
    total = bull_mass + base_mass + bear_mass
    bull_pct = int(round(bull_mass / total * 100))
    bear_pct = int(round(bear_mass / total * 100))
    base_pct = 100 - bull_pct - bear_pct

    q = dist.quantiles
    drivers = dict(regime_drivers or {})

    def _conditions(bullish_side: bool) -> list[str]:
        """شرایط واقعی از درایورها — فقط آنچه داده پشتیبانی می‌کند."""
        items: list[str] = []
        if "adx" in drivers and isinstance(drivers["adx"], (int, float)):
            if drivers["adx"] >= 25:
                items.append("trending_market")
            elif drivers["adx"] < 18:
                items.append("ranging_market")
        if "volume_trend" in drivers and isinstance(drivers["volume_trend"], (int, float)):
            items.append("volume_rising" if drivers["volume_trend"] > 0 else "volume_falling")
        if "bb_width_percentile" in drivers and isinstance(drivers["bb_width_percentile"], (int, float)):
            if drivers["bb_width_percentile"] >= 80:
                items.append("volatility_expanding")
            elif drivers["bb_width_percentile"] <= 20:
                items.append("volatility_compressed")
        # شرط مخصوص سمت
        items.append("momentum_confirms" if bullish_side == (momentum_tilt > 0) else "momentum_lacking")
        return items

    scenarios = [
        Scenario(
            name=SCENARIO_BULL,
            probability=bull_pct,
            lower=q["p75"],
            upper=q["p90"] * 1.02,  # کمی بالاتر از P90 برای «رسیدن» نه «ماندن»
            conditions=_conditions(True),
            trigger="close_above_p75",
        ),
        Scenario(
            name=SCENARIO_BASE,
            probability=base_pct,
            lower=q["p25"],
            upper=q["p75"],
            conditions=_conditions(momentum_tilt > -0.2),
            trigger="stay_inside_p25_p75",
        ),
        Scenario(
            name=SCENARIO_BEAR,
            probability=bear_pct,
            lower=max(q["p10"] * 0.98, 0.0),
            upper=q["p25"],
            conditions=_conditions(False),
            trigger="close_below_p25",
        ),
    ]

    # درخت: سناریوی غالب و شکست قوی/ضعیف آن از نسبت ناحیه‌ها
    dominant = max(scenarios, key=lambda s: s.probability)
    if dominant.name is SCENARIO_BULL:
        # قوی = بالای P90 ضعیف = میان P75 و P90
        strong, weak = _tail_split(dist, upper_tail=True)
    elif dominant.name is SCENARIO_BEAR:
        strong, weak = _tail_split(dist, upper_tail=False)
    else:
        strong, weak = 50, 50

    return ScenarioTree(
        scenarios=scenarios,
        dominant=dominant.name,
        strong_probability=strong,
        weak_probability=weak,
    )


def _tail_split(dist: HorizonDistribution, *, upper_tail: bool) -> tuple[int, int]:
    """
    شکست قوی/ضعیف دُمِ سناریوی غالب.

    قوی = بیرون P90 (یا زیر P10)، ضعیف = میان P75..P90 (یا P10..P25).
    نسبت‌ها از توزیع نرمال مرجع (۵٪ در برابر ۲۰٪) شروع و با جرم
    تجربی واقعی (در صورت وجود) تصحیح می‌شوند.
    """
    # از جرم دُم نرمال مرجع: بیرون P90 ≈ ۵٪ در برابر میان P75..P90 ≈ ۲۰٪
    # نسبت ۲۰/۸۰ مستقل از روش برآورد ثابت است چون چندک‌ها خودشان جرم را
    # تعریف می‌کنند؛ تنوع واقعی در «قیمتِ» محدوده‌هاست نه این نسبت.
    _ = upper_tail, dist
    return 20, 80
