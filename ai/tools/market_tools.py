"""
جعبه‌ابزار داده بازار برای عامل هوش مصنوعی.

چرا وجود دارد؟
    بند ۱۶ و ۵۳ سند پروژه صراحت دارند: «عامل نباید قیمت را از خودش حدس
    بزند». راه‌حل معماری این است که مدل هیچ داده‌ای در Prompt نداشته باشد
    مگر آنکه از این ابزارها آمده باشد، و هر ابزار مستقیماً به
    MarketDataEngine و IndicatorEngine وصل است.

ویژگی مهم:
    خروجی هر ابزار همیشه شامل «منبع» و «زمان داده» است تا در سابقه تحلیل
    قابل ردیابی باشد.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.constants import MIN_CANDLES_FOR_ANALYSIS
from app.core.models import RiskParameters
from app.exceptions import AppError, InsufficientDataError
from app.logging import get_logger
from indicators.engine import IndicatorEngine
from indicators.support_resistance import (
    analyze_market_structure,
    detect_trend,
    find_support_resistance,
)
from market.engine import MarketDataEngine

logger = get_logger(__name__)


@dataclass(slots=True)
class ToolDefinition:
    """
    توصیف یک ابزار برای معرفی به مدل.

    قالب parameters مطابق JSON Schema است تا با قرارداد Function Calling
    سرویس‌های سازگار با OpenAI هم‌خوانی داشته باشد.
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_openai_schema(self) -> dict[str, Any]:
        """تبدیل به قالب ابزار در API سازگار با OpenAI."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": [
                        key for key, value in self.parameters.items() if value.get("required", False)
                    ],
                },
            },
        }


@dataclass(slots=True)
class ToolResult:
    """
    نتیجه اجرای یک ابزار.

    ok=False یعنی داده در دسترس نبود؛ در این حالت مدل باید صراحتاً اعلام
    کند که داده کافی ندارد، نه اینکه عدد بسازد.
    """

    tool: str
    ok: bool
    data: Any = None
    error: str = ""
    source: str = ""
    fetched_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """تبدیل به دیکشنری برای درج در Prompt یا ثبت در سابقه."""
        payload: dict[str, Any] = {
            "tool": self.tool,
            "ok": self.ok,
            "source": self.source,
            "fetched_at_unix": int(self.fetched_at),
        }
        if self.ok:
            payload["data"] = self.data
        else:
            payload["error"] = self.error
        return payload


class MarketToolset:
    """
    مجموعه ابزارهای در دسترس عامل هوش مصنوعی.

    نمونه‌سازی با تزریق وابستگی:
        toolset = MarketToolset(market_engine, indicator_engine)
        result = await toolset.execute("get_current_price", {"symbol": "BTC/USDT"})
    """

    def __init__(
        self,
        market_engine: MarketDataEngine,
        indicator_engine: IndicatorEngine,
        *,
        risk_parameters: RiskParameters | None = None,
        default_candle_limit: int = 200,
        signal_engine: Any = None,
    ) -> None:
        self._market = market_engine
        self._indicators = indicator_engine
        self._risk = risk_parameters or RiskParameters()
        self._default_limit = default_candle_limit
        # موتور سیگنال به‌عنوان یک ابزار در اختیار مدل.
        #
        # پیش‌تر مدل فقط دادهٔ خام داشت و باید کل تحلیل را خودش
        # بازسازی می‌کرد؛ مدل‌های کوچک از پس آن برنمی‌آمدند و به
        # «انتظار» پناه می‌بردند. حالا می‌تواند نظر موتور ریاضی را
        # بپرسد و دربارهٔ آن قضاوت کند.
        self._signal_engine = signal_engine
        self._handlers: dict[str, Callable[..., Awaitable[Any]]] = {
            "get_current_price": self.get_current_price,
            "get_ticker": self.get_ticker,
            "get_ohlcv": self.get_ohlcv,
            "get_multi_timeframe_data": self.get_multi_timeframe_data,
            "calculate_indicator": self.calculate_indicator,
            "calculate_multiple_indicators": self.calculate_multiple_indicators,
            "get_volume": self.get_volume,
            "get_orderbook": self.get_orderbook,
            "detect_trend": self.detect_trend_tool,
            "detect_market_structure": self.detect_market_structure,
            "find_support_resistance": self.find_support_resistance_tool,
            "calculate_risk": self.calculate_risk,
            "get_engine_signal": self.get_engine_signal,
            "forecast_next_timeframe": self.forecast_next_timeframe,
        }

    async def get_engine_signal(
        self, symbol: str, timeframes: list[str] | None = None
    ) -> dict[str, Any]:
        """
        پرسیدن نظر موتور ریاضی سیگنال دربارهٔ یک نماد.

        این ابزار جای قضاوت مدل را نمی‌گیرد؛ یک نظر دوم است که مدل
        می‌تواند تأیید یا ردش کند — ولی باید دلیل بیاورد.
        """
        if self._signal_engine is None:
            raise RuntimeError("The signal engine is not available to the toolset")
        frames = list(timeframes) if timeframes else ["1h", "4h", "1d"]
        signal = await self._signal_engine.generate(symbol, frames)
        return {
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "confidence": signal.confidence,
            "entry_min": signal.entry_min,
            "entry_max": signal.entry_max,
            "stop_loss": signal.stop_loss,
            "take_profits": list(signal.take_profits or []),
            "risk_reward": signal.risk_reward,
            "leverage": signal.leverage,
            "reason": signal.reason,
            "timeframes": list(signal.timeframes or []),
            "note": (
                "This is the deterministic engine's opinion, not a final answer. "
                "Confidence is capped by how many independent strategies and "
                "timeframes actually agree."
            ),
        }

    async def forecast_next_timeframe(
        self, symbol: str, timeframe: str = "15m"
    ) -> dict[str, Any]:
        """
        برآورد بازهٔ محتمل قیمت برای افق‌های بعدی.

        خروجی عمداً یک بازه است نه یک عدد: پیش‌بینی قیمت دقیق ممکن
        نیست و ادعای آن، گمراه‌کننده است.
        """
        from signals.forecast import forecast_next

        candles = await self._market.get_candles(symbol, timeframe, self._default_limit)
        result = forecast_next(
            symbol=symbol, timeframe=timeframe, candles=candles
        )
        return result.as_dict()

    def set_risk_parameters(self, parameters: RiskParameters) -> None:
        """به‌روزرسانی پارامترهای ریسک از تنظیمات کاربر."""
        self._risk = parameters

    # ------------------------------------------------------------------
    # اجرای ابزار
    # ------------------------------------------------------------------
    @property
    def tool_names(self) -> list[str]:
        """فهرست نام ابزارهای موجود."""
        return sorted(self._handlers)

    async def execute(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        """
        اجرای امن یک ابزار.

        هر خطایی به ToolResult ناموفق تبدیل می‌شود تا زنجیره تحلیل قطع نشود
        و مدل بداند که این داده در دسترس نیست.
        """
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(tool=name, ok=False, error=f"Unknown tool: {name}")

        try:
            data = await handler(**(arguments or {}))
            return ToolResult(
                tool=name, ok=True, data=data, source=f"{self._market.exchange_name}:live"
            )
        except InsufficientDataError as exc:
            logger.info("Tool %s reported insufficient data: %s", name, exc.message)
            return ToolResult(tool=name, ok=False, error=f"INSUFFICIENT_DATA: {exc.message}")
        except AppError as exc:
            logger.warning("Tool %s failed: %s", name, exc.message)
            return ToolResult(tool=name, ok=False, error=f"{exc.__class__.__name__}: {exc.message}")
        except TypeError as exc:
            return ToolResult(tool=name, ok=False, error=f"Invalid arguments for {name}: {exc}")
        except Exception as exc:  # noqa: BLE001 - ابزار نباید کل تحلیل را از بین ببرد
            logger.exception("Unexpected error in tool %s", name)
            return ToolResult(tool=name, ok=False, error=f"{exc.__class__.__name__}")

    # ------------------------------------------------------------------
    # ابزارهای قیمت
    # ------------------------------------------------------------------
    async def get_current_price(self, symbol: str) -> dict[str, Any]:
        """قیمت لحظه‌ای یک نماد از موتور داده بازار."""
        price = await self._market.get_current_price(symbol)
        return {"symbol": symbol, "price": price, "exchange": self._market.exchange_name}

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        """وضعیت ۲۴ ساعته یک نماد."""
        ticker = await self._market.get_ticker(symbol)
        return ticker.to_dict()

    async def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> dict[str, Any]:
        """
        دریافت کندل‌ها.

        برای پرهیز از پر شدن Context مدل، فقط ۳۰ کندل آخر به‌صورت کامل و
        بقیه به‌صورت خلاصه آماری برگردانده می‌شوند.
        """
        candles = await self._market.get_candles(symbol, timeframe, min(int(limit), 500))
        if not candles:
            raise InsufficientDataError(f"No candles for {symbol} {timeframe}")

        closes = [c.close for c in candles]
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(candles),
            "first_candle_time": candles[0].timestamp,
            "last_candle_time": candles[-1].timestamp,
            "summary": {
                "highest": max(c.high for c in candles),
                "lowest": min(c.low for c in candles),
                "first_close": closes[0],
                "last_close": closes[-1],
                "change_percent": round((closes[-1] - closes[0]) / closes[0] * 100, 3) if closes[0] else 0.0,
                "total_volume": round(sum(c.volume for c in candles), 4),
            },
            "recent_candles": [c.to_dict() for c in candles[-30:]],
        }

    async def get_multi_timeframe_data(
        self, symbol: str, timeframes: list[str] | None = None, limit: int = 200
    ) -> dict[str, Any]:
        """
        دریافت خلاصه چند تایم‌فریم به‌صورت هم‌زمان.

        این ابزار پرکاربردترین ورودی تحلیل چند تایم‌فریمی است.
        """
        frames = timeframes or ["15m", "1h", "4h", "12h", "1d"]
        candles_by_tf = await self._market.get_multi_timeframe_candles(symbol, frames, limit)

        result: dict[str, Any] = {"symbol": symbol, "timeframes": {}, "missing": []}
        for timeframe, candles in candles_by_tf.items():
            if len(candles) < MIN_CANDLES_FOR_ANALYSIS:
                result["missing"].append(timeframe)
                continue
            closes = [c.close for c in candles]
            result["timeframes"][timeframe] = {
                "count": len(candles),
                "last_candle_time": candles[-1].timestamp,
                "last_close": closes[-1],
                "highest": max(c.high for c in candles),
                "lowest": min(c.low for c in candles),
                "change_percent": round((closes[-1] - closes[0]) / closes[0] * 100, 3) if closes[0] else 0.0,
                "trend": detect_trend(candles).value,
            }
        return result

    # ------------------------------------------------------------------
    # ابزارهای اندیکاتور
    # ------------------------------------------------------------------
    async def calculate_indicator(
        self, symbol: str, indicator: str, timeframe: str = "1h", limit: int = 200, **parameters: Any
    ) -> dict[str, Any]:
        """محاسبه یک اندیکاتور روی داده واقعی بازار."""
        candles = await self._market.get_candles(symbol, timeframe, int(limit))
        result = self._indicators.calculate(
            indicator, candles, timeframe, symbol=symbol, **parameters
        )
        return result.to_summary()

    async def calculate_multiple_indicators(
        self, symbol: str, indicators: list[str] | None = None, timeframe: str = "1h", limit: int = 200
    ) -> dict[str, Any]:
        """محاسبه چند اندیکاتور در یک فراخوانی."""
        names = indicators or ["RSI", "MACD", "EMA", "ATR", "BBANDS", "ADX"]
        candles = await self._market.get_candles(symbol, timeframe, int(limit))
        results = self._indicators.calculate_many(names, candles, timeframe, symbol=symbol)
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "candles_used": len(candles),
            "indicators": {name: result.to_summary() for name, result in results.items()},
            "unavailable": [name.upper() for name in names if name.upper() not in results],
        }

    async def get_volume(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> dict[str, Any]:
        """
        تحلیل حجم: میانگین، حجم فعلی، نسبت و روند حجم.
        """
        candles = await self._market.get_candles(symbol, timeframe, int(limit))
        if len(candles) < 20:
            raise InsufficientDataError(f"Not enough candles to analyse volume for {symbol}")

        volumes = [c.volume for c in candles]
        recent_average = sum(volumes[-20:]) / 20
        previous_average = sum(volumes[-40:-20]) / 20 if len(volumes) >= 40 else recent_average
        current = volumes[-1]
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_volume": round(current, 4),
            "average_volume_20": round(recent_average, 4),
            "volume_ratio": round(current / recent_average, 3) if recent_average else 0.0,
            "volume_trend": (
                "INCREASING" if recent_average > previous_average * 1.1
                else "DECREASING" if recent_average < previous_average * 0.9
                else "STABLE"
            ),
            "spike": bool(recent_average and current >= recent_average * 2),
        }

    async def get_orderbook(self, symbol: str, depth: int = 20) -> dict[str, Any]:
        """
        دفتر سفارش به‌همراه سنجه عدم توازن خرید/فروش.

        imbalance مثبت یعنی حجم خرید بیشتر است.
        """
        orderbook = await self._market.get_orderbook(symbol, int(depth))
        bid_volume = sum(level.quantity for level in orderbook.bids)
        ask_volume = sum(level.quantity for level in orderbook.asks)
        total = bid_volume + ask_volume
        return {
            "symbol": symbol,
            "best_bid": orderbook.best_bid,
            "best_ask": orderbook.best_ask,
            "spread": orderbook.spread,
            "spread_percent": (
                round(orderbook.spread / orderbook.best_ask * 100, 5)
                if orderbook.spread is not None and orderbook.best_ask
                else None
            ),
            "bid_volume": round(bid_volume, 4),
            "ask_volume": round(ask_volume, 4),
            "imbalance": round((bid_volume - ask_volume) / total, 4) if total else 0.0,
            "timestamp": orderbook.timestamp,
        }

    # ------------------------------------------------------------------
    # ابزارهای ساختار بازار
    # ------------------------------------------------------------------
    async def detect_trend_tool(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> dict[str, Any]:
        """تشخیص جهت روند در یک تایم‌فریم."""
        candles = await self._market.get_candles(symbol, timeframe, int(limit))
        trend = detect_trend(candles)
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "trend": trend.value,
            "candles_used": len(candles),
            "last_close": candles[-1].close if candles else None,
        }

    async def detect_market_structure(
        self, symbol: str, timeframe: str = "1h", limit: int = 200
    ) -> dict[str, Any]:
        """تحلیل ساختار بازار (توالی سقف‌ها و کف‌ها)."""
        candles = await self._market.get_candles(symbol, timeframe, int(limit))
        structure = analyze_market_structure(candles, timeframe)
        payload = structure.to_dict()
        payload["symbol"] = symbol
        return payload

    async def find_support_resistance_tool(
        self, symbol: str, timeframe: str = "1h", limit: int = 200, max_levels: int = 8
    ) -> dict[str, Any]:
        """یافتن سطوح کلیدی حمایت و مقاومت."""
        candles = await self._market.get_candles(symbol, timeframe, int(limit))
        levels = find_support_resistance(candles, max_levels=int(max_levels))
        if not levels:
            raise InsufficientDataError(f"No support/resistance levels found for {symbol} {timeframe}")
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": candles[-1].close,
            "levels": [
                {
                    "price": round(level.price, 8),
                    "type": level.kind,
                    "strength": level.strength,
                    "distance_percent": round(level.distance_percent, 3),
                }
                for level in levels
            ],
        }

    # ------------------------------------------------------------------
    # ابزار ریسک
    # ------------------------------------------------------------------
    async def calculate_risk(
        self,
        symbol: str,
        entry: float,
        stop_loss: float,
        take_profit: float | None = None,
        timeframe: str = "1h",
    ) -> dict[str, Any]:
        """
        محاسبه سنجه‌های ریسک یک ستاپ پیشنهادی.

        این ابزار عمداً «محاسبه‌گر» است نه «تصمیم‌گیر»: تصمیم نهایی درباره
        پذیرش یا رد ستاپ با موتور ریسک است که قواعد سخت‌گیرانه‌تری دارد.
        """
        entry_price = float(entry)
        stop_price = float(stop_loss)
        if entry_price <= 0 or stop_price <= 0:
            raise InsufficientDataError("Entry and stop loss must be positive numbers")
        if entry_price == stop_price:
            raise InsufficientDataError("Entry and stop loss cannot be equal")

        stop_distance = abs(entry_price - stop_price)
        stop_distance_percent = stop_distance / entry_price * 100
        risk_amount = self._risk.account_balance * (self._risk.risk_percent / 100)
        position_size = risk_amount / stop_distance if stop_distance else 0.0

        payload: dict[str, Any] = {
            "symbol": symbol,
            "entry": entry_price,
            "stop_loss": stop_price,
            "direction": "LONG" if stop_price < entry_price else "SHORT",
            "stop_distance": round(stop_distance, 8),
            "stop_distance_percent": round(stop_distance_percent, 3),
            "risk_amount": round(risk_amount, 4),
            "position_size": round(position_size, 8),
            "max_allowed_leverage": self._risk.max_leverage,
            "min_required_risk_reward": self._risk.min_risk_reward,
        }

        if take_profit is not None:
            reward = abs(float(take_profit) - entry_price)
            payload["take_profit"] = float(take_profit)
            payload["risk_reward"] = round(reward / stop_distance, 3) if stop_distance else None
            payload["meets_min_rr"] = bool(
                stop_distance and (reward / stop_distance) >= self._risk.min_risk_reward
            )

        # افزودن ATR واقعی برای سنجش منطقی بودن فاصله حد ضرر
        try:
            candles = await self._market.get_candles(symbol, timeframe, 100)
            atr_result = self._indicators.calculate("ATR", candles, timeframe, symbol=symbol)
            atr_value = atr_result.latest.get("atr")
            if atr_value:
                payload["atr"] = round(atr_value, 8)
                payload["stop_distance_in_atr"] = round(stop_distance / atr_value, 3)
                payload["stop_is_too_tight"] = stop_distance < atr_value
        except AppError:
            payload["atr"] = None
        return payload

    # ------------------------------------------------------------------
    # تعریف ابزارها برای مدل
    # ------------------------------------------------------------------
    @staticmethod
    def get_definitions() -> list[ToolDefinition]:
        """
        فهرست توصیف ابزارها جهت معرفی به مدل‌هایی که Function Calling دارند.
        """
        symbol_param = {"type": "string", "description": "Trading pair, e.g. BTC/USDT", "required": True}
        timeframe_param = {
            "type": "string",
            "description": "Timeframe code: 1m, 5m, 15m, 30m, 1h, 4h, 12h, 1d, 1w",
        }
        return [
            ToolDefinition("get_current_price", "Get the live price of a symbol.", {"symbol": symbol_param}),
            ToolDefinition("get_ticker", "Get 24h statistics of a symbol.", {"symbol": symbol_param}),
            ToolDefinition(
                "get_ohlcv",
                "Get candlestick data with a statistical summary.",
                {"symbol": symbol_param, "timeframe": timeframe_param, "limit": {"type": "integer"}},
            ),
            ToolDefinition(
                "get_multi_timeframe_data",
                "Get summarised data across several timeframes at once.",
                {"symbol": symbol_param, "timeframes": {"type": "array", "items": {"type": "string"}}},
            ),
            ToolDefinition(
                "get_engine_signal",
                "Ask the deterministic signal engine for its opinion on a symbol. "
                "Returns direction, evidence-capped confidence, entry, stop and targets. "
                "Use it as a second opinion you may agree with or argue against.",
                {
                    "symbol": symbol_param,
                    "timeframes": {"type": "array", "items": {"type": "string"}},
                },
            ),
            ToolDefinition(
                "forecast_next_timeframe",
                "Estimate the probable price RANGE for the next horizons "
                "(e.g. from 15m data: the next 15m, 1h and 4h). Returns lower/upper "
                "bounds derived from measured volatility, never a single price.",
                {"symbol": symbol_param, "timeframe": timeframe_param},
            ),
            ToolDefinition(
                "calculate_indicator",
                "Calculate one technical indicator on real market data.",
                {
                    "symbol": symbol_param,
                    "indicator": {"type": "string", "description": "e.g. RSI, MACD, ATR", "required": True},
                    "timeframe": timeframe_param,
                },
            ),
            ToolDefinition(
                "calculate_multiple_indicators",
                "Calculate several indicators in one call.",
                {
                    "symbol": symbol_param,
                    "indicators": {"type": "array", "items": {"type": "string"}},
                    "timeframe": timeframe_param,
                },
            ),
            ToolDefinition(
                "get_volume", "Analyse volume behaviour.", {"symbol": symbol_param, "timeframe": timeframe_param}
            ),
            ToolDefinition(
                "get_orderbook",
                "Get order book depth and bid/ask imbalance.",
                {"symbol": symbol_param, "depth": {"type": "integer"}},
            ),
            ToolDefinition(
                "detect_trend", "Detect trend direction.", {"symbol": symbol_param, "timeframe": timeframe_param}
            ),
            ToolDefinition(
                "detect_market_structure",
                "Analyse HH/HL/LH/LL market structure.",
                {"symbol": symbol_param, "timeframe": timeframe_param},
            ),
            ToolDefinition(
                "find_support_resistance",
                "Find key support and resistance levels.",
                {"symbol": symbol_param, "timeframe": timeframe_param},
            ),
            ToolDefinition(
                "calculate_risk",
                "Compute risk metrics for a proposed setup.",
                {
                    "symbol": symbol_param,
                    "entry": {"type": "number", "required": True},
                    "stop_loss": {"type": "number", "required": True},
                    "take_profit": {"type": "number"},
                },
            ),
        ]
