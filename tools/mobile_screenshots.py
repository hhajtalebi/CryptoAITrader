"""
گرفتن تصویر از پنج صفحهٔ برنامهٔ موبایل — روی سرور GitHub (xvfb + mesa).

    xvfb-run -s "-screen 0 1100x2000x24" python tools/mobile_screenshots.py docs/mobile_screens

دادهٔ واقعی LBank؛ اگر در دسترس نبود، دادهٔ ساختگی (و این روی تصویر نوشته
می‌شود تا کسی آن را با بازار واقعی اشتباه نگیرد).
"""

from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else REPO / "docs" / "mobile_screens").resolve()
os.chdir(REPO / "mobile")
sys.path[:0] = [str(REPO / "mobile")]

os.environ.setdefault("KIVY_METRICS_DENSITY", "2.2")
os.environ["KIVY_NO_ARGS"] = "1"
from kivy.config import Config  # noqa: E402

Config.set("graphics", "width", "906")  # ≈ 412dp × 2.2
Config.set("graphics", "height", "1980")  # ≈ 900dp × 2.2
Config.set("graphics", "resizable", "0")

from kivy.clock import Clock  # noqa: E402

import main as mobile_main  # noqa: E402
from app import market_lite  # noqa: E402

SYNTHETIC = {"on": False}


def _fake_tickers(quote: str = "usdt") -> list[dict]:
    names = ["BTC", "ETH", "SOL", "XRP", "DOGE", "PEPE", "ADA", "LINK", "TRX", "SUI", "AVAX", "TON"]
    prices = [65000, 3200, 150, 0.6, 0.12, 0.0000123, 0.45, 14.2, 0.11, 1.8, 27.5, 5.4]
    return [{"symbol": f"{b}/USDT", "base": b, "price": p, "change": (-1) ** i * (0.4 + i * 0.7),
             "turnover": 9e8 / (i + 1), "high": p * 1.03, "low": p * 0.97} for i, (b, p) in enumerate(zip(names, prices, strict=True))]


def _fake_candles(symbol: str, timeframe: str = "1h", limit: int = 200):  # noqa: ANN202
    seed = sum(map(ord, symbol))
    base = 100.0 + seed % 50
    closes = [base * (1 + 0.025 * math.sin(i / 9 + seed) + 0.0008 * i) for i in range(limit)]
    return [c * 1.004 for c in closes], [c * 0.996 for c in closes], closes


try:
    market_lite.fetch_tickers()
except Exception as exc:  # noqa: BLE001
    print(f"[shots] LBank unreachable ({exc}); using synthetic data")
    SYNTHETIC["on"] = True
    mobile_main.fetch_tickers = _fake_tickers
    mobile_main.fetch_candles = _fake_candles


class ShotApp(mobile_main.TraderApp):
    @property
    def user_data_dir(self) -> str:
        path = REPO / ".cache" / "mobile_shots"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def on_start(self) -> None:
        self.store.data["watchlist"] = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT"]
        OUT.mkdir(parents=True, exist_ok=True)
        steps = [
            (3.0, lambda: self.go("market"), "1_market"),
            (0.5, lambda: (self.go("signals"), self.screens["signals"].refresh(force=True)), None),
            (20.0, lambda: None, "2_signals"),
            (0.5, lambda: self.go("watch"), None),
            (6.0, lambda: None, "3_watchlist"),
            (0.5, lambda: self.open_analysis("BTC/USDT"), None),
            (6.0, lambda: None, "4_analysis"),
            (0.5, lambda: self.go("settings"), None),
            (1.5, lambda: None, "5_settings"),
        ]
        self._run(steps)

    def _run(self, steps: list) -> None:  # noqa: ANN001
        if not steps:
            print("[shots] done", sorted(p.name for p in OUT.glob("*.png")))
            source = "synthetic (LBank unreachable from runner)" if SYNTHETIC["on"] else "live LBank public API"
            (OUT / "SOURCE.txt").write_text(f"data: {source}\ntaken: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}\n", encoding="utf-8")
            Clock.schedule_once(lambda _dt: self.stop(), 0.5)
            return
        wait, action, name = steps[0]
        action()

        def after(_dt) -> None:  # noqa: ANN001
            if name:
                path = OUT / f"{name}.png"
                self.root.export_to_png(str(path))
                print(f"[shots] {path.name}")
            self._run(steps[1:])

        Clock.schedule_once(after, wait)


if __name__ == "__main__":
    ShotApp().run()
