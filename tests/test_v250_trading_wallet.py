"""
آزمون‌های نسخهٔ ۲.۵.۰ — اشتراک سیگنال، جست‌وجوی کشسان، اقدام به معامله با
اهداف پلکانی، جدول تاریخچهٔ بازسازی‌شده، ماشین‌حساب پرشده، کیف پول سه‌زبانه،
موجودی فیوچرز LBank و موجودی کاغذی.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.database.models import Base
from app.database.repositories import PaperTradeRepository, UserRepository
from app.database.session import DatabaseManager


# ---------------------------------------------------------------------------
# LBank — پاسخ قرارداد و موجودی فیوچرز
# ---------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.headers: dict[str, str] = {}

    def json(self) -> Any:
        return self._payload


def _client():
    from market.providers.lbank.rest_client import LBankRestClient

    return LBankRestClient(api_key="k", api_secret="s")


def test_contract_success_payload_is_not_an_error() -> None:
    """`result:""` + `success:true` (مستند رسمی قرارداد) موفقیت است نه «LBank error 0»."""
    payload = {"data": {"available": "12.5"}, "error_code": 0, "msg": "", "result": "", "success": True}
    data = _client()._handle_response(_FakeResponse(payload), "/cfd/openApi/v1/prv/account", contract=True)
    assert data == {"available": "12.5"}


def test_contract_rate_limit_and_auth_codes() -> None:
    from app.exceptions.errors import AuthenticationError, RateLimitError

    client = _client()
    with pytest.raises(RateLimitError):
        client._handle_response(
            _FakeResponse({"error_code": 10012, "success": False, "result": "", "msg": "freq"}),
            "/x", contract=True,
        )
    with pytest.raises(AuthenticationError):
        client._handle_response(
            _FakeResponse({"error_code": 10008, "success": False, "result": "", "msg": "key"}),
            "/x", contract=True,
        )


def test_spot_path_keeps_old_rule() -> None:
    """مسیر اسپات تغییر نکرده: `result` خالی همچنان موفقیت حساب نمی‌شود."""
    from app.exceptions.errors import ExchangeError

    with pytest.raises(ExchangeError):
        _client()._handle_response(
            _FakeResponse({"error_code": 0, "result": "", "success": True}), "/v2/x"
        )


def test_futures_details_accept_common_field_names() -> None:
    from market.providers.lbank.provider import LBankProvider

    details = LBankProvider._parse_futures_details(
        {"walletBalance": "100", "unrealProfit": "-4", "availableBalance": "60",
         "positionMargin": "30", "frozenMargin": "6"},
        "USDT",
    )
    usdt = details["USDT"]
    assert usdt["total"] == pytest.approx(96.0)  # wallet + unrealized
    assert usdt["available"] == pytest.approx(60.0)
    assert usdt["margin"] == pytest.approx(30.0)
    assert usdt["frozen"] == pytest.approx(6.0)
    assert usdt["unrealized"] == pytest.approx(-4.0)
    # نگاشت قدیمی «دارایی → کل» همچنان کار می‌کند
    assert LBankProvider._parse_futures_balances({"data": [{"asset": "usdt", "balance": 5}]}) == {"USDT": 5.0}


def test_sync_balances_stores_wallet_details() -> None:
    import asyncio
    from unittest.mock import MagicMock

    from app.core.exchange_account_service import ExchangeAccountService

    repo = MagicMock()
    repo.get_account.return_value = {"id": 1, "exchange": "lbank"}
    service = ExchangeAccountService.__new__(ExchangeAccountService)
    service._repository = repo
    service.credentials = lambda _id: {"api_key": "k", "api_secret": "s"}

    class Provider:
        last_spot_details = {"USDT": {"free": 8.0, "locked": 2.0, "total": 10.0}}
        last_futures_details = {"USDT": {"total": 50.0, "available": 40.0}}

        async def get_account_balance(self):
            return {"USDT": 10.0}

        async def get_futures_balance(self):
            return {"USDT": 50.0}

        async def close(self):
            return None

    result = asyncio.run(
        service.sync_balances(1, lambda *_a: Provider(), price_lookup=lambda _asset: 1.0)
    )
    assert result["futures_value_usdt"] == pytest.approx(50.0)
    assert result["spot_value_usdt"] == pytest.approx(10.0)
    kwargs = repo.update_balances.call_args.kwargs
    assert kwargs["details"]["futures"]["USDT"]["available"] == 40.0
    assert kwargs["details"]["spot"]["USDT"]["locked"] == 2.0


# ---------------------------------------------------------------------------
# اهداف پلکانی
# ---------------------------------------------------------------------------
def test_clean_targets_and_fractions() -> None:
    from trading.staged_targets import clean_targets, stage_fractions

    assert clean_targets([110, 0, "105", 95, 120, 130], entry=100, side="long") == [105.0, 110.0, 120.0]
    assert clean_targets([90, 80, 105], entry=100, side="short") == [90.0, 80.0]
    assert sum(stage_fractions(3)) == pytest.approx(1.0)
    assert stage_fractions(3)[0] == pytest.approx(1 / 3)
    assert stage_fractions(2) == [0.5, 0.5]
    assert stage_fractions(1) == [1.0]


def test_next_step_sequence_long() -> None:
    from trading.staged_targets import next_step

    base = dict(side="long", targets=[105, 110, 120], original_quantity=3.0, entry=100.0)
    assert next_step(price=103, stop_loss=95, targets_hit=0, remaining_quantity=3.0, **base) is None
    step = next_step(price=105.5, stop_loss=95, targets_hit=0, remaining_quantity=3.0, **base)
    assert step["action"] == "partial" and step["index"] == 0
    assert step["quantity"] == pytest.approx(1.0) and step["new_stop"] == 100.0
    step = next_step(price=110, stop_loss=100, targets_hit=1, remaining_quantity=2.0, **base)
    assert step["action"] == "partial" and step["index"] == 1 and step["new_stop"] is None
    step = next_step(price=121, stop_loss=100, targets_hit=2, remaining_quantity=1.0, **base)
    assert step == {"action": "final", "index": 2, "reason": "take_profit"}
    # پس از TP1، برگشت به ورود = سربه‌سر
    step = next_step(price=99.9, stop_loss=100, targets_hit=1, remaining_quantity=2.0, **base)
    assert step == {"action": "stop", "reason": "breakeven"}
    # حد ضرر پیش از هدف بررسی می‌شود
    step = next_step(price=94, stop_loss=95, targets_hit=0, remaining_quantity=3.0, **base)
    assert step == {"action": "stop", "reason": "stop_loss"}


def test_next_step_short() -> None:
    from trading.staged_targets import next_step

    step = next_step(price=94.9, side="short", stop_loss=103, targets=[95, 90, 85],
                     targets_hit=0, original_quantity=3, remaining_quantity=3, entry=100)
    assert step["action"] == "partial" and step["new_stop"] == 100


@pytest.fixture()
def trades(tmp_path: Path) -> PaperTradeRepository:
    manager = DatabaseManager(f"sqlite:///{tmp_path / 'trades.db'}")
    Base.metadata.create_all(manager.engine)
    UserRepository(manager).create_user(username="first", password="Strong!pass1")
    return PaperTradeRepository(manager)


def test_partial_close_then_final_includes_realized(trades: PaperTradeRepository) -> None:
    trade = trades.open_trade(
        symbol="BTC/USDT", side="long", quantity=3.0, entry_price=100.0, user_id=1,
        stop_loss=95.0, take_profit=120.0, leverage=1.0,
        extra={"targets": [105, 110, 120], "original_quantity": 3.0},
    )
    after = trades.partial_close(trade["id"], quantity=1.0, exit_price=105.0, fee=0.1,
                                 target_index=0, new_stop_loss=100.0)
    assert after["quantity"] == pytest.approx(2.0)
    assert after["stop_loss"] == 100.0
    assert after["extra"]["targets_hit"] == 1
    assert after["extra"]["realized_gross"] == pytest.approx(5.0)
    trades.partial_close(trade["id"], quantity=1.0, exit_price=110.0, target_index=1)
    closed = trades.close_trade(trade["id"], exit_price=120.0, note="take_profit")
    # 5 + 10 + 20 − کارمزد 0.1
    assert closed["pnl"] == pytest.approx(34.9)
    assert closed["pnl_percent"] == pytest.approx(34.9 / 300 * 100)
    assert trades.realized_pnl_since(1) == pytest.approx(34.9)


def test_partial_close_rejects_full_quantity(trades: PaperTradeRepository) -> None:
    trade = trades.open_trade(symbol="ETH/USDT", side="short", quantity=1.0, entry_price=10.0, user_id=1)
    assert trades.partial_close(trade["id"], quantity=1.0, exit_price=9.0) is None


def test_evaluate_staged_reads_record_extra() -> None:
    from trading.trade_monitor import evaluate_staged, position_from_record

    record = {"id": 7, "symbol": "BTC/USDT", "side": "long", "quantity": 2.0, "entry_price": 100.0,
              "stop_loss": 100.0, "take_profit": 120.0, "leverage": 2,
              "extra": {"targets": [105, 110, 120], "targets_hit": 1, "original_quantity": 3.0,
                        "realized_gross": 5.0}}
    position = position_from_record(record)
    assert position.is_staged and position.targets_hit == 1
    updates, steps = evaluate_staged([position], {"BTC/USDT": 110.0})
    # 2×10 + 5 = 25 روی مارجین اولیهٔ 150
    assert updates[0]["pnl"] == pytest.approx(25.0)
    assert updates[0]["pnl_percent"] == pytest.approx(25 / 150 * 100, rel=1e-4)
    assert steps[0][2]["action"] == "partial" and steps[0][2]["index"] == 1


def test_evaluate_staged_legacy_trade_uses_single_tp() -> None:
    from trading.trade_monitor import LivePosition, evaluate_staged

    position = LivePosition(1, "X/USDT", "long", 1.0, 100.0, take_profit=110.0, stop_loss=90.0)
    _updates, steps = evaluate_staged([position], {"X/USDT": 111.0})
    assert steps == [(1, 111.0, {"action": "final", "reason": "take_profit"})]


# ---------------------------------------------------------------------------
# موجودی کاغذی
# ---------------------------------------------------------------------------
def test_paper_account_math() -> None:
    from trading.paper_account import build_account

    account = build_account(
        start=1000.0, realized=50.0, source="wallet",
        open_trades=[{"entry_price": 100.0, "quantity": 2.0, "leverage": 4, "pnl": -3.0}],
    )
    assert account.used_margin == pytest.approx(50.0)
    assert account.balance == pytest.approx(1050.0)
    assert account.available == pytest.approx(1000.0)
    assert account.equity == pytest.approx(1047.0)


# ---------------------------------------------------------------------------
# اشتراک‌گذاری
# ---------------------------------------------------------------------------
def test_share_urls() -> None:
    from ui.signal_share import SHARE_TARGETS, share_mode, share_url

    text = "BTC/USDT LONG\nTP1 1 & 2"
    assert share_url("telegram", text).startswith("https://t.me/share/url?url=%20&text=BTC%2FUSDT%20LONG%0ATP1")
    assert "%26" in share_url("whatsapp", text) and share_url("whatsapp", text).startswith("https://wa.me/?text=")
    assert share_url("x", text).startswith("https://x.com/intent/post?text=")
    assert share_url("email", text, subject="Sig").startswith("mailto:?subject=Sig&body=")
    assert share_url("rubika", text) == "https://web.rubika.ir/"
    assert share_mode("eitaa") == "copy" and share_mode("telegram") == "url"
    assert {t for t, _m in SHARE_TARGETS} >= {"telegram", "whatsapp", "rubika", "eitaa", "bale", "x", "email"}


# ---------------------------------------------------------------------------
# رابط کاربری (Qt)
# ---------------------------------------------------------------------------
QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

from localization import Translator  # noqa: E402

SIGNAL = {
    "symbol": "BTC/USDT", "direction": "LONG", "confidence": 74,
    "entry_min": 99.0, "entry_max": 101.0, "stop_loss": 95.0,
    "take_profits": [105.0, 110.0, 120.0], "leverage": 3,
}


@pytest.fixture()
def fa(qt_application) -> Translator:  # noqa: ARG001
    translator = Translator("fa")
    translator.load()
    return translator


def test_calculator_prefills_from_entry_range(fa) -> None:
    from ui.widgets.position_calculator import PositionCalculator

    calc = PositionCalculator(fa)
    calc.load_signal(SIGNAL)
    calc.set_capital(2000)
    values = calc.trade_values()
    assert values["entry"] == pytest.approx(100.0)  # وسط بازه، نه صفر
    assert values["targets"] == [105.0, 110.0, 120.0]
    assert values["leverage"] == 3
    assert values["quantity"] > 0
    assert calc.plan.valid


def test_dialog_payload_share_and_close(fa) -> None:
    from ui.dialogs.signal_detail_dialog import SignalDetailDialog

    dialog = SignalDetailDialog(SIGNAL, fa)
    dialog.set_account_balance(5000, 1.0, "source")
    assert dialog.calculator.capital_source_label.text() == "source"
    payload = dialog.trade_payload()
    assert payload["plan"]["capital"] == pytest.approx(5000)
    assert payload["plan"]["targets"] == [105.0, 110.0, 120.0]

    opened: list[str] = []
    dialog.url_opener = opened.append  # type: ignore[assignment]
    assert dialog.share_to("telegram").startswith("https://t.me/share/url")
    assert dialog.share_to("bale") == "https://web.bale.ai/"
    assert len(opened) == 2
    assert set(dialog.share_actions) >= {"telegram", "rubika", "whatsapp"}

    received: list[dict] = []
    dialog.trade_requested.connect(received.append)
    dialog.trade_button.click()
    assert received and "plan" in received[0]
    dialog.show()
    dialog.trade_opened()
    assert not dialog.isVisible()


def test_history_headers_are_set_at_build_and_rows_update_in_place(fa) -> None:
    from ui.pages.trades_page import HISTORY_COLUMNS, TradesPage

    page = TradesPage(fa)
    headers = [page.table.horizontalHeaderItem(i).text() for i in range(page.table.columnCount())]
    assert headers[HISTORY_COLUMNS.index("targets")] == fa.tr("trades.history_cols.targets")
    assert all(headers) and not any(h.isdigit() for h in headers)

    row = {"id": 1, "symbol": "BTC/USDT", "side": "long", "status": "open",
           "exit_text": "101", "targets_text": "TP1 105 ✓ · TP2 110", "pnl": 1.0, "pnl_text": "+1"}
    page.set_trades([row])
    action = HISTORY_COLUMNS.index("action")
    button = page.table.cellWidget(0, action)
    page.set_trades([dict(row, exit_text="102")])
    assert page.table.cellWidget(0, action) is button  # دکمه از نو ساخته نشد
    assert page.table.item(0, HISTORY_COLUMNS.index("price")).text() == "102"
    assert page.table.item(0, HISTORY_COLUMNS.index("targets")).text().strip("\u2066\u2069").startswith("TP1")


def test_wallet_has_three_tabs_and_detail_tables(fa) -> None:
    from ui.pages.wallet_page import FUTURES_COLUMNS, SPOT_COLUMNS, WALLET_TABS, WalletPage

    page = WalletPage(fa)
    assert page.tabs.count() == len(WALLET_TABS) == 3
    page.set_spot([{"asset": "BTC", "free_text": "0.1", "total_text": "0.1", "value_text": "$6,000"}],
                  {"value": "$6,000", "assets": "1"})
    assert page.spot_table.rowCount() == 1
    assert page.spot_table.columnCount() == len(SPOT_COLUMNS)
    assert page.spot_strip.value_text("value") == "$6,000"
    page.set_futures([{"asset": "USDT", "equity_text": "50", "unrealized": -1.0, "unrealized_text": "-1"}],
                     {"equity": "$50"}, note="")
    assert page.futures_table.item(0, FUTURES_COLUMNS.index("equity")).text() == "50"
    assert page.futures_strip.value_text("equity") == "$50"
    fired: list[bool] = []
    page.paper_sync_requested.connect(lambda: fired.append(True))
    page.paper_sync_button.click()
    assert fired == [True]


def test_search_box_is_expanding_and_rounded(fa) -> None:
    from PySide6.QtWidgets import QSizePolicy

    from ui.themes.stylesheet import build_stylesheet
    from ui.widgets.chrome import SEARCH_MAX_WIDTH, SearchBox

    box = SearchBox()
    assert box.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert box.maximumWidth() == SEARCH_MAX_WIDTH >= 700
    assert callable(build_stylesheet)


def test_search_style_rule_is_rounded() -> None:
    source = Path("ui/themes/stylesheet.py").read_text(encoding="utf-8")
    start = source.index('QLineEdit[role="search"] {{')
    assert "border-radius: 19px" in source[start:start + 200]


# ---------------------------------------------------------------------------
# کنترلر: اقدام به معامله (بدون ساخت پنجرهٔ اصلی)
# ---------------------------------------------------------------------------
class _Settings(dict):
    def get(self, key, default=None):  # noqa: D401
        return super().get(key, default)

    def set(self, key, value, notify=True):  # noqa: ARG002
        self[key] = value


def _fake_controller(trades: PaperTradeRepository, live_price: float = 0.0):
    from signals.paper_trader import PaperTrader
    from ui.controllers.main_controller import MainController

    translator = Translator("en")
    translator.load()
    settings = _Settings({"risk.risk_percent": 1.0, "scalp.taker_fee_rate": 0.0})

    class Fake:
        tr_ = translator
        _on_trade_requested = MainController._on_trade_requested
        record_paper_trade = MainController.record_paper_trade
        _paper_account = MainController._paper_account
        _trading_capital = MainController._trading_capital
        _is_paper_mode = MainController._is_paper_mode

        def __init__(self) -> None:
            self.app = SimpleNamespace(settings=settings, trade_repository=trades,
                                       auth=SimpleNamespace(user_id=1))
            self.toasts: list[str] = []
            self.pages: list[str] = []
            self.trades = SimpleNamespace(show_open_history=lambda: self.pages.append("open"))
            self._trader = PaperTrader(settings)

        def _paper_trader(self):
            return self._trader

        def _wallet_total_usdt(self):
            return 10_000.0

        def _live_fill_price(self, _symbol, _side):
            return live_price

        def _money(self, value):
            return f"${value:,.2f}"

        def status(self, _text):
            return None

        def _toast(self, text, level="info"):  # noqa: ARG002
            self.toasts.append(text)

        def refresh_trades(self):
            return None

        def _update_streamed_symbols(self):
            return None

        def _go_to(self, key):
            self.pages.append(key)

        def _on_error(self, *_a):
            raise AssertionError(_a)

    return Fake(), settings


def test_act_on_trade_opens_staged_trade_and_closes_dialog(trades: PaperTradeRepository) -> None:
    controller, settings = _fake_controller(trades, live_price=100.5)
    closed: list[bool] = []
    dialog = SimpleNamespace(trade_opened=lambda: closed.append(True))
    payload = dict(SIGNAL, plan={"entry": 100.0, "stop_loss": 95.0, "targets": [105, 110, 120],
                                 "capital": 0.0, "risk_percent": 1.0, "leverage": 3})
    controller._on_trade_requested(payload, dialog=dialog)

    assert closed == [True]
    assert controller.pages == ["nav.trades", "open"]
    opened = trades.open_trades(1)
    assert len(opened) == 1
    record = opened[0]
    assert record["entry_price"] == pytest.approx(100.5)  # قیمت زندهٔ قابل‌اجرا
    assert record["take_profit"] == pytest.approx(120.0)
    assert record["extra"]["targets"] == [105.0, 110.0, 120.0]
    # موجودی کاغذی = کیف پول واقعی (۱۰٬۰۰۰) و ریسک ۱٪ → ۱۰۰ دلار روی فاصلهٔ ۵٫۵
    assert settings["paper.start_balance"] == pytest.approx(10_000.0)
    assert record["quantity"] == pytest.approx(100 / 5.5, rel=1e-6)
    assert any("BTC/USDT" in text for text in controller.toasts)


def test_act_on_trade_refuses_when_price_passed_stop(trades: PaperTradeRepository) -> None:
    controller, _settings = _fake_controller(trades, live_price=94.0)
    closed: list[bool] = []
    controller._on_trade_requested(dict(SIGNAL), dialog=SimpleNamespace(trade_opened=lambda: closed.append(True)))
    assert closed == [] and trades.open_trades(1) == []


def test_localization_keys_exist_in_both_languages() -> None:
    for lang in ("fa", "en"):
        wallet = json.loads(Path(f"localization/{lang}/wallet.json").read_text(encoding="utf-8"))
        trades_json = json.loads(Path(f"localization/{lang}/trades.json").read_text(encoding="utf-8"))
        signals = json.loads(Path(f"localization/{lang}/signals.json").read_text(encoding="utf-8"))
        assert set(wallet["tabs"]) == {"overview", "spot", "futures"}
        from ui.pages.trades_page import HISTORY_COLUMNS

        assert set(HISTORY_COLUMNS) <= set(trades_json["history_cols"])
        for target in ("telegram", "whatsapp", "x", "email", "rubika", "eitaa", "bale"):
            assert signals["share"][f"to_{target}"]
