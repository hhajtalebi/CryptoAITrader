"""Headless controller contracts using the actual method AST, mocked Qt-facing objects.

These do not replace native Qt/window tests. Extraction avoids linking unavailable
system GUI libraries while exercising the real controller method bodies.
"""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, AsyncMock


ROOT = Path(__file__).resolve().parents[1]


def method(name):
    tree = ast.parse((ROOT / "ui/controllers/main_controller.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MainController")
    node = next(n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])
    ast.fix_missing_locations(module)
    scope = {"asyncio": asyncio}
    exec(compile(module, "main_controller.py:extracted", "exec"), scope)
    return scope[name]


class Runner:
    def __init__(self):
        self.pending = []

    def active_keys(self):
        return [p[0] for p in self.pending]

    def submit(self, key, coroutine, **callbacks):
        self.pending.append((key, coroutine, callbacks))

    async def finish(self):
        key, coroutine, callbacks = self.pending.pop(0)
        result = await coroutine
        callbacks["on_success"](result)


def translator():
    return NS(tr=lambda key, **kwargs: key + str(kwargs))


async def test_manual_entry_constructs_engine_and_navigates_only_after_success():
    candidate = object()
    engine = NS(opportunity_candidate=lambda s: None,
                open_trade=AsyncMock(return_value=NS(entry_price=100)),
                rejection_reason=lambda s: "stale_data")
    ctrl = NS(_auto_trader_engine=None, _auto_trader=Mock(return_value=engine),
              _watch_candidates={"BTC/USDT": candidate}, runner=Runner(),
              _toast=Mock(), tr_=translator(), _go_to=Mock(),
              trades=NS(show_open_history=Mock()), refresh_trades=Mock(), _on_error=Mock())
    call = method("on_opportunity_enter")
    call(ctrl, "BTC/USDT")
    call(ctrl, "BTC/USDT")  # same symbol pending; must not cancel/re-submit an order
    assert len(ctrl.runner.pending) == 1
    ctrl._go_to.assert_not_called()
    await ctrl.runner.finish()
    engine.open_trade.assert_awaited_once_with(candidate)
    ctrl._go_to.assert_called_once_with("nav.trades")
    ctrl.trades.show_open_history.assert_called_once()
    ctrl.refresh_trades.assert_called_once()


async def test_rejected_entry_keeps_page_and_surfaces_specific_guard_reason():
    engine = NS(opportunity_candidate=lambda s: object(), open_trade=AsyncMock(return_value=None),
                rejection_reason=lambda s: "fees_exceed_loss_budget")
    ctrl = NS(_auto_trader_engine=engine, runner=Runner(), _toast=Mock(), tr_=translator(),
              _go_to=Mock(), refresh_trades=Mock(), _on_error=Mock())
    method("on_opportunity_enter")(ctrl, "BTC/USDT")
    await ctrl.runner.finish()
    ctrl._go_to.assert_not_called()
    assert "fees_exceed_loss_budget" in ctrl._toast.call_args.args[0]


async def test_history_close_routes_managed_position_to_engine_not_repository():
    trade = NS(trade_id=42)
    engine = NS(open_trades=[trade], close_trade=AsyncMock(return_value={"id": 42}))
    repo = NS(close_trade=Mock())
    ctrl = NS(_auto_trader_engine=engine, runner=Runner(), _ensure_tick_engine=lambda: object(),
              app=NS(market=object(), trade_repository=repo), tr_=translator(),
              _toast=Mock(), refresh_trades=Mock(), refresh_wallet=Mock(), _on_error=Mock())
    call = method("close_paper_trade")
    call(ctrl, 42)
    call(ctrl, 42)
    assert len(ctrl.runner.pending) == 1
    await ctrl.runner.finish()
    engine.close_trade.assert_awaited_once_with(trade, "manual")
    repo.close_trade.assert_not_called()


def test_stopped_engine_is_reused_instead_of_orphaning_open_positions():
    engine = NS(is_running=False, apply_config=Mock(), open_trades=[object()])
    config = object()
    ctrl = NS(_auto_trader_engine=engine, _auto_trade_config=lambda: config)
    assert method("_auto_trader")(ctrl) is engine
    engine.apply_config.assert_called_once_with(config)


def test_all_position_close_buttons_share_history_close_path():
    ctrl = NS(close_paper_trade=Mock())
    method("close_auto_position")(ctrl, 42)
    ctrl.close_paper_trade.assert_called_once_with(42)


async def test_exchange_switch_stops_old_feed_before_rebinding():
    feed = NS(stop=AsyncMock(), start=AsyncMock())
    supervisor = NS(stop=AsyncMock(), start=AsyncMock())
    old_market = NS(exchange_name="old")
    new_market = NS(exchange_name="new", add_ticker_listener=Mock())
    app = NS(market=old_market, settings=NS(set=Mock()), auth=NS(user_id=None),
             trade_repository=NS(open_trades=lambda user_id: []))
    async def switch(exchange):
        feed.stop.assert_awaited_once()
        supervisor.stop.assert_awaited_once()
        app.market = new_market
        return "new"
    app.switch_exchange = switch
    ctrl = NS(app=app, _auto_trader_engine=None, runner=Runner(), tr_=translator(),
              _toast=Mock(), status=Mock(), _live_feed=feed, _connection_supervisor=supervisor,
              _pending_updates={}, _start_live_feed=Mock(), _tick_engine=NS(clear=Mock()),
              _on_market_ticker=Mock(), _refresh_connection_indicator=Mock(),
              refresh_markets=Mock(), refresh_dashboard=Mock(), refresh_wallet=Mock(), _on_error=Mock())
    method("apply_exchange_switch")(ctrl, "new")
    assert ctrl._exchange_switching
    await ctrl.runner.finish()
    assert not ctrl._exchange_switching
    ctrl._start_live_feed.assert_called_once()
    ctrl._tick_engine.clear.assert_called_once()
    callback = new_market.add_ticker_listener.call_args.args[0]
    callback("fresh")
    app.market = old_market
    callback("late-old-exchange-frame")
    ctrl._on_market_ticker.assert_called_once_with("fresh")


def test_switch_is_blocked_while_positions_are_open():
    ctrl = NS(_auto_trader_engine=None, runner=Runner(), tr_=translator(), _toast=Mock(),
              app=NS(market=NS(exchange_name="old"), settings=NS(set=Mock()),
                     auth=NS(user_id=None), trade_repository=NS(open_trades=lambda uid: [{"id": 1}])))
    method("apply_exchange_switch")(ctrl, "new")
    assert not ctrl.runner.pending
    ctrl.app.settings.set.assert_called_once_with("exchange.active", "old")
