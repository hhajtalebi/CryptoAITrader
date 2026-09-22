"""
مخزن پیش‌بینی‌های ثبت‌شده — پل DB برای قانون حیاتی ۵.

قاعدهٔ مهم (همانند سایر مخازن): هیچ منطق تصمیم‌گیری اینجا نیست؛
«درست بودن جهت» را `signals/prediction/store.py` محاسبه می‌کند و اینجا
فقط خواندن و نوشتن است.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Integer, func, select

from app.database.models import PredictionRecord
from app.database.repositories.base import BaseRepository
from app.logging import get_logger

logger = get_logger(__name__)

STATUS_OPEN = "open"
STATUS_RESOLVED = "resolved"


def _naive(moment: datetime | None) -> datetime | None:
    """حذف منطقهٔ زمانی برای ذخیره در SQLite (الگوی پروژه)."""
    if moment is None:
        return None
    return moment.replace(tzinfo=None) if moment.tzinfo else moment


class PredictionRepository(BaseRepository[PredictionRecord]):
    """خواندن/نوشتن پیش‌بینی‌ها."""

    model = PredictionRecord

    def record(self, entity: PredictionRecord) -> PredictionRecord:
        """ثبت یک پیش‌بینی تازه."""
        return self.add(entity)

    def due_for_resolution(self, *, now: datetime, limit: int = 200) -> list[PredictionRecord]:
        """پیش‌بینی‌های بازِ سرآمده — باید با قیمت واقعی حل شوند."""
        moment = _naive(now) or datetime.now(timezone.utc).replace(tzinfo=None)
        # حتماً int — مقایسهٔ عدد با رشته در SQLite همیشه True می‌شود
        now_epoch = int(moment.timestamp())
        with self._db.session_scope() as session:
            rows = session.execute(
                select(PredictionRecord)
                .where(
                    PredictionRecord.status == STATUS_OPEN,
                    # افق سپری شده؟ ستون created_at + horizon_minutes*60
                    (
                        func.cast(
                            func.strftime("%s", PredictionRecord.created_at), Integer
                        )
                        + PredictionRecord.horizon_minutes * 60
                    )
                    <= now_epoch,
                )
                .order_by(PredictionRecord.created_at)
                .limit(limit)
            ).scalars().all()
            session.expunge_all()
        return list(rows)

    def resolve(
        self,
        prediction_id: int,
        *,
        actual_price: float,
        direction_correct: bool,
        range_correct: bool,
        resolved_at: datetime,
    ) -> bool:
        """حل یک پیش‌بینی با قیمت واقعی — فقط یک بار."""
        with self._db.session_scope() as session:
            row = session.get(PredictionRecord, prediction_id)
            if row is None or row.status == STATUS_RESOLVED:
                return False
            row.status = STATUS_RESOLVED
            row.actual_price = float(actual_price)
            row.direction_correct = bool(direction_correct)
            row.range_correct = bool(range_correct)
            row.resolved_at = _naive(resolved_at)
            session.commit()
        return True

    def recent(self, *, symbol: str | None = None, limit: int = 50) -> list[PredictionRecord]:
        """آخرین پیش‌بینی‌ها (برای Timeline — خواستهٔ ۲۹)."""
        with self._db.session_scope() as session:
            query = select(PredictionRecord).order_by(PredictionRecord.created_at.desc())
            if symbol:
                query = query.where(PredictionRecord.symbol == symbol)
            rows = session.execute(query.limit(limit)).scalars().all()
            session.expunge_all()
        return list(rows)

    def resolved(self, *, symbol: str | None = None, limit: int = 1000) -> list[PredictionRecord]:
        """پیش‌بینی‌های حل‌شده — مادهٔ خام امتیازدهی و کالیبراسیون."""
        with self._db.session_scope() as session:
            query = (
                select(PredictionRecord)
                .where(PredictionRecord.status == STATUS_RESOLVED)
                .order_by(PredictionRecord.created_at.desc())
            )
            if symbol:
                query = query.where(PredictionRecord.symbol == symbol)
            rows = session.execute(query.limit(limit)).scalars().all()
            session.expunge_all()
        return list(rows)

    def accuracy_group(self, attribute: str) -> dict[str, dict[str, Any]]:
        """دقت به تفکیک یک ستون (horizon/symbol/regime) — قانون ۶."""
        allowed = {"horizon", "symbol", "regime", "method"}
        if attribute not in allowed:
            raise ValueError(f"grouping by {attribute!r} is not allowed")
        column = getattr(PredictionRecord, attribute)
        with self._db.session_scope() as session:
            rows = session.execute(
                select(
                    column,
                    func.count(PredictionRecord.id),
                    func.sum(
                        func.coalesce(PredictionRecord.direction_correct.cast(Integer), 0)
                    ),
                )
                .where(PredictionRecord.status == STATUS_RESOLVED)
                .group_by(column)
            ).all()
        return {
            str(key): {
                "resolved": int(count),
                "direction_hits": int(hits or 0),
                "accuracy": round(int(hits or 0) / int(count), 4) if count else 0.0,
            }
            for key, count, hits in rows
        }
