"""
نسخهٔ ۲.۵.۹ — معاملهٔ دستی.

کاربر: «نماد، مبلغ از موجودی، اسپات/فیوچرز، اهرم ۱ تا ۱۰۰، حد سود و ضرر را
انتخاب و معامله را باز کنم؛ از سیگنال با مقادیر پرشده (ویرایش/تأیید)، از یک
صفحه، و با دکمهٔ «باز کردن معامله» در تاریخچهٔ معاملات.»
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trading.manual_order import (
    MAX_MANUAL_LEVERAGE,
    ManualOrderRequest,
    liquidation_price,
    normalize_symbol,
    percent_from_price,
    plan_manual_order,
    prefill_from_signal,
    price_from_percent,
)

ROOT = Path(__file__).resolve().parent.parent


def _plan(**overrides):
    values = dict(
        symbol="BTC/USDT", market_type="futures", direction="LONG", amount=100.0,
        leverage=10, entry=100.0, take_profit=110.0, stop_loss=95.0, available=1000.0, fee_rate=0.0,
    )
    values.update(overrides)
    return plan_manual_order(ManualOrderRequest(**values))


# ---------------------------------------------------------------------------
# منطق
# ---------------------------------------------------------------------------


class TestPlan:
    def test_valid_futures_long_numbers(self) -> None:
        plan = _plan()
        assert plan.valid, plan.errors
        assert plan.notional == pytest.approx(1000.0)
        assert plan.quantity == pytest.approx(10.0)
        assert plan.profit_at_tp == pytest.approx(100.0)
        assert plan.loss_at_sl == pytest.approx(-50.0)
        assert plan.risk_reward == pytest.approx(2.0)
        assert plan.liquidation == pytest.approx(100 * (1 - (0.1 - 0.005)))
        assert plan.side == "long"

    def test_short_sides_are_mirrored(self) -> None:
        assert _plan(direction="SHORT", take_profit=90.0, stop_loss=105.0).valid
        plan = _plan(direction="SHORT", take_profit=110.0, stop_loss=95.0)
        assert {"tp_wrong_side", "sl_wrong_side"} <= set(plan.errors)

    def test_wrong_sides_for_long(self) -> None:
        plan = _plan(take_profit=90.0, stop_loss=105.0)
        assert "tp_wrong_side" in plan.errors and "sl_wrong_side" in plan.errors

    @pytest.mark.parametrize("leverage", [1, 50, MAX_MANUAL_LEVERAGE])
    def test_leverage_range_accepted(self, leverage: int) -> None:
        plan = _plan(leverage=leverage, stop_loss=99.9)
        assert "leverage_range" not in plan.errors
        assert plan.leverage == leverage

    @pytest.mark.parametrize("leverage", [0, 101, 500])
    def test_leverage_out_of_range(self, leverage: int) -> None:
        assert "leverage_range" in _plan(leverage=leverage).errors

    def test_spot_has_no_leverage_and_no_short(self) -> None:
        spot = _plan(market_type="spot", leverage=25)
        assert spot.valid and spot.leverage == 1 and spot.liquidation == 0.0
        assert spot.notional == pytest.approx(100.0)
        assert "spot_no_short" in _plan(market_type="spot", direction="SHORT",
                                        take_profit=90.0, stop_loss=105.0).errors

    def test_amount_rules(self) -> None:
        assert "amount_required" in _plan(amount=0).errors
        assert "amount_exceeds_balance" in _plan(amount=2000.0).errors
        # موجودی نامعلوم (۰) سقفی نمی‌گذارد
        assert _plan(amount=2000.0, available=0.0).valid

    def test_entry_required(self) -> None:
        assert "entry_required" in _plan(entry=0.0).errors

    def test_stop_beyond_liquidation_is_refused(self) -> None:
        plan = _plan(leverage=100, stop_loss=95.0)
        assert "sl_beyond_liquidation" in plan.errors
        assert "high_leverage" in plan.warnings

    def test_missing_levels_are_warnings_not_errors(self) -> None:
        plan = _plan(take_profit=0.0, stop_loss=0.0)
        assert plan.valid
        assert {"no_stop_loss", "no_take_profit", "liquidation_risk"} <= set(plan.warnings)

    def test_fees_reduce_outcomes(self) -> None:
        plan = _plan(fee_rate=0.001)
        assert plan.fees == pytest.approx(2.0)
        assert plan.profit_at_tp == pytest.approx(98.0)
        assert plan.loss_at_sl == pytest.approx(-52.0)


class TestHelpers:
    @pytest.mark.parametrize("raw,expected", [
        ("btcusdt", "BTC/USDT"), ("BTC/USDT", "BTC/USDT"), (" eth-usdt ", "ETH/USDT"), ("", ""),
    ])
    def test_normalize_symbol(self, raw: str, expected: str) -> None:
        assert normalize_symbol(raw) == expected

    def test_percent_round_trip(self) -> None:
        assert price_from_percent(100, 5, "LONG", "tp") == pytest.approx(105)
        assert price_from_percent(100, 5, "LONG", "sl") == pytest.approx(95)
        assert price_from_percent(100, 5, "SHORT", "tp") == pytest.approx(95)
        assert price_from_percent(100, 5, "SHORT", "sl") == pytest.approx(105)
        assert percent_from_price(100, 95) == pytest.approx(5)

    def test_liquidation(self) -> None:
        assert liquidation_price(100, 1, "LONG") == 0.0
        assert liquidation_price(100, 10, "SHORT") == pytest.approx(109.5)

    def test_prefill_from_signal(self) -> None:
        values = prefill_from_signal({
            "symbol": "SOLUSDT", "direction": "short", "entry_min": 99.0, "entry_max": 101.0,
            "stop_loss": 104.0, "take_profits": [95.0, 90.0], "leverage": 7,
        })
        assert values["symbol"] == "SOL/USDT"
        assert values["direction"] == "SHORT"
        assert values["entry"] == pytest.approx(100.0)
        assert values["take_profit"] == pytest.approx(95.0)
        assert values["stop_loss"] == pytest.approx(104.0)
        assert values["leverage"] == 7


# ---------------------------------------------------------------------------
# ترجمه‌ها
# ---------------------------------------------------------------------------


def test_every_error_and_warning_has_a_translation() -> None:
    keys = {"symbol_required", "direction_required", "spot_no_short", "leverage_range",
            "amount_required", "amount_exceeds_balance", "entry_required", "tp_wrong_side",
            "sl_wrong_side", "sl_beyond_liquidation"}
    warns = {"no_stop_loss", "no_take_profit", "liquidation_risk", "high_leverage"}
    for lang in ("fa", "en"):
        manual = json.loads((ROOT / "localization" / lang / "trades.json").read_text("utf-8"))["manual"]
        for key in keys:
            assert manual.get(f"error_{key}"), (lang, key)
        for key in warns:
            assert manual.get(f"warn_{key}"), (lang, key)
        for key in ("button", "edit_and_open", "title", "opened_toast", "refused_live"):
            assert manual.get(key), (lang, key)


# ---------------------------------------------------------------------------
# رابط کاربری
# ---------------------------------------------------------------------------


@pytest.fixture()
def tr():
    from localization.translator import Translator

    return Translator(language="fa")


def test_dialog_prefill_payload_and_open(qtbot, tr) -> None:
    from ui.dialogs.manual_trade_dialog import ManualTradeDialog

    dialog = ManualTradeDialog(tr, symbols=["BTC/USDT", "ETH/USDT"], available=500.0, fee_rate=0.0)
    qtbot.addWidget(dialog)
    dialog.prefill({"symbol": "ETH/USDT", "direction": "SHORT", "entry": 2000.0,
                    "take_profit": 1900.0, "stop_loss": 2050.0, "leverage": 5})
    assert dialog.symbol() == "ETH/USDT"
    assert dialog.direction() == "SHORT"
    dialog.apply_amount_percent(50)
    payload = dialog.payload()
    assert payload["amount"] == pytest.approx(250.0)
    assert payload["leverage"] == 5
    assert payload["market_type"] == "futures"
    assert dialog.plan().valid, dialog.plan().errors

    received: list[dict] = []
    dialog.order_requested.connect(received.append)
    dialog._on_open()  # noqa: SLF001
    assert received and received[0]["symbol"] == "ETH/USDT"


def test_dialog_blocks_invalid_order(qtbot, tr) -> None:
    from ui.dialogs.manual_trade_dialog import ManualTradeDialog

    dialog = ManualTradeDialog(tr, symbols=["BTC/USDT"], available=100.0, fee_rate=0.0)
    qtbot.addWidget(dialog)
    dialog.prefill({"symbol": "BTC/USDT", "direction": "LONG", "entry": 100.0,
                    "take_profit": 90.0, "stop_loss": 95.0, "leverage": 10})
    dialog.apply_amount_percent(50)
    received: list[dict] = []
    dialog.order_requested.connect(received.append)
    dialog._on_open()  # noqa: SLF001
    assert not received
    assert not dialog.plan().valid


def test_dialog_set_price_fills_entry(qtbot, tr) -> None:
    from ui.dialogs.manual_trade_dialog import ManualTradeDialog

    dialog = ManualTradeDialog(tr, symbols=["BTC/USDT"], available=100.0)
    qtbot.addWidget(dialog)
    dialog.prefill({"symbol": "BTC/USDT"})
    dialog.set_price("BTC/USDT", 65000.5)
    assert dialog.payload()["entry"] == pytest.approx(65000.5)
    # قیمت نماد دیگری نباید ورود را عوض کند
    dialog.set_price("ETH/USDT", 3000.0)
    assert dialog.payload()["entry"] == pytest.approx(65000.5)


def test_trades_page_has_open_trade_buttons(qtbot, tr) -> None:
    from ui.pages.trades_page import TradesPage

    page = TradesPage(tr)
    qtbot.addWidget(page)
    hits: list[bool] = []
    page.manual_trade_requested.connect(lambda: hits.append(True))
    page.manual_trade_button.click()
    page.history_open_trade_button.click()
    assert len(hits) == 2


def test_signal_detail_dialog_emits_manual_prefill(qtbot, tr) -> None:
    from ui.dialogs.signal_detail_dialog import SignalDetailDialog

    signal = {
        "symbol": "BTC/USDT", "direction": "LONG", "confidence": 70, "entry_min": 100.0,
        "entry_max": 100.0, "stop_loss": 95.0, "take_profits": [105.0, 110.0], "leverage": 3,
    }
    dialog = SignalDetailDialog(signal, tr)
    qtbot.addWidget(dialog)
    received: list[dict] = []
    dialog.manual_trade_requested.connect(received.append)
    dialog.manual_trade_button.click()
    assert received
    values = received[0]
    assert values["symbol"] == "BTC/USDT"
    assert values["direction"] == "LONG"
    assert values["stop_loss"] > 0 and values["take_profit"] > values["entry"] > 0
    assert values["source"] == "signal_manual"


# ---------------------------------------------------------------------------
# کنترلر: قیمت زنده، اعتبارسنجی دوباره و ثبت کاغذی
# ---------------------------------------------------------------------------


class _FakeController:
    """فقط همان چیزهایی که `_on_manual_order` لازم دارد."""

    def __init__(self, tr, live_price: float) -> None:
        from types import SimpleNamespace

        self.tr_ = tr
        self.app = SimpleNamespace(settings=SimpleNamespace(get=lambda key, default=None: default))
        self._live = live_price
        self.recorded: list[dict] = []
        self.toasts: list[tuple[str, str]] = []
        self.trades = SimpleNamespace(show_open_history=lambda: None)

    def _live_fill_price(self, symbol, side):  # noqa: ANN001, ARG002
        return self._live

    def record_paper_trade(self, record):  # noqa: ANN001
        self.recorded.append(record)
        return {"id": 1}

    def _update_streamed_symbols(self) -> None: ...
    def _go_to(self, key) -> None: ...  # noqa: ANN001
    def refresh_trades(self) -> None: ...
    def status(self, text) -> None: ...  # noqa: ANN001

    def _toast(self, text, level="info") -> None:  # noqa: ANN001
        self.toasts.append((level, text))

    def _money(self, value) -> str:  # noqa: ANN001
        return f"{value:.2f}"


class _FakeDialog:
    def __init__(self) -> None:
        self.opened = False
        self.errors: list[str] = []

    def trade_opened(self) -> None:
        self.opened = True

    def show_error(self, text: str) -> None:
        self.errors.append(text)


ORDER = {"symbol": "BTC/USDT", "market_type": "futures", "direction": "LONG", "amount": 100.0,
         "leverage": 10, "entry": 100.0, "take_profit": 110.0, "stop_loss": 95.0, "available": 1000.0}


def test_controller_records_manual_paper_trade_at_live_price(tr) -> None:
    from ui.controllers.main_controller import MainController

    fake, dialog = _FakeController(tr, live_price=101.0), _FakeDialog()
    MainController._on_manual_order(fake, dict(ORDER), dialog=dialog)  # type: ignore[arg-type]
    assert dialog.opened and not dialog.errors
    record = fake.recorded[0]
    assert record["entry_price"] == pytest.approx(101.0)
    assert record["leverage"] == 10
    assert record["quantity"] == pytest.approx(1000.0 / 101.0)
    assert record["take_profits"] == [110.0] and record["stop_loss"] == 95.0
    assert record["source"] == "manual" and record["market_type"] == "futures"
    assert "id" not in record  # signal_id خالی؛ شناسهٔ ناموجود خطای پایگاه داده می‌داد


def test_controller_refuses_when_live_price_crossed_the_stop(tr) -> None:
    from ui.controllers.main_controller import MainController

    fake, dialog = _FakeController(tr, live_price=94.0), _FakeDialog()
    MainController._on_manual_order(fake, dict(ORDER), dialog=dialog)  # type: ignore[arg-type]
    assert not fake.recorded and not dialog.opened
    assert dialog.errors and fake.toasts[0][0] == "warning"
