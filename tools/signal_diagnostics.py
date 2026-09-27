"""
تشخیص کیفیت جهت سیگنال — نسخهٔ ۲.۵.۶.

روی ارزیابی‌های ذخیره‌شدهٔ `tools/run_backtest.py` (evals_<SYM>.json) و
کندل‌های همان داده، جدا از مدیریت معامله می‌سنجد:
  • جهت سیگنال چقدر با بازده آینده هم‌سوست (۱۲/۴۸/۹۶ کندل، بدون هزینه)،
  • رأی هر راهبرد چقدر درست بوده،
  • چند درصد معاملات حد ضرر خورده‌اند ولی بعد قیمت به هدف اول رسیده (حد ضرر تنگ)،
  • تفکیک بر اساس جهت، رژیم و اطمینان،
  • چرخش جهت (سیگنال‌های پیاپی متناقض).

اجرا:
    PYTHONPATH=. python tools/signal_diagnostics.py --data-dir <candles> --evals <folder with evals_*.json> [--out file.json]
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.data import load_candles  # noqa: E402

HORIZONS = (12, 48, 96)


def _symbol(stem: str) -> str:
    return stem.split("-")[0].replace("_", "/")


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    hits = sum(1 for v in values if v > 0)
    return {"n": len(values), "hit_percent": round(hits / len(values) * 100, 2),
            "mean_return_percent": round(sum(values) / len(values), 4)}


def analyse(candles: dict[str, list[Any]], evals: list[dict[str, Any]], min_conf: int = 50) -> dict[str, Any]:
    fwd: dict[int, list[float]] = defaultdict(list)
    by_dir: dict[str, list[float]] = defaultdict(list)
    by_regime: dict[str, list[float]] = defaultdict(list)
    by_conf: dict[str, list[float]] = defaultdict(list)
    by_quality: dict[str, list[float]] = defaultdict(list)
    strat: dict[str, list[float]] = defaultdict(list)
    stop_then_target = 0
    stopped = 0
    tp1_first = 0
    neither = 0
    stop_atr: list[float] = []
    flips = 0
    pairs = 0
    per_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in evals:
        per_symbol[e["symbol"]].append(e)

    for symbol, items in per_symbol.items():
        base = candles.get(symbol)
        if not base:
            continue
        stamps = [c.timestamp for c in base]
        items.sort(key=lambda x: x["time"])
        last_dir = None
        for e in items:
            d = e["base_direction"]
            if d in ("LONG", "SHORT") and e.get("stop_loss"):
                if last_dir is not None:
                    pairs += 1
                    flips += 1 if d != last_dir else 0
                last_dir = d
            if d not in ("LONG", "SHORT") or not e.get("stop_loss") or e["technical_confidence"] < min_conf:
                continue
            i = bisect.bisect_left(stamps, e["time"])
            if i >= len(base) - max(HORIZONS):
                continue
            sign = 1 if d == "LONG" else -1
            entry = base[i].open
            for h in HORIZONS:
                ret = (base[i + h - 1].close - entry) / entry * 100 * sign
                fwd[h].append(ret)
            r48 = fwd[48][-1]
            intel = e.get("intelligence") or {}
            by_dir[d].append(r48)
            by_regime[str(intel.get("regime") or "unknown")].append(r48)
            c = e["technical_confidence"]
            by_conf[f"{c // 10 * 10}-{c // 10 * 10 + 9}"].append(r48)
            by_quality[str(e.get("quality") or "")].append(r48)
            for name, score in (intel.get("strategy_scores") or {}).items():
                if abs(score) >= 0.2:
                    # هم‌سویی رأی راهبرد با بازدهٔ آینده (مستقل از جهت نهایی)
                    raw = (base[i + 47].close - entry) / entry * 100
                    strat[name].append(raw * (1 if score > 0 else -1))
            # حد ضرر در برابر هدف اول در ۹۶ کندل
            stop = float(e["stop_loss"])
            tps = e.get("take_profits") or []
            if not tps:
                continue
            tp1 = float(tps[0])
            stop_hit_at = tp_hit_at = None
            for k, candle in enumerate(base[i:i + 96]):
                if stop_hit_at is None and ((candle.low <= stop) if sign > 0 else (candle.high >= stop)):
                    stop_hit_at = k
                if tp_hit_at is None and ((candle.high >= tp1) if sign > 0 else (candle.low <= tp1)):
                    tp_hit_at = k
            if stop_hit_at is not None and (tp_hit_at is None or stop_hit_at <= tp_hit_at):
                stopped += 1
                # آیا پس از خوردن حد ضرر، قیمت به هدف اول رسید؟
                for candle in base[i + stop_hit_at + 1:i + 96]:
                    if (candle.high >= tp1) if sign > 0 else (candle.low <= tp1):
                        stop_then_target += 1
                        break
            elif tp_hit_at is not None:
                tp1_first += 1
            else:
                neither += 1
            atr = None
            for comp in intel.get("components") or []:
                if comp.get("name") == "execution":
                    pass
            stop_atr.append(abs(entry - stop) / entry * 100)

    total_levels = stopped + tp1_first + neither
    return {
        "setups": len(fwd[48]),
        "forward_return_in_signal_direction": {f"{h}_bars": _stats(fwd[h]) for h in HORIZONS},
        "by_direction_48": {k: _stats(v) for k, v in by_dir.items()},
        "by_regime_48": {k: _stats(v) for k, v in sorted(by_regime.items())},
        "by_confidence_48": {k: _stats(v) for k, v in sorted(by_conf.items())},
        "by_quality_48": {k: _stats(v) for k, v in sorted(by_quality.items())},
        "strategy_vote_accuracy_48": {k: _stats(v) for k, v in sorted(strat.items())},
        "levels_96": {
            "stop_first_percent": round(stopped / total_levels * 100, 2) if total_levels else None,
            "tp1_first_percent": round(tp1_first / total_levels * 100, 2) if total_levels else None,
            "neither_percent": round(neither / total_levels * 100, 2) if total_levels else None,
            "stopped_then_reached_tp1_percent_of_stops": round(stop_then_target / stopped * 100, 2) if stopped else None,
            "median_stop_distance_percent": sorted(stop_atr)[len(stop_atr) // 2] if stop_atr else None,
        },
        "direction_flip_percent_between_consecutive_signals": round(flips / pairs * 100, 2) if pairs else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--evals", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--min-confidence", type=int, default=50)
    args = parser.parse_args(argv)
    candles = {}
    for path in sorted(Path(args.data_dir).iterdir()):
        if path.suffix.lower() in (".feather", ".csv", ".parquet") and "-5m" in path.stem:
            candles[_symbol(path.stem)] = load_candles(path)
    evals: list[dict[str, Any]] = []
    for path in sorted(Path(args.evals).glob("evals_*.json")):
        evals += json.loads(path.read_text())
    report = analyse(candles, evals, args.min_confidence)
    report["management_variants_all"] = management_variants(candles, evals, min_conf=args.min_confidence)
    modern = {s for s in candles if s.endswith("/USDT")}
    if modern:
        report["management_variants_usdt_2025"] = management_variants(
            candles, evals, min_conf=args.min_confidence, symbols=modern)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0



def management_variants(candles: dict[str, list[Any]], evals: list[dict[str, Any]], *,
                        min_conf: int = 50, symbols: set[str] | None = None) -> dict[str, Any]:
    """
    همان سیگنال‌ها با مدیریت‌های مختلف: فاصلهٔ حد ضرر × k (اهداف همان
    ضرایب R نسبت به ریسک جدید)، هدف واحد یا پلکانی، نگه‌داری ۹۶/۱۹۲.
    بدون تغییر جهت — فقط اینکه زیان از مدیریت معامله است یا نه.
    """
    from backtest.execution import ExecutionModel, simulate_trade
    from backtest.metrics import summarize

    model = ExecutionModel()
    variants = {
        "current_1x_staged_96": (1.0, (1.5, 2.5, 4.0), 96),
        "stop_1.5x_staged_96": (1.5, (1.5, 2.5, 4.0), 96),
        "stop_2x_staged_192": (2.0, (1.5, 2.5, 4.0), 192),
        "1x_single_tp_2R_96": (1.0, (2.0,), 96),
        "1x_single_tp_1R_96": (1.0, (1.0,), 96),
        "1.5x_single_tp_1.5R_192": (1.5, (1.5,), 192),
    }
    out: dict[str, Any] = {}
    for name, (k, rs, hold) in variants.items():
        trades = []
        for symbol, base in candles.items():
            if symbols and symbol not in symbols:
                continue
            stamps = [c.timestamp for c in base]
            busy = -1
            for e in sorted((x for x in evals if x["symbol"] == symbol), key=lambda x: x["time"]):
                d = e["base_direction"]
                if d not in ("LONG", "SHORT") or not e.get("stop_loss") or e["technical_confidence"] < min_conf:
                    continue
                if e["time"] <= busy:
                    continue
                i = bisect.bisect_left(stamps, e["time"])
                future = base[i:i + hold]
                if len(future) < 2:
                    continue
                sign = 1 if d == "LONG" else -1
                ref = future[0].open
                risk = abs(ref - float(e["stop_loss"])) * k
                stop = ref - sign * risk
                tps = [ref + sign * risk * r for r in rs]
                result = simulate_trade(symbol=symbol, direction=d, signal_time=e["time"], stop_loss=stop,
                                        take_profits=tps, future=future, model=model, max_bars=hold)
                if result is not None:
                    trades.append(result)
                    busy = result.exit_time + 300
        s = summarize(trades)
        out[name] = {key: s.get(key) for key in ("trades", "win_rate", "profit_factor", "expectancy_r", "max_drawdown_percent", "avg_bars")}
    return out


if __name__ == "__main__":
    raise SystemExit(main())
