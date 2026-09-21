"""
آزمون پوسته‌های سفارشی و ویرایشگر زندهٔ ظاهر.

کاربر خواست «بتواند همهٔ جزئیات ظاهری را تغییر دهد و پوستهٔ خودش را
ذخیره کند». نکتهٔ حساس اینجا پایداری است: یک مقدار نامعتبر در فایل
پوسته نباید رابط کاربری را سفید یا برنامه را بی‌بالا کند.
"""

from __future__ import annotations

import json
import re

import pytest

from localization import Translator
from ui.themes.catalog import THEME_CATALOG, get_theme
from ui.themes.custom import (
    CUSTOM_PREFIX,
    METRIC_LIMITS,
    CustomThemeStore,
    build_tokens,
    is_custom,
    sanitise_overrides,
    slugify,
)
from ui.themes.stylesheet import build_stylesheet


@pytest.fixture()
def store(tmp_path) -> CustomThemeStore:
    """انبار پوستهٔ سفارشی روی یک پوشهٔ موقت."""
    created = CustomThemeStore(tmp_path)
    yield created
    for key in created.registered:
        THEME_CATALOG.pop(key, None)


class TestSanitising:
    """پاک‌سازی ورودی پیش از رسیدن به QSS."""

    def test_invalid_colour_is_dropped(self) -> None:
        """رنگ نامعتبر کل برگهٔ سبک را خراب می‌کند، پس نباید عبور کند."""
        clean = sanitise_overrides({"colors": {"primary": "not-a-colour"}})

        assert "primary" not in clean.get("colors", {})

    def test_valid_colour_formats_pass(self) -> None:
        """قالب‌های رایج رنگ باید پذیرفته شوند."""
        clean = sanitise_overrides(
            {"colors": {"primary": "#abc", "bg": "#112233", "surface": "rgba(0,0,0,0.4)"}}
        )

        assert set(clean["colors"]) == {"primary", "bg", "surface"}

    def test_unknown_token_is_ignored(self) -> None:
        """فایل دستکاری‌شده نباید بتواند کلید تازه تزریق کند."""
        clean = sanitise_overrides({"colors": {"evil": "#ffffff"}})

        assert not clean.get("colors")

    def test_metric_is_clamped_to_its_range(self) -> None:
        """مقدار دور از بازه، رابط را غیرقابل‌استفاده می‌کند."""
        low, high = METRIC_LIMITS["row_height"]

        clean = sanitise_overrides({"metrics": {"row_height": high + 500}})

        assert clean["metrics"]["row_height"] == high
        assert sanitise_overrides({"metrics": {"row_height": -20}})["metrics"]["row_height"] == low

    def test_non_numeric_metric_is_dropped(self) -> None:
        """متن به‌جای عدد نباید به سنجه‌ها برسد."""
        assert not sanitise_overrides({"metrics": {"radius_md": "big"}}).get("metrics")

    def test_effect_flags_are_coerced_to_bool(self) -> None:
        """جلوه‌ها بولی‌اند و باید بولی بمانند."""
        clean = sanitise_overrides({"effects": {"glass": 1, "elevation": 0}})

        assert clean["effects"] == {"glass": True, "elevation": False}


class TestBuildTokens:
    """ساخت پوسته از پایه و بازنویسی."""

    def test_unset_values_come_from_the_base(self) -> None:
        """پوستهٔ سفارشی باید همیشه کامل باشد."""
        base = get_theme("gold_dark")

        tokens = build_tokens("custom_x", "آزمون", "Test", "gold_dark", {})

        assert tokens.colors.bg == base.colors.bg
        assert tokens.metrics.row_height == base.metrics.row_height

    def test_overrides_win_over_the_base(self) -> None:
        """مقداری که کاربر داده باید واقعاً اعمال شود."""
        tokens = build_tokens(
            "custom_x", "آزمون", "Test", "gold_dark", {"colors": {"primary": "#22d3ee"}}
        )

        assert tokens.colors.primary == "#22d3ee"

    def test_changing_primary_clears_a_stale_gradient(self) -> None:
        """
        گرادیان پوستهٔ پایه نباید رنگ انتخابی کاربر را بپوشاند.

        بدون این، کاربر رنگ اصلی را عوض می‌کند و هیچ تغییری نمی‌بیند.
        """
        base = get_theme("gold_dark")
        assert base.effects.primary_gradient, "پوستهٔ پایهٔ این آزمون باید گرادیان داشته باشد"

        tokens = build_tokens(
            "custom_x", "آزمون", "Test", "gold_dark", {"colors": {"primary": "#22d3ee"}}
        )

        assert tokens.effects.primary_gradient == ""
        assert "#22d3ee" in build_stylesheet(tokens)

    def test_explicit_gradient_is_respected(self) -> None:
        """اگر خود کاربر گرادیان بدهد، نباید پاک شود."""
        gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #111111, stop:1 #222222)"

        tokens = build_tokens(
            "custom_x",
            "آزمون",
            "Test",
            "gold_dark",
            {"colors": {"primary": "#22d3ee"}, "effects": {"primary_gradient": gradient}},
        )

        assert tokens.effects.primary_gradient == gradient

    def test_generated_stylesheet_is_complete(self) -> None:
        """پوستهٔ سفارشی هم نباید جاگذاری حل‌نشده داشته باشد."""
        tokens = build_tokens(
            "custom_x",
            "آزمون",
            "Test",
            "glass_dark",
            {"colors": {"primary": "#ff0066"}, "metrics": {"radius_md": 0}},
        )

        assert not re.findall(r"\{[a-z_]+\}", build_stylesheet(tokens))


class TestStore:
    """ذخیره، خواندن و حذف روی دیسک."""

    def test_save_registers_the_theme_immediately(self, store: CustomThemeStore) -> None:
        """پوستهٔ تازه باید بدون راه‌اندازی دوباره قابل انتخاب باشد."""
        key = store.save("طلایی من", "gold_dark", {"colors": {"primary": "#d4a537"}})

        assert is_custom(key)
        assert key in THEME_CATALOG

    def test_saved_theme_survives_a_restart(self, store: CustomThemeStore, tmp_path) -> None:
        """بازخوانی از دیسک باید همان مقادیر را برگرداند."""
        key = store.save("من", "gold_dark", {"colors": {"primary": "#123456"}})
        THEME_CATALOG.pop(key, None)

        fresh = CustomThemeStore(tmp_path)
        loaded = fresh.load_all()

        assert key in loaded
        assert THEME_CATALOG[key].colors.primary == "#123456"
        THEME_CATALOG.pop(key, None)

    def test_duplicate_name_does_not_overwrite(self, store: CustomThemeStore) -> None:
        """پوستهٔ قبلی کاربر نباید با هم‌نام‌شدن پاک شود."""
        first = store.save("من", "gold_dark", {"colors": {"primary": "#111111"}})
        second = store.save("من", "gold_dark", {"colors": {"primary": "#222222"}})

        assert first != second
        assert THEME_CATALOG[first].colors.primary == "#111111"

    def test_saving_with_an_explicit_key_updates_in_place(self, store: CustomThemeStore) -> None:
        """ویرایش دوبارهٔ یک پوسته نباید کپی بسازد."""
        key = store.save("من", "gold_dark", {"colors": {"primary": "#111111"}})

        again = store.save("من", "gold_dark", {"colors": {"primary": "#333333"}}, key=key)

        assert again == key
        assert THEME_CATALOG[key].colors.primary == "#333333"

    def test_only_differences_are_written(self, store: CustomThemeStore, tmp_path) -> None:
        """
        ذخیرهٔ کامل توکن‌ها پوستهٔ کاربر را با نسخه‌های بعدی ناسازگار
        می‌کند؛ فقط تفاوت‌ها باید ذخیره شوند.
        """
        key = store.save("من", "gold_dark", {"colors": {"primary": "#123456"}})

        data = json.loads((tmp_path / "themes" / f"{key}.json").read_text(encoding="utf-8"))

        assert data["base"] == "gold_dark"
        assert data["overrides"]["colors"] == {"primary": "#123456"}

    def test_corrupt_file_is_skipped_not_fatal(self, store: CustomThemeStore, tmp_path) -> None:
        """یک فایل خراب نباید جلوی بالا آمدن برنامه را بگیرد."""
        store.save("سالم", "gold_dark", {"colors": {"primary": "#123456"}})
        (tmp_path / "themes" / "broken.json").write_text("{ not json", encoding="utf-8")

        fresh = CustomThemeStore(tmp_path)
        loaded = fresh.load_all()

        assert len(loaded) == 1
        for key in loaded:
            THEME_CATALOG.pop(key, None)

    def test_delete_removes_theme_and_file(self, store: CustomThemeStore, tmp_path) -> None:
        """حذف باید هم از فهرست و هم از دیسک پاک کند."""
        key = store.save("من", "gold_dark", {})

        assert store.delete(key)
        assert key not in THEME_CATALOG
        assert not (tmp_path / "themes" / f"{key}.json").exists()

    def test_builtin_themes_cannot_be_deleted(self, store: CustomThemeStore) -> None:
        """پوستهٔ داخلی برنامه حذف‌شدنی نیست."""
        assert not store.delete("gold_dark")
        assert "gold_dark" in THEME_CATALOG

    def test_persian_name_produces_a_usable_key(self) -> None:
        """نام فارسی باید شناسهٔ معتبر بدهد، نه رشتهٔ خالی."""
        assert slugify("طلایی من").strip()
        assert slugify("!!!") == "theme"

    def test_missing_directory_is_not_an_error(self, tmp_path) -> None:
        """نخستین اجرا هنوز پوشه‌ای ندارد."""
        assert CustomThemeStore(tmp_path / "nowhere").load_all() == []


class TestEditorWidget:
    """ویرایشگر در صفحهٔ تنظیمات."""

    @pytest.fixture()
    def editor(self, qt_application):  # noqa: ARG002 - نیاز به QApplication
        """ویرایشگر بارگذاری‌شده با پوستهٔ طلایی."""
        from ui.widgets.theme_editor import ThemeEditor

        widget = ThemeEditor(Translator("fa"))
        widget.load_theme(get_theme("gold_dark"))
        return widget

    def test_loading_a_theme_emits_nothing(self, qt_application) -> None:  # noqa: ARG002
        """بازکردن ویرایشگر نباید خودش پوسته را عوض کند."""
        from ui.widgets.theme_editor import ThemeEditor

        widget = ThemeEditor(Translator("fa"))
        seen: list[dict] = []
        widget.overrides_changed.connect(seen.append)

        widget.load_theme(get_theme("gold_dark"))

        assert seen == []
        assert widget.overrides == {}

    def test_changing_a_metric_records_an_override(self, editor) -> None:
        """تغییر اسلایدر باید در بازنویسی‌ها ثبت شود."""
        base = get_theme("gold_dark").metrics.radius_md

        editor._metric_widgets["radius_md"].setValue(base + 10)  # noqa: SLF001

        assert editor.overrides["metrics"]["radius_md"] == base + 10

    def test_returning_to_the_base_value_drops_the_override(self, editor) -> None:
        """بازنویسیِ بی‌اثر نباید در پوستهٔ کاربر ذخیره شود."""
        base = get_theme("gold_dark").metrics.radius_md
        slider = editor._metric_widgets["radius_md"]  # noqa: SLF001

        slider.setValue(base + 8)
        slider.setValue(base)

        assert "radius_md" not in editor.overrides.get("metrics", {})

    def test_reset_clears_every_override(self, editor) -> None:
        """دکمهٔ بازگشت باید واقعاً همه‌چیز را پاک کند."""
        editor._metric_widgets["radius_md"].setValue(30)  # noqa: SLF001
        editor._effect_checks["glass"].setChecked(True)  # noqa: SLF001

        editor.clear_overrides()

        assert editor.overrides == {}

    def test_colour_buttons_show_the_theme_colours(self, editor) -> None:
        """دکمه‌های رنگ باید وضعیت واقعی پوسته را نشان دهند."""
        theme = get_theme("gold_dark")

        assert editor._color_buttons["primary"].color == theme.colors.primary  # noqa: SLF001
        assert editor._color_buttons["bg"].color == theme.colors.bg  # noqa: SLF001

    def test_editor_labels_are_translated(self, editor) -> None:
        """هیچ برچسبی نباید نام خام توکن بماند."""
        labels = [label.text() for label, _ in editor._token_labels]  # noqa: SLF001

        assert "primary" not in labels
        assert all(text.strip() for text in labels)

    def test_editor_exists_in_settings_appearance_tab(self, qt_application) -> None:  # noqa: ARG002
        """ویرایشگر باید در زبانهٔ «ظاهر برنامه» باشد."""
        from ui.pages.settings_page import SettingsPage

        page = SettingsPage(Translator("fa"))

        assert page.TAB_KEYS[1] == "settings.appearance.title"
        assert page.theme_editor is not None
        assert page.editor_toggle.text().strip()

    def test_settings_page_relays_token_changes(self, qt_application) -> None:  # noqa: ARG002
        """تغییر در ویرایشگر باید به کنترلر برسد، وگرنه پیش‌نمایشی نیست."""
        from ui.pages.settings_page import SettingsPage

        page = SettingsPage(Translator("fa"))
        page.load_theme_editor(get_theme("gold_dark"))
        seen: list[dict] = []
        page.theme_tokens_changed.connect(seen.append)

        page.theme_editor._metric_widgets["row_height"].setValue(60)  # noqa: SLF001

        assert seen and seen[-1]["metrics"]["row_height"] == 60

    def test_refresh_theme_cards_includes_custom_themes(
        self, qt_application, store: CustomThemeStore  # noqa: ARG002
    ) -> None:
        """پوستهٔ ذخیره‌شده باید در شبکهٔ کارت‌ها ظاهر شود."""
        from ui.pages.settings_page import SettingsPage

        page = SettingsPage(Translator("fa"))
        before = len(page._theme_cards)  # noqa: SLF001

        key = store.save("من", "gold_dark", {"colors": {"primary": "#123456"}})
        page.refresh_theme_cards()

        assert key in page._theme_cards  # noqa: SLF001
        assert len(page._theme_cards) == before + 1  # noqa: SLF001


def test_custom_prefix_cannot_collide_with_builtin_themes() -> None:
    """شناسهٔ سفارشی نباید پوستهٔ داخلی را بازنویسی کند."""
    builtin = {key for key in THEME_CATALOG if not is_custom(key)}

    assert not any(key.startswith(CUSTOM_PREFIX) for key in builtin)
