"""
آزمون‌های اتصال رابط کاربری.

این آزمون‌ها دقیقاً همان ایرادهایی را پوشش می‌دهند که کاربر گزارش کرد،
تا اگر روزی دوباره خراب شدند، بی‌سروصدا از قلم نیفتند.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from localization import Translator  # noqa: E402
from market.timeframes import SUPPORTED_TIMEFRAMES  # noqa: E402
from ui.pages.analysis_page import AnalysisPage  # noqa: E402
from ui.pages.markets_page import (  # noqa: E402
    COL_PRICE_TOMAN,
    COL_PRICE_USD,
    COL_SYMBOL,
    MarketsPage,
)
from ui.pages.settings_page import SettingsPage  # noqa: E402
from ui.pages.signals_page import SignalsPage  # noqa: E402
from ui.themes import ThemeManager  # noqa: E402
from ui.widgets import RefreshButton  # noqa: E402


@pytest.fixture()
def qt_app(qt_application: QApplication) -> QApplication:
    """نمونه Qt مشترک جلسه (از conftest)."""
    return qt_application


@pytest.fixture()
def translator() -> Translator:
    return Translator("fa")


@pytest.fixture()
def palette(qt_app: QApplication) -> dict[str, str]:
    manager = ThemeManager()
    manager.apply(qt_app, "dark")
    return manager.palette


# ----------------------------------------------------------------------
# ایراد ۳: دکمه تازه‌سازی بازخورد نمی‌داد
# ----------------------------------------------------------------------
def test_refresh_button_shows_busy_then_done(qt_app: QApplication) -> None:
    """کاربر باید ببیند دکمه کار می‌کند، حتی وقتی داده عوض نشود."""
    button = RefreshButton("تازه‌سازی", busy_text="در حال…", done_text="به‌روز شد")

    assert button.text() == "تازه‌سازی"
    assert button.isEnabled()

    button.start_busy()
    assert button.text() == "در حال…"
    assert not button.isEnabled(), "دکمه هنگام کار باید غیرفعال باشد"

    button.finish_busy(success=True)
    assert "✓" in button.text(), "تأیید دیدنی لازم است"
    assert button.isEnabled()


def test_refresh_button_restores_on_failure(qt_app: QApplication) -> None:
    """در صورت شکست نباید علامت موفقیت نشان داده شود."""
    button = RefreshButton("تازه‌سازی", busy_text="در حال…")
    button.start_busy()
    button.finish_busy(success=False)

    assert button.text() == "تازه‌سازی"
    assert "✓" not in button.text()
    assert button.isEnabled()


# ----------------------------------------------------------------------
# ایراد ۹: تایم‌فریم‌ها ناقص بودند
# ----------------------------------------------------------------------
def test_analysis_page_offers_every_timeframe(qt_app: QApplication, translator: Translator) -> None:
    """از یک دقیقه تا ماهانه باید در دسترس باشد."""
    page = AnalysisPage(translator)
    codes = [page.timeframe_combo.itemData(i) for i in range(page.timeframe_combo.count())]

    assert len(codes) == len(SUPPORTED_TIMEFRAMES) == 14
    assert "1m" in codes and "1d" in codes and "1w" in codes and "1M" in codes


def test_signals_page_offers_every_timeframe(qt_app: QApplication, translator: Translator) -> None:
    """صفحه سیگنال هم باید انتخاب تایم‌فریم داشته باشد."""
    page = SignalsPage(translator)
    codes = [page.timeframe_combo.itemData(i) for i in range(page.timeframe_combo.count())]

    assert len(codes) == 14
    assert "1M" in codes


# ----------------------------------------------------------------------
# ایرادهای ۲، ۶، ۱۰: فهرست نمادها ناقص بود
# ----------------------------------------------------------------------
def test_pages_accept_full_symbol_list(qt_app: QApplication, translator: Translator) -> None:
    """هر دو صفحه باید فهرست کامل نمادها را بپذیرند، نه فقط بیت‌کوین."""
    symbols = [f"SYM{i}/USDT" for i in range(1200)]

    analysis = AnalysisPage(translator)
    signals = SignalsPage(translator)
    analysis.set_symbols(symbols)
    signals.set_symbols(symbols)

    assert analysis.symbol_combo.count() == 1200
    assert signals.symbol_combo.count() == 1200


def test_symbol_selection_survives_reload(qt_app: QApplication, translator: Translator) -> None:
    """تازه‌سازی فهرست نباید انتخاب کاربر را از بین ببرد."""
    page = AnalysisPage(translator)
    page.set_symbols(["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    page.symbol_combo.setCurrentText("SOL/USDT")

    page.set_symbols(["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"])

    assert page.symbol_combo.currentText() == "SOL/USDT"


# ----------------------------------------------------------------------
# ایراد ۵: قیمت دلار/تومان با رنگ سبز و قرمز
# ----------------------------------------------------------------------
def test_markets_page_has_usd_and_toman_columns(
    qt_app: QApplication, translator: Translator
) -> None:
    """هر دو ستون قیمت باید وجود داشته باشند."""
    page = MarketsPage(translator)
    assert page.table.columnCount() == 8


def test_toman_column_needs_a_rate(qt_app: QApplication, translator: Translator) -> None:
    """بدون نرخ، عدد ساختگی نشان داده نمی‌شود."""
    page = MarketsPage(translator)
    page.set_rows([{"symbol": "BTC/USDT", "price": 100.0, "change_percent": 1.0}])

    assert page.table.item(0, COL_PRICE_TOMAN).text() == "—"

    page.set_toman_rate(90_000, source="nobitex")
    assert page.table.item(0, COL_PRICE_TOMAN).text() != "—"


def test_rising_price_is_green_falling_is_red(
    qt_app: QApplication, translator: Translator, palette: dict[str, str]
) -> None:
    """رنگ باید جهت حرکت قیمت را نشان دهد."""
    page = MarketsPage(translator)
    page.set_palette(palette)
    page.set_rows([
        {"symbol": "UP/USDT", "price": 10.0, "change_percent": 1.0},
        {"symbol": "DOWN/USDT", "price": 20.0, "change_percent": -1.0},
    ])

    page.apply_price_updates({
        "UP/USDT": {"price": 11.0, "change_percent": 2.0, "tick_direction": 1},
        "DOWN/USDT": {"price": 19.0, "change_percent": -2.0, "tick_direction": -1},
    })

    up_row = page._row_index["UP/USDT"]
    down_row = page._row_index["DOWN/USDT"]
    green = palette["success"].lower()
    red = palette["danger"].lower()

    assert page.table.item(up_row, COL_PRICE_USD).foreground().color().name().lower() == green
    assert page.table.item(down_row, COL_PRICE_USD).foreground().color().name().lower() == red


def test_price_update_lands_on_the_correct_row(
    qt_app: QApplication, translator: Translator, palette: dict[str, str]
) -> None:
    """
    مرتب‌سازی جدول نباید تیک قیمت را روی ردیف اشتباه بنشاند.

    این باگ واقعی بود: نمایه هنگام پر کردن ساخته می‌شد ولی مرتب‌سازی
    بعد از آن ردیف‌ها را جابه‌جا می‌کرد.
    """
    page = MarketsPage(translator)
    page.set_palette(palette)
    page.set_rows([
        {"symbol": "AAA/USDT", "price": 1.0, "change_percent": 0.0},
        {"symbol": "ZZZ/USDT", "price": 2.0, "change_percent": 0.0},
    ])

    page.apply_price_updates({"ZZZ/USDT": {"price": 99.0, "tick_direction": 1}})

    row = page._row_index["ZZZ/USDT"]
    assert page.table.item(row, COL_SYMBOL).text() == "ZZZ/USDT"
    # ارقام در فارسی به شکل فارسی نمایش داده می‌شوند
    latin = translator.to_latin_digits(page.table.item(row, COL_PRICE_USD).text())
    assert "99" in latin


def test_live_update_preserves_colour_on_periodic_reload(
    qt_app: QApplication, translator: Translator, palette: dict[str, str]
) -> None:
    """تازه‌سازی دوره‌ای نباید رنگ نوسان زنده را پاک کند."""
    page = MarketsPage(translator)
    page.set_palette(palette)
    rows = [{"symbol": "BTC/USDT", "price": 100.0, "change_percent": 1.0}]
    page.set_rows(rows)
    page.apply_price_updates({"BTC/USDT": {"price": 101.0, "tick_direction": 1}})

    page.set_rows([{"symbol": "BTC/USDT", "price": 101.0, "change_percent": 1.2}])

    colour = page.table.item(0, COL_PRICE_USD).foreground().color().name().lower()
    assert colour == palette["success"].lower()


# ----------------------------------------------------------------------
# ایراد ۱۳ و ۱۴: صرافی‌ها و سرویس‌های هوش مصنوعی
# ----------------------------------------------------------------------
def test_settings_offers_multiple_exchanges(
    qt_app: QApplication, translator: Translator
) -> None:
    """کاربر باید بتواند میان صرافی‌ها جابه‌جا شود."""
    page = SettingsPage(translator)
    assert page.exchange_combo.count() >= 5

    keys = [page.exchange_combo.itemData(i) for i in range(page.exchange_combo.count())]
    assert "lbank" in keys


def test_settings_offers_many_ai_providers(
    qt_app: QApplication, translator: Translator
) -> None:
    """اتصال به سرویس‌های متعدد هوش مصنوعی."""
    page = SettingsPage(translator)
    keys = [page.ai_provider_combo.itemData(i) for i in range(page.ai_provider_combo.count())]

    assert len(keys) >= 10
    for expected in ("ollama", "openai", "openrouter", "anthropic"):
        assert expected in keys


def test_ai_key_field_disabled_for_local_providers(
    qt_app: QApplication, translator: Translator
) -> None:
    """سرویس محلی کلید نمی‌خواهد؛ ورودی نباید گمراه‌کننده باشد."""
    page = SettingsPage(translator)
    index = page.ai_provider_combo.findData("ollama")
    page.ai_provider_combo.setCurrentIndex(index)

    assert not page.ai_key_input.isEnabled()

    index = page.ai_provider_combo.findData("openai")
    page.ai_provider_combo.setCurrentIndex(index)
    assert page.ai_key_input.isEnabled()


def test_secrets_are_namespaced_per_exchange_and_provider(
    qt_app: QApplication, translator: Translator
) -> None:
    """
    کلید هر صرافی و هر سرویس جداگانه ذخیره می‌شود.

    بدون این، تعویض صرافی کلید قبلی را روی صرافی جدید می‌نوشت.
    """
    page = SettingsPage(translator)
    page.api_key_input.setText("exchange-key")
    page.ai_key_input.setText("ai-key")

    secrets = page.collect_secrets()

    assert "exchange.lbank.api_key" in secrets
    assert any(key.startswith("ai.") and key.endswith(".api_key") for key in secrets)


def test_settings_collects_ai_enabled_flag(
    qt_app: QApplication, translator: Translator
) -> None:
    """هوش مصنوعی باید از تنظیمات قابل فعال‌سازی باشد."""
    page = SettingsPage(translator)
    page.ai_enabled_check.setChecked(True)

    assert page.collect_values()["ai.enabled"] is True
