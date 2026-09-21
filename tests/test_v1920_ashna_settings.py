"""
آزمون‌های دسترسی کاربر به «آشنا هوش مصنوعی» از صفحهٔ تنظیمات.

کاربر گزارش داد «تنظیمات آشنا در تنظیمات نیست و نمی‌شود استفاده کرد».
بررسی نشان داد سرویس و کلاینتش سر جایشان بودند ولی نشانی گرفتن کلید
هیچ‌جا نمایش داده نمی‌شد. این آزمون‌ها کل مسیر «انتخاب سرویس ← وارد
کردن کلید ← رسیدن کلید به لایهٔ ذخیره‌سازی» را قفل می‌کنند تا دوباره
بی‌سروصدا نشکند.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from ai.providers.catalog import PROVIDER_PRESETS, get_preset
from localization import Translator
from ui.pages.settings_page import SettingsPage

AI_TAB_INDEX = 3


@pytest.fixture(scope="module")
def qt_application() -> QApplication:
    """یک نمونهٔ QApplication برای کل این فایل."""
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def page(qt_application: QApplication) -> SettingsPage:  # noqa: ARG001
    """
    صفحهٔ تنظیمات روی زبانهٔ «هوش مصنوعی».

    بدون `show()` و بدون فعال کردن زبانه، ویجت‌ها از نظر Qt نامرئی‌اند
    و `isVisible()` جواب گمراه‌کننده می‌دهد.
    """
    widget = SettingsPage(Translator("fa"))
    widget.resize(1200, 900)
    widget.show()
    widget.tabs.setCurrentIndex(AI_TAB_INDEX)
    QApplication.processEvents()
    return widget


class TestAshnaPreset:
    """خودِ تعریف سرویس در کاتالوگ."""

    def test_ashna_is_registered(self) -> None:
        """سرویس باید در کاتالوگ باشد وگرنه در فهرست تنظیمات نمی‌آید."""
        assert get_preset("ashna") is not None

    def test_base_url_keeps_the_v1_api_suffix(self) -> None:
        """
        مسیر پایه `/v1/api` است نه `/v1`.

        این را با درخواست واقعی سنجیدیم: هر دو پاسخ می‌دهند ولی قالب
        خطاشان فرق دارد؛ `/v1/api` همان قالب سازگار با OpenAI است که
        کلاینت ما انتظار دارد.
        """
        assert get_preset("ashna").base_url == "https://api.ashna.ai/v1/api"

    def test_ashna_asks_for_a_key(self) -> None:
        """بدون کلید سرویس ۴۰۱ می‌دهد، پس کادر کلید باید فعال باشد."""
        preset = get_preset("ashna")
        assert preset.requires_key is True
        assert preset.key_field_enabled is True

    def test_signup_url_points_at_the_key_page(self) -> None:
        """نشانی باید مستقیم به صفحهٔ کلید برود، نه صفحهٔ اصلی سایت."""
        assert get_preset("ashna").signup_url == "https://app.ashna.ai/account?tab=api"


class TestProviderDropdown:
    """دیده‌شدن سرویس در فهرست کشویی تنظیمات."""

    def test_ashna_appears_in_the_dropdown(self, page: SettingsPage) -> None:
        """شکایت اصلی کاربر دقیقاً همین بود."""
        assert page.ai_provider_combo.findData("ashna") >= 0

    def test_dropdown_lists_every_catalog_preset(self, page: SettingsPage) -> None:
        """هیچ سرویسی نباید از قلم بیفتد."""
        shown = {
            page.ai_provider_combo.itemData(i)
            for i in range(page.ai_provider_combo.count())
        }
        assert {preset.key for preset in PROVIDER_PRESETS} <= shown

    def test_display_name_is_findable_in_persian(self, page: SettingsPage) -> None:
        """کاربر فارسی‌زبان باید بتواند «آشنا» را ببیند."""
        index = page.ai_provider_combo.findData("ashna")
        assert "آشنا" in page.ai_provider_combo.itemText(index)


class TestSelectingAshna:
    """رفتار صفحه پس از انتخاب آشنا."""

    def _select(self, page: SettingsPage) -> None:
        """انتخاب آشنا و پردازش رویدادها."""
        combo = page.ai_provider_combo
        combo.setCurrentIndex(combo.findData("ashna"))
        QApplication.processEvents()

    def test_key_field_is_visible_and_enabled(self, page: SettingsPage) -> None:
        """اگر کادر کلید نامرئی یا غیرفعال بود، کاربر واقعاً گیر می‌کرد."""
        self._select(page)
        assert page.ai_key_input.isVisible() is True
        assert page.ai_key_input.isEnabled() is True

    def test_key_field_hides_what_is_typed(self, page: SettingsPage) -> None:
        """کلید نباید روی صفحه خوانده شود."""
        self._select(page)
        assert page.ai_key_input.echoMode().name == "Password"

    def test_base_url_is_filled_automatically(self, page: SettingsPage) -> None:
        """کاربر نباید مجبور باشد نشانی را از مستندات پیدا کند."""
        self._select(page)
        assert page.ai_base_url_input.text() == "https://api.ashna.ai/v1/api"

    def test_suggested_models_are_offered(self, page: SettingsPage) -> None:
        """بدون فهرست مدل، کاربر نمی‌داند چه بنویسد."""
        self._select(page)
        items = [page.ai_model_combo.itemText(i) for i in range(page.ai_model_combo.count())]
        assert any("ashna-x1" in text for text in items)

    def test_hint_shows_where_to_get_the_key(self, page: SettingsPage) -> None:
        """
        همان چیزی که واقعاً کم بود.

        `signup_url` برای هر ۱۶ سرویس ذخیره شده بود ولی هرگز نمایش
        داده نمی‌شد.
        """
        self._select(page)
        assert "https://app.ashna.ai/account?tab=api" in page.ai_hint.text()

    def test_every_provider_with_a_signup_url_shows_it(self, page: SettingsPage) -> None:
        """این راهنما مخصوص آشنا نیست؛ برای همهٔ سرویس‌ها باید بیاید."""
        combo = page.ai_provider_combo
        for preset in PROVIDER_PRESETS:
            if not preset.signup_url:
                continue
            combo.setCurrentIndex(combo.findData(preset.key))
            QApplication.processEvents()
            assert preset.signup_url in page.ai_hint.text(), preset.key


class TestKeyReachesStorage:
    """مسیر کلید از کادر تا لایهٔ رمزگذاری‌شده."""

    def test_typed_key_is_collected_under_the_provider_name(
        self, page: SettingsPage
    ) -> None:
        """
        کلید باید با نام خود سرویس ذخیره شود.

        اینطوری کاربر می‌تواند چند سرویس را هم‌زمان پیکربندی کند و با
        تعویض، کلید درست خودکار بیاید.
        """
        combo = page.ai_provider_combo
        combo.setCurrentIndex(combo.findData("ashna"))
        QApplication.processEvents()
        page.ai_key_input.setText("ashna-secret-key")

        assert page.collect_secrets().get("ai.ashna.api_key") == "ashna-secret-key"

    def test_provider_choice_is_collected(self, page: SettingsPage) -> None:
        """انتخاب سرویس باید در تنظیمات ذخیره شود."""
        combo = page.ai_provider_combo
        combo.setCurrentIndex(combo.findData("ashna"))
        QApplication.processEvents()

        assert page.collect_values().get("ai.provider") == "ashna"

    def test_key_is_not_collected_as_a_plain_setting(self, page: SettingsPage) -> None:
        """
        کلید محرمانه است و نباید در جدول تنظیمات ساده بنشیند.

        قاعدهٔ همیشگی پروژه: رمزها فقط در انبار رمزگذاری‌شده.
        """
        combo = page.ai_provider_combo
        combo.setCurrentIndex(combo.findData("ashna"))
        QApplication.processEvents()
        page.ai_key_input.setText("ashna-secret-key")

        values = page.collect_values()
        assert not any("api_key" in key for key in values)
        assert "ashna-secret-key" not in str(values)
