"""
آزمون‌های زیباسازی نسخهٔ ۱٫۶٫۰.

پوشش: پوستهٔ تازه، گرد بودن همهٔ گوشه‌ها، تمایز بصری حالت ورود/مهمان، و
پاک‌سازی راهنمای داخلی از پاسخ چت.
"""

from __future__ import annotations

import re

import pytest

from ai.agent.chat_agent import ChatAgent
from app.core.constants import Theme
from ui.themes.catalog import THEME_CATALOG, get_theme, list_themes, resolve_key
from ui.themes.stylesheet import build_stylesheet


class TestRoyalSilkTheme:
    """پوستهٔ تازهٔ «ابریشم سلطنتی»."""

    def test_theme_exists_and_is_dark(self) -> None:
        """پوستهٔ تازه باید در کاتالوگ باشد."""
        theme = get_theme("royal_silk")
        assert theme.key == "royal_silk"
        assert theme.is_dark is True
        assert theme.name_fa
        assert theme.name_en == "Royal Silk"

    def test_theme_is_selectable_from_settings(self) -> None:
        """
        باید در فهرست انتخاب تنظیمات دیده شود.

        کاربر خواست پوسته را با نام از تنظیمات انتخاب کند.
        """
        keys = [theme.key for theme in list_themes()]
        assert "royal_silk" in keys

    def test_theme_is_registered_in_the_enum(self) -> None:
        """
        هر پوستهٔ کاتالوگ باید در `Theme` هم باشد.

        اگر جا بماند، ذخیرهٔ انتخاب کاربر می‌شکند.
        """
        enum_values = {item.value for item in Theme}
        for theme in list_themes():
            assert theme.key in enum_values, f"{theme.key} در Theme نیست"

    def test_accent_differs_from_market_colors(self) -> None:
        """
        لهجهٔ طلایی نباید با سبز/قرمز بازار اشتباه شود.

        اگر لهجه به رنگ سود یا زیان نزدیک باشد، کاربر در یک نگاه
        اشتباه می‌کند.
        """
        colors = get_theme("royal_silk").colors
        assert colors.accent != colors.success
        assert colors.accent != colors.danger
        assert colors.chart_up != colors.chart_down

    def test_stylesheet_renders_without_leftover_placeholders(self) -> None:
        """هیچ جای‌گیرِ قالب نباید در خروجی بماند."""
        qss = build_stylesheet(get_theme("royal_silk"))
        assert len(qss) > 1000
        assert not re.findall(r"\{[a-z_]+\}", qss)


class TestAllThemesRender:
    """همهٔ پوسته‌ها باید سالم ساخته شوند."""

    @pytest.mark.parametrize("key", sorted(THEME_CATALOG))
    def test_stylesheet_is_complete(self, key: str) -> None:
        """هر پوسته باید شیوه‌نامهٔ کامل و بدون جای‌گیر بدهد."""
        qss = build_stylesheet(get_theme(key))
        assert len(qss) > 1000
        assert not re.findall(r"\{[a-z_]+\}", qss)

    def test_legacy_keys_still_resolve(self, ) -> None:
        """نام‌های قدیمی نباید تنظیمات کاربران فعلی را بشکنند."""
        assert resolve_key("dark") == "glass_dark"
        assert resolve_key("light") == "minimal_light"
        assert resolve_key(None) in THEME_CATALOG
        assert resolve_key("nonsense") in THEME_CATALOG


class TestRoundedCorners:
    """
    هیچ گوشهٔ تیزی نباید بماند — خواستهٔ صریح کاربر.
    """

    #: عناصری که کاربر به‌عنوان «دکمه/جعبه» می‌بیند
    BOXY_SELECTORS = (
        "QPushButton {",
        'QPushButton[role="primary"] {',
        'QPushButton[role="icon"] {',
        'QPushButton[role="chip"] {',
        'QPushButton[role="segment"] {',
        'QPushButton[role="nav"] {',
        "QLineEdit, QTextEdit, QPlainTextEdit",
        "QComboBox {",
        "QTabBar::tab {",
        'QToolButton[role="user_chip"] {',
    )

    @pytest.mark.parametrize("theme_key", sorted(THEME_CATALOG))
    def test_key_widgets_declare_a_radius(self, theme_key: str) -> None:
        """هر عنصر جعبه‌ای باید border-radius داشته باشد."""
        qss = build_stylesheet(get_theme(theme_key))
        for selector in self.BOXY_SELECTORS:
            index = qss.find(selector)
            assert index >= 0, f"{selector} در پوسته {theme_key} نیست"
            block = qss[index : qss.find("}", index)]
            # گردی می‌تواند یکجا (`border-radius`) یا گوشه‌به‌گوشه
            # (`border-top-left-radius`) اعلام شود؛ هر دو پذیرفته است.
            assert "radius" in block, f"{selector} گوشهٔ تیز دارد ({theme_key})"

    #: پوسته‌هایی که کاربر عمداً «خطوط مربعی» خواسته است. گوشهٔ تیز در
    #: اینها اشکال نیست، بلکه هویت همان پوسته است؛ در بقیه همچنان ممنوع.
    SQUARE_THEMES = frozenset({"gold_dark"})

    @pytest.mark.parametrize("theme_key", sorted(THEME_CATALOG))
    def test_button_radius_matches_theme_character(self, theme_key: str) -> None:
        """گوشهٔ تیز فقط در پوستهٔ مربعی مجاز است، نه جای دیگر."""
        qss = build_stylesheet(get_theme(theme_key))
        index = qss.find("QPushButton {")
        block = qss[index : qss.find("}", index)]
        match = re.search(r"border-radius:\s*(\d+)px", block)
        assert match is not None
        radius = int(match.group(1))

        if theme_key in self.SQUARE_THEMES:
            assert radius == 0, "پوستهٔ مربعی باید واقعاً مربع باشد"
        else:
            assert radius >= 6

    @pytest.mark.parametrize("theme_key", sorted(THEME_CATALOG))
    def test_tabs_declare_top_corner_radius(self, theme_key: str) -> None:
        """زبانه‌ها باید گوشهٔ بالا را صریح تعیین کنند (گرد یا مربع)."""
        qss = build_stylesheet(get_theme(theme_key))
        index = qss.find("QTabBar::tab {")
        block = qss[index : qss.find("}", index)]
        assert "border-top-left-radius" in block
        assert "border-top-right-radius" in block

    def test_square_theme_is_square_everywhere(self) -> None:
        """
        «خطوط مربعی» یعنی همه‌جا، نه فقط دکمه‌ها.

        اگر کارت‌ها یا ورودی‌ها گرد بمانند، پوسته دورگه به نظر می‌رسد و
        حس تابلوی معاملاتی که کاربر خواست از بین می‌رود.
        """
        qss = build_stylesheet(get_theme("gold_dark"))
        for selector in self.BOXY_SELECTORS:
            index = qss.find(selector)
            block = qss[index : qss.find("}", index)]
            for value in re.findall(r"radius:\s*(\d+)px", block):
                assert int(value) == 0, f"{selector} در پوستهٔ مربعی گرد است"


class TestUserChipStates:
    """تمایز بصری حالت ورود و مهمان در نوار بالا."""

    @pytest.mark.parametrize("theme_key", sorted(THEME_CATALOG))
    def test_both_states_are_styled(self, theme_key: str) -> None:
        """هر دو حالت باید قاعدهٔ ظاهری جدا داشته باشند."""
        qss = build_stylesheet(get_theme(theme_key))
        assert 'state="signed_in"' in qss
        assert 'state="guest"' in qss

    def test_guest_and_signed_in_look_different(self) -> None:
        """
        دو حالت نباید یکسان به نظر برسند.

        اگر یکی باشند، کاربر نمی‌فهمد با حساب خودش کار می‌کند یا نه.
        """
        qss = build_stylesheet(get_theme("royal_silk"))
        signed = qss[qss.find('[state="signed_in"] {') :][:220]
        guest = qss[qss.find('[state="guest"] {') :][:220]
        assert signed != guest
        # مهمان قاب خط‌چین می‌گیرد تا «موقتی بودن» را برساند
        assert "dashed" in guest

    def test_chip_reflects_authentication(self, qt_application) -> None:
        """`set_user` باید ویژگی state را درست ست کند."""
        from ui.widgets.chrome import UserMenuButton

        chip = UserMenuButton()
        chip.set_user("مهمان", authenticated=False)
        assert chip.property("state") == "guest"
        chip.set_user("حسین", authenticated=True)
        assert chip.property("state") == "signed_in"

    def test_inline_padding_does_not_kill_theme_colors(self, qt_application) -> None:
        """
        شیوه‌نامهٔ درون‌خطی نباید قاعدهٔ پوسته را خنثی کند.

        این یک باگ واقعی بود: پدینگِ بدون انتخابگر، رنگ و قاب حالت را
        از بین می‌برد و نشان کاربر همیشه بی‌رنگ می‌ماند.
        """
        from ui.widgets.chrome import UserMenuButton

        chip = UserMenuButton()
        chip.set_user("مهمان", authenticated=False)
        inline = chip.styleSheet()
        # باید محدود به همان حالت باشد، نه یک قاعدهٔ سراسری بی‌انتخابگر
        assert "user_chip" in inline
        assert "state=" in inline
        assert "padding" in inline


class TestChatInternalLeak:
    """راهنمای داخلی نباید در پاسخ چت دیده شود."""

    def test_app_context_block_is_removed(self) -> None:
        """
        بلوک `[App context: …]` باید حذف شود.

        این متن عمداً به مدل داده می‌شود ولی مدل‌های کوچک آن را تکرار
        می‌کنند و کاربر متن داخلی برنامه را می‌بیند.
        """
        raw = "تحلیل روند صعودی است.\n[App context: symbol=BTC/USDT, mode=general]"
        assert ChatAgent._strip_fences(raw) == "تحلیل روند صعودی است."

    def test_mode_guidance_block_is_removed(self) -> None:
        """راهنمای حالت هم نباید دیده شود."""
        raw = "پاسخ کوتاه.\n[Mode guidance: Focus on an actionable setup]"
        assert ChatAgent._strip_fences(raw) == "پاسخ کوتاه."

    def test_both_blocks_removed_together(self) -> None:
        """هر دو بلوک با هم حذف می‌شوند."""
        raw = (
            "خط اول\n"
            "[App context: symbol=ETH/USDT]\n"
            "خط دوم\n"
            "[Mode guidance: teach slowly]"
        )
        cleaned = ChatAgent._strip_fences(raw)
        assert "App context" not in cleaned
        assert "Mode guidance" not in cleaned
        assert "خط اول" in cleaned
        assert "خط دوم" in cleaned

    def test_code_fences_still_stripped(self) -> None:
        """رفتار قبلی (حذف ```) نباید از بین برود."""
        assert ChatAgent._strip_fences("```\nسلام\n```") == "سلام"

    def test_normal_text_is_untouched(self) -> None:
        """متن عادی نباید تغییر کند."""
        text = "روند صعودی است و حمایت نزدیک است."
        assert ChatAgent._strip_fences(text) == text

    def test_brackets_in_normal_text_survive(self) -> None:
        """
        براکت‌های معمولی نباید قربانی شوند.

        فقط بلوک‌های شناخته‌شده حذف می‌شوند، نه هر چیزی داخل براکت.
        """
        text = "سطح [مهم] حمایت ۷۷۰۰۰ است."
        assert ChatAgent._strip_fences(text) == text
