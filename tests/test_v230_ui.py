"""Native Qt smoke tests; explicitly skipped when system Qt libraries are absent."""
from unittest.mock import Mock

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from localization import Translator
from ui.pages.trades_page import HISTORY_COLUMNS, TradesPage
from ui.dialogs.trading_dialogs import PositionDetailDialog
from tests.conftest import destroy_window


@pytest.fixture
def page():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    translator = Translator("fa")
    translator.load()
    widget = TradesPage(translator)
    yield widget
    destroy_window(widget)


def test_open_history_navigation_and_complete_columns(page):
    page.show_open_history()
    assert page.tabs.currentIndex() == 1
    assert page.filters()["status"] == "open"
    # v2.5.0: جدول تاریخچه بازسازی شد (۱۶ ستون از HISTORY_COLUMNS)
    assert page.table.columnCount() == len(HISTORY_COLUMNS) == 16
    assert page.positions_table.columnCount() >= 17


def test_history_has_per_row_close_only_for_open_records(page):
    page.set_trades([{"id": 1, "symbol": "BTC/USDT", "status": "open"},
                     {"id": 2, "symbol": "ETH/USDT", "status": "closed"}])
    closed = Mock()
    page.close_requested.connect(closed)
    page.table.cellWidget(0, HISTORY_COLUMNS.index("action")).click()
    closed.assert_called_once_with(1)
    assert page.table.cellWidget(1, HISTORY_COLUMNS.index("action")) is None


def test_closed_details_do_not_offer_another_trade_exit(page):
    dialog = PositionDetailDialog(page.tr_, {"id": 1, "symbol": "BTC/USDT", "status": "closed"}, page)
    text = page.tr_.tr("trades.auto.close_selected")
    assert all(button.text() != text for button in dialog.findChildren(QtWidgets.QPushButton))
    destroy_window(dialog)
