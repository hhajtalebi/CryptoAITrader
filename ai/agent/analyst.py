"""
عامل تحلیل‌گر چند تایم‌فریمی.

چرا وجود دارد؟
    این کلاس، مغز لایه هوش مصنوعی است و چرخه زیر را اجرا می‌کند:

        جمع‌آوری داده واقعی (ابزارها)
              ↓
        ساخت Prompt از قالب نسخه‌بندی‌شده
              ↓
        فراخوانی مدل با زنجیره جایگزینی
              ↓
        اعتبارسنجی خروجی → در صورت نیاز، یک تلاش ترمیم
              ↓
        نتیجه ساختاریافته + فهرست داده‌های استفاده‌شده

    اصل حاکم بر کل کلاس: مدل هرگز داده نمی‌سازد. اگر ابزارها داده کافی
    نداشته باشند، تحلیل با وضعیت INSUFFICIENT_DATA برمی‌گردد و اصلاً به
    مدل فرستاده نمی‌شود.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ai.agent.validator import ResponseValidator, ValidationOutcome
from ai.prompt_budget import compact_json, shrink_market_data, strip_reasoning_block
from ai.prompts import PromptManager
from ai.providers.base import AIMessage
from ai.recommendation import parse_recommendation, strip_recommendation_line
from ai.providers.manager import AIProviderManager
from ai.tools import MarketToolset, ToolResult
from app.core.constants import MIN_CANDLES_FOR_ANALYSIS, AnalysisStatus, Language
from app.core.models import RiskParameters
from app.exceptions import AIError, InsufficientDataError
from app.logging import get_logger

logger = get_logger(__name__)

# دستور زبان خروجی؛ شناسه‌ها انگلیسی می‌مانند ولی متن توضیحی ترجمه می‌شود
LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    Language.FA.value: (
        "Write your explanation in Persian (فارسی). Keep technical terms and all "
        "field names in English, but the narrative must be Persian."
    ),
    Language.EN.value: "Write your explanation in clear, professional English.",
}


@dataclass(slots=True)
class AnalysisRequest:
    """
    درخواست تحلیل.

    تایم‌فریم‌ها به‌ترتیب از بزرگ به کوچک بررسی می‌شوند تا تحلیل از تصویر
    کلان به جزئیات برسد — همان روشی که تحلیل‌گر انسانی به کار می‌برد.
    """

    symbol: str
    timeframes: list[str] = field(default_factory=lambda: ["1d", "4h", "1h", "15m"])
    indicators: list[str] | None = None
    language: str = Language.FA.value
    prompt_name: str = "technical_analysis"
    candle_limit: int = 200
    include_orderbook: bool = True


@dataclass(slots=True)
class AnalysisResult:
    """
    نتیجه یک تحلیل.

    market_data همان داده‌ای است که به مدل داده شد؛ نگه داشتن آن برای
    شفافیت و قابلیت بازبینی تحلیل ضروری است.
    """

    symbol: str
    status: AnalysisStatus
    content: str = ""
    structured: dict[str, Any] = field(default_factory=dict)
    market_data: dict[str, Any] = field(default_factory=dict)
    tools_used: list[str] = field(default_factory=list)
    failed_tools: list[str] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    prompt_version: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    #: توصیهٔ صریح خرید/فروش/انتظار که از آخرین خط پاسخ استخراج شده.
    #: `None` یعنی مدل آن را ننوشت — حدس نمی‌زنیم.
    recommendation: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def succeeded(self) -> bool:
        """آیا تحلیل با موفقیت کامل شد؟"""
        return self.status == AnalysisStatus.OK

    def to_dict(self) -> dict[str, Any]:
        """تبدیل برای ذخیره در پایگاه داده یا گزارش."""
        return {
            "symbol": self.symbol,
            "status": self.status.value,
            "content": self.content,
            "structured": self.structured,
            "recommendation": self.recommendation,
            "tools_used": self.tools_used,
            "failed_tools": self.failed_tools,
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "warnings": self.warnings,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 3),
            "created_at": self.created_at.isoformat(),
        }


class AIAnalyst:
    """
    عامل تحلیل‌گر.

    وابستگی‌ها همگی تزریق می‌شوند تا در تست بتوان آن‌ها را جایگزین کرد
    (اصل وارونگی وابستگی).
    """

    def __init__(
        self,
        provider_manager: AIProviderManager,
        toolset: MarketToolset,
        prompt_manager: PromptManager | None = None,
        validator: ResponseValidator | None = None,
        *,
        risk_parameters: RiskParameters | None = None,
        max_repair_attempts: int = 1,
        preferred_provider: str | None = None,
    ) -> None:
        self._providers = provider_manager
        #: سرویس انتخابی کاربر، تا زنجیره از سرویس‌های خاموش شروع نشود
        self._preferred = preferred_provider
        self._tools = toolset
        self._prompts = prompt_manager or PromptManager()
        self._validator = validator or ResponseValidator()
        self._risk = risk_parameters or RiskParameters()
        self._max_repair_attempts = max(0, int(max_repair_attempts))
        self._validator.set_max_leverage(self._risk.max_leverage)
        self._validator.set_min_risk_reward(self._risk.min_risk_reward)

    def set_risk_parameters(self, parameters: RiskParameters) -> None:
        """هم‌گام‌سازی پارامترهای ریسک در عامل، ابزارها و اعتبارسنج."""
        self._risk = parameters
        self._tools.set_risk_parameters(parameters)
        self._validator.set_max_leverage(parameters.max_leverage)
        self._validator.set_min_risk_reward(parameters.min_risk_reward)

    def _fit_for_model(self, market_data: dict[str, Any], primary: str = "") -> tuple[str, str]:
        """
        آماده‌سازی دادهٔ بازار متناسب با توان مدل فعال.

        چرا اینجا و نه در لایهٔ ارائه‌دهنده؟
            لایهٔ ارائه‌دهنده فقط می‌تواند متن آماده را کور ببرد. اینجا
            هنوز **ساختار** داده را داریم، پس می‌توانیم آگاهانه انتخاب
            کنیم چه چیزی برود و چه چیزی بماند: دفتر سفارش زودتر از
            اندیکاتورها، تایم‌فریم فرعی زودتر از تایم‌فریم اصلی.

        بازگشتی: متن JSON فشرده، و جمله‌ای که به مدل می‌گوید چه چیزی را
        در اختیار ندارد. آن جمله حیاتی است — مدلی که نداند داده‌ای کم
        دارد، جای خالی را با حدس پر می‌کند و همان می‌شود سیگنال
        بی‌اعتماد.
        """
        budget = self._provider_prompt_budget()
        if budget <= 0:
            return compact_json(market_data), ""

        # حدود ۲۵٪ بودجه برای خود قالب، دستورها و بافت ریسک کنار می‌رود.
        data_budget = int(budget * 0.75)
        result = shrink_market_data(
            market_data, budget_tokens=data_budget, primary_timeframe=primary
        )
        if result.dropped:
            logger.info(
                "Market data trimmed for %s to fit the model: %s",
                market_data.get("symbol", ""),
                ", ".join(result.dropped),
            )
        return compact_json(result.data), result.note

    def _provider_prompt_budget(self) -> int:
        """
        بودجهٔ توکن پرامپت برای ارائه‌دهندهٔ فعال.

        فقط مدل‌های محلی سقف سخت‌گیرانه دارند؛ مدل‌های ابری پنجره‌های
        بزرگ دارند و محدودکردنشان یعنی دورانداختن داده بی‌دلیل. اگر
        ارائه‌دهنده این قابلیت را اعلام نکند، صفر برمی‌گردد یعنی
        «محدودیتی نیست».
        """
        try:
            provider = self._providers.active_provider()
        except (AttributeError, TypeError):
            provider = None
        budget_fn = getattr(provider, "prompt_token_budget", None)
        if callable(budget_fn):
            try:
                return int(budget_fn())
            except (TypeError, ValueError):
                return 0
        return 0

    # ------------------------------------------------------------------
    # گردآوری داده
    # ------------------------------------------------------------------
    async def collect_market_data(self, request: AnalysisRequest) -> tuple[dict[str, Any], list[ToolResult]]:
        """
        اجرای ابزارها و ساخت بسته داده واقعی بازار.

        شکست یک ابزار، کل تحلیل را متوقف نمی‌کند؛ فقط در failed_tools ثبت
        می‌شود تا مدل بداند آن بخش از تصویر را ندارد.
        """
        symbol = request.symbol
        indicators = request.indicators or ["RSI", "MACD", "EMA", "SMA", "ATR", "BBANDS", "ADX", "OBV"]

        results: list[ToolResult] = [
            await self._tools.execute("get_ticker", {"symbol": symbol}),
        ]

        data: dict[str, Any] = {
            "symbol": symbol,
            "exchange": self._tools_exchange_name(),
            "collected_at_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "timeframes": {},
        }
        if results[0].ok:
            data["ticker_24h"] = results[0].data

        for index, timeframe in enumerate(request.timeframes):
            frame: dict[str, Any] = {}
            for tool_name, arguments, key in (
                ("get_ohlcv", {"symbol": symbol, "timeframe": timeframe, "limit": request.candle_limit}, "price_action"),
                ("calculate_multiple_indicators", {"symbol": symbol, "indicators": indicators, "timeframe": timeframe}, "indicators"),
                ("detect_market_structure", {"symbol": symbol, "timeframe": timeframe}, "structure"),
                ("find_support_resistance", {"symbol": symbol, "timeframe": timeframe}, "levels"),
                ("get_volume", {"symbol": symbol, "timeframe": timeframe}, "volume"),
            ):
                result = await self._tools.execute(tool_name, arguments)
                results.append(result)
                if result.ok:
                    payload = result.data
                    if key == "price_action" and isinstance(payload, dict):
                        # کندل‌های خام حجیم‌اند؛ فقط خلاصه و ۱۰ کندل آخر می‌رود
                        payload = {
                            "summary": payload.get("summary"),
                            "count": payload.get("count"),
                            "last_candles": payload.get("recent_candles", [])[-10:],
                        }
                    if key == "indicators" and isinstance(payload, dict):
                        payload = payload.get("indicators", payload)
                    frame[key] = payload
            if frame:
                data["timeframes"][timeframe] = frame
            elif index == 0 and not results[0].ok:
                # توقف زودهنگام: نه تیکر آمد و نه هیچ داده‌ای از اولین
                # تایم‌فریم. ادامه دادن یعنی ده‌ها درخواست بی‌فایده به
                # صرافی برای نمادی که وجود ندارد.
                logger.warning(
                    "Aborting data collection for %s: symbol appears to be unavailable", symbol
                )
                data["aborted_reason"] = "symbol_unavailable"
                return data, results

        if request.include_orderbook and data["timeframes"]:
            orderbook = await self._tools.execute("get_orderbook", {"symbol": symbol, "depth": 20})
            results.append(orderbook)
            if orderbook.ok:
                data["orderbook"] = orderbook.data

        return data, results

    def _tools_exchange_name(self) -> str:
        """نام صرافی فعال، برای درج در Prompt و سابقه تحلیل."""
        return getattr(getattr(self._tools, "_market", None), "exchange_name", "unknown")

    # ------------------------------------------------------------------
    # تحلیل متنی
    # ------------------------------------------------------------------
    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """
        اجرای تحلیل تکنیکال متنی چند تایم‌فریمی.
        """
        started = time.perf_counter()
        # وضعیت اولیه FAILED است تا هر مسیر خروج ناقص، به‌اشتباه موفق تلقی نشود
        result = AnalysisResult(symbol=request.symbol, status=AnalysisStatus.FAILED)

        market_data, tool_results = await self.collect_market_data(request)
        result.market_data = market_data
        result.tools_used = [r.tool for r in tool_results if r.ok]
        result.failed_tools = [f"{r.tool}: {r.error}" for r in tool_results if not r.ok]

        if not market_data.get("timeframes"):
            result.status = AnalysisStatus.INSUFFICIENT_DATA
            result.errors.append("INSUFFICIENT_DATA: no timeframe could be analysed")
            result.duration_seconds = time.perf_counter() - started
            logger.warning("Analysis aborted for %s: no usable market data", request.symbol)
            return result

        fitted_data, completeness_note = self._fit_for_model(
            market_data, (request.timeframes or [""])[-1]
        )
        template = self._prompts.get(request.prompt_name)
        prompt = template.render(
            symbol=request.symbol,
            exchange=market_data.get("exchange", ""),
            data_timestamp=market_data.get("collected_at_utc", ""),
            current_price=self._current_price(market_data),
            market_data=fitted_data,
            language_instruction=(
                LANGUAGE_INSTRUCTIONS.get(
                    request.language, LANGUAGE_INSTRUCTIONS[Language.EN.value]
                )
                + ("\n" + completeness_note if completeness_note else "")
            ),
        )
        result.prompt_version = template.identifier

        try:
            response = await self._providers.generate(
                [
                    AIMessage("system", "You are a precise, data-driven crypto technical analyst."),
                    AIMessage("user", prompt),
                ],
                preferred=self._preferred,
            )
        except Exception as exc:  # noqa: BLE001 - شکست مدل نباید برنامه را ببندد
            result.status = AnalysisStatus.FAILED
            result.errors.append(f"{exc.__class__.__name__}: {getattr(exc, 'message', str(exc))}")
            result.duration_seconds = time.perf_counter() - started
            # سطح WARNING است نه ERROR: نبود سرویس هوش مصنوعی یک حالت
            # کاملاً پشتیبانی‌شده است و برنامه بدون آن هم کار می‌کند.
            logger.warning("AI analysis unavailable for %s: %s", request.symbol, exc.__class__.__name__)
            return result

        raw_content = strip_reasoning_block(response.content).strip()

        # توصیه پیش از پاک‌سازی استخراج می‌شود و سپس خط ماشین‌خوان از
        # متنِ نمایشی حذف می‌گردد: کاربر همان اطلاعات را در کارت توصیه
        # با قالب درست می‌بیند و نباید دو بار ببیندش.
        recommendation = parse_recommendation(raw_content)
        if recommendation is not None:
            result.recommendation = recommendation.to_dict()
            result.content = strip_recommendation_line(raw_content)
        else:
            result.content = raw_content
            # نبود توصیه یک نقص کیفی است، نه شکست. تحلیل متنی همچنان
            # ارزش دارد، ولی باید بدانیم کدام مدل‌ها دستور را رعایت
            # نمی‌کنند.
            result.warnings.append("NO_RECOMMENDATION: model omitted the final recommendation line")

        result.provider = response.provider
        result.model = response.model
        result.status = AnalysisStatus.OK
        result.duration_seconds = time.perf_counter() - started
        logger.info(
            "Analysis completed for %s via %s in %.2fs", request.symbol, response.provider, result.duration_seconds
        )
        return result

    # ------------------------------------------------------------------
    # تولید سیگنال ساختاریافته
    # ------------------------------------------------------------------
    async def generate_signal(
        self,
        request: AnalysisRequest,
        *,
        prior_analysis: str = "",
    ) -> AnalysisResult:
        """
        تولید سیگنال Futures با خروجی JSON معتبر.

        در صورت نامعتبر بودن خروجی، خطاها به مدل بازگردانده می‌شوند تا
        حداکثر max_repair_attempts بار آن را اصلاح کند. اگر باز هم معتبر
        نشد، وضعیت FAILED برمی‌گردد — هرگز سیگنال ناقص به کاربر نمی‌رسد.
        """
        started = time.perf_counter()
        # وضعیت اولیه FAILED است تا هر مسیر خروج ناقص، به‌اشتباه موفق تلقی نشود
        result = AnalysisResult(symbol=request.symbol, status=AnalysisStatus.FAILED)

        market_data, tool_results = await self.collect_market_data(request)
        result.market_data = market_data
        result.tools_used = [r.tool for r in tool_results if r.ok]
        result.failed_tools = [f"{r.tool}: {r.error}" for r in tool_results if not r.ok]

        usable = [
            tf for tf, payload in market_data.get("timeframes", {}).items() if payload.get("indicators")
        ]
        if not usable:
            result.status = AnalysisStatus.INSUFFICIENT_DATA
            result.errors.append(
                f"INSUFFICIENT_DATA: fewer than {MIN_CANDLES_FOR_ANALYSIS} candles on every requested timeframe"
            )
            result.duration_seconds = time.perf_counter() - started
            return result

        fitted_data, completeness_note = self._fit_for_model(market_data, usable[-1])
        template = self._prompts.get("futures_signal")
        result.prompt_version = template.identifier
        prompt = template.render(
            symbol=request.symbol,
            exchange=market_data.get("exchange", ""),
            data_timestamp=market_data.get("collected_at_utc", ""),
            current_price=self._current_price(market_data),
            market_data=fitted_data,
            risk_context=json.dumps(self._risk_context(), ensure_ascii=False),
            analysis_context=(
                (prior_analysis or "No prior narrative analysis was provided.")
                + ("\n\n" + completeness_note if completeness_note else "")
            ),
        )

        messages = [
            AIMessage(
                "system",
                "You are a risk-aware futures signal engine. Output only valid JSON, no prose.",
            ),
            AIMessage("user", prompt),
        ]

        outcome: ValidationOutcome | None = None
        for attempt in range(self._max_repair_attempts + 1):
            try:
                response = await self._providers.generate(
                    messages, json_mode=True, temperature=0.2, preferred=self._preferred
                )
            except Exception as exc:  # noqa: BLE001
                result.status = AnalysisStatus.FAILED
                result.errors.append(f"{exc.__class__.__name__}: {getattr(exc, 'message', str(exc))}")
                result.duration_seconds = time.perf_counter() - started
                return result

            result.provider = response.provider
            result.model = response.model
            result.content = response.content.strip()

            outcome = self._validator.validate_signal(response.content, symbol=request.symbol)
            if outcome.valid:
                break

            logger.warning(
                "Invalid signal JSON from %s (attempt %d): %s",
                response.provider,
                attempt + 1,
                outcome.error_text,
            )
            if attempt >= self._max_repair_attempts:
                break

            # تلاش ترمیم: خطاها را به مدل برمی‌گردانیم
            messages = messages[:2] + [
                AIMessage("assistant", response.content),
                AIMessage(
                    "user",
                    "Your JSON was rejected by the validator for these reasons: "
                    f"{outcome.error_text}. Return the corrected JSON only, with no other text.",
                ),
            ]

        if outcome is None or not outcome.valid:
            result.status = AnalysisStatus.FAILED
            result.errors.extend(outcome.errors if outcome else ["No response produced"])
            result.duration_seconds = time.perf_counter() - started
            return result

        result.structured = outcome.data
        result.warnings.extend(outcome.warnings)
        result.status = AnalysisStatus.OK
        result.duration_seconds = time.perf_counter() - started
        logger.info(
            "Signal generated for %s: %s (confidence %s)",
            request.symbol,
            outcome.data.get("signal"),
            outcome.data.get("confidence"),
        )
        return result

    # ------------------------------------------------------------------
    # کمکی‌ها
    # ------------------------------------------------------------------
    @staticmethod
    def _current_price(market_data: dict[str, Any]) -> Any:
        """استخراج آخرین قیمت از بسته داده، بدون حدس زدن."""
        ticker = market_data.get("ticker_24h") or {}
        price = ticker.get("last_price")
        if price:
            return price
        for frame in market_data.get("timeframes", {}).values():
            candles = (frame.get("price_action") or {}).get("last_candles") or []
            if candles:
                return candles[-1].get("close")
        return "UNKNOWN"

    def _risk_context(self) -> dict[str, Any]:
        """قیود ریسک کاربر که مدل موظف به رعایت آن‌هاست."""
        return {
            "max_leverage": self._risk.max_leverage,
            "risk_percent_per_trade": self._risk.risk_percent,
            "min_risk_reward": self._risk.min_risk_reward,
            "note": (
                "Confidence is the alignment of analytical factors, not a probability of profit. "
                "Returning WAIT is preferred over a low-quality setup."
            ),
        }

    async def quick_check(self, symbol: str, timeframe: str = "1h") -> dict[str, Any]:
        """
        بررسی سریع بدون فراخوانی مدل زبانی.

        برای داشبورد استفاده می‌شود تا وضعیت کلی نماد بدون هزینه و تأخیر
        مدل نمایش داده شود.
        """
        trend = await self._tools.execute("detect_trend", {"symbol": symbol, "timeframe": timeframe})
        structure = await self._tools.execute(
            "detect_market_structure", {"symbol": symbol, "timeframe": timeframe}
        )
        indicators = await self._tools.execute(
            "calculate_multiple_indicators",
            {"symbol": symbol, "indicators": ["RSI", "MACD", "ATR"], "timeframe": timeframe},
        )
        if not trend.ok and not structure.ok:
            raise InsufficientDataError(f"Quick check failed for {symbol}: no data available")
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "trend": trend.data.get("trend") if trend.ok else None,
            "structure": structure.data.get("structure") if structure.ok else None,
            "indicators": indicators.data.get("indicators") if indicators.ok else {},
            "ai_used": False,
        }
