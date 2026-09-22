"""
ثبت و حل پیش‌بینی‌ها — اجرای قانون حیاتی ۵.

چرا این فایل وجود دارد؟
    «هر Prediction ذخیره شود… چهار ساعت بعد: Actual — درست بود؟»
    این ماژول دقیقاً همین چرخه را اجرا می‌کند:
    • `save_report`: هر افقِ یک گزارش → یک رکورد open
    • `resolve_due`: رکوردهای سرآمده را با «بستهٔ کندل در لحظهٔ سرآمدن»
      حل می‌کند — نه با قیمت لحظهٔ اجرا (که می‌تواند ساعت‌ها بعد باشد).

    معیار درستی:
    • direction_correct: جهت اعلامی با علامت بازدهٔ افق هم‌خوان باشد؛
      «neutral/uncertain» وقتی درست است که قیمت داخل بازهٔ P25..P75 مانده.
    • range_correct: قیمت واقعی داخل P10..P90 باشد (بازهٔ اعلامی ما).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, Callable

from app.core.models import Candle
from app.logging import get_logger

logger = get_logger(__name__)


def _as_utc(moment: datetime) -> datetime:
    """نرمال‌سازی منطقهٔ زمانی."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class PredictionStore:
    """
    نگارندهٔ چرخهٔ عمر پیش‌بینی‌ها.

    پارامتر سازنده:
        repository: PredictionRepository واقعی (در آزمون با SQLite موقت).
        price_lookup: تابع (symbol, at_utc) → قیمت بستهٔ مرتبط یا None.
                      None یعنی «قیمت واقعی هنوز در دسترس نیست» و حل
                      به بعد موکول می‌شود — هیچ قیمتی جعل نمی‌شود.
    """

    def __init__(
        self,
        repository: Any,
        price_lookup: Callable[[str, datetime], float | None] | None = None,
    ) -> None:
        self._repo = repository
        self._price_lookup = price_lookup

    # ------------------------------------------------------------------
    def save_horizon(
        self,
        *,
        symbol: str,
        horizon: str,
        horizon_minutes: int,
        direction: str,
        probability: int,
        confidence_effective: int,
        quantiles: dict[str, float],
        last_price: float,
        method: str,
        regime: str,
        model_agreement: float,
        models: list[dict[str, Any]] | None = None,
        contributors: list[dict[str, Any]] | None = None,
        created_at: datetime | None = None,
    ) -> Any:
        """ثبت یک افق پیش‌بینی به‌صورت open."""
        from app.database.models import PredictionRecord  # noqa: PLC0415 - جلوگیری از import چرخشی

        entity = PredictionRecord(
            symbol=symbol,
            horizon=horizon,
            horizon_minutes=horizon_minutes,
            direction=direction,
            probability=int(probability),
            confidence_effective=int(confidence_effective),
            p10=float(quantiles.get("p10", 0.0)),
            p25=float(quantiles.get("p25", 0.0)),
            p50=float(quantiles.get("p50", 0.0)),
            p75=float(quantiles.get("p75", 0.0)),
            p90=float(quantiles.get("p90", 0.0)),
            last_price=float(last_price),
            method=method,
            regime=regime,
            model_agreement=float(model_agreement),
            models=list(models or []),
            contributors=list(contributors or []),
            status="open",
        )
        if created_at is not None:
            # ستون‌های DateTime این پروژه naive‌اند (الگوی موجود)
            entity.created_at = created_at.replace(tzinfo=None)
        return self._repo.record(entity)

    # ------------------------------------------------------------------
    def resolve_due(self, *, now: datetime | None = None) -> dict[str, int]:
        """
        حل همهٔ پیش‌بینی‌های سرآمده.

        بازگشتی: آمار {resolved, skipped_no_price, already_done}.
        """
        moment = _as_utc(now or datetime.now(UTC))
        due = self._repo.due_for_resolution(now=moment)
        stats = {"due": len(due), "resolved": 0, "skipped_no_price": 0}

        for record in due:
            expires_at = _as_utc(
                record.created_at.replace(tzinfo=UTC)
            ).timestamp() + record.horizon_minutes * 60
            actual = self._lookup(record.symbol, datetime.fromtimestamp(expires_at, tz=UTC))
            if actual is None or actual <= 0:
                stats["skipped_no_price"] += 1
                continue

            direction_correct = self._judge_direction(record, actual)
            range_correct = bool(
                record.p10 <= actual <= record.p90 if record.p10 > 0 else False
            )
            ok = self._repo.resolve(
                record.id,
                actual_price=actual,
                direction_correct=direction_correct,
                range_correct=range_correct,
                resolved_at=moment,
            )
            if ok:
                stats["resolved"] += 1
        return stats

    def _lookup(self, symbol: str, at: datetime) -> float | None:
        """قیمت واقعی از منبع تزریق‌شده؛ خطا = None نه جعل."""
        if self._price_lookup is None:
            return None
        try:
            value = self._price_lookup(symbol, at)
            return float(value) if value is not None and float(value) > 0 else None
        except Exception:  # noqa: BLE001 - منبع قیمت نباید حل را بکشد
            logger.debug("Price lookup failed for %s", symbol, exc_info=True)
            return None

    @staticmethod
    def _judge_direction(record: Any, actual: float) -> bool:
        """قضاوت درستی جهت — خنثی/نامطمئن با ماندن در بازه درست است."""
        base = record.last_price
        if base <= 0:
            return False
        change = math.log(actual / base)
        if record.direction == "bullish":
            return change > 0
        if record.direction == "bearish":
            return change < 0
        # neutral / uncertain: درست وقتی جنبش معنادار نبوده
        return record.p25 <= actual <= record.p75 if record.p25 > 0 else abs(change) < 0.002


def price_lookup_from_candles(
    candles: list[Candle],
) -> Callable[[str, datetime], float | None]:
    """
    سازندهٔ price_lookup از یک لیست کندل.

    قیمت «بستهٔ آخرین کندلی که پیش از لحظهٔ هدف بسته شده» — نزدیک‌ترین
    واقعیت قابل‌استناد به آن لحظه.
    """
    ordered = sorted(candles, key=lambda candle: candle.timestamp)

    def lookup(_symbol: str, at: datetime) -> float | None:
        target = at.timestamp()
        best: Candle | None = None
        for candle in ordered:
            if candle.timestamp <= target:
                best = candle
            else:
                break
        return float(best.close) if best is not None else None

    return lookup
