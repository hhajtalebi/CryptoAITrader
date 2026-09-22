"""
بستهٔ موتور هوش پیش‌بینی (Predictive Intelligence Engine).

چرا یک بستهٔ جدا زیر signals؟
    این بسته «لایهٔ پیش‌بینی» نرم‌افزار است: از دادهٔ پاک‌شده فیچر می‌سازد،
    رژیم بازار را تشخیص می‌دهد، توزیع احتمال و سناریو تولید می‌کند و
    عملکرد خودش را می‌سنجد. همهٔ این‌ها **روی** موتورهای موجود (اندیکاتور،
    سیگنال، تحلیل چندتایم‌فریمی) سوار می‌شوند؛ هیچ‌کدام را بازنویسی
    نمی‌کنند.

قوانین حاکم (سند docs/PREDICTIVE_ENGINE_FA.md):
    • هیچ عددی بدون داده ساخته نمی‌شود؛ نبود داده = خروجی disabled.
    • همهٔ فیچرها به «زمان بسته‌شدن کندل» مهر می‌خورند (ضد look-ahead).
    • LLM فقط توضیح می‌دهد؛ عدد از Quant/ML می‌آید.
"""

from __future__ import annotations

from signals.prediction.engine import (
    CANDLE_LIMIT,
    DEFAULT_TIMEFRAMES,
    ENSEMBLE_TTL,
    HorizonReport,
    IntelligenceReport,
    PredictiveIntelligenceEngine,
    REPORT_TTL,
)
from signals.prediction.features import FeatureSet, FeatureStore, FeatureVector
from signals.prediction.horizons import HorizonPlan, plan_horizons
from signals.prediction.scoring import accuracy_summary, brier_score, model_health
from signals.prediction.store import PredictionStore, price_lookup_from_candles

__all__ = [
    "CANDLE_LIMIT",
    "DEFAULT_TIMEFRAMES",
    "ENSEMBLE_TTL",
    "FeatureSet",
    "FeatureStore",
    "FeatureVector",
    "HorizonPlan",
    "HorizonReport",
    "IntelligenceReport",
    "PredictionStore",
    "PredictiveIntelligenceEngine",
    "REPORT_TTL",
    "accuracy_summary",
    "brier_score",
    "model_health",
    "plan_horizons",
    "price_lookup_from_candles",
]
