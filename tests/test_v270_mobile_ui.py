"""
۲.۷.۰ — رابط جدید موبایل (۵ صفحه با نوار پایین) و لایهٔ داده.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mobile.app import market_lite, viewmodel as vm
from mobile.app.signal_lite import analyse
from mobile.app.store import DEFAULTS, Store

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- داده
class TestCandleWindow:
    def test_start_covers_the_latest_candles_for_every_timeframe(self) -> None:
        """اشکال قدیمی: شروع = limit×3600 برای همه؛ ۱۵ دقیقه کهنه، روزانه ۸ کندل."""
        now = 1_760_000_000
        for tf, step in (("15m", 900), ("1h", 3600), ("4h", 14400), ("1d", 86400)):
            start = market_lite.candles_start(tf, 200, now=now)
            assert start % step == 0
            assert (now - start) // step == 199  # ۱۹۹ کندل بسته + کندل جاری = ۲۰۰

    def test_start_is_stable_within_a_candle_so_the_cache_hits(self) -> None:
        a = market_lite.candles_start("1h", 200, now=1_760_000_000)
        b = market_lite.candles_start("1h", 200, now=1_760_000_000 + 30)
        assert a == b


class TestTickers:
    PAYLOAD = {"data": [
        {"symbol": "btc_usdt", "ticker": {"latest": "65000", "turnover": "9e8", "change": "1.5", "high": "66000", "low": "64000"}},
        {"symbol": "eth_btc", "ticker": {"latest": "0.05", "turnover": "100", "change": "0"}},
        {"symbol": "dead_usdt", "ticker": {"latest": "0", "turnover": "0", "change": "0"}},
        {"symbol": "bad_usdt", "ticker": {"latest": "x"}},
        "junk",
    ]}

    def test_only_quote_pairs_with_price_and_volume(self) -> None:
        rows = market_lite.parse_tickers(self.PAYLOAD)
        assert [r["symbol"] for r in rows] == ["BTC/USDT"]
        assert rows[0]["price"] == 65000 and rows[0]["change"] == 1.5 and rows[0]["base"] == "BTC"

    def test_garbage_payload_gives_empty_list(self) -> None:
        assert market_lite.parse_tickers(None) == []
        assert market_lite.parse_tickers({"data": "x"}) == []


# ---------------------------------------------------------------- منطق نمایش
def _row(base: str, price: float, change: float, turnover: float) -> dict:
    return {"symbol": f"{base}/USDT", "base": base, "price": price, "change": change, "turnover": turnover, "high": 0, "low": 0}


ROWS = [_row("BTC", 65000, 1.0, 9e8), _row("PEPE", 0.0000123, 12.0, 2e8), _row("ETH", 3200, -3.0, 5e8),
        _row("DEAD", 0.01, 300.0, 50)]


class TestViewModel:
    def test_price_format_keeps_tiny_prices_readable(self) -> None:
        assert vm.format_price(65432.1) == "65,432.1"
        assert vm.format_price(0.0000123) == "0.00001230"
        assert vm.format_price(2.5) == "2.5"
        assert vm.format_price(0) == "—"

    def test_change_and_volume(self) -> None:
        assert vm.format_change(1.234) == "+1.23%" and vm.format_change(-2) == "-2.00%"
        assert vm.format_volume(1.25e9) == "1.2B" and vm.format_volume(34_500_000) == "34.5M"

    def test_sorting_and_search(self) -> None:
        assert [r["base"] for r in vm.filter_and_sort(ROWS)] == ["BTC", "ETH", "PEPE", "DEAD"]
        assert [r["base"] for r in vm.filter_and_sort(ROWS, sort="gainers")] == ["PEPE", "BTC", "ETH"]
        assert [r["base"] for r in vm.filter_and_sort(ROWS, sort="losers")][0] == "ETH"
        assert [r["base"] for r in vm.filter_and_sort(ROWS, query="pe")] == ["PEPE"]
        assert [r["base"] for r in vm.filter_and_sort(ROWS, query="BTC/USDT")] == ["BTC"]

    def test_dead_coins_never_enter_the_scan(self) -> None:
        assert vm.scan_universe(ROWS, 40) == ["BTC/USDT", "ETH/USDT", "PEPE/USDT"]

    def test_breadth_is_volume_weighted_and_ignores_illiquid(self) -> None:
        b = vm.market_breadth(ROWS)
        assert b["count"] == 3 and b["up"] == 2 and b["down"] == 1
        assert b["avg"] < 12  # ۳۰۰٪ نماد مرده حساب نشده

    def test_sparkline_fits_its_box(self) -> None:
        pts = vm.sparkline_points([1, 3, 2], 100, 50, pad=5)
        xs, ys = pts[0::2], pts[1::2]
        assert xs[0] == 5 and xs[-1] == 95 and min(ys) == 5 and max(ys) == 45
        assert vm.sparkline_points([1], 100, 50) == []

    def test_indicator_snapshot_has_all_tiles(self) -> None:
        closes = [100 + i * 0.5 for i in range(120)]
        snap = vm.indicator_snapshot([c * 1.01 for c in closes], [c * 0.99 for c in closes], closes)
        assert snap["trend"][0] == "صعودی" and snap["trend"][1] == "up"
        assert set(snap) >= {"rsi", "macd", "atr", "trend", "ema20"}
        assert vm.indicator_snapshot([], [], [])["rsi"][0] == "—"


def test_tiny_price_levels_keep_precision() -> None:
    """میم‌کوین: با round(…, 6) حد ضرر و هدف روی ورود می‌افتادند."""
    closes = [0.0000123 * (1 + 0.003 * i) for i in range(120)]
    s = analyse("PEPE/USDT", [c * 1.01 for c in closes], [c * 0.99 for c in closes], closes, "1h")
    if s.direction != "WAIT":
        assert s.stop_loss != s.entry_low and s.take_profits[0] != s.entry_high
        assert len({s.stop_loss, *s.take_profits}) == 4


# ---------------------------------------------------------------- ذخیره‌سازی
class TestStore:
    def test_defaults_and_persistence(self, tmp_path) -> None:
        store = Store(tmp_path)
        assert store.get("timeframe") == DEFAULTS["timeframe"]
        store.set("scan_size", 40)
        assert store.toggle_watch("doge/usdt") is True
        again = Store(tmp_path)
        assert again.get("scan_size") == 40 and again.is_watched("DOGE/USDT")
        assert again.toggle_watch("DOGE/USDT") is False and not Store(tmp_path).is_watched("DOGE/USDT")

    def test_invalid_values_are_rejected(self, tmp_path) -> None:
        with pytest.raises(ValueError):
            Store(tmp_path).set("scan_size", 999)

    def test_corrupt_file_falls_back_to_defaults(self, tmp_path) -> None:
        (tmp_path / "mobile_settings.json").write_text("{not json", encoding="utf-8")
        assert Store(tmp_path).get("timeframe") == "1h"
        (tmp_path / "mobile_settings.json").write_text(json.dumps(
            {"timeframe": "7m", "scan_size": "x", "watchlist": ["BTC/USDT", 5, "btc/usdt", "nope"]}), encoding="utf-8")
        s = Store(tmp_path)
        assert s.get("timeframe") == "1h" and s.get("scan_size") == 20 and s.watchlist == ["BTC/USDT"]


# ---------------------------------------------------------------- بسته‌بندی
def test_new_modules_stay_light() -> None:
    for name in ("store.py", "viewmodel.py", "widgets.py", "screens.py"):
        src = (ROOT / "mobile" / "app" / name).read_text(encoding="utf-8")
        assert "import pandas" not in src and "import numpy" not in src and "PySide6" not in src
        assert "kivymd" not in src  # بدون دستور ساخت اضافه روی اندروید


def test_mobile_version_bumped() -> None:
    assert '"2.7.0"' in (ROOT / "mobile" / "version.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------- اجرای کامل رابط (بی‌سر)
@pytest.mark.skipif(importlib.util.find_spec("kivy") is None, reason="kivy not installed")
def test_full_app_runs_headless() -> None:
    env = dict(os.environ)
    env.pop("QT_QPA_PLATFORM", None)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "mobile_ui_driver.py")],
        cwd=ROOT / "mobile", capture_output=True, text=True, timeout=240, env=env, check=False,
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")), None)
    assert line, f"driver failed:\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}"
    r = json.loads(line[len("RESULT "):])

    assert r["market_rows"] == 11 and r["market_first"] == "BTC"
    assert r["gainers_excludes_dead"] and r["search_pep"] == ["PEPE"] and r["pepe_price_text"] == "0.00001230"
    assert r["search_empty_state"]
    assert r["watch_rows"] == 4 and r["watch_signals"] == 4
    assert r["signals_count"] == 10 and r["signal_cards"] >= 1 and r["scan_universe_excludes_dead"]
    assert r["tradeable_only_saved"] is True
    assert r["analysis_current_screen"] == "analysis" and r["analysis_symbol"] == r["analysis_target"]
    assert r["chart_points"] == 120 and r["tiles"] == 4 and r["analysis_texts_have_reasons"]
    assert r["analysis_tf"] == "4h"
    assert r["back_handled"] is True and r["after_back"] == "signals"
    assert r["refresh_event_off"]
    assert r["toast_on_error"] and r["rows_kept_on_error"] > 0
    assert "DOGE/USDT" in r["persisted_watch"] and r["persisted_tradeable_only"] is True
    # کش: ۱۰ نماد پویش + دیدبان (که هم‌پوشانی دارد) — نه یک درخواست به ازای هر رسم
    assert r["calls"]["candles"] <= 16
