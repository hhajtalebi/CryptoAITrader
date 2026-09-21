"""
آزمون‌های رفع سه ایراد گزارش‌شدهٔ کاربر (نسخه ۱٫۷٫۲).

کاربر سه چیز گزارش کرد:

۱. «هوش مصنوعی در چت درست است ولی در سیگنال اصلاً وصل نمی‌شود و تحلیل
   نمی‌کند.» — علت: مهلت تحلیل سیگنال ۴۵ ثانیه بود در حالی که مهلت چت
   ۱۲۰ ثانیه است. مدل محلی در نخستین درخواست وزنه‌ها را بارگذاری
   می‌کند و همین از ۴۵ ثانیه بیشتر طول می‌کشد، پس مسیر سیگنال همیشه
   تسلیم می‌شد و **بی‌صدا** متن قالبی برمی‌گرداند.

۲. «دکمه‌های تحلیل در سیگنال‌های پویشی خراب است، نه ظاهر مناسبی دارد
   نه کار می‌کند.» — علت: پدینگ خانهٔ جدول در شیوه‌نامه، دکمه را در
   ردیف ۳۰ پیکسلی به ۱۲ پیکسل له می‌کرد.

۳. «روی نماد کلیک می‌کنی جزئیات باز نمی‌شود.» — علت: جدول پویش هیچ
   اتصال کلیکی نداشت.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from app.config.defaults import DEFAULT_SETTINGS, SettingKey
from app.config.settings_service import SettingsService
from ui.pages.signals_page import SignalsPage


# ------------------------------------------------------------ ۱) مهلت زمانی


def test_signal_ai_timeout_is_not_shorter_than_the_chat_timeout() -> None:
    """
    مهم‌ترین آزمون این فایل.

    چت و تحلیل سیگنال به یک سرویس یکسان وصل می‌شوند؛ اگر مهلت سیگنال
    کوتاه‌تر باشد، کاربر دقیقاً همان چیزی را می‌بیند که گزارش کرد:
    «در چت کار می‌کند ولی در سیگنال نه».
    """
    signal_timeout = int(DEFAULT_SETTINGS[SettingKey.SIGNAL_AI_TIMEOUT.value])
    chat_timeout = int(DEFAULT_SETTINGS[SettingKey.AI_CHAT_TIMEOUT.value])
    assert signal_timeout >= chat_timeout


def test_signal_ai_timeout_allows_a_local_model_to_warm_up() -> None:
    """
    بارگذاری اولیهٔ یک مدل محلی روی دستگاه معمولی بیش از یک دقیقه طول
    می‌کشد؛ مهلت باید دست‌کم این‌قدر باشد.
    """
    assert int(DEFAULT_SETTINGS[SettingKey.SIGNAL_AI_TIMEOUT.value]) >= 90


class _FakeRepository:
    """انبارهٔ تنظیمات در حافظه برای آزمون مهاجرت."""

    def __init__(self, stored: dict[str, Any]) -> None:
        self.stored = dict(stored)
        self.writes: list[tuple[str, Any]] = []

    def ensure_defaults(self, defaults: dict[str, Any], categories: Any) -> int:
        for key, value in defaults.items():
            self.stored.setdefault(key, value)
        return 0

    def get_all(self) -> dict[str, Any]:
        return dict(self.stored)

    def get(self, key: str, default: Any = None) -> Any:
        return self.stored.get(key, default)

    def set(self, key: str, value: Any, **kwargs: Any) -> None:
        self.stored[key] = value
        self.writes.append((key, value))


def test_an_existing_install_gets_the_raised_timeout() -> None:
    """
    تغییر پیش‌فرض فقط روی نصب تازه اثر دارد.

    کسی که ارتقا می‌دهد مقدار ۴۵ را در پایگاه داده دارد و بدون مهاجرت
    همچنان باگ را می‌بیند.
    """
    key = SettingKey.SIGNAL_AI_TIMEOUT.value
    repository = _FakeRepository({key: 45})
    service = SettingsService(repository)
    service.initialize_defaults()

    assert int(repository.stored[key]) == 120


def test_a_value_the_user_chose_is_never_overwritten() -> None:
    """
    قاعدهٔ سخت پروژه: تنظیمات کاربر بازنویسی نمی‌شود.

    اگر کاربر عمداً ۳۰ ثانیه گذاشته باشد، باید ۳۰ بماند — حتی با آنکه
    از پیش‌فرض معیوب قدیمی هم کمتر است.
    """
    key = SettingKey.SIGNAL_AI_TIMEOUT.value
    repository = _FakeRepository({key: 30})
    service = SettingsService(repository)
    service.initialize_defaults()

    assert int(repository.stored[key]) == 30
    assert repository.writes == []


def test_a_raised_value_is_left_alone() -> None:
    """مقداری که از پیش درست است نباید دوباره نوشته شود."""
    key = SettingKey.SIGNAL_AI_TIMEOUT.value
    repository = _FakeRepository({key: 200})
    service = SettingsService(repository)
    service.initialize_defaults()

    assert int(repository.stored[key]) == 200
    assert repository.writes == []


# --------------------------------------------------- ۲) دکمهٔ ستون تحلیل


@pytest.fixture
def signals_page(qt_application: Any) -> Any:
    """
    صفحهٔ سیگنال با پوستهٔ فعال، بدون ساخت کل برنامه.

    شیوه‌نامه در پایان پاک می‌شود.

    چرا مهم است؟ `QApplication` بین **همهٔ** آزمون‌های یک فرایند مشترک
    است. این فیکسچر شیوه‌نامهٔ سراسری می‌گذاشت و برنمی‌داشت؛ پدینگ آن
    به ارتفاع حداقلی هر صفحه‌ای که بعداً ساخته می‌شد اضافه می‌کرد و
    `test_v193_page_scrolling` را در اجرای کامل مجموعه می‌شکست — در
    حالی که همان آزمون‌ها تنها اجرا می‌شدند و سبز بودند. نشتِ حالت
    سراسری، آزمون را به ترتیب اجرا وابسته می‌کند و همین، عیب‌یابی را
    ساعت‌ها طولانی می‌کند.
    """
    from localization.translator import Translator
    from ui.pages.signals_page import SignalsPage
    from ui.themes.catalog import THEME_CATALOG
    from ui.themes.stylesheet import build_stylesheet

    previous = qt_application.styleSheet()
    qt_application.setStyleSheet(build_stylesheet(THEME_CATALOG["glass_dark"]))
    page = SignalsPage(Translator("fa"))
    page.apply_theme(THEME_CATALOG["glass_dark"])
    page.resize(1250, 900)
    # ویجت نمایش‌داده‌نشده هندسهٔ واقعی ندارد و آزمون اندازه بی‌معنا می‌شود
    page.show()
    try:
        yield page
    finally:
        page.close()
        qt_application.setStyleSheet(previous)


SCAN_ROWS = [
    {"symbol": "BTC/USDT", "direction": "LONG", "confidence": 72,
     "risk_reward": 2.6, "leverage": 3, "stop_loss": 75000, "entry_min": 77000},
    {"symbol": "ETH/USDT", "direction": "SHORT", "confidence": 55,
     "risk_reward": 1.8, "leverage": 5, "stop_loss": 3300, "entry_min": 3200},
]


def test_the_analyse_button_is_tall_enough_to_read(signals_page: Any) -> None:
    """
    دکمه نباید زیر پدینگِ خانه له شود.

    پیش از این ارتفاع واقعی دکمه ۱۲ پیکسل بود در حالی که دست‌کم ۲۸
    پیکسل لازم دارد؛ ستون «تحلیل» عملاً خالی به نظر می‌رسید.
    """
    signals_page.set_scan_results(SCAN_ROWS)
    button = signals_page.scan_table.cellWidget(0, SignalsPage.SCAN_COL_ACTION)

    assert button is not None
    assert button.height() >= button.sizeHint().height()
    assert button.height() >= 24


def test_the_analyse_button_shows_its_full_label(signals_page: Any) -> None:
    """عرض ستون باید متن کامل دکمه را جا بدهد."""
    signals_page.set_scan_results(SCAN_ROWS)
    button = signals_page.scan_table.cellWidget(0, SignalsPage.SCAN_COL_ACTION)

    assert button.text().strip() != ""
    assert button.width() >= button.sizeHint().width()


def test_the_analyse_button_emits_its_symbol(signals_page: Any) -> None:
    """کلیک روی دکمه باید نماد همان ردیف را بفرستد."""
    signals_page.set_scan_results(SCAN_ROWS)
    fired: list[str] = []
    signals_page.scan_ai_requested.connect(fired.append)

    signals_page.scan_table.cellWidget(1, SignalsPage.SCAN_COL_ACTION).click()
    assert fired == ["ETH/USDT"]


def test_the_history_table_button_is_also_tall_enough(signals_page: Any) -> None:
    """
    جدول سابقه همان ایراد را داشت.

    رفعِ فقط یکی از دو جدول، نیمی از مشکل را باقی می‌گذاشت.
    """
    signals_page.set_history([
        {"id": 1, "symbol": "BTC/USDT", "direction": "LONG", "confidence": 70,
         "risk_reward": 2.0, "leverage": 3, "created_at": "2026-09-14 10:00"},
    ])
    button = signals_page.history_table.cellWidget(0, SignalsPage.HISTORY_COL_ACTION)

    assert button is not None
    assert button.height() >= button.sizeHint().height()


def test_the_button_column_helper_sets_both_width_and_row_height(
    qt_application: Any,
) -> None:
    """
    کمک‌تابع باید هر دو کار را بکند.

    فراموش‌کردن هرکدام، ستون دکمه را دوباره خراب می‌کند: بدون عرض
    ثابت بریده می‌شود و بدون ارتفاع ردیف، له.
    """
    from PySide6.QtWidgets import QHeaderView, QTableWidget

    from ui.widgets.common import BUTTON_ROW_HEIGHT, configure_button_column

    table = QTableWidget(2, 3)
    configure_button_column(table, 2)

    assert table.columnWidth(2) >= 120
    assert table.verticalHeader().defaultSectionSize() == BUTTON_ROW_HEIGHT
    assert (
        table.horizontalHeader().sectionResizeMode(2)
        == QHeaderView.ResizeMode.Fixed
    )


def test_the_helper_ignores_a_column_that_does_not_exist(
    qt_application: Any,
) -> None:
    """شمارهٔ ستون نامعتبر نباید استثنا بدهد."""
    from PySide6.QtWidgets import QTableWidget

    from ui.widgets.common import configure_button_column

    table = QTableWidget(1, 2)
    configure_button_column(table, 9)  # نباید پرتاب کند


# ------------------------------------------------- ۳) کلیک روی ردیف پویش


def test_clicking_a_scanned_symbol_asks_for_details(signals_page: Any) -> None:
    """
    کلیک روی نماد باید جزئیات بخواهد.

    جدول پویش هیچ اتصال کلیکی نداشت، پس کلیک کاربر بی‌اثر بود.
    """
    signals_page.set_scan_results(SCAN_ROWS)
    asked: list[str] = []
    signals_page.scan_detail_requested.connect(asked.append)

    signals_page.scan_table.cellClicked.emit(0, 1)
    assert asked == ["BTC/USDT"]


def test_double_clicking_also_opens_details(signals_page: Any) -> None:
    """جدول سابقه با دوکلیک باز می‌شود؛ کاربر همان را انتظار دارد."""
    signals_page.set_scan_results(SCAN_ROWS)
    asked: list[str] = []
    signals_page.scan_detail_requested.connect(asked.append)

    signals_page.scan_table.cellDoubleClicked.emit(1, 2)
    assert asked == ["ETH/USDT"]


def test_clicking_the_button_column_does_not_also_open_details(
    signals_page: Any,
) -> None:
    """
    ستون دکمه استثناست.

    وگرنه یک کلیک هم تحلیل می‌خواست و هم پنجرهٔ جزئیات باز می‌کرد.
    """
    signals_page.set_scan_results(SCAN_ROWS)
    asked: list[str] = []
    signals_page.scan_detail_requested.connect(asked.append)

    signals_page.scan_table.cellClicked.emit(0, SignalsPage.SCAN_COL_ACTION)
    assert asked == []


def test_clicking_an_empty_row_is_harmless(signals_page: Any) -> None:
    """کلیک روی ردیفی که آیتم ندارد نباید استثنا بدهد."""
    asked: list[str] = []
    signals_page.scan_detail_requested.connect(asked.append)

    signals_page.scan_table.setRowCount(1)
    signals_page.scan_table.cellClicked.emit(0, 1)
    assert asked == []


def test_the_controller_connects_the_detail_signal() -> None:
    """سیگنال بدون اتصال، همان باگ قبلی است با ظاهر تازه."""
    from ui.controllers.main_controller import MainController

    body = inspect.getsource(MainController._connect)
    assert "scan_detail_requested.connect" in body


def test_the_controller_can_open_a_scanned_signal() -> None:
    """متد مقصد باید واقعاً وجود داشته باشد."""
    from ui.controllers.main_controller import MainController

    assert callable(MainController.show_scanned_signal_detail)


# ------------------------------------------- صداقت دربارهٔ منبع تحلیل


def test_the_user_is_told_when_the_engine_wrote_the_analysis() -> None:
    """
    ادعای «تحلیل هوشمند انجام شد» وقتی هوش مصنوعی شکست خورده گمراه‌کننده
    است.

    `NarrativeWriter` در شکست بی‌صدا متن قالبی برمی‌گرداند؛ رابط کاربری
    باید منبع را بررسی کند نه اینکه موفقیت را فرض بگیرد.
    """
    from ui.controllers.main_controller import MainController

    body = inspect.getsource(MainController.analyze_scanned_symbol)
    assert "analysis_source" in body
    assert "scan_ai_fallback" in body


def test_a_disabled_ai_is_reported_before_any_work() -> None:
    """وقتی هوش مصنوعی خاموش است باید همان اول گفته شود."""
    from ui.controllers.main_controller import MainController

    body = inspect.getsource(MainController.analyze_scanned_symbol)
    assert "ai_enabled" in body
    assert "ai_disabled_hint" in body


@pytest.mark.parametrize("language", ["fa", "en"])
@pytest.mark.parametrize("key", ["ai_disabled_hint", "scan_ai_fallback"])
def test_the_new_messages_are_translated(language: str, key: str) -> None:
    """پیام ترجمه‌نشده یعنی کلید خام روی صفحه."""
    import json

    with open(f"localization/{language}/signals.json", encoding="utf-8") as handle:
        data = json.load(handle)

    assert key in data
    assert data[key].strip() != ""
