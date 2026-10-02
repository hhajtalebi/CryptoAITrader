"""
مخزن رویدادهای ممیزی (نسخهٔ ۲.۶.۰) — جست‌وجوی سریع و خط زمانی معامله.

نوشتن فقط از رشتهٔ پس‌زمینهٔ `AuditStoreWriter` و دسته‌ای انجام می‌شود؛
مسیر ورود معامله هرگز منتظر این مخزن نمی‌ماند.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, or_, select

from app.database.models import AuditEventRecord
from app.database.repositories.base import BaseRepository

#: فیلدهای سطح‌اول رویداد که ستون جدا دارند
_COLUMNS = ("level", "category", "event", "symbol", "reason_code", "scan_id", "correlation_id", "module", "message")


def _utc_from_epoch(epoch: float) -> datetime:
    return datetime.fromtimestamp(float(epoch or 0.0), tz=timezone.utc).replace(tzinfo=None)


def _to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        # زمان محلی (ورودی رابط کاربری) → UTC
        value = value.astimezone()
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _row_to_event(row: AuditEventRecord) -> dict[str, Any]:
    created = row.created_at.replace(tzinfo=timezone.utc)
    event: dict[str, Any] = {
        "id": row.id,
        "ts": created.astimezone().isoformat(timespec="milliseconds"),
        "epoch": float(row.epoch or created.timestamp()),
        "level": row.level,
        "category": row.category,
        "event": row.event,
        "module": row.module,
        "message": row.message,
        "context": dict(row.context or {}),
        "audit": True,
    }
    for name in ("symbol", "reason_code", "scan_id", "correlation_id"):
        value = getattr(row, name)
        if value:
            event[name] = value
    if row.trade_id is not None:
        event["trade_id"] = row.trade_id
    return event


class AuditRepository(BaseRepository[AuditEventRecord]):
    """ذخیره و جست‌وجوی رویدادهای ممیزی."""

    model = AuditEventRecord

    def add_events(self, events: Iterable[dict[str, Any]]) -> int:
        """درج دسته‌ای رویدادها (همان دیکشنری‌های `record_to_event`)."""
        rows = []
        for event in events:
            trade_id = event.get("trade_id")
            try:
                trade_id = int(trade_id) if trade_id not in (None, "") else None
            except (TypeError, ValueError):
                trade_id = None
            epoch = float(event.get("epoch") or 0.0)
            values = {name: str(event.get(name) or "")[: 4000 if name == "message" else 120] for name in _COLUMNS}
            rows.append(AuditEventRecord(
                created_at=_utc_from_epoch(epoch) if epoch else datetime.now(timezone.utc).replace(tzinfo=None),
                epoch=epoch,
                trade_id=trade_id,
                context=dict(event.get("context") or {}),
                **values,
            ))
        if not rows:
            return 0
        with self._db.session_scope() as session:
            session.add_all(rows)
        return len(rows)

    def query(
        self,
        *,
        categories: Iterable[str] | None = None,
        events: Iterable[str] | None = None,
        levels: Iterable[str] | None = None,
        symbol: str | None = None,
        trade_id: int | None = None,
        reason_code: str | None = None,
        scan_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        search: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """جست‌وجوی رویدادها؛ خروجی قدیمی‌ترین اول (حداکثر `limit` تای آخر)."""
        stmt = select(AuditEventRecord)
        if categories:
            stmt = stmt.where(AuditEventRecord.category.in_(list(categories)))
        if events:
            stmt = stmt.where(AuditEventRecord.event.in_(list(events)))
        if levels:
            stmt = stmt.where(AuditEventRecord.level.in_([lv.upper() for lv in levels]))
        if symbol:
            stmt = stmt.where(AuditEventRecord.symbol.like(f"%{symbol.strip().upper()}%"))
        if trade_id is not None:
            stmt = stmt.where(AuditEventRecord.trade_id == int(trade_id))
        if reason_code:
            stmt = stmt.where(AuditEventRecord.reason_code == reason_code)
        if scan_id:
            stmt = stmt.where(AuditEventRecord.scan_id == scan_id)
        if start is not None:
            stmt = stmt.where(AuditEventRecord.created_at >= _to_utc_naive(start))
        if end is not None:
            stmt = stmt.where(AuditEventRecord.created_at <= _to_utc_naive(end))
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(or_(AuditEventRecord.message.like(pattern),
                                  AuditEventRecord.reason_code.like(pattern),
                                  AuditEventRecord.symbol.like(pattern)))
        stmt = stmt.order_by(AuditEventRecord.created_at.desc(), AuditEventRecord.id.desc()).limit(max(1, int(limit)))
        with self._db.session_scope() as session:
            rows = list(session.execute(stmt).scalars().all())
            return [_row_to_event(row) for row in reversed(rows)]

    def timeline(self, trade_id: int) -> list[dict[str, Any]]:
        """
        خط زمانی کامل یک معامله: رویدادهای همین `trade_id` + گام‌های پیش از
        ورود (سیگنال/نامزد/اعتبارسنجی) که `correlation_id` مشترک دارند.
        """
        with self._db.session_scope() as session:
            correlation_ids = [
                cid for cid in session.execute(
                    select(AuditEventRecord.correlation_id).where(
                        AuditEventRecord.trade_id == int(trade_id),
                        AuditEventRecord.correlation_id != "",
                    ).distinct()
                ).scalars().all() if cid
            ]
            condition = AuditEventRecord.trade_id == int(trade_id)
            if correlation_ids:
                condition = or_(condition, AuditEventRecord.correlation_id.in_(correlation_ids))
            rows = session.execute(
                select(AuditEventRecord).where(condition)
                .order_by(AuditEventRecord.created_at, AuditEventRecord.id)
            ).scalars().all()
            return [_row_to_event(row) for row in rows]

    def scan_summaries(self, *, limit: int = 100, engine: str | None = None) -> list[dict[str, Any]]:
        """آخرین خلاصه‌های پویش (جدیدترین آخر)."""
        events = self.query(events=["scan_summary"], limit=limit * 3 if engine else limit)
        if engine:
            events = [e for e in events if (e.get("context") or {}).get("engine") == engine]
        return events[-limit:]

    def recent_trade_ids(self, limit: int = 200) -> list[int]:
        """شناسهٔ معامله‌هایی که رویداد ورود دارند (جدیدترین اول)."""
        with self._db.session_scope() as session:
            rows = session.execute(
                select(AuditEventRecord.trade_id, func.max(AuditEventRecord.created_at).label("last"))
                .where(AuditEventRecord.trade_id.is_not(None))
                .group_by(AuditEventRecord.trade_id)
                .order_by(func.max(AuditEventRecord.created_at).desc())
                .limit(max(1, int(limit)))
            ).all()
            return [int(r[0]) for r in rows]

    def purge(self, *, older_than_days: int = 30, max_rows: int = 500_000) -> int:
        """حذف رویدادهای قدیمی‌تر از نگه‌داری و اضافه بر سقف تعداد ردیف."""
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=max(1, int(older_than_days)))
        removed = 0
        with self._db.session_scope() as session:
            result = session.execute(delete(AuditEventRecord).where(AuditEventRecord.created_at < cutoff))
            removed += int(result.rowcount or 0)
            total = int(session.execute(select(func.count(AuditEventRecord.id))).scalar() or 0)
            if total > max_rows:
                threshold = session.execute(
                    select(AuditEventRecord.id).order_by(AuditEventRecord.id.desc()).offset(max_rows).limit(1)
                ).scalar()
                if threshold is not None:
                    result = session.execute(delete(AuditEventRecord).where(AuditEventRecord.id <= threshold))
                    removed += int(result.rowcount or 0)
        return removed

    def clear(self) -> int:
        with self._db.session_scope() as session:
            result = session.execute(delete(AuditEventRecord))
            return int(result.rowcount or 0)


__all__ = ["AuditRepository"]
