"""
عامل خودمختار تحلیل ارز دیجیتال.

تفاوت این عامل با `AIAnalyst`: در آنجا برنامه از پیش تصمیم می‌گرفت چه
داده‌ای جمع شود و مدل فقط آن را تفسیر می‌کرد. اینجا **خود مدل** تصمیم
می‌گیرد: چه تایم‌فریمی را نگاه کند، کدام اندیکاتور را حساب کند، آیا داده
بیشتری لازم دارد، و کی به نتیجه رسیده است.

حلقه کار (الگوی ReAct):

    اندیشیدن  →  فراخوانی ابزار  →  مشاهده نتیجه  →  اندیشیدن دوباره …
                                                    ↓
                                        وقتی مدل کافی دانست: نتیجه نهایی

سه محافظ که این حلقه را از کنترل خارج نشدن نگه می‌دارند:
    ۱. سقف تعداد گام (`max_iterations`) — جلوگیری از حلقه بی‌پایان
    ۲. سقف زمان (`timeout_seconds`) — کاربر منتظر نمی‌ماند
    ۳. اعتبارسنجی خروجی — عدد بی‌معنا هرگز به کاربر نمی‌رسد

مدل هرگز داده نمی‌سازد: تنها راه دسترسی‌اش به بازار، همین ابزارهاست و
اگر داده نباشد موظف است `INSUFFICIENT_DATA` بدهد.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.constants import MIN_CANDLES_FOR_ANALYSIS
from app.core.models import RiskParameters
from app.core.timeutil import now_utc
from app.exceptions import AIError
from app.logging import get_logger
from ai.agent.validator import ResponseValidator
from ai.providers.base import AIMessage
from ai.providers.manager import AIProviderManager
from ai.tools.market_tools import MarketToolset, ToolResult

logger = get_logger(__name__)

#: بیشینه گام‌های اندیشه/ابزار در یک تحلیل
DEFAULT_MAX_ITERATIONS = 8

#: سقف زمان یک تحلیل کامل (ثانیه)
DEFAULT_TIMEOUT = 180.0

#: بیشینه طول متن نتیجه یک ابزار که به مدل داده می‌شود
MAX_OBSERVATION_CHARS = 3500


@dataclass
class AgentStep:
    """یک گام از کار عامل — برای نمایش شفاف مسیر تصمیم‌گیری به کاربر."""

    index: int
    thought: str = ""
    tool: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    observation: str = ""
    ok: bool = True

    def summary(self) -> str:
        """خلاصه یک‌خطی برای نمایش."""
        if self.tool:
            status = "✓" if self.ok else "✗"
            return f"{status} {self.tool}({', '.join(f'{k}={v}' for k, v in self.arguments.items())})"
        return self.thought[:120]


@dataclass
class AgentOutcome:
    """نتیجه کامل یک اجرای عامل."""

    symbol: str
    succeeded: bool = False
    decision: dict[str, Any] = field(default_factory=dict)
    narrative: str = ""
    steps: list[AgentStep] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    elapsed_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def direction(self) -> str:
        """جهت پیشنهادی عامل."""
        return str(self.decision.get("direction", "WAIT")).upper()

    @property
    def confidence(self) -> int:
        """درجه اطمینان (هم‌جهتی عوامل، نه احتمال سود)."""
        try:
            return int(self.decision.get("confidence", 0))
        except (TypeError, ValueError):
            return 0

    def to_dict(self) -> dict[str, Any]:
        """خروجی قابل ذخیره‌سازی."""
        return {
            "symbol": self.symbol,
            "succeeded": self.succeeded,
            "decision": self.decision,
            "narrative": self.narrative,
            "steps": [
                {"index": s.index, "thought": s.thought, "tool": s.tool,
                 "arguments": s.arguments, "ok": s.ok}
                for s in self.steps
            ],
            "tools_used": self.tools_used,
            "provider": self.provider,
            "model": self.model,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "errors": self.errors,
            "warnings": self.warnings,
            "generated_at": now_utc().isoformat(),
        }


SYSTEM_PROMPT = """You are a senior cryptocurrency derivatives analyst with 15+ years of \
professional trading experience across crypto, forex, equities and commodities. Your specialty \
is PERPETUAL FUTURES: funding rates, open interest, liquidation cascades, leverage risk, \
order-book imbalance and volatility regimes. You have traded through multiple bull and bear \
cycles and you have seen every way a "perfect" setup can fail.

You think like a risk manager first and a trader second. Capital preservation outranks being \
right. You are precise, quantitative and blunt: you state what the evidence supports and \
nothing more. You never hedge with vague language, and you never pad an answer to sound \
confident.

You work autonomously: you decide which data to gather, which indicators to compute, and when \
you have enough evidence.

HOW A PROFESSIONAL SIZES CONFIDENCE
Confidence is not enthusiasm. It is the probability that this setup survives contact with the \
market. Anchor it:
  80-92  many independent factors agree across multiple timeframes, structure is clean,
         invalidation is tight and obvious. RARE - a few setups a month.
  60-79  the weight of evidence clearly favours one side, with one or two caveats.
  40-59  a real but conflicted setup; the honest answer is usually WAIT.
  0-39   no edge. Say so.
A confident-sounding number that is not earned is the single most damaging thing you can \
produce: the user trades real money on it.

AVAILABLE TOOLS
{tool_list}

HOW TO RESPOND
Reply with ONE JSON object per turn. Two shapes are allowed.

To use a tool:
{{"thought": "why you need this", "tool": "tool_name", "arguments": {{"symbol": "BTC/USDT"}}}}

To finish:
{{"thought": "your reasoning", "final": {{
  "direction": "LONG" | "SHORT" | "WAIT",
  "confidence": 0-100,
  "entry_min": number|null, "entry_max": number|null,
  "stop_loss": number|null, "take_profits": [number, ...],
  "leverage": integer, "risk_reward": number|null,
  "trend": "BULLISH"|"BEARISH"|"NEUTRAL",
  "market_structure": "UPTREND"|"DOWNTREND"|"RANGING"|"BREAKOUT"|"BREAKDOWN"|"UNDEFINED",
  "timeframes_analysed": ["4h", "1h"],
  "key_levels": {{"support": [numbers], "resistance": [numbers]}},
  "reason": "concise evidence-based explanation",
  "invalidation": "what would prove this wrong",
  "narrative": "2-4 paragraph analysis for the trader"
}}}}

RULES YOU MUST FOLLOW
1. NEVER invent prices, indicator values, or candles. Every number in your final answer must
   come from a tool result. If you did not fetch it, you may not state it.
2. Gather evidence from at least TWO timeframes before deciding. Higher timeframe sets context,
   lower timeframe sets entry.
3. If data is missing or insufficient, return direction "WAIT" and say so in `reason`.
4. "WAIT" is a legitimate, valuable answer when the evidence genuinely conflicts.
   But WAIT is NOT a way to avoid doing the work. If you return WAIT you must cite the
   specific conflicting evidence in `reason`. "Not enough information" is only acceptable
   if your tool calls actually failed.
4b. NEVER return confidence 0 together with a decision you actually reasoned about.
   Confidence 0 means "I have no information at all". If you gathered any evidence,
   state a real confidence between 1 and 100.
5. `confidence` measures how well the factors ALIGN, not the probability of profit.
6. For LONG: stop_loss < entry_min and every take_profit > entry_max.
   For SHORT: stop_loss > entry_max and every take_profit < entry_min.
   Take profits must be ordered away from entry.
7. Respect leverage limits: never exceed {max_leverage}. Recommend the LOWEST leverage that
   makes the setup worthwhile; high leverage converts a normal retrace into a liquidation.
7b. FUTURES-SPECIFIC CHECKS you are expected to reason about when the data is available:
   • Volatility regime: an ATR far above its own average means stops must be wider, not tighter.
   • Order-book imbalance and spread: a wide spread quietly eats a scalp profit.
   • Liquidity: thin books slip badly on exit. A great signal on an illiquid pair is a bad trade.
   • Round numbers and prior swing points attract stop hunts; do not place a stop just beyond
     an obvious level where everyone else has theirs.
   • Say plainly when the market is ranging: most losing futures trades are range trades taken
     as if they were trends.
8. Aim for risk/reward of at least {min_risk_reward}. If the setup cannot reach it, return WAIT.
9. Be efficient: you have at most {max_iterations} tool calls. Do not repeat identical calls.
10. Output ONLY the JSON object. No markdown fences, no commentary around it.

PRE-COMPUTED EVIDENCE
{baseline}

CONTEXT
Symbol: {symbol}
Requested timeframe focus: {timeframe}
Account risk settings: max leverage {max_leverage}, min R/R {min_risk_reward}
Current UTC time: {now}
"""


class AutonomousAgent:
    """
    عامل خودمختاری که خودش تحلیل می‌کند و تصمیم می‌گیرد.

    مثال:
        agent = AutonomousAgent(provider_manager, toolset, risk_parameters)
        outcome = await agent.run("BTC/USDT", timeframe="4h")
        print(outcome.direction, outcome.confidence)
        for step in outcome.steps:
            print(step.summary())
    """

    def __init__(
        self,
        provider_manager: AIProviderManager,
        toolset: MarketToolset,
        risk_parameters: RiskParameters,
        *,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        timeout_seconds: float = DEFAULT_TIMEOUT,
        preferred_provider: str | None = None,
    ) -> None:
        self._providers = provider_manager
        self._tools = toolset
        self._risk = risk_parameters
        self._max_iterations = max(2, int(max_iterations))
        self._timeout = float(timeout_seconds)
        self._preferred = preferred_provider
        self._validator = ResponseValidator(
            max_leverage=risk_parameters.max_leverage,
            min_risk_reward=risk_parameters.min_risk_reward,
        )
        self._progress: Any = None

    def set_risk_parameters(self, parameters: RiskParameters) -> None:
        """به‌روزرسانی پارامترهای ریسک هنگام تغییر تنظیمات کاربر."""
        self._risk = parameters
        self._tools.set_risk_parameters(parameters)
        self._validator = ResponseValidator(
            max_leverage=parameters.max_leverage,
            min_risk_reward=parameters.min_risk_reward,
        )

    def set_progress_callback(self, callback: Any) -> None:
        """
        تعیین تابعی که با هر گام صدا زده می‌شود.

        رابط کاربری از این برای نمایش زنده مسیر تحلیل استفاده می‌کند تا
        کاربر در برابر یک نوار انتظار ساکت ننشیند.
        """
        self._progress = callback

    def _emit(self, step: AgentStep) -> None:
        """اطلاع‌رسانی یک گام به رابط کاربری."""
        if self._progress is None:
            return
        try:
            self._progress(step)
        except Exception:  # noqa: BLE001 - نمایش خراب نباید تحلیل را متوقف کند
            logger.debug("Agent progress callback failed", exc_info=True)

    # ------------------------------------------------------------------
    # اجرا
    # ------------------------------------------------------------------
    async def run(
        self, symbol: str, timeframe: str = "4h", baseline: Any = None
    ) -> AgentOutcome:
        """
        اجرای کامل تحلیل خودمختار روی یک نماد.

        `baseline` سیگنال موتور ریاضی است و اختیاری است. دادنش تفاوت
        بزرگی می‌سازد: بدون آن، مدل باید در چند گام همه‌چیز را از صفر
        کشف کند و مدل‌های کوچک‌تر در این حالت به «انتظار با اطمینان صفر»
        پناه می‌برند. با آن، مدل از یک تحلیل کامل شروع می‌کند و کارش
        قضاوت دربارهٔ آن است، نه بازسازی‌اش.

        هرگز خطا پرتاب نمی‌کند؛ شکست در `outcome.errors` گزارش می‌شود تا
        رابط کاربری بتواند پیام مناسب نشان دهد.
        """
        started = time.monotonic()
        outcome = AgentOutcome(symbol=symbol)

        if not self._providers.has_providers:
            outcome.errors.append("No AI provider is configured")
            return outcome

        try:
            await asyncio.wait_for(
                self._loop(symbol, timeframe, outcome, baseline), timeout=self._timeout
            )
        except TimeoutError:
            outcome.errors.append(f"Analysis exceeded the {self._timeout:.0f}s time limit")
            logger.warning("Agent timed out for %s after %d steps", symbol, len(outcome.steps))
        except AIError as exc:
            outcome.errors.append(getattr(exc, "message", str(exc)))
            logger.warning("Agent failed for %s: %s", symbol, exc)
        except Exception as exc:  # noqa: BLE001 - آخرین سد دفاعی
            outcome.errors.append(f"{exc.__class__.__name__}: {exc}")
            logger.exception("Unexpected agent failure for %s", symbol)

        outcome.elapsed_seconds = time.monotonic() - started

        # اگر عامل به نتیجه نرسید، خروجی امن و صادقانه بده
        if not outcome.succeeded and not outcome.decision:
            outcome.decision = {
                "direction": "WAIT",
                "confidence": 0,
                "reason": outcome.errors[0] if outcome.errors else "The agent reached no conclusion",
                "trend": "NEUTRAL",
                "market_structure": "UNDEFINED",
            }
        return outcome

    async def _loop(
        self, symbol: str, timeframe: str, outcome: AgentOutcome, baseline: Any = None
    ) -> None:
        """حلقه اصلی اندیشه/ابزار."""
        definitions = self._tools.get_definitions()
        tool_list = "\n".join(
            f"  - {d.name}({', '.join(d.parameters.keys())}): {d.description}" for d in definitions
        )
        system = SYSTEM_PROMPT.format(
            tool_list=tool_list,
            symbol=symbol,
            timeframe=timeframe,
            max_leverage=self._risk.max_leverage,
            min_risk_reward=self._risk.min_risk_reward,
            max_iterations=self._max_iterations,
            now=now_utc().strftime("%Y-%m-%d %H:%M UTC"),
            baseline=self._format_baseline(baseline),
        )

        # شواهد پایه **پیش از** شروع حلقه و به‌صورت موازی گرفته می‌شوند.
        #
        # چرا: هر دور حلقه یک رفت‌وبرگشت کامل به مدل است. مدل محلی روی
        # کارت گرافیک ضعیف برای هر پاسخ ده‌ها ثانیه وقت می‌گیرد، پس
        # چهار گامِ ابزار یعنی چند دقیقه انتظار — همان چیزی که کاربر
        # گزارش کرد: «در بخش پویش سریع است ولی در بالای صفحه کار
        # نمی‌کند». پویش سریع است چون اصلاً مدل را صدا نمی‌زند.
        #
        # با آماده‌کردن شواهد، مدل معمولاً در **یک** فراخوانی تصمیم
        # می‌گیرد. ابزارها همچنان در دسترس‌اند اگر چیز بیشتری خواست.
        evidence = await self._preload_evidence(symbol, timeframe)

        user_content = (
            f"Analyse {symbol}. Focus timeframe: {timeframe}. "
            f"Gather the evidence you need, then give your final decision."
        )
        if evidence:
            user_content = (
                f"Analyse {symbol}. Focus timeframe: {timeframe}.\n\n"
                f"MARKET DATA ALREADY FETCHED FOR YOU (all live, from the exchange):\n"
                f"{evidence}\n\n"
                f"This is normally enough to decide. Call a tool ONLY if something "
                f"essential is missing — every tool call costs the user real waiting "
                f"time. Otherwise reply now with your `final` decision."
            )

        messages: list[AIMessage] = [
            AIMessage(role="system", content=system),
            AIMessage(role="user", content=user_content),
        ]

        seen_calls: set[str] = set()
        # مهلت واقعی، نه فقط شمارش گام.
        #
        # سقف گام به‌تنهایی کافی نیست: مدل کند ممکن است با ۳ گام هم از
        # مهلت کل رد شود و کاربر در نهایت «انتظار ۰٪» بگیرد — یعنی چند
        # دقیقه انتظار برای هیچ. با دانستن زمان باقی‌مانده می‌توانیم
        # پیش از سوختن مهلت، مدل را وادار به جمع‌بندی کنیم.
        loop_started = time.monotonic()

        def remaining() -> float:
            """
            ثانیهٔ باقی‌مانده تا پایان مهلت.

            `_timeout` با `getattr` خوانده می‌شود چون `_loop` مستقیماً هم
            صدا زده می‌شود (مثلاً در آزمون‌ها) و نبودِ مهلت نباید تحلیل
            را با استثنا از کار بیندازد.
            """
            budget = float(getattr(self, "_timeout", 0.0) or 0.0)
            if budget <= 0:
                return float("inf")
            return budget - (time.monotonic() - loop_started)

        # میانگین زمان هر فراخوانی، برای تخمین اینکه یک دور دیگر جا می‌شود یا نه.
        call_durations: list[float] = []

        for index in range(1, self._max_iterations + 1):
            call_started = time.monotonic()
            response = await self._providers.generate(
                messages, preferred=self._preferred, temperature=0.2
            )
            call_durations.append(time.monotonic() - call_started)
            outcome.provider = response.provider or outcome.provider
            outcome.model = response.model or outcome.model

            payload = self._parse(response.content)
            if payload is None:
                # مدل JSON نداد: یک بار تذکر می‌دهیم، بار دوم رها می‌کنیم
                step = AgentStep(index=index, thought="(unparseable response)", ok=False)
                step.observation = "Response was not valid JSON"
                outcome.steps.append(step)
                self._emit(step)
                messages.append(AIMessage(role="assistant", content=response.content[:500]))
                messages.append(
                    AIMessage(
                        role="user",
                        content="That was not valid JSON. Reply with ONE JSON object only.",
                    )
                )
                # فقط وقتی تسلیم شو که دو پاسخ **پشت سر هم** بی‌اعتبار باشند؛
                # یک خطای گذرا نباید کل تحلیل را دور بیندازد.
                recent = [s for s in outcome.steps if not s.tool]
                if len(recent) >= 2 and all(
                    s.observation == "Response was not valid JSON" for s in recent[-2:]
                ):
                    outcome.errors.append("The model did not return valid JSON twice in a row")
                    return
                continue

            thought = str(payload.get("thought", "")).strip()

            # ---- مدل به نتیجه رسیده است ----
            if "final" in payload:
                step = AgentStep(index=index, thought=thought, tool="", ok=True)
                outcome.steps.append(step)
                self._emit(step)
                self._finalise(payload["final"], outcome)
                return

            # ---- مدل ابزار می‌خواهد ----
            tool_name = str(payload.get("tool", "")).strip()
            arguments = payload.get("arguments") or {}
            if not isinstance(arguments, dict):
                arguments = {}
            arguments.setdefault("symbol", symbol)

            step = AgentStep(index=index, thought=thought, tool=tool_name, arguments=dict(arguments))

            # فراخوانی تکراری با همان پارامترها هیچ دانش تازه‌ای نمی‌دهد ولی
            # یک گام و یک درخواست شبکه می‌سوزاند — سهمیهٔ رایگان روزانه با
            # همین تکرارها زود تمام می‌شود.
            signature = f"{tool_name}:{json.dumps(arguments, sort_keys=True, default=str)}"
            if signature in seen_calls:
                step.ok = True
                step.observation = (
                    "You already called this tool with these exact arguments. "
                    "Do not repeat it — use the earlier result and move on, or give your final decision."
                )
                outcome.steps.append(step)
                self._emit(step)
                messages.append(
                    AIMessage(role="assistant", content=json.dumps(payload, ensure_ascii=False))
                )
                messages.append(AIMessage(role="user", content=step.observation))
                continue
            seen_calls.add(signature)

            result = await self._tools.execute(tool_name, arguments)
            step.ok = result.ok
            step.observation = self._observation(result)
            outcome.steps.append(step)
            if result.ok and tool_name not in outcome.tools_used:
                outcome.tools_used.append(tool_name)
            self._emit(step)

            messages.append(AIMessage(role="assistant", content=json.dumps(payload, ensure_ascii=False)))
            messages.append(
                AIMessage(
                    role="user",
                    content=f"Tool result for {tool_name}:\n{step.observation}",
                )
            )

            # مهلت رو به پایان: همین حالا جمع‌بندی بخواه.
            #
            # اگر وقت یک رفت‌وبرگشت دیگر نمانده، ادامه‌دادن یعنی تضمینِ
            # «انتظار ۰٪». یک فراخوانی آخر با دستور صریحِ تصمیم، دست‌کم
            # نتیجهٔ قابل استفاده می‌دهد.
            slowest = max(call_durations) if call_durations else 0.0
            if remaining() < slowest * 2.2:
                messages.append(
                    AIMessage(
                        role="user",
                        content=(
                            "TIME IS UP. Do not call any more tools. "
                            "Reply NOW with your `final` decision using the evidence "
                            "you already have. If it is genuinely inconclusive, say "
                            "WAIT and state the specific conflict in `reason`."
                        ),
                    )
                )
                final_response = await self._providers.generate(
                    messages, preferred=self._preferred, temperature=0.2
                )
                final_payload = self._parse(final_response.content)
                if isinstance(final_payload, dict) and final_payload.get("final"):
                    outcome.decision = final_payload["final"]
                    outcome.succeeded = True
                    outcome.provider = final_response.provider or outcome.provider
                    outcome.model = final_response.model or outcome.model
                return

            # نزدیک سقف: مدل را به جمع‌بندی وادار کن
            if index == self._max_iterations - 1:
                messages.append(
                    AIMessage(
                        role="user",
                        content=(
                            "This is your last step. Give your final decision now as JSON with a "
                            "'final' key, using only the data you have already gathered."
                        ),
                    )
                )

        # سقف تمام شد ولی داده‌ها جمع شده‌اند؛ یک درخواست آخر فقط برای
        # جمع‌بندی می‌فرستیم. مدل‌های استدلالی تمام بودجه را صرف فکر کردن
        # می‌کنند و هرگز به JSON نمی‌رسند — این مرحله آن حالت را نجات می‌دهد.
        if await self._force_final(messages, outcome):
            return

        outcome.errors.append("The agent used all its steps without reaching a decision")

    async def _force_final(self, messages: list[AIMessage], outcome: AgentOutcome) -> bool:
        """
        آخرین تلاش برای گرفتن تصمیم نهایی از مدل.

        تمام تاریخچهٔ ابزارها حفظ می‌شود ولی دستور صریح می‌دهیم که فقط JSON
        بنویسد و اصلاً استدلال نکند؛ چون دلیل اصلی شکست، تمام‌شدن توکن‌ها
        وسط زنجیرهٔ فکری است.
        """
        closing = list(messages)
        closing.append(
            AIMessage(
                role="user",
                content=(
                    "STOP analysing. Output ONLY this JSON object and nothing else - no "
                    "reasoning, no explanation, no markdown:\n"
                    '{"thought":"<one short sentence>","final":{"direction":"LONG|SHORT|WAIT",'
                    '"confidence":<0-100>,"entry":<number>,"stop_loss":<number>,'
                    '"take_profits":[<number>],"leverage":<number>,"risk_reward":<number>,'
                    '"trend":"BULLISH|BEARISH|NEUTRAL","market_structure":"<text>",'
                    '"reason":"<why>"}}\n'
                    "The 'reason' field is REQUIRED even for WAIT - explain in one sentence "
                    "why you are not taking a trade.\n"
                    "If the evidence does not support a trade, use direction WAIT."
                ),
            )
        )
        try:
            response = await self._providers.generate(
                closing, preferred=self._preferred, temperature=0.0
            )
        except Exception as exc:  # noqa: BLE001
            outcome.errors.append(f"Final summary request failed: {exc}")
            return False

        payload = self._parse(response.content)
        if not isinstance(payload, dict) or "final" not in payload:
            return False

        step = AgentStep(
            index=len(outcome.steps) + 1,
            thought=str(payload.get("thought", "")).strip(),
            tool="",
            ok=True,
        )
        outcome.steps.append(step)
        self._emit(step)
        self._finalise(payload["final"], outcome)
        return outcome.succeeded

    # ------------------------------------------------------------------
    # کمکی
    # ------------------------------------------------------------------
    @staticmethod
    def _parse(content: str) -> dict[str, Any] | None:
        """
        استخراج شیء JSON از پاسخ مدل.

        مدل‌های کوچک‌تر گاهی JSON را داخل ``` می‌گذارند یا قبلش توضیح
        می‌نویسند؛ هر دو حالت پذیرفته می‌شود.
        """
        text = (content or "").strip()
        if not text:
            return None
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                cleaned = part.strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                if cleaned.startswith("{"):
                    text = cleaned
                    break
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                return parsed

        # مدل‌های استدلالی گاهی وسط JSON بریده می‌شوند؛ آکولادهای باز را
        # می‌بندیم و دوباره تلاش می‌کنیم تا یک پاسخ تقریباً کامل دور نرود.
        if start != -1:
            return AutonomousAgent._repair_json(text[start:])
        return None

    @staticmethod
    def _repair_json(fragment: str) -> dict[str, Any] | None:
        """
        ترمیم JSON ناقصی که به‌خاطر تمام‌شدن توکن‌ها بریده شده است.

        رشتهٔ نیمه‌کاره بسته می‌شود و پرانتزهای باز به ترتیب معکوس بسته
        می‌شوند؛ اگر باز هم نشد، None برمی‌گردد.
        """
        stack: list[str] = []
        in_string = False
        escaped = False
        for char in fragment:
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char in "{[":
                stack.append("}" if char == "{" else "]")
            elif char in "}]" and stack:
                stack.pop()

        closers = "".join(reversed(stack))
        body = fragment
        if in_string:
            # رشتهٔ نیمه‌تمام را نگه می‌داریم چون متن بریده هم معنا دارد
            body += '"'
        else:
            # عدد یا مقدار نیمه‌تمام را دور می‌ریزیم؛ «60» بریده به «6»
            # تبدیل می‌شود و در یک برنامهٔ معاملاتی این فاجعه است.
            body = re.sub(r",\s*(?:\"[^\"]*\"\s*:\s*)?[-+0-9.eE]*$", "", body)
            body = re.sub(r"[:,]\s*$", "", body)

        for _ in range(6):
            try:
                parsed = json.loads(body + closers)
            except json.JSONDecodeError as exc:
                cut = max(exc.pos, 0)
                if cut >= len(body):
                    cut = len(body) - 1
                trimmed = body[:cut].rstrip()
                # تا مرز امن (پایان یک مقدار کامل) عقب برو
                while trimmed and trimmed[-1] not in '}]"0123456789eltrufas':
                    trimmed = trimmed[:-1].rstrip()
                trimmed = re.sub(r",\s*(?:\"[^\"]*\"\s*:\s*)?[-+0-9.eE]*$", "", trimmed)
                trimmed = re.sub(r"[:,]\s*$", "", trimmed)
                if len(trimmed) < 2:
                    return None
                body = trimmed
                continue
            return parsed if isinstance(parsed, dict) else None
        return None

    @staticmethod
    def _observation(result: ToolResult) -> str:
        """
        تبدیل نتیجه ابزار به متنی که به مدل داده می‌شود.

        متن بریده می‌شود تا پنجره متنی مدل با صدها کندل خام پر نشود.
        """
        if not result.ok:
            return f"ERROR: {result.error}"
        try:
            text = json.dumps(result.data, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(result.data)
        if len(text) > MAX_OBSERVATION_CHARS:
            text = text[:MAX_OBSERVATION_CHARS] + " …(truncated)"
        return text

    async def _preload_evidence(self, symbol: str, timeframe: str) -> str:
        """
        گرفتن موازی شواهد پایه پیش از صدا زدن مدل.

        سه ابزارِ همیشه-لازم با هم اجرا می‌شوند (نه پشت سر هم)، پس کل
        کار به اندازهٔ کندترینشان طول می‌کشد نه مجموعشان. خروجی یک متن
        فشرده است که مستقیم داخل پیام کاربر می‌نشیند.

        شکست هر کدام بی‌صداست: شاهدِ ناقص از شاهدِ هیچ بهتر است و مدل
        همچنان می‌تواند خودش ابزار صدا بزند.
        """
        wanted = (
            ("get_ticker", {"symbol": symbol}),
            ("get_multi_timeframe_data", {"symbol": symbol}),
            (
                "calculate_multiple_indicators",
                {"symbol": symbol, "timeframe": timeframe},
            ),
        )

        async def one(name: str, args: dict) -> tuple[str, Any]:
            """اجرای یک ابزار با مهار خطا."""
            try:
                return name, await self._tools.execute(name, args)
            except Exception:  # noqa: BLE001 - شاهد اختیاری است
                logger.debug("Preload tool %s failed", name, exc_info=True)
                return name, None

        results = await asyncio.gather(
            *(one(name, args) for name, args in wanted), return_exceptions=True
        )

        chunks: list[str] = []
        for item in results:
            if isinstance(item, BaseException):
                continue
            name, result = item
            if result is None or not getattr(result, "ok", False):
                continue
            rendered = self._render_tool_data(getattr(result, "data", None))
            if rendered:
                chunks.append(f"### {name}\n{rendered}")

        # هر گام پیش‌بارگذاری‌شده در مسیر تصمیم هم ثبت می‌شود تا کاربر
        # ببیند چه داده‌ای واقعاً گرفته شده است.
        return "\n\n".join(chunks)

    @staticmethod
    def _render_tool_data(data: Any, limit: int = 1400) -> str:
        """
        تبدیل خروجی ابزار به متن کوتاه و خوانا برای مدل.

        سقف طول لازم است: مدل محلی پنجرهٔ متن کوچکی دارد و متن بلند
        باعث می‌شود اول پیام (که دستورها آنجاست) بریده شود.
        """
        if data is None:
            return ""
        try:
            text = json.dumps(data, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(data)
        if len(text) > limit:
            text = text[:limit] + " …(truncated)"
        return text

    @staticmethod
    def _format_baseline(baseline: Any) -> str:
        """
        تبدیل سیگنال موتور ریاضی به متنی که مدل بتواند دربارهٔ آن قضاوت کند.

        نبودِ baseline خطا نیست؛ در آن حالت جملهٔ روشنی می‌گذاریم تا مدل
        نداند «بخش خالی» یعنی چیزی پنهان شده است.
        """
        if baseline is None:
            return (
                "No pre-computed analysis is available. Gather the evidence yourself "
                "with the tools."
            )

        def _get(name: str, default: Any = None) -> Any:
            """خواندن یک مقدار، چه از شیء چه از دیکشنری."""
            if isinstance(baseline, dict):
                return baseline.get(name, default)
            return getattr(baseline, name, default)

        direction = _get("direction", "")
        direction = getattr(direction, "value", direction)
        confidence = _get("confidence", 0)
        reasons = _get("reasons", None) or _get("reason", "") or ""
        if isinstance(reasons, (list, tuple)):
            reasons = "; ".join(str(item) for item in reasons if item)

        lines = [
            "The deterministic signal engine already analysed this symbol using 24 "
            "indicators across the requested timeframes. Its result:",
            f"  direction : {direction}",
            f"  confidence: {confidence} (how well the factors align, 0-100)",
        ]
        for label, key in (
            ("entry_min", "entry_min"),
            ("entry_max", "entry_max"),
            ("stop_loss", "stop_loss"),
            ("take_profits", "take_profits"),
            ("risk_reward", "risk_reward"),
            ("trend", "trend"),
            ("market_structure", "market_structure"),
        ):
            value = _get(key, None)
            # مقادیر شمارشی (`TrendDirection.BULLISH`) باید به متن ساده
            # تبدیل شوند وگرنه مدل نام کلاس پایتون را می‌بیند.
            value = getattr(value, "value", value)
            if value not in (None, "", [], 0):
                lines.append(f"  {label:10}: {value}")
        if reasons:
            lines.append(f"  evidence  : {str(reasons)[:600]}")
        lines.append("")
        lines.append(
            "This is a real, computed analysis - not a guess. Treat it as your starting "
            "point: verify or challenge it with the tools, then give YOUR decision. You "
            "may disagree with it, but if you do, say why. Do not ignore it and return "
            "WAIT with confidence 0."
        )
        return "\n".join(lines)

    @staticmethod
    def _to_validator_schema(final: dict[str, Any]) -> dict[str, Any]:
        """
        نگاشت خروجی مدل به قراردادی که اعتبارسنج می‌شناسد.

        در پرامپت از نام‌های گویاتر (`direction`, `entry_min/entry_max`,
        `take_profits`) استفاده شده چون مدل‌ها با آن‌ها دقیق‌تر جواب
        می‌دهند، ولی اعتبارسنج قرارداد داخلی خودش را دارد. بدون این
        نگاشت، هر پیشنهاد معتبری هم رد می‌شد.
        """
        payload = dict(final)

        if "signal" not in payload and "direction" in payload:
            payload["signal"] = payload["direction"]

        if "entry" not in payload:
            entry_min = payload.get("entry_min")
            entry_max = payload.get("entry_max")
            if entry_min is not None or entry_max is not None:
                payload["entry"] = {"min": entry_min, "max": entry_max}

        if "take_profit" not in payload and "take_profits" in payload:
            payload["take_profit"] = payload["take_profits"]

        # مدل‌ها نام‌های گوناگونی برای «دلیل» می‌گذارند. اگر فقط دنبال
        # کلید `reason` بگردیم، یک تصمیم کاملاً معتبر با پیام
        # «'reason' must explain the decision» رد می‌شود و کاربر می‌بیند
        # «سیگنال با هوش مصنوعی تولید نمی‌شود».
        if not str(payload.get("reason") or "").strip():
            for alias in ("reasoning", "explanation", "analysis", "rationale", "narrative", "summary"):
                candidate = str(payload.get(alias) or "").strip()
                if candidate:
                    payload["reason"] = candidate
                    break

        # همین ماجرا برای حد ضرر: مدل گاهی stopLoss یا stop می‌نویسد
        if "stop_loss" not in payload:
            for alias in ("stopLoss", "stop", "sl"):
                if payload.get(alias) is not None:
                    payload["stop_loss"] = payload[alias]
                    break

        return payload

    @staticmethod
    def _from_validator_schema(data: dict[str, Any]) -> dict[str, Any]:
        """برگرداندن نتیجه اعتبارسنجی به قرارداد یکدست برنامه."""
        decision = dict(data)
        decision["direction"] = decision.get("signal", "WAIT")

        entry = decision.get("entry")
        if isinstance(entry, dict):
            decision["entry_min"] = entry.get("min")
            decision["entry_max"] = entry.get("max")

        if "take_profit" in decision:
            decision["take_profits"] = decision.get("take_profit") or []

        return decision

    def _finalise(self, final: Any, outcome: AgentOutcome) -> None:
        """
        اعتبارسنجی و ثبت تصمیم نهایی.

        خروجی مدل مستقیم پذیرفته نمی‌شود: اهرم، ترتیب اهداف، سمت حد ضرر و
        بازه اطمینان همگی بررسی و در صورت نیاز اصلاح می‌شوند.
        """
        if not isinstance(final, dict):
            outcome.errors.append("The 'final' field was not an object")
            return

        # مدل‌های کوچک‌تر گاهی WAIT را بدون دلیل برمی‌گردانند و اعتبارسنج
        # ردش می‌کند؛ نتیجه برای کاربر «اطمینان ۰٪» بدون هیچ توضیحی است.
        # وقتی خودِ اندیشهٔ مدل در دست است، همان را به‌عنوان دلیل بگذار.
        if not str(final.get("reason") or "").strip():
            fallback_reason = str(
                final.get("narrative")
                or (outcome.steps[-1].thought if outcome.steps else "")
                or ""
            ).strip()
            if fallback_reason:
                final = {**final, "reason": fallback_reason[:300]}

        payload = self._to_validator_schema(final)

        validation = self._validator.validate_signal(
            json.dumps(payload, ensure_ascii=False, default=str)
        )
        if validation.valid and validation.data:
            outcome.decision = self._from_validator_schema(validation.data)
            outcome.succeeded = True
        else:
            # اعتبارسنجی رد کرد: به‌جای دور انداختن، به WAIT امن تبدیل کن
            outcome.decision = {
                **{k: v for k, v in final.items() if k in ("trend", "market_structure", "reason")},
                "direction": "WAIT",
                "confidence": 0,
                "reason": (
                    f"The AI proposal failed validation ({validation.error_text}). "
                    f"Original reasoning: {str(final.get('reason', ''))[:200]}"
                ),
            }
            outcome.errors.append(f"Validation failed: {validation.error_text}")

        outcome.warnings.extend(validation.warnings)
        outcome.narrative = str(final.get("narrative") or final.get("reason") or "").strip()
        if not outcome.decision.get("reason"):
            outcome.decision["reason"] = outcome.narrative[:300] or "No reason provided"

        # داده‌های کمکی که اعتبارسنج نگه نمی‌دارد ولی برای نمایش مفیدند
        for key in ("timeframes_analysed", "key_levels", "invalidation", "trend", "market_structure"):
            if key in final and key not in outcome.decision:
                outcome.decision[key] = final[key]

    # ------------------------------------------------------------------
    # بررسی آمادگی
    # ------------------------------------------------------------------
    async def health_check(self) -> tuple[bool, str]:
        """
        بررسی اینکه عامل واقعاً می‌تواند کار کند.

        در تنظیمات استفاده می‌شود تا کاربر پیش از اولین تحلیل بفهمد
        اتصالش درست است یا نه.
        """
        if not self._providers.has_providers:
            return False, "No AI provider configured"
        results = await self._providers.check_all()
        for name, (ok, message) in results.items():
            if ok:
                return True, f"{name}: {message}"
        details = "; ".join(f"{n}: {m}" for n, (_, m) in results.items())
        return False, details or "No provider responded"

    @staticmethod
    def minimum_candles() -> int:
        """حداقل کندل لازم برای اینکه تحلیل معنا داشته باشد."""
        return MIN_CANDLES_FOR_ANALYSIS
