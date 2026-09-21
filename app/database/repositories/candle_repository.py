"""
مخزن کندل‌ها.

هدف اصلی: نگهداری داده اخیر برای «حالت آفلاین» و کاهش درخواست تکراری از
صرافی. برای سبک ماندن پایگاه داده، فقط تعداد محدودی کندل برای هر
نماد/تایم‌فریم نگهداری می‌شود.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select

from app.core.models import Candle
from app.database.models import CandleRecord, MarketDataSnapshot
from app.database.repositories.base import BaseRepository
from app.logging import get_logger

logger = get_logger(__name__)


class CandleRepository(BaseRepository[CandleRecord]):
    """ذخیره و بازیابی کندل‌ها و آخرین وضعیت لحظه‌ای نمادها."""

    model = CandleRecord

    def save_candles(self, exchange: str, symbol: str, timeframe: str, candles: list[Candle]) -> int:
        """
        ذخیره یا به‌روزرسانی مجموعه‌ای از کندل‌ها.

        کندل جاری (ناتمام) نیز ممکن است بارها به‌روزرسانی شود؛ بنابراین
        رکورد موجود با همان open_time جایگزین می‌شود، نه اینکه رکورد تکراری
        ساخته شود.
        """
        if not candles:
            return 0
        saved = 0
        with self._db.session_scope() as session:
            times = [c.timestamp for c in candles]
            existing = {
                r.open_time: r
                for r in session.execute(
                    select(CandleRecord).where(
                        CandleRecord.exchange == exchange,
                        CandleRecord.symbol == symbol,
                        CandleRecord.timeframe == timeframe,
                        CandleRecord.open_time.in_(times),
                    )
                ).scalars().all()
            }
            for candle in candles:
                record = existing.get(candle.timestamp)
                if record is None:
                    session.add(
                        CandleRecord(
                            exchange=exchange,
                            symbol=symbol,
                            timeframe=timeframe,
                            open_time=candle.timestamp,
                            open=candle.open,
                            high=candle.high,
                            low=candle.low,
                            close=candle.close,
                            volume=candle.volume,
                        )
                    )
                else:
                    record.open = candle.open
                    record.high = candle.high
                    record.low = candle.low
                    record.close = candle.close
                    record.volume = candle.volume
                saved += 1
        return saved

    def get_candles(
        self, exchange: str, symbol: str, timeframe: str, limit: int = 300
    ) -> list[Candle]:
        """
        خواندن آخرین کندل‌های ذخیره‌شده، مرتب‌شده از قدیم به جدید.
        """
        with self._db.session_scope() as session:
            rows = session.execute(
                select(CandleRecord)
                .where(
                    CandleRecord.exchange == exchange,
                    CandleRecord.symbol == symbol,
                    CandleRecord.timeframe == timeframe,
                )
                .order_by(CandleRecord.open_time.desc())
                .limit(limit)
            ).scalars().all()
        return [
            Candle(
                timestamp=r.open_time,
                open=r.open,
                high=r.high,
                low=r.low,
                close=r.close,
                volume=r.volume,
            )
            for r in reversed(rows)
        ]

    def prune(self, exchange: str, symbol: str, timeframe: str, keep: int = 1000) -> int:
        """
        حذف کندل‌های قدیمی و نگهداری فقط «keep» کندل آخر.

        این کار از رشد بی‌رویه فایل پایگاه داده جلوگیری می‌کند.
        """
        with self._db.session_scope() as session:
            total = int(
                session.execute(
                    select(func.count())
                    .select_from(CandleRecord)
                    .where(
                        CandleRecord.exchange == exchange,
                        CandleRecord.symbol == symbol,
                        CandleRecord.timeframe == timeframe,
                    )
                ).scalar()
                or 0
            )
            if total <= keep:
                return 0
            cutoff = session.execute(
                select(CandleRecord.open_time)
                .where(
                    CandleRecord.exchange == exchange,
                    CandleRecord.symbol == symbol,
                    CandleRecord.timeframe == timeframe,
                )
                .order_by(CandleRecord.open_time.desc())
                .offset(keep)
                .limit(1)
            ).scalar()
            if cutoff is None:
                return 0
            result = session.execute(
                delete(CandleRecord).where(
                    CandleRecord.exchange == exchange,
                    CandleRecord.symbol == symbol,
                    CandleRecord.timeframe == timeframe,
                    CandleRecord.open_time <= cutoff,
                )
            )
            return int(result.rowcount or 0)

    def save_ticker_snapshot(
        self,
        exchange: str,
        symbol: str,
        *,
        last_price: float,
        high_24h: float = 0.0,
        low_24h: float = 0.0,
        volume_24h: float = 0.0,
        turnover_24h: float = 0.0,
        change_percent: float = 0.0,
    ) -> None:
        """ذخیره آخرین وضعیت لحظه‌ای یک نماد برای نمایش در حالت آفلاین."""
        with self._db.session_scope() as session:
            record = session.execute(
                select(MarketDataSnapshot).where(
                    MarketDataSnapshot.exchange == exchange, MarketDataSnapshot.symbol == symbol
                )
            ).scalar_one_or_none()
            if record is None:
                record = MarketDataSnapshot(exchange=exchange, symbol=symbol)
                session.add(record)
            record.last_price = last_price
            record.high_24h = high_24h
            record.low_24h = low_24h
            record.volume_24h = volume_24h
            record.turnover_24h = turnover_24h
            record.change_percent = change_percent

    def get_ticker_snapshots(self, exchange: str) -> dict[str, dict[str, float]]:
        """خواندن تمام وضعیت‌های لحظه‌ای ذخیره‌شده یک صرافی."""
        with self._db.session_scope() as session:
            rows = session.execute(
                select(MarketDataSnapshot).where(MarketDataSnapshot.exchange == exchange)
            ).scalars().all()
            return {
                r.symbol: {
                    "last_price": r.last_price,
                    "high_24h": r.high_24h,
                    "low_24h": r.low_24h,
                    "volume_24h": r.volume_24h,
                    "turnover_24h": r.turnover_24h,
                    "change_percent": r.change_percent,
                }
                for r in rows
            }
