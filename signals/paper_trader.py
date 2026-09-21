"""
دفتر معاملهٔ کاغذی (تمرینی).

کاربر خواست کنار هر سیگنال دکمه‌ای برای «اقدام» باشد. این پرونده همان
اقدام را انجام می‌دهد، ولی **بدون پول واقعی**: موقعیت در پایگاه دادهٔ
محلی ثبت می‌شود تا کاربر بتواند نتیجهٔ تصمیم‌هایش را دنبال کند.

چرا واقعی نیست: ثبت سفارش زنده یعنی دسترسی نوشتنی به حساب صرافی. تا
وقتی مسیر سفارش زیر آزمون کامل نرفته و کاربر صریحاً فعالش نکرده، دکمه‌ای
که پول جابه‌جا کند خطرناک است. ساختار زیر طوری است که با پیاده‌سازی
`OrderExecutor` و روشن‌کردن یک تنظیم، همین جریان به سفارش واقعی وصل شود.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from app.core.timeutil import now_utc
from app.logging import get_logger

logger = get_logger(__name__)

#: کلید تنظیمی که موقعیت‌های کاغذی زیر آن ذخیره می‌شوند
PAPER_POSITIONS_KEY = "trading.paper_positions"

#: بیشینه تعداد موقعیتی که نگه داشته می‌شود
MAX_POSITIONS = 200


@dataclass
class PaperPosition:
    """یک موقعیت معاملاتی تمرینی."""

    symbol: str
    direction: str
    entry: float
    stop_loss: float | None = None
    take_profits: list[float] = field(default_factory=list)
    leverage: int = 1
    size: float = 0.0
    confidence: int = 0
    opened_at: datetime = field(default_factory=now_utc)
    status: str = "OPEN"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """تبدیل به دیکشنری قابل ذخیره."""
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "entry": self.entry,
            "stop_loss": self.stop_loss,
            "take_profits": list(self.take_profits),
            "leverage": self.leverage,
            "size": self.size,
            "confidence": self.confidence,
            "opened_at": self.opened_at.isoformat(),
            "status": self.status,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaperPosition:
        """بازسازی از دادهٔ ذخیره‌شده."""
        opened = data.get("opened_at")
        try:
            opened_at = datetime.fromisoformat(opened) if opened else now_utc()
        except (TypeError, ValueError):
            opened_at = now_utc()
        return cls(
            symbol=str(data.get("symbol", "")),
            direction=str(data.get("direction", "WAIT")),
            entry=float(data.get("entry") or 0.0),
            stop_loss=data.get("stop_loss"),
            take_profits=list(data.get("take_profits") or []),
            leverage=int(data.get("leverage") or 1),
            size=float(data.get("size") or 0.0),
            confidence=int(data.get("confidence") or 0),
            opened_at=opened_at,
            status=str(data.get("status", "OPEN")),
            note=str(data.get("note", "")),
        )


class OrderExecutor(Protocol):
    """
    قرارداد ثبت سفارش واقعی.

    هنوز پیاده‌سازی نشده؛ فقط برای این تعریف شده که وقتی معاملهٔ واقعی
    اضافه شد، `PaperTrader` بدون بازنویسی به آن وصل شود.
    """

    async def place_order(self, position: PaperPosition) -> dict[str, Any]:
        """ثبت سفارش روی صرافی."""
        ...


class PaperTrader:
    """
    مدیریت موقعیت‌های تمرینی.

    مثال:
        trader = PaperTrader(settings_service)
        position = trader.open_from_signal(signal_dict, balance=1000, risk_percent=1)
        print(trader.open_positions())
    """

    def __init__(self, settings: Any, executor: OrderExecutor | None = None) -> None:
        self._settings = settings
        self._executor = executor

    @property
    def live_trading_enabled(self) -> bool:
        """آیا ثبت سفارش واقعی فعال است؟ (فعلاً همیشه خیر)"""
        return self._executor is not None

    # ------------------------------------------------------------------
    # خواندن و نوشتن
    # ------------------------------------------------------------------
    def _load(self) -> list[dict[str, Any]]:
        """خواندن موقعیت‌های ذخیره‌شده."""
        raw = self._settings.get(PAPER_POSITIONS_KEY, "[]")
        if isinstance(raw, list):
            return raw
        try:
            data = json.loads(str(raw or "[]"))
            return data if isinstance(data, list) else []
        except (TypeError, ValueError):
            logger.warning("Stored paper positions were unreadable; starting fresh")
            return []

    def _save(self, positions: list[dict[str, Any]]) -> None:
        """ذخیرهٔ موقعیت‌ها."""
        trimmed = positions[-MAX_POSITIONS:]
        self._settings.set(PAPER_POSITIONS_KEY, json.dumps(trimmed, ensure_ascii=False))

    # ------------------------------------------------------------------
    # عملیات
    # ------------------------------------------------------------------
    def open_from_signal(
        self,
        signal: dict[str, Any],
        *,
        balance: float = 0.0,
        risk_percent: float = 1.0,
    ) -> PaperPosition | None:
        """
        باز کردن موقعیت تمرینی از روی یک سیگنال.

        روی سیگنال «انتظار» چیزی باز نمی‌شود، چون اقدامی وجود ندارد.
        """
        direction = str(signal.get("direction", "WAIT")).upper()
        if direction not in {"LONG", "SHORT"}:
            logger.info("No position opened: signal direction is %s", direction)
            return None

        entry = self._pick_entry(signal)
        if entry is None or entry <= 0:
            logger.warning("No position opened: signal has no usable entry price")
            return None

        stop_loss = signal.get("stop_loss")
        size = self._position_size(entry, stop_loss, balance, risk_percent)

        take_profits = signal.get("take_profits") or signal.get("take_profit") or []
        if isinstance(take_profits, (int, float)):
            take_profits = [take_profits]

        position = PaperPosition(
            symbol=str(signal.get("symbol", "")),
            direction=direction,
            entry=float(entry),
            stop_loss=float(stop_loss) if stop_loss else None,
            take_profits=[float(t) for t in take_profits if t],
            leverage=int(signal.get("leverage") or 1),
            size=size,
            confidence=int(signal.get("confidence") or 0),
            note=str(signal.get("reason", ""))[:300],
        )

        positions = self._load()
        positions.append(position.to_dict())
        self._save(positions)
        logger.info(
            "Paper position opened: %s %s @ %.8g (size %.8g)",
            position.direction, position.symbol, position.entry, position.size,
        )
        return position

    def open_positions(self) -> list[PaperPosition]:
        """موقعیت‌های باز."""
        return [
            PaperPosition.from_dict(item)
            for item in self._load()
            if str(item.get("status", "OPEN")).upper() == "OPEN"
        ]

    def all_positions(self) -> list[PaperPosition]:
        """همهٔ موقعیت‌ها، شامل بسته‌شده‌ها."""
        return [PaperPosition.from_dict(item) for item in self._load()]

    def close_position(self, index: int, *, note: str = "") -> bool:
        """بستن یک موقعیت بر اساس نمایه."""
        positions = self._load()
        if not 0 <= index < len(positions):
            return False
        positions[index]["status"] = "CLOSED"
        positions[index]["note"] = note or positions[index].get("note", "")
        self._save(positions)
        return True

    def clear(self) -> None:
        """پاک کردن دفتر تمرینی."""
        self._save([])

    # ------------------------------------------------------------------
    # کمکی
    # ------------------------------------------------------------------
    @staticmethod
    def _pick_entry(signal: dict[str, Any]) -> float | None:
        """
        انتخاب قیمت ورود از میان قالب‌های ممکن.

        سیگنال ممکن است بازهٔ ورود بدهد یا یک عدد؛ وسط بازه منطقی‌ترین
        نقطهٔ ورود است.
        """
        entry_min = signal.get("entry_min")
        entry_max = signal.get("entry_max")
        if entry_min is None and entry_max is None:
            entry = signal.get("entry")
            if isinstance(entry, dict):
                entry_min, entry_max = entry.get("min"), entry.get("max")
            elif entry is not None:
                entry_min = entry_max = entry
        values = [float(v) for v in (entry_min, entry_max) if v not in (None, "")]
        if not values:
            return None
        return sum(values) / len(values)

    @staticmethod
    def _position_size(
        entry: float, stop_loss: Any, balance: float, risk_percent: float
    ) -> float:
        """
        اندازهٔ موقعیت بر پایهٔ ریسک مجاز.

        همان فرمول موتور ریسک: مبلغ در خطر تقسیم بر فاصلهٔ ورود تا حد ضرر.
        بدون حد ضرر، اندازه محاسبه نمی‌شود چون ریسک تعریف‌شده‌ای ندارد.
        """
        if not balance or not stop_loss:
            return 0.0
        try:
            distance = abs(float(entry) - float(stop_loss))
        except (TypeError, ValueError):
            return 0.0
        if distance <= 0:
            return 0.0
        return (float(balance) * float(risk_percent) / 100.0) / distance
