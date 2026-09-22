"""
رویدادهای مهم بازار (Event Impact) — خواسته‌های ۳۱ و ۳۲، حالت دستی.

چرا این فایل وجود دارد؟
    تصمیم کاربر (۲۰۲۶-۰۹-۲۲): رویدادها (Fed/CPI/FOMC/…) **دستی** وارد
    می‌شوند و هیچ منبع خارجی اضافه نمی‌شود. پس این ماژول:
    • تقویم رویداد را از تنظیمات کاربر می‌خواند (کلید prediction.events)
    • رویداد نزدیکِ «پرتأثیر» را در پیش‌بینی اعمال می‌کند: کاهش
      اطمینان و برچسب صریح — نه تغییر عدد جهت به دلیلی که نداریم.

چرا رویداد جهت را تغییر نمی‌دهد؟ چون اثر تاریخیِ رویدادها را در این
حالت داده‌ای برای سنجش نداریم؛ صادقانه‌ترین کار کاهش «اعتبار» است تا
کاربر بداند پیش‌بینی در پنجرهٔ رویداد ضعیف‌تر است.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: کلید تنظیمات تقویم رویداد — لیست JSON از dictها.
SETTINGS_KEY = "prediction.events"

#: تأثیرهای مجاز.
IMPACT_LEVELS = ("high", "medium", "low")

#: پنجرهٔ تأثیر رویداد پرتأثیر (دقیقه قبل تا بعد).
HIGH_IMPACT_WINDOW_MINUTES = 120

#: حداکثر رویداد ذخیره‌شده — جلوگیری از بی‌نهایت شدن تنظیمات.
MAX_EVENTS = 100


@dataclass(slots=True)
class MarketEvent:
    """یک رویداد تقویمی وارد‌شده توسط کاربر."""

    name: str
    at: datetime
    impact: str = "medium"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری برای تنظیمات و گزارش."""
        return {
            "name": self.name,
            "at": self.at.astimezone(timezone.utc).isoformat(),
            "impact": self.impact,
            "note": self.note,
        }


def parse_events(raw: Any) -> list[MarketEvent]:
    """
    تبدیل JSON تنظیمات به رویداد — با اعتبارسنجی سخت.

    ردیف خراب کل را نمی‌شکند؛ فقط همان ردیف با لاگ حذف می‌شود.
    """
    events: list[MarketEvent] = []
    if not raw:
        return events
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except ValueError:
            logger.warning("Invalid JSON in %s; ignoring", SETTINGS_KEY)
            return events
    if not isinstance(raw, list):
        return events

    for item in raw[:MAX_EVENTS]:
        try:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            moment = datetime.fromisoformat(str(item["at"]))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            impact = str(item.get("impact", "medium")).lower()
            if not name or impact not in IMPACT_LEVELS:
                continue
            events.append(MarketEvent(name=name, at=moment, impact=impact,
                                      note=str(item.get("note", ""))))
        except (KeyError, ValueError, TypeError):
            logger.debug("Skipping malformed event entry: %r", item)
    events.sort(key=lambda event: event.at)
    return events


def load_events(settings: Any) -> list[MarketEvent]:
    """خواندن تقویم از سرویس تنظیمات (کلید با پیش‌فرض خالی)."""
    getter = getattr(settings, "get", None)
    if getter is None:
        return []
    try:
        return parse_events(getter(SETTINGS_KEY, "[]"))
    except Exception:  # noqa: BLE001 - تنظیمات خراب نباید موتور را بکشد
        logger.warning("Could not read %s", SETTINGS_KEY, exc_info=True)
        return []


@dataclass(slots=True)
class EventPressure:
    """فشار رویداد نزدیک بر پیش‌بینی."""

    active: bool
    minutes_until: float | None
    event: MarketEvent | None = None
    strength: float = 0.0        # 0..1 برای کاهش اطمینان
    horizon_minutes: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "active": self.active,
            "minutes_until": round(self.minutes_until, 1) if self.minutes_until is not None else None,
            "event": self.event.to_dict() if self.event else None,
            "strength": round(self.strength, 2),
            "horizon_minutes": self.horizon_minutes,
        }


def event_pressure(
    events: list[MarketEvent],
    *,
    now: datetime,
    horizon_minutes: int,
) -> EventPressure:
    """
    فشار رویدادهای نزدیک روی یک افق — خواستهٔ ۳۲.

    رویداد پرتأثیری که در پنجرهٔ افق (با حاشیهٔ ۱۲۰ دقیقه) می‌افتد،
    پیش‌بینی را «رویدادآگاه» می‌کند: اطمینان کاهش می‌یابد.
    """
    now = now.astimezone(timezone.utc)
    horizon_end = now.timestamp() + horizon_minutes * 60 + HIGH_IMPACT_WINDOW_MINUTES * 60

    best: MarketEvent | None = None
    best_minutes: float | None = None
    best_strength = 0.0

    for event in events:
        minutes_until = (event.at.timestamp() - now.timestamp()) / 60.0
        # فقط رویدادهایی که در پنجرهٔ تأثیرِ افق‌اند
        if event.at.timestamp() > horizon_end:
            continue
        if minutes_until < -HIGH_IMPACT_WINDOW_MINUTES:
            continue  # خیلی گذشته
        weight = {"high": 1.0, "medium": 0.5, "low": 0.2}.get(event.impact, 0.3)
        # نزدیک‌تر = فشار بیشتر
        proximity = 1.0 if minutes_until >= 0 else max(0.0, 1.0 + minutes_until / HIGH_IMPACT_WINDOW_MINUTES)
        if minutes_until > HIGH_IMPACT_WINDOW_MINUTES:
            proximity = HIGH_IMPACT_WINDOW_MINUTES / max(minutes_until, 1.0)
        strength = weight * (0.4 + 0.6 * proximity)
        if strength > best_strength:
            best, best_minutes, best_strength = event, minutes_until, strength

    if best is None or best_strength < 0.25:
        return EventPressure(False, None, None, 0.0, horizon_minutes)

    reasons = [f"{best.impact}_impact_event_within_horizon"]
    return EventPressure(
        active=True,
        minutes_until=best_minutes,
        event=best,
        strength=round(min(1.0, best_strength), 2),
        horizon_minutes=horizon_minutes,
        reasons=reasons,
    )
