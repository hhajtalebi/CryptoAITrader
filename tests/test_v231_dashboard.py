"""2.3.1 — داشبورد حرفه‌ای: مرکز فرمان، پهنای بازار و بیشترین تغییرها."""
from types import SimpleNamespace as NS

import pytest

from localization import Translator

pytest.importorskip("PySide6.QtWidgets")


def _ticker(symbol, change, turnover, price=1.0):
    return NS(symbol=symbol, last_price=price, change_percent=change, turnover_24h=turnover)


def test_summary_ranks_only_liquid_markets():
    from ui.controllers.main_controller import summarise_market

    tickers = [_ticker(f"L{i}/USDT", i - 5, 1e6 + i) for i in range(10)]
    tickers.append(_ticker("ILLIQ/USDT", 80.0, 10.0))       # کم‌گردش ولی +۸۰٪
    tickers.append(_ticker("DEAD/USDT", 5.0, 0.0))          # بدون گردش
    summary = summarise_market(tickers, liquid_count=10, movers=3)
    assert summary["total"] == 10
    assert [r["symbol"] for r in summary["gainers"]] == ["L9/USDT", "L8/USDT", "L7/USDT"]
    assert [r["symbol"] for r in summary["losers"]] == ["L0/USDT", "L1/USDT", "L2/USDT"]
    assert summary["up"] == 4 and summary["down"] == 5 and summary["flat"] == 1
    assert summarise_market([]) == {"total": 0, "gainers": [], "losers": []}


@pytest.fixture()
def dashboard(qt_application):  # noqa: ARG001
    from ui.pages.dashboard_page import DashboardPage

    return DashboardPage(Translator("fa"))


def test_command_center_starts_without_fake_numbers(dashboard):
    tiles = dashboard.command_tiles
    assert set(tiles) == {"connection", "portfolio", "engine", "breadth"}
    assert tiles["portfolio"].state["value"] == "—"
    assert tiles["breadth"].state["value"] == "—"
    assert dashboard.blocks.order[0] == "command"


def test_connection_tile_explains_rate_limit(dashboard):
    dashboard.set_connection_health({
        "state": "degraded", "exchange": "toobit", "data_age": 42,
        "streams": {"connections": 2, "connected": 1},
        "rest": {"failures": 0, "cooldown_seconds": 25},
    })
    state = dashboard.command_tiles["connection"].state
    assert state["value"] == dashboard.tr_.tr("dashboard.command.rate_limited")
    assert state["chip"] == "TOOBIT"
    assert state["caption"]
    labels = {key: (value, role) for key, value, role in state["details"]}
    assert labels[dashboard.tr_.tr("dashboard.command.data_age")][1] == "bearish"


def test_portfolio_and_engine_tiles_use_net_values(dashboard):
    dashboard.set_portfolio({"open_count": 2, "unrealised": -1.5, "realised_today": 3.0,
                             "margin": 20.0, "win_rate": 50.0})
    tile = dashboard.command_tiles["portfolio"]
    assert "−$" in tile.state["value"] and tile.value_label.property("role") == "metric_down"
    dashboard.set_engine_status({"exists": True, "running": False, "open": 1, "max": 3,
                                 "live": False, "daily_limit": 20})
    assert dashboard.command_tiles["engine"].state["value"] == dashboard.tr_.tr(
        "dashboard.command.engine_stopped")


def test_movers_click_opens_coin_details(dashboard):
    seen = []
    dashboard.coin_activated.connect(seen.append)
    dashboard.set_movers([{"symbol": "SOL/USDT", "price": 150.0, "change_percent": 7.0}], [])
    dashboard.gainers_list._clicked(0)
    assert seen == ["SOL/USDT"]


def test_old_saved_layout_puts_command_center_on_top(dashboard):
    dashboard.apply_layout_state("signals,ticker,stats,overview")
    assert dashboard.blocks.order[0] == "command"


def test_retranslate_keeps_command_data(dashboard):
    dashboard.set_breadth({"up": 6, "down": 3, "flat": 1, "avg_change": 0.8})
    dashboard.tr_.set_language("en") if hasattr(dashboard.tr_, "set_language") else None
    dashboard.retranslate()
    assert dashboard.command_tiles["breadth"].state["value"].startswith(("60", "۶۰"))
