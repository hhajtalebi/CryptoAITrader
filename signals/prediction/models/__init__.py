"""
بستهٔ مدل‌های پیش‌بینی — فاز ۵ و ۱۳.

اصل حاکم (خواستهٔ ۲۰ و قانون ۸): مدل ساده‌ای که بهتر عمل می‌کند،
حق دارد جای مدل پیچیده را بگیرد؛ Deep Learning فقط برای «پیشرفته به
نظر رسیدن» به کار نمی‌رود. انتخاب نهایی همیشه از سوی walk-forward
اعتبارسنجی است، نه سلیقه.

ساختار:
    base.py        قرارداد مدل + ساخت برچسب سه‌مانعی (بدون ناحیهٔ خنثی)
    statistical.py مدل آماری همیشه‌در دسترس (بدون وابستگی خارجی)
    gbm.py         LightGBM/XGBoost (اختیاری — نصب‌شده در گروه ml)
    lstm.py        شبکهٔ LSTM کوچک با PyTorch (اختیاری)
    walkforward.py اعتبارسنجی غلتان با گسست زمانی (ضد leakage)
    ensemble.py    آنسامبل وزن‌دار + تشخیص تعارض + انتخاب تطبیقی
    drift.py       تشخیص افت عملکرد مدل (فاز ۱۰)
"""

from __future__ import annotations

from signals.prediction.models.base import ForecastModel, ModelOutput, forward_labels
from signals.prediction.models.ensemble import EnsembleForecast, ModelEnsemble
from signals.prediction.models.walkforward import WalkForwardResult, walk_forward

__all__ = [
    "ForecastModel",
    "ModelOutput",
    "forward_labels",
    "EnsembleForecast",
    "ModelEnsemble",
    "WalkForwardResult",
    "walk_forward",
]
