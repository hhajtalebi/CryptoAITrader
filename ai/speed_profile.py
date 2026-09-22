"""پروفایل سرعت هوش مصنوعی.

پیش‌فرض «متعادل» همان عددهای ذخیره‌شدهٔ فعلی را نگه می‌دارد تا ذخیرهٔ
کاربر بازنویسی نشود. «سریع» و «عمیق» فقط وقتی اثر می‌کنند که کاربر
خودش پروفایل را انتخاب کرده باشد.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpeedProfile:
    """سقف گام و زمان برای عامل، چت و تولید سیگنال."""

    key: str
    agent_steps: int
    agent_timeout: int
    chat_tools: int
    chat_timeout: int
    signal_timeout: int


PROFILES: dict[str, SpeedProfile] = {
    "fast": SpeedProfile("fast", 1, 45, 1, 40, 30),
    "balanced": SpeedProfile("balanced", 8, 180, 4, 120, 45),
    "deep": SpeedProfile("deep", 12, 300, 8, 180, 90),
}


def resolve_profile(name: str | None) -> SpeedProfile:
    """نام ناشناخته به متعادل برمی‌گردد، نه به سریع."""
    key = str(name or "balanced").strip().lower()
    return PROFILES.get(key, PROFILES["balanced"])


def _read(settings: Any, key: str, default: Any) -> Any:
    """خواندن تنظیم از شیء تنظیمات یا دیکشنری، بدون فرض نوع."""
    getter = getattr(settings, "get", None)
    if callable(getter):
        value = getter(key, default)
        return default if value in (None, "") else value
    if isinstance(settings, dict):
        value = settings.get(key, default)
        return default if value in (None, "") else value
    return default


def _read_int(settings: Any, key: str, default: int) -> int:
    """خواندن عدد صحیح. مقدار خراب به پیش‌فرض برمی‌گردد."""
    try:
        return int(_read(settings, key, default))
    except (TypeError, ValueError):
        return int(default)


def limits_for(settings: Any) -> SpeedProfile:
    """
    سقف اجرایی بر پایهٔ پروفایل.

    در حالت متعادل، عددهای ذخیره‌شدهٔ کاربر مقدم‌اند. در سریع و عمیق،
    خود پروفایل سقف را تعیین می‌کند.
    """
    profile = resolve_profile(_read(settings, "ai.speed_profile", "balanced"))
    if profile.key != "balanced":
        return profile
    return SpeedProfile(
        key="balanced",
        agent_steps=_read_int(settings, "ai.max_agent_steps", profile.agent_steps),
        agent_timeout=_read_int(settings, "ai.agent_timeout", profile.agent_timeout),
        chat_tools=_read_int(settings, "ai.chat_max_tools", profile.chat_tools),
        chat_timeout=_read_int(settings, "ai.chat_timeout", profile.chat_timeout),
        signal_timeout=_read_int(settings, "signals.ai_timeout", profile.signal_timeout),
    )


def signal_timeout_seconds(settings: Any) -> float:
    """مهلت تولید سیگنال، با رعایت پروفایل سرعت."""
    return float(limits_for(settings).signal_timeout)
