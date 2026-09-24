"""
آزمون‌های نسخهٔ ۲.۴.۲ — سبک‌سازی (استخر فرایند، صفحهٔ عملکرد تنبل، حذف
ذخیرهٔ تکراری) و کپی نام/اطلاعات سیگنال.
"""

from __future__ import annotations

import asyncio
import logging
import pickle
import types
from pathlib import Path

import pytest

from app.core.constants import SignalDirection
from indicators.engine import IndicatorEngine
from market.engine import bulk_fetch
from signals import compute_pool as cp
from signals.engine import SignalEngine, compute_timeframe_analysis
from tests.test_v241_performance import _candles

ROOT = Path(__file__).resolve().parents[1]


class _Market:
    exchange_name = "fake"

    async def get_candles(self, symbol, timeframe, limit=None):
        await asyncio.sleep(0)
        return _candles(limit or 250, seed=hash((symbol, timeframe)) % 1000)


class _CountingPool:
    """استخر ساختگی: همان محاسبه را هم‌گام انجام می‌دهد و فراخوانی را می‌شمارد."""

    def __init__(self, result_none: bool = False) -> None:
        self.calls = 0
        self.result_none = result_none

    async def compute_timeframe(self, symbol, timeframe, candles, default_parameters=None):
        self.calls += 1
        if self.result_none:
            return None
        status, payload = cp.compute_timeframe_job(symbol, timeframe, candles, default_parameters)
        assert status == "ok"
        return pickle.loads(pickle.dumps(payload))  # مثل عبور از مرز فرایند


# ================================================================ استخر محاسبه
def test_module_level_compute_matches_engine_method() -> None:
    engine = SignalEngine(_Market(), IndicatorEngine())
    candles = _candles(250, seed=3)
    a = engine._compute_timeframe("X/USDT", "1h", candles)
    b = compute_timeframe_analysis(IndicatorEngine(), "X/USDT", "1h", candles)
    assert a["indicators"] == b["indicators"]
    assert a["levels"] == b["levels"]
    assert a["trend"] == b["trend"]


def test_worker_job_returns_picklable_payload_without_candles() -> None:
    status, payload = cp.compute_timeframe_job("X/USDT", "1h", _candles(250), {})
    assert status == "ok"
    assert "candles" not in payload
    assert set(payload) >= {"indicators", "structure", "levels", "trend", "atr_result"}
    assert pickle.loads(pickle.dumps(payload))["indicators"] == payload["indicators"]


def test_worker_job_reports_errors_instead_of_raising() -> None:
    status, message = cp.compute_timeframe_job("X/USDT", "1h", _candles(10), {})
    assert status == "error"
    assert "InsufficientData" in message


def test_worker_job_honours_user_indicator_parameters() -> None:
    candles = _candles(250, seed=5)
    _, default = cp.compute_timeframe_job("X/USDT", "1h", candles, {})
    _, custom = cp.compute_timeframe_job("X/USDT", "1h", candles, {"rsi": {"period": 5}})
    assert default["indicators"]["RSI"] != custom["indicators"]["RSI"]
    # تنظیم یک کار به کار بعدی نشت نمی‌کند
    _, again = cp.compute_timeframe_job("X/USDT", "1h", candles, {})
    assert again["indicators"]["RSI"] == default["indicators"]["RSI"]


def test_default_worker_count_leaves_cores_for_ui() -> None:
    assert cp.default_worker_count(1) == 1
    assert cp.default_worker_count(2) == 1
    assert cp.default_worker_count(4) == 2
    assert cp.default_worker_count(64) == cp.MAX_WORKERS == 2


def test_engine_uses_pool_only_in_bulk_mode_and_results_match() -> None:
    frames = ["1d", "4h", "1h", "15m"]
    local_engine = SignalEngine(_Market(), IndicatorEngine())
    pooled_engine = SignalEngine(_Market(), IndicatorEngine())
    pool = _CountingPool()
    pooled_engine.set_compute_pool(pool)

    async def run():
        plain = await pooled_engine.generate("A/USDT", frames)
        assert pool.calls == 0  # خارج از پویش انبوه: همان مسیر محلی
        with bulk_fetch():
            pooled = await pooled_engine.generate("A/USDT", frames)
        local = await local_engine.generate("A/USDT", frames)
        return plain, pooled, local

    plain, pooled, local = asyncio.run(run())
    assert pool.calls == len(frames)
    for signal in (plain, pooled):
        assert signal.direction == local.direction
        assert signal.confidence == local.confidence
        assert signal.stop_loss == local.stop_loss
        assert list(signal.take_profits) == list(local.take_profits)


def test_engine_falls_back_to_local_when_pool_returns_none() -> None:
    engine = SignalEngine(_Market(), IndicatorEngine())
    pool = _CountingPool(result_none=True)
    engine.set_compute_pool(pool)
    reference = SignalEngine(_Market(), IndicatorEngine())

    async def run():
        with bulk_fetch():
            return await engine.generate("B/USDT", ["4h", "1h"])

    signal = asyncio.run(run())
    expected = asyncio.run(reference.generate("B/USDT", ["4h", "1h"]))
    assert pool.calls == 2
    assert signal.confidence == expected.confidence
    assert signal.direction == expected.direction


def test_pool_disables_itself_after_repeated_failures() -> None:
    class _BadExecutor:
        def submit(self, *args, **kwargs):
            raise TypeError("cannot pickle")

        def shutdown(self, **kwargs):
            pass

    pool = cp.ComputePool(1)
    pool._executor = _BadExecutor()

    async def run():
        results = []
        for _ in range(cp.MAX_CONSECUTIVE_FAILURES + 1):
            results.append(await pool.compute_timeframe("A", "1h", _candles(250)))
        return results

    assert asyncio.run(run()) == [None] * (cp.MAX_CONSECUTIVE_FAILURES + 1)
    assert not pool.enabled
    assert not pool.running
    assert pool.fallbacks == cp.MAX_CONSECUTIVE_FAILURES


def test_real_process_pool_matches_local_compute() -> None:
    """کارگر واقعی (spawn) همان نتیجهٔ محاسبهٔ محلی را می‌دهد."""
    pool = cp.ComputePool(1, idle_shutdown=0)
    candles = _candles(250, seed=11)

    async def run():
        try:
            return await asyncio.wait_for(
                pool.compute_timeframe("R/USDT", "1h", candles, {}), timeout=120
            )
        finally:
            pool.shutdown()

    payload = asyncio.run(run())
    if payload is None:
        pytest.skip("process pool unavailable in this environment")
    local = compute_timeframe_analysis(IndicatorEngine(), "R/USDT", "1h", candles)
    assert payload["indicators"] == local["indicators"]
    assert payload["levels"] == local["levels"]
    assert payload["trend"] == local["trend"]
    assert pool.jobs_done == 1
    assert not pool.running


def test_worker_module_does_not_import_qt() -> None:
    source = (ROOT / "signals" / "compute_pool.py").read_text(encoding="utf-8")
    assert "PySide" not in source.split('"""', 2)[2].replace("PySide وارد", "")


def test_main_calls_freeze_support() -> None:
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "multiprocessing.freeze_support()" in source


def test_application_compute_pool_respects_switches(monkeypatch) -> None:
    from app.application import Application

    fake = types.SimpleNamespace(
        _compute_pool=None,
        settings=types.SimpleNamespace(get_bool=lambda key, default=False: default),
    )
    monkeypatch.setenv("CRYPTOAI_NO_PROCESS_POOL", "1")
    assert Application.compute_pool(fake) is None
    monkeypatch.setenv("CRYPTOAI_NO_PROCESS_POOL", "0")
    pool = Application.compute_pool(fake)
    assert isinstance(pool, cp.ComputePool)
    assert Application.compute_pool(fake) is pool  # یک نمونه برای کل نشست
    assert not pool.running  # تنبل: کارگری بالا نیامده
    fake.settings = types.SimpleNamespace(get_bool=lambda key, default=False: False)
    fake._compute_pool = None
    assert Application.compute_pool(fake) is None


# ================================================================ حذف ذخیرهٔ تکراری
def test_scan_dedup_skips_repeats_within_window() -> None:
    from app.application import SCAN_DEDUP_SECONDS, Application

    fake = types.SimpleNamespace(_scan_saved={})

    def sig(confidence, direction=SignalDirection.LONG, symbol="BTC/USDT"):
        return types.SimpleNamespace(
            exchange="lbank", symbol=symbol, direction=direction, confidence=confidence
        )

    store = lambda s, t: Application._should_store_scanned(fake, s, now=t)  # noqa: E731
    assert store(sig(70), 0.0) is True
    assert store(sig(72), 60.0) is False  # همان سیگنال، تغییر ناچیز
    assert store(sig(76), 120.0) is True  # اطمینان ≥۵ واحد تغییر کرد
    assert store(sig(76, SignalDirection.SHORT), 130.0) is True  # جهت عوض شد
    assert store(sig(76, symbol="ETH/USDT"), 130.0) is True
    assert store(sig(76), 120.0 + SCAN_DEDUP_SECONDS + 1) is True  # پنجره گذشت


def test_scan_market_consults_dedup_before_saving() -> None:
    source = (ROOT / "app" / "application.py").read_text(encoding="utf-8")
    body = source[source.index("async def scan_market"):]
    body = body[: body.index("return result")]
    assert body.index("_should_store_scanned") < body.index("save_signal(")


# ================================================================ متن اشتراک سیگنال
_SIGNAL = {
    "symbol": "btc/usdt",
    "exchange": "LBank",
    "direction": "LONG",
    "confidence": 72,
    "entry_min": 64100.0,
    "entry_max": 64250.5,
    "stop_loss": 63200,
    "take_profits": [65000, 66100.25, 0],
    "leverage": 5,
    "risk_reward": 2.1,
    "timeframes": ["1d", "4h", "1h"],
    "primary_timeframe": "1h",
    "created_at": "2026-09-24T14:05:00",
}


def test_format_price_precision_and_latin_digits() -> None:
    from ui.signal_share import format_price

    assert format_price(64250.5) == "64,250.5"
    assert format_price(1.23456789) == "1.2346"
    assert format_price(0.000012345678) == "0.0000123457"  # شش رقم معنادار
    assert format_price(0.5) == "0.5"
    assert format_price(None) == "—"
    assert format_price("bad") == "—"
    assert format_price(0) == "—"


def test_format_signal_text_english() -> None:
    from localization import Translator
    from ui.signal_share import format_signal_text, signal_symbol

    assert signal_symbol(_SIGNAL) == "BTC/USDT"
    text = format_signal_text(_SIGNAL, Translator("en"))
    lines = text.splitlines()
    assert lines[0] == "🟢 BTC/USDT — LONG"
    assert "Confidence: 72%" in lines
    assert "Entry: 64,100 – 64,250.5" in lines
    assert "Stop loss: 63,200" in lines
    assert "Targets: TP1 65,000 | TP2 66,100.25" in lines
    assert "Leverage: ×5 | R:R 2.10" in lines
    assert "Timeframes: 1d, 4h, 1h (primary 1h)" in lines
    assert "Exchange: LBank" in lines
    assert "Time: 2026-09-24 14:05" in lines
    assert lines[-1].startswith("⚠️")


def test_format_signal_text_persian_keeps_latin_numbers() -> None:
    from localization import Translator
    from ui.signal_share import format_signal_text

    text = format_signal_text(_SIGNAL, Translator("fa"))
    assert "خرید" in text.splitlines()[0]
    assert "حد ضرر: 63,200" in text
    assert "اطمینان: 72%" in text
    assert not any(ch in text for ch in "۰۱۲۳۴۵۶۷۸۹")


def test_format_signal_text_wait_signal_omits_trade_levels() -> None:
    from ui.signal_share import format_signal_text

    text = format_signal_text({"symbol": "SOL/USDT", "direction": "WAIT", "confidence": 40})
    assert text.splitlines()[0] == "⚪ SOL/USDT — WAIT"
    assert "Stop loss" not in text and "Targets" not in text


def test_share_keys_exist_in_both_languages() -> None:
    import json

    keys = None
    for lang in ("en", "fa"):
        data = json.loads((ROOT / "localization" / lang / "signals.json").read_text("utf-8"))
        share = data["share"]
        keys = keys or set(share)
        assert set(share) == keys
        for value in share.values():
            assert value.strip()


# ================================================================ رابط: کپی
def test_detail_dialog_copy_buttons(qt_application) -> None:
    from PySide6.QtGui import QGuiApplication

    from localization import Translator
    from ui.dialogs.signal_detail_dialog import SignalDetailDialog

    dialog = SignalDetailDialog(dict(_SIGNAL), Translator("en"))
    try:
        assert dialog.copy_symbol_button.text() == "Copy symbol"
        assert dialog.copy_info_button.text() == "Copy signal info"
        assert dialog.copy_symbol()
        assert QGuiApplication.clipboard().text() == "BTC/USDT"
        assert dialog.copy_symbol_button.text() == "Copied ✓"
        assert dialog.copy_info()
        copied = QGuiApplication.clipboard().text()
        assert copied.startswith("🟢 BTC/USDT") and "Stop loss: 63,200" in copied
    finally:
        dialog.deleteLater()


def test_signals_page_copy_from_tables(qt_application) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication

    from localization import Translator
    from ui.pages.signals_page import SignalsPage

    page = SignalsPage(Translator("en"))
    notices: list[str] = []
    page.copy_notice.connect(notices.append)
    try:
        page.set_scan_results([dict(_SIGNAL, symbol="ETH/USDT"), dict(_SIGNAL)])
        row = page.scan_row_at(1)
        assert row["symbol"] == "btc/usdt"
        assert page.copy_signal_symbol(row)
        assert QGuiApplication.clipboard().text() == "BTC/USDT"
        assert notices[-1] == "Symbol BTC/USDT copied"

        page.set_history([dict(_SIGNAL, id=7, symbol="XRP/USDT")])
        assert page.history_row_at(0)["id"] == 7
        assert page.history_row_at(5) == {}
        assert page.copy_signal_info(page.history_row_at(0))
        assert QGuiApplication.clipboard().text().startswith("🟢 XRP/USDT")
        assert "XRP/USDT" in notices[-1]
        assert not page.copy_signal_info({})

        for table in (page.scan_table, page.history_table):
            assert table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
        assert "right-click" in page.scan_copy_hint.text()
    finally:
        page.deleteLater()


# ================================================================ پاسخ‌گویی رابط
def test_stall_watchdog_logs_ui_stack_once_per_interval(qt_application, caplog) -> None:
    from ui.responsiveness import UiStallWatchdog

    clock = {"t": 0.0}
    dog = UiStallWatchdog(threshold=1.0, report_interval=30.0, clock=lambda: clock["t"])
    dog.beat()
    clock["t"] = 0.5
    assert dog.check() is False
    with caplog.at_level(logging.WARNING):
        clock["t"] = 2.0
        assert dog.check() is True
        clock["t"] = 3.0
        assert dog.check() is True
    reports = [r for r in caplog.records if "UI thread unresponsive" in r.getMessage()]
    assert len(reports) == 1
    assert "test_stall_watchdog" in reports[0].getMessage()  # پشتهٔ همین نخ
    assert dog.stalls == 2 and dog.longest == pytest.approx(3.0)
    dog.beat()
    assert dog.check() is False
    dog.stop()


def test_outcome_view_is_lazy_when_hidden() -> None:
    from ui.controllers.main_controller import MainController

    queried: list[str] = []
    repository = types.SimpleNamespace(
        performance=lambda **kw: queried.append("performance") or {},
        history=lambda **kw: queried.append("history") or [],
    )
    page = types.SimpleNamespace(
        isVisible=lambda: False,
        selected_period=lambda: 0,
        set_performance=lambda report: queried.append("set"),
        set_history=lambda rows: queried.append("rows"),
    )
    fake = types.SimpleNamespace(
        performance=page,
        _outcome_watch_installed=True,
        _outcome_view_stale=False,
        app=types.SimpleNamespace(outcome_repository=repository),
        runner=types.SimpleNamespace(running=False),
        _outcome_row=lambda record: record,
    )
    MainController._refresh_outcome_view(fake, quiet=True)
    assert queried == [] and fake._outcome_view_stale is True

    # نمایش صفحه → تازه‌سازی
    fake._refresh_outcome_view = lambda quiet=False: MainController._refresh_outcome_view(
        fake, quiet=quiet
    )
    page.isVisible = lambda: True
    MainController._on_outcome_view_shown(fake)
    assert queried == ["performance", "history", "set", "rows"]
    assert fake._outcome_view_stale is False


def test_outcome_view_queries_run_off_ui_thread() -> None:
    from ui.controllers.main_controller import MainController

    submitted: dict[str, object] = {}

    def run_blocking(name, function, **kwargs):
        submitted.update(name=name, function=function, **kwargs)

    repository = types.SimpleNamespace(performance=lambda **kw: {"n": 1},
                                       history=lambda **kw: [1, 2])
    applied: list[object] = []
    page = types.SimpleNamespace(
        isVisible=lambda: True, selected_period=lambda: 7,
        set_performance=applied.append, set_history=applied.append,
    )
    fake = types.SimpleNamespace(
        performance=page, _outcome_watch_installed=True, _outcome_view_stale=True,
        app=types.SimpleNamespace(outcome_repository=repository),
        runner=types.SimpleNamespace(running=True, run_blocking=run_blocking),
        _outcome_row=lambda record: {"r": record},
    )
    MainController._refresh_outcome_view(fake, quiet=True)
    assert submitted["name"] == "outcome-view"
    assert applied == []  # هنوز چیزی روی نخ رابط اجرا نشده
    result = submitted["function"]()  # در نخ پس‌زمینه
    submitted["on_success"](result)  # روی نخ رابط
    assert applied == [{"n": 1}, [{"r": 1}, {"r": 2}]]


def test_terminal_tick_skips_hidden_trades_page() -> None:
    from ui.controllers.main_controller import MainController

    calls: list[int] = []
    fake = types.SimpleNamespace(
        trades=types.SimpleNamespace(isVisible=lambda: False),
        _refresh_auto_terminal=lambda: calls.append(1),
    )
    MainController._terminal_timer_tick(fake)
    assert calls == []
    fake.trades.isVisible = lambda: True
    MainController._terminal_timer_tick(fake)
    assert calls == [1]
