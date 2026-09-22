"""
توضیح‌پذیری پیش‌بینی (Explainable AI) — خواستهٔ ۳۰.

چرا این فایل وجود دارد؟
    کاربر خواسته: «هر Prediction باید قابل توضیح باشد — Main
    Contributors با علامت.» برای مدل‌های درختی می‌توان SHAP سرراست
    داشت، اما دو مانع صادقانه هست:
    ۱. اینجا چند مدل (آماری/GBM/LSTM) در آنسامبل‌اند؛ توضیح باید از
       «کل» سیستم بیاید نه یک عضو.
    ۲. سهم هر منبع در فیوژن وزن‌دار از قبل معلوم است — این خودش
       توضیحِ درست‌تر و پایدارتری از اثر میانگین SHAP تک‌مدل است.

    پس خروجی: سهم علامت‌دارِ هر مؤلفهٔ فیوژن (توزیع/آنسامبل/رژیم/
    مومنتوم/آنومالی) به‌علاوهٔ برجستگی فیچرهای ورودی (فاصله از نرمال).
    SHAP جایی که مدل تکی حاکم باشد می‌تواند در فازهای بعد اضافه شود؛
    الان ادعایش را نمی‌کنیم.
"""

from __future__ import annotations

import math
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: نام‌های پایدار عوامل — UI با prediction.factor.<name> ترجمه می‌کند.
FACTOR_LABELS = {
    "distribution": "historical_distribution",
    "ensemble": "model_ensemble",
    "regime": "market_regime",
    "momentum": "momentum",
    "anomaly": "anomaly",
    "volume": "volume",
    "volatility": "volatility",
    "resistance": "resistance",
    "support": "support",
}


def explain_from_fusion(
    components: list[dict[str, Any]],
    *,
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """
    سهم علامت‌دار هر مؤلفهٔ فیوژن از انحراف احتمال از ۵۰.

    components: خروجی to_dict فیوژن (نام، احتمال، وزن).
    خروجی: فهرست {name, contribution} مرتب از بیشترین |سهم|.
    """
    items: list[dict[str, Any]] = []
    total_weight = sum(
        (weights or {}).get(c.get("name", ""), float(c.get("weight", 1.0)))
        for c in components
    ) or 1.0
    for component in components:
        name = str(component.get("name", ""))
        weight = (weights or {}).get(name, float(component.get("weight", 1.0)))
        deviation = float(component.get("probability", 50)) - 50.0
        contribution = deviation * weight / total_weight
        items.append({"name": name, "contribution": round(contribution, 2)})
    items.sort(key=lambda item: -abs(item["contribution"]))
    return items


def feature_highlights(latest: dict[str, float | None]) -> list[dict[str, Any]]:
    """
    برجستگی فیچرهای لحظه‌ای — چه چیزی غیرعادی است و به کدام سمت.

    ورودی: مقادیر latest بردار فیچر. خروجی: فیچرهای خارج از بازهٔ
    عادی با جهت و شدت — مادهٔ خام «شرایط» سناریوها و توضیح عامل AI.
    """
    interesting: list[dict[str, Any]] = []
    checks: list[tuple[str, float, float, float]] = [
        # (نام، مقدار، کف غیرعادی، سقف غیرعادی)
        ("rsi", 30.0, 70.0, 1.0),
        ("ema_distance", -1.5, 1.5, 1.0),
        ("atr_percent", 0.0, 0.0, 0.0),  # وابسته به نماد؛ فقط علامت‌دار
        ("adx", 0.0, 25.0, 1.0),
    ]
    for name, low, high, _scale in checks:
        value = latest.get(name)
        if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
            continue
        if name == "rsi" and (value > high or value < low):
            interesting.append(
                {"name": name, "value": round(float(value), 1),
                 "direction": "overbought" if value > high else "oversold"}
            )
        elif name == "ema_distance" and abs(value) > 1.5:
            interesting.append(
                {"name": name, "value": round(float(value), 2),
                 "direction": "above_trend" if value > 0 else "below_trend"}
            )
        elif name == "adx" and value >= 25:
            interesting.append(
                {"name": name, "value": round(float(value), 1), "direction": "strong_trend"}
            )
    volume_change = latest.get("volume_change")
    if isinstance(volume_change, (int, float)) and math.isfinite(volume_change) and abs(volume_change) > 0.5:
        interesting.append(
            {"name": "volume", "value": round(float(volume_change) * 100, 1),
             "direction": "surging" if volume_change > 0 else "fading"}
        )
    return interesting


def split_contributors(contributors: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """تفکیک عوامل مثبت و منفی — برای نمایش دو ستونی UI."""
    positive = [c for c in contributors if c.get("contribution", 0) > 0]
    negative = [c for c in contributors if c.get("contribution", 0) < 0]
    return {"positive": positive, "negative": negative}
