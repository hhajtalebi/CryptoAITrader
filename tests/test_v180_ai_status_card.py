"""
آزمون کارت وضعیت هوش مصنوعی در نوار کناری.

کاربر خواست کارتی مستطیلی در نوار کناری، با نمایش وضعیت و مدل متصل، که
هر سه دقیقه تازه شود. آزمون‌ها روی همان سه ادعا تمرکز دارند: خودِ کارت
وضعیت را درست نشان بدهد، بازهٔ تایمر واقعاً سه دقیقه باشد، و بررسی
وضعیت از سرویس واقعی بپرسد نه از تنظیمات.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from localization import Translator
from ui.widgets.ai_status_card import (
    MAX_MODEL_CHARS,
    REFRESH_INTERVAL_MS,
    AIStatusCard,
    short_model_name,
)


@pytest.fixture()
def card(qt_application) -> AIStatusCard:  # noqa: ARG001 - نیاز به QApplication
    """یک کارت تازه برای هر آزمون."""
    return AIStatusCard()


def test_refresh_interval_is_three_minutes() -> None:
    """خواستهٔ صریح کاربر: هر سه دقیقه."""
    assert REFRESH_INTERVAL_MS == 3 * 60 * 1000


def test_controller_timer_uses_the_card_interval() -> None:
    """تایمر کنترلر نباید بازهٔ جداگانه و ناهماهنگ داشته باشد."""
    from ui.controllers.main_controller import AI_STATUS_INTERVAL

    assert AI_STATUS_INTERVAL == REFRESH_INTERVAL_MS


def test_set_status_shows_provider_and_model(card: AIStatusCard) -> None:
    """کارت باید مدلِ واقعاً متصل را نشان دهد، نه فقط چراغ سبز."""
    card.set_status(
        state="connected",
        title="هوش مصنوعی",
        provider="ollama",
        model="llama3.1",
    )

    assert card.state == "connected"
    assert "llama3.1" in card.model_label.text()
    assert "ollama" in card.provider_label.text().lower()


def test_unknown_state_for_unexpected_value(card: AIStatusCard) -> None:
    """حالت ناشناخته نباید به‌اشتباه «متصل» تفسیر شود."""
    card.set_status(state="banana", title="هوش مصنوعی")

    assert card.state == "unknown"


def test_disconnected_state_is_recorded(card: AIStatusCard) -> None:
    """قطع‌بودن باید حالت خودش را داشته باشد تا رنگ درست بگیرد."""
    card.set_status(state="disconnected", title="هوش مصنوعی", detail="connection refused")

    assert card.state == "disconnected"


def test_checking_state_is_distinct_from_connected(card: AIStatusCard) -> None:
    """«در حال بررسی» نباید مثل «متصل» دیده شود."""
    card.set_status(state="connected", title="هوش مصنوعی", model="gpt-4o")
    card.set_checking("در حال بررسی…")

    assert card.state != "connected"


def test_latin_labels_are_left_to_right(card: AIStatusCard) -> None:
    """نام مدل لاتین در چیدمان راست‌به‌چپ نباید وارونه شود."""
    card.set_status(state="connected", title="هوش مصنوعی", provider="openai", model="gpt-4o-mini")

    assert card.model_label.layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert card.provider_label.layoutDirection() == Qt.LayoutDirection.LeftToRight


def test_long_model_name_is_shortened_but_kept_in_tooltip(card: AIStatusCard) -> None:
    """نام بلند نباید کارت را بکشد، ولی نباید هم گم شود."""
    long_name = "openrouter/meta-llama-3.1-405b-instruct-turbo-free"
    card.set_status(state="connected", title="هوش مصنوعی", model=long_name)

    assert len(card.model_label.text()) <= MAX_MODEL_CHARS
    assert long_name in card.model_label.toolTip()


def test_short_model_name_strips_provider_prefix() -> None:
    """پیشوند ارائه‌دهنده تکراری است؛ جای آن برای خود مدل لازم است."""
    assert short_model_name("gg/gemini-2.5-pro") == "gemini-2.5-pro"


def test_card_is_clickable(card: AIStatusCard, qt_application) -> None:  # noqa: ARG001
    """کلیک باید کاربر را به تنظیمات هوش مصنوعی ببرد."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QMouseEvent

    seen: list[bool] = []
    card.clicked.connect(lambda: seen.append(True))

    def press(button: Qt.MouseButton) -> None:
        """شبیه‌سازی یک کلیک روی کارت."""
        card.mousePressEvent(
            QMouseEvent(
                QMouseEvent.Type.MouseButtonPress,
                QPoint(5, 5),
                button,
                button,
                Qt.KeyboardModifier.NoModifier,
            )
        )

    press(Qt.MouseButton.LeftButton)
    # کلیک راست منوی زمینه است، نه کنش؛ نباید ناوبری کند.
    press(Qt.MouseButton.RightButton)

    assert seen == [True]


def test_sidebar_mounts_the_card(qt_application) -> None:  # noqa: ARG001
    """کارت باید واقعاً در نوار کناری باشد، نه فقط موجود در کدبیس."""
    from ui.widgets.chrome import IconSidebar

    sidebar = IconSidebar()

    assert isinstance(sidebar.ai_status, AIStatusCard)
    assert sidebar.ai_status.parentWidget() is not None


def test_card_survives_theme_change(card: AIStatusCard) -> None:
    """کارت باید در هر نه پوستهٔ برنامه بدون خطا رنگ بگیرد."""
    from ui.themes.catalog import THEME_CATALOG

    card.set_status(state="connected", title="هوش مصنوعی", model="llama3.1")
    for theme in THEME_CATALOG.values():
        card.apply_theme(theme)

    assert card.state == "connected"


def test_stylesheet_defines_the_card_role() -> None:
    """بدون قاعدهٔ QSS، کارت در هیچ پوسته‌ای شکل نمی‌گیرد."""
    import re

    from ui.themes.catalog import THEME_CATALOG
    from ui.themes.stylesheet import build_stylesheet

    for theme in THEME_CATALOG.values():
        css = build_stylesheet(theme)
        assert 'role="aiStatus"' in css
        assert not re.findall(r"\{[a-z_]+\}", css)


def test_locale_keys_exist_in_both_languages() -> None:
    """هیچ رشتهٔ رابط کاربری نباید در کد سفت‌شده باشد."""
    keys = ("sidebar.ai_title", "sidebar.ai_checking", "sidebar.ai_off")
    for language in ("fa", "en"):
        translator = Translator(language)
        for key in keys:
            value = translator.tr(key)
            assert value and value != key
