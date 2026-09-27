"""
دروازهٔ اعتبارسنجی معاملهٔ واقعی — نسخهٔ ۲.۵.۵.

قاعده: **اجرای واقعی قفل است** تا وقتی شواهد کافی ثبت شده باشد — حتی اگر
حالت live و عبارت تأیید کامل باشد. این دروازه فقط «ارسال سفارش واقعی
جدید» را کنترل می‌کند:
    • تولید سیگنال، معاملهٔ کاغذی، بک‌تست و یادگیری همیشه فعال‌اند.
    • بستن موقعیتی که قبلاً واقعی باز شده هرگز مسدود نمی‌شود.
    • راه دور زدن (override) وجود ندارد؛ تنها راه باز شدن، شواهد است.

معیارها (همه باید برقرار باشند):
    1. backtest      : ≥ ۲۰۰ معامله، PF ≥ ۱٫۱۰، امید ریاضی > ۰، افت ≤ ۲۰٪
    2. walk_forward  : ≥ ۳ پنجرهٔ آزمون، PF آزمون ≥ ۱٫۰۵، امید آزمون > ۰
    3. paper         : ≥ ۱۰۰ معاملهٔ کاغذی بسته‌شده، PF ≥ ۱٫۰۵، افت ≤ ۱۵٪
    4. calibration   : Brier ≤ ۰٫۲۶ و جدول اطمینان تقریباً صعودی
    5. risk          : حد ضرر روزانه و حد ضرر هر معامله تنظیم شده
    6. learner       : یادگیرنده سالم (≥ ۹۰ نتیجهٔ ثبت‌شده)

شواهد بک‌تست/walk-forward/کالیبراسیون از خروجی `tools/run_backtest.py`
(report.json) با `record_backtest_report` ثبت می‌شود. هیچ عبور از این
دروازه به معنای تضمین سود نیست.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class GateCriteria:
    """آستانه‌های دروازه (محافظه‌کارانه)."""

    backtest_min_trades: int = 200
    backtest_min_pf: float = 1.10
    backtest_max_dd: float = 20.0
    wf_min_folds: int = 3
    wf_min_pf: float = 1.05
    paper_min_trades: int = 100
    paper_min_pf: float = 1.05
    paper_max_dd: float = 15.0
    calibration_max_brier: float = 0.26
    learner_min_records: int = 90


@dataclass(slots=True)
class GateCheck:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass(slots=True)
class GateStatus:
    passed: bool
    checks: list[GateCheck] = field(default_factory=list)
    checked_at: str = ""

    @property
    def reason(self) -> str:
        failed = [c for c in self.checks if not c.passed]
        if not failed:
            return "all validation checks passed"
        return "; ".join(f"{c.name}: {c.detail}" for c in failed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "locked": not self.passed,
            "reason": self.reason,
            "checks": [c.to_dict() for c in self.checks],
            "checked_at": self.checked_at,
        }


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None


def paper_stats_from_database(database: Any, *, limit: int = 2000) -> dict[str, Any]:
    """آمار معاملات کاغذی بسته‌شده (برای معیار paper)."""
    try:
        from sqlalchemy import func, select

        from app.database.models import PaperTradeRecord

        with database.session_scope() as session:
            stmt = (
                select(PaperTradeRecord.pnl, PaperTradeRecord.closed_at)
                .where(func.lower(PaperTradeRecord.status) == "closed")
                .where(func.lower(PaperTradeRecord.mode) != "live")
                .order_by(PaperTradeRecord.closed_at.asc())
                .limit(limit)
            )
            pnls = [float(row[0] or 0.0) for row in session.execute(stmt).all()]
    except Exception:
        logger.debug("Paper stats unavailable", exc_info=True)
        return {"trades": 0}
    return summarize_pnls(pnls)


def summarize_pnls(pnls: list[float], *, start_equity: float = 1000.0) -> dict[str, Any]:
    """PF و افت سرمایه از فهرست سود/زیان به ترتیب زمان."""
    if not pnls:
        return {"trades": 0}
    gross_win = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    equity = start_equity
    peak = equity
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    return {
        "trades": len(pnls),
        "win_rate": round(sum(1 for p in pnls if p > 0) / len(pnls) * 100.0, 2),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else None,
        "net_pnl": round(sum(pnls), 4),
        "max_drawdown_percent": round(max_dd, 3),
    }


class ValidationGate:
    """دروازهٔ پیش‌فرض قفل؛ شواهد در فایل JSON نگه‌داری می‌شود."""

    def __init__(
        self,
        store_path: str | Path | None = None,
        *,
        criteria: GateCriteria | None = None,
        paper_source: Any = None,
        learner_source: Any = None,
        risk_source: Any = None,
    ) -> None:
        self.criteria = criteria or GateCriteria()
        self._path = Path(store_path) if store_path else None
        self._evidence: dict[str, Any] = {}
        self._paper_source = paper_source
        self._learner_source = learner_source
        self._risk_source = risk_source
        self._load()

    # ------------------------------------------------------------ شواهد
    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._evidence = data
        except Exception:  # noqa: BLE001 - فایل خراب = بدون شواهد = قفل
            logger.warning("Validation gate evidence unreadable; gate stays locked")
            self._evidence = {}

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._evidence, indent=2, default=str), encoding="utf-8")
        except Exception:
            logger.warning("Validation gate evidence could not be saved", exc_info=True)

    @property
    def evidence(self) -> dict[str, Any]:
        return dict(self._evidence)

    def record_backtest_report(self, report: dict[str, Any]) -> None:
        """
        ثبت شواهد از report.json ابزار run_backtest.

        معیار بک‌تست از موتور جدید کل دوره؛ walk-forward از جمع پنجره‌های
        آزمون (بهترین گونهٔ اعلام‌شده: tuned+learning) و کالیبراسیون از
        اطمینان نهایی.
        """
        full = (report.get("full_period") or {}).get("new") or {}
        folds = 0
        wf_trades: dict[str, Any] = {}
        for period in (report.get("walk_forward") or {}).values():
            folds += len(period.get("folds") or [])
            total = (period.get("test_total") or {}).get("new_tuned_learning") or {}
            wf_trades[str(len(wf_trades))] = total
        calibration = (report.get("full_period") or {}).get("calibration_new_final") or {}
        self._evidence.update({
            "backtest": full,
            "walk_forward": {"folds": folds, "periods": wf_trades},
            "calibration": calibration,
            "recorded_at": datetime.now(UTC).isoformat(),
        })
        self._save()

    # ------------------------------------------------------------ ارزیابی
    def evaluate(
        self,
        *,
        paper: dict[str, Any] | None = None,
        learner: dict[str, Any] | None = None,
        risk: dict[str, Any] | None = None,
    ) -> GateStatus:
        """ارزیابی همهٔ معیارها. نبود شاهد = رد."""
        c = self.criteria
        checks: list[GateCheck] = []

        bt = self._evidence.get("backtest") or {}
        n = int(bt.get("trades") or 0)
        pf = _num(bt.get("profit_factor"))
        exp = _num(bt.get("expectancy_r"))
        dd = _num(bt.get("max_drawdown_percent"))
        ok = n >= c.backtest_min_trades and pf is not None and pf >= c.backtest_min_pf and (exp or 0) > 0 and dd is not None and dd <= c.backtest_max_dd
        checks.append(GateCheck("backtest", ok, f"trades {n}/{c.backtest_min_trades}, PF {pf}, expectancy {exp}R, DD {dd}%"))

        wf = self._evidence.get("walk_forward") or {}
        folds = int(wf.get("folds") or 0)
        periods = list((wf.get("periods") or {}).values())
        wins = sum(float(p.get("total_r") or 0.0) for p in periods if p.get("trades"))
        pfs = [_num(p.get("profit_factor")) for p in periods if p.get("trades")]
        wf_ok = folds >= c.wf_min_folds and bool(pfs) and all(v is not None and v >= c.wf_min_pf for v in pfs) and wins > 0
        checks.append(GateCheck("walk_forward", wf_ok, f"folds {folds}/{c.wf_min_folds}, test PF {pfs}, test total {wins:.2f}R"))

        paper = paper if paper is not None else self._call(self._paper_source) or {"trades": 0}
        pn = int(paper.get("trades") or 0)
        ppf = _num(paper.get("profit_factor"))
        pdd = _num(paper.get("max_drawdown_percent"))
        p_ok = pn >= c.paper_min_trades and ppf is not None and ppf >= c.paper_min_pf and pdd is not None and pdd <= c.paper_max_dd
        checks.append(GateCheck("paper", p_ok, f"closed paper trades {pn}/{c.paper_min_trades}, PF {ppf}, DD {pdd}%"))

        cal = self._evidence.get("calibration") or {}
        brier = _num(cal.get("brier"))
        mono = cal.get("roughly_monotonic")
        cal_ok = brier is not None and brier <= c.calibration_max_brier and mono is True
        checks.append(GateCheck("calibration", cal_ok, f"Brier {brier}, monotonic {mono}"))

        risk = risk if risk is not None else self._call(self._risk_source) or {}
        r_ok = bool(risk.get("max_loss_set")) and bool(risk.get("daily_limit_set"))
        checks.append(GateCheck("risk", r_ok, f"per-trade loss limit {bool(risk.get('max_loss_set'))}, daily limit {bool(risk.get('daily_limit_set'))}"))

        learner = learner if learner is not None else self._call(self._learner_source) or {}
        records = int(learner.get("records") or 0)
        l_ok = records >= c.learner_min_records and learner.get("status") == "ok"
        checks.append(GateCheck("learner", l_ok, f"records {records}/{c.learner_min_records}, status {learner.get('status', 'empty')}"))

        return GateStatus(
            passed=all(check.passed for check in checks),
            checks=checks,
            checked_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def _call(source: Any) -> dict[str, Any] | None:
        if source is None:
            return None
        try:
            value = source() if callable(source) else source
            return value if isinstance(value, dict) else None
        except Exception:
            logger.debug("Validation gate source failed", exc_info=True)
            return None

    def live_allowed(self) -> tuple[bool, str]:
        """(اجازهٔ سفارش واقعی جدید، دلیل). هر خطا → قفل."""
        try:
            status = self.evaluate()
        except Exception as exc:  # noqa: BLE001
            return False, f"validation gate error: {exc}"
        return status.passed, status.reason


__all__ = [
    "GateCheck",
    "GateCriteria",
    "GateStatus",
    "ValidationGate",
    "paper_stats_from_database",
    "summarize_pnls",
]
