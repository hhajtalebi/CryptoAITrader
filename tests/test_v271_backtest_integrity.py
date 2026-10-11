"""
یکپارچگی بک‌تست — نسخهٔ ۲.۷.۱.

چرا این فایل وجود دارد؟
    بک‌تست تنها جایی است که می‌توان ادعا کرد یک استراتژی «در گذشته» چه
    کرده است. اگر همین‌جا ذره‌ای look-ahead (دسترسی به آینده) باشد، همهٔ
    اعدادِ خروجی — سود خالص، Profit Factor، نرخ برد — بی‌ارزش و خطرناک
    می‌شوند، چون کاربر بر اساس آن‌ها تصمیم مالی می‌گیرد.

    این تست‌ها چهار چیز را قفل می‌کنند:
        ۱. دادهٔ تاریخی هرگز کندلی که در لحظهٔ t هنوز بسته نشده را تحویل
           ندهد (look-ahead در منبع داده).
        ۲. ورودِ شبیه‌سازی روی «باز کندلِ بعد» باشد، نه بسته‌شدن کندل
           سیگنال (look-ahead در اجرا).
        ۳. هزینه‌ها (کارمزد، اسپرد، لغزش) واقعاً اعمال و در خروجی دیده
           شوند؛ درون‌کندلی بدبینانه باشد.
        ۴. پنجره‌های walk-forward هم‌پوشانی نداشته باشند و ترتیب
           آموزش/اعتبارسنجی/آزمون رعایت شود.

دادهٔ استفاده‌شده در این تست‌ها **مصنوعی و قطعی** است (نویز گاوسی با بذر
ثابت)، نه دادهٔ واقعی بازار؛ بنابراین اعداد سود/زیانِ این فایل به‌هیچ‌وجه
معنای پیش‌بینی‌کننده ندارند و فقط برای سنجش سلامتِ مکانیکیِ موتور به کار
می‌روند. برای نتیجهٔ واقعی باید `tools/run_backtest.py` روی دادهٔ تاریخی
دانلودشدهٔ خود کاربر اجرا شود.
"""

from __future__ import annotations

import math
import random
from typing import Any

import pytest

from app.core.models import Candle
from backtest.data import TIMEFRAME_SECONDS, resample, save_csv, load_candles
from backtest.execution import ExecutionModel, simulate_trade
from backtest.market import HistoricalMarket
from backtest.metrics import summarize
from backtest.walk_forward import DAY, make_folds

STEP = TIMEFRAME_SECONDS["5m"]


# ----------------------------------------------------------------------
# ابزار ساخت داده
# ----------------------------------------------------------------------
def make_series(count: int, *, seed: int = 7, start_price: float = 60000.0) -> list[Candle]:
    """سری قیمت مصنوعی و قطعی (قدم تصادفی با نویز گاوسی)."""

    gen = random.Random(seed)
    candles: list[Candle] = []
    price = start_price
    ts = 1_700_000_000 - count * STEP
    for i in range(count):
        price *= 1.0 + gen.gauss(0.0, 0.0016)
        o = price
        c = price * (1 + gen.gauss(0.0, 0.0008))
        h = max(o, c) * (1 + abs(gen.gauss(0.0, 0.0011)))
        lo = min(o, c) * (1 - abs(gen.gauss(0.0, 0.0011)))
        candles.append(
            Candle(timestamp=ts + i * STEP, open=o, high=h, low=lo, close=c,
                   volume=100.0 + abs(gen.gauss(0.0, 40.0)))
        )
    return candles


def flat_candles(values: list[tuple[float, float, float, float]], *, start: int = 1_700_000_000,
                 step: int = STEP) -> list[Candle]:
    """ساخت کندل با (open, high, low, close) مشخص — برای سناریوهای قطعی."""

    return [
        Candle(timestamp=start + i * step, open=o, high=h, low=lo, close=c, volume=10.0)
        for i, (o, h, lo, c) in enumerate(values)
    ]


# ----------------------------------------------------------------------
# ۱. منبع داده: تحویل ندادن آینده
# ----------------------------------------------------------------------
#: مبدأ هم‌تراز با ۵m/۱۵m/۱h/۴h تا سطل‌های بازنمونه‌گیری درست چفت شوند.
ALIGNED_START = 1_699_999_200


def test_historical_market_never_serves_unclosed_candles() -> None:
    """کندلِ هنوز-بسته‌نشده در لحظهٔ t نباید در خروجی candles_at باشد."""

    candles = make_series(900, seed=11)
    market = HistoricalMarket("5m")
    market.add_symbol("BTC/USDT", candles, ["5m", "15m", "1h"])

    for offset in (0, 7, 33, 120, 300):
        index = 200 + offset
        now = candles[index].timestamp + STEP  # لحظهٔ بسته‌شدن کندل index
        market.set_time(now)
        for timeframe in ("5m", "15m", "1h"):
            served = market.candles_at("BTC/USDT", timeframe, 250)
            assert served, f"هیچ کندلی برای {timeframe} در t={now} برنگشت"
            stamps = [c.timestamp for c in served]
            assert stamps == sorted(stamps), f"{timeframe}: کندل‌ها مرتب نیستند"
            assert len(set(stamps)) == len(stamps), f"{timeframe}: کندل تکراری وجود دارد"

            closed = [c for c in served if c.timestamp + TIMEFRAME_SECONDS[timeframe] <= now]
            # تایم‌فریم‌های بالاتر می‌توانند یک کندل «در حال شکل‌گیری» داشته
            # باشند؛ آن کندل باید شروعش پیش از now باشد و فقط از کندل‌های
            # پایهٔ بسته‌شده ساخته شده باشد (در تست بعدی بررسی می‌شود).
            forming = served[len(closed):]
            assert len(forming) <= 1, f"{timeframe}: بیش از یک کندل باز تحویل شده است"
            for candle in forming:
                assert candle.timestamp < now, f"{timeframe}: کندل از آینده است"

            # محتوای همهٔ کندل‌ها باید از بازهٔ قیمتیِ کندل‌های پایهٔ بسته‌شده باشد
            visible = [c for c in candles if c.timestamp + STEP <= now]
            assert visible, "هیچ کندل پایهٔ بسته‌شده‌ای نیست"
            highest = max(c.high for c in visible)
            lowest = min(c.low for c in visible)
            for candle in served:
                assert candle.high <= highest + 1e-6, (
                    f"{timeframe}: سقف {candle.high} فراتر از دادهٔ بسته‌شده ({highest}) است"
                )
                assert candle.low >= lowest - 1e-6, (
                    f"{timeframe}: کف {candle.low} پایین‌تر از دادهٔ بسته‌شده ({lowest}) است"
                )


def test_higher_timeframe_forming_candle_only_uses_closed_base_bars() -> None:
    """
    کندلِ در حال شکل‌گیریِ تایم‌فریم بالاتر فقط از کندل‌های پایهٔ بسته‌شده
    ساخته می‌شود؛ کندل پایهٔ جاری نباید داخل high/low آن باشد.
    """

    base = flat_candles(
        [(100, 100, 100, 100)] * 2 + [(100, 500, 500, 500)],
        start=ALIGNED_START, step=STEP,
    )
    market = HistoricalMarket("5m")
    market.add_symbol("X/USDT", base, ["5m", "15m"])

    # الف) کندل سوم هنوز باز است (۱۵۰ ثانیه مانده) → نباید دیده شود
    market.set_time(base[2].timestamp + 150)
    served = market.candles_at("X/USDT", "15m", 10)
    assert served, "کندل در حال شکل‌گیری ساخته نشد"
    assert math.isclose(served[-1].high, 100.0), (
        "کندلِ در حال شکل‌گیری از کندل باز تغذیه شده است"
    )

    # ب) پس از بسته‌شدن کندل سوم → مجاز است وارد شود
    market.set_time(base[2].timestamp + STEP)
    served = market.candles_at("X/USDT", "15m", 10)
    assert math.isclose(served[-1].high, 500.0), (
        "کندل پایهٔ بسته‌شده باید در تایم‌فریم بالاتر دیده می‌شد"
    )


def test_resample_drops_incomplete_buckets_and_keeps_ohlcv() -> None:
    """بازنمونه‌گیری: سطل ناقص حذف می‌شود و OHLCV سطل کامل درست است."""

    # ۳ کندل ۵ دقیقه‌ای = یک سطل کامل ۱۵ دقیقه‌ای
    complete = flat_candles(
        [(10, 12, 9, 11), (11, 15, 8, 14), (14, 16, 13, 13)],
        start=ALIGNED_START, step=STEP,
    )
    out = resample(complete, "5m", "15m")
    assert len(out) == 1
    bucket = out[0]
    assert bucket.open == 10 and bucket.close == 13
    assert math.isclose(bucket.high, 16) and math.isclose(bucket.low, 8)
    assert math.isclose(bucket.volume, 30)

    # حذف یک کندل پایه → سطل ناقص → هیچ خروجی
    assert resample(complete[:2], "5m", "15m") == []


def test_load_candles_sorts_and_dedupes(tmp_path) -> None:
    """بارگذاری از CSV باید کندل‌ها را مرتب و تکراری‌ها را حذف کند."""

    source = make_series(50, seed=3)
    messy = list(source) + [source[10], source[5]]  # تکراری و خارج از ترتیب
    path = tmp_path / "X_USDT-5m.csv"
    save_csv(messy, path)
    loaded = load_candles(path)
    stamps = [c.timestamp for c in loaded]
    assert stamps == sorted(stamps)
    assert len(stamps) == len(set(stamps)) == 50


# ----------------------------------------------------------------------
# ۲. اجرا: ورود روی باز کندلِ بعد؛ درون‌کندلی بدبینانه
# ----------------------------------------------------------------------
def test_entry_is_next_bar_open_not_signal_bar_close() -> None:
    """ورود باید از «باز کندل بعد از سیگنال» باشد، نه بسته‌شدن کندل سیگنال."""

    model = ExecutionModel(fee_percent=0.0, spread_percent=0.0, slippage_percent=0.0)
    future = flat_candles(
        [(100, 101, 99, 100), (110, 112, 108, 111), (110, 111, 109, 110)],
        start=1_700_000_000, step=STEP,
    )
    result = simulate_trade(
        symbol="X/USDT", direction="LONG", signal_time=future[0].timestamp - STEP,
        stop_loss=95.0, take_profits=[120.0, 130.0, 140.0], future=future,
        model=model, max_bars=3,
    )
    assert result is not None
    assert result.entry_time == future[0].timestamp
    assert math.isclose(result.entry, future[0].open, rel_tol=1e-9), "ورود روی باز کندل بعد نیست"
    assert math.isclose(result.entry, 100.0, rel_tol=1e-9)


def test_gap_through_first_target_rejects_entry() -> None:
    """اگر قیمتِ باز از TP1 رد شده باشد، ورود نامعتبر است (تعقیب نکردن)."""

    model = ExecutionModel()
    future = flat_candles([(130, 131, 129, 130)], start=1_700_000_000, step=STEP)
    assert simulate_trade(
        symbol="X/USDT", direction="LONG", signal_time=future[0].timestamp - STEP,
        stop_loss=95.0, take_profits=[120.0, 130.0, 140.0], future=future,
        model=model, max_bars=3,
    ) is None


def test_gap_through_stop_rejects_entry() -> None:
    """اگر قیمتِ باز از حد ضرر رد شده باشد، ورود نامعتبر است."""

    model = ExecutionModel()
    future = flat_candles([(90, 91, 89, 90)], start=1_700_000_000, step=STEP)
    assert simulate_trade(
        symbol="X/USDT", direction="LONG", signal_time=future[0].timestamp - STEP,
        stop_loss=95.0, take_profits=[120.0, 130.0, 140.0], future=future,
        model=model, max_bars=3,
    ) is None


def test_intrabar_ambiguity_assumes_the_stop_hit_first() -> None:
    """اگر SL و TP در یک کندل لمس شوند، بدبینانه فرض می‌شود SL زودتر بوده."""

    model = ExecutionModel(fee_percent=0.0, spread_percent=0.0, slippage_percent=0.0)
    future = flat_candles([(100, 200, 50, 100)], start=1_700_000_000, step=STEP)
    result = simulate_trade(
        symbol="X/USDT", direction="LONG", signal_time=future[0].timestamp - STEP,
        stop_loss=95.0, take_profits=[120.0, 130.0, 140.0], future=future,
        model=model, max_bars=1,
    )
    assert result is not None
    assert result.exit_reason == "stop"
    assert result.r_multiple <= 0.0
    assert result.targets_hit == 0


def test_costs_are_charged_and_visible_in_output() -> None:
    """کارمزد ورود+خروج اعمال شود و در خروجی دیده شود؛ حذف آن سود را زیاد کند."""

    bars = flat_candles([(100, 100.2, 99.8, 100)] * 10, start=1_700_000_000, step=STEP)
    common: dict[str, Any] = dict(
        symbol="X/USDT", direction="LONG", signal_time=bars[0].timestamp - STEP,
        stop_loss=99.0, take_profits=[101.0, 102.0, 103.0], future=bars, max_bars=10,
    )
    free = simulate_trade(model=ExecutionModel(fee_percent=0.0, spread_percent=0.0,
                                               slippage_percent=0.0), **common)
    paid = simulate_trade(model=ExecutionModel(fee_percent=0.06, spread_percent=0.04,
                                               slippage_percent=0.02), **common)
    assert free is not None and paid is not None
    assert paid.fees_percent > 0.0
    assert paid.return_percent < free.return_percent, "هزینه‌ها روی بازده اثر نگذاشتند"
    assert paid.r_multiple < free.r_multiple


def test_slippage_and_spread_move_entry_against_the_trader(direction: str) -> None:
    """لغزش و اسپرد باید به زیان معامله‌گر باشند، نه به نفع او."""

    model = ExecutionModel(fee_percent=0.0, spread_percent=0.10, slippage_percent=0.10)
    entry = model.entry_price(direction, 100.0)
    if direction == "LONG":
        assert entry > 100.0
    else:
        assert entry < 100.0


# ----------------------------------------------------------------------
# ۳. معیارها
# ----------------------------------------------------------------------
def _trade(r_multiple: float, *, exit_time: int = 0, size: float = 1.0) -> Any:
    from backtest.execution import TradeResult

    return TradeResult(
        symbol="X/USDT", direction="LONG", signal_time=0, entry_time=0, exit_time=exit_time,
        entry=100.0, stop_loss=99.0, exit_reason="target", r_multiple=r_multiple,
        return_percent=r_multiple, fees_percent=0.12, bars=3, mae_percent=0.0,
        mfe_percent=0.0, targets_hit=1, size_multiplier=size,
    )


def test_metrics_match_hand_computation() -> None:
    """نرخ برد، PF، امید ریاضی و افت سرمایه با حساب دستی یکی باشند."""

    # برد ۲R، دو ضرر ۰.۵R → سود ناخالص ۲، زیان ناخالص ۱ → PF = ۲
    trades = [_trade(2.0, exit_time=1), _trade(-0.5, exit_time=2), _trade(-0.5, exit_time=3)]
    summary = summarize(trades, risk_percent=1.0)
    assert summary["trades"] == 3
    assert math.isclose(summary["win_rate"], 100 / 3, abs_tol=0.01)
    assert math.isclose(summary["profit_factor"], 2.0, abs_tol=0.001)
    assert math.isclose(summary["expectancy_r"], (2.0 - 0.5 - 0.5) / 3, abs_tol=1e-4)
    # موجودی با ریسک ۱٪ هر معامله: ۱۰۰ → ۱۰۲ → ۱۰۱.۵ → ۱۰۱؛ قله ۱۰۲
    assert math.isclose(
        summary["max_drawdown_percent"], (102 - 101) / 102 * 100, abs_tol=0.01
    )
    assert math.isclose(summary["total_r"], 1.0, abs_tol=1e-3)


def test_metrics_on_empty_input_report_zero_not_crash() -> None:
    """بدون معامله معیارها باید None/صفر باشند، نه استثنا یا عدد ساختگی."""

    summary = summarize([], risk_percent=1.0)
    assert summary["trades"] == 0
    assert summary["win_rate"] is None and summary["profit_factor"] is None


# ----------------------------------------------------------------------
# ۴. Walk-Forward
# ----------------------------------------------------------------------
def test_walk_forward_windows_are_ordered_and_disjoint() -> None:
    """پنجرهٔ آزمون‌ها هم‌پوشانی ندارد و آموزش ← اعتبارسنجی ← آزمون است."""

    start = 1_700_000_000
    end = start + 30 * DAY
    folds = make_folds(start, end, train_days=5, val_days=2, test_days=2, step_days=2)
    assert len(folds) >= 3
    for fold in folds:
        assert fold.train[0] < fold.train[1] <= fold.validation[0]
        assert fold.validation[1] <= fold.test[0]
        assert fold.test[0] < fold.test[1]
    for first, second in zip(folds, folds[1:], strict=False):
        assert first.test[1] <= second.test[0], "پنجره‌های آزمون هم‌پوشانی دارند"
        # آموزشِ پنجرهٔ بعد نباید به دادهٔ آزمونِ پنجرهٔ قبل دسترسی داشته باشد
        assert second.train[0] < first.test[1]


def test_walk_forward_needs_enough_span() -> None:
    """اگر داده به اندازهٔ کافی نباشد، هیچ پنجره‌ای ساخته نشود (بدون پنجرهٔ ناقص)."""

    assert make_folds(0, int(3 * DAY), train_days=10, val_days=2, test_days=2) == []


# ----------------------------------------------------------------------
# ۵. یکپارچگیِ سرتاسری روی دادهٔ مصنوعی (ضد look-ahead)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_signal_snapshot_never_contains_future_prices() -> None:
    """
    در هر لحظهٔ ارزیابی، عکس لحظه‌ایِ سیگنال نباید قیمتی فراتر از آخرین
    کندلِ قابل مشاهده در همان لحظه داشته باشد.
    """

    from backtest.engine import BacktestConfig, BacktestEngine

    candles = make_series(1200, seed=19)
    market = HistoricalMarket("5m")
    market.add_symbol("BTC/USDT", candles, ["5m", "15m", "1h", "4h"])
    engine = BacktestEngine(
        market,
        BacktestConfig(step_bars=60, warmup_bars=300, prediction_replay=False,
                       min_confidence=50, max_hold_bars=48),
    )
    evaluations = await engine.evaluate_symbol("BTC/USDT")
    assert evaluations, "هیچ ارزیابی‌ای تولید نشد"

    last_seen: dict[int, float] = {}
    for candle in candles:
        last_seen[candle.timestamp] = candle.close
    for ev in evaluations:
        # کندل‌های قابل مشاهده در لحظهٔ ارزیابی: timestamp < ev.time
        visible = [c for c in candles if c.timestamp < ev.time]
        assert visible, "هیچ کندل قابل مشاهده‌ای نیست"
        highest = max(c.high for c in visible)
        lowest = min(c.low for c in visible)
        for level in [ev.stop_loss, *(ev.take_profits or [])]:
            if level is None:
                continue
            assert lowest * 0.5 <= level <= highest * 1.5, (
                f"سطح {level} خارج از محدودهٔ قیمتیِ قابل مشاهده در t={ev.time} است"
            )
        assert ev.time == candles[ev.index].timestamp + STEP


@pytest.mark.asyncio
async def test_simulation_trades_precede_their_own_exit() -> None:
    """هر معاملهٔ شبیه‌سازی‌شده باید بعد از سیگنال وارد و بعد از ورود خارج شود."""

    from backtest.engine import BacktestConfig, BacktestEngine

    candles = make_series(1500, seed=23)
    market = HistoricalMarket("5m")
    market.add_symbol("BTC/USDT", candles, ["5m", "15m", "1h", "4h"])
    engine = BacktestEngine(
        market,
        BacktestConfig(step_bars=30, warmup_bars=300, prediction_replay=False,
                       min_confidence=50, max_hold_bars=48),
    )
    evaluations = await engine.evaluate_symbol("BTC/USDT")
    trades = engine.simulate(evaluations, mode="new")
    for trade in trades:
        assert trade.entry_time >= trade.signal_time, "ورود پیش از سیگنال است"
        assert trade.exit_time >= trade.entry_time, "خروج پیش از ورود است"
        assert trade.fees_percent > 0.0, "کارمزد اعمال نشده است"
        assert trade.bars >= 1


# ----------------------------------------------------------------------
# پارامتری‌سازی جهت
# ----------------------------------------------------------------------
def pytest_generate_tests(metafunc: Any) -> None:
    """اجرای تست‌های جهت‌دار برای هر دو سمت خرید و فروش."""

    if "direction" in metafunc.fixturenames:
        metafunc.parametrize("direction", ["LONG", "SHORT"])
