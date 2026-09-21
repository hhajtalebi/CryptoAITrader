"""
ارائه‌دهنده سازگار با API استاندارد OpenAI.

چرا مهم است؟
    اکثر سرویس‌های امروزی (از جمله بسیاری از سرویس‌های دارای طرح رایگان و
    سرورهای محلی) همین قرارداد /v1/chat/completions را پیاده‌سازی می‌کنند.
    بنابراین با یک کلاس، طیف وسیعی از ارائه‌دهندگان پشتیبانی می‌شوند و کاربر
    فقط باید Base URL و نام مدل را وارد کند.

سه سازگاری که در این نسخه اضافه شده و بدون آن‌ها مدل‌های جدید کار نمی‌کردند:

۱) مدل‌های نسل جدید OpenAI (خانواده gpt-5، o1، o3، o4) پارامتر `max_tokens`
   را رد می‌کنند و `max_completion_tokens` می‌خواهند.
۲) همان مدل‌ها فقط `temperature = 1` را می‌پذیرند.
۳) پیام خطای واقعی سرویس باید به کاربر نشان داده شود. قبلاً همه چیز به
   «HTTP 429» تبدیل می‌شد؛ در حالی که تفاوت «اعتبار تمام شده» با «سرعت
   درخواست زیاد است» برای کاربر حیاتی است.

هشدار امنیتی: کلید فقط در سرآیند Authorization ارسال می‌شود و هرگز لاگ
نمی‌گردد؛ فیلتر لاگ نیز هرگونه نشت احتمالی را پنهان می‌کند.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any

import httpx

from ai.providers.base import AIMessage, AIProvider, AIProviderConfig, AIResponse
from app.exceptions import AIProviderError, AuthenticationError, TimeoutErrorApp
from app.logging import get_logger

from ai.providers.ranking import sort_models

logger = get_logger(__name__)

#: نشانهٔ داخلی «جریان تمام شد» (خط `data: [DONE]`). شیء یکتا است تا با
#: هیچ مقدار واقعیِ پاسخ اشتباه گرفته نشود.
_STREAM_DONE = object()

#: الگوی مدل‌هایی که پارامترهای قدیمی را نمی‌پذیرند
RESTRICTED_MODEL_PATTERN = re.compile(r"^(o[1-9]|gpt-[5-9]|gpt-\d{2})", re.IGNORECASE)


def uses_completion_tokens(model: str) -> bool:
    """
    آیا این مدل به‌جای max_tokens پارامتر max_completion_tokens می‌خواهد؟

    تشخیص بر پایه نام است چون سرویس راه دیگری برای پرسیدن نمی‌دهد؛ ولی اگر
    حدس اشتباه باشد، منطق تلاش دوباره در `generate` آن را جبران می‌کند.
    """
    name = (model or "").split("/")[-1]
    return bool(RESTRICTED_MODEL_PATTERN.match(name))


class OpenAICompatibleProvider(AIProvider):
    """
    کلاینت سرویس‌های سازگار با OpenAI.

    مسیرهای استفاده‌شده:
        POST {base_url}/chat/completions
        GET  {base_url}/models
    """

    provider_type = "openai_compatible"

    def __init__(self, config: AIProviderConfig, api_key: str | None = None) -> None:
        super().__init__(config, api_key)
        self._client: httpx.AsyncClient | None = None
        #: پارامترهایی که این سرویس/مدل نپذیرفته و نباید دوباره ارسال شوند
        self._rejected_params: set[str] = set()

    async def _get_client(self) -> httpx.AsyncClient:
        """ساخت یا استفاده مجدد از کلاینت HTTP."""
        base_url = (self._config.base_url or "").rstrip("/")
        if self._client is None or self._client.is_closed or str(self._client.base_url).rstrip("/") != base_url:
            if self._client is not None and not self._client.is_closed:
                await self._client.aclose()
            # سرویس محلی یا در دسترس است یا نیست؛ ۱۵ ثانیه انتظار برای
            # اتصال به 127.0.0.1 فقط کاربر را معطل می‌کند. سرویس ابری
            # ممکن است کند باشد، پس مهلت آن دست‌نخورده می‌ماند.
            connect_timeout = 2.0 if self._is_local(base_url) else 15.0
            self._client = httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(self._config.timeout, connect=connect_timeout),
                follow_redirects=True,
            )
        return self._client

    @staticmethod
    def _is_local(base_url: str) -> bool:
        """آیا نشانی به سرویسی روی همین دستگاه اشاره می‌کند."""
        lowered = (base_url or "").lower()
        return any(
            host in lowered
            for host in ("127.0.0.1", "localhost", "::1", "0.0.0.0")
        )

    def _headers(self) -> dict[str, str]:
        """ساخت سرآیندها؛ کلید فقط در صورت وجود اضافه می‌شود."""
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        # OpenRouter این دو سرآیند را برای شناسایی برنامه توصیه می‌کند و
        # نبودشان روی برخی مدل‌های رایگان باعث محدودیت می‌شود.
        if "openrouter.ai" in (self._config.base_url or ""):
            headers["HTTP-Referer"] = "https://github.com/crypto-ai-trader"
            headers["X-Title"] = "Crypto AI Trader"
        return headers

    def update_config(self, config: AIProviderConfig) -> None:
        """با تغییر مدل، حافظه پارامترهای ردشده باید پاک شود."""
        super().update_config(config)
        self._rejected_params.clear()

    # ------------------------------------------------------------------
    # خطاها
    # ------------------------------------------------------------------
    @staticmethod
    def _error_text(response: httpx.Response) -> str:
        """
        بیرون کشیدن پیام خطای واقعی از بدنه پاسخ.

        بدون این، کاربر فقط یک کد HTTP می‌دید و نمی‌فهمید مشکل از کلید است،
        از اعتبار، یا از نام مدل.
        """
        try:
            payload = response.json()
        except ValueError:
            return (response.text or "").strip()[:300]

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = str(error.get("message") or "").strip()
                code = str(error.get("code") or "").strip()
                if message:
                    return f"{message} ({code})" if code and code not in message else message
            if isinstance(error, str) and error.strip():
                return error.strip()
            for key in ("message", "detail"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return (response.text or "").strip()[:300]

    def _raise_for_status(self, response: httpx.Response) -> None:
        """تبدیل پاسخ ناموفق به خطای معنادار برنامه."""
        if response.status_code < 400:
            return

        detail = self._error_text(response)
        lowered = detail.lower()

        if response.status_code in (401, 403):
            raise AuthenticationError(
                f"Authentication failed for provider '{self.name}': {detail}",
                details={"provider": self.name, "status": response.status_code},
            )
        # سقف روزانهٔ مدل‌های رایگان: پیام OpenRouter واژهٔ «credits» دارد و
        # به‌اشتباه «اعتبار تمام شد» تفسیر می‌شد، در حالی‌که این سهمیه
        # فردا خودش برمی‌گردد و کاربر لازم نیست چیزی بخرد.
        if "per-day" in lowered or "per day" in lowered or "daily" in lowered:
            raise AIProviderError(
                f"Daily free-tier quota reached for provider '{self.name}'. "
                f"It resets automatically; add credit or pick another provider to continue now: {detail}",
                details={
                    "provider": self.name,
                    "reason": "daily_quota",
                    "status": response.status_code,
                },
            )
        # اعتبار تمام‌شده گاهی 429 و گاهی 402 برمی‌گردد؛ پیام آن با
        # محدودیت سرعت فرق دارد و کاربر باید تفاوت را ببیند.
        if response.status_code == 402 or "quota" in lowered or "credit" in lowered or "billing" in lowered:
            raise AIProviderError(
                f"Provider '{self.name}' has no remaining credit: {detail}",
                details={"provider": self.name, "reason": "insufficient_quota", "status": response.status_code},
            )
        if response.status_code == 429:
            raise AIProviderError(
                f"Rate limit reached for provider '{self.name}': {detail}",
                details={"provider": self.name, "reason": "rate_limit"},
            )
        if response.status_code == 404 or "model" in lowered and "not" in lowered:
            raise AIProviderError(
                f"Model '{self._config.model}' is not available on provider '{self.name}': {detail}",
                details={"provider": self.name, "model": self._config.model, "reason": "model_not_found"},
            )
        raise AIProviderError(
            f"Provider '{self.name}' returned HTTP {response.status_code}: {detail}",
            details={"provider": self.name, "status": response.status_code},
        )

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    async def is_available(self) -> tuple[bool, str]:
        """
        بررسی دسترسی با فراخوانی فهرست مدل‌ها.

        این سبک‌ترین درخواست ممکن است و معمولاً هزینه‌ای ندارد. توجه: پاسخ
        موفق یعنی «کلید معتبر است»، نه لزوماً «اعتبار مالی دارید» — آن مورد
        فقط هنگام تولید واقعی معلوم می‌شود.
        """
        if not (self._config.base_url or "").strip():
            return False, "Base URL is not configured"
        if self._config.requires_api_key and not self._api_key:
            return False, "API key is not configured"
        try:
            client = await self._get_client()
            response = await client.get("/models", headers=self._headers(), timeout=20.0)
            if response.status_code in (401, 403):
                return False, f"Authentication failed: {self._error_text(response)}"
            if response.status_code >= 400:
                return False, f"HTTP {response.status_code}: {self._error_text(response)}"
            return True, "Service is reachable"
        except httpx.TimeoutException:
            return False, "Connection timed out"
        except httpx.HTTPError as exc:
            return False, f"Connection error: {exc.__class__.__name__}"

    # ------------------------------------------------------------------
    # تولید پاسخ
    # ------------------------------------------------------------------
    def _build_payload(self, messages: list[AIMessage], json_mode: bool, temperature: float | None) -> dict[str, Any]:
        """ساخت بدنه درخواست با رعایت محدودیت‌های شناخته‌شده مدل."""
        model = self._config.model
        payload: dict[str, Any] = {
            "model": model,
            "messages": [message.to_dict() for message in messages],
        }

        token_field = "max_completion_tokens" if uses_completion_tokens(model) else "max_tokens"
        if token_field in self._rejected_params:
            token_field = "max_tokens" if token_field == "max_completion_tokens" else "max_completion_tokens"
        if token_field not in self._rejected_params:
            payload[token_field] = self._config.max_tokens

        # مدل‌های استدلالی جدید فقط دمای پیش‌فرض را می‌پذیرند
        if "temperature" not in self._rejected_params and not uses_completion_tokens(model):
            payload["temperature"] = self._config.temperature if temperature is None else temperature

        if json_mode and "response_format" not in self._rejected_params:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _adapt_to_error(self, detail: str, payload: dict[str, Any]) -> bool:
        """
        یادگیری از پیام خطا و حذف پارامتر مشکل‌ساز.

        بازگشتی True یعنی چیزی تغییر کرد و ارزش تلاش دوباره را دارد.
        """
        lowered = detail.lower()
        changed = False
        for parameter in ("max_tokens", "max_completion_tokens", "temperature", "response_format"):
            if parameter in lowered and parameter in payload and parameter not in self._rejected_params:
                self._rejected_params.add(parameter)
                payload.pop(parameter, None)
                logger.info("Provider %s rejected '%s'; retrying without it", self.name, parameter)
                changed = True
        # اگر max_tokens رد شد، معادل جدیدش را امتحان کن
        if "max_completion_tokens" in lowered and "max_tokens" not in payload:
            payload["max_completion_tokens"] = self._config.max_tokens
            self._rejected_params.discard("max_completion_tokens")
            changed = True
        return changed

    async def generate(
        self, messages: list[AIMessage], *, json_mode: bool = False, temperature: float | None = None
    ) -> AIResponse:
        """
        ارسال گفتگو به مدل و دریافت پاسخ.

        اگر سرویس یکی از پارامترها را نشناسد، همان پارامتر حذف و درخواست
        یک‌بار دیگر فرستاده می‌شود. این کار سازگاری با هم مدل‌های قدیمی و هم
        نسل جدید را بدون پیکربندی دستی تضمین می‌کند.
        """
        if not (self._config.base_url or "").strip():
            raise AIProviderError(
                f"Base URL for provider '{self.name}' is not configured", details={"provider": self.name}
            )
        if self._config.requires_api_key and not self._api_key:
            raise AuthenticationError(
                f"API key for provider '{self.name}' is not configured", details={"provider": self.name}
            )

        payload = self._build_payload(messages, json_mode, temperature)
        started_at = time.monotonic()

        try:
            client = await self._get_client()
            response = await client.post("/chat/completions", json=payload, headers=self._headers())

            # حداکثر دو بار خودش را با محدودیت‌های سرویس تطبیق می‌دهد
            for _ in range(2):
                if response.status_code != 400:
                    break
                detail = self._error_text(response)
                if not self._adapt_to_error(detail, payload):
                    break
                response = await client.post("/chat/completions", json=payload, headers=self._headers())

            self._raise_for_status(response)
            data = response.json()
        except httpx.TimeoutException as exc:
            raise TimeoutErrorApp(f"Provider '{self.name}' timed out") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Network error contacting provider '{self.name}'") from exc
        except ValueError as exc:
            raise AIProviderError(f"Provider '{self.name}' returned invalid JSON") from exc

        choices = data.get("choices") or []
        if not choices:
            # برخی درگاه‌ها خطا را با کد ۲۰۰ برمی‌گردانند
            error = data.get("error")
            if error:
                message = error.get("message") if isinstance(error, dict) else str(error)
                raise AIProviderError(f"Provider '{self.name}': {message}", details={"provider": self.name})
            raise AIProviderError(f"Provider '{self.name}' returned no choices")

        message = choices[0].get("message") or {}
        usage = data.get("usage") or {}
        content = str(message.get("content") or "")
        # مدل‌های استدلالی گاهی متن را در فیلد reasoning می‌گذارند
        if not content.strip():
            content = str(message.get("reasoning_content") or message.get("reasoning") or "")

        return AIResponse(
            content=content,
            provider=self.name,
            model=str(data.get("model") or self._config.model),
            finish_reason=str(choices[0].get("finish_reason") or ""),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            latency_seconds=round(time.monotonic() - started_at, 3),
        )

    # ------------------------------------------------------------------
    # پاسخ جریانی
    # ------------------------------------------------------------------
    @property
    def supports_streaming(self) -> bool:
        """سرویس‌های سازگار با OpenAI جریان SSE می‌دهند."""
        return True

    async def stream(
        self,
        messages: list[AIMessage],
        on_chunk: Callable[[str], None],
        *,
        temperature: float | None = None,
    ) -> AIResponse:
        """
        دریافت پاسخ به‌صورت جریانی از راه Server-Sent Events.

        قالب هر خط `data: {...}` است و پایان جریان با `data: [DONE]`
        اعلام می‌شود. متن در `choices[0].delta.content` می‌آید.

        اگر جریان به هر دلیلی شکست بخورد — سرویس پشتیبانی نکند، درگاه
        وسط راه ببرد، یا هیچ متنی نیاید — به `generate()` معمولی برمی‌گردیم.
        کاربر در بدترین حالت پاسخ را یکجا می‌بیند، نه اینکه خطا بگیرد.
        """
        if not (self._config.base_url or "").strip():
            raise AIProviderError(
                f"Base URL for provider '{self.name}' is not configured",
                details={"provider": self.name},
            )
        if self._config.requires_api_key and not self._api_key:
            raise AuthenticationError(
                f"API key for provider '{self.name}' is not configured",
                details={"provider": self.name},
            )

        payload = self._build_payload(messages, False, temperature)
        payload["stream"] = True
        started_at = time.monotonic()

        parts: list[str] = []
        model_name = ""
        finish_reason = ""
        usage: dict[str, Any] = {}

        try:
            client = await self._get_client()
            async with client.stream(
                "POST", "/chat/completions", json=payload, headers=self._headers()
            ) as response:
                if response.status_code >= 400:
                    # بدنه باید کامل خوانده شود وگرنه متن خطا در دست نیست
                    await response.aread()
                    self._raise_for_status(response)

                async for line in response.aiter_lines():
                    piece = self._parse_sse_line(line)
                    if piece is None:
                        continue
                    if piece is _STREAM_DONE:
                        break
                    chunk_text, chunk_model, chunk_finish, chunk_usage = piece
                    if chunk_model:
                        model_name = chunk_model
                    if chunk_finish:
                        finish_reason = chunk_finish
                    if chunk_usage:
                        usage = chunk_usage
                    if chunk_text:
                        parts.append(chunk_text)
                        # خطای مصرف‌کننده نباید جریان را قطع کند
                        try:
                            on_chunk(chunk_text)
                        except Exception:  # noqa: BLE001
                            logger.exception("Stream consumer callback failed")
        except (AuthenticationError, AIProviderError):
            raise
        except httpx.TimeoutException as exc:
            raise TimeoutErrorApp(f"Provider '{self.name}' timed out") from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "Streaming failed for provider '%s' (%s); falling back to a single response",
                self.name,
                exc.__class__.__name__,
            )
            return await self.generate(messages, temperature=temperature)

        content = "".join(parts)
        if not content.strip():
            # جریان چیزی نداد؛ درخواست معمولی می‌فرستیم تا کاربر
            # دست‌خالی نماند.
            logger.info(
                "Provider '%s' streamed no content; retrying without streaming", self.name
            )
            return await self.generate(messages, temperature=temperature)

        return AIResponse(
            content=content,
            provider=self.name,
            model=str(model_name or self._config.model),
            finish_reason=finish_reason,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            latency_seconds=round(time.monotonic() - started_at, 3),
        )

    @staticmethod
    def _parse_sse_line(line: str) -> Any:
        """
        تجزیهٔ یک خط SSE.

        بازگشتی‌ها: `None` یعنی خط بی‌ربط (خالی، کامنت، یا JSON خراب)،
        `_STREAM_DONE` یعنی پایان جریان، و در حالت عادی چهارتایی
        (متن، نام مدل، دلیل پایان، مصرف توکن).

        JSON خراب عمداً نادیده گرفته می‌شود نه پرتاب: بعضی درگاه‌ها میان
        جریان خطوط keep-alive می‌فرستند و یک خط ناقص نباید کل پاسخ را
        از بین ببرد.
        """
        text = (line or "").strip()
        if not text or text.startswith(":"):
            return None
        if text.startswith("data:"):
            text = text[5:].strip()
        if not text:
            return None
        if text == "[DONE]":
            return _STREAM_DONE

        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            return None
        if not isinstance(data, dict):
            return None

        choices = data.get("choices") or []
        chunk_text = ""
        finish_reason = ""
        if choices and isinstance(choices[0], dict):
            delta = choices[0].get("delta") or {}
            if isinstance(delta, dict):
                # مدل‌های استدلالی گاهی متن را در فیلد reasoning می‌ریزند
                chunk_text = str(
                    delta.get("content")
                    or delta.get("reasoning_content")
                    or delta.get("reasoning")
                    or ""
                )
            finish_reason = str(choices[0].get("finish_reason") or "")

        usage = data.get("usage")
        return (
            chunk_text,
            str(data.get("model") or ""),
            finish_reason,
            usage if isinstance(usage, dict) else {},
        )

    async def list_models(self) -> list[str]:
        """دریافت فهرست مدل‌های در دسترس سرویس."""
        try:
            client = await self._get_client()
            response = await client.get("/models", headers=self._headers(), timeout=25.0)
            if response.status_code >= 400:
                logger.info(
                    "Model listing failed for %s: HTTP %s", self.name, response.status_code
                )
                return []
            data = response.json()
            items = data.get("data") if isinstance(data, dict) else data
            # قوی‌ترین مدل‌ها بالای فهرست تا کاربر مجبور به جست‌وجو نباشد
            return sort_models(
                [
                    str(item.get("id"))
                    for item in (items or [])
                    if isinstance(item, dict) and item.get("id")
                ]
            )
        except (httpx.HTTPError, ValueError):
            return []

    async def close(self) -> None:
        """بستن کلاینت HTTP."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
