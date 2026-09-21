"""
مخزن سیگنال‌ها و تحلیل‌های مرتبط.

هر سیگنال به همراه عکس لحظه‌ای داده‌ای که بر اساس آن ساخته شده ذخیره
می‌شود تا بعداً قابل بازبینی و حسابرسی باشد.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.models import TradingSignal
from app.database.models import SignalAnalysisRecord, SignalRecord
from app.database.repositories.base import BaseRepository
from app.logging import get_logger

logger = get_logger(__name__)


class SignalRepository(BaseRepository[SignalRecord]):
    """ذخیره، جستجو و آمارگیری سیگنال‌ها."""

    model = SignalRecord

    def save_signal(
        self,
        signal: TradingSignal,
        *,
        market_snapshot: dict[str, Any] | None = None,
        ai_raw_response: str = "",
        source: str = "engine",
    ) -> int:
        """
        ذخیره یک سیگنال به همراه تحلیل آن.

        بازگشتی: شناسه سیگنال ذخیره‌شده.
        """
        with self._db.session_scope() as session:
            record = SignalRecord(
                symbol=signal.symbol,
                exchange=signal.exchange,
                direction=signal.direction.value,
                entry_min=signal.entry_min,
                entry_max=signal.entry_max,
                stop_loss=signal.stop_loss,
                take_profits=list(signal.take_profits),
                risk_reward=signal.risk_reward,
                leverage=signal.leverage,
                confidence=signal.confidence,
                trend=signal.trend.value,
                market_structure=signal.market_structure.value,
                timeframes=list(signal.timeframes),
                indicators_used=list(signal.indicators_used),
                ai_provider=signal.ai_provider or "",
                ai_model=signal.ai_model or "",
                reason=signal.reason,
                invalidation=signal.invalidation,
                status=signal.status.value,
                source=source,
                # پنجرهٔ اعتبار و پیش‌بینی تا امروز ذخیره نمی‌شدند، پس
                # سیگنالِ بازخوانده‌شده از پایگاه داده «بی‌تاریخ‌مصرف»
                # به نظر می‌رسید و جدول سابقه ناچار بود دوباره حدس بزند.
                primary_timeframe=signal.primary_timeframe or "",
                enter_before=signal.enter_before,
                valid_until=signal.expires_at,
                forecast=list(signal.forecast or []),
            )
            session.add(record)
            session.flush()

            risk_payload: dict[str, Any] = {}
            if signal.risk is not None:
                risk_payload = {
                    "stop_distance_percent": signal.risk.stop_distance_percent,
                    "risk_reward": signal.risk.risk_reward,
                    "suggested_leverage": signal.risk.suggested_leverage,
                    "position_size": signal.risk.position_size,
                    "risk_amount": signal.risk.risk_amount,
                    "atr_value": signal.risk.atr_value,
                    "volatility_note": signal.risk.volatility_note,
                    "approved": signal.risk.approved,
                    "rejection_reason": signal.risk.rejection_reason,
                }

            session.add(
                SignalAnalysisRecord(
                    signal_id=record.id,
                    analysis_text=signal.analysis_text,
                    market_snapshot=market_snapshot or {},
                    risk_assessment=risk_payload,
                    ai_raw_response=ai_raw_response,
                    data_timestamp=signal.created_at.replace(tzinfo=None),
                )
            )
            signal_id = record.id
        logger.info("Signal saved: id=%s symbol=%s direction=%s", signal_id, signal.symbol, signal.direction.value)
        return signal_id

    def search(
        self,
        *,
        symbol: str | None = None,
        direction: str | None = None,
        min_confidence: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: str = "created_at",
        descending: bool = True,
        limit: int = 200,
        offset: int = 0,
    ) -> list[SignalRecord]:
        """
        جستجوی سیگنال‌ها با فیلترهای ترکیبی برای بخش گزارش‌ها.

        sort_by فقط از میان ستون‌های مجاز پذیرفته می‌شود تا امکان تزریق نام
        ستون دلخواه وجود نداشته باشد.
        """
        allowed_sort = {
            "created_at": SignalRecord.created_at,
            "symbol": SignalRecord.symbol,
            "confidence": SignalRecord.confidence,
            "risk_reward": SignalRecord.risk_reward,
            "direction": SignalRecord.direction,
        }
        sort_column = allowed_sort.get(sort_by, SignalRecord.created_at)

        with self._db.session_scope() as session:
            stmt = select(SignalRecord)
            if symbol:
                stmt = stmt.where(SignalRecord.symbol == symbol)
            if direction:
                stmt = stmt.where(SignalRecord.direction == direction.upper())
            if min_confidence is not None:
                stmt = stmt.where(SignalRecord.confidence >= min_confidence)
            if date_from is not None:
                stmt = stmt.where(SignalRecord.created_at >= date_from)
            if date_to is not None:
                stmt = stmt.where(SignalRecord.created_at <= date_to)
            stmt = stmt.order_by(sort_column.desc() if descending else sort_column.asc())
            stmt = stmt.limit(limit).offset(offset)
            return list(session.execute(stmt).scalars().all())

    def get_latest(self, limit: int = 10) -> list[SignalRecord]:
        """آخرین سیگنال‌ها برای نمایش در داشبورد."""
        return self.search(limit=limit)

    def get_with_analysis(self, signal_id: int) -> tuple[SignalRecord, SignalAnalysisRecord | None] | None:
        """خواندن یک سیگنال به همراه تحلیل کامل آن."""
        with self._db.session_scope() as session:
            record = session.execute(
                select(SignalRecord)
                .options(selectinload(SignalRecord.analysis))
                .where(SignalRecord.id == signal_id)
            ).scalar_one_or_none()
            if record is None:
                return None
            return record, record.analysis

    def analysis_payload(self, signal_id: int) -> dict[str, Any]:
        """
        سیگنال و تحلیلش را به شکل یک دیکشنری تخت برمی‌گرداند.

        `get_with_analysis` یک **تاپل** می‌دهد؛ هرجا نتیجه‌اش را مثل
        دیکشنری باز کرده بودیم خطا می‌گرفت. این متد شکل آمادهٔ نمایش
        می‌دهد تا آن اشتباه تکرار نشود.
        """
        found = self.get_with_analysis(int(signal_id))
        if found is None:
            return {}
        record, analysis = found
        payload: dict[str, Any] = {
            "id": record.id,
            "symbol": record.symbol,
            "direction": record.direction,
            "confidence": record.confidence,
            "timeframe": getattr(record, "primary_timeframe", "") or "",
            "entry_min": record.entry_min,
            "entry_max": record.entry_max,
            "stop_loss": record.stop_loss,
            "created_at": record.created_at,
        }
        if analysis is not None:
            payload["analysis_text"] = analysis.analysis_text or ""
            payload["market_snapshot"] = analysis.market_snapshot or {}
            payload["risk_assessment"] = analysis.risk_assessment or {}
        return payload

    def update_analysis(self, signal_id: int, analysis_text: str) -> bool:
        """
        جایگزینی متن تحلیل یک سیگنال موجود.

        کاربر خواست بتواند روی سیگنالی که قبلاً ساخته شده دوباره تحلیل
        بگیرد؛ نتیجه باید در همان سیگنال ذخیره شود تا دفعهٔ بعد هم
        دیده شود، نه اینکه با بستن پنجره از بین برود.
        """
        with self._db.session_scope() as session:
            record = session.execute(
                select(SignalRecord)
                .options(selectinload(SignalRecord.analysis))
                .where(SignalRecord.id == int(signal_id))
            ).scalar_one_or_none()
            if record is None:
                return False
            if record.analysis is None:
                session.add(
                    SignalAnalysisRecord(
                        signal_id=record.id,
                        analysis_text=analysis_text,
                        market_snapshot={},
                        risk_assessment={},
                        ai_raw_response="",
                        data_timestamp=record.created_at,
                    )
                )
            else:
                record.analysis.analysis_text = analysis_text
        return True

    def get_statistics(self) -> dict[str, Any]:
        """
        آمار کلی سیگنال‌ها برای داشبورد و گزارش‌ها.

        توجه: این آمار «عملکرد معاملاتی» نیست، بلکه صرفاً توزیع سیگنال‌های
        تولیدشده است.
        """
        with self._db.session_scope() as session:
            total = int(session.execute(select(func.count()).select_from(SignalRecord)).scalar() or 0)
            by_direction = dict(
                session.execute(
                    select(SignalRecord.direction, func.count()).group_by(SignalRecord.direction)
                ).all()
            )
            avg_confidence = session.execute(select(func.avg(SignalRecord.confidence))).scalar()
            top_symbols = session.execute(
                select(SignalRecord.symbol, func.count().label("c"))
                .group_by(SignalRecord.symbol)
                .order_by(func.count().desc())
                .limit(5)
            ).all()
        return {
            "total": total,
            "by_direction": {str(k): int(v) for k, v in by_direction.items()},
            "average_confidence": round(float(avg_confidence or 0.0), 1),
            "top_symbols": [{"symbol": s, "count": int(c)} for s, c in top_symbols],
        }
