"""
راننده‌ی آزمون رابط موبایل — در یک فرایند جدا با cwd=mobile اجرا می‌شود
(بستهٔ `app` موبایل با بستهٔ `app` دسکتاپ هم‌نام است).

برنامه را بی‌سر می‌سازد، دادهٔ ساختگی تزریق می‌کند، بین صفحه‌ها می‌چرخد و
نتیجه را JSON چاپ می‌کند.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "mobile")]  # `app` و `main` باید از mobile بیایند
sys.path.append(REPO)  # فقط برای tests.kivy_headless
os.chdir(os.path.join(REPO, "mobile"))  # مسیر فونت assets/…

from tests.kivy_headless import install  # noqa: E402

install()

from kivy.clock import Clock  # noqa: E402

import main as mobile_main  # noqa: E402
from app import market_lite  # noqa: E402

CALLS = {"tickers": 0, "candles": 0}
FAIL = {"on": False}


def fake_tickers(quote: str = "usdt") -> list[dict]:
    CALLS["tickers"] += 1
    if FAIL["on"]:
        raise market_lite.MarketError("اتصال به اینترنت برقرار نشد")
    rows = []
    for i, base in enumerate(["BTC", "ETH", "SOL", "XRP", "DOGE", "PEPE", "ADA", "LINK", "TRX", "SUI", "DEAD"]):
        price = [65000, 3200, 150, 0.6, 0.12, 0.0000123, 0.45, 14.2, 0.11, 1.8, 0.001][i]
        rows.append({"symbol": f"{base}/USDT", "base": base, "price": price, "change": (-1) ** i * (i + 0.5),
                     "turnover": 5e8 / (i + 1) if base != "DEAD" else 50.0, "high": price * 1.03, "low": price * 0.97})
    return rows


def fake_candles(symbol: str, timeframe: str = "1h", limit: int = 200):  # noqa: ANN201
    CALLS["candles"] += 1
    seed = sum(map(ord, symbol + timeframe))
    base = 100.0 + seed % 50
    closes = [base * (1 + 0.02 * math.sin(i / (5 + seed % 7)) + 0.0006 * i * (1 if seed % 2 else -1)) for i in range(limit)]
    highs = [c * 1.004 for c in closes]
    lows = [c * 0.996 for c in closes]
    return highs, lows, closes


mobile_main.fetch_tickers = fake_tickers
mobile_main.fetch_candles = fake_candles


def pump(seconds: float = 0.6) -> None:
    end = time.time() + seconds
    while time.time() < end:
        Clock.tick()
        time.sleep(0.01)


def texts(widget) -> list[str]:  # noqa: ANN001
    out = []
    for w in widget.walk():
        raw = getattr(w, "raw", None)
        if raw:
            out.append(raw)
    return out


def main() -> None:
    result: dict = {}
    data_dir = tempfile.mkdtemp()

    class TestApp(mobile_main.TraderApp):
        @property
        def user_data_dir(self) -> str:  # noqa: D401
            return data_dir

    application = TestApp()
    root = application.build()
    application.root = root
    mobile_main.App._running_app = application  # noqa: SLF001
    pump(1.0)

    # بازار
    market = application.screens["market"]
    result["market_rows"] = len(market.list.data)
    result["market_first"] = market.list.data[0]["base"] if market.list.data else None
    result["breadth"] = market.breadth_text.raw
    market.sort_chips._clicked(market.sort_chips.chips[0])  # آخرین گزینه چون معکوس افزوده شده
    pump(0.1)
    result["sort_after_click"] = market.sort
    result["gainers_excludes_dead"] = "DEAD" not in [r["base"] for r in market.list.data]
    market.search_input.text = "pep"
    pump(0.1)
    result["search_pep"] = [r["base"] for r in market.list.data]
    result["pepe_price_text"] = market.list.data[0]["price_text"] if market.list.data else None
    market.search_input.text = "zzz"
    pump(0.1)
    result["search_empty_state"] = any("پیدا نشد" in t for t in texts(market))
    market.search_input.text = ""
    pump(0.1)

    # دیدبان + ستاره
    store = application.store
    result["default_watch"] = store.watchlist
    store.toggle_watch("DOGE/USDT")
    application.go("watch")
    pump(1.0)
    watch = application.screens["watch"]
    result["watch_rows"] = sum(1 for w in watch.column.children if type(w).__name__ == "WatchRow")
    result["watch_signals"] = len(watch.signals)

    # سیگنال‌ها
    application.go("signals")
    pump(0.2)
    signals = application.screens["signals"]
    signals.refresh(force=True)
    pump(2.0)
    result["signals_count"] = len(signals.signals)
    result["signal_cards"] = sum(1 for w in signals.column.children if type(w).__name__ == "SignalCard")
    result["scan_universe_excludes_dead"] = all(s.symbol != "DEAD/USDT" for s in signals.signals)
    signals.only_chip.dispatch("on_release")
    pump(0.1)
    result["tradeable_only_saved"] = store.get("tradeable_only")

    # تحلیل از روی کارت سیگنال
    card = next((w for w in signals.column.children if type(w).__name__ == "SignalCard"), None)
    target = card.signal.symbol if card else "BTC/USDT"
    if card:
        card.dispatch("on_release")
    else:
        application.open_analysis(target)
    pump(1.0)
    analysis = application.screens["analysis"]
    result["analysis_symbol"] = analysis.symbol
    result["analysis_target"] = target
    result["analysis_current_screen"] = application.manager.current
    result["chart_points"] = len(analysis.chart.values)
    result["tiles"] = len(analysis.tiles.children)
    result["analysis_texts_have_reasons"] = any(t.startswith("• ") for t in texts(analysis))
    analysis.tf_chips._clicked(next(c for c in analysis.tf_chips.chips if c.value == "4h"))
    pump(0.8)
    result["analysis_tf"] = analysis.timeframe

    # بازگشت اندروید
    result["back_handled"] = application._on_key(None, 27)  # noqa: SLF001
    pump(0.2)
    result["after_back"] = application.manager.current

    # تنظیمات
    application.go("settings")
    pump(0.2)
    store.set("refresh_seconds", 0)
    application.settings_changed("refresh_seconds")
    result["refresh_event_off"] = application._refresh_event is None  # noqa: SLF001
    application.go("market")
    pump(0.2)

    # خطای شبکه: صفحه نباید بشکند و پیام بدهد
    FAIL["on"] = True
    market_lite._cache.clear()  # noqa: SLF001
    market.refresh(force=True)
    pump(0.6)
    result["toast_on_error"] = application._toast_label.raw  # noqa: SLF001
    result["rows_kept_on_error"] = len(market.list.data)

    # تنظیمات پس از راه‌اندازی دوباره ماندگارند
    from app.store import Store  # noqa: PLC0415

    again = Store(data_dir)
    result["persisted_watch"] = again.watchlist
    result["persisted_tradeable_only"] = again.get("tradeable_only")
    result["calls"] = CALLS
    application.on_stop()
    print("RESULT " + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
