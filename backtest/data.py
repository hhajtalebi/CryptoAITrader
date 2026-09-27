"""
بارگذاری دادهٔ تاریخی و بازنمونه‌گیری.

قالب‌های پشتیبانی‌شده:
    • CSV با ستون‌های date/timestamp, open, high, low, close, volume
      (timestamp ثانیه یا میلی‌ثانیه یا رشتهٔ تاریخ)
    • Feather/Parquet (نیازمند pyarrow؛ اختیاری)

بازنمونه‌گیری فقط کندل‌های «کامل» می‌سازد: سطل (bucket) زمانی که همهٔ
کندل‌های پایه‌اش موجود نباشد کنار گذاشته می‌شود تا کندل ناقص به‌عنوان
کندل بسته‌شده وارد تحلیل نشود.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.models import Candle

TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200, "1d": 86400,
}


def _to_seconds(value: Any) -> int:
    if isinstance(value, (int, float)):
        number = float(value)
        return int(number / 1000) if number > 1e11 else int(number)
    if hasattr(value, "timestamp"):
        ts = value
        if getattr(ts, "tzinfo", None) is None and hasattr(ts, "tz_localize"):
            ts = ts.tz_localize("UTC")
        elif getattr(ts, "tzinfo", None) is None:
            ts = ts.replace(tzinfo=UTC)
        return int(ts.timestamp())
    text = str(value).strip()
    if text.replace(".", "", 1).isdigit():
        return _to_seconds(float(text))
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp())


def load_candles(path: str | Path) -> list[Candle]:
    """بارگذاری کندل از CSV یا Feather/Parquet؛ مرتب و بدون تکرار."""
    path = Path(path)
    rows: list[Candle] = []
    suffix = path.suffix.lower()
    if suffix in (".feather", ".parquet"):
        import pandas as pd  # وابستگی موجود پروژه

        frame = pd.read_feather(path) if suffix == ".feather" else pd.read_parquet(path)
        time_col = "date" if "date" in frame.columns else frame.columns[0]
        for record in frame.itertuples(index=False):
            data = record._asdict()
            rows.append(
                Candle(
                    timestamp=_to_seconds(data[time_col]),
                    open=float(data["open"]), high=float(data["high"]),
                    low=float(data["low"]), close=float(data["close"]),
                    volume=float(data["volume"]),
                )
            )
    else:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for data in reader:
                lowered = {k.strip().lower(): v for k, v in data.items() if k}
                stamp = lowered.get("timestamp") or lowered.get("date") or lowered.get("time")
                if stamp is None:
                    continue
                rows.append(
                    Candle(
                        timestamp=_to_seconds(stamp),
                        open=float(lowered["open"]), high=float(lowered["high"]),
                        low=float(lowered["low"]), close=float(lowered["close"]),
                        volume=float(lowered.get("volume") or 0.0),
                    )
                )
    rows.sort(key=lambda c: c.timestamp)
    unique: list[Candle] = []
    last = None
    for candle in rows:
        if candle.timestamp != last:
            unique.append(candle)
            last = candle.timestamp
    return unique


def save_csv(candles: list[Candle], path: str | Path) -> None:
    """ذخیرهٔ کندل‌ها در CSV ساده (timestamp ثانیه)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for c in candles:
            writer.writerow([c.timestamp, c.open, c.high, c.low, c.close, c.volume])


def resample(candles: list[Candle], base_tf: str, target_tf: str) -> list[Candle]:
    """
    بازنمونه‌گیری به تایم‌فریم بزرگ‌تر؛ فقط سطل‌های کامل.

    سطل کامل یعنی تعداد کندل پایه = target/base. سطل ناقص (شکاف داده)
    حذف می‌شود.
    """
    base = TIMEFRAME_SECONDS[base_tf]
    step = TIMEFRAME_SECONDS[target_tf]
    if step == base:
        return list(candles)
    if step % base:
        raise ValueError(f"{target_tf} is not a multiple of {base_tf}")
    need = step // base
    out: list[Candle] = []
    bucket: list[Candle] = []
    bucket_start: int | None = None
    for candle in candles:
        start = candle.timestamp - candle.timestamp % step
        if bucket_start is not None and start != bucket_start:
            if len(bucket) == need:
                out.append(_merge(bucket_start, bucket))
            bucket = []
        bucket_start = start
        bucket.append(candle)
    if bucket and bucket_start is not None and len(bucket) == need:
        out.append(_merge(bucket_start, bucket))
    return out


def _merge(start: int, bucket: list[Candle]) -> Candle:
    return Candle(
        timestamp=start,
        open=bucket[0].open,
        high=max(c.high for c in bucket),
        low=min(c.low for c in bucket),
        close=bucket[-1].close,
        volume=sum(c.volume for c in bucket),
    )


__all__ = ["TIMEFRAME_SECONDS", "load_candles", "resample", "save_csv"]
