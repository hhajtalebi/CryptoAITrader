"""
مخزن نتیجهٔ واقعی سیگنال‌ها.

این مخزن پل میان منطق خالص `signals/outcome_tracker.py` و پایگاه داده
است: سیگنال‌های تازه را برای پیگیری ثبت می‌کند، وضعیت‌های باز را
برمی‌گرداند تا با قیمت روز به‌روز شوند، و آمار عملکرد را می‌سازد.

قاعدهٔ مهم: هیچ منطق تصمیم‌گیری‌ای اینجا نیست. «آیا به هدف رسید؟» را
ماژول ردیاب پاسخ می‌دهد؛ اینجا فقط خواندن و نوشتن است.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from app.database.models import SignalOutcomeRecord, SignalRecord
from app.database.repositories.base import BaseRepository
from app.logging import get_logger
from signals.outcome_tracker import (
    CLOSED_STATUSES,
    STATUS_CANCELLED,
    STATUS_PENDING,
    OutcomeState,
    confidence_buckets,
    expiry_for,
    group_by,
    summarize,
)

logger = get_logger(__name__)


def _naive(moment: datetime | None) -> datetime | None:
    """
    حذف منطقهٔ زمانی برای ذخیره در SQLite.

    ستون‌های `DateTime` در این پروژه بدون منطقهٔ زمانی‌اند؛ نوشتن مقدار
    آگاه از منطقه، هنگام مقایسه با مقادیر موجود خطا می‌دهد.
    """
    if moment is None:
        return None
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


class SignalOutcomeRepository(BaseRepository[SignalOutcomeRecord]):
    """ثبت و به‌روزرسانی نتیجهٔ سیگنال‌ها و آمار عملکرد."""

    model = SignalOutcomeRecord

    # ------------------------------------------------------------ ثبت

    def track_signal(self, signal_id: int) -> int | None:
        """
        آغاز پیگیری یک سیگنال ذخیره‌شده.

        اگر سیگنال از نوع WAIT باشد یا حد ضرر نداشته باشد، پیگیری معنا
        ندارد و `None` برمی‌گردد. سیگنالی که قبلاً ثبت شده دوباره ثبت
        نمی‌شود (شناسهٔ موجود برمی‌گردد).
        """
        with self._db.session_scope() as session:
            existing = session.execute(
                select(SignalOutcomeRecord.id).where(
                    SignalOutcomeRecord.signal_id == signal_id
                )
            ).scalar_one_or_none()
            if existing is not None:
                return int(existing)

            signal = session.get(SignalRecord, signal_id)
            if signal is None:
                logger.debug("Cannot track unknown signal id=%s", signal_id)
                return None

            direction = str(signal.direction or "").upper()
            if direction not in {"LONG", "SHORT"}:
                # WAIT نتیجه‌ای برای سنجش ندارد.
                return None
            if not signal.stop_loss or signal.stop_loss <= 0:
                logger.debug("Signal id=%s has no stop loss; not tracked", signal_id)
                return None

            entry = self._entry_price(signal)
            if entry <= 0:
                return None

            timeframes = list(signal.timeframes or [])
            primary = str(timeframes[0]) if timeframes else ""
            created = signal.created_at or datetime.utcnow()

            record = SignalOutcomeRecord(
                signal_id=signal_id,
                symbol=signal.symbol,
                direction=direction,
                status=STATUS_PENDING,
                entry_price=entry,
                stop_loss=float(signal.stop_loss),
                take_profits=[float(value) for value in (signal.take_profits or [])],
                confidence=int(signal.confidence or 0),
                primary_timeframe=primary,
                expires_at=_naive(expiry_for(primary, created_at=created)),
            )
            session.add(record)
            session.flush()
            outcome_id = int(record.id)
        logger.info("Tracking signal id=%s (%s)", signal_id, signal_id and outcome_id)
        return outcome_id

    @staticmethod
    def _entry_price(signal: SignalRecord) -> float:
        """
        قیمت ورود مرجع: میانهٔ بازهٔ ورود.

        سیگنال یک **بازه** پیشنهاد می‌دهد نه یک عدد. میانه منصفانه‌ترین
        انتخاب است: نه خوش‌بینانه (لبهٔ بهتر بازه) و نه بدبینانه.
        """
        low = float(signal.entry_min or 0)
        high = float(signal.entry_max or 0)
        if low > 0 and high > 0:
            return (low + high) / 2
        return low or high

    def track_many(self, signal_ids: list[int]) -> int:
        """پیگیری گروهی؛ تعداد موارد تازه‌ثبت‌شده را برمی‌گرداند."""
        return sum(1 for sid in signal_ids if self.track_signal(sid) is not None)

    # ------------------------------------------------------------ خواندن

    def open_outcomes(self, *, limit: int = 200) -> list[SignalOutcomeRecord]:
        """
        نتیجه‌های هنوز باز، قدیمی‌ترین بررسی اول.

        ترتیب عمدی است: نمادی که مدت بیشتری بررسی نشده اولویت دارد تا
        وقتی سقف تعداد می‌خورد، هیچ سیگنالی برای همیشه عقب نیفتد.
        """
        with self._db.session_scope() as session:
            stmt = (
                select(SignalOutcomeRecord)
                .where(SignalOutcomeRecord.status == STATUS_PENDING)
                .order_by(
                    SignalOutcomeRecord.checked_at.is_(None).desc(),
                    SignalOutcomeRecord.checked_at.asc(),
                )
                .limit(limit)
            )
            return list(session.execute(stmt).scalars().all())

    def open_symbols(self) -> list[str]:
        """نمادهای یکتایی که سیگنال باز دارند — برای واکشی قیمت."""
        with self._db.session_scope() as session:
            rows = session.execute(
                select(SignalOutcomeRecord.symbol)
                .where(SignalOutcomeRecord.status == STATUS_PENDING)
                .distinct()
            ).scalars()
            return [str(value) for value in rows]

    def get_by_signal(self, signal_id: int) -> SignalOutcomeRecord | None:
        """نتیجهٔ یک سیگنال مشخص."""
        with self._db.session_scope() as session:
            return session.execute(
                select(SignalOutcomeRecord).where(
                    SignalOutcomeRecord.signal_id == signal_id
                )
            ).scalar_one_or_none()

    def history(
        self,
        *,
        symbol: str = "",
        status: str = "",
        timeframe: str = "",
        min_confidence: int | None = None,
        days: int | None = None,
        limit: int = 500,
    ) -> list[SignalOutcomeRecord]:
        """فهرست نتیجه‌ها با فیلترهای ترکیبی برای صفحهٔ عملکرد."""
        with self._db.session_scope() as session:
            stmt = select(SignalOutcomeRecord)
            if symbol:
                stmt = stmt.where(SignalOutcomeRecord.symbol == symbol)
            if status:
                stmt = stmt.where(SignalOutcomeRecord.status == status.upper())
            if timeframe:
                stmt = stmt.where(SignalOutcomeRecord.primary_timeframe == timeframe)
            if min_confidence is not None:
                stmt = stmt.where(SignalOutcomeRecord.confidence >= min_confidence)
            if days:
                cutoff = datetime.utcnow() - timedelta(days=int(days))
                stmt = stmt.where(SignalOutcomeRecord.created_at >= cutoff)
            stmt = stmt.order_by(SignalOutcomeRecord.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars().all())

    # ------------------------------------------------------------ نوشتن

    def apply_state(self, outcome_id: int, state: OutcomeState) -> bool:
        """
        نوشتن وضعیت محاسبه‌شده روی رکورد.

        ردیاب تصمیم می‌گیرد، اینجا فقط ثبت می‌شود.
        """
        with self._db.session_scope() as session:
            record = session.get(SignalOutcomeRecord, outcome_id)
            if record is None:
                return False
            record.status = state.status
            record.targets_hit = int(state.targets_hit)
            record.exit_price = state.exit_price
            record.result_percent = float(state.result_percent)
            record.realized_r = float(state.realized_r)
            record.max_favorable_percent = float(state.max_favorable_percent)
            record.max_adverse_percent = float(state.max_adverse_percent)
            record.last_price = float(state.last_price)
            record.checked_at = _naive(state.checked_at)
            record.closed_at = _naive(state.closed_at)
            return True

    def cancel(self, outcome_id: int, *, note: str = "") -> bool:
        """لغو دستی پیگیری یک سیگنال."""
        with self._db.session_scope() as session:
            record = session.get(SignalOutcomeRecord, outcome_id)
            if record is None or record.status in CLOSED_STATUSES:
                return False
            record.status = STATUS_CANCELLED
            record.manual = True
            record.closed_at = datetime.utcnow()
            record.note = note
            return True

    def to_state(self, record: SignalOutcomeRecord) -> OutcomeState:
        """تبدیل رکورد پایگاه داده به شیء منطق خالص."""
        return OutcomeState(
            symbol=record.symbol,
            direction=record.direction,
            entry_price=float(record.entry_price or 0),
            stop_loss=float(record.stop_loss or 0),
            take_profits=tuple(float(value) for value in (record.take_profits or [])),
            status=record.status,
            targets_hit=int(record.targets_hit or 0),
            exit_price=record.exit_price,
            result_percent=float(record.result_percent or 0),
            realized_r=float(record.realized_r or 0),
            max_favorable_percent=float(record.max_favorable_percent or 0),
            max_adverse_percent=float(record.max_adverse_percent or 0),
            last_price=float(record.last_price or 0),
            checked_at=record.checked_at,
            closed_at=record.closed_at,
            expires_at=record.expires_at,
            manual=bool(record.manual),
        )

    # ------------------------------------------------------------ آمار

    def performance(self, *, days: int | None = None) -> dict[str, Any]:
        """
        گزارش کامل عملکرد: خلاصه به‌علاوهٔ تفکیک نماد، تایم‌فریم و
        بازهٔ ضریب اطمینان.
        """
        records = self.history(days=days, limit=5000)
        return {
            "summary": summarize(records),
            "by_symbol": group_by(records, "symbol"),
            "by_timeframe": group_by(records, "primary_timeframe"),
            "by_confidence": confidence_buckets(records),
            "by_direction": group_by(records, "direction"),
        }

    def confidence_buckets(self, *, days: int | None = 180) -> dict[str, Any]:
        """
        نرخ برد واقعی به تفکیک بازهٔ ضریب اطمینان.

        موتور سیگنال از این برای کالیبره‌کردن عدد اطمینان استفاده می‌کند:
        اگر سیگنال‌های «۸۰٪» در عمل ۵۰٪ برد داشته‌اند، عدد نمایشی باید
        به واقعیت نزدیک شود.

        نتیجه کش می‌شود چون در مسیر تولید هر سیگنال خوانده می‌شود و
        پرس‌وجوی تاریخچه ارزان نیست.
        """
        import time

        now = time.monotonic()
        cached = getattr(self, "_buckets_cache", None)
        if cached is not None and now - cached[0] < 300.0:
            return cached[1]

        records = self.history(days=days, limit=5000)
        buckets = confidence_buckets(records)
        self._buckets_cache = (now, buckets)
        return buckets

    def pending_count(self) -> int:
        """تعداد سیگنال‌های در حال پیگیری."""
        with self._db.session_scope() as session:
            return int(
                session.execute(
                    select(func.count())
                    .select_from(SignalOutcomeRecord)
                    .where(SignalOutcomeRecord.status == STATUS_PENDING)
                ).scalar()
                or 0
            )

    def backfill(self, *, limit: int = 500) -> int:
        """
        ثبت پیگیری برای سیگنال‌های قدیمی که هنگام تولید ردیابی نشده‌اند.

        بدون این، کاربری که ماه‌ها سیگنال ساخته صفحهٔ عملکرد خالی
        می‌بیند. سیگنال‌های گذشته هم قیمت‌شان قابل بررسی است، پس داده
        از دست نمی‌رود.
        """
        with self._db.session_scope() as session:
            tracked = select(SignalOutcomeRecord.signal_id)
            stmt = (
                select(SignalRecord.id)
                .where(SignalRecord.direction.in_(("LONG", "SHORT")))
                .where(SignalRecord.id.not_in(tracked))
                .order_by(SignalRecord.created_at.desc())
                .limit(limit)
            )
            pending_ids = [int(value) for value in session.execute(stmt).scalars().all()]
        return self.track_many(pending_ids)


__all__ = ["SignalOutcomeRepository"]
