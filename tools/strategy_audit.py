"""
ممیزی رأی راهبردها روی کندل واقعی — نسخهٔ ۲.۵.۷ (مستند SIGNAL_ENGINE_PIPELINE_FA).

برای هر پنجرهٔ ۲۵۰ کندلی (گام ۶) همان `compute_timeframe_analysis` موتور را
اجرا می‌کند، رأی هر ۵ راهبرد را می‌گیرد و با بازده ۱۲ کندل بعد می‌سنجد:
  • چند بار LONG / SHORT / WAIT / N/A رأی داده،
  • دقت جهت (hit%) هر راهبرد،
  • جمع‌بندی تک‌تایم‌فریمی (میانگین وزن‌دار، آستانهٔ ±۰٫۲۲) و دقت آن،
  • چند بار شاخهٔ %B در mean_reversion فعال شده.

نسخهٔ ۲.۵.۸: سه باگ نام/مقیاس (STOCHASTIC، BOLLINGER، مقیاس %B) در خود
راهبردها اصلاح شد؛ گزینهٔ قدیمی --patched حذف شد (اعداد «پیش از اصلاح» در
docs/SIGNAL_ENGINE_PIPELINE_FA.md §۱۸ ثبت شده‌اند).

اجرا:
    PYTHONPATH=. python tools/strategy_audit.py --data-dir <folder of *.feather|*.csv>
"""

from __future__ import annotations

import argparse
import glob
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.models import SignalDirection  # noqa: E402
from backtest.data import load_candles  # noqa: E402
from indicators.engine import IndicatorEngine  # noqa: E402
from indicators.registry import register_builtin_indicators  # noqa: E402
from signals.engine import DECISION_THRESHOLD, compute_timeframe_analysis  # noqa: E402
from signals.strategies.base import StrategyContext  # noqa: E402
from signals.strategies.registry import register_builtin_strategies, strategy_registry  # noqa: E402

HORIZON = 12
WINDOW = 250
STEP = 6


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    register_builtin_indicators()
    register_builtin_strategies()
    engine = IndicatorEngine()
    stats = defaultdict(lambda: {"long": 0, "short": 0, "wait": 0, "na": 0, "hit": 0, "directional": 0})
    percent_b = Counter()
    decisions = Counter()
    decision_hits = Counter()
    scores: list[float] = []
    files = sorted(glob.glob(str(Path(args.data_dir) / "*.feather")) + glob.glob(str(Path(args.data_dir) / "*.csv")))
    for path in files:
        candles = load_candles(path)
        for i in range(WINDOW, len(candles) - HORIZON, STEP):
            window = candles[i - WINDOW:i]
            analysis = compute_timeframe_analysis(engine, path, "15m", window)
            ctx = StrategyContext(
                symbol="X", timeframe="15m", candles=window, indicators=analysis["indicators"],
                structure=analysis["structure"], levels=analysis["levels"], trend=analysis["trend"],
                higher_timeframe_trend=analysis["trend"],
            )
            forward = candles[i - 1 + HORIZON].close / window[-1].close - 1
            pb = ctx.indicator_value("BBANDS", "percent_b")
            adx = ctx.indicator_value("ADX", "adx")
            if pb is not None and (adx is None or adx <= 30):
                # %B در مقیاس ۰..۱۰۰؛ همان آستانه‌های mean_reversion
                from signals.strategies.mean_reversion import PERCENT_B_HIGH, PERCENT_B_LOW

                percent_b["fires_short" if pb > PERCENT_B_HIGH else "fires_long" if pb < PERCENT_B_LOW else "none"] += 1
            weighted = total = 0.0
            for strategy in strategy_registry.all():
                vote = strategy.evaluate(ctx)
                row = stats[strategy.name]
                if not vote.applicable:
                    row["na"] += 1
                    continue
                weighted += vote.weighted_score
                total += vote.weight
                if vote.direction == SignalDirection.WAIT:
                    row["wait"] += 1
                    continue
                sign = 1 if vote.direction == SignalDirection.LONG else -1
                row["long" if sign > 0 else "short"] += 1
                row["directional"] += 1
                row["hit"] += int(sign * forward > 0)
            score = weighted / total if total else 0.0
            scores.append(score)
            decision = "LONG" if score >= DECISION_THRESHOLD else "SHORT" if score <= -DECISION_THRESHOLD else "WAIT"
            decisions[decision] += 1
            if decision != "WAIT":
                decision_hits[decision] += int((forward > 0) == (decision == "LONG"))
    report = {
        "strategies": {
            name: {**row, "hit_percent": round(row["hit"] / row["directional"] * 100, 1) if row["directional"] else None}
            for name, row in stats.items()
        },
        "percent_b_branch_adx_le_30": dict(percent_b),
        "decisions": dict(decisions),
        "decision_hit_percent": {
            k: round(decision_hits[k] / decisions[k] * 100, 1) for k in ("LONG", "SHORT") if decisions[k]
        },
        "mean_score": round(statistics.mean(scores), 4) if scores else None,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    # نسخهٔ ۲.۷.۰: خروجی هدایت‌شده به فایل در ویندوز cp1252 است و متن فارسی
    # UnicodeEncodeError می‌داد (doctor_report.txt خالی/خطا).
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    main()
