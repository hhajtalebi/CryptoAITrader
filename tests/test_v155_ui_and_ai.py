"""
آزمون‌های نسخهٔ ۱٫۵٫۵ — کرش مدال بازار، نشانی سرویس هوش مصنوعی و ظاهر.

هر سه از گزارش مستقیم کاربر آمده‌اند.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("qt_application")


# ---------------------------------------------------------------------------
# کرش هنگام بستن مدال بازار
# ---------------------------------------------------------------------------
def test_dialog_alive_detects_destroyed_widget(qt_application) -> None:  # type: ignore[no-untyped-def]
    """
    نگهبان باید پنجرهٔ نابودشده را تشخیص دهد.

    نقص واقعی: کاربر مدال جزئیات ارز را می‌بست، ولی کار پس‌زمینه که هنوز
    در راه بود نتیجه را روی همان پنجره اعمال می‌کرد و برنامه با
    «Internal C++ object already deleted» بسته می‌شد.
    """
    from PySide6.QtCore import QCoreApplication, QEventLoop, Qt

    from localization import Translator
    from ui.controllers.main_controller import _dialog_alive
    from ui.dialogs.coin_detail_dialog import CoinDetailDialog

    translator = Translator("fa")
    translator.load()

    dialog = CoinDetailDialog("BTC/USDT", {"price": 100.0}, translator, None)
    assert _dialog_alive(dialog) is True

    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dialog.show()
    dialog.close()
    for _ in range(5):
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
        QCoreApplication.sendPostedEvents(None, 0)

    assert _dialog_alive(dialog) is False
    assert _dialog_alive(None) is False


def test_async_runner_can_cancel_by_key() -> None:
    """
    باید بتوان کار در حال اجرا را با کلیدش لغو کرد.

    بدون این، بستن پنجره کار پس‌زمینه را رها می‌کرد و پاسخ به شیء
    نابودشده می‌رسید.
    """
    import asyncio

    from ui.controllers.async_runner import AsyncRunner

    runner = AsyncRunner()
    runner.start()
    try:

        async def slow() -> str:
            await asyncio.sleep(30)
            return "done"

        runner.submit("job-1", slow())
        assert "job-1" in runner.active_keys()

        assert runner.cancel("job-1") is True
        assert "job-1" not in runner.active_keys()
        # لغو دوباره باید بی‌خطر باشد
        assert runner.cancel("job-1") is False
    finally:
        runner.stop()


# ---------------------------------------------------------------------------
# نشانی سرویس هوش مصنوعی
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("configured", "default_url", "expected"),
    [
        # نشانیِ به‌جامانده از اولاما نباید سرویس ابری را خراب کند
        ("http://127.0.0.1:11434", "https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1"),
        ("http://localhost:11434", "https://api.openai.com/v1", "https://api.openai.com/v1"),
        # نشانی محلی برای سرویس محلی معتبر است
        ("http://127.0.0.1:1234", "http://localhost:11434", "http://127.0.0.1:1234"),
        # نشانی ابریِ سفارشی برای سرویس ابری معتبر است
        ("https://proxy.example.com/v1", "https://openrouter.ai/api/v1", "https://proxy.example.com/v1"),
        # خالی یعنی پیش‌فرض کاتالوگ
        ("", "https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1"),
    ],
)
def test_base_url_resolution(configured: str, default_url: str, expected: str) -> None:
    """
    نشانی ذخیره‌شده فقط وقتی به کار می‌رود که به همین سرویس بخورد.

    نقص واقعی: پیش‌فرض `ai.base_url` نشانی اولاما بود و همان مقدار روی
    هر سرویسی سوار می‌شد. کاربر سرویس را روی openrouter می‌گذاشت ولی
    درخواست به 127.0.0.1:11434 می‌رفت و «Network error» می‌گرفت — یعنی
    هوش مصنوعی هرگز کار نمی‌کرد.
    """
    from app.application import Application

    assert Application._resolve_base_url(configured, default_url, "openrouter") == expected


def test_default_base_url_is_empty() -> None:
    """پیش‌فرض باید خالی باشد تا نشانی درستِ هر سرویس از کاتالوگ بیاید."""
    from app.config.defaults import DEFAULT_SETTINGS, SettingKey

    assert DEFAULT_SETTINGS[SettingKey.AI_BASE_URL.value] == ""


# ---------------------------------------------------------------------------
# ظاهر
# ---------------------------------------------------------------------------
def test_midnight_aurora_theme_is_registered() -> None:
    """پوستهٔ تازه باید در کاتالوگ و در شمارشگر پوسته‌ها باشد."""
    from app.core.constants import Theme
    from ui.themes import THEME_CATALOG, get_theme

    assert "midnight_aurora" in THEME_CATALOG
    assert Theme.MIDNIGHT_AURORA.value == "midnight_aurora"

    theme = get_theme("midnight_aurora")
    assert theme.is_dark is True
    assert theme.name_fa.strip()
    assert theme.name_en == "Midnight Aurora"


def test_every_theme_builds_a_stylesheet() -> None:
    """هر پوسته باید بدون کلید گمشده به QSS تبدیل شود."""
    from ui.themes import THEME_CATALOG, build_stylesheet

    for key, theme in THEME_CATALOG.items():
        qss = build_stylesheet(theme)
        assert "{" in qss and len(qss) > 500, f"پوستهٔ {key} ناقص است"
        # جای‌گذاری نشده نباید بماند
        assert "{primary}" not in qss
        assert "{radius_lg}" not in qss


def test_avatar_paints_in_both_states(qt_application) -> None:  # type: ignore[no-untyped-def]
    """
    آواتار باید هم برای کاربر واردشده و هم مهمان رسم شود.

    پیش‌تر آواتار با متن ساخته می‌شد و وضعیت ورود را نشان نمی‌داد.
    """
    from ui.themes import THEME_CATALOG
    from ui.widgets import Avatar

    for theme in THEME_CATALOG.values():
        avatar = Avatar()
        avatar.apply_theme(theme)

        avatar.set_user("حسین", authenticated=True)
        assert not avatar.grab().isNull()

        avatar.set_user("", authenticated=False)
        assert not avatar.grab().isNull()


def test_buttons_use_soft_corners() -> None:
    """
    کاربر خواست لبهٔ دکمه‌ها تیز نباشد.

    شعاع دکمه باید دست‌کم به اندازهٔ `radius_lg` پوسته باشد.
    """
    from ui.themes import THEME_CATALOG, build_stylesheet

    for key, theme in THEME_CATALOG.items():
        qss = build_stylesheet(theme)
        start = qss.index("QPushButton {")
        block = qss[start : start + 260]
        radius_line = [ln for ln in block.splitlines() if "border-radius" in ln][0]
        radius = int("".join(ch for ch in radius_line if ch.isdigit()))
        assert radius >= theme.metrics.radius_lg, f"{key}: لبهٔ دکمه تیز است ({radius})"
