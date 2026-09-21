"""
موتور تولید سیگنال.

چرا وجود دارد؟
    این موتور، قلب تصمیم‌گیری برنامه است و طبق بند ۲۶ سند پروژه **کاملاً
    مستقل از هوش مصنوعی** کار می‌کند:

        داده واقعی → اندیکاتورها → رأی راهبردها → جمع‌بندی وزن‌دار
              → موتور ریسک → سیگنال نهایی (LONG / SHORT / WAIT)

    هوش مصنوعی در صورت در دسترس بودن، فقط توضیح متنی سیگنال را غنی‌تر
    می‌کند و **هرگز جهت سیگنال را تغییر نمی‌دهد**.

درباره امتیاز اطمینان:
    عدد Confidence «میزان هم‌سویی عوامل تحلیلی» است، نه احتمال سود. این
    نکته باید در رابط کاربری و گزارش‌ها هم به کاربر گفته شود.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.constants import (
    DEFAULT_TIMEFRAME_ROLES,
    MIN_CANDLES_FOR_ANALYSIS,
    AnalysisStatus,
    MarketStructureType,
    SignalDirection,
    TrendDirection,
)
from app.core.models import (
    RiskParameters,
    SupportResistanceLevel,
    TradingSignal,
)
from app.exceptions import AppError, InsufficientDataError
from app.logging import get_logger
from indicators.engine import IndicatorEngine
from indicators.support_resistance import (
    analyze_market_structure,
    detect_trend,
    find_support_resistance,
)
from market.engine import MarketDataEngine
from signals.risk_engine import RiskEngine
from signals.validity import entry_window_minutes, expiry_minutes, primary_timeframe as pick_speed_frame
from signals import confidence as confidence_model
from signals.forecast import forecast_next
from signals.strategies.base import StrategyContext, StrategyVote
from signals.strategies.registry import StrategyRegistry, strategy_registry

logger = get_logger(__name__)

#: اندیکاتورهایی که موتور سیگنال همیشه لازم دارد
REQUIRED_INDICATORS = [
    "EMA", "SMA", "RSI", "MACD", "ADX", "ATR",
    "BBANDS", "STOCH", "DONCHIAN", "KELTNER", "VOLUME_SMA", "OBV",
]

#: پارامترهای اجباری موتور سیگنال.
#: پیش‌فرض EMA برابر ۲۱ و SMA برابر ۲۰ است؛ مقایسه این دو به‌عنوان
#: «میانگین تند و کند» بی‌معناست چون تقریباً بر هم منطبق‌اند. بنابراین
#: SMA را صریحاً روی ۵۰ می‌بریم تا تقاطع میانگین‌ها واقعاً معنا داشته باشد.
SIGNAL_INDICATOR_PARAMETERS: dict[str, dict[str, Any]] = {
    "EMA": {"period": 21},
    "SMA": {"period": 50},
}

#: وزن هر تایم‌فریم در جمع‌بندی (تایم‌فریم بزرگ‌تر، وزن بیشتر)
TIMEFRAME_WEIGHTS: dict[str, float] = {
    "1m": 0.3, "3m": 0.4, "5m": 0.5, "15m": 0.7, "30m": 0.8,
    "1h": 1.0, "2h": 1.1, "4h": 1.3, "6h": 1.4, "8h": 1.45,
    "12h": 1.5, "1d": 1.8, "1w": 2.0,
}

#: آستانه تصمیم‌گیری؛ زیر این مقدار یعنی عوامل به‌اندازه کافی هم‌سو نیستند
DECISION_THRESHOLD = 0.22


class SignalEngine:
    """
    تولیدکننده سیگنال معاملاتی.

    وابستگی‌ها تزریق می‌شوند تا در تست بتوان جایگزینشان کرد.
    """

    def __init__(
        self,
        market_engine: MarketDataEngine,
        indicator_engine: IndicatorEngine,
        risk_engine: RiskEngine | None = None,
        registry: StrategyRegistry | None = None,
        *,
        risk_parameters: RiskParameters | None = None,
        candle_limit: int = 250,
        calibration_source: Any = None,
    ) -> None:
        self._market = market_engine
        self._indicators = indicator_engine
        self._risk_engine = risk_engine or RiskEngine(risk_parameters)
        self._registry = registry or strategy_registry
        self._candle_limit = candle_limit
        # منبع آمار نتایج واقعی (اختیاری). وقتی وصل باشد، ضریب اطمینان
        # با نرخ برد واقعی همان بازه تعدیل می‌شود؛ نبودش یعنی سامانه
        # ادعای اثبات‌نشده نمی‌کند.
        self._calibration_source = calibration_source

    @property
    def risk_engine(self) -> RiskEngine:
        """دسترسی به موتور ریسک (برای هم‌گام‌سازی تنظیمات)."""
        return self._risk_engine

    def set_risk_parameters(self, parameters: RiskParameters) -> None:
        """به‌روزرسانی پارامترهای ریسک."""
        self._risk_engine.set_parameters(parameters)

    # ------------------------------------------------------------------
    # تولید سیگنال
    # ------------------------------------------------------------------
    async def generate(
        self,
        symbol: str,
        timeframes: list[str] | None = None,
        *,
        primary_timeframe: str | None = None,
    ) -> TradingSignal:
        """
        تولید سیگنال برای یک نماد.

        اگر داده هیچ تایم‌فریمی کافی نباشد، به‌جای حدس زدن، سیگنال WAIT با
        وضعیت INSUFFICIENT_DATA برگردانده می‌شود.
        """
        frames = timeframes or ["1d", "4h", "1h", "15m"]
        primary = primary_timeframe or self._pick_primary(frames)

        analyses: dict[str, dict[str, Any]] = {}
        notes: list[str] = []

        # تحلیل همه تایم‌فریم‌ها به‌صورت موازی انجام می‌شود.
        # قبلاً حلقه ترتیبی بود و زمان کل، جمع زمان تک‌تک تایم‌فریم‌ها می‌شد؛
        # حالا زمان کل تقریباً برابر کندترین تایم‌فریم است (حدود ۳ برابر سریع‌تر).
        results = await asyncio.gather(
            *(self._analyze_timeframe(symbol, timeframe) for timeframe in frames),
            return_exceptions=True,
        )
        for timeframe, analysis in zip(frames, results, strict=True):
            if isinstance(analysis, InsufficientDataError):
                notes.append(f"{timeframe}: {analysis.message}")
                continue
            if isinstance(analysis, AppError):
                notes.append(f"{timeframe}: {analysis.__class__.__name__}")
                logger.warning("Timeframe %s failed for %s: %s", timeframe, symbol, analysis.message)
                continue
            if isinstance(analysis, BaseException):
                notes.append(f"{timeframe}: {analysis.__class__.__name__}")
                logger.warning("Timeframe %s crashed for %s: %s", timeframe, symbol, analysis)
                continue
            analyses[timeframe] = analysis

        if not analyses:
            logger.info("No usable timeframe for %s; returning WAIT", symbol)
            return self._wait_signal(
                symbol,
                frames,
                reason="Insufficient market data on every requested timeframe",
                status=AnalysisStatus.INSUFFICIENT_DATA,
                notes=notes,
            )

        if primary not in analyses:
            primary = self._pick_primary(list(analyses))

        # رأی‌گیری راهبردها روی هر تایم‌فریم
        higher_trend = self._higher_timeframe_trend(analyses, frames)
        votes_by_timeframe: dict[str, list[StrategyVote]] = {}
        for timeframe, analysis in analyses.items():
            context = StrategyContext(
                symbol=symbol,
                timeframe=timeframe,
                candles=analysis["candles"],
                indicators=analysis["indicators"],
                structure=analysis["structure"],
                levels=analysis["levels"],
                trend=analysis["trend"],
                higher_timeframe_trend=higher_trend,
            )
            votes_by_timeframe[timeframe] = [
                strategy.evaluate(context) for strategy in self._registry.all()
            ]

        total_score, alignment, vote_reasons = self._aggregate(votes_by_timeframe)
        direction = self._decide(total_score)

        primary_analysis = analyses[primary]
        entry = primary_analysis["candles"][-1].close
        atr = self._atr_of(primary_analysis)

        if direction == SignalDirection.WAIT:
            waiting = self._wait_signal(
                symbol,
                list(analyses),
                reason=(
                    f"Analytical factors are not aligned enough (score {total_score:+.2f}, "
                    f"threshold ±{DECISION_THRESHOLD}). Waiting is the safer choice."
                ),
                status=AnalysisStatus.OK,
                notes=notes,
                confidence=int(alignment * 100),
                trend=primary_analysis["trend"],
                structure=self._structure_type(primary_analysis),
                votes=votes_by_timeframe,
                extra_reasons=vote_reasons,
            )
            # حتی وقتی پاسخ «انتظار» است، کاربر باید بداند بازار
            # احتمالاً در چه محدوده‌ای می‌ماند؛ همین بازه به او می‌گوید
            # منتظر شکست کدام عدد باشد.
            self._attach_forecast(waiting, analyses, primary)
            return waiting

        # محاسبه حد ضرر و اهداف بر پایه ساختار واقعی
        structure = primary_analysis["structure"]
        stop_loss, stop_method = self._risk_engine.calculate_stop_loss(
            direction,
            entry,
            atr,
            levels=primary_analysis["levels"],
            swing_high=structure.last_swing_high if structure else None,
            swing_low=structure.last_swing_low if structure else None,
        )
        take_profits = self._risk_engine.calculate_take_profits(
            direction, entry, stop_loss, primary_analysis["levels"]
        )
        confidence = int(round(alignment * 100))
        assessment = self._risk_engine.assess(
            direction, entry, stop_loss, take_profits, atr, confidence=confidence
        )

        # موتور ریسک حق وتو دارد
        if not assessment.approved:
            logger.info("Risk engine rejected %s setup for %s: %s", direction.value, symbol, assessment.rejection_reason)
            signal = self._wait_signal(
                symbol,
                list(analyses),
                reason=(
                    f"A {direction.value} setup was found but the risk engine rejected it: "
                    f"{assessment.rejection_reason}"
                ),
                status=AnalysisStatus.OK,
                notes=notes,
                confidence=min(confidence, 45),
                trend=primary_analysis["trend"],
                structure=self._structure_type(primary_analysis),
                votes=votes_by_timeframe,
                extra_reasons=vote_reasons,
            )
            signal.risk = assessment
            self._attach_forecast(signal, analyses, primary)
            return signal

        entry_band = atr * 0.15 if atr else entry * 0.001
        reason = self._build_reason(direction, total_score, vote_reasons, stop_method, assessment)

        signal = TradingSignal(
            symbol=symbol,
            exchange=self._market.exchange_name,
            direction=direction,
            entry_min=round(entry - entry_band, 8),
            entry_max=round(entry + entry_band, 8),
            stop_loss=stop_loss,
            take_profits=take_profits,
            risk_reward=assessment.risk_reward,
            leverage=assessment.suggested_leverage,
            confidence=confidence,
            trend=primary_analysis["trend"],
            market_structure=self._structure_type(primary_analysis),
            reason=reason,
            invalidation=self._build_invalidation(direction, stop_loss, structure),
            timeframes=list(analyses),
            indicators_used=sorted(primary_analysis["indicators"]),
            status=AnalysisStatus.OK,
            created_at=datetime.now(UTC),
            risk=assessment,
        )
        # پنجرهٔ اعتبار بخشی از خود سیگنال است، نه افزودنی بعدی.
        # سیگنالی بدون تاریخ مصرف، به کاربر می‌گوید «همیشه معتبر است»
        # که هرگز درست نیست: شرایطی که سیگنال را ساخت با گذشت چند
        # کندل از بین می‌رود.
        self._stamp_validity(signal)
        self._attach_forecast(signal, analyses, primary)
        logger.info(
            "Signal for %s: %s | entry %.6g | SL %.6g | R/R %.2f | confidence %d",
            symbol, direction.value, entry, stop_loss, assessment.risk_reward, confidence,
        )
        return signal

    @staticmethod
    def _attach_forecast(
        signal: TradingSignal,
        analyses: dict[str, dict],
        primary: str,
    ) -> None:
        """
        افزودن پیش‌بینی تایم‌فریم بعدی به سیگنال.

        کاربر خواست بداند «۱۵ دقیقه، یک ساعت و چهار ساعت بعد بازار کجا
        می‌رود». پاسخ صادقانه یک بازهٔ محتمل است، نه یک عدد قطعی؛ منطقش
        در signals.forecast توضیح داده شده.

        خطای پیش‌بینی هرگز نباید تولید سیگنال را متوقف کند: سیگنال
        بدون پیش‌بینی هنوز ارزشمند است.
        """
        analysis = analyses.get(primary)
        if not analysis:
            return
        candles = analysis.get("candles") or []
        if not candles:
            return
        try:
            atr_payload = analysis.get("indicators", {}).get("ATR", {})
            atr_value = None
            if isinstance(atr_payload, dict):
                latest = atr_payload.get("latest")
                if isinstance(latest, dict):
                    raw = latest.get("atr")
                    if isinstance(raw, (int, float)):
                        atr_value = float(raw)
            result = forecast_next(
                symbol=signal.symbol,
                timeframe=primary,
                candles=candles,
                direction=signal.direction,
                confidence=signal.confidence,
                atr=atr_value,
            )
            signal.forecast = [h.as_dict() for h in result.horizons]
        except Exception:  # pragma: no cover - پیش‌بینی هرگز مسدودکننده نیست
            logger.warning("Forecast failed for %s", signal.symbol, exc_info=True)

    @staticmethod
    def _stamp_validity(signal: TradingSignal) -> None:
        """
        نوشتن پنجرهٔ اعتبار روی سیگنال.

        تایم‌فریم سرعت، **کوچک‌ترین** تایم‌فریم تحلیل است: سیگنالی که
        به کندل ۱۵ دقیقه‌ای نگاه می‌کند با همان سرعت هم کهنه می‌شود،
        حتی اگر تصویر کلان از نمودار روزانه آمده باشد.
        """
        frame = pick_speed_frame(signal.timeframes)
        signal.primary_timeframe = frame
        signal.enter_before = signal.created_at + timedelta(
            minutes=entry_window_minutes(frame)
        )
        signal.expires_at = signal.created_at + timedelta(minutes=expiry_minutes(frame))

    # ------------------------------------------------------------------
    # غنی‌سازی اختیاری با هوش مصنوعی
    # ------------------------------------------------------------------
    async def enrich_with_ai(self, signal: TradingSignal, analyst: Any) -> TradingSignal:
        """
        افزودن توضیح تحلیلی هوش مصنوعی به سیگنال موجود.

        **جهت، ورود، حد ضرر و اهداف تغییر نمی‌کنند.** اگر هوش مصنوعی در
        دسترس نباشد، سیگنال دست‌نخورده و بدون خطا برمی‌گردد — این تضمین
        همان استقلال موتور سیگنال از هوش مصنوعی است.
        """
        try:
            from ai.agent.analyst import AnalysisRequest

            result = await analyst.analyze(
                AnalysisRequest(symbol=signal.symbol, timeframes=list(signal.timeframes))
            )
            if result.succeeded and result.content:
                signal.analysis_text = result.content
                signal.ai_provider = result.provider
                signal.ai_model = result.model
                logger.info("Signal for %s enriched by %s", signal.symbol, result.provider)
            else:
                signal.analysis_text = ""
                logger.info("AI enrichment unavailable for %s; base signal kept", signal.symbol)
        except Exception as exc:  # noqa: BLE001 - غنی‌سازی هرگز نباید سیگنال را خراب کند
            logger.warning("AI enrichment failed for %s: %s", signal.symbol, exc.__class__.__name__)
        return signal

    # ------------------------------------------------------------------
    # تحلیل یک تایم‌فریم
    # ------------------------------------------------------------------
    async def _analyze_timeframe(self, symbol: str, timeframe: str) -> dict[str, Any]:
        """گردآوری کندل، اندیکاتور، ساختار و سطوح یک تایم‌فریم."""
        candles = await self._market.get_candles(symbol, timeframe, self._candle_limit)
        if len(candles) < MIN_CANDLES_FOR_ANALYSIS:
            raise InsufficientDataError(
                f"Only {len(candles)} candles available (need {MIN_CANDLES_FOR_ANALYSIS})",
                details={"symbol": symbol, "timeframe": timeframe},
            )

        results = self._indicators.calculate_many(
            REQUIRED_INDICATORS,
            candles,
            timeframe,
            symbol=symbol,
            parameters=SIGNAL_INDICATOR_PARAMETERS,
        )
        indicators = {name: result.to_summary() for name, result in results.items()}

        return {
            "candles": candles,
            "indicators": indicators,
            "structure": analyze_market_structure(candles, timeframe),
            "levels": find_support_resistance(candles, max_levels=10),
            "trend": detect_trend(candles),
            "atr_result": results.get("ATR"),
        }

    # ------------------------------------------------------------------
    # جمع‌بندی رأی‌ها
    # ------------------------------------------------------------------
    def _confidence_buckets(self) -> dict[str, dict[str, Any]] | None:
        """
        آمار نرخ برد به تفکیک بازهٔ اطمینان، اگر در دسترس باشد.

        شکست در خواندن آمار نباید تولید سیگنال را متوقف کند؛ در آن حالت
        فقط کالیبراسیون انجام نمی‌شود.
        """
        source = self._calibration_source
        if source is None:
            return None
        try:
            getter = getattr(source, "confidence_buckets", None)
            return getter() if callable(getter) else None
        except Exception:  # noqa: BLE001 - آمار نبود، سیگنال که هست
            logger.debug("Confidence calibration unavailable", exc_info=True)
            return None

    def _aggregate(
        self,
        votes_by_timeframe: dict[str, list[StrategyVote]],
    ) -> tuple[float, float, list[str]]:
        """
        جمع‌بندی وزن‌دار رأی راهبردها در همه تایم‌فریم‌ها.

        بازگشتی: (امتیاز نهایی در بازه ۱-، ۱+ ، درجه هم‌سویی، دلایل)

        درجه هم‌سویی از دو مؤلفه ساخته می‌شود:
            • قدرت مطلق امتیاز نهایی
            • درصد رأی‌های هم‌جهت با نتیجه (اجماع)
        بنابراین اگر راهبردها یکدیگر را خنثی کنند، اطمینان پایین می‌ماند.
        """
        weighted_sum = 0.0
        weight_total = 0.0
        directional_votes: list[SignalDirection] = []
        # نام راهبردهایی که رأی جهت‌دار داده‌اند و تایم‌فریم‌هایی که
        # دست‌کم یک رأی جهت‌دار داشته‌اند؛ مبنای «پوشش شواهد».
        votes_by_strategy: dict[str, set[SignalDirection]] = {}
        frames_with_opinion: set[str] = set()
        # دلایل به تفکیک جهت نگه داشته می‌شوند تا در پایان فقط عوامل
        # هم‌سو با تصمیم نهایی به کاربر نشان داده شود؛ نمایش دلایل متناقض
        # در کنار هم، توضیح سیگنال را بی‌معنا می‌کند.
        reasons_by_direction: dict[SignalDirection, list[str]] = {
            SignalDirection.LONG: [],
            SignalDirection.SHORT: [],
        }

        for timeframe, votes in votes_by_timeframe.items():
            tf_weight = TIMEFRAME_WEIGHTS.get(timeframe, 1.0)
            for vote in votes:
                if not vote.applicable:
                    continue
                weighted_sum += vote.weighted_score * tf_weight
                weight_total += vote.weight * tf_weight
                directional_votes.append(vote.direction)
                if vote.direction != SignalDirection.WAIT:
                    votes_by_strategy.setdefault(str(vote.strategy), set()).add(
                        vote.direction
                    )
                    frames_with_opinion.add(timeframe)
                if vote.direction in reasons_by_direction:
                    for reason in vote.reasons[:2]:
                        entry = f"[{timeframe}] {reason}"
                        if entry not in reasons_by_direction[vote.direction]:
                            reasons_by_direction[vote.direction].append(entry)

        if weight_total <= 0:
            return 0.0, 0.0, ["No strategy was applicable in the current market conditions"]

        score = weighted_sum / weight_total
        score = max(-1.0, min(1.0, score))

        # اجماع: چند درصد رأی‌های جهت‌دار هم‌سو با نتیجه‌اند؟
        target = SignalDirection.LONG if score > 0 else SignalDirection.SHORT
        meaningful = [v for v in directional_votes if v != SignalDirection.WAIT]
        consensus = (
            sum(1 for v in meaningful if v == target) / len(meaningful) if meaningful else 0.0
        )

        agreeing_strategies = {
            name for name, directions in votes_by_strategy.items() if target in directions
        }
        contributing_frames = frames_with_opinion

        # پوشش شواهد: چند راهبرد **متمایز** و چند تایم‌فریم واقعاً رأی
        # جهت‌دار داده‌اند. بدون این، یک راهبرد تنها با امتیاز کامل
        # ضریب ۱۰۰٪ می‌ساخت — همان سیگنال‌های «۱۰۰٪» که ضرر دادند.
        alignment = confidence_model.compute(
            score=score,
            consensus=consensus,
            strategy_count=len(agreeing_strategies),
            timeframe_count=len(contributing_frames),
            buckets=self._confidence_buckets(),
        ).final / 100.0

        # دلایل هم‌سو اول، و در صورت وجود، عوامل مخالف با برچسب صریح
        supporting = reasons_by_direction[target]
        opposing = reasons_by_direction[
            SignalDirection.SHORT if target == SignalDirection.LONG else SignalDirection.LONG
        ]
        reasons = list(supporting)
        if opposing:
            reasons.append(f"Opposing factors ({len(opposing)}): " + "; ".join(opposing[:2]))
        return score, alignment, reasons

    @staticmethod
    def _decide(score: float) -> SignalDirection:
        """تبدیل امتیاز نهایی به جهت سیگنال."""
        if score >= DECISION_THRESHOLD:
            return SignalDirection.LONG
        if score <= -DECISION_THRESHOLD:
            return SignalDirection.SHORT
        return SignalDirection.WAIT

    # ------------------------------------------------------------------
    # کمکی‌ها
    # ------------------------------------------------------------------
    @staticmethod
    def _pick_primary(frames: list[str]) -> str:
        """
        انتخاب تایم‌فریم اصلی برای ورود.

        نقش‌های پیش‌فرض در constants تعریف شده‌اند؛ در نبود آن‌ها،
        تایم‌فریم میانی انتخاب می‌شود تا نه بیش از حد کوتاه باشد و نه کند.
        """
        # نگاشت به‌صورت «تایم‌فریم → نقش» است، پس دنبال نقش entry می‌گردیم
        for timeframe, role in DEFAULT_TIMEFRAME_ROLES.items():
            if role == "entry" and timeframe in frames:
                return timeframe
        for preferred in ("1h", "4h", "15m", "30m"):
            if preferred in frames:
                return preferred
        return frames[len(frames) // 2] if frames else "1h"

    @staticmethod
    def _higher_timeframe_trend(
        analyses: dict[str, dict[str, Any]], frames: list[str]
    ) -> TrendDirection:
        """روند بزرگ‌ترین تایم‌فریم موجود، به‌عنوان فیلتر جهت."""
        ordered = sorted(
            analyses, key=lambda tf: TIMEFRAME_WEIGHTS.get(tf, 1.0), reverse=True
        )
        return analyses[ordered[0]]["trend"] if ordered else TrendDirection.NEUTRAL

    @staticmethod
    def _atr_of(analysis: dict[str, Any]) -> float | None:
        """استخراج مقدار ATR از تحلیل یک تایم‌فریم."""
        atr_result = analysis.get("atr_result")
        if atr_result is None:
            return None
        value = atr_result.latest.get("atr")
        return float(value) if isinstance(value, (int, float)) else None

    @staticmethod
    def _structure_type(analysis: dict[str, Any]) -> MarketStructureType:
        """نوع ساختار بازار یک تایم‌فریم."""
        structure = analysis.get("structure")
        return structure.structure if structure else MarketStructureType.UNDEFINED

    @staticmethod
    def _build_reason(
        direction: SignalDirection,
        score: float,
        reasons: list[str],
        stop_method: str,
        assessment: Any,
    ) -> str:
        """ساخت متن دلیل سیگنال از رأی راهبردها."""
        head = (
            f"{direction.value} setup with an aggregated factor score of {score:+.2f}. "
            f"Stop loss placement: {stop_method}. {assessment.volatility_note}."
        )
        body = " ".join(f"• {reason}" for reason in reasons[:6])
        return f"{head} Contributing factors: {body}"

    @staticmethod
    def _build_invalidation(
        direction: SignalDirection, stop_loss: float, structure: Any
    ) -> str:
        """ساخت شرط ابطال تحلیل."""
        side = "below" if direction == SignalDirection.LONG else "above"
        text = f"A candle close {side} {stop_loss:.6g} invalidates this setup"
        if structure is not None:
            reference = (
                structure.last_swing_low
                if direction == SignalDirection.LONG
                else structure.last_swing_high
            )
            if reference:
                text += f" (structural reference: {reference:.6g})"
        return text + "."

    def _wait_signal(
        self,
        symbol: str,
        frames: list[str],
        *,
        reason: str,
        status: AnalysisStatus,
        notes: list[str] | None = None,
        confidence: int = 0,
        trend: TrendDirection = TrendDirection.NEUTRAL,
        structure: MarketStructureType = MarketStructureType.UNDEFINED,
        votes: dict[str, list[StrategyVote]] | None = None,
        extra_reasons: list[str] | None = None,
    ) -> TradingSignal:
        """
        ساخت سیگنال WAIT.

        WAIT یک شکست نیست؛ یک تصمیم معتبر و اغلب درست است.
        """
        full_reason = reason
        if extra_reasons:
            full_reason += " Observed factors: " + " ".join(f"• {r}" for r in extra_reasons[:5])
        if notes:
            full_reason += " Data notes: " + "; ".join(notes[:3])

        wait = TradingSignal(
            symbol=symbol,
            exchange=self._market.exchange_name,
            direction=SignalDirection.WAIT,
            entry_min=None,
            entry_max=None,
            stop_loss=None,
            take_profits=[],
            risk_reward=None,
            leverage=1,
            confidence=max(0, min(confidence, 100)),
            trend=trend,
            market_structure=structure,
            reason=full_reason,
            invalidation="Re-evaluate when the timeframes align or volatility conditions change.",
            timeframes=list(frames),
            indicators_used=[],
            status=status,
            created_at=datetime.now(UTC),
        )
        self._stamp_validity(wait)
        return wait
