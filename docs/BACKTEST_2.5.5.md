# Backtest & walk-forward report — v2.5.5

> **No result in this file guarantees future profit or accuracy.** These are
> historical simulations on a small public dataset. They measure whether the
> v2.5.5 intelligence layer changed behaviour; they do not prove an edge.

## How it was produced

```
PYTHONPATH=. python tools/run_backtest.py --data-dir <folder of *-5m.feather|csv> --out data/backtest --workers 2
# optional: record the evidence into the live-execution validation gate
PYTHONPATH=. python tools/run_backtest.py --data-dir <...> --out data/backtest --from-report \
    --record-gate <app data dir>/validation_gate.json
```

* **Data:** freqtrade public test data (`tests/testdata/*.feather`), 5-minute candles.
  * 10 `*/BTC` pairs (ADA, DASH, ETC, ETH, LTC, NXT, TRX, XLM, XMR, ZEC): 2018-01-10 → 2018-01-30 (~5,760 bars each; a sharp bear market).
  * `BTC/USDT`, `XRP/USDT`: 2025-11-24 → 2025-12-04 (3,106 bars).
  * Higher timeframes (15m/1h/4h) are resampled from 5m, complete buckets only.
* **Same code as the app:** `SignalEngine` with the 7 strategy components, the prediction
  engine, `IntelligentDecisionEngine`, the risk engine and quality-based size multipliers.
* **No look-ahead:** at time *t* the engine sees closed candles only (a higher-timeframe
  "forming" candle is built from closed 5m candles ≤ *t*). Entry is the **next** candle's open.
* **Costs:** fee 0.06 % per side, spread 0.04 %, slippage 0.02 % (entry + stop exits).
  Pessimistic: if a candle touches both SL and TP, SL is assumed first.
* **Exits:** staged TP (1/3 each at TP1/TP2/TP3, SL → entry after TP1), max hold 96 bars (8 h).
* **Walk-forward:** per period, folds of train 40 % → validation 20 % → unseen test (3 × 13 %),
  window moves forward. Thresholds/weights are tuned only on train and accepted only if they
  also beat the default on validation. The learner is fitted only on train + validation.
  Only test-window numbers are reported.
* **Risk accounting:** 1 % risk per 1R, additive equity starting at 100. A "Max DD" above 100 %
  means the simulated account would have been wiped out.

## Results (verbatim from `report.md`)

No result here guarantees future profit.

## Signal counts
```
{
  "evaluations": 18372,
  "old_engine": {
    "LONG": 1219,
    "WAIT": 13409,
    "SHORT": 3744
  },
  "old_signals_over_threshold": 4469,
  "new_engine": {
    "LONG": 1219,
    "WAIT": 13409,
    "SHORT": 3744
  },
  "new_quality": {
    "NORMAL": 3142,
    "STRONG": 1006,
    "WEAK": 321
  },
  "new_no_trade": 0
}
```

## Full period (in-sample for the fusion defaults)
| Engine | Trades | Win% | PF | Expectancy (R) | Max DD % | Return % (1% risk) | L/S |
|---|---|---|---|---|---|---|---|
| old | 556 | 37.59 | 0.65 | -0.2174 | 128.973 | -120.864 | 140/416 |
| new | 556 | 37.59 | 0.652 | -0.1641 | 97.706 | -91.24 | 140/416 |
| new (final conf ≥ threshold) | 555 | 37.3 | 0.648 | -0.167 | 99.137 | -92.672 | 140/415 |

### New engine by quality
| Engine | Trades | Win% | PF | Expectancy (R) | Max DD % | Return % (1% risk) | L/S |
|---|---|---|---|---|---|---|---|
| NORMAL | 435 | 36.32 | 0.61 | -0.1843 | 83.136 | -80.157 | 107/328 |
| STRONG | 73 | 39.73 | 0.808 | -0.112 | 15.748 | -8.178 | 31/42 |
| WEAK | 48 | 45.83 | 0.795 | -0.0605 | 7.411 | -2.905 | 2/46 |

## Walk-forward 2018-01 (unseen test windows only)
| Engine | Trades | Win% | PF | Expectancy (R) | Max DD % | Return % (1% risk) | L/S |
|---|---|---|---|---|---|---|---|
| old | 198 | 38.89 | 0.537 | -0.2727 | 58.698 | -53.993 | 36/162 |
| new default | 198 | 38.89 | 0.552 | -0.1895 | 41.587 | -37.523 | 36/162 |
| new tuned | 198 | 38.89 | 0.561 | -0.1773 | 39.216 | -35.108 | 36/162 |
| new tuned + learning | 198 | 38.89 | 0.561 | -0.1771 | 39.181 | -35.072 | 36/162 |

## Walk-forward 2025-11 (unseen test windows only)
| Engine | Trades | Win% | PF | Expectancy (R) | Max DD % | Return % (1% risk) | L/S |
|---|---|---|---|---|---|---|---|
| old | 18 | 50.0 | 1.065 | 0.0327 | 3.479 | 0.589 | 9/9 |
| new default | 18 | 50.0 | 1.115 | 0.0463 | 2.719 | 0.833 | 9/9 |
| new tuned | 18 | 50.0 | 1.106 | 0.0407 | 2.517 | 0.733 | 9/9 |
| new tuned + learning | 18 | 50.0 | 1.106 | 0.0407 | 2.517 | 0.733 | 9/9 |

## Scalp direction
| Engine | Trades | Win% | PF | Expectancy (R) | Max DD % | Return % (1% risk) | L/S |
|---|---|---|---|---|---|---|---|
| old momentum only | 9796 | 45.09 | 0.457 | -0.3504 | 3407.043 | -3432.897 | 4750/5046 |
| new evidence | 9796 | 44.58 | 0.445 | -0.3618 | 3517.274 | -3544.04 | 4540/5256 |

### Calibration (final vs technical confidence, full period)

| Confidence source | Brier (lower is better) | Monotonic win-rate by bucket |
|---|---|---|
| Old: technical confidence | 0.281 | no |
| New: final confidence | 0.308 | no |

## Honest analysis

1. **Signal count unchanged.** 18,372 evaluations produced the same 4,963 directional signals
   (1,219 LONG / 3,744 SHORT) and the same 4,469 over the user threshold, in both engines.
   **NO_TRADE = 0.** Quality tiers: NORMAL 3,142, STRONG 1,006, WEAK 321.
2. **The trade set is identical, so win rate is identical (37.59 %).** The new engine's better
   expectancy (−0.217R → −0.164R) and lower drawdown (129 % → 98 %) come from **smaller
   position sizes** (NORMAL ×0.75, WEAK ×0.5). The average size multiplier is ≈ 0.76, and
   −0.217 × 0.76 ≈ −0.165R. **After adjusting for size, the new engine is no better than the old
   one on this data.** This is lower exposure, not better trade selection.
3. **Quality tiers are not validated.** WEAK trades did *better* than NORMAL (−0.06R vs
   −0.18R). The tier ordering is not supported by this data, and final confidence is *less*
   calibrated than technical confidence (Brier 0.308 vs 0.281).
4. **Walk-forward (unseen test windows):** the same pattern holds. 2018: PF 0.537 → 0.561,
   DD 58.7 % → 39.2 %, still losing. 2025: PF 1.065 → 1.106 on only 18 trades, which is far too
   few to mean anything. Tuned configurations were accepted by validation in 3 of 6 folds.
5. **Scalp direction:** the multi-timeframe evidence resolver (required by the spec: direction
   not from momentum alone) did **not** improve results: PF 0.457 → 0.445, expectancy
   −0.350R → −0.362R over 9,796 simulated scalps. Both are strongly negative. At 5 minutes,
   costs (~0.36R per trade) dominate. The resolver stays on by default because the spec
   requires it. It can be switched off with the `scalp.evidence_direction` setting.
6. **The old engine itself loses on this dataset** (short-heavy, 2018 crash). Twenty days of
   2018 data and ten days of 2025 data are not enough to validate any strategy.
7. **Validation gate:** fed this report, it stays **LOCKED**: backtest PF 0.652 < 1.1,
   expectancy < 0, DD 97.7 % > 20 %, walk-forward total −34.3R, calibration fails,
   0/100 paper trades, learner empty, risk limits not set. Live execution stays locked.

## What would be needed before trusting anything

* Months of data across several regimes and many USDT pairs (the exchange APIs were
  unreachable from the development sandbox; run `tools/run_backtest.py` locally on
  exported candles).
* ≥ 100 closed paper trades through the real pipeline, measured per quality tier.
* Re-running the walk-forward once the learner has ≥ 90 real outcomes.
