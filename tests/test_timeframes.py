"""آزمون موتور تایم‌فریم."""

from __future__ import annotations

import pytest

from market.timeframes import (
    SUPPORTED_TIMEFRAMES,
    aggregate_candles,
    align_timestamp,
    candles_needed,
    find_aggregation_source,
    timeframe_seconds,
)
from tests.conftest import make_candles


def test_fourteen_timeframes_are_defined() -> None:
    """
    برنامه باید ۱۴ تایم‌فریم داشته باشد: از ۱ دقیقه تا ۲۴ ساعت،
    به‌علاوه هفتگی و ماهانه.
    """
    codes = [tf.code for tf in SUPPORTED_TIMEFRAMES]

    assert len(SUPPORTED_TIMEFRAMES) == 14
    assert codes == [
        "1m", "3m", "5m", "15m", "30m",
        "1h", "2h", "4h", "6h", "8h", "12h",
        "1d", "1w", "1M",
    ]


def test_monthly_timeframe_is_available() -> None:
    """تایم‌فریم ماهانه باید تعریف شده و قابل استفاده باشد."""
    monthly = [tf for tf in SUPPORTED_TIMEFRAMES if tf.code == "1M"]

    assert monthly, "تایم‌فریم ماهانه تعریف نشده است"
    assert timeframe_seconds("1M") == 2592000


def test_monthly_alignment_snaps_to_first_of_month() -> None:
    """
    شروع کندل ماهانه باید اول ماه باشد.

    ماه‌ها طول یکسان ندارند، پس نمی‌توان مثل بقیه تایم‌فریم‌ها با
    باقی‌مانده ساده هم‌ترازش کرد.
    """
    from datetime import UTC, datetime

    middle = int(datetime(2026, 3, 17, 13, 45, tzinfo=UTC).timestamp())
    expected = int(datetime(2026, 3, 1, tzinfo=UTC).timestamp())

    assert align_timestamp(middle, "1M") == expected


def test_monthly_cannot_be_aggregated() -> None:
    """
    ماه مضرب صحیحی از هیچ تایم‌فریم کوچک‌تری نیست (۲۸ تا ۳۱ روز)،
    پس باید مستقیم از صرافی گرفته شود نه با تجمیع.
    """
    assert find_aggregation_source("1M", {"1d", "1w", "4h", "1h"}) is None


def test_monthly_is_never_confused_with_one_minute() -> None:
    """
    «1M» ماهانه است و «1m» یک‌دقیقه‌ای.

    این دو فقط در بزرگی یک حرف فرق دارند و کدی که ورودی را lower()
    می‌کرد، بی‌صدا نمودار ماهانه را به یک‌دقیقه‌ای تبدیل می‌کرد.
    """
    from market.timeframes import normalize_timeframe

    assert normalize_timeframe("1M") == "1M"
    assert normalize_timeframe("1m") == "1m"
    assert timeframe_seconds("1M") != timeframe_seconds("1m")

    # ورودی نامرتب یا با حروف بزرگ برای بقیه کدها باید همچنان کار کند
    assert normalize_timeframe(" 1H ") == "1h"
    assert normalize_timeframe("4H") == "4h"


def test_timeframe_seconds_are_correct() -> None:
    """تبدیل تایم‌فریم به ثانیه باید دقیق باشد."""
    assert timeframe_seconds("1m") == 60
    assert timeframe_seconds("1h") == 3600
    assert timeframe_seconds("4h") == 14400
    assert timeframe_seconds("1d") == 86400
    assert timeframe_seconds("1w") == 604800


def test_weekly_alignment_starts_on_monday() -> None:
    """
    هفته باید از دوشنبه شروع شود.

    این مورد قبلاً اشتباه بود (یکشنبه) و باعث جابه‌جایی کندل هفتگی می‌شد.
    """
    from datetime import UTC, datetime

    # چهارشنبه ۱۵ ژانویه ۲۰۲۵
    wednesday = int(datetime(2025, 1, 15, 12, 0, tzinfo=UTC).timestamp())
    aligned = align_timestamp(wednesday, "1w")
    assert datetime.fromtimestamp(aligned, UTC).weekday() == 0


def test_aggregation_produces_fewer_candles() -> None:
    """تجمیع باید تعداد کندل را کاهش دهد."""
    hourly = make_candles(count=240, seed=5)
    four_hourly = aggregate_candles(hourly, "1h", "4h")
    assert 0 < len(four_hourly) <= len(hourly) // 4 + 1


def test_aggregation_preserves_ohlc_semantics() -> None:
    """در تجمیع، بالاترین و پایین‌ترین قیمت باید حفظ شوند."""
    hourly = make_candles(count=80, seed=6)
    aggregated = aggregate_candles(hourly, "1h", "4h")
    assert aggregated
    for candle in aggregated:
        assert candle.high >= candle.close
        assert candle.high >= candle.open
        assert candle.low <= candle.close
        assert candle.low <= candle.open


def test_unsupported_timeframes_find_an_aggregation_source() -> None:
    """
    تایم‌فریم‌هایی که LBank ندارد باید از منبع دیگری ساخته شوند.
    """
    supported = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"}
    for target in ("3m", "2h", "6h", "8h", "12h"):
        source = find_aggregation_source(target, supported)
        assert source is not None, f"No aggregation source for {target}"
        assert timeframe_seconds(target) % timeframe_seconds(source) == 0


def test_candles_needed_accounts_for_aggregation() -> None:
    """تعداد کندل موردنیاز منبع باید ضریبی از هدف باشد."""
    assert candles_needed("4h", "1h", 100) >= 400
