"""
معیارهای عملکرد بک‌تست.

همه بر حسب R (مضرب ریسک) و درصد سرمایه با ریسک ثابت هر معامله
(`risk_percent` × size_multiplier) محاسبه می‌شوند. افت سرمایه روی منحنی
سرمایهٔ پرتفوی (معاملات همهٔ نمادها به ترتیب زمان خروج) است.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from backtest.execution import TradeResult


def summarize(trades: Iterable[TradeResult], *, risk_percent: float = 1.0) -> dict[str, Any]:
    """خلاصهٔ عملکرد: تعداد، نرخ برد، PF، امید ریاضی، افت، بازده."""
    items = sorted(trades, key=lambda t: (t.exit_time, t.symbol))
    n = len(items)
    if n == 0:
        return {
            "trades": 0, "win_rate": None, "profit_factor": None, "expectancy_r": None,
            "avg_r": None, "total_r": 0.0, "return_percent": 0.0, "max_drawdown_percent": 0.0,
            "long": 0, "short": 0,
        }
    wins = [t for t in items if t.r_multiple > 0]
    gross_win = sum(t.r_multiple * t.size_multiplier for t in items if t.r_multiple > 0)
    gross_loss = -sum(t.r_multiple * t.size_multiplier for t in items if t.r_multiple < 0)
    equity = 100.0
    peak = equity
    max_dd = 0.0
    for trade in items:
        equity += trade.r_multiple * risk_percent * trade.size_multiplier
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100.0 if peak > 0 else 0.0)
    sized_r = [t.r_multiple * t.size_multiplier for t in items]
    mean = sum(sized_r) / n
    std = math.sqrt(sum((r - mean) ** 2 for r in sized_r) / (n - 1)) if n > 1 else 0.0
    return {
        "trades": n,
        "win_rate": round(len(wins) / n * 100.0, 2),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else None,
        "expectancy_r": round(mean, 4),
        "avg_r": round(sum(t.r_multiple for t in items) / n, 4),
        "total_r": round(sum(sized_r), 3),
        "return_percent": round(equity - 100.0, 3),
        "max_drawdown_percent": round(max_dd, 3),
        "sharpe_per_trade": round(mean / std, 4) if std > 0 else None,
        "long": sum(1 for t in items if t.direction == "LONG"),
        "short": sum(1 for t in items if t.direction == "SHORT"),
        "avg_bars": round(sum(t.bars for t in items) / n, 2),
        "fees_percent_total": round(sum(t.fees_percent for t in items), 3),
    }


def by_key(trades: Iterable[TradeResult], key: str, *, risk_percent: float = 1.0) -> dict[str, Any]:
    """خلاصه به تفکیک یک کلید meta (مثلاً quality یا regime)."""
    groups: dict[str, list[TradeResult]] = defaultdict(list)
    for trade in trades:
        groups[str(trade.meta.get(key, ""))].append(trade)
    return {name: summarize(group, risk_percent=risk_percent) for name, group in sorted(groups.items())}


def calibration(trades: Iterable[TradeResult], *, key: str = "final_confidence") -> dict[str, Any]:
    """
    کالیبراسیون: نرخ برد واقعی هر بازهٔ اطمینان و امتیاز Brier.

    توجه: confidence برنامه «احتمال» نیست؛ این جدول دقیقاً نشان می‌دهد
    فاصلهٔ آن از احتمال واقعی چقدر است.
    """
    buckets: dict[str, list[TradeResult]] = defaultdict(list)
    brier_sum = 0.0
    count = 0
    monotonic_rates: list[float] = []
    for trade in trades:
        value = trade.meta.get(key)
        if not isinstance(value, (int, float)):
            continue
        low = int(value // 10 * 10)
        buckets[f"{low}-{low + 9}"].append(trade)
        p = max(0.0, min(1.0, float(value) / 100.0))
        brier_sum += (p - (1.0 if trade.won else 0.0)) ** 2
        count += 1
    table = {}
    for name in sorted(buckets, key=lambda s: int(s.split("-")[0])):
        group = buckets[name]
        rate = sum(1 for t in group if t.won) / len(group) * 100.0
        table[name] = {"trades": len(group), "win_rate": round(rate, 2),
                       "avg_r": round(sum(t.r_multiple for t in group) / len(group), 4)}
        if len(group) >= 10:
            monotonic_rates.append(rate)
    increasing = all(b >= a - 5 for a, b in zip(monotonic_rates, monotonic_rates[1:]))
    return {
        "buckets": table,
        "brier": round(brier_sum / count, 4) if count else None,
        "samples": count,
        "roughly_monotonic": increasing if len(monotonic_rates) >= 2 else None,
    }


__all__ = ["by_key", "calibration", "summarize"]
