"""
مخزن معاملات کاغذی.

کاربر خواسته است دکمهٔ «معامله» فعلاً فقط معاملهٔ شبیه‌سازی‌شده ثبت کند.
معماری طوری است که با روشن‌شدن سفارش‌گذاری واقعی، تنها منبع پرشدن سفارش
عوض می‌شود و صفحهٔ «تاریخچهٔ معاملات» و گزارش‌ها دست‌نخورده می‌مانند —
به همین دلیل ستون `mode` از همین حالا وجود دارد.

الگوی خروجی: دیکشنری، نه شیء ORM (مثل بقیهٔ مخازن این پروژه).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select

from app.database.models import PaperTradeRecord
from app.database.repositories.base import BaseRepository
from app.logging import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    """زمان جاری UTC بدون منطقهٔ زمانی."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_dict(record: PaperTradeRecord) -> dict[str, Any]:
    """تبدیل رکورد معامله به دیکشنری برای لایهٔ رابط کاربری."""
    return {
        "id": record.id,
        "user_id": record.user_id,
        "account_id": record.account_id,
        "signal_id": record.signal_id,
        "symbol": record.symbol,
        "side": record.side,
        "status": record.status,
        "mode": record.mode,
        "quantity": record.quantity,
        "entry_price": record.entry_price,
        "exit_price": record.exit_price,
        "stop_loss": record.stop_loss,
        "take_profit": record.take_profit,
        "leverage": record.leverage,
        "fee": record.fee,
        "pnl": record.pnl,
        "pnl_percent": record.pnl_percent,
        "last_price": record.last_price,
        "opened_at": record.opened_at,
        "closed_at": record.closed_at,
        "note": record.note,
        "extra": dict(record.extra or {}),
    }


class PaperTradeRepository(BaseRepository[PaperTradeRecord]):
    """ثبت، به‌روزرسانی و گزارش‌گیری معاملات کاغذی."""

    model = PaperTradeRecord

    # ------------------------------------------------------------------
    # نوشتن
    # ------------------------------------------------------------------
    def open_trade(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        user_id: int | None = None,
        account_id: int | None = None,
        signal_id: int | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        leverage: float = 1.0,
        fee: float = 0.0,
        mode: str = "paper",
        note: str = "",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """باز کردن یک معاملهٔ تازه و بازگرداندن رکورد آن."""
        with self._db.session_scope() as session:
            record = PaperTradeRecord(
                user_id=user_id,
                account_id=account_id,
                signal_id=signal_id,
                symbol=(symbol or "").upper(),
                side=(side or "long").lower(),
                status="open",
                mode=mode,
                quantity=float(quantity or 0.0),
                entry_price=float(entry_price or 0.0),
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=float(leverage or 1.0),
                fee=float(fee or 0.0),
                note=note or "",
                extra=dict(extra or {}),
                opened_at=_utcnow(),
            )
            session.add(record)
            session.flush()
            logger.info(
                "Paper trade opened: %s %s qty=%s @ %s",
                record.side,
                record.symbol,
                record.quantity,
                record.entry_price,
            )
            return _to_dict(record)

    def update_live_pnl(
        self, trade_id: int, *, price: float, pnl: float, pnl_percent: float
    ) -> bool:
        """
        ثبت سود/زیان تحقق‌نیافتهٔ یک معاملهٔ باز.

        بدون این، ستون سود/زیان تا لحظهٔ بستن خالی می‌ماند و کاربر
        نمی‌داند معامله‌اش در چه وضعی است — همان «معلوم نیست سود و
        زیان چه می‌شود».
        """
        with self._db.session_scope() as session:
            record = session.get(PaperTradeRecord, int(trade_id))
            if record is None or record.status != "open":
                return False
            record.pnl = float(pnl)
            record.pnl_percent = float(pnl_percent)
            record.last_price = float(price)
            return True

    def close_trade(
        self,
        trade_id: int,
        *,
        exit_price: float,
        fee: float = 0.0,
        note: str = "",
    ) -> dict[str, Any] | None:
        """
        بستن معامله و محاسبهٔ سود/زیان.

        محاسبه جهت‌آگاه است: در موقعیت فروش، افت قیمت سود محسوب می‌شود.
        اهرم در سود درصدی ضرب می‌گردد چون همان چیزی است که کاربر در حساب
        فیوچرز می‌بیند.
        """
        with self._db.session_scope() as session:
            record = session.get(PaperTradeRecord, int(trade_id))
            if record is None or record.status != "open":
                return None

            price = float(exit_price or 0.0)
            entry = float(record.entry_price or 0.0)
            direction = 1.0 if record.side == "long" else -1.0
            gross = (price - entry) * direction * float(record.quantity or 0.0)
            total_fee = float(record.fee or 0.0) + float(fee or 0.0)

            record.exit_price = price
            record.fee = total_fee
            record.pnl = gross - total_fee
            record.pnl_percent = (
                ((price - entry) / entry * 100.0 * direction * float(record.leverage or 1.0))
                if entry
                else 0.0
            )
            record.status = "closed"
            record.closed_at = _utcnow()
            if note:
                record.note = note
            logger.info("Paper trade closed: id=%s pnl=%.4f", trade_id, record.pnl)
            return _to_dict(record)

    def cancel_trade(self, trade_id: int) -> bool:
        """لغو یک معاملهٔ باز بدون ثبت سود یا زیان."""
        with self._db.session_scope() as session:
            record = session.get(PaperTradeRecord, int(trade_id))
            if record is None or record.status != "open":
                return False
            record.status = "cancelled"
            record.closed_at = _utcnow()
            return True

    def delete_trade(self, trade_id: int) -> bool:
        """حذف یک معامله از تاریخچه."""
        with self._db.session_scope() as session:
            record = session.get(PaperTradeRecord, int(trade_id))
            if record is None:
                return False
            session.delete(record)
            return True

    def clear_history(self, user_id: int | None = None) -> int:
        """پاک‌کردن کل تاریخچه (با تأیید کاربر در رابط کاربری)."""
        with self._db.session_scope() as session:
            stmt = delete(PaperTradeRecord)
            if user_id is not None:
                stmt = stmt.where(PaperTradeRecord.user_id == int(user_id))
            return int(session.execute(stmt).rowcount or 0)

    # ------------------------------------------------------------------
    # خواندن
    # ------------------------------------------------------------------
    def list_trades(
        self,
        *,
        user_id: int | None = None,
        symbol: str = "",
        side: str = "",
        status: str = "",
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        فهرست معاملات با فیلترهای صفحهٔ «تاریخچهٔ معاملات».

        فیلتر خالی یعنی «همه»، بنابراین رابط کاربری می‌تواند بی‌قید و شرط
        همین متد را صدا بزند.
        """
        with self._db.session_scope() as session:
            stmt = select(PaperTradeRecord)
            stmt = self._apply_filters(stmt, user_id, symbol, side, status, start, end)
            stmt = (
                stmt.order_by(PaperTradeRecord.opened_at.desc())
                .limit(int(limit))
                .offset(int(offset))
            )
            return [_to_dict(item) for item in session.execute(stmt).scalars().all()]

    def count_trades(
        self,
        *,
        user_id: int | None = None,
        symbol: str = "",
        side: str = "",
        status: str = "",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> int:
        """شمار معاملات مطابق فیلتر — برای صفحه‌بندی."""
        with self._db.session_scope() as session:
            stmt = select(func.count()).select_from(PaperTradeRecord)
            stmt = self._apply_filters(stmt, user_id, symbol, side, status, start, end)
            return int(session.execute(stmt).scalar_one())

    def open_trades(self, user_id: int | None = None) -> list[dict[str, Any]]:
        """معاملات باز — برای محاسبهٔ سود شناور و کارت‌های داشبورد."""
        return self.list_trades(user_id=user_id, status="open", limit=500)

    def statistics(
        self,
        *,
        user_id: int | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, Any]:
        """
        آمار کلی برای نوار معیارها و صفحهٔ گزارش‌ها.

        شامل: تعداد کل، بسته‌شده، برنده، بازنده، نرخ برد، مجموع سود و
        میانگین سود درصدی.
        """
        with self._db.session_scope() as session:
            stmt = select(PaperTradeRecord)
            stmt = self._apply_filters(stmt, user_id, "", "", "", start, end)
            records = list(session.execute(stmt).scalars().all())

        closed = [item for item in records if item.status == "closed"]
        wins = [item for item in closed if (item.pnl or 0.0) > 0]
        losses = [item for item in closed if (item.pnl or 0.0) < 0]
        total_pnl = sum(float(item.pnl or 0.0) for item in closed)
        gross_win = sum(float(item.pnl or 0.0) for item in wins)
        gross_loss = abs(sum(float(item.pnl or 0.0) for item in losses))

        return {
            "total": len(records),
            "open": len([item for item in records if item.status == "open"]),
            "closed": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": (len(wins) / len(closed) * 100.0) if closed else 0.0,
            "total_pnl": total_pnl,
            "average_pnl_percent": (
                sum(float(item.pnl_percent or 0.0) for item in closed) / len(closed)
                if closed
                else 0.0
            ),
            "best": max((float(item.pnl or 0.0) for item in closed), default=0.0),
            "worst": min((float(item.pnl or 0.0) for item in closed), default=0.0),
            # ضریب سود: نسبت مجموع سودها به مجموع زیان‌ها
            "profit_factor": (gross_win / gross_loss) if gross_loss else 0.0,
        }

    def equity_curve(
        self, *, user_id: int | None = None, starting_balance: float = 0.0
    ) -> list[float]:
        """
        منحنی رشد سرمایه بر پایهٔ معاملات بسته‌شده.

        برای نمودار مساحتی صفحهٔ کیف پول و گزارش‌ها استفاده می‌شود.
        """
        with self._db.session_scope() as session:
            stmt = select(PaperTradeRecord).where(PaperTradeRecord.status == "closed")
            if user_id is not None:
                stmt = stmt.where(PaperTradeRecord.user_id == int(user_id))
            records = list(
                session.execute(stmt.order_by(PaperTradeRecord.closed_at)).scalars().all()
            )

        balance = float(starting_balance)
        curve = [balance]
        for item in records:
            balance += float(item.pnl or 0.0)
            curve.append(balance)
        return curve

    def symbols_traded(self, user_id: int | None = None) -> list[str]:
        """فهرست نمادهای معامله‌شده — برای پرکردن فیلتر نماد."""
        with self._db.session_scope() as session:
            stmt = select(PaperTradeRecord.symbol).distinct()
            if user_id is not None:
                stmt = stmt.where(PaperTradeRecord.user_id == int(user_id))
            return sorted(item for item in session.execute(stmt).scalars().all() if item)

    # ------------------------------------------------------------------
    # داخلی
    # ------------------------------------------------------------------
    @staticmethod
    def _apply_filters(stmt, user_id, symbol, side, status, start, end):
        """اعمال فیلترهای مشترک روی یک پرس‌وجو."""
        if user_id is not None:
            stmt = stmt.where(PaperTradeRecord.user_id == int(user_id))
        if symbol:
            stmt = stmt.where(PaperTradeRecord.symbol == symbol.upper())
        if side:
            stmt = stmt.where(PaperTradeRecord.side == side.lower())
        if status:
            stmt = stmt.where(PaperTradeRecord.status == status.lower())
        if start is not None:
            stmt = stmt.where(PaperTradeRecord.opened_at >= start)
        if end is not None:
            stmt = stmt.where(PaperTradeRecord.opened_at <= end)
        return stmt


__all__ = ["PaperTradeRepository"]
