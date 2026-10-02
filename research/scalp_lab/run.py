"""
اجرای پژوهش: خط پایهٔ فعلی + جست‌وجوی شبکه‌ای + اعتبارسنجی بیرون از نمونه.

    python -m research.scalp_lab.run --days 7 --train-days 4 --out research/results

روش (برای جلوگیری از خودفریبی):
    ۱. روزهای اول (train) فقط برای انتخاب پارامتر؛
    ۲. روزهای آخر (test) هرگز در انتخاب دیده نمی‌شوند؛ عدد گزارش‌شده همین است؛
    ۳. هزینهٔ کامل: کارمزد taker هر دو طرف، اسپرد واقعی LBank، لغزش هر طرف؛
    ۴. خط پایه = دقیقاً پیش‌تنظیم فعلی اولترا (۱۰$ × ۵۰، هدف خالص ۲$، حد ضرر ۲$،
       ۱۸۰ ثانیه، سر‌به‌سر در ۱$، دروازهٔ دست‌یافتنی بودن هدف).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from research.scalp_lab import data as data_mod
from research.scalp_lab import signals as sig
from research.scalp_lab.sim import Costs, ExitRule, metrics, simulate

SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "BNB/USDT", "ADA/USDT",
    "AVAX/USDT", "LINK/USDT", "DOT/USDT", "LTC/USDT", "TRX/USDT", "SUI/USDT", "NEAR/USDT",
    "APT/USDT", "ARB/USDT", "OP/USDT", "PEPE/USDT", "WIF/USDT", "FIL/USDT", "ATOM/USDT",
    "UNI/USDT", "AAVE/USDT", "INJ/USDT", "ETC/USDT", "BCH/USDT",
]

#: خط پایه = پیش‌تنظیم فعلی اولترا (trades_page.ULTRA_PRESET + پیش‌فرض‌های AutoTradeConfig)
BASELINE_SIGNAL = ("momentum", {"w": 30, "min_move": 0.04, "min_cons": 0.35})
BASELINE_EXIT = ExitRule(tp=2.0, sl=2.0, hold=180, be_trigger=1.0, be_lock=0.1)
SLIPPAGE_PCT = 0.02  # AutoTradeConfig.slippage_percent

EXIT_GRID = [
    ExitRule(tp=tp, sl=sl, hold=hold, be_trigger=(round(tp * 0.6, 2) if be else 0.0))
    for tp in (0.5, 1.0, 2.0, 3.0)
    for sl in (1.0, 2.0, 4.0)
    for hold in (60, 180, 600)
    for be in (False, True)
]


def pkey(params: dict) -> str:
    return ",".join(f"{k}={v:g}" for k, v in params.items())


def evaluate_day(job):
    """همهٔ ترکیب‌ها روی یک نماد-روز ← آمار جمعی فشرده برای هر ترکیب."""
    symbol, day, cache, spread, fee, combos = job
    d = data_mod.load_day(symbol, day, Path(cache))
    if d is None or len(d) < 4000:
        return symbol, day, {}
    costs = Costs(notional=500.0, fee=fee, spread_pct=spread, slip_pct=SLIPPAGE_PCT)
    f = sig.Features(d)
    out: dict[str, list] = {}
    signal_cache: dict = {}
    for family, params, rule, gated in combos:
        skey = (family, pkey(params), gated, rule.hold, rule.tp)
        if skey not in signal_cache:
            idx, sides = sig.build(family, f, params)
            if gated:
                g = sig.ultra_gate(f, rule.hold, rule.tp, costs)
                keep = g[idx]
                idx, sides = idx[keep], sides[keep]
            signal_cache[skey] = (idx, sides)
        idx, sides = signal_cache[skey]
        pnl, reason, _dur, _ = simulate(d, idx, sides, rule, costs)
        key = f"{family}|{pkey(params)}|{rule.key()}|{'gate' if gated else 'raw'}"
        wins = pnl[pnl > 0]
        out[key] = [int(pnl.shape[0]), int(wins.shape[0]), float(pnl.sum()),
                    float(wins.sum()), float(-pnl[pnl <= 0].sum()),
                    [int((reason == r).sum()) for r in range(4)]]
    return symbol, day, out


def aggregate(results, days: list[str]) -> dict[str, dict]:
    agg: dict[str, dict] = {}
    for _symbol, day, stats in results:
        for key, (n, w, total, gw, gl, exits) in stats.items():
            a = agg.setdefault(key, {"n": 0, "w": 0, "total": 0.0, "gw": 0.0, "gl": 0.0,
                                     "exits": [0, 0, 0, 0], "daily": {}})
            a["n"] += n; a["w"] += w; a["total"] += total; a["gw"] += gw; a["gl"] += gl
            a["exits"] = [x + y for x, y in zip(a["exits"], exits)]
            a["daily"][day] = a["daily"].get(day, 0.0) + total
    for a in agg.values():
        n = max(1, a["n"])
        a["win_rate"] = round(100.0 * a["w"] / n, 2)
        a["avg"] = round(a["total"] / n, 4)
        a["pf"] = round(a["gw"] / a["gl"], 3) if a["gl"] > 0 else (99.0 if a["gw"] > 0 else 0.0)
        a["profitable_days"] = sum(1 for d in days if a["daily"].get(d, 0.0) > 0)
        a["exits"] = dict(zip(("stop", "tp", "timeout", "break_even"), a["exits"]))
        a["total"] = round(a["total"], 2)
        a.pop("gw"); a.pop("gl"); a.pop("w")
    return agg


def run(args) -> dict:
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    end = datetime.now(UTC).date() - timedelta(days=args.lag)
    days = [(end - timedelta(days=i)).isoformat() for i in range(args.days)][::-1]
    train_days, test_days = days[: args.train_days], days[args.train_days:]
    symbols = args.symbols.split(",") if args.symbols else SYMBOLS
    print(f"[run] days={days} train={train_days} test={test_days} symbols={len(symbols)}")

    spreads = data_mod.lbank_spreads(symbols, out_dir / "lbank_spreads.json") if not args.no_spread \
        else {s: data_mod.DEFAULT_SPREAD_MAJOR if s.split("/")[0] in data_mod.MAJORS else data_mod.DEFAULT_SPREAD_ALT for s in symbols}
    print("[run] spreads:", json.dumps(spreads))

    # پیش‌دانلود (موازی‌سازی ساده روی نمادها؛ آرشیو بایننس محدودیت جدی ندارد)
    cache = Path(args.cache)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(_prefetch, [(s, d, str(cache)) for s in symbols for d in days]))
    print(f"[run] data ready in {time.time() - t0:.0f}s")

    combos = [(BASELINE_SIGNAL[0], BASELINE_SIGNAL[1], BASELINE_EXIT, True)]
    for family, plist in sig.FAMILIES.items():
        for params in plist:
            for rule in EXIT_GRID:
                combos.append((family, params, rule, False))
    print(f"[run] combos={len(combos)}")

    def grid(day_list, fee, combo_list):
        jobs = [(s, d, str(cache), spreads[s], fee, combo_list) for s in symbols for d in day_list]
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            res = list(pool.map(evaluate_day, jobs, chunksize=1))
        return aggregate(res, day_list)

    t0 = time.time()
    train = grid(train_days, 0.0006, combos)
    print(f"[run] train grid {time.time() - t0:.0f}s")

    baseline_key = next(k for k in train if k.endswith("|gate"))
    ranked = sorted((k for k, v in train.items() if v["n"] >= args.min_trades and not k.endswith("|gate")),
                    key=lambda k: train[k]["avg"], reverse=True)
    finalists = [baseline_key] + ranked[:15]
    for family in sig.FAMILIES:
        best = [k for k in ranked if k.startswith(family + "|")][:2]
        finalists += [k for k in best if k not in finalists]
    high_win = [k for k in ranked if train[k]["win_rate"] >= 80.0][:5]
    finalists += [k for k in high_win if k not in finalists]

    by_key = {}
    for c in combos:
        by_key[f"{c[0]}|{pkey(c[1])}|{c[2].key()}|{'gate' if c[3] else 'raw'}"] = c
    final_combos = [by_key[k] for k in finalists]

    t0 = time.time()
    test = grid(test_days, 0.0006, final_combos)
    test_maker = grid(test_days, 0.0002, final_combos)
    print(f"[run] test {time.time() - t0:.0f}s")

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "days": days, "train_days": train_days, "test_days": test_days,
        "symbols": symbols, "spreads": spreads, "slippage_pct": SLIPPAGE_PCT,
        "notional": 500.0, "combos_evaluated": len(combos),
        "baseline": baseline_key,
        "rows": [
            {"key": k, "train": train.get(k), "test": test.get(k), "test_maker_fee": test_maker.get(k)}
            for k in finalists
        ],
        "train_80pct_winrate_count": sum(1 for v in train.values() if v["n"] >= args.min_trades and v["win_rate"] >= 80),
        "train_positive_count": sum(1 for v in train.values() if v["n"] >= args.min_trades and v["avg"] > 0),
        "train_count": sum(1 for v in train.values() if v["n"] >= args.min_trades),
    }
    (out_dir / "scalp_research.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    (out_dir / "scalp_research.md").write_text(render(report), encoding="utf-8")
    print(render(report))
    return report


def _prefetch(job):
    symbol, day, cache = job
    data_mod.load_day(symbol, day, Path(cache))


def render(report: dict) -> str:
    def row(name, m):
        if not m:
            return f"| {name} | — | — | — | — | — |"
        return f"| {name} | {m['n']} | {m['win_rate']}% | {m['avg']:+.3f} | {m['total']:+.1f} | {m['pf']} |"

    lines = [
        "# Scalp research (real 1s data, full costs)",
        "",
        f"Generated {report['generated_at']} — days {report['days'][0]} … {report['days'][-1]}",
        f"Train {report['train_days']} · Test (out-of-sample) {report['test_days']}",
        f"Notional $500 (10$ × 50x) · taker fee 0.06%/side · slippage {report['slippage_pct']}%/side · LBank spreads",
        f"Combos with ≥min trades on train: {report['train_count']}; positive expectancy: "
        f"{report['train_positive_count']}; win-rate ≥80%: {report['train_80pct_winrate_count']}",
        "",
    ]
    for r in report["rows"]:
        lines.append(f"## {r['key']}" + ("  ← CURRENT ULTRA" if r["key"] == report["baseline"] else ""))
        lines.append("| set | trades | win | avg $ | total $ | PF |")
        lines.append("|---|---|---|---|---|---|")
        lines.append(row("train", r["train"]))
        lines.append(row("TEST", r["test"]))
        lines.append(row("TEST maker 0.02%", r["test_maker_fee"]))
        if r["test"]:
            lines.append(f"exits(test): {r['test']['exits']} · profitable test days: {r['test']['profitable_days']}/{len(report['test_days'])}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--train-days", type=int, default=4)
    p.add_argument("--lag", type=int, default=2, help="روزهای عقب از امروز (آرشیو روزانه با تأخیر منتشر می‌شود)")
    p.add_argument("--symbols", default="")
    p.add_argument("--min-trades", type=int, default=150)
    p.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    p.add_argument("--cache", default=".cache/scalp_lab")
    p.add_argument("--out", default="research/results")
    p.add_argument("--no-spread", action="store_true")
    run(p.parse_args())


if __name__ == "__main__":
    main()
