"""
ذخیرهٔ تنظیمات و دیدبان روی گوشی — یک فایل JSON ساده.

* نوشتن اتمی (فایل موقت + replace): اگر برنامه وسط ذخیره بسته شود،
  فایل قبلی سالم می‌ماند.
* فایل خراب یا ناقص ← مقادیر پیش‌فرض (برنامه هرگز به خاطرش باز نشدن
  نمی‌خورد).
* بدون Kivy، تا آزمون‌پذیر باشد.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

TIMEFRAMES = ("15m", "1h", "4h", "1d")
SCAN_SIZES = (10, 20, 40)
REFRESH_CHOICES = (0, 30, 60, 120)  # ثانیه؛ ۰ = خاموش

DEFAULTS: dict = {
    "timeframe": "1h",
    "scan_size": 20,
    "refresh_seconds": 60,
    "tradeable_only": False,
    "watchlist": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
}


class Store:
    """تنظیمات + دیدبان، با اعتبارسنجی هر مقدار هنگام خواندن."""

    def __init__(self, folder: str | os.PathLike) -> None:
        self.path = Path(folder) / "mobile_settings.json"
        self.data: dict = dict(DEFAULTS)
        self.data["watchlist"] = list(DEFAULTS["watchlist"])
        self._load()

    # ---- خواندن/نوشتن --------------------------------------------------
    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        if raw.get("timeframe") in TIMEFRAMES:
            self.data["timeframe"] = raw["timeframe"]
        if raw.get("scan_size") in SCAN_SIZES:
            self.data["scan_size"] = raw["scan_size"]
        if raw.get("refresh_seconds") in REFRESH_CHOICES:
            self.data["refresh_seconds"] = raw["refresh_seconds"]
        if isinstance(raw.get("tradeable_only"), bool):
            self.data["tradeable_only"] = raw["tradeable_only"]
        wl = raw.get("watchlist")
        if isinstance(wl, list):
            clean: list[str] = []
            for item in wl:
                if isinstance(item, str) and "/" in item and item.upper() not in clean:
                    clean.append(item.upper())
            self.data["watchlist"] = clean

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass  # ذخیره نشدن تنظیمات نباید برنامه را ببندد

    # ---- تنظیمات ---------------------------------------------------------
    def get(self, key: str):  # noqa: ANN201
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value) -> None:  # noqa: ANN001
        allowed = {
            "timeframe": TIMEFRAMES, "scan_size": SCAN_SIZES,
            "refresh_seconds": REFRESH_CHOICES, "tradeable_only": (True, False),
        }
        if key not in allowed or value not in allowed[key]:
            raise ValueError(f"invalid setting {key}={value!r}")
        self.data[key] = value
        self.save()

    # ---- دیدبان ----------------------------------------------------------
    @property
    def watchlist(self) -> list[str]:
        return list(self.data["watchlist"])

    def is_watched(self, symbol: str) -> bool:
        return symbol.upper() in self.data["watchlist"]

    def toggle_watch(self, symbol: str) -> bool:
        """افزودن/حذف؛ خروجی = آیا الان در دیدبان هست."""
        symbol = symbol.upper()
        wl = self.data["watchlist"]
        if symbol in wl:
            wl.remove(symbol)
            watched = False
        else:
            wl.append(symbol)
            watched = True
        self.save()
        return watched
