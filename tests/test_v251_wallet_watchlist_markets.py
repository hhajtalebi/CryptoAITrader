"""
آزمون‌های نسخهٔ ۲.۵.۱ — نمایش‌ندادن دارایی کیف پول، واچ‌لیستی که ذخیره
نمی‌شد، منوی کلیک راست بازارها، ترتیب «ارزش بازار + حجم» و قیمت تتری دقیق.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from app.exceptions.errors import AuthenticationError, RateLimitError


# ---------------------------------------------------------------------------
# LBank اسپات — امضا در سرآیند + مسیرهای جایگزین موجودی
# ---------------------------------------------------------------------------
def _client_with(handler):
    from market.providers.lbank.rest_client import LBankRestClient

    client = LBankRestClient(api_key="key-1", api_secret="secret-1")
    client._client = httpx.AsyncClient(
        base_url="https://api.lbkex.com", transport=httpx.MockTransport(handler)
    )
    return client


def test_signed_spot_request_sends_signature_headers() -> None:
    """
    علت اصلی «هیچ دارایی نمایش داده نمی‌شود»: timestamp/signature_method/
    echostr باید مثل کتابخانهٔ رسمی LBank در سرآیند هم باشند.
    """
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = dict(request.headers)
        seen["body"] = dict(httpx.QueryParams(request.content.decode()))
        return httpx.Response(200, json={"result": "true", "error_code": 0, "data": []})

    client = _client_with(handler)
    asyncio.run(client.post_signed("/v2/supplement/user_info_account.do"))
    headers, body = seen["headers"], seen["body"]
    assert headers["timestamp"] == body["timestamp"]
    assert headers["echostr"] == body["echostr"] and 30 <= len(body["echostr"]) <= 40
    assert headers["signature_method"] == "HmacSHA256"
    assert body["api_key"] == "key-1" and body["sign"]
    # امضا روی همهٔ پارامترها به‌جز sign است
    expected = client._build_signature({k: v for k, v in body.items() if k != "sign"})
    assert body["sign"] == expected


def test_spot_rows_accept_all_three_payload_formats() -> None:
    from market.providers.lbank.provider import LBankProvider

    supplement = [{"coin": "usdt", "usableAmt": "10", "freezeAmt": "2", "assetAmt": "12"},
                  {"coin": "doge", "usableAmt": "0", "freezeAmt": "0"}]
    account = {"canTrade": True, "balances": [{"asset": "btc", "free": "0.5", "locked": "0.1"}]}
    legacy = {"free": {"eth": "1.5", "usdt": "0"}, "freeze": {"eth": "0.5"}, "asset": {"eth": "2"},
              "toBtc": {"eth": "0.07"}}
    assert LBankProvider._spot_rows(supplement) == {"USDT": {"free": 10.0, "locked": 2.0, "total": 12.0}}
    assert LBankProvider._parse_balances(account) == {"BTC": pytest.approx(0.6)}
    assert LBankProvider._parse_spot_details(legacy)["ETH"] == {"free": 1.5, "locked": 0.5, "total": 2.0}
    # قالب قدیمی درون data هم
    assert LBankProvider._parse_balances({"data": legacy}) == {"ETH": 2.0}


def _provider(responses: dict[str, Any]):
    from market.providers.lbank.provider import LBankProvider

    provider = LBankProvider.__new__(LBankProvider)
    provider.last_spot_details = {}
    provider.last_futures_details = {}
    provider.last_sync_report = {}
    calls: list[str] = []

    async def post_signed(endpoint, params=None):  # noqa: ANN001, ARG001
        calls.append(endpoint)
        value = responses[endpoint]
        if isinstance(value, Exception):
            raise value
        return value

    async def post_contract_signed(endpoint, params=None):  # noqa: ANN001
        calls.append(f"{endpoint}:{params['asset']}")
        value = responses.get(f"contract:{params['asset']}", AuthenticationError("no contract"))
        if isinstance(value, Exception):
            raise value
        return value

    provider._client = SimpleNamespace(post_signed=post_signed, post_contract_signed=post_contract_signed,
                                       has_credentials=True)
    return provider, calls


def test_spot_balance_falls_back_to_next_endpoint() -> None:
    """کلید فقط‌خواندنی: اولین مسیر «بدون مجوز»، مسیر دوم (user_info.do) جواب می‌دهد."""
    from market.providers.lbank.constants import LBankEndpoints

    provider, calls = _provider({
        LBankEndpoints.USER_INFO_ACCOUNT: AuthenticationError("denied", details={"error_code": 10022}),
        LBankEndpoints.USER_INFO_LEGACY: {"free": {"usdt": "25"}, "freeze": {"usdt": "5"}, "asset": {"usdt": "30"}},
        LBankEndpoints.USER_INFO: [],
    })
    balances = asyncio.run(provider.get_account_balance())
    assert balances == {"USDT": 30.0}
    assert provider.last_spot_details["USDT"]["free"] == 25.0
    assert calls == [LBankEndpoints.USER_INFO_ACCOUNT, LBankEndpoints.USER_INFO_LEGACY]
    report = provider.last_sync_report["spot"]
    assert report["ok"] and report["endpoint"] == LBankEndpoints.USER_INFO_LEGACY and report["assets"] == 1


def test_spot_rate_limit_does_not_try_other_endpoints() -> None:
    from market.providers.lbank.constants import LBankEndpoints

    provider, calls = _provider({LBankEndpoints.USER_INFO_ACCOUNT: RateLimitError("slow")})
    with pytest.raises(RateLimitError):
        asyncio.run(provider.get_account_balance())
    assert calls == [LBankEndpoints.USER_INFO_ACCOUNT]
    assert provider.last_sync_report["spot"]["ok"] is False


def test_spot_all_endpoints_fail_reports_first_error() -> None:
    from market.providers.lbank.constants import LBankEndpoints

    first = AuthenticationError("bad signature", details={"error_code": 10007})
    provider, _calls = _provider({
        LBankEndpoints.USER_INFO_ACCOUNT: first,
        LBankEndpoints.USER_INFO_LEGACY: AuthenticationError("x"),
        LBankEndpoints.USER_INFO: AuthenticationError("y"),
    })
    with pytest.raises(AuthenticationError) as info:
        asyncio.run(provider.get_account_balance())
    assert info.value is first
    assert "10007" in provider.last_sync_report["spot"]["error"]


def test_futures_ctp_style_fields_are_recognised() -> None:
    """نام فیلدهای `prv/account` مستند نیست؛ نام‌های شبیه CTP با حدس شناخته می‌شوند."""
    from market.providers.lbank.provider import LBankProvider

    payload = {"accountID": "1", "balance": "100", "available": "80", "frozenMargin": "5",
               "positionMargin": "15", "positionProfit": "2.5", "clearCurrency": "USDT"}
    usdt = LBankProvider._parse_futures_details(payload, "USDT")["USDT"]
    assert usdt["available"] == 80.0
    assert usdt["frozen"] == 5.0
    assert usdt["margin"] == 15.0
    assert usdt["unrealized"] == 2.5
    assert usdt["wallet"] == 100.0
    assert usdt["total"] == pytest.approx(102.5)
    # قالب تودرتو {"account": {...}}
    nested = LBankProvider._parse_futures_details({"account": {"availableBalance": "7"}}, "USDT")
    assert nested["USDT"]["available"] == 7.0


def test_futures_report_lists_fields_when_nothing_recognised() -> None:
    provider, _calls = _provider({
        "contract:USDT": {"weirdA": "1", "weirdB": {"inner": "2"}},
        "contract:USDC": AuthenticationError("none"),
        "contract:BTC": AuthenticationError("none"),
        "contract:ETH": AuthenticationError("none"),
    })
    assert asyncio.run(provider.fetch_futures_balance()) == {}
    report = provider.last_sync_report["futures"]
    assert report["ok"] is True and report["note"] == "no_positive_fields"
    assert {"weirdA", "weirdB", "inner"} <= set(report["fields"])


# ---------------------------------------------------------------------------
# سرویس حساب — شکست اسپات دیگر فیوچرز را نمی‌برد
# ---------------------------------------------------------------------------
def _service():
    from app.core.exchange_account_service import ExchangeAccountService

    repo = MagicMock()
    repo.get_account.return_value = {"id": 1, "exchange": "lbank"}
    service = ExchangeAccountService.__new__(ExchangeAccountService)
    service._repository = repo
    service.credentials = lambda _id: {"api_key": "key-XYZ", "api_secret": "sec-XYZ"}
    return service, repo


def test_spot_failure_keeps_futures_balance() -> None:
    service, repo = _service()

    class Provider:
        last_spot_details: dict = {}
        last_futures_details = {"USDT": {"total": 50.0, "available": 40.0}}
        last_sync_report = {"futures": {"ok": True, "endpoint": "/cfd", "assets": 1, "error": ""}}

        async def get_account_balance(self):
            raise AuthenticationError("denied key-XYZ (code 10022)")

        async def get_futures_balance(self):
            return {"USDT": 50.0}

        async def close(self):
            return None

    result = asyncio.run(service.sync_balances(1, lambda *_a: Provider(), price_lookup=lambda _a: 1.0))
    assert result["futures"] == {"USDT": 50.0}
    details = repo.update_balances.call_args.kwargs["details"]
    spot_report = details["report"]["spot"]
    assert spot_report["ok"] is False and "10022" in spot_report["error"]
    assert "key-XYZ" not in spot_report["error"]  # کلید هرگز ذخیره نمی‌شود
    status = repo.set_status.call_args.kwargs
    assert status["status"] == "connected" and "10022" in status["error"]


def test_both_failing_records_error() -> None:
    service, repo = _service()

    class Provider:
        last_sync_report = {"futures": {"ok": False, "error": "x"}}

        async def get_account_balance(self):
            raise AuthenticationError("bad signature")

        async def get_futures_balance(self):
            return {}

        async def close(self):
            return None

    assert asyncio.run(service.sync_balances(1, lambda *_a: Provider())) == {}
    repo.update_balances.assert_not_called()
    assert repo.set_status.call_args.kwargs["status"] == "error"


# ---------------------------------------------------------------------------
# واچ‌لیست — ذخیره بدون جدول نمادهای پرشده
# ---------------------------------------------------------------------------
@pytest.fixture()
def symbols(database):  # noqa: ANN001, ANN201
    from app.database.repositories.symbol_repository import SymbolRepository

    return SymbolRepository(database)


def test_add_to_watchlist_creates_missing_symbol_record(symbols) -> None:  # noqa: ANN001
    """علت «واچ‌لیست همیشه خالی»: جدول symbols هرگز پر نمی‌شد."""
    assert symbols.add_to_watchlist("BTC/USDT", "lbank") is True
    assert symbols.add_to_watchlist("btc_usdt", "lbank") is False  # تکراری، شکل دیگر نام
    assert symbols.get_watchlist() == ["BTC/USDT"]
    record = symbols.get_by_symbol("BTC/USDT", "lbank")
    assert record.base_asset == "BTC" and record.quote_asset == "USDT"
    assert symbols.is_in_watchlist("BTC/USDT")


def test_add_without_exchange_and_remove_any_exchange(symbols) -> None:  # noqa: ANN001
    assert symbols.add_to_watchlist("ETH/USDT") is True
    assert symbols.get_watchlist() == ["ETH/USDT"]
    # برداشتن با صرافی دیگر هم کار می‌کند (ستاره نباید گیر کند)
    assert symbols.remove_from_watchlist("ETH/USDT", "lbank") is True
    assert symbols.get_watchlist() == []
    assert symbols.remove_from_watchlist("ETH/USDT") is False


def test_symbol_sync_after_on_demand_record_keeps_watchlist(symbols) -> None:  # noqa: ANN001
    from app.core.models import SymbolInfo

    symbols.add_to_watchlist("SOL/USDT", "lbank")
    symbols.sync_symbols("lbank", [SymbolInfo("SOL/USDT", "sol_usdt", "SOL", "USDT", 3, 2)])
    assert symbols.get_watchlist() == ["SOL/USDT"]
    assert symbols.get_by_symbol("SOL/USDT", "lbank").price_precision == 3


def _watch_controller(repo):  # noqa: ANN001
    from ui.controllers.main_controller import MainController

    events: list[Any] = []

    class Fake:
        set_watchlist_membership = MainController.set_watchlist_membership
        _coin_watchlist_toggled = MainController._coin_watchlist_toggled
        _on_watchlist_toggled = MainController._on_watchlist_toggled
        add_to_watchlist = MainController.add_to_watchlist

        def __init__(self) -> None:
            self.app = SimpleNamespace(settings=SimpleNamespace(active_exchange="lbank"),
                                       symbol_repository=repo)
            self.tr_ = SimpleNamespace(tr=lambda key, **kw: key)
            self.markets = SimpleNamespace(set_watchlist=lambda s: events.append(("stars", list(s))),
                                           selected_symbol=lambda: "XRP/USDT")
            self.status = lambda text: events.append(("status", text))
            self._toast = lambda text, level="info": events.append(("toast", text, level))
            self.refresh_watchlist_panel = lambda: events.append(("panel",))
            self._update_streamed_symbols = lambda: events.append(("stream",))
            self.refresh_dashboard = lambda: events.append(("dashboard",))

    return Fake(), events


def test_modal_add_to_watchlist_really_saves(symbols) -> None:  # noqa: ANN001
    """مدال قبلاً add_to_watchlist(symbol) را بدون صرافی صدا می‌زد → TypeError بی‌صدا."""
    controller, events = _watch_controller(symbols)
    controller._coin_watchlist_toggled("BTC/USDT", True)
    assert symbols.get_watchlist() == ["BTC/USDT"]
    assert ("stars", ["BTC/USDT"]) in events and ("panel",) in events
    assert ("toast", "markets.added_to_watchlist", "success") in events
    controller._coin_watchlist_toggled("BTC/USDT", False)
    assert symbols.get_watchlist() == []


def test_toolbar_button_and_star_use_same_path(symbols) -> None:  # noqa: ANN001
    controller, events = _watch_controller(symbols)
    controller.add_to_watchlist()
    controller._on_watchlist_toggled("ETH/USDT", True)
    assert symbols.get_watchlist() == ["XRP/USDT", "ETH/USDT"]
    assert events.count(("panel",)) == 2


# ---------------------------------------------------------------------------
# ترتیب ارزش بازار و قیمت تتری
# ---------------------------------------------------------------------------
def test_market_rank_orders_majors_then_turnover() -> None:
    from market.market_rank import sort_by_market_value

    rows = [
        {"symbol": "MEME/USDT", "price": 0.00001, "volume": 9e11, "quote_volume": 9e6},
        {"symbol": "ETH/USDT", "price": 3000, "volume": 1e5, "quote_volume": 3e8},
        {"symbol": "NEWX/USDT", "price": 1, "volume": 1, "quote_volume": 5e7},
        {"symbol": "BTC/USDT", "price": 60000, "volume": 1e3, "quote_volume": 6e7},
        {"symbol": "SOL/USDT", "price": 150, "volume": 1, "quote_volume": 1},
    ]
    order = [r["symbol"].split("/")[0] for r in sort_by_market_value(rows)]
    assert order == ["BTC", "ETH", "SOL", "NEWX", "MEME"]


def test_price_decimals_keep_significant_digits() -> None:
    from market.market_rank import price_decimals

    assert price_decimals(64231.5) == 2
    assert price_decimals(12.3456) == 4
    assert f"{0.000012345:.{price_decimals(0.000012345)}f}" == "0.00001234"
    assert price_decimals(0.00000001234) >= 11
    assert price_decimals(0.5, precision=5) == 5  # دقت صرافی مقدم است


QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)


@pytest.fixture()
def fa(qt_application):  # noqa: ANN001, ANN201, ARG001
    from localization import Translator

    translator = Translator("fa")
    translator.load()
    return translator


@pytest.fixture()
def en(qt_application):  # noqa: ANN001, ANN201, ARG001
    from localization import Translator

    translator = Translator("en")
    translator.load()
    return translator


ROWS = [
    {"symbol": "TINY/USDT", "price": 0.000012345, "volume": 9e11, "change_percent": 1.0, "high": 0.00002},
    {"symbol": "ETH/USDT", "price": 3000.0, "volume": 5e4, "quote_volume": 1.5e8, "change_percent": 2.0, "high": 3100.0},
    {"symbol": "BTC/USDT", "price": 60000.0, "volume": 1200, "quote_volume": 7.2e7, "change_percent": -1.0,
     "high": 61000.0, "price_precision": 2},
    {"symbol": "ETH/BTC", "price": 0.05, "volume": 100, "change_percent": 0.5, "high": 0.051},
]


def _markets(translator):  # noqa: ANN001, ANN202
    from ui.pages.markets_page import MarketsPage

    page = MarketsPage(translator)
    page.quote_toggle.set_current("USDT", emit=False)
    page.set_rows([dict(r) for r in ROWS])
    return page


def _symbols_in_table(page) -> list[str]:  # noqa: ANN001
    from ui.pages.markets_page import COL_SYMBOL

    return [page.table.item(r, COL_SYMBOL).text() for r in range(page.table.rowCount())]


def test_markets_default_order_is_market_value(en) -> None:  # noqa: ANN001
    page = _markets(en)
    assert _symbols_in_table(page) == ["BTC/USDT", "ETH/USDT", "TINY/USDT"]


def test_markets_prices_are_exact_usdt(en) -> None:  # noqa: ANN001
    from ui.pages.markets_page import COL_PRICE_USD, COL_VOLUME

    page = _markets(en)
    texts = {page.table.item(r, 1).text(): page.table.item(r, COL_PRICE_USD).text()
             for r in range(page.table.rowCount())}
    assert texts["BTC/USDT"] == "60,000.00"
    assert texts["TINY/USDT"] == "0.00001234"  # قبلاً ۰٫۰۰۰۰۱۲۳۵ با ۸ رقم ثابت/گرد
    # ستون حجم = ارزش معاملات به تتر، فشرده
    volumes = {page.table.item(r, 1).text(): page.table.item(r, COL_VOLUME).text()
               for r in range(page.table.rowCount())}
    assert volumes["ETH/USDT"] == "150.00M"
    # جفت ETH/BTC در زبانهٔ BTC: قیمت به تتر تبدیل می‌شود (۰٫۰۵ × ۶۰٬۰۰۰)
    page._on_quote_changed("BTC")
    row = _symbols_in_table(page).index("ETH/BTC")
    item = page.table.item(row, COL_PRICE_USD)
    assert item.text() == "3,000.00"
    assert "BTC" in item.toolTip()


def test_live_update_uses_usdt_conversion(en) -> None:  # noqa: ANN001
    from ui.pages.markets_page import COL_PRICE_USD

    page = _markets(en)
    page._on_quote_changed("BTC")
    page.apply_price_updates({"BTC/USDT": {"price": 50000.0, "tick_direction": -1}})
    page.apply_price_updates({"ETH/BTC": {"price": 0.06, "tick_direction": 1}})
    row = _symbols_in_table(page).index("ETH/BTC")
    # ۰٫۰۶ × ۵۰٬۰۰۰ (قیمت زندهٔ BTC با اینکه ردیفش در زبانهٔ BTC پنهان است)
    assert page.table.item(row, COL_PRICE_USD).text() == "3,000.00"


def test_context_menu_adds_to_watchlist(fa) -> None:  # noqa: ANN001
    """کلیک راست روی نماد ← منو؛ گزینهٔ اول افزودن به واچ‌لیست است."""
    page = _markets(fa)
    toggled: list[tuple[str, bool]] = []
    analysed: list[str] = []
    page.watchlist_toggled.connect(lambda s, a: toggled.append((s, a)))
    page.analyze_requested.connect(analysed.append)
    menu = page.build_context_menu("ETH/USDT")
    actions = [a for a in menu.actions() if not a.isSeparator()]
    keys = [a.data() for a in actions]
    assert keys[0] == "watchlist"
    assert {"details", "analyze", "signal", "alert", "copy_symbol", "copy_price"} <= set(keys)
    actions[0].trigger()
    assert toggled == [("ETH/USDT", True)]
    next(a for a in actions if a.data() == "analyze").trigger()
    assert analysed == ["ETH/USDT"]
    # پس از افزودن، همان گزینه «برداشتن» است
    page.set_watchlist(["ETH/USDT"])
    menu2 = page.build_context_menu("ETH/USDT")
    first = [a for a in menu2.actions() if not a.isSeparator()][0]
    assert fa.tr("markets.remove_from_watchlist") in first.text()


def test_context_menu_policy_is_enabled(fa) -> None:  # noqa: ANN001
    from PySide6.QtCore import Qt

    page = _markets(fa)
    assert page.table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


def test_copy_symbol_action_uses_clipboard(fa) -> None:  # noqa: ANN001
    from PySide6.QtGui import QGuiApplication

    page = _markets(fa)
    menu = page.build_context_menu("BTC/USDT")
    for action in menu.actions():
        if action.data() == "copy_price":
            action.trigger()
    assert QGuiApplication.clipboard().text() == "60000.00"


# ---------------------------------------------------------------------------
# کیف پول — گزارش همگام‌سازی، فیلتر اسپات، همگام‌سازی خودکار
# ---------------------------------------------------------------------------
def test_wallet_report_panel_and_spot_filters(fa) -> None:  # noqa: ANN001
    from ui.pages.wallet_page import WalletPage

    page = WalletPage(fa)
    assert page.status_panel.isHidden()
    page.set_sync_report([("ok", "اسپات: ۳ دارایی"), ("error", "فیوچرز: خطا")], hint="راه‌حل")
    assert not page.status_panel.isHidden()
    assert "فیوچرز" in page.report_text() and page.status_hint.text() == "راه‌حل"

    rows = [
        {"asset": "USDT", "value": 120.0, "total_text": "120"},
        {"asset": "BTC", "value": 60.0, "total_text": "0.001"},
        {"asset": "DUST", "value": 0.2, "total_text": "5"},
    ]
    page.set_spot(rows, {"value": "180"})
    assert page.spot_table.rowCount() == 3
    page.hide_small_checkbox.setChecked(True)
    assert [r["asset"] for r in page._spot_rows] == ["USDT", "BTC"]
    page.spot_search.setText("bt")
    assert [r["asset"] for r in page._spot_rows] == ["BTC"]
    assert page.auto_sync_checkbox.isChecked()


def _report_controller(account: dict[str, Any]):  # noqa: ANN202
    from localization import Translator
    from ui.controllers.main_controller import MainController

    captured: dict[str, Any] = {}

    class Fake:
        _fill_wallet_report = MainController._fill_wallet_report
        _wallet_error_hint = MainController._wallet_error_hint
        _localize_exchange_message = MainController._localize_exchange_message

        def __init__(self) -> None:
            self.tr_ = Translator("en")
            self.tr_.load()
            self.wallet = SimpleNamespace(
                set_sync_report=lambda lines, hint: captured.update(lines=lines, hint=hint)
            )

    Fake()._fill_wallet_report(account, dict((account.get("extra_config") or {}).get("wallet_details") or {}))
    return captured


def test_wallet_report_explains_futures_permission() -> None:
    captured = _report_controller({
        "last_sync_at": "2026-09-24T10:00:00",
        "extra_config": {"wallet_details": {"report": {
            "spot": {"ok": True, "assets": 4, "endpoint": "/v2/user_info.do"},
            "futures": {"ok": False, "error": "AuthenticationError: no permission (code 10009)"},
        }}},
    })
    levels = [level for level, _ in captured["lines"]]
    assert levels == ["ok", "error"]
    assert "4 assets" in captured["lines"][0][1]
    assert "Contract" in captured["hint"]


def test_wallet_report_never_synced_error_shows_signature_hint() -> None:
    captured = _report_controller({"last_error": "LBank authentication failed: Invalid signature (10007)"})
    assert captured["lines"][0][0] == "error"
    assert "Secret" in captured["hint"]


def test_auto_sync_timer_and_silent_guard() -> None:
    from ui.controllers.main_controller import MainController

    calls: list[bool] = []

    class Fake:
        start_wallet_auto_sync = MainController.start_wallet_auto_sync
        _on_wallet_activated = MainController._on_wallet_activated
        WALLET_AUTO_SYNC_MS = MainController.WALLET_AUTO_SYNC_MS
        WALLET_STALE_SECONDS = MainController.WALLET_STALE_SECONDS

        def __init__(self) -> None:
            self.window = None
            self._wallet_timer = SimpleNamespace(start=lambda: calls.append("start"),
                                                 stop=lambda: calls.append("stop"))
            self.app = SimpleNamespace(settings=SimpleNamespace(get=lambda key, default=None: True))
            box = SimpleNamespace(blockSignals=lambda _b: None, setChecked=lambda _v: None)
            self.wallet = SimpleNamespace(auto_sync_checkbox=box)

        def sync_wallet(self, silent: bool = False) -> None:
            calls.append(silent)

    fake = Fake()
    fake.start_wallet_auto_sync()
    assert calls == ["start", True]
    assert MainController.WALLET_AUTO_SYNC_MS == 60_000
    fake._wallet_synced_at = __import__("time").monotonic()
    fake._on_wallet_activated()  # تازه است ← همگام‌سازی نمی‌شود
    assert calls == ["start", True]
    fake._wallet_synced_at -= 120
    fake._on_wallet_activated()
    assert calls[-1] is True and len(calls) == 3


def test_localization_keys_exist_in_both_languages() -> None:
    root = Path(__file__).resolve().parents[1] / "localization"
    needed = {
        "wallet": ["auto_sync", "auto_sync_tip", "spot_tab.search", "spot_tab.hide_small",
                   "report.ok", "report.failed", "report.unknown_fields", "report.never",
                   "hint.permission", "hint.futures_permission", "hint.signature", "hint.network"],
        "markets": ["sort_market_cap", "turnover_usdt", "menu.details", "menu.analyze",
                    "menu.signal", "menu.copy_symbol", "menu.copy_price"],
        "watchlist": ["save_failed"],
    }
    for lang in ("fa", "en"):
        for fname, keys in needed.items():
            data = json.loads((root / lang / f"{fname}.json").read_text(encoding="utf-8"))
            for key in keys:
                node: Any = data
                for part in key.split("."):
                    node = node[part]
                assert isinstance(node, str) and node, (lang, fname, key)


# ---------------------------------------------------------------------------
# مهاجرت یک‌بارهٔ ترتیب پیش‌فرض بازارها
# ---------------------------------------------------------------------------
class _Settings:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = dict(values)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any, *, notify: bool = True) -> None:  # noqa: ARG002
        self.values[key] = value


def _apply_sort(values: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    from ui.controllers.main_controller import MainController

    chosen: list[str] = []
    modes = ["market_cap", "value", "gainers"]
    combo = SimpleNamespace(findData=modes.index, currentIndex=lambda: 0,
                            setCurrentIndex=lambda i: chosen.append(modes[i]))
    fake = SimpleNamespace(app=SimpleNamespace(settings=_Settings(values)),
                           markets=SimpleNamespace(sort_combo=combo))
    MainController._apply_display_settings(fake)
    return (chosen[-1] if chosen else "market_cap"), fake.app.settings.values


def test_old_default_value_sort_migrates_once() -> None:
    """کاربرِ قبلی با پیش‌فرض «value» باید BTC/ETH را بالا ببیند (خواستهٔ ۴)."""
    from ui.controllers.main_controller import MARKETS_SORT_MIGRATION_KEY

    mode, stored = _apply_sort({"ui.markets_sort": "value"})
    assert mode == "market_cap" and stored["ui.markets_sort"] == "market_cap"
    assert stored[MARKETS_SORT_MIGRATION_KEY] is True
    # پس از مهاجرت، انتخاب دوبارهٔ «value» محترم است
    mode, _ = _apply_sort({"ui.markets_sort": "value", MARKETS_SORT_MIGRATION_KEY: True})
    assert mode == "value"
    # انتخاب صریح دیگر دست نمی‌خورد
    mode, stored = _apply_sort({"ui.markets_sort": "gainers"})
    assert mode == "gainers" and stored["ui.markets_sort"] == "gainers"


# ---------------------------------------------------------------------------
# فیوچرز: HTTP 403 از Cloudflare (گزارش کاربر پس از 2.5.1)
# ---------------------------------------------------------------------------
def _response(status: int, body: str, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, text=body, headers=headers or {},
                          request=httpx.Request("POST", "https://lbkperp.lbank.com/x"))


def test_cloudflare_403_is_classified_with_code() -> None:
    from app.exceptions.errors import AccessBlockedError
    from market.providers.lbank.rest_client import LBankRestClient

    client = LBankRestClient(api_key="key-1", api_secret="secret-1")
    page = "<html><title>Attention Required! | Cloudflare</title>Error 1020 Access denied</html>"
    with pytest.raises(AccessBlockedError) as info:
        client._handle_response(_response(403, page, {"server": "cloudflare", "cf-ray": "8abc-FRA"}),
                                "/cfd/openApi/v1/prv/account", contract=True)
    error = info.value
    assert error.details["cf_code"] == "1020" and error.details["cf_ray"] == "8abc-FRA"
    assert "Cloudflare 1020" in str(error) and "firewall" in str(error)
    assert "key-1" not in str(error) and "secret-1" not in str(error)


def test_cloudflare_country_block_and_plain_text_code() -> None:
    from app.exceptions.errors import AccessBlockedError
    from market.providers.lbank.rest_client import LBankRestClient

    client = LBankRestClient(api_key="k", api_secret="s")
    with pytest.raises(AccessBlockedError) as info:
        client._handle_response(_response(403, "error code: 1009", {"server": "cloudflare"}), "/x", contract=True)
    assert "country/region" in str(info.value)
    # 1015 = محدودیت نرخ Cloudflare ← مکث، نه «مسدود»
    with pytest.raises(RateLimitError):
        client._handle_response(_response(403, "error code: 1015", {"server": "cloudflare"}), "/x",
                                contract=True)
    # 403 بدون نشان Cloudflare هم «رد دسترسی» است نه «قطعی شبکه»
    with pytest.raises(AccessBlockedError) as info:
        client._handle_response(_response(403, "Forbidden", {"server": "nginx"}), "/x", contract=True)
    assert "IP whitelist" in str(info.value)


def test_403_with_lbank_json_uses_exchange_error_codes() -> None:
    """اگر بدنهٔ 403 پاسخ JSON خود صرافی باشد، کد خطای صرافی مبنا است."""
    from market.providers.lbank.rest_client import LBankRestClient

    client = LBankRestClient(api_key="k", api_secret="s")
    body = json.dumps({"error_code": 10008, "success": False, "result": "", "msg": "key"})
    with pytest.raises(AuthenticationError):
        client._handle_response(_response(403, body, {"server": "cloudflare"}), "/x", contract=True)


def test_blocked_contract_request_is_not_retried_and_uses_browser_headers() -> None:
    from app.exceptions.errors import AccessBlockedError
    from market.providers.lbank.rest_client import LBankRestClient

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(403, text="error code: 1010", headers={"server": "cloudflare"})

    client = LBankRestClient(api_key="k", api_secret="s")

    async def run() -> None:
        real = await client._contract_client()
        client._contract_http = httpx.AsyncClient(base_url="https://lbkperp.lbank.com",
                                                  headers=dict(real.headers),
                                                  transport=httpx.MockTransport(handler))
        await real.aclose()
        with pytest.raises(AccessBlockedError):
            await client.post_contract_signed("/cfd/openApi/v1/prv/account", {"asset": "USDT"})
        await client._contract_http.aclose()

    asyncio.run(run())
    assert len(calls) == 1  # بدون تکرار
    headers = calls[0].headers
    assert headers["user-agent"].startswith("Mozilla/5.0") and "CryptoAITrader" not in headers["user-agent"]
    assert headers["content-type"] == "application/json" and headers["echostr"]


def test_futures_loop_stops_after_block() -> None:
    from app.exceptions.errors import AccessBlockedError

    blocked = AccessBlockedError("HTTP 403 blocked by Cloudflare 1009 — access from your country/region "
                                 "is blocked while calling /cfd/openApi/v1/prv/account")
    provider, calls = _provider({"contract:USDT": blocked, "contract:USDC": {"available": "5"}})
    with pytest.raises(AccessBlockedError):
        asyncio.run(provider.fetch_futures_balance())
    assert len(calls) == 1  # USDC/BTC/ETH دیگر پرسیده نمی‌شوند
    assert "Cloudflare 1009" in provider.last_sync_report["futures"]["error"]


def test_blocked_hint_says_not_a_key_problem() -> None:
    from localization import Translator
    from ui.controllers.main_controller import MainController

    fake = SimpleNamespace(tr_=Translator("en"))
    fake.tr_.load()
    hint = MainController._wallet_error_hint(
        fake, "AccessBlockedError: HTTP 403 blocked by Cloudflare 1020 — access denied by firewall rule",
        futures=True)
    assert "Cloudflare" in hint and "not the problem" in hint
    region = MainController._wallet_error_hint(
        fake, "HTTP 403 blocked by Cloudflare 1009 — access from your country/region is blocked", futures=True)
    assert "1009" in region
    # همان متن قدیمیِ کاربر («NetworkError: HTTP 403 …») هم راهنمای درست می‌گیرد
    old = MainController._wallet_error_hint(
        fake, "NetworkError: HTTP 403 while calling /cfd/openApi/v1/prv/account", futures=True)
    assert old == hint
