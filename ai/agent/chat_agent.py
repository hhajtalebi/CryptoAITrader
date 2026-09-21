"""
دستیار گفتگوی هوش مصنوعی متصل به داده‌های زنده بازار.

چرا وجود دارد؟
    کاربر خواست یک بخش «چت با هوش مصنوعی» داشته باشد که هم بتواند درباره
    بازار حرف بزند و هم واقعاً به داده‌ها دسترسی داشته باشد و بتواند
    کاری انجام دهد. یک چت‌بات بدون داده، فقط حدس می‌زند.

تفاوت با `AutonomousAgent`:
    عامل خودمختار یک وظیفه مشخص دارد (تولید سیگنال برای یک نماد) و خروجی
    ساخت‌یافته می‌دهد. این کلاس یک گفتگوی چندنوبتی است: حافظه دارد، موضوع
    عوض می‌شود، و پاسخش متن طبیعی است — ولی وسط همان گفتگو می‌تواند ابزار
    صدا بزند.

سه توانایی، مطابق درخواست کاربر:
    ۱) گفتگوی آزاد
    ۲) خواندن داده زنده: قیمت، اندیکاتور، کندل، روند، سیگنال‌های ذخیره‌شده
    ۳) اقدام: تولید تحلیل/سیگنال و باز کردن معامله کاغذی

نکته امنیتی مهم: اقدام‌ها هرگز بی‌اجازه اجرا نمی‌شوند. مدل فقط می‌تواند
اقدام را «پیشنهاد» کند؛ اجرای واقعی به تأیید صریح کاربر در رابط کاربری
نیاز دارد. این یعنی یک Prompt Injection در داده بازار نمی‌تواند معامله باز
کند.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from ai.agent.stream_extractor import StreamingAnswerExtractor
from ai.providers.base import AIMessage
from app.core.timeutil import now_utc
from app.exceptions import AIError
from app.logging import get_logger

logger = get_logger(__name__)

#: بیشترین تعداد پیام نگه‌داشته‌شده در حافظه گفتگو (بدون احتساب system)
MAX_HISTORY_MESSAGES = 24

#: بیشترین طول متن یک مشاهده ابزار که به مدل داده می‌شود
MAX_OBSERVATION_CHARS = 2500

#: بیشترین تعداد ابزاری که مدل می‌تواند در یک نوبت پاسخ صدا بزند
MAX_TOOL_CALLS_PER_TURN = 4

#: مهلت پیش‌فرض یک نوبت گفتگو
DEFAULT_CHAT_TIMEOUT = 120.0


SYSTEM_PROMPT = """You are the built-in AI assistant of "Crypto AI Trader", a desktop app for cryptocurrency futures analysis.

You are talking to the app's owner. Always answer in the SAME language the user writes in. If the user writes Persian (فارسی), answer in fluent, natural Persian.

## You are a general assistant, not only a market bot
Talk about ANY topic the user raises — greetings, general questions, explanations, casual conversation. Be warm, natural and helpful. Only reach for market tools when the user actually asks about markets, prices, coins, indicators or trading. Never refuse a normal question by saying you only handle crypto.

## Live market access
When the user DOES ask about markets, you have live access to their exchange data through tools. In that case never invent a price, an indicator value or a market statistic — call a tool and use the real number. If a tool fails, say so plainly.

Available tools:
{tool_list}

## How to reply
Reply with plain, natural text. Write normally, as a person would.

ONLY when you need live market data, reply instead with a single JSON object and nothing else:
{{"thought": "why I need this data", "tools": [{{"name": "get_ticker", "arguments": {{"symbol": "BTC/USDT"}}}}]}}
You may request up to {max_calls} tools at once. After the tool results come back, reply again with plain natural text.

ONLY when you want to offer the user a one-click action, end your reply with a single JSON object on its own final line:
{{"answer": "your reply", "action": {{"type": "generate_signal", "symbol": "BTC/USDT", "timeframe": "4h", "label": "تولید سیگنال برای BTC/USDT"}}}}

Action types you may propose:
  - generate_signal : run the full AI signal agent on a symbol
  - run_analysis    : run technical analysis on a symbol
  - open_paper_trade: open a simulated position from the last signal
  - show_markets    : open the markets page
Never claim an action was performed. You only propose it; the user must click to approve.

## Rules
- Current UTC time: {now}
- User's risk settings: max leverage {max_leverage}x, minimum risk/reward {min_risk_reward}
- WAIT is a legitimate and often correct recommendation. Do not manufacture a trade.
- Confidence means how well the factors agree, NOT a probability of winning.
- Be concise and concrete. Use numbers you actually fetched.
- You are an analysis tool, not a financial advisor. Never promise profit.
"""


@dataclass(slots=True)
class ChatToolCall:
    """یک فراخوانی ابزار در جریان گفتگو."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    ok: bool = False
    observation: str = ""

    def summary(self) -> str:
        """خلاصه یک‌خطی برای نمایش در رابط کاربری."""
        mark = "✓" if self.ok else "✗"
        argument_text = ", ".join(f"{k}={v}" for k, v in self.arguments.items())
        return f"{mark} {self.name}({argument_text})"


@dataclass(slots=True)
class ChatAction:
    """
    اقدام پیشنهادی مدل.

    فقط یک پیشنهاد است؛ تا کاربر روی دکمه کلیک نکند هیچ اتفاقی نمی‌افتد.
    """

    type: str
    label: str = ""
    symbol: str = ""
    timeframe: str = ""

    def to_dict(self) -> dict[str, Any]:
        """تبدیل به دیکشنری برای لایه رابط کاربری."""
        return {
            "type": self.type,
            "label": self.label,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
        }


@dataclass(slots=True)
class ChatReply:
    """
    پاسخ کامل یک نوبت گفتگو.

    هرگز استثنا پرتاب نمی‌شود؛ شکست در `error` می‌نشیند تا رابط کاربری
    بتواند پیام مناسب و ترجمه‌شده نشان دهد.
    """

    text: str = ""
    tool_calls: list[ChatToolCall] = field(default_factory=list)
    action: ChatAction | None = None
    provider: str = ""
    model: str = ""
    elapsed_seconds: float = 0.0
    error: str = ""

    @property
    def succeeded(self) -> bool:
        """آیا پاسخ قابل نمایش تولید شد؟"""
        return bool(self.text.strip()) and not self.error

    @property
    def tools_used(self) -> list[str]:
        """نام ابزارهایی که با موفقیت اجرا شدند."""
        return [call.name for call in self.tool_calls if call.ok]

    def to_dict(self) -> dict[str, Any]:
        """تبدیل به دیکشنری برای ذخیره یا آزمون."""
        return {
            "text": self.text,
            "tools": [call.summary() for call in self.tool_calls],
            "action": self.action.to_dict() if self.action else None,
            "provider": self.provider,
            "model": self.model,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "error": self.error,
        }


class ChatAgent:
    """
    دستیار گفتگوی متصل به بازار.

    نمونه‌سازی:
        chat = ChatAgent(provider_manager, toolset, risk_parameters)
        reply = await chat.send("قیمت بیت‌کوین چنده؟")

    حافظه گفتگو داخل همین شیء نگه داشته می‌شود؛ برای شروع گفتگوی تازه
    `reset()` را صدا بزنید.
    """

    def __init__(
        self,
        provider_manager: Any,
        toolset: Any,
        risk_parameters: Any,
        *,
        max_tool_calls: int = MAX_TOOL_CALLS_PER_TURN,
        timeout_seconds: float = DEFAULT_CHAT_TIMEOUT,
        preferred_provider: str | None = None,
    ) -> None:
        self._providers = provider_manager
        self._tools = toolset
        self._risk = risk_parameters
        self._max_tool_calls = max(1, int(max_tool_calls))
        self._timeout = float(timeout_seconds)
        self._preferred = preferred_provider
        #: تاریخچه گفتگو، بدون پیام system (که هر بار تازه ساخته می‌شود)
        self._history: list[AIMessage] = []
        self._progress: Any = None
        #: مصرف‌کنندهٔ پاسخ جریانی (در صورت ثبت، پاسخ تکه‌تکه می‌رسد)
        self._stream: Any = None

    # ------------------------------------------------------------------
    # پیکربندی
    # ------------------------------------------------------------------
    def set_risk_parameters(self, parameters: Any) -> None:
        """هم‌گام‌سازی با تنظیمات ریسک کاربر."""
        self._risk = parameters
        if hasattr(self._tools, "set_risk_parameters"):
            self._tools.set_risk_parameters(parameters)

    def set_progress_callback(self, callback: Any) -> None:
        """
        ثبت تابعی که هنگام اجرای هر ابزار صدا زده می‌شود.

        رابط کاربری با این، می‌تواند «در حال گرفتن قیمت…» نشان دهد به‌جای
        اینکه کاربر به یک پنجره بی‌حرکت نگاه کند.
        """
        self._progress = callback

    def set_stream_callback(self, callback: Any) -> None:
        """
        ثبت تابعی که با هر تکه از پاسخ در حال تایپ صدا زده می‌شود.

        امضای فراخوان `(delta: str, replace: bool)` است: `replace=True`
        یعنی «هرچه نشان داده‌ای را دور بریز و این را بگذار» که هنگام
        جابه‌جایی به سرویس بعدی لازم می‌شود.

        نبودنش یعنی حالت عادی (بدون جریان) و هیچ‌چیز نمی‌شکند.
        """
        self._stream = callback

    @property
    def streaming_enabled(self) -> bool:
        """آیا مصرف‌کننده‌ای برای جریان ثبت شده است؟"""
        return self._stream is not None

    def _emit(self, call: ChatToolCall, *, running: bool = False) -> None:
        """
        اطلاع‌رسانی امن پیشرفت (خطای رابط کاربری نباید گفتگو را بشکند).

        `running=True` یعنی «این ابزار **تازه شروع شده**» و
        `running=False` یعنی «تمام شد، نتیجه در `call` است». رابط کاربری
        با همین تمایز می‌تواند اول چرخ‌دنده و بعد تیک نشان دهد.

        پس‌فراخوان‌های قدیمی که فقط یک آرگومان می‌گیرند همچنان کار
        می‌کنند؛ اگر امضا `running` را نپذیرد، بدون آن صدا زده می‌شود.
        """
        if self._progress is None:
            return
        try:
            self._progress(call, running=running)
        except TypeError:
            # پس‌فراخوان قدیمی با امضای تک‌آرگومانی
            try:
                if not running:
                    self._progress(call)
            except Exception:  # noqa: BLE001
                logger.debug("Chat progress callback failed", exc_info=True)
        except Exception:  # noqa: BLE001
            logger.debug("Chat progress callback failed", exc_info=True)

    def _emit_stream(self, delta: str, *, replace: bool = False) -> None:
        """ارسال امن یک تکه به رابط کاربری."""
        if self._stream is None:
            return
        try:
            self._stream(delta, replace)
        except Exception:  # noqa: BLE001
            logger.debug("Chat stream callback failed", exc_info=True)

    def reset(self) -> None:
        """پاک کردن حافظه گفتگو و شروع از نو."""
        self._history.clear()
        logger.info("Chat history cleared")

    @property
    def history(self) -> list[AIMessage]:
        """تاریخچه فعلی گفتگو (فقط خواندنی از دید مصرف‌کننده)."""
        return list(self._history)

    @property
    def message_count(self) -> int:
        """تعداد پیام‌های نگه‌داشته‌شده."""
        return len(self._history)

    def _trim_history(self) -> None:
        """
        کوتاه کردن حافظه به آخرین پیام‌ها.

        گفتگوی طولانی هم هزینه توکن دارد و هم مدل‌های کوچک را گیج می‌کند.
        """
        if len(self._history) > MAX_HISTORY_MESSAGES:
            self._history = self._history[-MAX_HISTORY_MESSAGES:]

    # ------------------------------------------------------------------
    # اجرا
    # ------------------------------------------------------------------
    async def send(self, message: str, *, context: dict[str, Any] | None = None) -> ChatReply:
        """
        ارسال یک پیام کاربر و دریافت پاسخ.

        `context` اطلاعات جانبی رابط کاربری است (نماد انتخاب‌شده، تایم‌فریم
        جاری) تا وقتی کاربر می‌گوید «تحلیلش کن» مدل بداند منظور چیست.
        """
        started = time.monotonic()
        reply = ChatReply()

        text = (message or "").strip()
        if not text:
            reply.error = "Empty message"
            return reply

        if not self._providers.has_providers:
            reply.error = "No AI provider is configured"
            return reply

        try:
            await asyncio.wait_for(self._turn(text, context or {}, reply), timeout=self._timeout)
        except TimeoutError:
            reply.error = f"The assistant did not answer within {self._timeout:.0f}s"
            logger.warning("Chat turn timed out")
        except AIError as exc:
            reply.error = getattr(exc, "message", str(exc))
            logger.warning("Chat turn failed: %s", reply.error)
        except Exception as exc:  # noqa: BLE001 - آخرین سد دفاعی
            reply.error = f"{exc.__class__.__name__}: {exc}"
            logger.exception("Unexpected chat failure")

        reply.elapsed_seconds = time.monotonic() - started
        return reply

    async def _generate_round(self, messages: list[AIMessage], round_index: int) -> Any:
        """
        اجرای یک دور از گفتگو با مدل.

        جریان در **همهٔ** دورها فعال است، حتی دور اول.

        نکتهٔ کلیدی: خروجی دور اول ممکن است درخواست ابزار باشد
        (`{"tool": ...}`) نه پاسخ. ولی `StreamingAnswerExtractor` فقط
        مقدار کلید `answer` را بیرون می‌کشد، پس درخواست ابزار به‌طور
        طبیعی نامرئی می‌ماند و چیزی روی صفحه نمی‌افتد.

        تلاش اول این بود که دور اول از جریان محروم شود، ولی چون در
        برنامهٔ واقعی ابزارها همیشه ثبت‌اند، عملاً هیچ پاسخی جریانی
        نمی‌شد — و رایج‌ترین حالت (پرسش ساده‌ای که ابزار نمی‌خواهد) دقیقاً
        همان دور اول است.
        """
        use_stream = self._stream is not None
        if not use_stream:
            return await self._providers.generate(
                messages, preferred=self._preferred, temperature=0.3
            )

        extractor = StreamingAnswerExtractor()

        def on_chunk(chunk: str) -> None:
            """تبدیل تکهٔ خام مدل به متن قابل نمایش."""
            if not chunk:
                # قرارداد بازنشانی مدیر سرویس‌ها: سراغ سرویس بعدی رفتیم
                extractor.reset()
                self._emit_stream("", replace=True)
                return
            delta = extractor.feed(chunk)
            if delta:
                self._emit_stream(delta)

        try:
            return await self._providers.stream(
                messages, on_chunk, preferred=self._preferred, temperature=0.3
            )
        except AIError:
            # جریان شکست خورد؛ صفحه را پاک می‌کنیم تا متن نیمه‌کاره
            # نماند و بگذاریم مسیر عادی خطا را گزارش کند.
            self._emit_stream("", replace=True)
            raise

    async def _turn(self, message: str, context: dict[str, Any], reply: ChatReply) -> None:
        """یک نوبت کامل: شاید چند دور ابزار، سپس یک پاسخ متنی."""
        self._history.append(AIMessage(role="user", content=self._with_context(message, context)))
        self._trim_history()

        # حداکثر دو دور ابزار در هر نوبت: بیشتر از این، گفتگو کند می‌شود
        for round_index in range(3):
            messages = [AIMessage(role="system", content=self._system_prompt())] + self._history
            response = await self._generate_round(messages, round_index)
            reply.provider = response.provider or reply.provider
            reply.model = response.model or reply.model

            payload = self._parse(response.content)

            # مدل JSON نداد: متن خامش را همان پاسخ در نظر می‌گیریم.
            # برای یک چت این کاملاً قابل قبول است و بهتر از خطا دادن.
            if payload is None:
                cleaned = self._strip_fences(response.content).strip()
                if cleaned:
                    reply.text = cleaned
                    self._history.append(AIMessage(role="assistant", content=cleaned))
                    return
                reply.error = "The model returned an empty response"
                return

            # ---- درخواست ابزار ----
            calls = self._extract_calls(payload, context)
            if calls and round_index < 2:
                # مدل به‌جای پاسخ، ابزار خواسته است. اگر در این دور چیزی
                # روی صفحه رفته (مثلاً مدل هم `answer` هم `tool` داده)،
                # باید پاک شود تا با پاسخ نهاییِ دور بعد قاطی نشود.
                self._emit_stream("", replace=True)
                self._history.append(
                    AIMessage(role="assistant", content=json.dumps(payload, ensure_ascii=False))
                )
                observations: list[str] = []
                for call in calls:
                    # اعلام **پیش از** اجرا. پیش‌تر فقط پس از پایان کار
                    # اطلاع داده می‌شد، یعنی دقیقاً در فاصله‌ای که کاربر
                    # منتظر شبکه بود هیچ بازخوردی نمی‌دید و «در حال فکر
                    # کردن…» بی‌حرکت می‌ماند. حالا نام ابزارِ در حال
                    # اجرا بی‌درنگ روی صفحه می‌رود.
                    self._emit(call, running=True)
                    result = await self._tools.execute(call.name, dict(call.arguments))
                    call.ok = bool(getattr(result, "ok", False))
                    call.observation = self._observation(result)
                    reply.tool_calls.append(call)
                    self._emit(call)
                    observations.append(f"[{call.name}]\n{call.observation}")

                self._history.append(
                    AIMessage(
                        role="user",
                        content="Tool results:\n" + "\n\n".join(observations),
                    )
                )
                self._trim_history()
                continue

            # ---- پاسخ نهایی ----
            answer = str(payload.get("answer") or payload.get("text") or "").strip()
            if not answer:
                # مدل JSON داد ولی کلید answer نداشت. اگر متن خامش چیزی
                # برای گفتن دارد، همان را نشان می‌دهیم؛ کاربر نباید فقط
                # چون قالب پاسخ عجیب بوده، دست خالی بماند.
                fallback = self._strip_fences(response.content).strip()
                if fallback and not fallback.startswith("{"):
                    reply.text = fallback
                    self._history.append(AIMessage(role="assistant", content=fallback))
                    return
                if round_index < 2:
                    self._history.append(
                        AIMessage(
                            role="user",
                            content="Reply now in plain natural text, answering the user.",
                        )
                    )
                    continue
                reply.error = "The model did not produce an answer"
                return

            reply.text = answer
            reply.action = self._extract_action(payload, context)
            self._history.append(AIMessage(role="assistant", content=answer))
            self._trim_history()
            return

        reply.error = "The assistant could not complete this turn"

    # ------------------------------------------------------------------
    # ساخت Prompt
    # ------------------------------------------------------------------
    def _system_prompt(self) -> str:
        """ساخت پیام سیستمی با فهرست به‌روز ابزارها."""
        definitions = self._tools.get_definitions()
        tool_list = "\n".join(
            f"  - {d.name}({', '.join(d.parameters.keys())}): {d.description}" for d in definitions
        )
        return SYSTEM_PROMPT.format(
            tool_list=tool_list,
            max_calls=self._max_tool_calls,
            now=now_utc().strftime("%Y-%m-%d %H:%M UTC"),
            max_leverage=getattr(self._risk, "max_leverage", 5),
            min_risk_reward=getattr(self._risk, "min_risk_reward", 1.5),
        )

    #: راهنمای هر حالت گفت‌وگو. حالت فقط لحن و تمرکز را عوض می‌کند؛
    #: هیچ ابزاری محدود نمی‌شود، چون قابلیت نباید پشت حالت قفل شود.
    MODE_HINTS: dict[str, str] = {
        "general": "Answer naturally on any topic.",
        "analysis": (
            "Focus on technical analysis: trend, market structure, key levels "
            "and indicators. Use the tools to fetch real data before judging."
        ),
        "signal": (
            "Focus on an actionable setup: direction, entry zone, stop loss, "
            "targets and risk/reward. Say WAIT when the factors do not align."
        ),
        "learn": (
            "Teach the concept step by step in simple words, with a short "
            "example. Assume the user is learning, not trading right now."
        ),
    }

    @classmethod
    def _with_context(cls, message: str, context: dict[str, Any]) -> str:
        """
        چسباندن وضعیت جاری رابط کاربری به پیام کاربر.

        بدون این، «تحلیلش کن» برای مدل بی‌معناست. «حالت» هم اینجا به
        راهنمای متنی تبدیل می‌شود تا انتخاب کاربر واقعاً روی پاسخ اثر
        بگذارد، نه اینکه فقط یک تراشهٔ تزئینی در رابط کاربری باشد.
        """
        parts = [f"{key}={value}" for key, value in context.items() if value]
        hint = cls.MODE_HINTS.get(str(context.get("mode") or "").strip())
        if not parts:
            return message
        suffix = f"[App context: {', '.join(parts)}]"
        if hint:
            suffix = f"{suffix}\n[Mode guidance: {hint}]"
        return f"{message}\n\n{suffix}"

    # ------------------------------------------------------------------
    # تجزیه پاسخ
    # ------------------------------------------------------------------
    #: بلوک‌های راهنمای داخلی که به مدل داده می‌شوند و نباید در پاسخ
    #: نمایش داده شوند. مدل‌های کوچک‌تر آن‌ها را طوطی‌وار تکرار می‌کنند.
    _INTERNAL_MARKERS = ("[App context:", "[Mode guidance:")

    @classmethod
    def _strip_internal_blocks(cls, text: str) -> str:
        """
        حذف راهنمای داخلی از پاسخی که به کاربر نشان داده می‌شود.

        این بلوک‌ها عمداً به مدل فرستاده می‌شوند تا بداند کاربر روی چه
        نماد و تایم‌فریمی است، ولی دیدنشان در پنجرهٔ چت برای کاربر
        بی‌معنا و زشت است.
        """
        lines = []
        for line in (text or "").splitlines():
            stripped = line.strip()
            if any(stripped.startswith(marker) for marker in cls._INTERNAL_MARKERS):
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    @classmethod
    def _strip_fences(cls, content: str) -> str:
        """حذف ``` و بلوک‌های راهنمای داخلی از دور پاسخ مدل."""
        text = (content or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]
        return cls._strip_internal_blocks(text)

    @classmethod
    def _parse(cls, content: str) -> dict[str, Any] | None:
        """
        استخراج شیء JSON از پاسخ مدل.

        مدل‌های کوچک‌تر گاهی JSON را داخل ``` می‌گذارند یا قبلش توضیح
        می‌نویسند؛ هر دو حالت پذیرفته می‌شود.
        """
        text = cls._strip_fences(content).strip()
        if not text:
            return None

        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except (ValueError, TypeError):
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            return None
        return data if isinstance(data, dict) else None

    def _extract_calls(self, payload: dict[str, Any], context: dict[str, Any]) -> list[ChatToolCall]:
        """
        بیرون کشیدن درخواست‌های ابزار.

        هر دو قالب پشتیبانی می‌شود: `tools` (فهرست) و `tool` (تکی)، چون
        مدل‌های کوچک‌تر معمولاً قالب ساده‌تر را انتخاب می‌کنند.
        """
        raw: list[Any] = []
        if isinstance(payload.get("tools"), list):
            raw = payload["tools"]
        elif payload.get("tool"):
            raw = [{"name": payload.get("tool"), "arguments": payload.get("arguments") or {}}]

        known = set(self._tools.tool_names)
        calls: list[ChatToolCall] = []
        for item in raw[: self._max_tool_calls]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("tool") or "").strip()
            if name not in known:
                continue
            arguments = item.get("arguments")
            if not isinstance(arguments, dict):
                arguments = {}
            # اگر مدل نماد را ننوشت، از نماد انتخاب‌شده در رابط کاربری استفاده کن
            if "symbol" not in arguments and context.get("symbol"):
                arguments["symbol"] = context["symbol"]
            calls.append(ChatToolCall(name=name, arguments=arguments))
        return calls

    @staticmethod
    def _extract_action(payload: dict[str, Any], context: dict[str, Any]) -> ChatAction | None:
        """
        بیرون کشیدن اقدام پیشنهادی.

        فقط انواع شناخته‌شده پذیرفته می‌شوند؛ هر چیز دیگری نادیده گرفته
        می‌شود تا مدل نتواند رفتار تعریف‌نشده بسازد.
        """
        raw = payload.get("action")
        if not isinstance(raw, dict):
            return None
        action_type = str(raw.get("type") or "").strip()
        if action_type not in {"generate_signal", "run_analysis", "open_paper_trade", "show_markets"}:
            return None
        return ChatAction(
            type=action_type,
            label=str(raw.get("label") or "").strip(),
            symbol=str(raw.get("symbol") or context.get("symbol") or "").strip(),
            timeframe=str(raw.get("timeframe") or context.get("timeframe") or "").strip(),
        )

    @staticmethod
    def _observation(result: Any) -> str:
        """تبدیل نتیجه ابزار به متن کوتاه و قابل فهم برای مدل."""
        try:
            payload = result.to_dict()
        except Exception:  # noqa: BLE001
            payload = {"ok": False, "error": "Tool returned an unreadable result"}
        text = json.dumps(payload, ensure_ascii=False, default=str)
        if len(text) > MAX_OBSERVATION_CHARS:
            text = text[:MAX_OBSERVATION_CHARS] + " …(truncated)"
        return text

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    async def health_check(self) -> tuple[bool, str]:
        """بررسی اینکه دست‌کم یک سرویس هوش مصنوعی پاسخ می‌دهد."""
        if not self._providers.has_providers:
            return False, "No AI provider is configured"
        results = await self._providers.check_all()
        for name, (ok, detail) in results.items():
            if ok:
                return True, f"{name}: {detail}"
        if results:
            name, (_, detail) = next(iter(results.items()))
            return False, f"{name}: {detail}"
        return False, "No AI provider is configured"
