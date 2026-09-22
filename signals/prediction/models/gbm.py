"""
مدل گرادیان بوتینگ (LightGBM → XGBoost) — اختیاری.

چرا ترتیب LightGBM اول؟ سریع‌تر است و با دادهٔ ریز جدولی بهتر رفتار
می‌کند؛ XGBoost جایگزین است نه هم‌زمان — آنسامبل نیازمند دو GBM
یکسان نیست (تنوع مدل واقعی از خانواده‌های متفاوت می‌آید).

چرا API بومی و نه پوشش sklearn؟ پوشش sklearn کتابخانهٔ اضافه‌ای
می‌خواهد که در نصب‌کنندهٔ ویندوز حجم بی‌مورد دارد؛ API بومی
(`lgb.train` / `xgb.train`) همین کار را با وابستگی کمتر انجام می‌دهد.

ضد بیش‌برازش با دادهٔ کم (قانون ۸):
    • تعداد برگ کم (۱۵)، نرخ یادگیری پایین، حداقل داده در برگ (۲۵)
    • تعداد دور محدود (۸۰) بدون early-stoppingِ خوش‌بینانه

اگر هیچ‌کدام نصب نباشد `is_available()` صادقانه False می‌دهد و
آنسامبل بدون این مدل ادامه می‌دهد.
"""

from __future__ import annotations

import math
from typing import Any

from app.logging import get_logger
from signals.prediction.models.base import ForecastModel, ModelOutput

logger = get_logger(__name__)

#: پارامترهای محافظه‌کار — بیش‌برازش با دادهٔ کم ممنوع.
_LIGHTGBM_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 25,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.9,
    "bagging_freq": 1,
    "verbose": -1,
    "seed": 42,
    "num_threads": 1,
}

_XGBOOST_PARAMS: dict[str, Any] = {
    "objective": "binary:logistic",
    "eta": 0.05,
    "max_leaves": 15,
    "min_child_weight": 25,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "verbosity": 0,
    "seed": 42,
    "nthread": 1,
}

#: کمینهٔ ردیف آموزشی — زیر این، مدل به‌عمد آموزش نمی‌بیند.
MIN_TRAIN_ROWS = 120

#: تعداد دور تقویت.
NUM_ROUNDS = 80


class GBMModel(ForecastModel):
    """مدل گرادیان بوتینگ با بک‌اند بومی LightGBM یا XGBoost."""

    name = "gbm"

    def __init__(self) -> None:
        self._backend = ""
        self._model: Any = None
        self._feature_count = 0

    def is_available(self) -> bool:
        """آیا یکی از بک‌اندها نصب است؟ (بدون import واقعی — find_spec)"""
        from importlib.util import find_spec  # noqa: PLC0415

        return find_spec("lightgbm") is not None or find_spec("xgboost") is not None

    def fit(
        self, times: list[int], rows: list[list[float]], labels: list[int | None]
    ) -> "GBMModel":
        """آموزش GBM؛ دادهٔ کم یا نبود وابستگی = بدون آموزش صادقانه."""
        if not self.is_available():
            return self
        labeled_rows = [
            row for row, label in zip(rows, labels, strict=False) if label is not None
        ]
        labeled_targets = [label for label in labels if label is not None]
        if len(labeled_rows) < MIN_TRAIN_ROWS or len(set(labeled_targets)) < 2:
            return self

        self._feature_count = len(labeled_rows[0])

        try:
            self._model = self._fit_lightgbm(labeled_rows, labeled_targets)
            if self._model is not None:
                self._backend = "lightgbm"
                return self
        except Exception:  # noqa: BLE001 - بک‌اند اول شکست خورد
            logger.debug("LightGBM fit failed; trying XGBoost", exc_info=True)

        try:
            self._model = self._fit_xgboost(labeled_rows, labeled_targets)
            if self._model is not None:
                self._backend = "xgboost"
                return self
        except Exception:  # noqa: BLE001 - شکست آموزش نباید موتور را بکشد
            logger.warning("GBM fit failed on both backends", exc_info=True)
            self._model = None
            self._backend = ""
        return self

    @staticmethod
    def _fit_lightgbm(rows: list[list[float]], targets: list[int]) -> Any:
        """آموزش با API بومی LightGBM — بدون وابستگی sklearn."""
        import lightgbm as lgb
        import numpy as np

        # lgb.Dataset لیستِ لیست را نمی‌پذیرد؛ آرایهٔ numpy بدهیم
        dataset = lgb.Dataset(np.asarray(rows, dtype=np.float64), label=targets)
        booster = lgb.train(_LIGHTGBM_PARAMS, dataset, num_boost_round=NUM_ROUNDS)
        return booster

    @staticmethod
    def _fit_xgboost(rows: list[list[float]], targets: list[int]) -> Any:
        """آموزش با API بومی XGBoost — بدون وابستگی sklearn."""
        import xgboost as xgb

        matrix = xgb.DMatrix(rows, label=targets)
        booster = xgb.train(_XGBOOST_PARAMS, matrix, num_boost_round=NUM_ROUNDS)
        return booster

    def predict(self, row: list[float]) -> ModelOutput:
        """احتمال کلاس صعودی؛ بدون مدل = unavailable صادقانه."""
        if self._model is None or not row:
            return ModelOutput(self.name, 0.5, False, "not_fitted_or_unavailable")
        try:
            if self._backend == "lightgbm":
                import numpy as np

                probability = float(self._model.predict(np.asarray([row], dtype=np.float64))[0])
            else:
                import xgboost as xgb

                probability = float(
                    self._model.predict(xgb.DMatrix([row]))[0]
                )
        except Exception:  # noqa: BLE001
            return ModelOutput(self.name, 0.5, False, "predict_failed")
        if not math.isfinite(probability):
            return ModelOutput(self.name, 0.5, False, "invalid_probability")
        return ModelOutput(self.name, probability, True, self._backend)
