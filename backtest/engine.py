"""
موتور بک‌تست — همان خط لولهٔ برنامه روی دادهٔ تاریخی.

گام ۱ (evaluate_symbol): در هر لحظهٔ ارزیابی t، `SignalEngine.generate`
واقعی با لایهٔ هوشمند (و در صورت درخواست، بازپخش موتور پیش‌بینی) اجرا و
یک `Evaluation` ذخیره می‌شود: جهت پایه، اطمینان فنی، ستاپ پایه (ورود/
SL/TP) و عکس لحظه‌ای کامل شواهد.

گام ۲ (simulate): از روی ارزیابی‌ها معامله ساخته و با `execution`
شبیه‌سازی می‌شود. دو حالت روی **همان** ارزیابی‌ها:
    old : موتور قبلی — هر ستاپ جهت‌دار با اطمینان فنی ≥ آستانه، اندازهٔ کامل.
    new : موتور جدید — همان ستاپ‌ها منهای NO_TRADE، اندازه طبق کیفیت
          (STRONG 1.0 / NORMAL 0.75 / WEAK 0.5).
چون گام ۱ یک‌بار اجرا می‌شود، مقایسه منصفانه است: تنها تفاوت لایهٔ تصمیم است.

یادگیری در walk-forward: یادگیرنده فقط روی معاملات بازهٔ آموزش fit و
مؤلفهٔ «history» عکس‌های بازهٔ آزمون با آن بازامتیازدهی می‌شود.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from backtest.data import TIMEFRAME_SECONDS
from backtest.execution import ExecutionModel, TradeResult, simulate_trade
from backtest.market import HistoricalMarket
from signals.intelligent_decision import (
    DECISION_NO_TRADE,
    DecisionConfig,
    IntelligentDecisionEngine,
)


@dataclass(slots=True)
class BacktestConfig:
    """پیکربندی اجرای بک‌تست."""

    timeframes: list[str] = field(default_factory=lambda: ["5m", "15m", "1h", "4h"])
    primary: str | None = None
    #: هر چند کندل پایه یک‌بار ارزیابی شود (۳ × ۵m = هر ۱۵ دقیقه)
    step_bars: int = 3
    #: کندل پایهٔ گرم‌کردن پیش از اولین ارزیابی
    warmup_bars: int = 720
    min_confidence: int = 50
    max_hold_bars: int = 96
    risk_percent: float = 1.0
    prediction_replay: bool = True
    execution: ExecutionModel = field(default_factory=ExecutionModel)


@dataclass(slots=True)
class Evaluation:
    """یک ارزیابی موتور در لحظهٔ t."""

    symbol: str
    time: int
    index: int
    base_direction: str
    technical_confidence: int
    final_confidence: int
    decision: str
    quality: str
    size_multiplier: float
    stop_loss: float | None
    take_profits: list[float]
    risk_reward: float | None
    intelligence: dict[str, Any] = field(default_factory=dict)

    @property
    def directional(self) -> bool:
        return self.base_direction in ("LONG", "SHORT") and self.stop_loss is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol, "time": self.time, "index": self.index,
            "base_direction": self.base_direction,
            "technical_confidence": self.technical_confidence,
            "final_confidence": self.final_confidence, "decision": self.decision,
            "quality": self.quality, "size_multiplier": self.size_multiplier,
            "stop_loss": self.stop_loss, "take_profits": list(self.take_profits),
            "risk_reward": self.risk_reward, "intelligence": self.intelligence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evaluation:
        return cls(**{k: data[k] for k in cls.__slots__ if k in data})


def build_signal_engine(market: HistoricalMarket, decision_config: DecisionConfig | None = None) -> Any:
    """ساخت همان SignalEngine برنامه روی بازار تاریخی (با رجیستری‌های واقعی)."""
    from indicators import IndicatorEngine
    from indicators.registry import register_builtin_indicators
    from signals.engine import SignalEngine
    from signals.strategies.registry import register_builtin_strategies

    register_builtin_indicators()
    register_builtin_strategies()
    engine = SignalEngine(market, IndicatorEngine())  # type: ignore[arg-type]
    engine.btc_cache_ttl = 0.0
    engine.set_intelligence(IntelligentDecisionEngine(decision_config))
    return engine


class BacktestEngine:
    """اجرای موتور روی یک HistoricalMarket."""

    def __init__(
        self,
        market: HistoricalMarket,
        config: BacktestConfig | None = None,
        *,
        decision_config: DecisionConfig | None = None,
    ) -> None:
        self.market = market
        self.config = config or BacktestConfig()
        self.decision = IntelligentDecisionEngine(decision_config)
        self.signal_engine = build_signal_engine(market, decision_config)
        self._prediction: Any = None
        if self.config.prediction_replay:
            from signals.prediction.engine import PredictiveIntelligenceEngine

            self._prediction = PredictiveIntelligenceEngine(
                market.candle_source,
                include_dl=False,
                now=lambda: datetime.fromtimestamp(market.now, UTC),
            )
            tfs = tuple(self.config.timeframes)

            async def _lookup(symbol: str) -> Any:
                return await self._prediction.assess(symbol, timeframes=tfs, force=True)

            self.signal_engine.set_intelligence(
                self.signal_engine.intelligence, prediction_lookup=_lookup
            )

    async def evaluate_symbol(
        self,
        symbol: str,
        *,
        start: int | None = None,
        end: int | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> list[Evaluation]:
        """ارزیابی نماد در همهٔ لحظه‌های t از بازهٔ [start, end]."""
        cfg = self.config
        base = self.market.base_candles(symbol)
        step = TIMEFRAME_SECONDS[self.market.base_tf]
        out: list[Evaluation] = []
        indices = list(range(cfg.warmup_bars, len(base) - 1, cfg.step_bars))
        for n, index in enumerate(indices):
            now = base[index].timestamp + step  # لحظهٔ بسته‌شدن کندل index
            if start is not None and now < start:
                continue
            if end is not None and now > end:
                break
            self.market.set_time(now)
            signal = await self.signal_engine.generate(
                symbol, list(cfg.timeframes), primary_timeframe=cfg.primary
            )
            out.append(self._to_evaluation(symbol, now, index, signal))
            if progress is not None and n % 50 == 0:
                progress(n, len(indices))
        return out

    @staticmethod
    def _to_evaluation(symbol: str, now: int, index: int, signal: Any) -> Evaluation:
        intel = dict(signal.intelligence or {})
        base_direction = str(intel.get("base_direction") or signal.direction.value)
        setup = intel.get("base_setup") or {}
        stop = signal.stop_loss if signal.stop_loss is not None else setup.get("stop_loss")
        targets = list(signal.take_profits) or list(setup.get("take_profits") or [])
        return Evaluation(
            symbol=symbol,
            time=now,
            index=index,
            base_direction=base_direction if base_direction in ("LONG", "SHORT") else "WAIT",
            technical_confidence=int(intel.get("technical_confidence", signal.confidence)),
            final_confidence=int(intel.get("final_confidence", signal.confidence)),
            decision=str(intel.get("decision") or ("TRADE" if signal.direction.value != "WAIT" else "WAIT")),
            quality=str(intel.get("quality") or ""),
            size_multiplier=float(intel.get("size_multiplier", 1.0) or 0.0),
            stop_loss=float(stop) if stop is not None else None,
            take_profits=[float(t) for t in targets],
            risk_reward=signal.risk_reward if signal.risk_reward is not None else setup.get("risk_reward"),
            intelligence=intel,
        )

    def annotate_extension(self, evaluations: list[Evaluation], *, limit: int = 250) -> int:
        """
        افزودن کشیدگی حرکت به ارزیابی‌های کش‌شدهٔ قدیمی (نسخهٔ ۲.۵.۶).

        همان تابع و همان کندل‌های قابل مشاهده در لحظهٔ t را به کار می‌برد که
        موتور زنده می‌بیند (بدون look-ahead)؛ ارزیابی‌هایی که مقدار دارند دست
        نمی‌خورند. تعداد ارزیابی‌های به‌روزشده را برمی‌گرداند.
        """
        from signals.intelligent_decision import extension_atr, extension_bucket

        updated = 0
        for ev in evaluations:
            intel = ev.intelligence
            if not ev.directional or not intel or "extension_bucket" in intel:
                continue
            timeframe = str(intel.get("primary_timeframe") or self.config.primary or "1h")
            candles = self.market.candles_at(ev.symbol, timeframe, limit, now=ev.time)
            value = extension_atr(candles, 1 if ev.base_direction == "LONG" else -1)
            intel["extension_atr"] = None if value is None else round(value, 3)
            intel["extension_bucket"] = extension_bucket(value)
            updated += 1
        return updated

    # ------------------------------------------------------------------
    def simulate(
        self,
        evaluations: list[Evaluation],
        *,
        mode: str = "new",
        decision_config: DecisionConfig | None = None,
        learner: Any = None,
        min_final_confidence: int | None = None,
    ) -> list[TradeResult]:
        """
        ساخت و شبیه‌سازی معاملات از ارزیابی‌ها.

        mode="old": همهٔ ستاپ‌های جهت‌دار با اطمینان فنی ≥ min_confidence، اندازهٔ ۱.
        mode="new": همان ستاپ‌ها؛ NO_TRADE رد، اندازه طبق کیفیت. اگر
        decision_config یا learner داده شود، عکس لحظه‌ای بازامتیازدهی می‌شود.
        min_final_confidence (اختیاری): گونهٔ «سخت‌گیر» برای مقایسه.
        """
        cfg = self.config
        trades: list[TradeResult] = []
        by_symbol: dict[str, list[Evaluation]] = {}
        for ev in evaluations:
            by_symbol.setdefault(ev.symbol, []).append(ev)
        for symbol, items in by_symbol.items():
            base = self.market.base_candles(symbol)
            stamps = [c.timestamp for c in base]
            busy_until = -1
            for ev in sorted(items, key=lambda e: e.time):
                if not ev.directional or ev.technical_confidence < cfg.min_confidence:
                    continue
                if ev.time <= busy_until:
                    continue
                meta = {
                    "technical_confidence": ev.technical_confidence,
                    "final_confidence": ev.final_confidence,
                    "quality": ev.quality or "",
                    "decision": ev.decision,
                    "regime": str(ev.intelligence.get("regime") or "unknown"),
                    "evidence_ratio": ev.intelligence.get("evidence_ratio"),
                    "extension_bucket": str(ev.intelligence.get("extension_bucket") or ""),
                }
                size = 1.0
                if mode == "new":
                    decision, quality, final, size = self._rescored(ev, decision_config, learner)
                    meta.update(decision=decision, quality=quality, final_confidence=final)
                    if decision == DECISION_NO_TRADE:
                        continue
                    if min_final_confidence is not None and final < min_final_confidence:
                        continue
                first = bisect.bisect_left(stamps, ev.time)  # اولین کندل با open ≥ t
                future = base[first:first + cfg.max_hold_bars]
                result = simulate_trade(
                    symbol=symbol,
                    direction=ev.base_direction,
                    signal_time=ev.time,
                    stop_loss=float(ev.stop_loss or 0.0),
                    take_profits=ev.take_profits,
                    future=future,
                    model=cfg.execution,
                    max_bars=cfg.max_hold_bars,
                    size_multiplier=size,
                    meta={**meta, "strategy_scores": ev.intelligence.get("strategy_scores") or {}},
                )
                if result is None:
                    continue
                trades.append(result)
                busy_until = result.exit_time + TIMEFRAME_SECONDS[self.market.base_tf]
        return trades

    def _rescored(
        self, ev: Evaluation, config: DecisionConfig | None, learner: Any
    ) -> tuple[str, str, int, float]:
        intel = ev.intelligence
        if not intel.get("components"):
            return ev.decision, ev.quality, ev.final_confidence, ev.size_multiplier or 1.0
        if config is None and learner is None:
            return ev.decision, ev.quality, ev.final_confidence, ev.size_multiplier
        snapshot = dict(intel)
        if learner is not None:
            history = learner.historical_edge(
                ev.base_direction, str(intel.get("regime") or "unknown"),
                str(intel.get("primary_timeframe") or ""),
                extension=str(intel.get("extension_bucket") or ""),
            )
            components = [dict(c) for c in intel["components"]]
            for comp in components:
                if comp["name"] == "history":
                    if history.get("reliable"):
                        edge = float(history.get("edge") or 50)
                        comp["score"] = max(-1.0, min(1.0, (edge - 50.0) / 25.0))
                        comp["reliability"] = max(0.3, min(1.0, float(history.get("samples") or 0) / 100.0))
                    else:
                        comp["score"], comp["reliability"] = 0.0, 0.0
            snapshot["components"] = components
        result = self.decision.rescore(snapshot, config)
        return result["decision"], result["quality"], result["final_confidence"], result["size_multiplier"]


def records_from_trades(trades: list[TradeResult]) -> list[Any]:
    """تبدیل معاملات بک‌تست به رکورد یادگیرنده."""
    from signals.learning import OutcomeRecord

    out = []
    for trade in trades:
        out.append(
            OutcomeRecord(
                direction=trade.direction,
                won=trade.won,
                r_multiple=trade.r_multiple,
                regime=str(trade.meta.get("regime") or "unknown"),
                timeframe="",
                quality=str(trade.meta.get("quality") or ""),
                symbol=trade.symbol,
                strategy_scores=dict(trade.meta.get("strategy_scores") or {}),
                source="backtest",
                mae=trade.mae_percent,
                mfe=trade.mfe_percent,
                exit_reason=trade.exit_reason,
                extension=str(trade.meta.get("extension_bucket") or ""),
            )
        )
    return out


__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "Evaluation",
    "build_signal_engine",
    "records_from_trades",
]
