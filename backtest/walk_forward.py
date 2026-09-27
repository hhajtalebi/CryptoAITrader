"""
Walk-forward: آموزش → اعتبارسنجی → آزمون نادیده → جابه‌جایی پنجره.

قواعد ضد نشت اطلاعات:
    • آستانه‌های لایهٔ تصمیم (NO_TRADE، WEAK، جریمه) فقط روی بازهٔ آموزش
      انتخاب و روی بازهٔ اعتبارسنجی تأیید می‌شوند؛ اگر در اعتبارسنجی از
      پیکربندی پیش‌فرض بدتر باشند، پیش‌فرض می‌ماند.
    • یادگیرنده (حافظهٔ الگو + ضرایب) فقط روی معاملات آموزش+اعتبارسنجی
      fit می‌شود و روی آزمون اعمال.
    • نتایج گزارش‌شده فقط از بازه‌های آزمون (دادهٔ نادیده) هستند.

قید صریح کاربر در جست‌وجو: پیکربندی‌ای که NO_TRADE را غالب کند یا تعداد
معاملات را بیش از ۴۰٪ کم کند، اصلاً کاندید نمی‌شود — «کمتر معامله کردن
به‌تنهایی موفقیت نیست».
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Any

from backtest.engine import BacktestEngine, Evaluation, records_from_trades
from backtest.metrics import summarize
from signals.intelligent_decision import DecisionConfig
from signals.learning import PerformanceLearner

DAY = 86400

DEFAULT_GRID: dict[str, list[Any]] = {
    "no_trade_ratio": [-0.35, -0.45, -0.55],
    "no_trade_min_opposing": [2, 3],
    "weak_final": [50, 55, 60],
    "penalty": [15.0, 20.0, 25.0],
}


@dataclass(slots=True, frozen=True)
class Fold:
    """یک پنجرهٔ walk-forward (ثانیه UTC)."""

    train: tuple[int, int]
    validation: tuple[int, int]
    test: tuple[int, int]

    def to_dict(self) -> dict[str, Any]:
        return {"train": list(self.train), "validation": list(self.validation), "test": list(self.test)}


def make_folds(
    start: int, end: int, *, train_days: float, val_days: float, test_days: float,
    step_days: float | None = None,
) -> list[Fold]:
    """ساخت پنجره‌های پیاپی؛ آزمون‌ها هم‌پوشانی ندارند."""
    step = int((step_days or test_days) * DAY)
    folds: list[Fold] = []
    cursor = start
    while True:
        a = cursor
        b = a + int(train_days * DAY)
        c = b + int(val_days * DAY)
        d = c + int(test_days * DAY)
        if d > end:
            break
        folds.append(Fold((a, b), (b, c), (c, d)))
        cursor += step
    return folds


def _within(evals: list[Evaluation], window: tuple[int, int]) -> list[Evaluation]:
    return [e for e in evals if window[0] <= e.time < window[1]]


def objective(trades: list[Any], risk_percent: float = 1.0) -> float:
    """هدف انتخاب: امید ریاضی × √n منهای جریمهٔ افت سرمایه."""
    if len(trades) < 10:
        return -math.inf
    summary = summarize(trades, risk_percent=risk_percent)
    return float(summary["expectancy_r"]) * math.sqrt(len(trades)) - 0.05 * float(summary["max_drawdown_percent"])


def tune(
    engine: BacktestEngine,
    train: list[Evaluation],
    validation: list[Evaluation],
    *,
    base: DecisionConfig | None = None,
    grid: dict[str, list[Any]] | None = None,
    min_trade_ratio: float = 0.6,
    max_no_trade_share: float = 0.25,
) -> tuple[DecisionConfig, dict[str, Any]]:
    """انتخاب پیکربندی روی آموزش، تأیید روی اعتبارسنجی."""
    base = base or DecisionConfig()
    grid = grid or DEFAULT_GRID
    old_train = engine.simulate(train, mode="old")
    setups = sum(1 for e in train if e.directional and e.technical_confidence >= engine.config.min_confidence)
    best_cfg = base
    best_score = objective(engine.simulate(train, mode="new", decision_config=base))
    tried = 0
    rejected = 0
    keys = list(grid)
    for values in itertools.product(*(grid[k] for k in keys)):
        cfg = base.with_overrides(**dict(zip(keys, values)))
        trades = engine.simulate(train, mode="new", decision_config=cfg)
        no_trade = sum(
            1 for e in train
            if e.directional and e.intelligence.get("components")
            and engine.decision.rescore(e.intelligence, cfg)["decision"] == "NO_TRADE"
        )
        tried += 1
        if old_train and len(trades) < min_trade_ratio * len(old_train):
            rejected += 1
            continue
        if setups and no_trade / setups > max_no_trade_share:
            rejected += 1
            continue
        score = objective(trades)
        if score > best_score:
            best_cfg, best_score = cfg, score
    val_default = objective(engine.simulate(validation, mode="new", decision_config=base))
    val_best = objective(engine.simulate(validation, mode="new", decision_config=best_cfg))
    accepted = best_cfg is not base and val_best >= val_default
    chosen = best_cfg if accepted else base
    return chosen, {
        "tried": tried,
        "rejected_by_constraints": rejected,
        "train_objective": None if math.isinf(best_score) else round(best_score, 4),
        "validation_objective_default": None if math.isinf(val_default) else round(val_default, 4),
        "validation_objective_best": None if math.isinf(val_best) else round(val_best, 4),
        "accepted": accepted,
        "chosen": {k: getattr(chosen, k) for k in keys},
    }


def run_walk_forward(
    engine: BacktestEngine,
    evaluations: list[Evaluation],
    folds: list[Fold],
    *,
    grid: dict[str, list[Any]] | None = None,
    min_samples: int = 30,
) -> dict[str, Any]:
    """اجرای کامل walk-forward؛ فقط معیارهای بازهٔ آزمون گزارش می‌شوند."""
    rp = engine.config.risk_percent
    all_old: list[Any] = []
    all_new: list[Any] = []
    all_tuned: list[Any] = []
    all_learn: list[Any] = []
    fold_reports: list[dict[str, Any]] = []
    for fold in folds:
        train = _within(evaluations, fold.train)
        val = _within(evaluations, fold.validation)
        test = _within(evaluations, fold.test)
        chosen, tuning = tune(engine, train, val, grid=grid)
        # یادگیرنده فقط از گذشته (آموزش + اعتبارسنجی)
        learner = PerformanceLearner(min_samples=min_samples).fit(
            records_from_trades(engine.simulate(train + val, mode="old"))
        )
        old = engine.simulate(test, mode="old")
        new = engine.simulate(test, mode="new")
        tuned = engine.simulate(test, mode="new", decision_config=chosen)
        learned = engine.simulate(test, mode="new", decision_config=chosen, learner=learner)
        all_old += old
        all_new += new
        all_tuned += tuned
        all_learn += learned
        fold_reports.append({
            "fold": fold.to_dict(),
            "evaluations": {"train": len(train), "validation": len(val), "test": len(test)},
            "tuning": tuning,
            "learner": learner.health(),
            "test_old": summarize(old, risk_percent=rp),
            "test_new_default": summarize(new, risk_percent=rp),
            "test_new_tuned": summarize(tuned, risk_percent=rp),
            "test_new_tuned_learning": summarize(learned, risk_percent=rp),
        })
    return {
        "folds": fold_reports,
        "test_total": {
            "old": summarize(all_old, risk_percent=rp),
            "new_default": summarize(all_new, risk_percent=rp),
            "new_tuned": summarize(all_tuned, risk_percent=rp),
            "new_tuned_learning": summarize(all_learn, risk_percent=rp),
        },
    }


__all__ = ["DEFAULT_GRID", "Fold", "make_folds", "objective", "run_walk_forward", "tune"]
