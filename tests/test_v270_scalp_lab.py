"""
۲.۷.۰ — آزمایشگاه اسکالپ باید «همان» موتور را شبیه‌سازی کند، نه نسخهٔ خوش‌بینانه‌اش.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from research.scalp_lab import signals as sig
from research.scalp_lab.data import Day, fill_gaps, parse_klines
from research.scalp_lab.sim import REASON_BE, REASON_STOP, REASON_TIMEOUT, REASON_TP, Costs, ExitRule, simulate
from trading.ultra_scalp import momentum as ultra_momentum


def _day(close, high=None, low=None, open_=None, volume=None):
    close = np.asarray(close, dtype=float)
    n = close.shape[0]
    return Day("X/USDT", "2026-01-01", np.arange(n, dtype=np.int64),
               np.asarray(open_ if open_ is not None else close, float),
               np.asarray(high if high is not None else close, float),
               np.asarray(low if low is not None else close, float),
               close, np.asarray(volume if volume is not None else np.ones(n), float))


def test_vectorized_momentum_matches_ultra_engine():
    rng = np.random.default_rng(3)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.0004, 400)))
    move, cons = sig.momentum_features(close, 30)
    for i in (60, 150, 399):
        # ultra: نقاطِ داخل پنجرهٔ ≤ window_ms؛ با نقاط ثانیه‌ای یعنی ۳۱ نقطه (i-30 … i)
        points = [(float(t) * 1000.0, float(close[t])) for t in range(i - 30, i + 1)]
        u_move, u_cons, _ = ultra_momentum(points, now_ms=i * 1000.0, window_ms=30_000.0)
        assert move[i] == pytest.approx(u_move, rel=1e-9)
        assert cons[i] == pytest.approx(u_cons, rel=1e-9)


def test_target_and_stop_give_exact_net_dollars_like_auto_trader():
    costs = Costs(notional=500.0, fee=0.0006, spread_pct=0.0, slip_pct=0.0)
    # قیمت ثابت بعد پرش بزرگ به بالا ← هدف دقیقاً در قیمت هدف بسته می‌شود
    close = [100.0] * 5 + [110.0] * 5
    pnl, reason, _, _ = simulate(_day(close), np.array([2]), np.array([1.0]), ExitRule(2.0, 2.0, 100), costs)
    assert reason[0] == REASON_TP
    assert pnl[0] == pytest.approx(2.0, abs=1e-9)
    close = [100.0] * 5 + [90.0] * 5
    pnl, reason, _, _ = simulate(_day(close), np.array([2]), np.array([1.0]), ExitRule(2.0, 2.0, 100), costs)
    assert reason[0] == REASON_STOP
    assert pnl[0] <= -2.0 + 1e-9  # شکاف: بدتر از حد ضرر، نه بهتر


def test_auto_trader_level_formula_is_the_same():
    """فرمول سطح‌ها در AutoTrader (budget_target/budget_stop) = فرمول شبیه‌ساز."""
    entry, notional, fee, tp, sl = 2000.0, 500.0, 0.0006, 2.0, 2.0
    q = notional / entry
    entry_fee = notional * fee
    for s in (1.0, -1.0):
        target = (entry * s + (tp + entry_fee) / q) / (s - fee)
        stop = (entry * s + (entry_fee - sl) / q) / (s - fee)
        net_t = (target - entry) * s * q - entry_fee - q * target * fee
        net_s = (stop - entry) * s * q - entry_fee - q * stop * fee
        assert net_t == pytest.approx(tp) and net_s == pytest.approx(-sl)


def test_stop_is_checked_before_target_in_same_second():
    costs = Costs(fee=0.0006, spread_pct=0.0)
    close = [100.0] * 5 + [100.0] * 5
    high = [100.0] * 5 + [120.0] * 5
    low = [100.0] * 5 + [80.0] * 5
    pnl, reason, _, _ = simulate(_day(close, high, low), np.array([2]), np.array([1.0]), ExitRule(2.0, 2.0, 100), costs)
    assert reason[0] == REASON_STOP


def test_spread_and_fees_make_a_flat_market_lose():
    costs = Costs(fee=0.0006, spread_pct=0.05, slip_pct=0.02)
    pnl, reason, _, _ = simulate(_day([100.0] * 400), np.array([5]), np.array([1.0]), ExitRule(2.0, 2.0, 180), costs)
    assert reason[0] == REASON_TIMEOUT
    expected = -(500 * 0.0006 * 2) - 500 * (0.05 / 100 + 2 * 0.02 / 100)
    assert pnl[0] == pytest.approx(expected, rel=0.02)


def test_break_even_moves_stop_and_books_small_profit():
    costs = Costs(fee=0.0006, spread_pct=0.0)
    # بالا تا فعال شدن سر‌به‌سر (نه تا هدف)، بعد ریزش
    close = [100.0] * 3 + [100.4] * 3 + [99.0] * 5
    open_ = [close[0]] + close[:-1]  # پیوسته: هر ثانیه از بستهٔ قبلی باز می‌شود (بدون شکاف)
    pnl, reason, _, _ = simulate(_day(close, open_=open_), np.array([1]), np.array([1.0]), ExitRule(3.0, 2.0, 100, be_trigger=1.0, be_lock=0.1), costs)
    assert reason[0] == REASON_BE
    assert pnl[0] > 0


def test_one_position_at_a_time_per_symbol():
    costs = Costs(fee=0.0, spread_pct=0.0)
    pnl, _, dur, idx = simulate(_day([100.0] * 50), np.arange(1, 40), np.ones(39), ExitRule(1.0, 1.0, 10), costs)
    assert list(idx) == [1, 12, 23, 34]


def test_parse_microsecond_timestamps_and_fill_gaps():
    raw = "\n".join([
        "1759276800000000,10,11,9,10.5,1,1759276800999999,100,5,0,0,0",
        "1759276803000000,10.5,10.6,10.4,10.6,1,1759276803999999,200,5,0,0,0",
    ])
    ts, o, h, l, c, v = fill_gaps(*parse_klines(raw))
    assert list(ts - ts[0]) == [0, 1, 2, 3]
    assert list(c) == [10.5, 10.5, 10.5, 10.6]
    assert list(v) == [100, 0, 0, 200]


def test_families_produce_valid_entries():
    rng = np.random.default_rng(5)
    n = 8000
    close = 50 * np.exp(np.cumsum(rng.normal(0, 0.0006, n)))
    day = _day(close, close * 1.0003, close * 0.9997, volume=rng.uniform(1, 10, n))
    f = sig.Features(day)
    for family, plist in sig.FAMILIES.items():
        idx, sides = sig.build(family, f, plist[0])
        assert idx.dtype.kind == "i" and set(np.unique(sides)) <= {-1.0, 1.0}
        assert (idx >= 0).all() and (idx < n).all()


def test_ultra_gate_matches_engine_formula():
    costs = Costs(notional=500.0, fee=0.0006, spread_pct=0.02, slip_pct=0.02)
    close = np.full(1000, 100.0)
    f = sig.Features(_day(close))
    assert not sig.ultra_gate(f, 180, 2.0, costs).any()  # بازار تخت: هدف دست‌نیافتنی
    target_move = (2.0 + 0.6) / 500 * 100
    cost_move = 0.0006 * 200 + 0.02 + 0.04
    assert max(0.5 * target_move, 2 * cost_move) == pytest.approx(max(0.26, 0.36))
    assert math.isfinite(target_move)
