"""
مخزن نمادها و فهرست پیگیری (Watchlist).

این مخزن نمادهای دریافتی از صرافی را همگام‌سازی می‌کند و امکان جستجو،
علاقه‌مندی و مدیریت فهرست پیگیری را فراهم می‌آورد.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.constants import DEFAULT_WATCHLIST
from app.core.models import SymbolInfo
from app.database.models import SymbolRecord, WatchlistItem
from app.database.repositories.base import BaseRepository
from app.logging import get_logger

logger = get_logger(__name__)

#: نام فهرست دیده‌بانی پیش‌فرض.
#:
#: تعریف اصلی در `app.core.constants` است تا لایهٔ رابط کاربری برای
#: خواندن یک رشته مجبور نباشد کل لایهٔ داده را وارد کند. این نام
#: به‌عنوان هم‌نام باقی می‌ماند چون کد موجود از همین‌جا واردش می‌کند.
DEFAULT_LIST = DEFAULT_WATCHLIST


class SymbolRepository(BaseRepository[SymbolRecord]):
    """دسترسی به جداول symbols و watchlists."""

    model = SymbolRecord

    def sync_symbols(self, exchange: str, symbols: list[SymbolInfo]) -> tuple[int, int]:
        """
        همگام‌سازی فهرست نمادها با داده تازه صرافی.

        بازگشتی: (تعداد افزوده‌شده، تعداد به‌روزشده)

        نکته: نمادهای حذف‌شده از صرافی، پاک نمی‌شوند بلکه is_active=False
        می‌گیرند تا تاریخچه سیگنال‌های مرتبط از بین نرود.
        """
        added = updated = 0
        incoming = {s.symbol for s in symbols}
        with self._db.session_scope() as session:
            existing_records = {
                r.symbol: r
                for r in session.execute(
                    select(SymbolRecord).where(SymbolRecord.exchange == exchange)
                ).scalars().all()
            }
            for info in symbols:
                record = existing_records.get(info.symbol)
                if record is None:
                    session.add(
                        SymbolRecord(
                            exchange=exchange,
                            symbol=info.symbol,
                            exchange_symbol=info.exchange_symbol,
                            base_asset=info.base_asset,
                            quote_asset=info.quote_asset,
                            price_precision=info.price_precision,
                            quantity_precision=info.quantity_precision,
                            min_order_amount=info.min_order_amount,
                            is_active=True,
                        )
                    )
                    added += 1
                else:
                    record.exchange_symbol = info.exchange_symbol
                    record.base_asset = info.base_asset
                    record.quote_asset = info.quote_asset
                    record.price_precision = info.price_precision
                    record.quantity_precision = info.quantity_precision
                    record.min_order_amount = info.min_order_amount
                    record.is_active = True
                    updated += 1
            # غیرفعال کردن نمادهایی که دیگر در صرافی موجود نیستند
            for symbol_name, record in existing_records.items():
                if symbol_name not in incoming:
                    record.is_active = False
        logger.info("Symbols synced for %s: %d added, %d updated", exchange, added, updated)
        return added, updated

    def search(
        self,
        query: str = "",
        *,
        exchange: str | None = None,
        quote_asset: str | None = None,
        favorites_only: bool = False,
        active_only: bool = True,
        limit: int = 200,
    ) -> list[SymbolRecord]:
        """
        جستجوی نمادها با فیلترهای ترکیبی.

        از پارامترهای امن SQLAlchemy استفاده می‌شود؛ رشته کاربر هرگز به
        Query خام الحاق نمی‌گردد (پیشگیری از SQL Injection).
        """
        with self._db.session_scope() as session:
            stmt = select(SymbolRecord)
            if exchange:
                stmt = stmt.where(SymbolRecord.exchange == exchange)
            if active_only:
                stmt = stmt.where(SymbolRecord.is_active.is_(True))
            if favorites_only:
                stmt = stmt.where(SymbolRecord.is_favorite.is_(True))
            if quote_asset:
                stmt = stmt.where(SymbolRecord.quote_asset == quote_asset.upper())
            if query:
                pattern = f"%{query.strip().upper()}%"
                stmt = stmt.where(SymbolRecord.symbol.like(pattern))
            stmt = stmt.order_by(SymbolRecord.is_favorite.desc(), SymbolRecord.symbol).limit(limit)
            return list(session.execute(stmt).scalars().all())

    def get_by_symbol(self, symbol: str, exchange: str) -> SymbolRecord | None:
        """یافتن یک نماد مشخص در یک صرافی."""
        with self._db.session_scope() as session:
            return session.execute(
                select(SymbolRecord).where(
                    SymbolRecord.symbol == symbol, SymbolRecord.exchange == exchange
                )
            ).scalar_one_or_none()

    def set_favorite(self, symbol: str, exchange: str, favorite: bool) -> bool:
        """تغییر وضعیت علاقه‌مندی یک نماد."""
        with self._db.session_scope() as session:
            record = session.execute(
                select(SymbolRecord).where(
                    SymbolRecord.symbol == symbol, SymbolRecord.exchange == exchange
                )
            ).scalar_one_or_none()
            if record is None:
                return False
            record.is_favorite = favorite
            return True

    def count_active(self, exchange: str) -> int:
        """تعداد نمادهای فعال یک صرافی."""
        with self._db.session_scope() as session:
            return int(
                session.execute(
                    select(func.count())
                    .select_from(SymbolRecord)
                    .where(SymbolRecord.exchange == exchange, SymbolRecord.is_active.is_(True))
                ).scalar()
                or 0
            )

    # ------------------------- فهرست پیگیری -------------------------
    def get_watchlist(self, list_name: str = "default") -> list[str]:
        """فهرست نام نمادهای موجود در یک Watchlist، به ترتیب چیدمان کاربر."""
        with self._db.session_scope() as session:
            rows = session.execute(
                select(SymbolRecord.symbol)
                .join(WatchlistItem, WatchlistItem.symbol_id == SymbolRecord.id)
                .where(WatchlistItem.list_name == list_name)
                .order_by(WatchlistItem.position, SymbolRecord.symbol)
            ).scalars().all()
            return list(rows)

    def add_to_watchlist(
        self, symbol: str, exchange: str | None = None, list_name: str = "default"
    ) -> bool:
        """
        افزودن یک نماد به فهرست پیگیری.

        افزودن تکراری خطا نیست و False برمی‌گرداند.

        v2.5.1 — علت «واچ‌لیست همیشه خالی»: جدول `symbols` در برنامه هیچ‌وقت
        پر نمی‌شد (`sync_symbols` فقط در آزمون صدا زده می‌شد)، پس این متد
        رکورد نماد را پیدا نمی‌کرد و بی‌صدا False برمی‌گرداند. حالا اگر
        رکورد نباشد همان‌جا از روی نام استاندارد (BTC/USDT) ساخته می‌شود.
        """
        symbol = _normalize_symbol(symbol)
        if not symbol:
            return False
        with self._db.session_scope() as session:
            record = _find_record(session, symbol, exchange, create=True)
            if record is None:
                return False
            already = session.execute(
                select(WatchlistItem).where(
                    WatchlistItem.list_name == list_name, WatchlistItem.symbol_id == record.id
                )
            ).scalar_one_or_none()
            if already is not None:
                return False
            max_position = int(
                session.execute(
                    select(func.coalesce(func.max(WatchlistItem.position), 0)).where(
                        WatchlistItem.list_name == list_name
                    )
                ).scalar()
                or 0
            )
            session.add(
                WatchlistItem(list_name=list_name, symbol_id=record.id, position=max_position + 1)
            )
            return True

    def is_in_watchlist(self, symbol: str, list_name: str = "default") -> bool:
        """آیا نماد (در هر صرافی) در این فهرست هست؟ (v2.5.1)"""
        return _normalize_symbol(symbol) in set(self.get_watchlist(list_name))

    def remove_from_watchlist(
        self, symbol: str, exchange: str | None = None, list_name: str = "default"
    ) -> bool:
        """
        حذف یک نماد از فهرست پیگیری.

        بدون `exchange` (یا اگر رکورد آن صرافی نباشد) هر رکوردی با همین نام
        که در فهرست است برداشته می‌شود — ستارهٔ جدول نباید به‌خاطر تفاوت نام
        صرافی «گیر» کند.
        """
        symbol = _normalize_symbol(symbol)
        removed = False
        with self._db.session_scope() as session:
            stmt = (
                select(WatchlistItem)
                .join(SymbolRecord, WatchlistItem.symbol_id == SymbolRecord.id)
                .where(WatchlistItem.list_name == list_name, SymbolRecord.symbol == symbol)
            )
            items = session.execute(stmt).scalars().all()
            if exchange:
                exact = [
                    i for i in items
                    if session.get(SymbolRecord, i.symbol_id).exchange == exchange
                ]
                items = exact or items
            for item in items:
                session.delete(item)
                removed = True
        return removed

    # ------------------- چند فهرست دیده‌بانی (مورد ۵.۳) -------------------
    #: هم‌نام ماژولی، برای کدی که از راه نمونهٔ مخزن به آن می‌رسد
    DEFAULT_LIST = DEFAULT_LIST

    def watchlist_names(self) -> list[str]:
        """
        نام همهٔ فهرست‌های ساخته‌شده، به ترتیب الفبا با پیش‌فرض در صدر.

        فهرست پیش‌فرض همیشه برمی‌گردد حتی اگر خالی باشد، وگرنه کاربر
        تازه‌وارد هیچ فهرستی برای افزودن نماد نمی‌بیند.
        """
        with self._db.session_scope() as session:
            rows = session.execute(
                select(WatchlistItem.list_name).distinct()
            ).scalars().all()
        names = {str(name) for name in rows if str(name).strip()}
        names.add(self.DEFAULT_LIST)
        others = sorted(names - {self.DEFAULT_LIST})
        return [self.DEFAULT_LIST, *others]

    def watchlist_counts(self) -> dict[str, int]:
        """تعداد نماد هر فهرست، برای نمایش کنار نامش."""
        with self._db.session_scope() as session:
            rows = session.execute(
                select(WatchlistItem.list_name, func.count())
                .group_by(WatchlistItem.list_name)
            ).all()
        counts = {str(name): int(count) for name, count in rows}
        counts.setdefault(self.DEFAULT_LIST, 0)
        return counts

    def create_watchlist(self, list_name: str) -> bool:
        """
        ساخت یک فهرست تازه.

        فهرست بدون عضو ردیفی در پایگاه داده ندارد، پس «ساخت» در عمل یعنی
        بررسی نبودِ نام تکراری؛ نام تازه با افزودن اولین نماد ماندگار
        می‌شود. `False` یعنی نام نامعتبر یا تکراری است.
        """
        name = str(list_name or "").strip()
        if not name or name in self.watchlist_names():
            return False
        return True

    def rename_watchlist(self, old_name: str, new_name: str) -> bool:
        """تغییر نام یک فهرست به همراه همهٔ اعضایش."""
        source = str(old_name or "").strip()
        target = str(new_name or "").strip()
        if not source or not target or source == target:
            return False
        if source == DEFAULT_LIST:
            # ستارهٔ صفحهٔ بازارها به همین نام گره خورده است؛ اگر نامش
            # عوض شود، ستاره‌ها به فهرستی اشاره می‌کنند که دیگر نیست.
            return False
        if target in self.watchlist_names():
            # ادغام دو فهرست کار این متد نیست؛ سکوت‌کردن یعنی از دست
            # رفتن بی‌صدای داده.
            return False
        with self._db.session_scope() as session:
            items = session.execute(
                select(WatchlistItem).where(WatchlistItem.list_name == source)
            ).scalars().all()
            if not items:
                return False
            for item in items:
                item.list_name = target
        logger.info("Watchlist renamed: %s -> %s", source, target)
        return True

    def delete_watchlist(self, list_name: str) -> int:
        """
        حذف یک فهرست و همهٔ اعضایش؛ تعداد حذف‌شده برمی‌گردد.

        فهرست پیش‌فرض حذف نمی‌شود — فقط خالی می‌شود — چون کاربر باید
        همیشه دست‌کم یک جا برای ستاره‌زدن داشته باشد.
        """
        name = str(list_name or "").strip()
        if not name:
            return 0
        with self._db.session_scope() as session:
            items = session.execute(
                select(WatchlistItem).where(WatchlistItem.list_name == name)
            ).scalars().all()
            for item in items:
                session.delete(item)
            removed = len(items)
        if removed:
            logger.info("Watchlist '%s' cleared (%s items)", name, removed)
        return removed

    def watchlist_details(self, list_name: str = DEFAULT_LIST) -> list[dict]:
        """
        اعضای یک فهرست با ترتیب و یادداشتشان.

        برخلاف `get_watchlist` که فقط نام نماد می‌دهد، این متد داده‌ای
        را برمی‌گرداند که صفحهٔ مدیریت برای جابه‌جایی و ویرایش لازم دارد.
        """
        with self._db.session_scope() as session:
            rows = session.execute(
                select(
                    SymbolRecord.symbol,
                    WatchlistItem.position,
                    WatchlistItem.note,
                    SymbolRecord.exchange,
                )
                .join(WatchlistItem, WatchlistItem.symbol_id == SymbolRecord.id)
                .where(WatchlistItem.list_name == list_name)
                .order_by(WatchlistItem.position, SymbolRecord.symbol)
            ).all()
        return [
            {
                "symbol": str(symbol),
                "position": int(position or 0),
                "note": str(note or ""),
                "exchange": str(exchange or ""),
            }
            for symbol, position, note, exchange in rows
        ]

    def reorder_watchlist(self, list_name: str, symbols: list[str]) -> bool:
        """
        بازچینش دستی اعضای یک فهرست بر پایهٔ ترتیب داده‌شده.

        نمادهایی که در `symbols` نیامده‌اند ترتیب فعلی‌شان را پس از
        بقیه حفظ می‌کنند؛ حذف بی‌صدا اتفاق نمی‌افتد.
        """
        wanted = [str(item) for item in symbols if str(item).strip()]
        if not wanted:
            return False
        with self._db.session_scope() as session:
            rows = session.execute(
                select(WatchlistItem, SymbolRecord.symbol)
                .join(SymbolRecord, WatchlistItem.symbol_id == SymbolRecord.id)
                .where(WatchlistItem.list_name == list_name)
            ).all()
            if not rows:
                return False
            by_symbol = {str(symbol): item for item, symbol in rows}
            position = 0
            for symbol in wanted:
                item = by_symbol.pop(symbol, None)
                if item is None:
                    continue
                position += 1
                item.position = position
            # باقی‌مانده‌ها پس از فهرست تازه، با ترتیب پیشین
            for item in sorted(by_symbol.values(), key=lambda row: row.position):
                position += 1
                item.position = position
        return True

    def move_in_watchlist(self, list_name: str, symbol: str, delta: int) -> bool:
        """
        جابه‌جایی یک نماد به اندازهٔ `delta` جایگاه (منفی یعنی بالاتر).

        برای دکمه‌های «بالا/پایین» که از کشیدن‌ورهاکردن قابل‌اعتمادترند.
        """
        order = [row["symbol"] for row in self.watchlist_details(list_name)]
        if symbol not in order or not delta:
            return False
        index = order.index(symbol)
        target = max(0, min(len(order) - 1, index + int(delta)))
        if target == index:
            return False
        order.insert(target, order.pop(index))
        return self.reorder_watchlist(list_name, order)

    def set_watchlist_note(
        self, symbol: str, exchange: str, note: str, list_name: str = DEFAULT_LIST
    ) -> bool:
        """ثبت یادداشت کوتاه روی یک عضو فهرست («منتظر شکست ۶۵ هزار»)."""
        with self._db.session_scope() as session:
            record = session.execute(
                select(SymbolRecord).where(
                    SymbolRecord.symbol == symbol, SymbolRecord.exchange == exchange
                )
            ).scalar_one_or_none()
            if record is None:
                return False
            item = session.execute(
                select(WatchlistItem).where(
                    WatchlistItem.list_name == list_name,
                    WatchlistItem.symbol_id == record.id,
                )
            ).scalar_one_or_none()
            if item is None:
                return False
            item.note = str(note or "")[:500]
            return True

    def find_symbol_lists(self, symbol: str, exchange: str) -> list[str]:
        """نام فهرست‌هایی که این نماد در آن‌هاست — برای رنگ‌کردن ستاره."""
        with self._db.session_scope() as session:
            record = session.execute(
                select(SymbolRecord).where(
                    SymbolRecord.symbol == symbol, SymbolRecord.exchange == exchange
                )
            ).scalar_one_or_none()
            if record is None:
                return []
            rows = session.execute(
                select(WatchlistItem.list_name).where(
                    WatchlistItem.symbol_id == record.id
                )
            ).scalars().all()
        return sorted(str(name) for name in rows)


def _normalize_symbol(symbol: str) -> str:
    """«btc_usdt» / «BTCUSDT» نه؛ فقط شکل استاندارد «BTC/USDT» با حروف بزرگ."""
    text = str(symbol or "").strip().upper()
    if "/" not in text and "_" in text:
        text = text.replace("_", "/")
    return text


def _find_record(session, symbol: str, exchange: str | None, *, create: bool = False):
    """
    یافتن رکورد نماد؛ اول همان صرافی، بعد هر صرافی؛ در صورت نیاز ساختن آن.
    """
    if exchange:
        record = session.execute(
            select(SymbolRecord).where(
                SymbolRecord.symbol == symbol, SymbolRecord.exchange == exchange
            )
        ).scalar_one_or_none()
        if record is not None:
            return record
    else:
        record = session.execute(
            select(SymbolRecord).where(SymbolRecord.symbol == symbol).order_by(SymbolRecord.id)
        ).scalars().first()
        if record is not None:
            return record
    if not create:
        return None
    base, _sep, quote = symbol.partition("/")
    record = SymbolRecord(
        exchange=str(exchange or "default"),
        symbol=symbol,
        exchange_symbol=symbol.replace("/", "_").lower(),
        base_asset=base,
        quote_asset=quote,
        is_active=True,
    )
    session.add(record)
    session.flush()
    return record

