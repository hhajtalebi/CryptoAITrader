"""
هشدار قیمت و هشدار سیگنال.

چرا لازم است: بدون هشدار، کاربر باید برنامه را باز نگه دارد و به صفحه
خیره شود. با هشدار، برنامه در پس‌زمینه کار می‌کند و خودش خبر می‌دهد.

دو نوع هشدار پشتیبانی می‌شود:

    • **قیمتی** — «هر وقت BTC/USDT از ۸۵۰۰۰ بالاتر رفت خبرم کن».
    • **سیگنالی** — «هر وقت سیگنالی با اطمینان بالای ۷۰٪ ساخته شد».

نکتهٔ طراحی: هشدار پس از فعال‌شدن **خاموش** می‌شود (`triggered=True`) نه
حذف. اگر هر تیک دوباره فعال شود، کاربر زیر بار اعلان دفن می‌شود؛ و اگر
حذف شود، تاریخچه‌اش از بین می‌رود. کاربر می‌تواند دستی دوباره مسلحش کند.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

#: جهت‌های مجاز برای هشدار قیمتی
ALERT_ABOVE = "above"
ALERT_BELOW = "below"
PRICE_DIRECTIONS = (ALERT_ABOVE, ALERT_BELOW)

#: انواع هشدار
KIND_PRICE = "price"
KIND_SIGNAL = "signal"


@dataclass(slots=True)
class Alert:
    """
    یک هشدار تعریف‌شده توسط کاربر.

    مثال:
        Alert(kind="price", symbol="BTC/USDT", direction="above", value=85000)
        Alert(kind="signal", min_confidence=70)
    """

    kind: str = KIND_PRICE
    symbol: str = ""
    direction: str = ALERT_ABOVE
    value: float = 0.0
    min_confidence: int = 0
    enabled: bool = True
    triggered: bool = False
    note: str = ""
    triggered_at: datetime | None = None
    id: int = 0

    def is_valid(self) -> tuple[bool, str]:
        """
        بررسی سلامت تعریف هشدار.

        هشدار نامعتبر بی‌سروصدا نادیده گرفته نمی‌شود؛ کاربر باید بداند
        چرا هشدارش هرگز فعال نمی‌شود.
        """
        if self.kind not in (KIND_PRICE, KIND_SIGNAL):
            return False, "نوع هشدار نامعتبر است"
        if self.kind == KIND_PRICE:
            if not self.symbol:
                return False, "نماد را انتخاب کنید"
            if self.direction not in PRICE_DIRECTIONS:
                return False, "جهت هشدار نامعتبر است"
            if self.value <= 0:
                return False, "قیمت هشدار باید بزرگ‌تر از صفر باشد"
        else:
            if not 0 < self.min_confidence <= 100:
                return False, "حداقل اطمینان باید بین ۱ تا ۱۰۰ باشد"
        return True, ""

    def matches_price(self, price: float) -> bool:
        """آیا این قیمت شرط هشدار را برآورده می‌کند؟"""
        if self.kind != KIND_PRICE or not self.enabled or self.triggered:
            return False
        if price <= 0:
            return False
        if self.direction == ALERT_ABOVE:
            return price >= self.value
        return price <= self.value

    def matches_signal(self, signal: dict[str, Any]) -> bool:
        """آیا این سیگنال شرط هشدار را برآورده می‌کند؟"""
        if self.kind != KIND_SIGNAL or not self.enabled or self.triggered:
            return False
        # سیگنال «انتظار» توصیهٔ معاملاتی نیست و نباید کاربر را بیدار کند.
        if str(signal.get("direction", "")).upper() == "WAIT":
            return False
        if self.symbol and str(signal.get("symbol", "")) != self.symbol:
            return False
        try:
            confidence = int(signal.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            return False
        return confidence >= self.min_confidence

    def describe(self) -> str:
        """توضیح کوتاه و خوانا برای نمایش در فهرست."""
        if self.kind == KIND_PRICE:
            arrow = "≥" if self.direction == ALERT_ABOVE else "≤"
            return f"{self.symbol} {arrow} {self.value:,.6g}"
        scope = self.symbol or "همهٔ نمادها"
        return f"{scope} — اطمینان ≥ {self.min_confidence}%"

    def as_dict(self) -> dict[str, Any]:
        """شکل قابل ذخیره در تنظیمات."""
        return {
            "id": self.id,
            "kind": self.kind,
            "symbol": self.symbol,
            "direction": self.direction,
            "value": self.value,
            "min_confidence": self.min_confidence,
            "enabled": self.enabled,
            "triggered": self.triggered,
            "note": self.note,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else "",
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Alert:
        """بازسازی از دادهٔ ذخیره‌شده، با تحمل فیلدهای گمشده."""
        raw_time = str(payload.get("triggered_at") or "")
        moment: datetime | None = None
        if raw_time:
            try:
                moment = datetime.fromisoformat(raw_time)
            except ValueError:
                moment = None
        return cls(
            id=int(payload.get("id", 0) or 0),
            kind=str(payload.get("kind", KIND_PRICE)),
            symbol=str(payload.get("symbol", "") or ""),
            direction=str(payload.get("direction", ALERT_ABOVE)),
            value=float(payload.get("value", 0.0) or 0.0),
            min_confidence=int(payload.get("min_confidence", 0) or 0),
            enabled=bool(payload.get("enabled", True)),
            triggered=bool(payload.get("triggered", False)),
            note=str(payload.get("note", "") or ""),
            triggered_at=moment,
        )


@dataclass(slots=True)
class AlertHit:
    """یک هشدار فعال‌شده، همراه با دلیلش."""

    alert: Alert
    message: str
    price: float = 0.0


@dataclass
class AlertBook:
    """
    مجموعهٔ هشدارهای کاربر.

    مثال:
        book = AlertBook.from_list(settings.get("alerts.items", []))
        hits = book.check_prices({"BTC/USDT": 86000})
        settings.set("alerts.items", book.as_list())
    """

    alerts: list[Alert] = field(default_factory=list)

    @classmethod
    def from_list(cls, payload: Any) -> AlertBook:
        """بازسازی از تنظیمات؛ دادهٔ خراب نادیده گرفته می‌شود."""
        items: list[Alert] = []
        if isinstance(payload, list):
            for entry in payload:
                if isinstance(entry, dict):
                    try:
                        items.append(Alert.from_dict(entry))
                    except (TypeError, ValueError):
                        logger.debug("Skipping malformed alert: %r", entry)
        return cls(alerts=items)

    def as_list(self) -> list[dict[str, Any]]:
        """شکل قابل ذخیره."""
        return [alert.as_dict() for alert in self.alerts]

    def add(self, alert: Alert) -> tuple[bool, str]:
        """افزودن هشدار پس از اعتبارسنجی."""
        ok, reason = alert.is_valid()
        if not ok:
            return False, reason
        alert.id = max((item.id for item in self.alerts), default=0) + 1
        self.alerts.append(alert)
        return True, ""

    def remove(self, alert_id: int) -> bool:
        """حذف یک هشدار."""
        before = len(self.alerts)
        self.alerts = [item for item in self.alerts if item.id != int(alert_id)]
        return len(self.alerts) != before

    def rearm(self, alert_id: int) -> bool:
        """مسلح‌کردن دوبارهٔ هشداری که قبلاً فعال شده."""
        for item in self.alerts:
            if item.id == int(alert_id):
                item.triggered = False
                item.triggered_at = None
                return True
        return False

    def active_symbols(self) -> list[str]:
        """
        نمادهایی که هشدار قیمتیِ فعال دارند.

        فقط برای همین‌ها قیمت گرفته می‌شود، نه برای کل بازار.
        """
        return sorted(
            {
                item.symbol
                for item in self.alerts
                if item.kind == KIND_PRICE
                and item.enabled
                and not item.triggered
                and item.symbol
            }
        )

    def check_prices(self, prices: dict[str, float]) -> list[AlertHit]:
        """بررسی هشدارهای قیمتی در برابر قیمت‌های تازه."""
        hits: list[AlertHit] = []
        moment = datetime.now(UTC)
        for item in self.alerts:
            price = prices.get(item.symbol)
            if price is None:
                continue
            if item.matches_price(float(price)):
                item.triggered = True
                item.triggered_at = moment
                hits.append(
                    AlertHit(
                        alert=item,
                        message=f"{item.symbol} {float(price):,.6g}",
                        price=float(price),
                    )
                )
        if hits:
            logger.info("Price alerts fired: %d", len(hits))
        return hits

    def check_signal(self, signal: dict[str, Any]) -> list[AlertHit]:
        """بررسی هشدارهای سیگنالی در برابر یک سیگنال تازه."""
        hits: list[AlertHit] = []
        moment = datetime.now(UTC)
        for item in self.alerts:
            if item.matches_signal(signal):
                item.triggered = True
                item.triggered_at = moment
                hits.append(
                    AlertHit(
                        alert=item,
                        message=(
                            f"{signal.get('symbol', '')} "
                            f"{str(signal.get('direction', '')).upper()} "
                            f"{int(signal.get('confidence', 0) or 0)}%"
                        ),
                    )
                )
        if hits:
            logger.info("Signal alerts fired: %d", len(hits))
        return hits
