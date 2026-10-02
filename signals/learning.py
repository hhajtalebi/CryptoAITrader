"""
موتور یادگیری از نتایج — نسخهٔ ۲.۵.۵.

هر سیگنال یک «عکس لحظه‌ای» (snapshot) از شرایط تصمیم دارد و هر معامله/
نتیجه یک «پیامد» (outcome). این ماژول این دو را کنار هم می‌گذارد و دو
خروجی کاملاً محافظه‌کارانه می‌سازد:

1. **ضریب وزن راهبرد به تفکیک رژیم** (۰٫۸ تا ۱٫۲۵):
   اگر راهبردی در رژیم «range» وقتی هم‌جهت معامله رأی داده، به‌طور
   معنادار بهتر از میانگین همان رژیم عمل کرده، وزنش کمی بالا می‌رود و
   برعکس. بدون دادهٔ کافی ضریب دقیقاً ۱٫۰ است.

2. **حافظهٔ الگو (historical edge)** برای ترکیب «جهت × رژیم × تایم‌فریم»:
   عدد ۰ تا ۱۰۰ که ۵۰ یعنی «خنثی/نامعلوم».

قواعد ضدبیش‌برازش (خواستهٔ صریح کاربر: «۳ معامله نباید باعث بلاک شود»):
   • حداقل نمونه (پیش‌فرض ۳۰) — زیر آن خروجی خنثی است.
   • هموارسازی بتا (Beta prior) برای نرخ برد و انقباض میانگین R به صفر.
   • بازهٔ اطمینان ویلسون گزارش می‌شود تا کاربر عدم‌قطعیت را ببیند.
   • تفکیک رژیم؛ الگوی یک رژیم به رژیم دیگر تعمیم داده نمی‌شود مگر در
     سطح سلسله‌مراتبی بالاتر (جهت×رژیم → رژیم).
   • ضرایب محدود (bounded) هستند؛ یادگیری هرگز یک راهبرد را خاموش نمی‌کند.

منابع داده:
   • `signal_outcomes` + `signal_analysis.market_snapshot["intelligence"]`
   • `paper_trades.extra["intelligence"]` (معاملات کاغذی خط لوله واقعی)
   • رکوردهای بک‌تست (در walk-forward فقط از بازهٔ آموزش).
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: حداقل نمونه برای اعتماد به یک الگو/ضریب
MIN_SAMPLES = 30
#: قدرت پیشین بتا (معادل این تعداد معامله با نرخ ۵۰٪)
PRIOR_STRENGTH = 10.0
#: مرز ضرایب وزن راهبرد
MULTIPLIER_BOUNDS = (0.8, 1.25)
#: رأی با قدر مطلق کمتر از این «نظر جهت‌دار» حساب نمی‌شود
VOTE_THRESHOLD = 0.15


def wilson_interval(wins: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """بازهٔ اطمینان ویلسون برای نرخ برد (۰ تا ۱)."""
    if total <= 0:
        return 0.0, 1.0
    p = wins / total
    denom = 1.0 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def smoothed_rate(wins: float, total: float, prior: float = 0.5, strength: float = PRIOR_STRENGTH) -> float:
    """نرخ برد هموارشده با پیشین بتا."""
    return (wins + prior * strength) / (total + strength)


def shrunk_mean(total_r: float, count: int, strength: float = PRIOR_STRENGTH) -> float:
    """میانگین R منقبض‌شده به صفر؛ با نمونهٔ کم نزدیک صفر می‌ماند."""
    return total_r / (count + strength)


@dataclass(slots=True)
class OutcomeRecord:
    """یک پیامد همراه با عکس لحظه‌ای تصمیم."""

    direction: str
    won: bool
    r_multiple: float
    regime: str = "unknown"
    timeframe: str = ""
    quality: str = ""
    symbol: str = ""
    strategy_scores: dict[str, float] = field(default_factory=dict)
    source: str = ""
    pnl: float = 0.0
    mae: float = 0.0
    mfe: float = 0.0
    exit_reason: str = ""
    duration_minutes: float = 0.0
    #: نسخهٔ ۲.۵.۶ — سطل کشیدگی حرکت هنگام ورود ("<1" / "1-2" / ">=2" یا "")
    extension: str = ""

    def agreeing_strategies(self) -> list[str]:
        """راهبردهایی که هم‌جهت معامله رأی داده بودند."""
        sign = 1.0 if self.direction == "LONG" else -1.0
        return [
            name for name, score in self.strategy_scores.items()
            if score * sign > VOTE_THRESHOLD
        ]


@dataclass(slots=True)
class _Stats:
    count: int = 0
    wins: int = 0
    total_r: float = 0.0

    def add(self, won: bool, r_multiple: float) -> None:
        self.count += 1
        self.wins += int(won)
        self.total_r += float(r_multiple)

    def summary(self, min_samples: int) -> dict[str, Any]:
        low, high = wilson_interval(self.wins, self.count)
        return {
            "samples": self.count,
            "win_rate": round(self.wins / self.count, 4) if self.count else None,
            "smoothed_win_rate": round(smoothed_rate(self.wins, self.count), 4),
            "avg_r": round(self.total_r / self.count, 4) if self.count else None,
            "shrunk_r": round(shrunk_mean(self.total_r, self.count), 4),
            "ci95": [round(low, 4), round(high, 4)],
            "reliable": self.count >= min_samples,
        }


class PerformanceLearner:
    """یادگیرندهٔ محافظه‌کار نتایج؛ بدون داده کاملاً خنثی."""

    def __init__(
        self,
        *,
        min_samples: int = MIN_SAMPLES,
        bounds: tuple[float, float] = MULTIPLIER_BOUNDS,
        sensitivity: float = 0.6,
    ) -> None:
        self.min_samples = int(min_samples)
        self.bounds = bounds
        self.sensitivity = float(sensitivity)
        self._records = 0
        self._overall = _Stats()
        self._by_regime: dict[str, _Stats] = defaultdict(_Stats)
        self._by_pattern: dict[tuple[str, ...], _Stats] = defaultdict(_Stats)
        self._by_strategy_regime: dict[tuple[str, str], _Stats] = defaultdict(_Stats)
        self._by_quality: dict[str, _Stats] = defaultdict(_Stats)
        self._multipliers: dict[tuple[str, str], float] = {}

    # ------------------------------------------------------------------
    def fit(self, records: Iterable[OutcomeRecord]) -> PerformanceLearner:
        """یادگیری از فهرست پیامدها (جایگزین کامل وضعیت قبلی)."""
        self.__init__(min_samples=self.min_samples, bounds=self.bounds, sensitivity=self.sensitivity)
        for record in records:
            if record.direction not in ("LONG", "SHORT"):
                continue
            self._records += 1
            regime = record.regime or "unknown"
            self._overall.add(record.won, record.r_multiple)
            self._by_regime[regime].add(record.won, record.r_multiple)
            self._by_pattern[(record.direction, regime, record.timeframe)].add(record.won, record.r_multiple)
            self._by_pattern[(record.direction, regime)].add(record.won, record.r_multiple)
            if record.extension:
                self._by_pattern[(record.direction, regime, "ext:" + record.extension)].add(
                    record.won, record.r_multiple
                )
            if record.quality:
                self._by_quality[record.quality].add(record.won, record.r_multiple)
            for name in record.agreeing_strategies():
                self._by_strategy_regime[(name, regime)].add(record.won, record.r_multiple)

        low, high = self.bounds
        for (name, regime), stats in self._by_strategy_regime.items():
            if stats.count < self.min_samples:
                continue
            base = self._by_regime.get(regime) or self._overall
            delta = shrunk_mean(stats.total_r, stats.count) - shrunk_mean(base.total_r, base.count)
            self._multipliers[(name, regime)] = max(low, min(high, 1.0 + self.sensitivity * delta))
        return self

    # ------------------------------------------------------------------
    @property
    def record_count(self) -> int:
        """تعداد پیامدهای یادگرفته‌شده."""
        return self._records

    def strategy_multiplier(self, strategy: str, regime: str | None) -> float:
        """ضریب وزن راهبرد در رژیم؛ بدون دادهٔ کافی دقیقاً ۱٫۰."""
        if not regime:
            return 1.0
        return self._multipliers.get((strategy, regime), 1.0)

    def multipliers_for(self, regime: str | None) -> dict[str, float]:
        """همهٔ ضرایب غیر ۱ یک رژیم (برای _aggregate و نمایش)."""
        if not regime:
            return {}
        return {name: value for (name, reg), value in self._multipliers.items() if reg == regime}

    def historical_edge(
        self, direction: str, regime: str | None, timeframe: str = "", extension: str = ""
    ) -> dict[str, Any]:
        """
        لبهٔ تاریخی الگو (۰ تا ۱۰۰؛ ۵۰ = خنثی).

        سلسله‌مراتب: (جهت، رژیم، تایم‌فریم) → (جهت، رژیم). اگر هیچ‌کدام به
        حداقل نمونه نرسد، خروجی خنثی با reliable=False است.
        """
        regime = regime or "unknown"
        keys: list[tuple[str, ...]] = []
        if extension:
            # دقیق‌ترین سطح: همین جهت و رژیم در همین میزان کشیدگی حرکت
            keys.append((direction, regime, "ext:" + extension))
        keys += [(direction, regime, timeframe), (direction, regime)]
        for key in keys:
            stats = self._by_pattern.get(key)
            if stats is None or stats.count < self.min_samples:
                continue
            summary = stats.summary(self.min_samples)
            shrunk = shrunk_mean(stats.total_r, stats.count)
            edge = 50.0 + 40.0 * math.tanh(shrunk)
            return {
                "edge": int(round(max(0.0, min(100.0, edge)))),
                "level": "/".join(k for k in key if k),
                **summary,
            }
        stats = self._by_pattern.get((direction, regime))
        return {
            "edge": 50,
            "level": "neutral",
            "samples": stats.count if stats else 0,
            "reliable": False,
            "ci95": None,
            "win_rate": None,
        }

    def quality_report(self) -> dict[str, Any]:
        """عملکرد به تفکیک کیفیت (STRONG/NORMAL/WEAK)."""
        return {name: stats.summary(self.min_samples) for name, stats in self._by_quality.items()}

    def health(self) -> dict[str, Any]:
        """سلامت یادگیرنده برای دروازهٔ اعتبارسنجی و UI."""
        reliable_patterns = sum(1 for s in self._by_pattern.values() if s.count >= self.min_samples)
        status = "ok" if self._records >= self.min_samples * 3 else (
            "learning" if self._records else "empty"
        )
        return {
            "records": self._records,
            "reliable_patterns": reliable_patterns,
            "active_multipliers": len(self._multipliers),
            "min_samples": self.min_samples,
            "status": status,
            "overall": self._overall.summary(self.min_samples) if self._records else None,
        }

    def to_dict(self) -> dict[str, Any]:
        """خلاصهٔ قابل ذخیره/نمایش."""
        return {
            "health": self.health(),
            "multipliers": {f"{s}@{r}": round(v, 4) for (s, r), v in self._multipliers.items()},
            "quality": self.quality_report(),
        }


# ----------------------------------------------------------------------
# ساخت رکورد از داده‌های ذخیره‌شده
# ----------------------------------------------------------------------
def record_from_snapshot(
    intelligence: dict[str, Any] | None,
    *,
    direction: str,
    r_multiple: float,
    won: bool | None = None,
    **extra: Any,
) -> OutcomeRecord | None:
    """ساخت OutcomeRecord از عکس لحظه‌ای `signal.intelligence`."""
    if direction not in ("LONG", "SHORT"):
        return None
    intel = intelligence or {}
    regime = intel.get("regime") or "unknown"
    if isinstance(regime, dict):
        regime = regime.get("regime") or "unknown"
    return OutcomeRecord(
        direction=direction,
        won=bool(r_multiple > 0) if won is None else bool(won),
        r_multiple=float(r_multiple),
        regime=str(regime),
        timeframe=str(intel.get("primary_timeframe") or extra.pop("timeframe", "") or ""),
        extension=str(intel.get("extension_bucket") or ""),
        quality=str(intel.get("quality") or ""),
        strategy_scores={
            str(k): float(v) for k, v in (intel.get("strategy_scores") or {}).items()
            if isinstance(v, (int, float))
        },
        **{k: v for k, v in extra.items() if k in OutcomeRecord.__slots__},
    )


def load_records_from_database(database: Any, *, limit: int = 5000) -> list[OutcomeRecord]:
    """
    خواندن پیامدهای بسته‌شده از پایگاه داده.

    • signal_outcomes (TARGET/STOP/EXPIRED) + market_snapshot["intelligence"]
    • paper_trades بسته‌شده با extra["intelligence"]
    هر خطا → فهرست خالی (یادگیرنده خنثی می‌ماند، برنامه متوقف نمی‌شود).
    """
    records: list[OutcomeRecord] = []
    try:
        from sqlalchemy import select

        from app.database.models import SignalAnalysisRecord, SignalOutcomeRecord

        with database.session_scope() as session:
            stmt = (
                select(SignalOutcomeRecord, SignalAnalysisRecord.market_snapshot)
                .join(
                    SignalAnalysisRecord,
                    SignalAnalysisRecord.signal_id == SignalOutcomeRecord.signal_id,
                    isouter=True,
                )
                .where(SignalOutcomeRecord.status.in_(("TARGET", "STOP", "EXPIRED")))
                .order_by(SignalOutcomeRecord.id.desc())
                .limit(limit)
            )
            for outcome, snapshot in session.execute(stmt).all():
                intel = (snapshot or {}).get("intelligence") if isinstance(snapshot, dict) else None
                record = record_from_snapshot(
                    intel,
                    direction=str(outcome.direction),
                    r_multiple=float(outcome.realized_r or 0.0),
                    symbol=str(outcome.symbol),
                    source="outcome",
                    mae=float(outcome.max_adverse_percent or 0.0),
                    mfe=float(outcome.max_favorable_percent or 0.0),
                    exit_reason=str(outcome.status),
                    timeframe=str(outcome.primary_timeframe or ""),
                )
                if record is not None:
                    records.append(record)
    except Exception:
        logger.debug("Learning: signal outcomes unavailable", exc_info=True)
    try:
        from sqlalchemy import func, select

        from app.database.models import PaperTradeRecord

        with database.session_scope() as session:
            stmt = (
                select(PaperTradeRecord)
                .where(func.lower(PaperTradeRecord.status) == "closed")
                .order_by(PaperTradeRecord.id.desc())
                .limit(limit)
            )
            for trade in session.execute(stmt).scalars().all():
                extra = trade.extra if isinstance(trade.extra, dict) else {}
                intel = extra.get("intelligence")
                if not intel:
                    continue
                risk = abs(float(trade.entry_price or 0) - float(trade.stop_loss or 0)) * float(trade.quantity or 0)
                pnl = float(trade.pnl or 0.0)
                r_multiple = pnl / risk if risk > 0 else (1.0 if pnl > 0 else -1.0)
                record = record_from_snapshot(
                    intel,
                    direction="LONG" if str(trade.side).upper() in ("LONG", "BUY") else "SHORT",
                    r_multiple=r_multiple,
                    symbol=str(trade.symbol),
                    source="paper",
                    pnl=pnl,
                )
                if record is not None:
                    records.append(record)
    except Exception:
        logger.debug("Learning: paper trades unavailable", exc_info=True)
    return records


__all__ = [
    "MIN_SAMPLES",
    "OutcomeRecord",
    "PerformanceLearner",
    "load_records_from_database",
    "record_from_snapshot",
    "shrunk_mean",
    "smoothed_rate",
    "wilson_interval",
]
