"""
اجرای بک‌تست واقعی و walk-forward روی دادهٔ تاریخی — نسخهٔ ۲.۵.۵.

استفاده (روی سیستم کاربر با داده‌ای که خودش دانلود کرده):

    python tools/run_backtest.py --data-dir path/to/candles --out data/backtest

هر فایل یک نماد است و نامش قالب `BASE_QUOTE-5m.csv` یا `.feather` دارد
(مثلاً `ETH_USDT-5m.csv`). ستون‌ها: timestamp/date, open, high, low, close, volume.
اگر `BTC_USDT-5m` هم باشد، برای آلت‌های USDT بافت BTC هم سنجیده می‌شود.

خروجی: `report.json` (همهٔ اعداد) و `report.md` (خلاصهٔ خوانا). ارزیابی‌ها
در `evals_<symbol>.json` کش می‌شوند تا اجرای دوباره سریع باشد.

هیچ نتیجه‌ای تضمین سود آینده نیست.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TIMEFRAMES = ["5m", "15m", "1h", "4h"]


def symbol_from_path(path: Path) -> tuple[str, str]:
    """`ETH_BTC-5m.feather` → ("ETH/BTC", "5m")."""
    stem = path.stem
    name, _, tf = stem.partition("-")
    base, _, quote = name.partition("_")
    return f"{base}/{quote}", (tf or "5m")


def _build_market(files: dict[str, str], symbol: str) -> Any:
    from backtest.data import load_candles
    from backtest.market import HistoricalMarket

    market = HistoricalMarket("5m")
    market.add_symbol(symbol, load_candles(files[symbol]), TIMEFRAMES)
    if symbol.endswith("/USDT") and "BTC/USDT" in files and symbol != "BTC/USDT":
        market.add_symbol("BTC/USDT", load_candles(files["BTC/USDT"]), TIMEFRAMES)
    return market


def evaluate_worker(args: tuple[dict[str, str], str, str, dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], float]:
    """کار هر فرایند: ارزیابی یک نماد + بک‌تست جهت اسکالپ."""
    files, symbol, out_dir, options = args
    logging.disable(logging.WARNING)
    from backtest.engine import BacktestConfig, BacktestEngine, Evaluation

    started = time.perf_counter()
    cache = Path(out_dir) / f"evals_{symbol.replace('/', '_')}.json"
    market = _build_market(files, symbol)
    config = BacktestConfig(
        step_bars=options["step_bars"], warmup_bars=options["warmup_bars"],
        prediction_replay=options["prediction"],
    )
    if cache.exists() and not options["refresh"]:
        evaluations = [Evaluation.from_dict(e) for e in json.loads(cache.read_text())]
    else:
        engine = BacktestEngine(market, config)
        evaluations = asyncio.run(engine.evaluate_symbol(symbol))
        cache.write_text(json.dumps([e.to_dict() for e in evaluations]))
    scalp = scalp_backtest(market, symbol, options)
    return symbol, [e.to_dict() for e in evaluations], scalp, time.perf_counter() - started


def scalp_backtest(market: Any, symbol: str, options: dict[str, Any]) -> list[dict[str, Any]]:
    """
    مقایسهٔ جهت اسکالپ: قدیم (فقط مومنتوم) و جدید (شواهد چندتایم‌فریمی)
    روی **همان** نامزدهای اسکنر (همان فیلترهای نقدینگی/اسپرد/نوسان).
    SL/TP یکسان (±۱٫۰× نوسان ۵ دقیقه‌ای)، نگه‌داری حداکثر ۱۲ کندل.
    """
    import copy
    from app.core.models import Ticker
    from backtest.execution import ExecutionModel, simulate_trade
    from trading.scalp_scanner import apply_direction_evidence, score_candidate

    base = market.base_candles(symbol)
    model = ExecutionModel()
    rows: list[dict[str, Any]] = []
    busy = {"old": -1, "new": -1}
    for index in range(options["warmup_bars"], len(base) - 13, options["step_bars"]):
        now = base[index].timestamp + 300
        market.set_time(now)
        c5 = market.candles_at(symbol, "5m", 60)
        ticker = Ticker(symbol=symbol, last_price=c5[-1].close,
                        high_24h=c5[-1].high, low_24h=c5[-1].low, volume_24h=1e9,
                        turnover_24h=1e9, change_percent=0.0, timestamp=now)
        candidate = score_candidate(ticker, c5, spread=model.spread_percent)
        if candidate is None:
            continue
        frames = {tf: market.candles_at(symbol, tf, 60) for tf in ("5m", "15m", "1h", "4h")}
        resolved = apply_direction_evidence(copy.deepcopy(candidate), frames)
        vol = candidate.volatility_5m / 100.0
        future = base[index + 1:index + 13]
        for mode, direction, source in (
            ("old", candidate.direction, "momentum"),
            ("new", resolved.direction, resolved.direction_source),
        ):
            if now <= busy[mode]:
                continue
            entry = future[0].open
            sign = 1 if direction == "LONG" else -1
            result = simulate_trade(
                symbol=symbol, direction=direction, signal_time=now,
                stop_loss=entry * (1 - sign * vol), take_profits=[entry * (1 + sign * vol)],
                future=future, model=model, max_bars=12,
                meta={"mode": mode, "direction_source": source, "conviction": resolved.conviction},
            )
            if result is not None:
                busy[mode] = result.exit_time
                rows.append(result.to_dict())
    return rows


def _group_by_period(evals: list[Any]) -> dict[str, list[Any]]:
    """گروه‌بندی نمادها بر اساس بازهٔ زمانی داده (برای پنجره‌های walk-forward)."""
    from datetime import UTC, datetime

    groups: dict[str, list[Any]] = {}
    firsts: dict[str, int] = {}
    for e in evals:
        firsts[e.symbol] = min(firsts.get(e.symbol, e.time), e.time)
    for e in evals:
        key = datetime.fromtimestamp(firsts[e.symbol], UTC).strftime("%Y-%m")
        groups.setdefault(key, []).append(e)
    return groups


def _trade_from_dict(data: dict[str, Any]) -> Any:
    from backtest.execution import TradeResult

    known = {k: data[k] for k in (
        "symbol", "direction", "signal_time", "entry_time", "exit_time", "entry", "stop_loss",
        "exit_reason", "r_multiple", "return_percent", "fees_percent", "bars", "mae_percent",
        "mfe_percent", "targets_hit", "size_multiplier",
    )}
    meta = {k: v for k, v in data.items() if k not in known}
    return TradeResult(**known, meta=meta)


def analyse(evaluations: list[Any], files: dict[str, str], scalp_rows: list[dict[str, Any]], options: dict[str, Any]) -> dict[str, Any]:
    """مقایسهٔ قدیم/جدید، walk-forward و کالیبراسیون."""
    from collections import Counter

    from backtest.data import load_candles
    from backtest.engine import BacktestConfig, BacktestEngine
    from backtest.market import HistoricalMarket
    from backtest.metrics import by_key, calibration, summarize
    from backtest.walk_forward import make_folds, run_walk_forward

    market = HistoricalMarket("5m")
    for symbol in sorted({e.symbol for e in evaluations}):
        market.add_symbol(symbol, load_candles(files[symbol]), ["5m", "15m", "1h", "4h"])
    config = BacktestConfig(step_bars=options["step_bars"], warmup_bars=options["warmup_bars"],
                            prediction_replay=False)
    engine = BacktestEngine.__new__(BacktestEngine)
    engine.market = market
    engine.config = config
    from signals.intelligent_decision import IntelligentDecisionEngine
    engine.decision = IntelligentDecisionEngine()
    # کش‌های قدیمی (پیش از ۲.۵.۶) کشیدگی حرکت ندارند؛ بدون look-ahead افزوده می‌شود
    engine.annotate_extension(evaluations)

    directional = [e for e in evaluations if e.directional]
    old_signals = [e for e in directional if e.technical_confidence >= config.min_confidence]
    counts = {
        "evaluations": len(evaluations),
        "old_engine": dict(Counter(e.base_direction for e in evaluations)),
        "old_signals_over_threshold": len(old_signals),
        "new_engine": dict(Counter(
            ("NO_TRADE" if e.decision == "NO_TRADE" else e.base_direction) for e in evaluations
        )),
        "new_quality": dict(Counter(e.quality for e in old_signals if e.decision != "NO_TRADE")),
        "new_no_trade": sum(1 for e in old_signals if e.decision == "NO_TRADE"),
    }
    rp = config.risk_percent
    old = engine.simulate(evaluations, mode="old")
    new = engine.simulate(evaluations, mode="new")
    strict = engine.simulate(evaluations, mode="new", min_final_confidence=config.min_confidence)
    full = {
        "old": summarize(old, risk_percent=rp),
        "new": summarize(new, risk_percent=rp),
        "new_strict_final_confidence": summarize(strict, risk_percent=rp),
        "new_by_quality": by_key(new, "quality", risk_percent=rp),
        "old_by_quality_label": by_key(old, "quality", risk_percent=rp),
        "old_by_regime": by_key(old, "regime", risk_percent=rp),
        "calibration_old_technical": calibration(old, key="technical_confidence"),
        "calibration_new_final": calibration(new, key="final_confidence"),
    }
    wf: dict[str, Any] = {}
    for period, group in _group_by_period(evaluations).items():
        start = min(e.time for e in group)
        end = max(e.time for e in group) + 1
        span = (end - start) / 86400
        folds = make_folds(start, end, train_days=span * 0.4, val_days=span * 0.2,
                           test_days=span * 0.4 / 3)
        wf[period] = run_walk_forward(engine, group, folds)

    scalp = [_trade_from_dict(r) for r in scalp_rows]
    scalp_report = {
        "old_momentum_only": summarize([t for t in scalp if t.meta.get("mode") == "old"], risk_percent=rp),
        "new_evidence": summarize([t for t in scalp if t.meta.get("mode") == "new"], risk_percent=rp),
        "new_by_direction_source": by_key([t for t in scalp if t.meta.get("mode") == "new"],
                                          "direction_source", risk_percent=rp),
    }
    return {"counts": counts, "full_period": full, "walk_forward": wf, "scalp": scalp_report}


def to_markdown(report: dict[str, Any]) -> str:
    """خلاصهٔ خوانا."""
    def row(name: str, s: dict[str, Any]) -> str:
        return (f"| {name} | {s['trades']} | {s['win_rate']} | {s['profit_factor']} | "
                f"{s['expectancy_r']} | {s['max_drawdown_percent']} | {s['return_percent']} | "
                f"{s.get('long', 0)}/{s.get('short', 0)} |")
    head = "| Engine | Trades | Win% | PF | Expectancy (R) | Max DD % | Return % (1% risk) | L/S |\n|---|---|---|---|---|---|---|---|"
    lines = ["# Backtest report (v2.5.5)", "", "No result here guarantees future profit.", ""]
    lines += ["## Signal counts", "```", json.dumps(report["counts"], indent=2), "```", ""]
    f = report["full_period"]
    lines += ["## Full period (in-sample for the fusion defaults)", head,
              row("old", f["old"]), row("new", f["new"]),
              row("new (final conf ≥ threshold)", f["new_strict_final_confidence"]), ""]
    lines += ["### New engine by quality", head]
    lines += [row(k or "-", v) for k, v in f["new_by_quality"].items()]
    lines += [""]
    for period, wf in report["walk_forward"].items():
        t = wf["test_total"]
        lines += [f"## Walk-forward {period} (unseen test windows only)", head,
                  row("old", t["old"]), row("new default", t["new_default"]),
                  row("new tuned", t["new_tuned"]), row("new tuned + learning", t["new_tuned_learning"]), ""]
    s = report["scalp"]
    lines += ["## Scalp direction", head, row("old momentum only", s["old_momentum_only"]),
              row("new evidence", s["new_evidence"]), ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CryptoAITrader backtest / walk-forward")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out", default="data/backtest")
    parser.add_argument("--symbols", default="", help="comma list (default: all files)")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--step-bars", type=int, default=3)
    parser.add_argument("--warmup-bars", type=int, default=720)
    parser.add_argument("--no-prediction", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--record-gate", default="",
        help="path of validation_gate.json (e.g. <data_dir>/validation_gate.json) to record this report into",
    )
    parser.add_argument(
        "--from-report", action="store_true",
        help="do not evaluate; reuse <out>/report.json (use with --record-gate)",
    )
    args = parser.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.from_report:
        report = json.loads((out / "report.json").read_text())
        _record_gate(args.record_gate, report)
        return 0
    files: dict[str, str] = {}
    for path in sorted(Path(args.data_dir).iterdir()):
        if path.suffix.lower() in (".csv", ".feather", ".parquet") and "-5m" in path.stem:
            symbol, _ = symbol_from_path(path)
            files[symbol] = str(path)
    wanted = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or sorted(files)
    options = {"step_bars": args.step_bars, "warmup_bars": args.warmup_bars,
               "prediction": not args.no_prediction, "refresh": args.refresh}
    from backtest.engine import Evaluation

    evaluations: list[Any] = []
    scalp_rows: list[dict[str, Any]] = []
    timings: dict[str, float] = {}
    jobs = [(files, s, str(out), options) for s in wanted if s in files]
    with ProcessPoolExecutor(max_workers=max(1, args.workers), mp_context=get_context("spawn")) as pool:
        for symbol, evals, scalp, seconds in pool.map(evaluate_worker, jobs):
            evaluations += [Evaluation.from_dict(e) for e in evals]
            scalp_rows += scalp
            timings[symbol] = round(seconds, 1)
            print(f"{symbol}: {len(evals)} evaluations in {seconds:.0f}s", flush=True)
    report = analyse(evaluations, files, scalp_rows, options)
    report["timings_seconds"] = timings
    report["data"] = {s: Path(p).name for s, p in files.items() if s in wanted}
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str))
    (out / "report.md").write_text(to_markdown(report))
    print(to_markdown(report))
    _record_gate(args.record_gate, report)
    return 0


def _record_gate(path: str, report: dict[str, Any]) -> None:
    """
    ثبت شواهد بک‌تست/walk-forward/کالیبراسیون در دروازهٔ اعتبارسنجی.

    این فقط «شاهد» ثبت می‌کند؛ دروازه همچنان معیارهای کاغذی، ریسک و
    یادگیرنده را جداگانه می‌سنجد و بدون عبور همه، اجرای واقعی قفل است.
    """
    if not path:
        return
    from trading.validation_gate import ValidationGate

    gate = ValidationGate(path)
    gate.record_backtest_report(report)
    status = gate.evaluate()
    print(f"validation gate recorded at {path}: {'PASSED' if status.passed else 'LOCKED'} — {status.reason}")


if __name__ == "__main__":
    raise SystemExit(main())
