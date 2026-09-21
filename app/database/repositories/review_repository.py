"""
مخزن بازبینی‌های هوش مصنوعی روی سیگنال‌های بسته‌شده.

چرا جدا از مخزن سیگنال؟
    بازبینی چرخهٔ عمر مستقلی دارد: سیگنال یک بار ساخته می‌شود، ولی
    بازبینی ممکن است روزها بعد و فقط برای سیگنال‌های بسته‌شده تولید
    شود. جداکردن مخزن یعنی صفحهٔ سابقه بتواند سیگنال‌ها را بدون
    بارکردن متن‌های بلند بازبینی نشان بدهد.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.database.models import SignalOutcomeRecord, SignalRecord, SignalReviewRecord
from app.database.repositories.base import BaseRepository
from app.logging import get_logger

logger = get_logger(__name__)

#: وضعیت‌هایی که بازبینی‌پذیرند
CLOSED_STATUSES = ("TARGET", "STOP", "EXPIRED")


class SignalReviewRepository(BaseRepository[SignalReviewRecord]):
    """خواندن و نوشتن بازبینی‌ها."""

    model = SignalReviewRecord

    # ------------------------------------------------------------ خواندن

    def for_signal(self, signal_id: int) -> SignalReviewRecord | None:
        """بازبینی یک سیگنال، اگر وجود داشته باشد."""
        with self._db.session_scope() as session:
            record = session.execute(
                select(SignalReviewRecord).where(
                    SignalReviewRecord.signal_id == int(signal_id)
                )
            ).scalar_one_or_none()
            if record is not None:
                session.expunge(record)
            return record

    def reviewed_ids(self) -> set[int]:
        """شناسهٔ سیگنال‌هایی که قبلاً بازبینی شده‌اند."""
        with self._db.session_scope() as session:
            return {
                int(row[0])
                for row in session.execute(select(SignalReviewRecord.signal_id)).all()
            }

    def pending_reviews(self, *, limit: int = 20) -> list[tuple[SignalRecord, SignalOutcomeRecord]]:
        """
        سیگنال‌های بسته‌شده‌ای که هنوز بازبینی نشده‌اند.

        تازه‌ترین‌ها اول: درس یک معاملهٔ دیروز بیشتر از معاملهٔ ماه پیش
        به کار کاربر می‌آید.
        """
        with self._db.session_scope() as session:
            statement = (
                select(SignalRecord, SignalOutcomeRecord)
                .join(SignalOutcomeRecord, SignalOutcomeRecord.signal_id == SignalRecord.id)
                .outerjoin(
                    SignalReviewRecord, SignalReviewRecord.signal_id == SignalRecord.id
                )
                .where(SignalOutcomeRecord.status.in_(CLOSED_STATUSES))
                .where(SignalReviewRecord.id.is_(None))
                .order_by(SignalOutcomeRecord.closed_at.desc())
                .limit(int(limit))
            )
            pairs: list[tuple[SignalRecord, SignalOutcomeRecord]] = []
            for signal, outcome in session.execute(statement).all():
                session.expunge(signal)
                session.expunge(outcome)
                pairs.append((signal, outcome))
            return pairs

    def lesson_counts(self) -> dict[str, int]:
        """
        شمار هر دستهٔ درس.

        این همان چیزی است که به پرسش «چرا سیگنال‌ها سودی نمی‌دهند»
        جواب می‌دهد: اگر بیشتر بازبینی‌ها `LATE_ENTRY` باشند، مشکل
        موتور نیست، سرعت واکنش است.
        """
        with self._db.session_scope() as session:
            rows = session.execute(
                select(SignalReviewRecord.lesson, func.count())
                .group_by(SignalReviewRecord.lesson)
                .order_by(func.count().desc())
            ).all()
            return {str(lesson): int(count) for lesson, count in rows if lesson}

    # ------------------------------------------------------------ نوشتن

    def save(
        self,
        signal_id: int,
        *,
        outcome_status: str,
        verdict: str,
        lesson: str,
        review_text: str,
        ai_provider: str = "",
        ai_model: str = "",
    ) -> int:
        """
        ثبت یا به‌روزرسانی بازبینی یک سیگنال.

        هر سیگنال فقط یک بازبینی دارد؛ تولید دوباره جایگزین می‌شود نه
        اضافه.
        """
        with self._db.session_scope() as session:
            record = session.execute(
                select(SignalReviewRecord).where(
                    SignalReviewRecord.signal_id == int(signal_id)
                )
            ).scalar_one_or_none()

            if record is None:
                record = SignalReviewRecord(signal_id=int(signal_id))
                session.add(record)

            record.outcome_status = str(outcome_status or "")[:20]
            record.verdict = str(verdict or "")[:300]
            record.lesson = str(lesson or "")[:40]
            record.review_text = str(review_text or "")
            record.ai_provider = str(ai_provider or "")[:50]
            record.ai_model = str(ai_model or "")[:100]
            session.flush()
            return int(record.id)

    def stats(self) -> dict[str, Any]:
        """خلاصهٔ وضعیت بازبینی‌ها برای صفحهٔ گزارش."""
        with self._db.session_scope() as session:
            total = int(
                session.execute(
                    select(func.count()).select_from(SignalReviewRecord)
                ).scalar()
                or 0
            )
            closed = int(
                session.execute(
                    select(func.count())
                    .select_from(SignalOutcomeRecord)
                    .where(SignalOutcomeRecord.status.in_(CLOSED_STATUSES))
                ).scalar()
                or 0
            )
        return {
            "reviewed": total,
            "closed": closed,
            "pending": max(0, closed - total),
            "lessons": self.lesson_counts(),
        }
