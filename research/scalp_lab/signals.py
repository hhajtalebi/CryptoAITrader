"""
خانواده‌های سیگنال ورود — برداری روی کندل ثانیه‌ای.

هر تابع (اندیس‌ها، جهت‌ها) برمی‌گرداند: ثانیه‌هایی که شرط ورود برقرار است و
جهت آن (۱+ خرید، ۱- فروش). شبیه‌ساز فقط وقتی وارد می‌شود که موقعیت قبلی همان
نماد بسته شده باشد.

خانواده‌ها:
    momentum   — منطق فعلی اولترا (`trading.ultra_scalp.momentum`): حرکت پنجرهٔ
                 کوتاه با یکنواختی کافی ← ادامهٔ همان جهت.
    reversion  — بازگشت به میانگین: حرکت غیرعادی (بر حسب نوسان) ← خلاف آن.
    pullback   — روند ۱۵ دقیقه‌ای + اصلاح کوتاه خلاف روند ← هم‌جهت روند.
    breakout   — شکست سقف/کف N ثانیه‌ای با جهش حجم ← ادامهٔ شکست.
"""

from __future__ import annotations

import numpy as np


def _shift(a: np.ndarray, k: int) -> np.ndarray:
    out = np.empty_like(a)
    out[:k] = np.nan
    out[k:] = a[:-k]
    return out


def rolling_sum(a: np.ndarray, w: int) -> np.ndarray:
    cs = np.concatenate([[0.0], np.cumsum(a)])
    out = np.full(a.shape[0], np.nan)
    out[w - 1:] = cs[w:] - cs[:-w]
    return out


def vol_per_second(close: np.ndarray, window: int = 300) -> np.ndarray:
    """انحراف معیار بازدهٔ لگاریتمی هر ثانیه (درصد) — مثل `ultra_scalp.volatility_per_second`."""
    r = np.zeros_like(close)
    r[1:] = np.log(close[1:] / close[:-1])
    var = rolling_sum(r * r, window) / window
    return np.sqrt(var) * 100.0


def momentum_features(close: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray]:
    """(حرکت درصدی، یکنواختی) پنجرهٔ w ثانیه — هم‌ارز `ultra_scalp.momentum` روی نقاط ثانیه‌ای."""
    prev = _shift(close, w)
    move = (close - prev) / prev * 100.0
    step = np.zeros_like(close)
    step[1:] = np.abs(np.diff(close))
    travel = rolling_sum(step, w)
    with np.errstate(invalid="ignore", divide="ignore"):
        cons = np.where(travel > 0, np.abs(close - prev) / travel, 0.0)
    return move, cons


def ema(a: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1.0)
    out = np.empty_like(a)
    acc = a[0]
    for i in range(a.shape[0]):  # یک بار در روز؛ سرعت کافی است
        acc = alpha * a[i] + (1 - alpha) * acc
        out[i] = acc
    return out


def _pack(long_mask: np.ndarray, short_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    long_mask = np.nan_to_num(long_mask, nan=0).astype(bool)
    short_mask = np.nan_to_num(short_mask, nan=0).astype(bool)
    idx = np.flatnonzero(long_mask | short_mask)
    sides = np.where(long_mask[idx], 1.0, -1.0)
    return idx, sides


class Features:
    """ویژگی‌های پرهزینه یک بار برای هر روز محاسبه و کش می‌شوند."""

    def __init__(self, day) -> None:
        self.day = day
        self._cache: dict = {}

    def get(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def vol(self, window: int = 300) -> np.ndarray:
        return self.get(("vol", window), lambda: vol_per_second(self.day.close, window))

    def mom(self, w: int):
        return self.get(("mom", w), lambda: momentum_features(self.day.close, w))

    def ema(self, span: int) -> np.ndarray:
        return self.get(("ema", span), lambda: ema(self.day.close, span))


def momentum(f: Features, w: int, min_move: float, min_cons: float, gate=None):
    move, cons = f.mom(w)
    ok = (np.abs(move) >= min_move) & (cons >= min_cons)
    if gate is not None:
        ok &= gate
    return _pack(ok & (move > 0), ok & (move < 0))


def reversion(f: Features, w: int, z: float):
    c = f.day.close
    sigma = f.vol(600) / 100.0 * np.sqrt(w)
    r = np.log(c / _shift(c, w))
    with np.errstate(invalid="ignore"):
        return _pack(r < -z * sigma, r > z * sigma)


def pullback(f: Features, w: int, z: float, trend_span: int = 900, slope_lag: int = 300):
    c = f.day.close
    e = f.ema(trend_span)
    up = (c > e) & (e > _shift(e, slope_lag))
    down = (c < e) & (e < _shift(e, slope_lag))
    sigma = f.vol(600) / 100.0 * np.sqrt(w)
    r = np.log(c / _shift(c, w))
    with np.errstate(invalid="ignore"):
        return _pack(up & (r < -z * sigma), down & (r > z * sigma))


def breakout(f: Features, n: int, vol_ratio: float):
    d = f.day
    from numpy.lib.stride_tricks import sliding_window_view as swv

    hi = np.full(d.close.shape[0], np.nan); lo = np.full(d.close.shape[0], np.nan)
    if d.close.shape[0] > n + 1:
        hi[n:] = swv(d.high, n)[:-1].max(axis=1)
        lo[n:] = swv(d.low, n)[:-1].min(axis=1)
    v60 = rolling_sum(d.volume, 60)
    v_hour = rolling_sum(d.volume, 3600) / 60.0
    with np.errstate(invalid="ignore", divide="ignore"):
        surge = v60 > vol_ratio * v_hour
        return _pack((d.close > hi) & surge, (d.close < lo) & surge)


def ultra_gate(f: Features, hold: int, target_net: float, costs) -> np.ndarray:
    """
    دروازهٔ `target_unreachable` موتور فعلی (reach_ratio=0.5) — برای بازسازی دقیق خط پایه.

    reach = vol_ps·√hold ≥ max(0.5·حرکت هدف، 2·حرکت هزینه)
    """
    vol = f.vol(300)
    target_move = (target_net + 2 * costs.notional * costs.fee) / costs.notional * 100.0
    cost_move = costs.fee * 200.0 + costs.spread_pct + costs.slip_pct * 2.0
    need = max(0.5 * target_move, 2.0 * cost_move)
    return np.nan_to_num(vol * np.sqrt(hold), nan=0.0) >= need


#: شبکهٔ پارامترهای هر خانواده (عمداً کوچک تا بیش‌برازش کم شود)
FAMILIES: dict[str, list[dict]] = {
    "momentum": [{"w": w, "min_move": m, "min_cons": cc}
                 for w in (10, 30, 60) for m in (0.04, 0.1) for cc in (0.35, 0.6)],
    "reversion": [{"w": w, "z": z} for w in (30, 120, 300) for z in (2.0, 3.0)],
    "pullback": [{"w": w, "z": z} for w in (30, 120) for z in (1.5, 2.5)],
    "breakout": [{"n": n, "vol_ratio": k} for n in (300, 900) for k in (2.0, 4.0)],
}


def build(family: str, f: Features, params: dict):
    if family == "momentum":
        return momentum(f, **params)
    if family == "reversion":
        return reversion(f, **params)
    if family == "pullback":
        return pullback(f, **params)
    if family == "breakout":
        return breakout(f, **params)
    raise KeyError(family)
