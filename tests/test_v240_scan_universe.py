"""
آزمون‌های نسخهٔ ۲.۴.۰ — پویش کل بازار و منبع سیگنال‌گیری خودکار.

پوشش:
    * سازندهٔ جهان پویش (`signals/scan_universe.py`) و پالایش هوشمند
    * پویشگر: حالت «کل صرافی»، پالایش و پس‌فراخوان `on_signal`
    * زمان‌بند خودکار: منبع found/market/both و `seed_focus`
    * کلیدهای تنظیمات و ترجمه‌ها
    * صفحهٔ سیگنال: دامنهٔ پویش، پالایش، منبع خودکار و برآورد زمان
"""

from __future__ import annotations

import asyncio
import json
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config.defaults import DEFAULT_SETTINGS, SettingKey
from app.core.constants import SignalDirection
from app.core.models import TradingSignal
from signals.auto_scanner import (
    MAX_FOCUS_SIZE,
    SOURCE_BOTH,
    SOURCE_FOUND,
    SOURCE_MARKET,
    AutoScanConfig,
    AutoScanScheduler,
    normalize_source,
)
from signals.scan_universe import (
    UNIVERSE_ALL,
    UNIVERSE_TOP,
    UniverseFilter,
    build_universe,
    is_leveraged_token,
    is_stable_pair,
    normalize_universe,
    priority_score,
    split_symbol,
)
from signals.scanner import MarketScanner

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _ticker(symbol: str, turnover: float, price: float = 1.0, change: float = 0.0):
    return types.SimpleNamespace(
        symbol=symbol, turnover_24h=turnover, last_price=price, change_percent=change
    )


def _signal(symbol: str, confidence: int, direction=SignalDirection.LONG) -> TradingSignal:
    return TradingSignal(
        symbol=symbol, exchange="test", direction=direction,
        confidence=confidence, risk_reward=2.0, leverage=3,
    )


class FakeSignal:
    def __init__(self, symbol: str, confidence: float, direction: str = "LONG") -> None:
        self.symbol = symbol
        self.confidence = confidence
        self.direction = type("D", (), {"name": direction})()


# ================================================================ جهان پویش
def test_symbol_helpers() -> None:
    assert split_symbol("btc/usdt") == ("BTC", "USDT")
    assert split_symbol("eth_btc") == ("ETH", "BTC")
    assert split_symbol("XRPUSDT") == ("XRPUSDT", "")
    assert normalize_universe("ALL") == UNIVERSE_ALL
    assert normalize_universe("nonsense") == UNIVERSE_TOP
    assert normalize_universe(None) == UNIVERSE_TOP
    assert is_stable_pair("USDC/USDT")
    assert not is_stable_pair("BTC/USDT")


def test_leveraged_detection_avoids_real_tokens() -> None:
    """BTC3L و ETHUP اهرمی‌اند؛ SYRUP (توکن واقعی) نباید حذف شود."""
    assert is_leveraged_token("BTC3L/USDT")
    assert is_leveraged_token("ETH5S/USDT")
    assert is_leveraged_token("ETHUP/USDT", {"ETH", "BTC"})
    assert not is_leveraged_token("SYRUP/USDT", {"ETH", "BTC"})
    assert not is_leveraged_token("JUP/USDT")
    assert not is_leveraged_token("1000SATS/USDT")


def test_priority_prefers_liquid_and_moving_markets() -> None:
    calm = _ticker("A/USDT", 1_000_000, change=0.0)
    moving = _ticker("B/USDT", 1_000_000, change=20.0)
    thin = _ticker("C/USDT", 1_000, change=20.0)
    assert priority_score(moving) > priority_score(calm) > priority_score(thin)
    assert priority_score(types.SimpleNamespace()) == 0.0


def test_build_universe_all_covers_every_exchange_symbol() -> None:
    """حالت «کل صرافی» نمادهای بدون تیکر را هم (در انتهای صف) پوشش می‌دهد."""
    tickers = [_ticker("A/USDT", 100), _ticker("B/USDT", 5000)]
    symbols = [types.SimpleNamespace(symbol=s) for s in ("A/USDT", "B/USDT", "C/USDT")]
    result = build_universe(tickers, symbols, mode="all", filters=UniverseFilter.create(smart=False))
    assert result == ["B/USDT", "A/USDT", "C/USDT"]


def test_build_universe_all_ignores_limit() -> None:
    tickers = [_ticker(f"S{i}/USDT", 1000 + i) for i in range(300)]
    result = build_universe(tickers, [], mode="all", limit=10)
    assert len(result) == 300


def test_build_universe_top_respects_limit_and_order() -> None:
    tickers = [_ticker(f"S{i}/USDT", 1000 * (i + 1)) for i in range(20)]
    result = build_universe(tickers, [], mode="top", limit=5)
    assert result == [f"S{i}/USDT" for i in (19, 18, 17, 16, 15)]


def test_smart_filter_drops_dead_stable_and_leveraged() -> None:
    tickers = [
        _ticker("BTC/USDT", 9_000_000, price=60000),
        _ticker("ETH/USDT", 5_000_000, price=3000),
        _ticker("DEAD/USDT", 0, price=1),
        _ticker("ZERO/USDT", 500, price=0),
        _ticker("USDC/USDT", 8_000_000),
        _ticker("BTC3L/USDT", 400_000),
        _ticker("ETHUP/USDT", 300_000),
        _ticker("SYRUP/USDT", 200_000),
    ]
    smart = build_universe(tickers, ["LISTED/USDT"], mode="all", filters=UniverseFilter.create())
    assert smart == ["BTC/USDT", "ETH/USDT", "SYRUP/USDT"]

    raw = build_universe(tickers, [], mode="all", filters=UniverseFilter.create(smart=False))
    assert {"DEAD/USDT", "USDC/USDT", "BTC3L/USDT"} <= set(raw)


def test_min_turnover_and_quote_filters() -> None:
    tickers = [
        _ticker("A/USDT", 50_000), _ticker("B/USDT", 2_000_000), _ticker("C/BTC", 3_000_000),
    ]
    rules = UniverseFilter.create(min_turnover=1_000_000, quotes=["usdt"])
    assert build_universe(tickers, ["D/USDT"], mode="all", filters=rules) == ["B/USDT"]


def test_universe_falls_back_to_symbol_list_without_tickers() -> None:
    """اگر تیکرها نرسند، فهرست خام نمادها پوشش کامل را حفظ می‌کند."""
    result = build_universe([], ["A/USDT", "B/USDT", "USDC/USDT"], mode="all")
    assert result == ["A/USDT", "B/USDT"]


def test_universe_filter_create_sanitises_input() -> None:
    rules = UniverseFilter.create(min_turnover="bad", smart=0, quotes=[" usdt ", ""])
    assert rules.min_turnover == 0.0
    assert rules.smart is False
    assert rules.quotes == ("USDT",)


# ================================================================ پویشگر
class _Market:
    def __init__(self) -> None:
        self.symbol_calls = 0

    async def get_all_tickers(self):
        return [
            _ticker("S1/USDT", 1000), _ticker("S2/USDT", 3000),
            _ticker("S3/USDT", 2000), _ticker("S4/USDT", 0),
        ]

    async def get_symbols(self):
        self.symbol_calls += 1
        return [types.SimpleNamespace(symbol=f"S{i}/USDT") for i in range(1, 8)]


class _Engine:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, symbol, frames=None):
        self.calls.append(symbol)
        index = int(symbol[1 : symbol.index("/")])
        return _signal(symbol, 40 + index * 5)


def test_scanner_top_path_unchanged() -> None:
    engine = _Engine()
    scanner = MarketScanner(_Market(), engine, concurrency=1)
    asyncio.run(scanner.scan(limit=2))
    assert engine.calls == ["S2/USDT", "S3/USDT"]


def test_scanner_all_universe_scans_whole_exchange() -> None:
    """بدون پالایش، همهٔ هفت نماد صرافی پویش می‌شوند (نه فقط limit)."""
    engine = _Engine()
    market = _Market()
    scanner = MarketScanner(market, engine, concurrency=2)
    result = asyncio.run(
        scanner.scan(limit=2, universe="all", filters=UniverseFilter.create(smart=False))
    )
    assert sorted(engine.calls) == [f"S{i}/USDT" for i in range(1, 8)]
    assert market.symbol_calls == 1
    assert result.scanned == 7


def test_scanner_all_universe_with_smart_filter_skips_dead_markets() -> None:
    engine = _Engine()
    scanner = MarketScanner(_Market(), engine, concurrency=1)
    asyncio.run(scanner.scan(universe="all", filters=UniverseFilter.create()))
    # S4 گردش صفر دارد؛ S5..S7 تیکری ندارند و با پالایش هوشمند فعال نیستند
    assert engine.calls == ["S2/USDT", "S3/USDT", "S1/USDT"]


def test_scanner_on_signal_reports_each_accepted_signal() -> None:
    engine = _Engine()
    seen: list[str] = []
    scanner = MarketScanner(_Market(), engine, concurrency=1)
    result = asyncio.run(
        scanner.scan(
            ["S1/USDT", "S2/USDT", "S3/USDT"], min_confidence=50, on_signal=lambda s: seen.append(s.symbol)
        )
    )
    # S1 → 45٪، زیر آستانه
    assert seen == ["S2/USDT", "S3/USDT"]
    assert [s.symbol for s in result.signals] == ["S3/USDT", "S2/USDT"]


def test_scanner_on_signal_failure_does_not_break_scan() -> None:
    def boom(_signal):
        raise RuntimeError("ui died")

    scanner = MarketScanner(_Market(), _Engine(), concurrency=1)
    result = asyncio.run(scanner.scan(["S1/USDT", "S2/USDT"], on_signal=boom))
    assert len(result.signals) == 2


# ================================================================ زمان‌بند خودکار
def _config(**overrides) -> AutoScanConfig:
    values = dict(enabled=True, focus_interval=300, full_interval=1800, focus_size=3,
                  focus_min_confidence=50)
    values.update(overrides)
    return AutoScanConfig(**values).normalized()


def test_source_normalisation_and_defaults() -> None:
    assert normalize_source("MARKET") == SOURCE_MARKET
    assert normalize_source("junk") == SOURCE_BOTH
    config = AutoScanConfig()
    assert config.source == SOURCE_BOTH
    assert config.universe == "all"
    assert config.smart_filter is True
    assert MAX_FOCUS_SIZE == 100
    assert _config(focus_size=500).focus_size == 100


def test_found_mode_never_sweeps_and_waits_for_seed() -> None:
    scheduler = AutoScanScheduler(_config(source=SOURCE_FOUND))
    assert not scheduler.config.sweep_active
    assert scheduler.due(T0) is None
    assert scheduler.seconds_until_next(T0) == 0

    scheduler.seed_focus([FakeSignal("BTC/USDT", 80), FakeSignal("ETH/USDT", 60)], replace=True)
    job = scheduler.due(T0)
    assert job is not None and job.kind == "focus"
    assert job.symbols == ("BTC/USDT", "ETH/USDT")
    scheduler.start(job)
    scheduler.complete(job, [], T0)
    assert scheduler.due(T0 + timedelta(minutes=2)) is None
    assert scheduler.due(T0 + timedelta(hours=5)).kind == "focus"


def test_market_mode_only_sweeps() -> None:
    scheduler = AutoScanScheduler(_config(source=SOURCE_MARKET))
    scheduler.focus_symbols = ["BTC/USDT"]
    assert not scheduler.config.focus_active
    job = scheduler.due(T0)
    assert job.kind == "full"
    scheduler.start(job)
    scheduler.complete(job, [FakeSignal("SOL/USDT", 90)], T0)
    # حتی با فهرست تمرکز پر، نوبت تمرکز اجرا نمی‌شود
    assert scheduler.due(T0 + timedelta(minutes=10)) is None
    assert scheduler.due(T0 + timedelta(minutes=31)).kind == "full"
    assert 0 < scheduler.seconds_until_next(T0 + timedelta(minutes=10)) <= 1800


def test_both_mode_sweeps_and_focuses() -> None:
    scheduler = AutoScanScheduler(_config(source=SOURCE_BOTH))
    job = scheduler.due(T0)
    assert job.kind == "full"
    scheduler.start(job)
    scheduler.complete(job, [FakeSignal("SOL/USDT", 90)], T0)
    assert scheduler.due(T0 + timedelta(minutes=6)).kind == "focus"


def test_seed_focus_merge_and_replace() -> None:
    scheduler = AutoScanScheduler(_config())
    scheduler.focus_symbols = ["OLD/USDT", "KEEP/USDT"]
    scheduler.seed_focus([FakeSignal("NEW/USDT", 90), FakeSignal("WEAK/USDT", 10),
                          FakeSignal("WAIT/USDT", 95, "WAIT")])
    assert scheduler.focus_symbols == ["NEW/USDT", "OLD/USDT", "KEEP/USDT"]

    scheduler.seed_focus([FakeSignal("A/USDT", 70), FakeSignal("B/USDT", 80)], replace=True)
    assert scheduler.focus_symbols == ["B/USDT", "A/USDT"]
    # جایگزینی با نتیجهٔ خالی فهرست قبلی را پاک نمی‌کند
    scheduler.seed_focus([], replace=True)
    assert scheduler.focus_symbols == ["B/USDT", "A/USDT"]


@pytest.mark.parametrize("source", [SOURCE_FOUND, SOURCE_MARKET, SOURCE_BOTH])
@pytest.mark.parametrize("sweep", [True, False])
def test_countdown_is_always_a_non_negative_int(source, sweep) -> None:
    scheduler = AutoScanScheduler(_config(source=source, full_sweep_enabled=sweep))
    for focus in ([], ["BTC/USDT"]):
        scheduler.focus_symbols = list(focus)
        value = scheduler.seconds_until_next(T0)
        assert isinstance(value, int) and value >= 0


def test_from_settings_reads_new_keys() -> None:
    values = {
        "signals.auto_scan_enabled": True,
        "signals.auto_scan_source": "market",
        "signals.auto_scan_universe": "top",
        "signals.auto_scan_min_turnover": "250000",
        "signals.auto_scan_smart_filter": False,
    }
    settings = types.SimpleNamespace(get=lambda key, default=None: values.get(key, default))
    config = AutoScanConfig.from_settings(settings)
    assert config.source == SOURCE_MARKET
    assert config.universe == "top"
    assert config.min_turnover == 250000.0
    assert config.smart_filter is False


# ================================================================ تنظیمات و ترجمه
def test_new_setting_keys_have_defaults() -> None:
    expected = {
        SettingKey.SIGNAL_AUTO_SCAN_SOURCE: "both",
        SettingKey.SIGNAL_AUTO_SCAN_UNIVERSE: "all",
        SettingKey.SIGNAL_AUTO_SCAN_MIN_TURNOVER: 0.0,
        SettingKey.SIGNAL_AUTO_SCAN_SMART_FILTER: True,
        SettingKey.SIGNAL_SCAN_UNIVERSE: "top",
        SettingKey.SIGNAL_SCAN_LIMIT: 60,
        SettingKey.SIGNAL_SCAN_MIN_TURNOVER: 0.0,
        SettingKey.SIGNAL_SCAN_SMART_FILTER: True,
    }
    for key, value in expected.items():
        assert DEFAULT_SETTINGS[key.value] == value


def _locale(lang: str) -> dict:
    return json.loads((ROOT / "localization" / lang / "signals.json").read_text(encoding="utf-8"))


NEW_TOP_KEYS = (
    "scan_scope", "scan_scope_top", "scan_scope_all", "scan_smart_filter",
    "scan_smart_filter_tip", "scan_min_turnover", "scan_min_turnover_tip",
    "scan_eta", "scan_cancelled_partial",
)
NEW_AUTO_KEYS = (
    "source", "source_both", "source_found", "source_market", "universe",
    "status_need_scan", "status_progress",
)


def test_locale_keys_present_and_persian() -> None:
    fa, en = _locale("fa"), _locale("en")
    assert set(fa["auto"]) == set(en["auto"])
    for key in NEW_TOP_KEYS:
        assert en[key] and fa[key]
        assert any("\u0600" <= ch <= "\u06ff" for ch in fa[key]), key
    for key in NEW_AUTO_KEYS:
        assert en["auto"][key] and fa["auto"][key]
        assert any("\u0600" <= ch <= "\u06ff" for ch in fa["auto"][key]), key


# ================================================================ صفحهٔ سیگنال
@pytest.fixture()
def signals_page(qt_application):
    from localization import Translator
    from ui.pages.signals_page import SignalsPage

    return SignalsPage(Translator("fa"))


def test_scan_scope_all_disables_limit(signals_page) -> None:
    page = signals_page
    assert page.scan_universe_options()["universe"] == "top"
    assert page.scan_limit_spin.isEnabled()
    page.scan_scope_combo.setCurrentIndex(page.scan_scope_combo.findData("all"))
    assert not page.scan_limit_spin.isEnabled()
    assert page.scan_universe_options()["universe"] == "all"
    # قرارداد قدیمی سه‌کلیدی دست نخورده است
    assert set(page.scan_options()) == {"limit", "min_confidence", "include_wait"}


def test_scan_settings_round_trip_and_emit(signals_page) -> None:
    page = signals_page
    emitted: list[dict] = []
    page.scan_settings_changed.connect(emitted.append)
    page.set_scan_settings({
        "signals.scan_universe": "all", "signals.scan_limit": 150,
        "signals.scan_min_turnover": 500000, "signals.scan_smart_filter": False,
    })
    assert emitted == []  # پرکردن فرم «تغییر کاربر» نیست
    assert page.scan_settings() == {
        "signals.scan_universe": "all", "signals.scan_limit": 150,
        "signals.scan_min_turnover": 500000.0, "signals.scan_smart_filter": False,
    }
    page.scan_smart_check.setChecked(True)
    assert emitted and emitted[-1]["signals.scan_smart_filter"] is True


def test_scanning_locks_new_controls_and_restores_scope(signals_page) -> None:
    page = signals_page
    page.scan_scope_combo.setCurrentIndex(page.scan_scope_combo.findData("all"))
    page.set_scanning(True)
    assert not page.scan_scope_combo.isEnabled()
    assert not page.scan_smart_check.isEnabled()
    page.set_scanning(False)
    assert page.scan_scope_combo.isEnabled()
    assert not page.scan_limit_spin.isEnabled()  # هنوز «کل صرافی»


def test_scan_progress_shows_eta(signals_page, monkeypatch) -> None:
    import ui.pages.signals_page as module

    page = signals_page
    clock = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    page.set_scanning(True)
    clock[0] += 30.0
    page.set_scan_progress(10, 100, "BTC/USDT", 2)
    # ۳۰ ثانیه برای ۱۰ نماد → ۹۰ نماد ≈ ۲۷۰ ثانیه = 4:30
    assert "4:30" in page.scan_status.text()


def test_auto_source_controls(signals_page) -> None:
    page = signals_page
    emitted: list[dict] = []
    page.auto_scan_changed.connect(emitted.append)
    page.auto_enable_check.setChecked(True)
    options = page.auto_scan_options()
    assert options["signals.auto_scan_source"] == "both"
    assert options["signals.auto_scan_universe"] == "all"
    assert options["signals.auto_scan_full_sweep"] is True
    assert not page.auto_sweep_limit_spin.isEnabled()  # «کل صرافی» سقف ندارد

    page.auto_source_combo.setCurrentIndex(page.auto_source_combo.findData("found"))
    last = emitted[-1]
    assert last["signals.auto_scan_source"] == "found"
    assert last["signals.auto_scan_full_sweep"] is False
    assert not page.auto_universe_combo.isEnabled()
    assert page.auto_focus_spin.isEnabled()

    page.auto_source_combo.setCurrentIndex(page.auto_source_combo.findData("market"))
    assert emitted[-1]["signals.auto_scan_full_sweep"] is True
    assert not page.auto_focus_spin.isEnabled()
    assert page.auto_focus_spin.maximum() == 100


def test_auto_options_legacy_full_sweep_off_means_found(signals_page) -> None:
    page = signals_page
    page.set_auto_scan_options({
        "signals.auto_scan_enabled": True,
        "signals.auto_scan_full_sweep": False,
        "signals.auto_scan_min_turnover": 250000,
        "signals.auto_scan_universe": "top",
    })
    assert page.auto_source_combo.currentData() == "found"
    assert page.auto_universe_combo.currentData() == "top"
    assert page.auto_turnover_spin.value() == 250


# ================================================================ کنترلر (بدون پنجرهٔ کامل)
class _FakePage:
    def __init__(self) -> None:
        self.results: list[list[dict]] = []
        self.status_text = ""
        self.auto_status = ""
        self.scanning = None

    def set_scan_results(self, rows):
        self.results.append(list(rows))

    def set_scan_status(self, text):
        self.status_text = text

    def set_scanning(self, value):
        self.scanning = value

    def set_auto_scan_status(self, text, *, focus=None):
        self.auto_status = text


class _FakeTr:
    def tr(self, key, **kwargs):
        return key + (repr(sorted(kwargs.items())) if kwargs else "")

    def format_number(self, value, _digits=0):
        return str(value)


def _fake_controller(scheduler=None):
    from ui.controllers.main_controller import MainController

    fake = types.SimpleNamespace()
    fake.signals = _FakePage()
    fake.tr_ = _FakeTr()
    fake.window = None
    fake.status = lambda _text: None
    fake.runner = types.SimpleNamespace(cancel=lambda _key: None, active_keys=lambda: [])
    fake._decorate_validity = lambda rows: rows
    fake._apply_stale_filter = lambda rows: rows
    fake._auto_scheduler = scheduler
    fake.SCAN_LIVE_FLUSH_MS = MainController.SCAN_LIVE_FLUSH_MS
    for name in ("_flush_scan_live", "_stop_live_flush", "_seed_auto_focus",
                 "_on_scan_partial_signal", "_refresh_auto_scan_status",
                 "_format_duration", "stop_market_scan", "_on_auto_scan_progress",
                 "_on_auto_partial_signal", "run_auto_scan_now"):
        setattr(fake, name, types.MethodType(getattr(MainController, name), fake))
    return fake


def test_controller_live_rows_sorted_and_kept_on_stop(qt_application) -> None:
    scheduler = AutoScanScheduler(_config(source=SOURCE_FOUND))
    ctrl = _fake_controller(scheduler)
    ctrl._scan_live_signals = []
    ctrl._scan_live_active = True
    ctrl._on_scan_partial_signal(_signal("A/USDT", 55))
    ctrl._on_scan_partial_signal(_signal("B/USDT", 80))
    ctrl._scan_live_dirty = True
    ctrl._flush_scan_live()
    assert [row["symbol"] for row in ctrl.signals.results[-1]] == ["B/USDT", "A/USDT"]

    ctrl._on_scan_partial_signal(_signal("C/USDT", 70))
    ctrl.stop_market_scan()
    assert [row["symbol"] for row in ctrl.signals.results[-1]] == ["B/USDT", "C/USDT", "A/USDT"]
    assert ctrl.signals.status_text.startswith("signals.scan_cancelled_partial")
    # نتیجهٔ نیمه‌کاره، فهرست حالت «فقط پیداشده‌ها» را پر کرد
    assert scheduler.focus_symbols == ["B/USDT", "C/USDT", "A/USDT"]
    # سیگنال دیررسیده پس از توقف جدول را عوض نمی‌کند
    count = len(ctrl.signals.results)
    ctrl._on_scan_partial_signal(_signal("D/USDT", 99))
    ctrl._flush_scan_live()
    assert len(ctrl.signals.results) == count


def test_controller_found_mode_without_signals_asks_for_scan(qt_application) -> None:
    scheduler = AutoScanScheduler(_config(source=SOURCE_FOUND))
    ctrl = _fake_controller(scheduler)
    ctrl._execute_auto_job = lambda job: pytest.fail("must not run")
    ctrl.run_auto_scan_now()
    assert ctrl.signals.auto_status == "signals.auto.status_need_scan"
    ctrl._refresh_auto_scan_status()
    assert ctrl.signals.auto_status == "signals.auto.status_need_scan"


def test_controller_market_mode_run_now_sweeps(qt_application) -> None:
    scheduler = AutoScanScheduler(_config(source=SOURCE_MARKET))
    scheduler.focus_symbols = ["BTC/USDT"]
    ctrl = _fake_controller(scheduler)
    jobs = []
    ctrl._execute_auto_job = jobs.append
    ctrl.run_auto_scan_now()
    assert jobs and jobs[0].kind == "full"


def test_controller_auto_progress_and_live_seed(qt_application) -> None:
    scheduler = AutoScanScheduler(_config())
    ctrl = _fake_controller(scheduler)
    scheduler.running = True
    ctrl._on_auto_scan_progress(40, 1200)
    assert "signals.auto.status_progress" in ctrl.signals.auto_status
    assert "1200" in ctrl.signals.auto_status
    ctrl._on_auto_partial_signal(FakeSignal("PEPE/USDT", 88))
    assert scheduler.focus_symbols == ["PEPE/USDT"]


@pytest.mark.parametrize("universe,expected_limit", [("all", None), ("top", 150)])
def test_controller_full_job_uses_universe_settings(qt_application, universe, expected_limit) -> None:
    from signals.auto_scanner import ScanJob
    from ui.controllers.main_controller import MainController

    scheduler = AutoScanScheduler(_config(universe=universe, sweep_limit=150,
                                          min_turnover=5000, smart_filter=False))
    ctrl = _fake_controller(scheduler)
    captured: dict = {}

    def scan_market(symbols, frames, **kwargs):
        captured.update(kwargs, symbols=symbols)
        return None

    ctrl.app = types.SimpleNamespace(signals=object(), scan_market=scan_market)
    ctrl.signals.selected_timeframes = lambda: ["1h"]
    ctrl.runner = types.SimpleNamespace(submit=lambda *a, **k: None, active_keys=lambda: [])
    ctrl.auto_scan_signal_found = types.SimpleNamespace(emit=lambda _s: None)
    ctrl.auto_scan_progress = types.SimpleNamespace(emit=lambda *_a: None)
    MainController._execute_auto_job(ctrl, ScanJob(kind="full", symbols=(), reason="x"))
    assert captured["symbols"] is None
    assert captured["limit"] == expected_limit
    assert captured["universe"] == universe
    assert captured["min_turnover"] == 5000.0
    assert captured["smart_filter"] is False
    assert callable(captured["on_signal"]) and callable(captured["on_progress"])

    captured.clear()
    scheduler.running = False
    MainController._execute_auto_job(ctrl, ScanJob(kind="focus", symbols=("BTC/USDT",), reason="x"))
    assert captured["symbols"] == ["BTC/USDT"]
    assert "universe" not in captured
