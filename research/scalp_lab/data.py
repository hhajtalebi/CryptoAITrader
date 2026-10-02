"""
دریافت دادهٔ ثانیه‌ای و اسپرد واقعی.

* کندل ۱ ثانیه‌ای از آرشیو عمومی بایننس (data.binance.vision) — هر روز یک فایل
  فشرده (~۲ تا ۴ مگابایت برای هر نماد). قیمت نمادهای پرحجم بین صرافی‌ها جز
  چند صدم درصد یکی است؛ تفاوت LBank (اسپرد بازتر) جدا با اسپرد واقعی LBank
  مدل می‌شود.
* اسپرد: عکس لحظه‌ای دفتر سفارش LBank (`/v2/depth.do`). اگر در دسترس نبود،
  مقدار محافظه‌کارانهٔ پیش‌فرض.
"""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

BINANCE_1S = "https://data.binance.vision/data/spot/daily/klines/{sym}/1s/{sym}-1s-{day}.zip"
LBANK_DEPTH = "https://api.lbkex.com/v2/depth.do?symbol={sym}&size=5"

#: اسپرد پیش‌فرض (درصد) وقتی دفتر LBank در دسترس نیست
DEFAULT_SPREAD_MAJOR = 0.02
DEFAULT_SPREAD_ALT = 0.06
MAJORS = {"BTC", "ETH", "SOL", "XRP", "BNB", "DOGE"}


@dataclass
class Day:
    """یک روز کندل ثانیه‌ای یک نماد (آرایه‌های هم‌طول، مرتب بر زمان)."""

    symbol: str
    day: str
    ts: np.ndarray  # ثانیهٔ یونیکس (int64)
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray  # حجم دلاری (quote)

    def __len__(self) -> int:
        return len(self.close)


def _http(url: str, timeout: float = 60.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "CryptoAITrader-research"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def parse_klines(raw_csv: str) -> tuple[np.ndarray, ...]:
    """CSV کندل بایننس ← (ts ثانیه، o، h، l، c، حجم دلاری). مهر میکروثانیه هم پشتیبانی می‌شود."""
    rows = [r for r in csv.reader(io.StringIO(raw_csv)) if r and r[0][:1].isdigit()]
    if not rows:
        raise ValueError("empty kline file")
    data = np.array([[float(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[7])] for r in rows])
    ts = data[:, 0]
    # از ۲۰۲۵ آرشیو اسپات میکروثانیه است؛ قبل از آن میلی‌ثانیه
    if ts[0] > 1e14:
        ts = ts / 1e6
    elif ts[0] > 1e11:
        ts = ts / 1e3
    order = np.argsort(ts, kind="stable")
    return (ts[order].astype(np.int64), *(data[order, i] for i in range(1, 6)))


def fill_gaps(ts: np.ndarray, o, h, l, c, v) -> tuple[np.ndarray, ...]:
    """
    پر کردن ثانیه‌های بدون معامله با کندل تخت (قیمت قبلی، حجم صفر).

    شبیه‌ساز بر پایهٔ اندیس = ثانیه کار می‌کند؛ بدون این، «۱۸۰ ثانیه نگه‌داری»
    در ساعت‌های کم‌معامله بیشتر از ۱۸۰ ثانیهٔ واقعی می‌شد.
    """
    start, end = int(ts[0]), int(ts[-1])
    n = end - start + 1
    idx = (ts - start).astype(np.int64)
    full_c = np.full(n, np.nan)
    full_c[idx] = c
    # پیش‌روی آخرین قیمت معتبر
    mask = np.isnan(full_c)
    last = np.maximum.accumulate(np.where(~mask, np.arange(n), 0))
    full_c = full_c[last]
    full_o = full_c.copy(); full_h = full_c.copy(); full_l = full_c.copy(); full_v = np.zeros(n)
    full_o[idx] = o; full_h[idx] = h; full_l[idx] = l; full_v[idx] = v
    return np.arange(start, end + 1, dtype=np.int64), full_o, full_h, full_l, full_c, full_v


def load_day(symbol: str, day: str, cache: Path) -> Day | None:
    """یک روز داده (با کش روی دیسک). خطای شبکه ← None (آن روز کنار گذاشته می‌شود)."""
    sym = symbol.replace("/", "").upper()
    cache.mkdir(parents=True, exist_ok=True)
    npz = cache / f"{sym}-{day}.npz"
    if npz.is_file():
        z = np.load(npz)
        return Day(symbol, day, z["ts"], z["o"], z["h"], z["l"], z["c"], z["v"])
    try:
        blob = _http(BINANCE_1S.format(sym=sym, day=day))
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            name = archive.namelist()[0]
            raw = archive.read(name).decode("utf-8")
        arrays = fill_gaps(*parse_klines(raw))
    except Exception as exc:  # noqa: BLE001
        print(f"[data] skip {sym} {day}: {exc.__class__.__name__}: {exc}")
        return None
    ts, o, h, l, c, v = arrays
    np.savez_compressed(npz, ts=ts, o=o, h=h, l=l, c=c, v=v)
    return Day(symbol, day, ts, o, h, l, c, v)


def lbank_spreads(symbols: list[str], out: Path | None = None) -> dict[str, float]:
    """
    اسپرد واقعی LBank (درصد) — میانهٔ چند عکس با فاصله، برای هر نماد.

    اسپرد یک عکس تکی پرنوسان است؛ میانهٔ ۵ عکس با ۲ ثانیه فاصله پایدارتر است.
    """
    result: dict[str, float] = {}
    for symbol in symbols:
        base = symbol.split("/")[0].upper()
        samples: list[float] = []
        for _ in range(5):
            try:
                payload = json.loads(_http(LBANK_DEPTH.format(sym=symbol.replace("/", "_").lower()), 15))
                data = payload.get("data") or {}
                bid = float(data["bids"][0][0]); ask = float(data["asks"][0][0])
                if bid > 0 and ask >= bid:
                    samples.append((ask - bid) / ((ask + bid) / 2) * 100.0)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.4)
        if samples:
            result[symbol] = float(np.median(samples))
        else:
            result[symbol] = DEFAULT_SPREAD_MAJOR if base in MAJORS else DEFAULT_SPREAD_ALT
    if out is not None:
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
