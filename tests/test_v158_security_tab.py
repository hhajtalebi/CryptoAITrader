"""
آزمون‌های زبانهٔ امنیت (نسخهٔ ۱.۵.۸).

`AuthService` از ابتدا توان تغییر رمز، ویرایش پروفایل و مدیریت نشست را
داشت ولی هیچ رابط کاربری‌ای به آن وصل نبود؛ این آزمون‌ها هم وجود آن
رابط و هم درستی رفتارش را قفل می‌کنند.

یک آزمون هم لغزش برچسب زبانه‌ها را می‌گیرد: فهرست بازترجمه از فهرست
ساخت عقب مانده بود و با تغییر زبان نام زبانه‌ها یک واحد جابه‌جا می‌شد.
"""

from __future__ import annotations

import pytest

from localization import Translator
from ui.pages.settings_page import SettingsPage


# ---------------------------------------------------------------------------
# ۱) ترازِ زبانه‌ها
# ---------------------------------------------------------------------------
class TestTabKeyAlignment:
    """نام زبانه‌ها نباید با تغییر زبان بلغزد."""

    def test_tab_count_matches_keys(self, qt_application):
        """تعداد زبانه‌های ساخته‌شده باید با TAB_KEYS یکی باشد."""
        page = SettingsPage(Translator("fa"))
        assert page.tabs.count() == len(SettingsPage.TAB_KEYS)

    def test_labels_survive_language_switch(self, qt_application):
        """
        پس از تغییر زبان، هر زبانه باید ترجمهٔ کلید خودش را نشان دهد.

        این دقیقاً همان چیزی است که پیش‌تر خراب بود: زبانهٔ «ظاهر برنامه»
        اضافه شده بود ولی به فهرست بازترجمه راه نیافته بود.
        """
        translator = Translator("fa")
        page = SettingsPage(translator)
        translator.set_language("en")
        page.retranslate()
        for index, key in enumerate(SettingsPage.TAB_KEYS):
            assert page.tabs.tabText(index) == translator.tr(key)

    def test_security_tab_exists(self, qt_application):
        """زبانهٔ امنیت باید در فهرست باشد."""
        assert "settings.security.title" in SettingsPage.TAB_KEYS


# ---------------------------------------------------------------------------
# ۲) اجزای زبانهٔ امنیت
# ---------------------------------------------------------------------------
class TestSecurityTabWidgets:
    """ویجت‌ها و سیگنال‌های لازم باید موجود باشند."""

    @pytest.fixture()
    def page(self, qt_application):
        """یک صفحهٔ تنظیمات تازه."""
        return SettingsPage(Translator("fa"))

    def test_widgets_present(self, page):
        """فیلدهای پروفایل، رمز و جدول نشست‌ها باید ساخته شوند."""
        for name in (
            "display_name_input",
            "email_input",
            "profile_save_button",
            "current_password_input",
            "new_password_input",
            "confirm_password_input",
            "password_change_button",
            "sessions_table",
            "revoke_session_button",
            "revoke_others_button",
        ):
            assert hasattr(page, name), f"missing widget: {name}"

    def test_password_fields_are_masked(self, page):
        """هیچ‌یک از فیلدهای رمز نباید متن را آشکار نشان دهد."""
        from PySide6.QtWidgets import QLineEdit

        for field in (
            page.current_password_input,
            page.new_password_input,
            page.confirm_password_input,
        ):
            assert field.echoMode() == QLineEdit.EchoMode.Password

    def test_password_signal_carries_three_values(self, page):
        """سیگنال باید رمز فعلی، جدید و تکرار را با هم بفرستد."""
        captured: list[tuple[str, str, str]] = []
        page.password_change_requested.connect(
            lambda a, b, c: captured.append((a, b, c))
        )
        page.current_password_input.setText("old")
        page.new_password_input.setText("new")
        page.confirm_password_input.setText("new")
        page.password_change_button.click()
        assert captured == [("old", "new", "new")]

    def test_clear_password_inputs(self, page):
        """پس از تغییر موفق، رمزها نباید روی صفحه بمانند."""
        page.current_password_input.setText("a")
        page.new_password_input.setText("b")
        page.confirm_password_input.setText("c")
        page.clear_password_inputs()
        assert page.current_password_input.text() == ""
        assert page.new_password_input.text() == ""
        assert page.confirm_password_input.text() == ""

    def test_sessions_table_fills(self, page):
        """جدول باید سطرهای داده‌شده را نشان دهد و شناسه را نگه دارد."""
        from PySide6.QtCore import Qt

        page.set_sessions(
            [
                {
                    "id": 7,
                    "device": "Windows 11",
                    "created": "۱۴۰۴-۰۶-۲۱",
                    "last_seen": "۱۴۰۴-۰۶-۲۱",
                    "status": "فعال",
                }
            ]
        )
        assert page.sessions_table.rowCount() == 1
        item = page.sessions_table.item(0, 0)
        assert item.text() == "Windows 11"
        assert item.data(Qt.ItemDataRole.UserRole) == 7

    def test_revoke_emits_selected_id(self, page):
        """دکمهٔ پایان نشست باید شناسهٔ سطر انتخاب‌شده را بفرستد."""
        captured: list[int] = []
        page.session_revoke_requested.connect(captured.append)
        page.set_sessions(
            [
                {"id": 3, "device": "A", "created": "", "last_seen": "", "status": ""},
                {"id": 9, "device": "B", "created": "", "last_seen": "", "status": ""},
            ]
        )
        page.sessions_table.setCurrentCell(1, 0)
        page.revoke_session_button.click()
        assert captured == [9]

    def test_revoke_works_in_rtl_layout(self, page, qt_application):
        """
        در چیدمان راست‌به‌چپ هم باید کار کند.

        کشف شده در اجرای کامل مجموعه: وقتی جهت برنامه RTL است،
        `QTableWidget.selectRow()` سطر «جاری» را تنظیم نمی‌کند و
        `currentRow()` منفی می‌ماند، هرچند ردیف انتخاب شده باشد. چون
        زبان پیش‌فرض برنامه فارسی است، تکیه بر `currentRow()` به‌تنهایی
        دکمه را برای کاربر واقعی بی‌اثر می‌کرد.
        """
        from PySide6.QtCore import Qt

        previous = qt_application.layoutDirection()
        try:
            qt_application.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            captured: list[int] = []
            page.session_revoke_requested.connect(captured.append)
            page.set_sessions(
                [
                    {"id": 3, "device": "A", "created": "", "last_seen": "", "status": ""},
                    {"id": 9, "device": "B", "created": "", "last_seen": "", "status": ""},
                ]
            )
            page.sessions_table.setCurrentCell(1, 0)
            page.revoke_session_button.click()
            assert captured == [9]
        finally:
            qt_application.setLayoutDirection(previous)

    def test_revoke_without_selection_warns(self, page):
        """بدون انتخاب سطر باید هشدار بدهد، نه اینکه بی‌صدا هیچ نکند."""
        captured: list[int] = []
        blocked: list[bool] = []
        page.session_revoke_requested.connect(captured.append)
        page.session_revoke_blocked.connect(lambda: blocked.append(True))
        page.set_sessions([])
        page.revoke_session_button.click()
        assert captured == []
        assert blocked == [True]

    def test_guest_mode_disables_controls(self, page):
        """مهمان حساب ندارد، پس کنترل‌های امنیتی باید خاموش باشند."""
        page.set_security_enabled(False)
        assert not page.password_change_button.isEnabled()
        assert not page.profile_save_button.isEnabled()
        assert not page.display_name_input.isEnabled()
        page.set_security_enabled(True)
        assert page.password_change_button.isEnabled()
        assert page.display_name_input.isEnabled()


# ---------------------------------------------------------------------------
# ۳) رفتار کنترلر
# ---------------------------------------------------------------------------
class TestSecurityController:
    """منطق تطابق رمز و قالب‌بندی نشست در کنترلر."""

    def test_password_mismatch_never_reaches_service(self, qt_application):
        """
        اگر تکرار رمز نخواند، نباید اصلاً به سرویس برسد.

        این بررسی در لایهٔ رابط انجام می‌شود تا کاربر فوری بازخورد بگیرد.
        """
        from ui.controllers.main_controller import MainController

        calls: list[tuple[str, str]] = []

        class FakeAuth:
            is_authenticated = True

            def change_password(self, current, new):
                calls.append((current, new))
                return True, ""

        class FakeApp:
            auth = FakeAuth()

        toasts: list[tuple[str, str]] = []
        controller = MainController.__new__(MainController)
        controller.app = FakeApp()
        controller.tr_ = Translator("fa")
        controller._toast = lambda message, level="info": toasts.append((message, level))
        controller.refresh_security = lambda: None

        MainController.change_password(controller, "old", "new1234A", "typo")
        assert calls == []
        assert toasts and toasts[-1][1] == "warning"

    def test_expired_detection_handles_bad_input(self):
        """مقدار نامعتبر نباید استثنا بدهد."""
        from ui.controllers.main_controller import MainController

        assert MainController._is_expired(None) is False
        assert MainController._is_expired("not-a-date") is False

    def test_expired_detection_flags_past(self):
        """زمان گذشته باید منقضی شمرده شود."""
        from datetime import datetime, timedelta

        from ui.controllers.main_controller import MainController

        assert MainController._is_expired(datetime.now() - timedelta(days=1)) is True
        assert MainController._is_expired(datetime.now() + timedelta(days=1)) is False


# ---------------------------------------------------------------------------
# ۴) ترجمه‌ها
# ---------------------------------------------------------------------------
class TestSecurityTranslations:
    """کلیدهای تازه باید در هر دو زبان موجود باشند."""

    @pytest.mark.parametrize("language", ["fa", "en"])
    @pytest.mark.parametrize(
        "key",
        [
            "settings.security.title",
            "settings.security.profile",
            "settings.security.display_name",
            "settings.security.email",
            "settings.security.save_profile",
            "settings.security.profile_saved",
            "settings.security.confirm_password",
            "settings.security.password_hint",
            "settings.security.password_mismatch",
            "settings.security.sessions",
            "settings.security.status",
            "settings.security.status_active",
            "settings.security.status_revoked",
            "settings.security.status_expired",
            "settings.security.session_revoked",
            "settings.security.others_revoked",
            "settings.security.note",
            "settings.security.guest_note",
        ],
    )
    def test_key_resolves(self, language, key):
        """کلید نباید به خودش برگردد (یعنی ترجمه‌نشده باشد)."""
        translator = Translator(language)
        value = translator.tr(key)
        assert value and value != key

    def test_others_revoked_has_placeholder(self):
        """پیام باید جای شمارش داشته باشد."""
        for language in ("fa", "en"):
            assert "{count}" in Translator(language).tr("settings.security.others_revoked")


# ---------------------------------------------------------------------------
# ۵) انتخاب سطر در چیدمان راست‌به‌چپ
# ---------------------------------------------------------------------------
class TestRtlRowSelection:
    """
    باگ کشف‌شده هنگام ساخت زبانهٔ امنیت.

    وقتی جهت برنامه راست‌به‌چپ است (یعنی حالت پیش‌فرض فارسی)،
    `QTableWidget.selectRow()` سطر «جاری» را تنظیم نمی‌کند و
    `currentRow()` منفی می‌ماند. هر کدی که فقط به `currentRow()` تکیه
    کند، در فارسی بی‌صدا از کار می‌افتد — دقیقاً بلایی که سر دکمه‌های
    «آزمایش اتصال»، «فعال‌سازی» و «حذف» حساب صرافی آمده بود.
    """

    ACCOUNTS = [
        {
            "id": 11,
            "exchange": "lbank",
            "label": "A",
            "api_key_masked": "x",
            "is_default": True,
            "status": "ok",
        },
        {
            "id": 22,
            "exchange": "lbank",
            "label": "B",
            "api_key_masked": "y",
            "is_default": False,
            "status": "ok",
        },
    ]

    @pytest.fixture()
    def rtl(self, qt_application):
        """اجرای آزمون در چیدمان راست‌به‌چپ و بازگرداندن حالت قبلی."""
        from PySide6.QtCore import Qt

        previous = qt_application.layoutDirection()
        qt_application.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        yield qt_application
        qt_application.setLayoutDirection(previous)

    def test_default_account_is_selected_in_rtl(self, rtl):
        """
        حساب پیش‌فرض باید در فارسی هم واقعاً انتخاب شده باشد.

        پیش از اصلاح، این مقدار صفر برمی‌گشت و کاربر فارسی‌زبان دکمه را
        می‌زد بی‌آنکه هیچ اتفاقی بیفتد.
        """
        page = SettingsPage(Translator("fa"))
        page.set_accounts(self.ACCOUNTS)
        assert page.selected_account_id() == 11

    def test_account_buttons_fire_in_rtl(self, rtl):
        """هر سه دکمهٔ حساب باید در چیدمان فارسی سیگنال بدهند."""
        page = SettingsPage(Translator("fa"))
        page.set_accounts(self.ACCOUNTS)
        activated: list[int] = []
        tested: list[int] = []
        removed: list[int] = []
        page.account_activate_requested.connect(activated.append)
        page.account_test_requested.connect(tested.append)
        page.account_remove_requested.connect(removed.append)
        page.account_activate_button.click()
        page.account_test_button.click()
        page.account_remove_button.click()
        assert activated == [11]
        assert tested == [11]
        assert removed == [11]

    def test_markets_selected_symbol_in_rtl(self, rtl):
        """صفحهٔ بازارها هم نباید در فارسی نماد را گم کند."""
        from ui.pages.markets_page import MarketsPage

        page = MarketsPage(Translator("fa"))
        page.set_rows(
            [
                {
                    "symbol": "BTC/USDT",
                    "price": 1.0,
                    "change_percent": 0.0,
                    "volume": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                }
            ]
        )
        page.table.setCurrentCell(0, 0)
        assert page.selected_symbol() == "BTC/USDT"
