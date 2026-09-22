"""
موتور مرکزی هوش پیش‌بینی (Predictive Intelligence Engine) — خواستهٔ ۵۰.

چرا این فایل وجود دارد؟
    این کلاس «رئیس ارکستر» است: همهٔ ماژول‌های کوچک (کیفیت، فیچر،
    رژیم، توزیع، آنسامبل، سناریو، هشدار، …) را برای یک نماد به هم
    می‌بندد و خروجی یکپارچهٔ «امتیاز نهایی» می‌سازد. بدون آن، هر
    مصرف‌کننده (UI، عامل AI، اسکنر) باید خودش ترتیب ماژول‌ها را بلد
    باشد — و دیر یا زود ترتیب‌ها ناسازگار می‌شوند.

خط لوله:
    کندل‌ها → کیفیت → فیچر → رژیم (+گذار/ماشین حالت) → برنامهٔ افق‌ها
    → توزیع هر افق → آنسامبل (با کش) → فیوژن وزن‌دار → عدم‌قطعیت و
    رویداد → سناریو → نوسان/شکست/آنومالی/هشدار → ثبت در DB → گزارش.

اصول:
    • هیچ افقی بدون داده فعال نمی‌شود؛ همهٔ افق‌های خاموش با دلیل در
      خروجی‌اند.
    • گزارش‌ها کش TTL دارند (خواستهٔ ۳۵ — debounce) و «رویداد مهم»
      اعتبار را کم می‌کند نه جهت را.
    • LLM هیچ نقشی در اعداد ندارد؛ خروجی این موتور دادهٔ ساخت‌یافته
      است که عامل AI فقط «توضیح» می‌کند (خواستهٔ ۴۹).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from app.core.models import Candle
from app.logging import get_logger
from market.quality import clean_candles
from signals.prediction import events as events_mod
from signals.prediction.anomaly import detect_anomalies
from signals.prediction.breakout import assess_breakout, detect_false_breakout
from signals.prediction.crossasset import detect_lead_lag, market_context
from signals.prediction.distribution import build_distribution
from signals.prediction.explain import explain_from_fusion, feature_highlights
from signals.prediction.features import FeatureStore
from signals.prediction.fusion import (
    FusionComponent,
    fuse,
    multi_timeframe_view,
)
from signals.prediction.horizons import HORIZON_MINUTES, plan_horizons
from signals.prediction.models.ensemble import ModelEnsemble
from signals.prediction.regime import (
    RegimeAssessment,
    classify_timeframe,
    detect_transition,
    stage_of,
    transition_probabilities,
)
from signals.prediction.scenarios import build_scenarios
from signals.prediction.scoring import accuracy_summary
from signals.prediction.timeline import prediction_timeline, what_changed
from signals.prediction.uncertainty import effective_confidence
from signals.prediction.volatility import forecast_for_horizon
from signals.prediction.warning import build_warnings

logger = get_logger(__name__)

#: تایم‌فریم‌های پیش‌فرض تحلیل رژیم (خواستهٔ ۴/۵).
DEFAULT_TIMEFRAMES: tuple[str, ...] = ("15m", "1h", "4h", "1d")

#: TTL کش گزارش (ثانیه) — فاز ۱۴: جلوگیری از بمباران CPU/API.
REPORT_TTL = 60.0

#: TTL کش آنسامبل (ثانیه) — بازآموزی مدل گران است.
ENSEMBLE_TTL = 900.0

#: سقف کندل خواسته‌شده از منبع.
CANDLE_LIMIT = 600


@dataclass(slots=True)
class HorizonReport:
    """گزارش کامل یک افق."""

    horizon: str
    minutes: int
    source_timeframe: str
    direction: str
    probability: int
    confidence: int
    quantiles: dict[str, float]
    expected_range: tuple[float, float]
    method: str
    samples: int
    volatility: dict[str, Any] | None = None
    models: list[dict[str, Any]] = field(default_factory=list)
    model_agreement: float = 0.0
    conflict: bool = False
    scenarios: dict[str, Any] | None = None
    event_pressure: dict[str, Any] | None = None
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "horizon": self.horizon,
            "minutes": self.minutes,
            "source_timeframe": self.source_timeframe,
            "direction": self.direction,
            "probability": self.probability,
            "confidence": self.confidence,
            "quantiles": {k: round(v, 8) for k, v in self.quantiles.items()},
            "expected_range": [round(self.expected_range[0], 8), round(self.expected_range[1], 8)],
            "method": self.method,
            "samples": self.samples,
            "volatility": self.volatility,
            "models": list(self.models),
            "model_agreement": round(self.model_agreement, 3),
            "conflict": self.conflict,
            "scenarios": self.scenarios,
            "event_pressure": self.event_pressure,
            "reasons": list(self.reasons),
        }


@dataclass(slots=True)
class IntelligenceReport:
    """امتیاز نهایی هوش بازار برای یک نماد — خواستهٔ ۵۰."""

    symbol: str
    generated_at: str
    last_price: float
    horizons: list[HorizonReport] = field(default_factory=list)
    disabled_horizons: list[dict[str, Any]] = field(default_factory=list)
    regimes: dict[str, dict[str, Any]] = field(default_factory=dict)
    regime_transition: dict[str, Any] = field(default_factory=dict)
    market_stage: str = ""
    stage_probabilities: dict[str, Any] = field(default_factory=dict)
    multi_timeframe: dict[str, Any] = field(default_factory=dict)
    breakout: dict[str, Any] | None = None
    false_breakout: dict[str, Any] | None = None
    anomalies: dict[str, Any] | None = None
    warnings: list[dict[str, Any]] = field(default_factory=list)
    contributors: list[dict[str, Any]] = field(default_factory=list)
    feature_highlights: list[dict[str, Any]] = field(default_factory=list)
    cross_asset: dict[str, Any] | None = None
    lead_lag: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    what_changed: dict[str, Any] | None = None
    accuracy: dict[str, Any] = field(default_factory=dict)
    model_health: dict[str, Any] = field(default_factory=dict)
    data_quality: dict[str, Any] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """نمایش کامل دیکشنری — مادهٔ خام UI و عامل AI."""
        return {
            "symbol": self.symbol,
            "generated_at": self.generated_at,
            "last_price": round(self.last_price, 8),
            "horizons": [h.to_dict() for h in self.horizons],
            "disabled_horizons": list(self.disabled_horizons),
            "regimes": dict(self.regimes),
            "regime_transition": dict(self.regime_transition),
            "market_stage": self.market_stage,
            "stage_probabilities": dict(self.stage_probabilities),
            "multi_timeframe": dict(self.multi_timeframe),
            "breakout": self.breakout,
            "false_breakout": self.false_breakout,
            "anomalies": self.anomalies,
            "warnings": list(self.warnings),
            "contributors": list(self.contributors),
            "feature_highlights": list(self.feature_highlights),
            "cross_asset": self.cross_asset,
            "lead_lag": list(self.lead_lag),
            "timeline": list(self.timeline),
            "what_changed": self.what_changed,
            "accuracy": dict(self.accuracy),
            "model_health": dict(self.model_health),
            "data_quality": dict(self.data_quality),
            "note": self.note,
        }


class PredictiveIntelligenceEngine:
    """
    موتور مرکزی.

    پارامترهای سازنده:
        candle_source : تابع (symbol, timeframe, limit) → list[Candle]
                        (همگام یا ناهمگام — هر دو پشتیبانی می‌شود).
        store         : PredictionStore برای ثبت/حل پیش‌بینی‌ها (اختیاری).
        settings      : سرویس تنظیمات برای وزن‌ها و رویدادها (اختیاری).
        now           : تابع زمان برای آزمون‌پذیری (پیش‌فرض ساعت واقعی).
    """

    def __init__(
        self,
        candle_source: Callable[..., Any],
        *,
        store: Any = None,
        settings: Any = None,
        feature_store: FeatureStore | None = None,
        include_dl: bool = True,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._source = candle_source
        self._store = store
        self._settings = settings
        self._features = feature_store or FeatureStore()
        self._include_dl = include_dl
        self._now = now or (lambda: datetime.now(UTC))
        self._report_cache: dict[str, tuple[float, IntelligenceReport]] = {}
        self._ensemble_cache: dict[tuple[str, str], tuple[float, ModelEnsemble]] = {}
        self._regime_history: dict[str, list[Any]] = {}
        self._weights: dict[str, float] | None = None

    # ------------------------------------------------------------------
    async def _fetch(self, symbol: str, timeframe: str, limit: int = CANDLE_LIMIT) -> list[Candle]:
        """دریافت کندل از منبع — همگام یا ناهمگام."""
        result = self._source(symbol, timeframe, limit)
        if hasattr(result, "__await__"):
            result = await result
        return list(result or [])

    def report(self, symbol: str, *, force: bool = False) -> IntelligenceReport | None:
        """نسخهٔ همگام گزارش (از کش) — برای مسیرهای بدون async."""
        cached = self._report_cache.get(symbol)
        if cached is None:
            return None
        timestamp, report = cached
        age = time.monotonic() - timestamp
        report_dict_age = age  # خوانایی
        if report_dict_age > REPORT_TTL and not force:
            return None
        return report

    async def assess(
        self,
        symbol: str,
        *,
        timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES,
        peers: dict[str, list[Candle]] | None = None,
        force: bool = False,
    ) -> IntelligenceReport | None:
        """
        ساخت گزارش کامل هوش بازار نماد.

        peers: کندل‌های دارایی‌های مرجع (BTC/ETH/…) برای کراس-asset —
        اگر داده نبود این بخش صادقانه غایب است.
        """
        cached = self._report_cache.get(symbol)
        if cached is not None and not force and time.monotonic() - cached[0] < REPORT_TTL:
            return cached[1]

        # ---------- ۰) حل افق‌های سرآمده (قانون ۵) ----------
        # هر گزارش، پیش‌بینی‌های قبلیِ سرآمده را با قیمت واقعی می‌سنجد؛
        # آمار دقت همیشه از رکوردهای حل‌شده می‌آید.
        if self._store is not None:
            try:
                self._store.resolve_due()
            except Exception:  # noqa: BLE001 - حل افق نباید گزارش را بکشد
                logger.debug("prediction resolution skipped", exc_info=True)

        now = self._now()
        now_seconds = int(now.timestamp())

        # ---------- ۱) داده + کیفیت ----------
        raw: dict[str, list[Candle]] = {}
        cleaned: dict[str, list[Candle]] = {}
        quality: dict[str, dict[str, Any]] = {}
        for timeframe in timeframes:
            candles = await self._fetch(symbol, timeframe)
            raw[timeframe] = candles
            kept, report_q = clean_candles(candles, timeframe, symbol=symbol, now=now_seconds)
            cleaned[timeframe] = kept
            quality[timeframe] = {
                "usable": report_q.usable,
                "checked": report_q.checked,
                "invalid": report_q.invalid,
                "missing": report_q.missing,
                "duplicates": report_q.duplicates,
            }

        usable = {
            tf: candles
            for tf, candles in cleaned.items()
            if candles and quality[tf]["usable"]
        }
        if not usable:
            return None

        last_price = max(candles[-1].close for candles in usable.values() if candles)

        # ---------- ۲) فیچر + رژیم به‌ازای تایم‌فریم ----------
        assessments: dict[str, RegimeAssessment] = {}
        feature_sets: dict[str, Any] = {}
        for timeframe, candles in usable.items():
            features = self._features.build(
                candles, timeframe, symbol=symbol, now=now_seconds
            )
            feature_sets[timeframe] = features
            assessments[timeframe] = classify_timeframe(timeframe, candles, features)

        primary_tf = self._primary_timeframe(usable)
        primary_assessment = assessments[primary_tf]

        # گذار + ماشین حالت از تاریخچهٔ درون‌حافظه
        history = self._regime_history.setdefault(symbol, [])
        transition = detect_transition(history[-1] if history else None, primary_assessment)
        history.append(primary_assessment)
        if len(history) > 200:
            del history[:100]

        stage_probabilities = transition_probabilities(
            [a.regime for a in history if isinstance(a, RegimeAssessment)]
        )

        # ---------- ۳) برنامهٔ افق‌ها ----------
        available = {
            timeframe: len(candles) - 1  # آخرین کندل ممکن است در حال شکل‌گیری باشد
            for timeframe, candles in usable.items()
        }
        plans = plan_horizons(available)

        # ---------- ۴) به‌ازای افق: توزیع + آنسامبل + فیوژن ----------
        horizons: list[HorizonReport] = []
        disabled: list[dict[str, Any]] = []
        for plan in plans:
            if not plan.enabled or plan.source_timeframe not in usable:
                disabled.append(plan.to_dict())
                continue
            candles = usable[plan.source_timeframe]
            horizon_minutes = HORIZON_MINUTES[plan.horizon]

            # مومنتوم تیلت از رژیم تایم‌فریم مبدأ
            tilt = assessments[plan.source_timeframe].direction * 0.6
            atr_value = self._atr_of(feature_sets, plan.source_timeframe, candles)

            dist = build_distribution(
                horizon=plan.horizon,
                steps=plan.steps,
                candles=candles,
                momentum_tilt=tilt,
                atr=atr_value,
            )
            if dist is None:
                disabled.append({**plan.to_dict(), "reason": "distribution_unavailable"})
                continue

            # آنسامبل (کش‌شده) روی فیچر تایم‌فریم مبدأ
            ensemble = self._ensemble_for(
                symbol, plan.source_timeframe, feature_sets[plan.source_timeframe],
                plan.steps, candles,
            )
            ensemble_component_prob = 50
            models_out: list[dict[str, Any]] = []
            agreement = 1.0
            conflict = False
            latest_row = self._latest_row(feature_sets[plan.source_timeframe])
            if ensemble is not None and latest_row is not None:
                forecast = ensemble.predict(latest_row)
                ensemble_component_prob = int(round(forecast.prob_up * 100))
                models_out = [m.to_dict() for m in forecast.per_model]
                agreement = forecast.agreement
                conflict = forecast.conflict

            # فیوژن: توزیع + آنسامبل + رژیم + مومنتوم
            momentum_prob = self._momentum_probability(feature_sets[primary_tf])
            components = [
                FusionComponent("distribution", dist.direction, dist.probability, 1.0),
                FusionComponent("ensemble", "", ensemble_component_prob, 1.0,
                                "" if ensemble is not None else "ensemble_unavailable"),
                FusionComponent("regime", "", 50 + primary_assessment.direction * 15, 0.8),
                FusionComponent("momentum", "", momentum_prob, 0.6),
            ]
            fused = fuse(components, weights=self._weights)

            # رویداد + عدم‌قطعیت
            pressure = events_mod.event_pressure(
                self._load_events(), now=now, horizon_minutes=horizon_minutes
            )
            stability = self._regime_stability(history)
            checked = max(quality[primary_tf]["checked"], 1)
            data_quality_ratio = 1.0 - quality[primary_tf]["invalid"] / checked
            adjusted = effective_confidence(
                probability=fused.probability,
                model_agreement=agreement,
                data_quality_ratio=data_quality_ratio,
                regime_stability=stability,
                event_pressure=pressure.strength,
                method_reliability=0.9 if dist.method == "empirical" else 0.7,
            )

            vol_forecast = forecast_for_horizon(
                horizon=plan.horizon, steps=plan.steps, candles=candles
            )
            scenarios = build_scenarios(
                dist, momentum_tilt=tilt, regime_drivers=primary_assessment.drivers
            )

            horizons.append(
                HorizonReport(
                    horizon=plan.horizon,
                    minutes=horizon_minutes,
                    source_timeframe=plan.source_timeframe,
                    direction=adjusted.direction,
                    probability=adjusted.probability,
                    confidence=adjusted.confidence,
                    quantiles=dist.quantiles,
                    expected_range=dist.expected_range,
                    method=dist.method,
                    samples=dist.samples,
                    volatility=vol_forecast.to_dict() if vol_forecast else None,
                    models=models_out,
                    model_agreement=agreement,
                    conflict=conflict or fused.conflict,
                    scenarios=scenarios.to_dict(),
                    event_pressure=pressure.to_dict(),
                    reasons=adjusted.reasons,
                )
            )

        if not horizons:
            return None

        # ---------- ۵) ساختار بازار فرعی: شکست/آنومالی/هشدار ----------
        primary_candles = usable[primary_tf]
        breakout = assess_breakout(primary_candles)
        false_break = detect_false_breakout(primary_candles)
        anomaly_report = detect_anomalies(primary_candles)
        rsi_series = [
            v.get("rsi")
            for v in (feature_sets[primary_tf].vectors if feature_sets[primary_tf] else [])
        ]
        closes = [c.close for c in primary_candles]
        volumes = [c.volume for c in primary_candles]
        vol_regime = horizons[0].volatility.get("regime", "") if horizons[0].volatility else ""
        warnings_list = build_warnings(
            rsi_series=rsi_series,
            closes=closes,
            volume_series=volumes,
            volatility_regime=vol_regime,
            market_regime=primary_assessment.regime.value,
            anomaly_composite_z=anomaly_report.composite_z,
            transition_risk=transition.risk_level,
        )

        # ---------- ۶) کراس-asset (اختیاری) ----------
        cross = None
        lead_lag_results: list[dict[str, Any]] = []
        if peers:
            changes: dict[str, float] = {}
            for peer_symbol, peer_candles in peers.items():
                if len(peer_candles) < 30:
                    continue
                first, lastv = peer_candles[0].close, peer_candles[-1].close
                if first > 0:
                    changes[peer_symbol] = (lastv / first - 1.0) * 100
                if symbol != peer_symbol:
                    result = detect_lead_lag(symbol, primary_candles, peer_symbol, peer_candles)
                    if result is not None:
                        lead_lag_results.append(result.to_dict())
            if changes:
                cross = market_context(changes)

        # ---------- ۷) توضیح‌پذیری + تایم‌لاین + ثبت ----------
        contributors = explain_from_fusion(_components_dicts(horizons))
        highlights = feature_highlights(
            feature_sets[primary_tf].latest().values if feature_sets[primary_tf].latest() else {}
        )

        timeline: list[dict[str, Any]] = []
        changed: dict[str, Any] | None = None
        if self._store is not None:
            # حل پیش‌بینی‌های سرآمده با قیمت واقعی
            self._store.resolve_due(now=now)
            # ثبت همهٔ افق‌های فعال — ولی نه اسپم: فقط وقتی نظر جابه‌جا
            # شده یا به اندازهٔ کافی گذشته (خواسته‌های ۲۳ و ۲۹)
            for horizon_report in horizons:
                previous_records = _recent_for_horizon(
                    self._store, symbol, horizon_report.horizon
                )
                last = previous_records[-1] if previous_records else None
                if last is not None and not self._should_record(last, horizon_report, now):
                    continue
                self._store.save_horizon(
                    symbol=symbol,
                    horizon=horizon_report.horizon,
                    horizon_minutes=horizon_report.minutes,
                    direction=horizon_report.direction,
                    probability=horizon_report.probability,
                    confidence_effective=horizon_report.confidence,
                    quantiles=horizon_report.quantiles,
                    last_price=last_price,
                    method=horizon_report.method,
                    regime=primary_assessment.regime.value,
                    model_agreement=horizon_report.model_agreement,
                    models=horizon_report.models,
                    contributors=contributors,
                    created_at=now,
                )
            primary_horizon = horizons[0]
            primary_records = _recent_for_horizon(
                self._store, symbol, primary_horizon.horizon
            )
            if len(primary_records) >= 2:
                changed = what_changed(primary_records[-2], primary_records[-1])
            timeline = prediction_timeline(primary_records)

        # دقت و سلامت مدل از رکوردهای حل‌شده
        accuracy = {}
        health = {}
        if self._store is not None:
            from signals.prediction.scoring import model_health as _mh  # noqa: PLC0415

            resolved = self._store._repo.resolved(symbol=symbol, limit=500)  # noqa: SLF001
            accuracy = accuracy_summary(resolved)
            health = _mh(resolved)

        report = IntelligenceReport(
            symbol=symbol,
            generated_at=now.isoformat(),
            last_price=float(last_price),
            horizons=horizons,
            disabled_horizons=disabled,
            regimes={tf: a.to_dict() for tf, a in assessments.items()},
            regime_transition=transition.to_dict(),
            market_stage=stage_of(primary_assessment.regime),
            stage_probabilities=stage_probabilities,
            multi_timeframe=multi_timeframe_view(
                {tf: a.to_dict() for tf, a in assessments.items()}
            ),
            breakout=breakout.to_dict() if breakout else None,
            false_breakout=false_break,
            anomalies=anomaly_report.to_dict() if anomaly_report else None,
            warnings=[w.to_dict() for w in warnings_list],
            contributors=contributors,
            feature_highlights=highlights,
            cross_asset=cross,
            lead_lag=lead_lag_results,
            timeline=timeline,
            what_changed=changed,
            accuracy=accuracy,
            model_health=health,
            data_quality=quality,
        )
        self._report_cache[symbol] = (time.monotonic(), report)
        return report

    # ------------------------------------------------------------------
    # ابزارهای داخلی
    # ------------------------------------------------------------------
    def _primary_timeframe(self, usable: dict[str, list[Candle]]) -> str:
        """تایم‌فریم مرجع: متوسط‌ترینِ موجود."""
        order = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
        available = [tf for tf in order if tf in usable]
        return available[len(available) // 2] if available else next(iter(usable))

    def _atr_of(self, feature_sets: dict[str, Any], timeframe: str, candles: list[Candle]) -> float:
        """ATR از فیچرها (سری) یا محاسبهٔ محلی."""
        features = feature_sets.get(timeframe)
        if features and features.latest():
            atr = features.latest().get("atr")
            if atr and atr > 0:
                return float(atr)
        from signals.prediction.breakout import _atr  # noqa: PLC0415

        return _atr(candles)

    def _momentum_probability(self, features: Any) -> int:
        """احتمال مومنتوم لحظه‌ای از فاصلهٔ EMA و MACD."""
        if not features or not features.latest():
            return 50
        latest = features.latest()
        ema_distance = latest.get("ema_distance") or 0.0
        macd_histogram = latest.get("macd_histogram") or 0.0
        atr = latest.get("atr") or 0.0
        score = max(-1.0, min(1.0, ema_distance / 2.0))
        if atr > 0:
            score = 0.7 * score + 0.3 * max(-1.0, min(1.0, macd_histogram / atr))
        return int(round(50 + 35 * score))

    def _regime_stability(self, history: list[Any]) -> float:
        """پایداری رژیم: سهم رژیم غالب در ۱۰ ارزیابی اخیر."""
        recent = history[-10:]
        if len(recent) < 3:
            return 0.5
        counts: dict[str, int] = {}
        for assessment in recent:
            key = assessment.regime.value
            counts[key] = counts.get(key, 0) + 1
        dominant = max(counts.values())
        return dominant / len(recent)

    def _ensemble_for(
        self,
        symbol: str,
        timeframe: str,
        features: Any,
        steps: int,
        candles: list[Candle],
    ) -> ModelEnsemble | None:
        """آنسامبل کش‌شده برای (نماد، تایم‌فریم) — بازآموزی فقط با TTL."""
        if features is None or len(features) < 200:
            return None
        key = (symbol, timeframe)
        cached = self._ensemble_cache.get(key)
        if cached is not None and time.monotonic() - cached[0] < ENSEMBLE_TTL:
            return cached[1]

        from market.quality import timeframe_seconds  # noqa: PLC0415

        names = ["price_returns", "volume_change", "rsi", "macd_histogram",
                 "atr", "atr_percent", "ema_distance", "bollinger_width", "adx"]
        names = [n for n in names if n in features.available]
        times, rows = features.matrix(names)
        if len(rows) < 200:
            return None

        # برچسب: بازدهٔ «steps» کندل جلوتر — هم‌تراز با ردیف‌های فیچر.
        # ردیف‌های فیچر با «زمان بسته‌شدن» مهر می‌خورند؛ نگاشت به ایندکس
        # کندل از روی همان مهر انجام می‌شود تا هیچ جابه‌جایی خاموش رخ ندهد.
        close_times = [v.close_time for v in features.vectors]
        labels: list[float | None] = []
        import math as _math  # noqa: PLC0415

        step_seconds = timeframe_seconds(timeframe)
        close_to_index = {c.timestamp + step_seconds: i for i, c in enumerate(candles)}
        for moment in close_times:
            candle_index = close_to_index.get(moment)
            if candle_index is None:
                labels.append(None)
                continue
            ahead_index = candle_index + steps
            if ahead_index >= len(candles):
                labels.append(None)
                continue
            base = candles[candle_index].close
            ahead = candles[ahead_index].close
            if base <= 0 or ahead <= 0:
                labels.append(None)
                continue
            labels.append(_math.log(ahead / base))

        from signals.prediction.models.base import forward_labels  # noqa: PLC0415

        kept_rows, kept_labels, kept_times, _ = forward_labels(
            rows=rows, times=times, forward_returns=labels
        )
        if len(kept_rows) < 150:
            return None

        ensemble = ModelEnsemble(include_dl=self._include_dl)
        try:
            ensemble.fit(
                kept_times, kept_rows, kept_labels,
                horizon_steps=steps, step_seconds=step_seconds,
            )
        except Exception:  # noqa: BLE001 - شکست مدل‌ها نباید گزارش را بکشد
            logger.warning("Ensemble fit failed for %s %s", symbol, timeframe, exc_info=True)
            return None
        self._ensemble_cache[key] = (time.monotonic(), ensemble)
        return ensemble

    def _latest_row(self, features: Any) -> list[float] | None:
        """آخرین ردیف کامل فیچر برای پیش‌بینی لحظه‌ای."""
        if features is None or not features.latest():
            return None
        names = ["price_returns", "volume_change", "rsi", "macd_histogram",
                 "atr", "atr_percent", "ema_distance", "bollinger_width", "adx"]
        names = [n for n in names if n in features.available]
        _, rows = features.matrix(names)
        return rows[-1] if rows else None

    def _load_events(self) -> list[Any]:
        """رویدادهای دستی از تنظیمات."""
        if self._settings is None:
            return []
        return events_mod.load_events(self._settings)

    @staticmethod
    def _should_record(last_record: Any, horizon: HorizonReport, now: datetime) -> bool:
        """
        آیا این افق باید رکورد تازه بگیرد؟

        سیاست ضد‌اسپم (فاز ۱۴): ثبتِ تکراریِ هر دقیقه‌ای فقط DB را چاق
        می‌کند. ثبت وقتی لازم است که: جهت عوض شده، یا احتمال ≥ ۳ واحد
        جابه‌جا شده، یا از آخرین ثبت به اندازهٔ «حداقل ۱۵ دقیقه یا یک‌چهارم
        افق» گذشته باشد.
        """
        created = last_record.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        age_minutes = (now - created).total_seconds() / 60.0
        if age_minutes >= max(15.0, horizon.minutes / 4.0):
            return True
        if last_record.direction != horizon.direction:
            return True
        return abs(int(last_record.probability) - int(horizon.probability)) >= 3

    def set_weights(self, weights: dict[str, float] | None) -> None:
        """به‌روزرسانی وزن‌های فیوژن از بیرون (تنظیمات/فاز ۱۰)."""
        self._weights = weights

    def invalidate(self, symbol: str) -> None:
        """باطل‌کردن کش گزارش نماد — خواستهٔ ۳۵ (بازمحاسبهٔ رویدادمحور)."""
        self._report_cache.pop(symbol, None)

    async def accuracy_snapshot(self, symbol: str) -> dict[str, Any]:
        """
        آمار دقت و سلامت مدل‌ها فقط از رکوردهای حل‌شده.

        ابزار `get_prediction_accuracy` عامل AI از این متد می‌خواند تا
        پاسخ همیشه از دیتابیس بیاید نه از حافظهٔ مدل زبانی.
        """
        snapshot: dict[str, Any] = {"symbol": symbol, "available": False}
        if self._store is None:
            snapshot["reason"] = "no_prediction_store"
            return snapshot
        from signals.prediction.scoring import (  # noqa: PLC0415
            model_health as _mh,
        )

        resolved = self._store._repo.resolved(symbol=symbol, limit=500)  # noqa: SLF001
        summary = accuracy_summary(resolved)
        if not summary.get("resolved"):
            snapshot["reason"] = "no_resolved_predictions_yet"
            snapshot["note"] = (
                "Nothing has been scored yet; predictions resolve after their "
                "horizon elapses and a real price is observed."
            )
            return snapshot
        snapshot.update(summary)
        snapshot["model_health"] = _mh(resolved)
        snapshot["available"] = True
        return snapshot



def _recent_for_horizon(store: Any, symbol: str, horizon: str) -> list[Any]:
    """رکوردهای اخیر همان نماد/افق برای Timeline و What-Changed."""
    try:
        records = [
            record
            for record in store._repo.recent(symbol=symbol, limit=100)  # noqa: SLF001
            if record.horizon == horizon
        ]
        return records
    except Exception:  # noqa: BLE001 - DB نباید گزارش را بکشد
        logger.debug("recent predictions unavailable", exc_info=True)
        return []


def _components_dicts(horizons: list[HorizonReport]) -> list[dict[str, Any]]:
    """بازسازی اجزای فیوژنِ افق مرجع برای توضیح‌پذیری."""
    if not horizons:
        return []
    primary = horizons[0]
    return [
        {"name": "distribution", "probability": primary.probability, "weight": 1.0},
        {"name": "ensemble", "probability": _models_avg_prob(primary), "weight": 1.2},
        {"name": "regime", "probability": 50, "weight": 0.8},
        {"name": "momentum", "probability": 50, "weight": 0.6},
    ]


def _models_avg_prob(horizon: HorizonReport) -> float:
    """میانگین احتمال صعودی مدل‌های عضو."""
    if not horizon.models:
        return 50.0
    return sum(float(m.get("prob_up", 0.5)) * 100 for m in horizon.models) / len(horizon.models)
