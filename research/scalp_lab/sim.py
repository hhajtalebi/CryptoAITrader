"""
شبیه‌ساز معامله روی کندل ثانیه‌ای — همان قواعد موتور واقعی.

قواعدی که عیناً از `trading/auto_trader.py` آمده‌اند:
    * ورود LONG با Ask و SHORT با Bid (نیم‌اسپرد + لغزش علیه ما)؛
    * خروج LONG با Bid و SHORT با Ask (باز هم با لغزش علیه ما)؛
    * سطح هدف/حد ضرر از عدد **خالص** دلاری پس از کارمزد ورود و خروج:
          target = (entry·s + (TP + fee_in)/q) / (s − f)
          stop   = (entry·s + (fee_in − SL)/q) / (s − f)
    * سر‌به‌سر: وقتی سود خالص به trigger رسید، حد ضرر به ورود + کارمزدها + قفل؛
    * ترتیب بررسی محافظه‌کارانه: اگر در یک ثانیه هم حد ضرر و هم هدف لمس شد،
      **حد ضرر** ثبت می‌شود؛
    * در هر نماد فقط یک موقعیت باز (ورود بعدی پس از بسته‌شدن قبلی).

اگر numba نصب باشد حلقه‌ها کامپایل می‌شوند؛ وگرنه همان کد پایتونی اجرا می‌شود.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:  # pragma: no cover - فقط شتاب
    from numba import njit
except Exception:  # noqa: BLE001
    def njit(*args, **kwargs):  # type: ignore[no-redef]
        if args and callable(args[0]):
            return args[0]
        return lambda f: f

REASON_STOP, REASON_TP, REASON_TIMEOUT, REASON_BE = 0, 1, 2, 3


@dataclass(frozen=True)
class ExitRule:
    """قواعد خروج به دلار خالص (روی ارزش موقعیت `notional`)."""

    tp: float          # سود خالص هدف ($)
    sl: float          # زیان خالص حد ضرر ($)
    hold: int          # بیشینهٔ نگه‌داری (ثانیه)
    be_trigger: float = 0.0  # ۰ = سر‌به‌سر خاموش
    be_lock: float = 0.1

    def key(self) -> str:
        be = f"be{self.be_trigger:g}" if self.be_trigger > 0 else "nobe"
        return f"tp{self.tp:g}_sl{self.sl:g}_h{self.hold}_{be}"


@dataclass(frozen=True)
class Costs:
    notional: float = 500.0   # ۱۰ دلار × اهرم ۵۰ (پیش‌تنظیم اولترا)
    fee: float = 0.0006       # کارمزد taker هر طرف
    spread_pct: float = 0.02  # اسپرد کامل (درصد)
    slip_pct: float = 0.0     # لغزش هر طرف (درصد)


@njit(cache=True)
def _simulate(o, h, l, c, entries, sides, notional, fee, half_spread, slip,
              tp, sl, hold, be_trigger, be_lock, out_pnl, out_reason, out_dur, out_idx):
    """حلقهٔ اصلی؛ بازگشتی = شمار معامله‌ها (خروجی‌ها در آرایه‌های out_*)."""
    n = c.shape[0]
    count = 0
    busy_until = -1
    for k in range(entries.shape[0]):
        i = entries[k]
        if i <= busy_until or i >= n - 2:
            continue
        s = sides[k]
        mid = c[i]
        if mid <= 0:
            continue
        if s > 0:
            entry = mid * (1.0 + half_spread) * (1.0 + slip)
        else:
            entry = mid * (1.0 - half_spread) * (1.0 - slip)
        q = notional / entry
        fee_in = notional * fee
        target = (entry * s + (tp + fee_in) / q) / (s - fee)
        stop = (entry * s + (fee_in - sl) / q) / (s - fee)
        be_price = 0.0
        if be_trigger > 0:
            be_price = (entry * s + (be_trigger + fee_in) / q) / (s - fee)
        armed = False
        end = min(n - 1, i + hold)
        exit_price = 0.0
        reason = REASON_TIMEOUT
        j_exit = end
        for j in range(i + 1, end + 1):
            # قیمت سمت خروج در این ثانیه (با اسپرد و لغزش علیه ما)
            if s > 0:
                adj = (1.0 - half_spread) * (1.0 - slip)
                hi = h[j] * adj; lo = l[j] * adj; op = o[j] * adj
                worst = lo; best = hi
                stop_hit = worst <= stop
                tp_hit = best >= target
            else:
                adj = (1.0 + half_spread) * (1.0 + slip)
                hi = h[j] * adj; lo = l[j] * adj; op = o[j] * adj
                worst = hi; best = lo
                stop_hit = worst >= stop
                tp_hit = best <= target
            if stop_hit:
                # شکاف: اگر ثانیه بیرون از حد ضرر باز شد، همان قیمت بدتر
                if s > 0:
                    exit_price = op if op < stop else stop
                else:
                    exit_price = op if op > stop else stop
                reason = REASON_BE if armed else REASON_STOP
                j_exit = j
                break
            if tp_hit:
                exit_price = target
                reason = REASON_TP
                j_exit = j
                break
            if be_trigger > 0 and not armed:
                if (s > 0 and best >= be_price) or (s < 0 and best <= be_price):
                    cover = (2.0 * fee_in + be_lock) / (q * (1.0 - s * fee))
                    new_stop = entry + s * cover
                    if (s > 0 and new_stop > stop) or (s < 0 and new_stop < stop):
                        stop = new_stop
                    armed = True
        if reason == REASON_TIMEOUT:
            if s > 0:
                exit_price = c[end] * (1.0 - half_spread) * (1.0 - slip)
            else:
                exit_price = c[end] * (1.0 + half_spread) * (1.0 + slip)
            j_exit = end
        pnl = (exit_price - entry) * s * q - fee_in - q * exit_price * fee
        out_pnl[count] = pnl
        out_reason[count] = reason
        out_dur[count] = j_exit - i
        out_idx[count] = i
        count += 1
        busy_until = j_exit
    return count


def simulate(day, entries: np.ndarray, sides: np.ndarray, rule: ExitRule, costs: Costs):
    """اجرای یک قاعدهٔ خروج روی ورودهای یک روز ← (pnl، دلیل، مدت، اندیس ورود)."""
    m = entries.shape[0]
    out_pnl = np.zeros(m); out_reason = np.zeros(m, dtype=np.int64)
    out_dur = np.zeros(m, dtype=np.int64); out_idx = np.zeros(m, dtype=np.int64)
    if m == 0:
        return out_pnl[:0], out_reason[:0], out_dur[:0], out_idx[:0]
    count = _simulate(
        day.open, day.high, day.low, day.close,
        entries.astype(np.int64), sides.astype(np.float64),
        float(costs.notional), float(costs.fee), float(costs.spread_pct) / 200.0, float(costs.slip_pct) / 100.0,
        float(rule.tp), float(rule.sl), int(rule.hold), float(rule.be_trigger), float(rule.be_lock),
        out_pnl, out_reason, out_dur, out_idx,
    )
    return out_pnl[:count], out_reason[:count], out_dur[:count], out_idx[:count]


def metrics(pnl: np.ndarray, reason: np.ndarray | None = None) -> dict:
    """آمار خلاصه: شمار، نرخ برد، میانگین خالص، ضریب سود، افت."""
    n = int(pnl.shape[0])
    if n == 0:
        return {"trades": 0, "win_rate": 0.0, "avg": 0.0, "total": 0.0, "pf": 0.0,
                "avg_win": 0.0, "avg_loss": 0.0, "max_dd": 0.0}
    wins = pnl[pnl > 0]; losses = pnl[pnl <= 0]
    equity = np.cumsum(pnl)
    dd = float(np.max(np.maximum.accumulate(equity) - equity)) if n else 0.0
    gross_win = float(wins.sum()); gross_loss = float(-losses.sum())
    out = {
        "trades": n,
        "win_rate": round(100.0 * wins.shape[0] / n, 2),
        "avg": round(float(pnl.mean()), 4),
        "total": round(float(pnl.sum()), 2),
        "pf": round(gross_win / gross_loss, 3) if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0),
        "avg_win": round(float(wins.mean()), 4) if wins.shape[0] else 0.0,
        "avg_loss": round(float(losses.mean()), 4) if losses.shape[0] else 0.0,
        "max_dd": round(dd, 2),
    }
    if reason is not None and n:
        names = {REASON_STOP: "stop", REASON_TP: "tp", REASON_TIMEOUT: "timeout", REASON_BE: "break_even"}
        out["exits"] = {names[k]: int((reason == k).sum()) for k in names}
    return out
