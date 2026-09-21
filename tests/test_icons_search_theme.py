"""
آزمون‌های نقص‌های گزارش‌شده در نسخهٔ ۱٫۵٫۱.

کاربر شش ایراد گرفت: تعویض‌نشدن پوسته، نبودن بخش ظاهر، نبودن پیشنهاد در
جست‌وجو، وصل‌نشدن هوش مصنوعی، خرابی آیکن‌ها و ضعف طراحی. این فایل برای
هر کدام یک آزمون می‌گذارد تا دوباره برنگردند.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QIcon

from ui.icons import available_icons, icon, icon_pixmap, icon_svg, resolve_name

pytestmark = pytest.mark.usefixtures("qt_application")


# ---------------------------------------------------------------------------
# آیکن‌ها — ایراد پنجم
# ---------------------------------------------------------------------------
def test_every_icon_renders_a_non_empty_pixmap() -> None:
    """
    هیچ آیکنی نباید خالی ترسیم شود.

    ایراد اصلی این بود که آیکن‌ها با گلیف فونت ساخته می‌شدند و چون آن
    گلیف‌ها در Vazirmatn نبودند، مربع خالی دیده می‌شد.
    """
    for name in available_icons():
        pixmap = icon_pixmap(name, "#ffffff", 24)
        assert not pixmap.isNull(), f"آیکن {name} تهی است"
        assert pixmap.width() > 0 and pixmap.height() > 0


def test_icon_returns_qicon_with_content() -> None:
    """خروجی icon باید یک QIcon واقعی و غیرتهی باشد."""
    result = icon("dashboard", "#22d3ee", 20)
    assert isinstance(result, QIcon)
    assert not result.isNull()


def test_unknown_icon_falls_back_instead_of_crashing() -> None:
    """نام ناشناخته نباید برنامه را بشکند."""
    assert resolve_name("this-icon-does-not-exist") == "info"
    assert not icon_pixmap("this-icon-does-not-exist", "#fff", 16).isNull()


def test_icon_svg_has_no_unresolved_currentcolor() -> None:
    """
    QSvgRenderer مقدار currentColor را نمی‌فهمد.

    اگر این کلمه در خروجی بماند، آیکن نامرئی ترسیم می‌شود.
    """
    svg = icon_svg("theme", "#ff0000")
    assert "currentColor" not in svg
    assert "#ff0000" in svg


def test_all_navigation_icons_exist() -> None:
    """هر ورودی منوی کناری باید آیکن تعریف‌شده داشته باشد."""
    from ui.windows.main_window import NAV_ICONS

    for name in NAV_ICONS:
        assert name in available_icons() or resolve_name(name) in available_icons()


# ---------------------------------------------------------------------------
# جست‌وجو — ایراد سوم
# ---------------------------------------------------------------------------
@pytest.fixture()
def search_box(qt_application):  # type: ignore[no-untyped-def]
    """یک کادر جست‌وجوی آمادهٔ آزمون."""
    from ui.widgets.chrome import SearchBox

    box = SearchBox()
    box.set_suggestions(
        [
            ("page", "nav.markets", "بازارها"),
            ("page", "nav.settings", "تنظیمات"),
            ("symbol", "BTC/USDT", "BTC/USDT"),
            ("symbol", "ETH/USDT", "ETH/USDT"),
        ]
    )
    return box


def test_search_box_has_completer_with_suggestions(search_box) -> None:  # type: ignore[no-untyped-def]
    """کادر جست‌وجو باید هنگام تایپ فهرست پیشنهاد بدهد."""
    completer = search_box.completer()
    assert completer is not None
    completer.setCompletionPrefix("BTC")
    assert completer.completionCount() == 1
    assert completer.currentCompletion() == "BTC/USDT"


def test_search_suggestions_match_in_the_middle(search_box) -> None:  # type: ignore[no-untyped-def]
    """جست‌وجو باید شامل‌بودن را ببیند، نه فقط شروع عبارت را."""
    completer = search_box.completer()
    completer.setCompletionPrefix("USDT")
    assert completer.completionCount() == 2


def test_choosing_a_suggestion_emits_kind_and_value(search_box) -> None:  # type: ignore[no-untyped-def]
    """انتخاب پیشنهاد باید نوع و مقدار را بدهد تا کنترلر بداند کجا برود."""
    seen: list[tuple[str, str]] = []
    search_box.suggestion_activated.connect(lambda k, v: seen.append((k, v)))
    search_box._on_suggestion_chosen("تنظیمات")
    assert seen == [("page", "nav.settings")]


# ---------------------------------------------------------------------------
# زنجیرهٔ هوش مصنوعی — ایراد چهارم
# ---------------------------------------------------------------------------
def test_fallback_registers_more_than_the_active_provider(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """
    باید همهٔ سرویس‌های قابل استفاده ثبت شوند.

    پیش‌تر فقط سرویس فعال ثبت می‌شد، پس گزینهٔ «جایگزینی» بی‌اثر بود و با
    خاموش‌بودن همان یک سرویس، چت کامل از کار می‌افتاد.
    """
    monkeypatch.setenv("CAT_DATA_DIR", str(tmp_path))
    from ai.providers import AIProviderManager
    from app.application import Application

    app = Application()
    app.settings.set("ai.fallback_enabled", True)
    app.secrets.set("ai.openrouter.api_key", "sk-or-v1-test")
    app.secrets.set("ai.groq.api_key", "gsk-test")

    manager = AIProviderManager(app.events, fallback_enabled=True)
    app._register_fallback_providers(manager, skip="ollama")
    registered = list(manager._providers)

    assert "openrouter" in registered, "سرویس دارای کلید باید در زنجیره باشد"
    assert "groq" in registered
    assert "ollama" not in registered, "سرویس فعال نباید دوباره ثبت شود"


def test_provider_without_key_is_not_registered(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """سرویسی که کلید ندارد نباید بیهوده در زنجیره بیفتد."""
    monkeypatch.setenv("CAT_DATA_DIR", str(tmp_path))
    from ai.providers import AIProviderManager
    from app.application import Application

    app = Application()
    manager = AIProviderManager(app.events, fallback_enabled=True)
    app._register_fallback_providers(manager, skip="ollama")

    assert "openai" not in manager._providers
    assert "anthropic" not in manager._providers


def test_fallback_disabled_registers_nothing_extra(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """اگر کاربر جایگزینی را خاموش کرده باشد، به انتخابش احترام می‌گذاریم."""
    monkeypatch.setenv("CAT_DATA_DIR", str(tmp_path))
    from ai.providers import AIProviderManager
    from app.application import Application

    app = Application()
    app.settings.set("ai.fallback_enabled", False)
    app.secrets.set("ai.openrouter.api_key", "sk-or-v1-test")

    manager = AIProviderManager(app.events, fallback_enabled=False)
    app._register_fallback_providers(manager, skip="ollama")

    assert not manager._providers


def test_chat_agent_prefers_the_selected_provider(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """
    سرویس انتخابی کاربر باید اول زنجیره باشد.

    بدون این، هر پیام چت اول سراغ سرویس‌های محلی خاموش می‌رفت و کاربر
    چند ثانیه منتظر شکست آن‌ها می‌ماند.
    """
    monkeypatch.setenv("CAT_DATA_DIR", str(tmp_path))
    from ai.providers import AIProviderConfig, AIProviderManager
    from app.application import Application

    app = Application()
    manager = AIProviderManager(app.events, fallback_enabled=True)
    for name, priority in (("ollama", 10), ("openrouter", 20)):
        manager.register_from_type(
            "openai_compatible",
            AIProviderConfig(
                name=name,
                base_url="http://127.0.0.1:1/v1",
                model="m",
                requires_api_key=False,
                priority=priority,
            ),
            None,
        )

    chain = [p.name for p in manager.ordered_providers("openrouter")]
    assert chain[0] == "openrouter"
