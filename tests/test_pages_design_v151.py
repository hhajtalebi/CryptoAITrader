"""
آزمون‌های طراحی نسخهٔ ۱.۵.۱ برای صفحات قدیمی.

این صفحات پیش‌تر هیچ‌کدام از ویجت‌های تازهٔ نسخهٔ ۱.۵ را به کار نمی‌بردند؛
آزمون‌های زیر تضمین می‌کنند اجزای تازه (ستون ستاره، تراشه‌های فیلتر،
اسپارک‌لاین، پنل اندیکاتور، حلقهٔ اطمینان و نمودارهای گزارش) دوباره حذف
یا خراب نشوند.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from localization import Translator  # noqa: E402
from ui.pages.analysis_page import CHART_TIMEFRAMES, AnalysisPage  # noqa: E402
from ui.pages.markets_page import (  # noqa: E402
    COL_CHANGE,
    COL_STAR,
    COL_SYMBOL,
    COL_TREND,
    MarketsPage,
)
from ui.pages.reports_page import STAT_KEYS, ReportsPage  # noqa: E402
from ui.pages.signals_page import SignalsPage  # noqa: E402
from ui.themes import get_theme  # noqa: E402

THEMES = ("glass_dark", "minimal_light", "corporate_navy", "violet_light")


@pytest.fixture(scope="module")
def translator() -> Translator:
    """مترجم فارسی مشترک آزمون‌ها."""
    tr = Translator("fa")
    tr.load()
    return tr


@pytest.fixture
def market_rows() -> list[dict[str, object]]:
    """چند ردیف بازار؛ فقط ردیف نخست تاریخچه دارد."""
    return [
        {
            "symbol": "BTC/USDT",
            "price": 77000.0,
            "change_percent": 2.34,
            "volume": 1.2e9,
            "high": 78000.0,
            "history": [1.0, 2.0, 3.0, 2.5],
        },
        {
            "symbol": "ETH/USDT",
            "price": 3010.0,
            "change_percent": -0.62,
            "volume": 5.0e8,
            "high": 3100.0,
        },
        {
            "symbol": "ETH/BTC",
            "price": 0.039,
            "change_percent": 0.31,
            "volume": 1.0e6,
            "high": 0.04,
        },
    ]


# ---------------------------------------------------------------------------
# صفحهٔ بازارها
# ---------------------------------------------------------------------------
def test_markets_has_star_and_trend_columns(
    qt_application: QApplication, translator: Translator, market_rows: list[dict[str, object]]
) -> None:
    """
    ستون ستاره و ستون روند باید وجود داشته باشند.

    کاربر گفت روند مشخص نیست؛ حالا هر ردیف — با تاریخچه یا بدون آن —
    سلول روند با برچسب فارسی و رنگ می‌گیرد. نمودار فقط وقتی تاریخچه
    هست نمایش داده می‌شود.
    """
    page = MarketsPage(translator)
    page.set_rows(market_rows)
    assert page.table.columnCount() == 8
    # هر دو ردیف سلول روند دارند؛ ستون دیگر هرگز خالی نمی‌ماند
    assert page.table.cellWidget(0, COL_TREND) is not None
    assert page.table.cellWidget(1, COL_TREND) is not None


def test_markets_star_click_toggles_watchlist(
    qt_application: QApplication, translator: Translator, market_rows: list[dict[str, object]]
) -> None:
    """کلیک روی ستون ستاره باید سیگنال واچ‌لیست بدهد نه مدال جزئیات."""
    page = MarketsPage(translator)
    page.set_rows(market_rows)

    toggled: list[tuple[str, bool]] = []
    activated: list[str] = []
    page.watchlist_toggled.connect(lambda symbol, added: toggled.append((symbol, added)))
    page.coin_activated.connect(activated.append)

    page._on_cell_clicked(0, COL_STAR)
    assert toggled == [("BTC/USDT", True)]
    assert activated == []
    assert page.table.item(0, COL_STAR).text() == "★"

    page._on_cell_clicked(0, COL_STAR)
    assert toggled[-1] == ("BTC/USDT", False)
    assert page.table.item(0, COL_STAR).text() == "☆"


def test_markets_quote_filter_and_chips(
    qt_application: QApplication, translator: Translator, market_rows: list[dict[str, object]]
) -> None:
    """کلید جفت‌ارز و تراشه‌ها باید ردیف‌ها را محدود کنند."""
    page = MarketsPage(translator)
    page.set_rows(market_rows)
    assert page.table.rowCount() == 2  # فقط USDT

    page.quote_toggle.set_current("BTC")
    assert page.table.rowCount() == 1
    assert page.table.item(0, COL_SYMBOL).text() == "ETH/BTC"

    page.quote_toggle.set_current("USDT")
    page.chip_bar.set_selection(["gainers"], emit=True)
    assert page.table.rowCount() == 1
    assert page.table.item(0, COL_SYMBOL).text() == "BTC/USDT"

    page.chip_bar.set_selection(["losers"], emit=True)
    assert page.table.item(0, COL_SYMBOL).text() == "ETH/USDT"

    # هر دو تراشه با هم = همهٔ بازارهای متحرک
    page.chip_bar.set_selection(["gainers", "losers"], emit=True)
    assert page.table.rowCount() == 2


def test_markets_watchlist_only_filter(
    qt_application: QApplication, translator: Translator, market_rows: list[dict[str, object]]
) -> None:
    """گزینهٔ «فقط واچ‌لیست» باید بقیهٔ ردیف‌ها را پنهان کند."""
    page = MarketsPage(translator)
    page.set_watchlist(["ETH/USDT"])
    page.set_rows(market_rows)
    page.watchlist_only_checkbox.setChecked(True)
    assert page.table.rowCount() == 1
    assert page.table.item(0, COL_SYMBOL).text() == "ETH/USDT"


def test_markets_change_sign_survives_rtl(
    qt_application: QApplication, translator: Translator, market_rows: list[dict[str, object]]
) -> None:
    """علامت + باید پیش از عدد بماند (نشانگر چپ‌به‌راست)."""
    page = MarketsPage(translator)
    page.set_rows(market_rows)
    text = page.table.item(0, COL_CHANGE).text()
    assert text.startswith("\u200e+"), text


def test_markets_star_column_is_not_sortable(
    qt_application: QApplication, translator: Translator, market_rows: list[dict[str, object]]
) -> None:
    """کلیک روی سرستون ستاره یا روند نباید ترتیب را به هم بزند."""
    page = MarketsPage(translator)
    page.set_rows(market_rows)
    before = [
        page.table.item(row, COL_SYMBOL).text() for row in range(page.table.rowCount())
    ]
    page._on_header_clicked(COL_STAR)
    page._on_header_clicked(COL_TREND)
    after = [
        page.table.item(row, COL_SYMBOL).text() for row in range(page.table.rowCount())
    ]
    assert before == after


# ---------------------------------------------------------------------------
# صفحهٔ تحلیل
# ---------------------------------------------------------------------------
def test_analysis_indicator_panel_toggles(
    qt_application: QApplication, translator: Translator
) -> None:
    """پنل اندیکاتورها باید وضعیت را نگه دارد و سیگنال بدهد."""
    page = AnalysisPage(translator)
    page.set_indicator_catalog(
        [
            {"name": "RSI", "label": "RSI", "description": "شاخص قدرت نسبی"},
            {"name": "MACD", "label": "MACD", "description": "همگرایی/واگرایی"},
        ],
        ["RSI"],
    )
    assert page.enabled_indicators() == ["RSI"]

    events: list[tuple[str, bool]] = []
    page.indicator_toggled.connect(lambda name, state: events.append((name, state)))
    page._indicator_rows["MACD"]["toggle"].setChecked(True)
    assert events == [("MACD", True)]
    assert page.enabled_indicators() == ["RSI", "MACD"]

    # تعیین برنامه‌ای نباید سیگنال تازه‌ای بفرستد
    page.set_enabled_indicators(["MACD"])
    assert events == [("MACD", True)]
    assert page.enabled_indicators() == ["MACD"]


def test_analysis_timeframe_bar_syncs_with_combo(
    qt_application: QApplication, translator: Translator
) -> None:
    """نوار تایم‌فریم و فهرست کشویی باید همیشه یک مقدار را نشان دهند."""
    page = AnalysisPage(translator)
    received: list[str] = []
    page.timeframe_changed.connect(received.append)

    page.timeframe_bar.set_current("1d")
    assert received == ["1d"]
    assert page.timeframe_combo.currentData() == "1d"

    # مسیر برعکس: تغییر فهرست کشویی باید نوار را هم جابه‌جا کند
    page.timeframe_combo.setCurrentIndex(page.timeframe_combo.findData("1h"))
    assert page.timeframe_bar.current() == "1h"
    assert "1h" in CHART_TIMEFRAMES


# ---------------------------------------------------------------------------
# صفحهٔ سیگنال‌ها
# ---------------------------------------------------------------------------
def test_signal_card_has_confidence_ring(
    qt_application: QApplication, translator: Translator
) -> None:
    """درصد اطمینان باید روی حلقه هم نمایش داده شود."""
    page = SignalsPage(translator)
    page.show_signal(
        {
            "symbol": "BTC/USDT",
            "direction": "WAIT",
            "confidence": 78,
            "entry_min": 63200,
            "entry_max": 63500,
            "stop_loss": 61800,
            "take_profits": [67900],
            "risk_reward": 2.4,
            "leverage": 1,
        }
    )
    ring = page.signal_card.confidence_ring
    assert ring._value == pytest.approx(78.0)
    assert "78" in ring._label


def test_signals_retranslate_keeps_history(
    qt_application: QApplication, translator: Translator
) -> None:
    """تغییر زبان نباید جدول سابقه را خالی کند."""
    page = SignalsPage(translator)
    page.set_history(
        [
            {
                "id": 1,
                "created_at": "۱۴۰۴/۰۶/۲۰",
                "symbol": "BTC/USDT",
                "direction": "LONG",
                "confidence": 71,
                "risk_reward": 2.1,
                "leverage": 3,
            }
        ]
    )
    translator.set_language("en")
    try:
        page.retranslate()
        assert page.history_table.rowCount() == 1
        assert page.signal_card._labels["entry"] == "Entry zone"
    finally:
        translator.set_language("fa")
        page.retranslate()


# ---------------------------------------------------------------------------
# صفحهٔ گزارش‌ها
# ---------------------------------------------------------------------------
def test_reports_charts_and_stat_cards(
    qt_application: QApplication, translator: Translator
) -> None:
    """کارت‌های آمار، حلقه و نمودار سری زمانی باید پر شوند."""
    page = ReportsPage(translator)
    page.set_summary(
        {
            "total": 48,
            "by_direction": {"LONG": 20, "SHORT": 15, "WAIT": 13},
            "average_confidence": 76.0,
            "top_symbols": {"BTC/USDT": 12},
            "confidence_series": [50.0, 60.0, 70.0, 80.0],
        }
    )
    assert set(page._stat_cards) == set(STAT_KEYS)
    assert len(page.donut_chart._segments) == 3
    assert len(page.area_chart._values) == 4
    # ارقام باید فارسی باشند
    assert "۴۸" in page._stat_cards["total_signals"].value_label.text()


def test_reports_empty_summary_is_safe(
    qt_application: QApplication, translator: Translator
) -> None:
    """خلاصهٔ خالی نباید خطا بدهد و باید حالت «بدون داده» نشان دهد."""
    page = ReportsPage(translator)
    page.set_summary({"total": 0, "by_direction": {}, "average_confidence": 0})
    assert page._stat_cards["long_share"].value_label.text() == "—"
    assert page.area_chart._values == []


# ---------------------------------------------------------------------------
# پوسته‌ها
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("theme_key", THEMES)
def test_updated_pages_accept_every_theme(
    qt_application: QApplication,
    translator: Translator,
    market_rows: list[dict[str, object]],
    theme_key: str,
) -> None:
    """هر چهار پوسته باید روی صفحات به‌روزشده بدون خطا اعمال شوند."""
    theme = get_theme(theme_key)

    markets = MarketsPage(translator)
    markets.set_rows(market_rows)
    markets.apply_theme(theme)
    assert markets.table.rowCount() == 2

    analysis = AnalysisPage(translator)
    analysis.set_indicator_catalog([{"name": "RSI", "label": "RSI", "description": "…"}], ["RSI"])
    analysis.apply_theme(theme)

    signals = SignalsPage(translator)
    signals.apply_theme(theme)

    reports = ReportsPage(translator)
    reports.set_summary({"total": 1, "by_direction": {"LONG": 1}, "average_confidence": 50})
    reports.apply_theme(theme)
