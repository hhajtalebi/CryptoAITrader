"""
آزمون‌های نسخهٔ ۱.۶.۰ — پیام‌های خطا، قالب گزارش و بستن معامله.

باگ اصلی که اینجا قفل می‌شود: کلاس‌های استثنا کلید ترجمهٔ خود را با
فضای‌نام مفرد `error.*` اعلام می‌کردند در حالی که فایل ترجمه
`errors.json` است. چون `_on_error` فقط وقتی ترجمه را نشان می‌دهد که
`has()` درست باشد، **هیچ‌کدام از پیام‌های کاربرپسند هرگز دیده نمی‌شدند**
و کاربر متن خام انگلیسی استثنا را می‌دید.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from localization import Translator

ROOT = Path(__file__).resolve().parents[1]
ERRORS_SOURCE = ROOT / "app" / "exceptions" / "errors.py"


def _declared_keys() -> list[str]:
    """کلیدهای ترجمه‌ای که کلاس‌های استثنا اعلام می‌کنند."""
    source = ERRORS_SOURCE.read_text(encoding="utf-8")
    return sorted(set(re.findall(r'default_user_key = "([^"]+)"', source)))


# ---------------------------------------------------------------------------
# ۱) کلیدهای استثنا
# ---------------------------------------------------------------------------
class TestExceptionUserKeys:
    """هر استثنا باید پیام کاربرپسند واقعی داشته باشد."""

    def test_at_least_one_key_declared(self):
        """اگر الگوی استخراج بشکند، بقیهٔ آزمون‌ها بی‌معنا می‌شوند."""
        assert len(_declared_keys()) >= 15

    def test_no_singular_namespace_remains(self):
        """
        هیچ کلیدی نباید با `error.` (مفرد) شروع شود.

        فضای‌نام واقعی `errors` است؛ مفرد یعنی ترجمه هرگز پیدا نمی‌شود.
        """
        offenders = [k for k in _declared_keys() if k.startswith("error.")]
        assert offenders == []

    @pytest.mark.parametrize("language", ["fa", "en"])
    def test_every_key_resolves(self, language):
        """هر کلید اعلام‌شده باید در هر دو زبان ترجمه داشته باشد."""
        translator = Translator(language)
        missing = [key for key in _declared_keys() if not translator.has(key)]
        assert missing == [], f"untranslated in {language}: {missing}"

    @pytest.mark.parametrize("language", ["fa", "en"])
    def test_translations_are_not_echoes(self, language):
        """ترجمه نباید خودِ کلید باشد."""
        translator = Translator(language)
        for key in _declared_keys():
            assert translator.tr(key) != key

    def test_real_exceptions_produce_persian_text(self):
        """
        نمونهٔ واقعی استثنا باید متن فارسی بدهد، نه کلید خام.

        این همان چیزی است که کاربر در نوار وضعیت می‌بیند.
        """
        from app.exceptions.errors import (
            AIError,
            AuthenticationError,
            DatabaseError,
            NetworkError,
        )

        translator = Translator("fa")
        for exception in (
            NetworkError("connection refused"),
            DatabaseError("database is locked"),
            AuthenticationError("invalid api key"),
            AIError("provider timeout"),
        ):
            text = translator.tr(exception.user_key)
            assert text != exception.user_key
            # متن فارسی باید دست‌کم یک حرف فارسی داشته باشد
            assert re.search(r"[\u0600-\u06FF]", text)

    def test_controller_prefers_the_user_key(self):
        """
        `_on_error` باید پیام ترجمه‌شده را جایگزین متن خام کند.

        بدون این، پیام فنی انگلیسی به کاربر نشان داده می‌شود.
        """
        from ui.controllers.main_controller import MainController
        from app.exceptions.errors import NetworkError

        shown: list[str] = []
        controller = MainController.__new__(MainController)
        controller.tr_ = Translator("fa")
        controller.status = shown.append

        MainController._on_error(
            controller, "Connection refused by host", NetworkError("boom")
        )
        assert shown
        assert "Connection refused" not in shown[0]
        assert re.search(r"[\u0600-\u06FF]", shown[0])


# ---------------------------------------------------------------------------
# ۲) قالب خروجی گزارش
# ---------------------------------------------------------------------------
class TestReportFormatSelection:
    """کد قالب نباید به متن نمایشی گره بخورد."""

    @pytest.fixture()
    def page(self, qt_application):
        """صفحهٔ گزارش‌ها با مترجم فارسی."""
        from ui.pages.reports_page import ReportsPage

        return ReportsPage(Translator("fa"))

    def test_default_is_csv(self, page):
        """قالب پیش‌فرض باید کد معتبر بدهد."""
        assert page.selected_format() == "csv"

    def test_every_entry_maps_to_a_code(self, page):
        """هر گزینه باید کد صادرکنندهٔ درست بدهد."""
        codes = []
        for index in range(page.format_combo.count()):
            page.format_combo.setCurrentIndex(index)
            codes.append(page.selected_format())
        assert codes == ["csv", "xlsx", "json", "pdf", "html"]

    def test_selection_survives_language_switch(self, qt_application):
        """
        تغییر زبان نباید انتخاب کاربر را خراب کند.

        پیش‌تر کد قالب از روی متن نمایشی خوانده می‌شد؛ ترجمهٔ گزینه‌ها
        باعث `KeyError` می‌شد.
        """
        from ui.pages.reports_page import ReportsPage

        translator = Translator("fa")
        page = ReportsPage(translator)
        page.format_combo.setCurrentIndex(1)
        assert page.selected_format() == "xlsx"
        translator.set_language("en")
        page.retranslate()
        assert page.selected_format() == "xlsx"

    @pytest.mark.parametrize("language", ["fa", "en"])
    def test_format_labels_translate(self, language):
        """برچسب‌ها باید از فایل ترجمه بیایند."""
        translator = Translator(language)
        for _code, key in __import__(
            "ui.pages.reports_page", fromlist=["ReportsPage"]
        ).ReportsPage.EXPORT_FORMATS:
            assert translator.has(key)


# ---------------------------------------------------------------------------
# ۳) بستن معامله
# ---------------------------------------------------------------------------
class TestCloseTradeButton:
    """
    بستن معامله پیش‌تر فقط با دوبار کلیک ممکن بود و هیچ نشانه‌ای روی
    صفحه نداشت.
    """

    ROWS = [
        {
            "id": 1,
            "symbol": "BTC/USDT",
            "side": "long",
            "status": "open",
            "pnl": 5.0,
            "date_text": "x",
            "pnl_text": "+۵",
            "pnl_percent_text": "+۱٪",
        },
        {
            "id": 2,
            "symbol": "ETH/USDT",
            "side": "short",
            "status": "closed",
            "pnl": -2.0,
            "date_text": "y",
            "pnl_text": "-۲",
            "pnl_percent_text": "-۱٪",
        },
    ]

    @pytest.fixture()
    def page(self, qt_application):
        """صفحهٔ معاملات با دو سطر نمونه."""
        from ui.pages.trades_page import TradesPage

        page = TradesPage(Translator("fa"))
        page.set_trades(list(self.ROWS), page=1, pages=1)
        return page

    def test_button_exists(self, page):
        """دکمهٔ صریح باید روی صفحه باشد."""
        assert hasattr(page, "close_trade_button")
        assert page.close_trade_button.text()

    def test_open_trade_closes(self, page):
        """انتخاب معاملهٔ باز باید درخواست بستن بفرستد."""
        fired: list[int] = []
        page.close_requested.connect(fired.append)
        page.table.setCurrentCell(0, 0)
        page.close_trade_button.click()
        assert fired == [1]

    def test_closed_trade_is_rejected(self, page):
        """معاملهٔ بسته دوباره بسته نمی‌شود."""
        fired: list[int] = []
        blocked: list[bool] = []
        page.close_requested.connect(fired.append)
        page.close_blocked.connect(lambda: blocked.append(True))
        page.table.setCurrentCell(1, 0)
        page.close_trade_button.click()
        assert fired == []
        assert blocked == [True]

    def test_no_selection_warns(self, page):
        """بدون انتخاب باید هشدار بدهد، نه سکوت."""
        blocked: list[bool] = []
        page.close_blocked.connect(lambda: blocked.append(True))
        page.table.clearSelection()
        page.table.setCurrentCell(-1, -1)
        page.close_trade_button.click()
        assert blocked == [True]

    def test_works_in_rtl(self, page, qt_application):
        """در چیدمان فارسی هم باید کار کند."""
        from PySide6.QtCore import Qt

        previous = qt_application.layoutDirection()
        try:
            qt_application.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            fired: list[int] = []
            page.close_requested.connect(fired.append)
            page.table.setCurrentCell(0, 0)
            page.close_trade_button.click()
            assert fired == [1]
        finally:
            qt_application.setLayoutDirection(previous)
