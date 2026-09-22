"""
آنسامبل وزن‌دار مدل‌ها — خواسته‌های ۲۰، ۲۱، ۲۷ و ۳۶.

چرا این فایل وجود دارد؟
    خواستهٔ ۲۱ دقیقاً مثال زده: XGBoost ۷۲٪، LSTM ۶۴٪، … و خروجی نهایی
    وزن‌دار. وزن هر مدل از عملکرد **walk-forward** خودش می‌آید — مدلی
    که در اعتبارسنجی از شانس (۵۰٪) بهتر نیست، وزنش به حداقل می‌رسد.

    آنسامبل همچنین تشخیص تعارض می‌دهد (خواستهٔ ۳۶): اختلاف بزرگ مدل‌ها
    اعلام می‌شود، نه اینکه زیر میانگین پنهان شود.

انتخاب تطبیقی (خواستهٔ ۲۷): با `reweight`، وزن‌ها بر اساس دقت تفکیکی
(مثلاً به‌ازای هر رژیم) از بیرون به‌روز می‌شوند — فاز ۱۰ این قلاب را
با آمار واقعی از جدول پیش‌بینی‌ها پر می‌کند.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.logging import get_logger
from signals.prediction.models.base import ForecastModel, ModelOutput
from signals.prediction.models.gbm import GBMModel
from signals.prediction.models.lstm import LSTMModel
from signals.prediction.models.statistical import StatisticalModel
from signals.prediction.models.walkforward import WalkForwardResult, walk_forward

logger = get_logger(__name__)

#: وزن حداقلی مدل‌هایی که بهتر از شانس نبوده‌اند.
FLOOR_WEIGHT = 0.1

#: اختلاف جفتی بیش از این (۰..۱) = تعارض مدل‌ها.
MODEL_CONFLICT_THRESHOLD = 0.35


@dataclass(slots=True)
class EnsembleForecast:
    """خروجی آنسامبل برای یک ردیف فیچر."""

    prob_up: float
    per_model: list[ModelOutput] = field(default_factory=list)
    agreement: float = 0.0      # 0..1
    conflict: bool = False
    method: str = "weighted_average"

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "prob_up": round(self.prob_up, 4),
            "per_model": [m.to_dict() for m in self.per_model],
            "agreement": round(self.agreement, 3),
            "conflict": self.conflict,
            "method": self.method,
        }


class ModelEnsemble:
    """
    آنسامبل مدل‌های در دسترس.

    چرخهٔ عمر: `fit` (آموزش همه + اعتبارسنجی غلتان برای وزن‌ها) →
    `predict` (وزن‌دار + تشخیص تعارض) → `reweight` (تطبیق از آمار واقعی).
    """

    def __init__(self, *, include_dl: bool = True) -> None:
        candidates: list[ForecastModel] = [StatisticalModel(), GBMModel()]
        if include_dl:
            candidates.append(LSTMModel())
        self._models = [model for model in candidates if model.is_available()]
        self._weights: dict[str, float] = {}
        self._validation: dict[str, WalkForwardResult] = {}
        self._fitted = False

    # ------------------------------------------------------------------
    @property
    def model_names(self) -> list[str]:
        """نام مدل‌های عضو."""
        return [model.name for model in self._models]

    def validation_summary(self) -> dict[str, Any]:
        """خلاصهٔ اعتبارسنجی هر مدل — برای داشبورد سلامت."""
        return {
            name: result.to_dict() for name, result in self._validation.items()
        }

    # ------------------------------------------------------------------
    def fit(
        self,
        times: list[int],
        rows: list[list[float]],
        labels: list[int | None],
        *,
        gap_seconds: int = 0,
        horizon_steps: int = 1,
        step_seconds: int = 900,
    ) -> "ModelEnsemble":
        """
        آموزش همهٔ مدل‌ها + وزن‌دهی از اعتبارسنجی غلتان.

        پارامترها:
            times/rows/labels : مجموعهٔ کامل (مرتب بر زمان).
            gap_seconds       : گسست purge؛ صفر یعنی «steps افق × گام».
            horizon_steps     : چند گام جلوتر برچسب خورده.
            step_seconds      : طول گام تایم‌فریم مبدأ.
        """
        if not self._models:
            return self
        gap = gap_seconds or max(horizon_steps * step_seconds, 1)

        for model in self._models:
            try:
                model.fit(times, rows, labels)
            except Exception:  # noqa: BLE001 - شکست یک مدل نباید بقیه را ببرد
                logger.warning("Model %s failed to fit", model.name, exc_info=True)

            # اعتبارسنجی غلتان با نسخهٔ تازهٔ همان مدل — ضد نشت
            try:
                result = walk_forward(
                    model.__class__,
                    times=times,
                    rows=rows,
                    labels=labels,
                    gap_seconds=gap,
                )
            except Exception:  # noqa: BLE001 - شکست اعتبارسنجی نباید fit را بکشد
                logger.warning("Walk-forward failed for %s", model.name, exc_info=True)
                result = WalkForwardResult()
                result.note = "validation_failed"
            self._validation[model.name] = result

        self._compute_weights()
        self._fitted = True
        return self

    def _compute_weights(self) -> None:
        """وزن ∝ برتری دقت بر شانس؛ مدل بی‌اعتبار = وزن کف."""
        weights: dict[str, float] = {}
        for model in self._models:
            result = self._validation.get(model.name)
            if result is None or not result.valid:
                weights[model.name] = FLOOR_WEIGHT
                continue
            edge = result.pooled_accuracy - 0.5
            weights[model.name] = max(FLOOR_WEIGHT, edge * 2.0) if edge > 0 else FLOOR_WEIGHT
        total = sum(weights.values())
        if total <= 0:
            self._weights = {name: 1.0 / len(weights) for name in weights}
        else:
            self._weights = {name: weight / total for name, weight in weights.items()}

    def reweight(self, accuracy_by_model: dict[str, float]) -> None:
        """
        به‌روزرسانی وزن‌ها از دقت واقعیِ ثبت‌شده — خواستهٔ ۲۷.

        ورودی: نام مدل → دقت (۰..۱) از جدول پیش‌بینی‌ها. مدل‌های بدون
        آمار دست‌نخورده می‌مانند.
        """
        updated: dict[str, float] = {}
        for name, weight in self._weights.items():
            accuracy = accuracy_by_model.get(name)
            if accuracy is None:
                updated[name] = weight
                continue
            edge = accuracy - 0.5
            updated[name] = max(FLOOR_WEIGHT, edge * 2.0) if edge > 0 else FLOOR_WEIGHT
        total = sum(updated.values())
        if total > 0:
            self._weights = {name: w / total for name, w in updated.items()}

    # ------------------------------------------------------------------
    def predict(self, row: list[float]) -> EnsembleForecast:
        """پیش‌بینی وزن‌دار + توافق + تعارض."""
        outputs: list[tuple[ModelOutput, float]] = []
        for model in self._models:
            if hasattr(model, "remember"):
                model.remember(row)  # type: ignore[attr-defined]
            try:
                output = model.predict(row)
            except Exception:  # noqa: BLE001
                logger.debug("Model %s predict failed", model.name, exc_info=True)
                continue
            if output.available:
                outputs.append((output, self._weights.get(model.name, FLOOR_WEIGHT)))

        if not outputs:
            return EnsembleForecast(0.5, [], 0.0, False, "no_model_available")

        total_weight = sum(weight for _, weight in outputs) or 1.0
        prob = sum(o.prob_up * w for o, w in outputs) / total_weight

        probabilities = [o.prob_up for o, _ in outputs]
        spread = max(probabilities) - min(probabilities)
        agreement = max(0.0, 1.0 - spread)

        return EnsembleForecast(
            prob_up=prob,
            per_model=[o for o, _ in outputs],
            agreement=agreement,
            conflict=spread > MODEL_CONFLICT_THRESHOLD and len(outputs) > 1,
        )

    @property
    def weights(self) -> dict[str, float]:
        """وزن‌های فعلی — برای شفافیت و گزارش."""
        return dict(self._weights)
