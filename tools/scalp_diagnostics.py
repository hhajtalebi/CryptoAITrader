"""
تشخیص علت زیان اسکالپ — نسخهٔ ۲.۵.۶.

پرسش: زیان از «جهت اشتباه» می‌آید یا از «هزینه» (کارمزد + اسپرد + لغزش)
و هندسهٔ هدف/حد ضرر؟ این ابزار روی کندل‌های تاریخی همان نامزدهای اسکنر
را با چند جهت (مومنتوم، معکوس، تصادفی) و چند هندسه شبیه‌سازی می‌کند و
امید ریاضی **ناخالص** (بدون هزینه) و **خالص** را کنار هم می‌گذارد.

اجرا:
    PYTHONPATH=. python tools/scalp_diagnostics.py --data-dir <folder of *-5m / *-1m feather|csv> [--out file.json]

هیچ نتیجه‌ای در این ابزار تضمین سود آینده نیست.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.data import load_candles  # noqa: E402
from backtest.execution import ExecutionModel, simulate_trade  # noqa: E402
from backtest.metrics import summarize  # noqa: E402
from trading.scalp_scanner import momentum_percent, recent_volatility  # noqa: E402

FREE = ExecutionModel(fee_percent=0.0, spread_percent=0.0, slippage_percent=0.0)
REAL = ExecutionModel()  # 0.06% fee/side, 0.04% spread, 0.02% slippage
#: هزینهٔ کامل رفت‌وبرگشت (درصد): ۲×کارمزد + اسپرد + ۲×لغزش (بدترین حالت)
ROUND_TRIP_COST = 2 * REAL.fee_percent + REAL.spread_percent + 2 * REAL.slippage_percent


def _direction(kind: str, move: float, rng: random.Random) -> str:
    if kind == "momentum":
        return "LONG" if move > 0 else "SHORT"
    if kind == "fade":
        return "SHORT" if move > 0 else "LONG"
    return rng.choice(("LONG", "SHORT"))


def scanner_trades(candles: list[Any], *, symbol: str, kind: str, model: ExecutionModel,
                   vol_multiple: float = 1.0, min_cost_multiple: float = 0.0,
                   hold: int = 12, seed: int = 7) -> list[Any]:
    """نامزدهای اسکنر (همان فیلتر نوسان/مومنتوم) با SL/TP = ±نوسان × ضریب."""
    rng = random.Random(seed)
    trades = []
    busy_until = -1
    for i in range(60, len(candles) - hold - 1):
        window = candles[i - 59:i + 1]
        vol = recent_volatility(window)
        move = momentum_percent(window)
        if not 0.15 <= vol <= 3.0 or abs(move) < 0.05:
            continue
        if vol * vol_multiple < min_cost_multiple * ROUND_TRIP_COST:
            continue
        if candles[i].timestamp <= busy_until:
            continue
        direction = _direction(kind, move, rng)
        future = candles[i + 1:i + 1 + hold]
        entry = future[0].open
        sign = 1 if direction == "LONG" else -1
        dist = vol * vol_multiple / 100.0
        result = simulate_trade(symbol=symbol, direction=direction, signal_time=candles[i].timestamp,
                                stop_loss=entry * (1 - sign * dist), take_profits=[entry * (1 + sign * dist)],
                                future=future, model=model, max_bars=hold)
        if result is not None:
            trades.append(result)
            busy_until = result.exit_time
    return trades


def ultra_trades(candles: list[Any], *, symbol: str, kind: str, tp_pct: float, sl_pct: float,
                 hold: int, min_move: float, seed: int = 11) -> list[Any]:
    """هندسهٔ پیش‌تنظیم فوق‌سریع: هدف/حد ضرر ثابت درصدی، نگه‌داری کوتاه."""
    rng = random.Random(seed)
    trades = []
    busy_until = -1
    for i in range(2, len(candles) - hold - 1):
        prev = candles[i - 1].close
        move = (candles[i].close - prev) / prev * 100.0 if prev else 0.0
        if abs(move) < min_move or candles[i].timestamp <= busy_until:
            continue
        direction = _direction(kind, move, rng)
        future = candles[i + 1:i + 1 + hold]
        entry = future[0].open
        sign = 1 if direction == "LONG" else -1
        result = simulate_trade(symbol=symbol, direction=direction, signal_time=candles[i].timestamp,
                                stop_loss=entry * (1 - sign * sl_pct / 100), take_profits=[entry * (1 + sign * tp_pct / 100)],
                                future=future, model=REAL, max_bars=hold)
        if result is not None:
            trades.append(result)
            busy_until = result.exit_time
    return trades


def persistence(candles: list[Any], horizons: tuple[int, ...] = (1, 3, 12)) -> dict[str, Any]:
    """پس از مومنتوم ≥ ۰٫۰۵٪ (۶ کندل)، بازده آینده چند درصد هم‌جهت است؟"""
    out: dict[str, Any] = {}
    for h in horizons:
        same = 0
        total = 0
        signed = 0.0
        for i in range(60, len(candles) - h):
            move = momentum_percent(candles[i - 59:i + 1])
            if abs(move) < 0.05:
                continue
            base = candles[i].close
            fwd = (candles[i + h].close - base) / base * 100.0
            if fwd == 0:
                continue
            total += 1
            s = 1 if move > 0 else -1
            same += 1 if fwd * s > 0 else 0
            signed += fwd * s
        out[f"{h}_bars"] = {
            "samples": total,
            "same_direction_percent": round(same / total * 100, 2) if total else None,
            "mean_signed_return_percent": round(signed / total, 4) if total else None,
        }
    return out


def _brief(trades: list[Any]) -> dict[str, Any]:
    s = summarize(trades)
    return {k: s.get(k) for k in ("trades", "win_rate", "profit_factor", "expectancy_r", "avg_bars")}


def dollar_ultra(trades: list[Any], notional: float = 500.0) -> dict[str, Any]:
    pnl = [t.return_percent / 100 * notional for t in trades]
    return {"trades": len(pnl), "win_rate": round(sum(1 for p in pnl if p > 0) / len(pnl) * 100, 2) if pnl else None,
            "avg_usd": round(sum(pnl) / len(pnl), 3) if pnl else None,
            "exit_reasons": {r: sum(1 for t in trades if t.exit_reason == r) for r in {t.exit_reason for t in trades}}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    five: dict[str, list[Any]] = {}
    one: dict[str, list[Any]] = {}
    for path in sorted(Path(args.data_dir).iterdir()):
        if path.suffix.lower() not in (".feather", ".csv", ".parquet"):
            continue
        if "-5m" in path.stem:
            five[path.stem.split("-")[0]] = load_candles(path)
        elif "-1m" in path.stem:
            one[path.stem.split("-")[0]] = load_candles(path)

    report: dict[str, Any] = {"round_trip_cost_percent": ROUND_TRIP_COST, "symbols_5m": sorted(five), "symbols_1m": sorted(one)}

    # ۱) جهت در برابر هزینه — هندسهٔ اسکنر (±۱× نوسان، ۱۲ کندل ۵m)
    block: dict[str, Any] = {}
    for kind in ("momentum", "fade", "random"):
        gross = [t for s, c in five.items() for t in scanner_trades(c, symbol=s, kind=kind, model=FREE)]
        net = [t for s, c in five.items() for t in scanner_trades(c, symbol=s, kind=kind, model=REAL)]
        block[kind] = {"gross_no_costs": _brief(gross), "net_with_costs": _brief(net)}
    report["scanner_geometry_5m"] = block

    # ۲) فیلتر هزینه: فقط وقتی نوسان ≥ k × هزینهٔ رفت‌وبرگشت
    filt: dict[str, Any] = {}
    for k in (0, 2, 3, 4, 6):
        net = [t for s, c in five.items() for t in scanner_trades(c, symbol=s, kind="momentum", model=REAL, min_cost_multiple=k)]
        filt[f"vol>={k}x_cost"] = _brief(net)
    report["cost_filter_momentum_5m"] = filt

    # ۳) هدف/حد ضرر پهن‌تر (نسبت به نوسان) — آیا هزینه نسبی کم می‌شود؟
    wide: dict[str, Any] = {}
    for mult, hold in ((1.0, 12), (2.0, 24), (3.0, 36)):
        net = [t for s, c in five.items() for t in scanner_trades(c, symbol=s, kind="momentum", model=REAL, vol_multiple=mult, hold=hold)]
        gross = [t for s, c in five.items() for t in scanner_trades(c, symbol=s, kind="momentum", model=FREE, vol_multiple=mult, hold=hold)]
        wide[f"{mult}x_vol_{hold}bars"] = {"gross": _brief(gross), "net": _brief(net)}
    report["wider_levels_momentum_5m"] = wide

    # ۴) ماندگاری مومنتوم
    report["momentum_persistence_5m"] = {s: persistence(c) for s, c in five.items()}

    # ۵) هندسهٔ پیش‌تنظیم فوق‌سریع (۱۰$×۵۰ ⇒ حجم ۵۰۰$؛ سود خالص ۲$ ⇒ ۰٫۵۲٪، ضرر خالص ۲$ ⇒ ۰٫۲۸٪)
    ultra: dict[str, Any] = {}
    for label, data, hold in (("1m_3bars", one, 3), ("5m_1bar", five, 1)):
        if not data:
            continue
        for kind in ("momentum", "fade", "random"):
            trades = [t for s, c in data.items() for t in ultra_trades(c, symbol=s, kind=kind, tp_pct=0.52, sl_pct=0.28, hold=hold, min_move=0.04)]
            ultra[f"{label}_{kind}"] = dollar_ultra(trades)
    report["ultra_preset_geometry"] = ultra

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    # نسخهٔ ۲.۷.۰: خروجی هدایت‌شده به فایل در ویندوز cp1252 است و متن فارسی
    # UnicodeEncodeError می‌داد (doctor_report.txt خالی/خطا).
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    raise SystemExit(main())
