"""سیم‌کشی ذخیرهٔ UI تا موتور؛ در محیط فاقد Qt صریحاً skip می‌شود."""

from types import MethodType, SimpleNamespace

import pytest

try:
    from ui.controllers.main_controller import MainController
except ImportError as exc:
    pytest.skip(f"Qt system libraries unavailable: {exc}", allow_module_level=True)

from app.config.settings_service import SettingsService
from app.database.repositories.settings_repository import SettingsRepository
from trading.auto_trader import AutoTradeConfig, AutoTrader
from trading.price_cache import TickEngine


def test_save_ui_settings_applies_runtime_config(database):
    settings = SettingsService(SettingsRepository(database))
    settings.initialize_defaults()
    engine = AutoTrader(config=AutoTradeConfig(), price_source=None, repository=None)
    ticks = TickEngine()
    engine.attach_tick_engine(ticks)
    refreshed = []
    controller = SimpleNamespace(
        app=SimpleNamespace(settings=settings), _auto_trader_engine=engine,
        refresh_auto_config=lambda: refreshed.append(True), _toast=lambda *a, **kw: None,
        tr_=SimpleNamespace(tr=lambda value: value),
    )
    controller._auto_trade_config = MethodType(MainController._auto_trade_config, controller)
    MainController.save_auto_trade_settings(controller, {
        "scalp.engine_mode": "selected", "scalp.selected_symbols": "ETH/USDT",
        "scalp.max_spread_percent": 0.05, "scalp.trailing_enabled": True,
        "scalp.max_total_margin_percent": 20.0, "scalp.stale_after_seconds": 3.0,
    })
    assert refreshed and engine.config.trailing_enabled
    assert engine.config.max_total_margin_percent == 20
    assert engine.config.max_spread_percent == 0.05
    assert engine._allowed_symbols() == ["ETH/USDT"]
    assert ticks.stale_after_ms == 3000
    assert not engine.config.is_live
