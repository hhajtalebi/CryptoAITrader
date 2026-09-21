"""
گردآوری داده گزارش.

چرا جدا از خروجی‌گیری است؟
    اصل تفکیک مسئولیت: این ماژول فقط داده را از پایگاه داده جمع می‌کند و
    هیچ اطلاعی از قالب خروجی ندارد. در نتیجه افزودن قالب جدید (مثلاً
    Markdown) نیازی به تغییر این فایل ندارد.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.constants import APP_NAME, APP_VERSION
from app.database.repositories import SignalRepository
from app.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class ReportData:
    """
    داده آماده‌شده یک گزارش.

    ساختار عمداً ساده و مستقل از پایگاه داده است تا خروجی‌گیرها فقط با
    دیکشنری و فهرست سروکار داشته باشند.
    """

    title: str
    generated_at: datetime
    period_from: datetime | None
    period_to: datetime | None
    rows: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    columns: list[str] = field(default_factory=list)
    app_name: str = APP_NAME
    app_version: str = APP_VERSION

    @property
    def is_empty(self) -> bool:
        """آیا گزارش داده‌ای دارد؟"""
        return not self.rows

    @property
    def period_label(self) -> str:
        """برچسب خوانا برای بازه زمانی."""
        if self.period_from and self.period_to:
            return f"{self.period_from:%Y-%m-%d} → {self.period_to:%Y-%m-%d}"
        return "All time"

    def to_dict(self) -> dict[str, Any]:
        """تبدیل کامل برای خروجی JSON."""
        return {
            "title": self.title,
            "app": {"name": self.app_name, "version": self.app_version},
            "generated_at": self.generated_at.isoformat(),
            "period": {
                "from": self.period_from.isoformat() if self.period_from else None,
                "to": self.period_to.isoformat() if self.period_to else None,
                "label": self.period_label,
            },
            "summary": self.summary,
            "columns": self.columns,
            "rows": self.rows,
            "disclaimer": (
                "This report contains technical analysis only and is not financial advice. "
                "Confidence values express the alignment of analytical factors, not a probability of profit."
            ),
        }


#: ستون‌های گزارش سیگنال و برچسب آن‌ها
SIGNAL_COLUMNS: list[tuple[str, str]] = [
    ("created_at", "Date"),
    ("symbol", "Symbol"),
    ("direction", "Direction"),
    ("entry_min", "Entry min"),
    ("entry_max", "Entry max"),
    ("stop_loss", "Stop loss"),
    ("take_profits", "Take profits"),
    ("risk_reward", "R/R"),
    ("leverage", "Leverage"),
    ("confidence", "Confidence"),
    ("trend", "Trend"),
    ("market_structure", "Structure"),
    ("timeframes", "Timeframes"),
    ("ai_provider", "AI provider"),
    ("status", "Status"),
]


class ReportBuilder:
    """
    سازنده گزارش از سابقه سیگنال‌ها.

    نمونه‌سازی:
        builder = ReportBuilder(SignalRepository(db))
        data = builder.build_signal_report(days=30)
    """

    def __init__(self, signal_repository: SignalRepository) -> None:
        self._signals = signal_repository

    def build_signal_report(
        self,
        *,
        days: int | None = 30,
        symbol: str | None = None,
        direction: str | None = None,
        title: str = "Signal History Report",
    ) -> ReportData:
        """
        ساخت گزارش سابقه سیگنال‌ها.

        اگر days برابر None باشد، کل سابقه گزارش می‌شود.
        """
        now = datetime.now(UTC)
        period_from = now - timedelta(days=days) if days else None

        records = self._signals.search(
            symbol=symbol,
            direction=direction,
            date_from=period_from.replace(tzinfo=None) if period_from else None,
            limit=10000,
        )

        rows: list[dict[str, Any]] = []
        for record in records:
            rows.append(
                {
                    "created_at": record.created_at.strftime("%Y-%m-%d %H:%M") if record.created_at else "",
                    "symbol": record.symbol,
                    "direction": record.direction,
                    "entry_min": record.entry_min,
                    "entry_max": record.entry_max,
                    "stop_loss": record.stop_loss,
                    "take_profits": ", ".join(str(t) for t in (record.take_profits or [])),
                    "risk_reward": record.risk_reward,
                    "leverage": record.leverage,
                    "confidence": record.confidence,
                    "trend": record.trend,
                    "market_structure": record.market_structure,
                    "timeframes": ", ".join(record.timeframes or []),
                    "ai_provider": record.ai_provider or "—",
                    "status": record.status,
                }
            )

        summary = self._summarize(rows)
        logger.info("Report built: %d rows over %s", len(rows), f"{days} days" if days else "all time")
        return ReportData(
            title=title,
            generated_at=now,
            period_from=period_from,
            period_to=now,
            rows=rows,
            summary=summary,
            columns=[label for _, label in SIGNAL_COLUMNS],
        )

    @staticmethod
    def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        """
        محاسبه آمار خلاصه.

        توجه: هیچ «نرخ موفقیت» گزارش نمی‌شود، چون نسخه ۱ معامله واقعی
        انجام نمی‌دهد و ادعای نرخ برد بدون اجرای واقعی، گمراه‌کننده است.
        """
        if not rows:
            return {"total": 0}

        directions: dict[str, int] = {}
        symbols: dict[str, int] = {}
        confidences: list[float] = []
        risk_rewards: list[float] = []

        for row in rows:
            directions[row["direction"]] = directions.get(row["direction"], 0) + 1
            symbols[row["symbol"]] = symbols.get(row["symbol"], 0) + 1
            if isinstance(row.get("confidence"), (int, float)):
                confidences.append(float(row["confidence"]))
            if isinstance(row.get("risk_reward"), (int, float)):
                risk_rewards.append(float(row["risk_reward"]))

        return {
            "total": len(rows),
            "by_direction": dict(sorted(directions.items(), key=lambda kv: -kv[1])),
            "unique_symbols": len(symbols),
            "top_symbols": dict(sorted(symbols.items(), key=lambda kv: -kv[1])[:5]),
            "average_confidence": round(sum(confidences) / len(confidences), 1) if confidences else 0.0,
            "average_risk_reward": round(sum(risk_rewards) / len(risk_rewards), 2) if risk_rewards else 0.0,
            # سری زمانی اطمینان برای نمودار صفحهٔ گزارش‌ها؛ ردیف‌ها از
            # جدیدترین به قدیمی‌ترین می‌آیند و برای نمودار وارونه می‌شوند.
            "confidence_series": list(reversed(confidences)),
            "note": "Confidence is factor alignment, not a probability of profit.",
        }

    def build_statistics_report(self, title: str = "Statistics Report") -> ReportData:
        """گزارش آماری کلی از کل سابقه."""
        stats = self._signals.get_statistics()
        now = datetime.now(UTC)
        rows = [{"metric": key, "value": str(value)} for key, value in stats.items()]
        return ReportData(
            title=title,
            generated_at=now,
            period_from=None,
            period_to=now,
            rows=rows,
            summary=stats,
            columns=["Metric", "Value"],
        )
