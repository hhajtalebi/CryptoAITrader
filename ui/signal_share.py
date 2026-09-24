"""
کپی نام و اطلاعات سیگنال — نسخهٔ ۲.۴.۲.

کاربر خواست بتواند نام نماد یا خلاصهٔ کامل یک سیگنال را از جدول یا پنجرهٔ
جزئیات کپی کند تا جای دیگری (پیام‌رسان، یادداشت، صرافی) بچسباند.

قالب‌بندی خالص است (بدون Qt) تا آزمون‌پذیر باشد؛ فقط `copy_to_clipboard`
به Qt دست می‌زند. اعداد همیشه با ارقام لاتین نوشته می‌شوند تا در صرافی و
ماشین‌حساب قابل چسباندن باشند، حتی وقتی زبان رابط فارسی است.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from app.core.constants import APP_NAME, APP_VERSION

_DIRECTION_MARK = {"LONG": "🟢", "SHORT": "🔴", "WAIT": "⚪"}


def _tr(translator: Any, key: str, default: str, **variables: Any) -> str:
    if translator is None:
        try:
            return default.format(**variables)
        except (KeyError, IndexError, ValueError):
            return default
    return str(translator.tr(key, default, **variables))


def signal_symbol(signal: dict[str, Any] | None) -> str:
    """نام نماد سیگنال، همان‌طور که در جدول دیده می‌شود (مثلاً BTC/USDT)."""
    return str((signal or {}).get("symbol") or "").strip().upper()


def format_price(value: Any) -> str:
    """قیمت با دقت متناسب با بزرگی آن، بدون نماد علمی و با ارقام لاتین."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if number != number or number <= 0:  # NaN یا نامعتبر
        return "—"
    if number >= 1000:
        text = f"{number:,.2f}"
    elif number >= 1:
        text = f"{number:,.4f}"
    else:
        # قیمت‌های خرد (مثل ۰٫۰۰۰۰۱۲۳۴): شش رقم معنادار
        text = f"{number:.{max(6, _leading_zeros(number) + 6)}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _leading_zeros(number: float) -> int:
    text = f"{number:.20f}".split(".")[1]
    return len(text) - len(text.lstrip("0"))


def _take_profits(signal: dict[str, Any]) -> list[float]:
    values: Iterable[Any] = signal.get("take_profits") or []
    if not values and signal.get("take_profit"):
        values = [signal.get("take_profit")]
    out: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            out.append(number)
    return out


def _created_text(signal: dict[str, Any]) -> str:
    raw = signal.get("created_at_raw") or signal.get("created_at")
    if isinstance(raw, datetime):
        return raw.strftime("%Y-%m-%d %H:%M")
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return text


def format_signal_text(signal: dict[str, Any] | None, translator: Any = None) -> str:
    """
    متن کامل و قابل اشتراک یک سیگنال.

    نمونه:
        🟢 BTC/USDT — LONG
        Confidence: 72%
        Entry: 64,100 – 64,250
        Stop loss: 63,200
        Targets: TP1 65,000 | TP2 66,100
        Leverage: ×5 | R:R 2.1
        ...
    """
    signal = dict(signal or {})
    symbol = signal_symbol(signal) or "—"
    direction = str(signal.get("direction") or "WAIT").upper()
    direction_text = _tr(translator, f"signals.{direction.lower()}", direction)
    lines = [f"{_DIRECTION_MARK.get(direction, '⚪')} {symbol} — {direction_text}"]

    confidence = signal.get("confidence")
    if confidence not in (None, ""):
        try:
            lines.append(_tr(translator, "signals.share.confidence", "Confidence: {value}%",
                             value=int(round(float(confidence)))))
        except (TypeError, ValueError):
            pass

    entry_min = signal.get("entry_min")
    entry_max = signal.get("entry_max")
    entry_single = signal.get("entry") or signal.get("entry_price")
    entry_text = ""
    if entry_min and entry_max and format_price(entry_min) != format_price(entry_max):
        entry_text = f"{format_price(entry_min)} – {format_price(entry_max)}"
    elif entry_min or entry_max or entry_single:
        entry_text = format_price(entry_min or entry_max or entry_single)
    if entry_text and entry_text != "—":
        lines.append(_tr(translator, "signals.share.entry", "Entry: {value}", value=entry_text))

    stop = format_price(signal.get("stop_loss"))
    if stop != "—":
        lines.append(_tr(translator, "signals.share.stop_loss", "Stop loss: {value}", value=stop))

    targets = _take_profits(signal)
    if targets:
        joined = " | ".join(
            f"TP{index} {format_price(value)}" for index, value in enumerate(targets, start=1)
        )
        lines.append(_tr(translator, "signals.share.targets", "Targets: {value}", value=joined))

    extras: list[str] = []
    try:
        leverage = int(signal.get("leverage") or 0)
    except (TypeError, ValueError):
        leverage = 0
    if leverage > 0:
        extras.append(_tr(translator, "signals.share.leverage", "Leverage: ×{value}",
                          value=leverage))
    try:
        ratio = float(signal.get("risk_reward") or 0)
    except (TypeError, ValueError):
        ratio = 0.0
    if ratio > 0:
        extras.append(_tr(translator, "signals.share.risk_reward", "R:R {value}",
                          value=f"{ratio:.2f}"))
    if extras:
        lines.append(" | ".join(extras))

    frames = [str(frame) for frame in (signal.get("timeframes") or []) if frame]
    primary = str(signal.get("primary_timeframe") or signal.get("timeframe") or "")
    if frames or primary:
        text = ", ".join(frames) if frames else primary
        if primary and frames:
            text += " " + _tr(translator, "signals.share.primary", "(primary {value})",
                              value=primary)
        lines.append(_tr(translator, "signals.share.timeframes", "Timeframes: {value}",
                         value=text))

    exchange = str(signal.get("exchange") or "").strip()
    if exchange:
        lines.append(_tr(translator, "signals.share.exchange", "Exchange: {value}",
                         value=exchange))
    created = _created_text(signal)
    if created:
        lines.append(_tr(translator, "signals.share.time", "Time: {value}", value=created))

    lines.append(
        _tr(translator, "signals.share.disclaimer",
            "⚠️ Not financial advice — {app} v{version}",
            app=APP_NAME, version=APP_VERSION)
    )
    return "\n".join(lines)


def copy_to_clipboard(text: str) -> bool:
    """قرار دادن متن در کلیپ‌بورد سیستم؛ شکست بی‌صدا و با بازگشت False."""
    if not text:
        return False
    try:
        from PySide6.QtGui import QGuiApplication  # noqa: PLC0415

        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return False
        clipboard.setText(text)
        return True
    except Exception:  # noqa: BLE001
        return False
