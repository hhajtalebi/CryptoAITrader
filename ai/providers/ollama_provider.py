"""
ارائه‌دهنده مدل محلی Ollama.

چرا وجود دارد؟
    طبق بند ۱۸ سند پروژه، در اولین اجرا هیچ API پولی نباید اجباری باشد.
    Ollama امکان اجرای مدل زبانی روی خود دستگاه کاربر را فراهم می‌کند:
    رایگان، بدون نیاز به کلید و بدون ارسال داده به بیرون.

نکته: Ollama یک مسیر سازگار با OpenAI نیز دارد، اما اینجا از API بومی آن
(/api/chat) استفاده می‌شود چون کنترل بهتری روی گزینه‌ها می‌دهد.

سه ایرادی که در نسخه قبلی باعث می‌شد «Ollama روی سیستم کار کند ولی برنامه
وصل نشود» و اینجا برطرف شده‌اند:

۱) نام مدل: پیش‌فرض برنامه `llama3.1` بود. اگر کاربر مدل دیگری نصب کرده
   باشد (مثلاً `qwen2.5:7b`)، هم `is_available` و هم `generate` شکست
   می‌خوردند — با پیامی که کاربر معمولی آن را «وصل نمی‌شود» می‌فهمد.
   حالا اگر مدل تنظیم‌شده نصب نباشد، به‌صورت خودکار یکی از مدل‌های
   نصب‌شده انتخاب می‌شود و فقط یک هشدار در لاگ می‌نشیند.

۲) نشانی میزبان: روی برخی ویندوزها `localhost` به IPv6 (::1) ترجمه می‌شود
   در حالی که Ollama فقط روی 127.0.0.1 گوش می‌دهد؛ نتیجه، خطای اتصال.
   حالا چند نشانی جایگزین به‌ترتیب آزمایش می‌شوند.

۳) مهلت زمانی: اولین پاسخ یک مدل محلی شامل بارگذاری مدل در حافظه است و
   می‌تواند ده‌ها ثانیه طول بکشد. مهلت اتصال و مهلت خواندن حالا از هم جدا
   شده‌اند تا «کند بودن» با «در دسترس نبودن» اشتباه گرفته نشود.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from ai.providers.base import AIMessage, AIProvider, AIProviderConfig, AIResponse
from app.exceptions import AIProviderError, TimeoutErrorApp
from app.logging import get_logger

from ai.prompt_budget import (
    choose_context_window,
    detect_total_memory_gb,
    estimate_tokens,
    safe_context_for_memory,
    strip_reasoning_block,
)
from ai.providers.ranking import sort_models

logger = get_logger(__name__)

#: نشانی پیش‌فرض وقتی کاربر چیزی وارد نکرده است
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"

#: حداقل مهلت خواندن پاسخ؛ بارگذاری اولیه مدل محلی زمان‌بر است
MIN_READ_TIMEOUT = 120.0

#: مهلت کوتاه برای بررسی «آیا سرویس بالا است؟»
# Ollama روی همین دستگاه اجرا می‌شود؛ اگر بالا باشد در چند صدم ثانیه
# پاسخ می‌دهد. مهلت ۶ ثانیه‌ای فقط وقتی خاموش است طول می‌کشید و کل
# زنجیرهٔ سیگنال/چت را کند می‌کرد.
PROBE_TIMEOUT = 2.0

#: پنجرهٔ متن امن وقتی دستگاه حافظهٔ کافی برای پنجرهٔ کامل ندارد
#: چند بار پس از مرگ اجراکنندهٔ مدل دوباره تلاش شود.
#:
#: عدد کوچک است چون هر تلاش، بارگذاری دوبارهٔ مدل را می‌طلبد و کاربر
#: پشت صفحه منتظر است. دو تلاش اکثر مرگ‌های گذرا را پوشش می‌دهد؛
#: بیشتر از آن یعنی مشکل پایدار است و باید به کاربر گفته شود.
#: حاشیهٔ امن (توکن) برای قالب‌بندی گفت‌وگو که خود اولاما اضافه می‌کند.
#:
#: برچسب نقش، جداکننده‌ها و توکن‌های ویژهٔ الگوی چت در شمارش ما نیستند
#: ولی جا می‌گیرند. بدون این حاشیه، پاسخ دقیقاً در لبهٔ پنجره می‌نشیند.
#: پنجرهٔ پیش‌فرضی که اولاما بدون `num_ctx` صریح استفاده می‌کند.
#:
#: تا وقتی پرامپت زیر این حد بماند، هیچ `num_ctx` نمی‌فرستیم و مدل
#: بارگذاری‌شده دست‌نخورده در حافظه می‌ماند — همان رفتاری که ترمینال
#: دارد و بی‌نقص کار می‌کند.
DEFAULT_MODEL_CONTEXT = 4096

#: مدت نگه‌داشتن مدل در حافظه بین درخواست‌ها.
#:
#: پیش‌فرض اولاما ۵ دقیقه است. برای برنامه‌ای که کاربر ممکن است بین دو
#: پرسش چند دقیقه فکر کند، کوتاه است: هر بار بارگذاری دوبارهٔ چند
#: گیگابایت، هم کند است و هم لحظهٔ پرخطر برای مرگ اجراکننده.
KEEP_ALIVE = "30m"

#: وقتی ناچار به فرستادن `num_ctx` شدیم، همان مقدار را تا پایان اجرا
#: نگه می‌داریم.
#:
#: چرا؟ در نسخهٔ ۱٫۹٫۷ فقط یک نیمهٔ مشکل حل شد: درخواست‌های کوچک دیگر
#: `num_ctx` نمی‌فرستادند. ولی یک نوبت چت چند دور دارد و هر دور پرامپت
#: را بزرگ‌تر می‌کند (نتیجهٔ ابزارها به تاریخچه اضافه می‌شود). دور اول
#: زیر ۴۰۹۶ بود و چیزی نمی‌فرستاد، دور سوم از آن رد می‌شد و ۸۱۹۲
#: می‌فرستاد — یعنی وسط همان یک نوبت، اولاما مجبور به تخلیه و بارگذاری
#: دوبارهٔ مدل می‌شد. دقیقاً همان‌جا اجراکننده می‌مرد.
#:
#: حالا به‌محض اینکه یک بار پنجرهٔ صریح لازم شود، مستقیم سقف امن دستگاه
#: انتخاب و تا آخر تکرار می‌شود. نتیجه: حداکثر **یک** بارگذاری در کل
#: عمر برنامه، و پس از آن هیچ تغییری در پنجره.

REPLY_SAFETY_MARGIN = 256

#: کمترین تعداد توکن پاسخ که ارزش درخواست دارد.
MIN_NUM_PREDICT = 256

#: کوچک‌ترین پنجره‌ای که هنگام نجات از مرگ اجراکننده سراغش می‌رویم.
#:
#: کمتر از این، پاسخ آن‌قدر بی‌بافت می‌شود که ارزش نمایش ندارد؛ بهتر
#: است صادقانه شکست را گزارش کنیم تا تحلیلی بی‌پایه بدهیم.
CRASH_MIN_CONTEXT = 1024

RUNNER_CRASH_RETRIES = 2

#: مکث پیش از تلاش مجدد (ثانیه). با هر تلاش ضرب می‌شود.
#:
#: بدون مکث، درخواست بعدی به اولامایی می‌رسد که هنوز مشغول پاک‌کردن
#: مدل مُرده است و باز هم شکست می‌خورد.
RUNNER_CRASH_BACKOFF = 1.5

FALLBACK_NUM_CTX = 4096

#: بیشترین توکن پاسخ در حالت کم‌حافظه
FALLBACK_NUM_PREDICT = 700

#: نشانه‌های متنی خطای کمبود حافظه در پاسخ اولاما
MEMORY_ERROR_HINTS = (
    "memory",
    "out of memory",
    "oom",
    "cudamalloc",
    "unable to allocate",
    "no space",
    "model requires more system memory",
    "failed to allocate",
)


def _is_runner_crash(response: Any) -> bool:
    """
    آیا این خطا از مرگ زیرفرایند مدل است، نه از بزرگی پنجره؟

    تفکیک این دو مهم است چون درمانشان فرق دارد: سرریز پنجره با
    کوچک‌کردن پنجره حل می‌شود، ولی مرگ اجراکننده با تلاش مجدد و
    بارگذاری دوبارهٔ مدل.
    """
    reason = (_response_error(response) or "").lower()
    if not reason:
        return False
    return any(
        marker in reason
        for marker in (
            "forcibly closed",       # ویندوز، گزارش‌شده توسط کاربر
            "wsarecv",               # همان، نام تابع سوکت ویندوز
            "connection reset",      # لینوکس و مک
            "broken pipe",
            "eof",
            "error was encountered while running the model",
            "runner",
            "exit status",
        )
    )


def _response_error(response: Any) -> str:
    """
    بیرون کشیدن پیام خطای اولاما از بدنهٔ پاسخ.

    اولاما خطا را به‌صورت `{"error": "..."}` برمی‌گرداند، ولی هنگام
    فروپاشی ممکن است متن خام یا HTML بدهد؛ هر دو حالت باید خوانده شود.
    """
    try:
        payload = response.json()
    except (ValueError, AttributeError):
        payload = None
    if isinstance(payload, dict):
        message = payload.get("error") or payload.get("message") or ""
        if message:
            return str(message).strip()
    text = str(getattr(response, "text", "") or "").strip()
    return text[:300]


def _looks_like_memory(reason: str) -> bool:
    """آیا متن خطا از کمبود حافظه حکایت دارد؟"""
    lowered = reason.lower()
    return any(hint in lowered for hint in MEMORY_ERROR_HINTS)


def host_candidates(base_url: str) -> list[str]:
    """
    ساخت فهرست نشانی‌های قابل آزمایش برای یک نشانی ورودی.

    ترتیب مهم است: اول دقیقاً همان چیزی که کاربر داده، بعد جایگزین‌های
    رایجی که در ویندوز مشکل‌گشا هستند.
    """
    raw = (base_url or "").strip().rstrip("/") or DEFAULT_OLLAMA_URL
    if "://" not in raw:
        raw = f"http://{raw}"

    candidates = [raw]
    parts = urlsplit(raw)
    hostname = parts.hostname or ""
    port = parts.port or 11434

    # localhost ⇄ 127.0.0.1 : یکی از این دو تقریباً همیشه جواب می‌دهد
    swaps = {"localhost": "127.0.0.1", "127.0.0.1": "localhost", "::1": "127.0.0.1"}
    alternative = swaps.get(hostname)
    if alternative:
        candidates.append(urlunsplit((parts.scheme, f"{alternative}:{port}", "", "", "")))

    # اگر کاربر پورت را جا انداخته باشد
    if parts.port is None:
        candidates.append(urlunsplit((parts.scheme, f"{hostname}:11434", "", "", "")))

    seen: set[str] = set()
    unique: list[str] = []
    for item in candidates:
        cleaned = item.rstrip("/")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return unique


def model_matches(configured: str, installed: str) -> bool:
    """
    آیا مدل نصب‌شده همان مدل درخواستی است؟

    Ollama نام مدل را به شکل `name:tag` نگه می‌دارد. کاربر معمولاً فقط
    `llama3.1` می‌نویسد در حالی که نسخه نصب‌شده `llama3.1:8b` است — این دو
    باید یکی حساب شوند.
    """
    wanted = (configured or "").strip().lower()
    have = (installed or "").strip().lower()
    if not wanted or not have:
        return False
    if wanted == have:
        return True
    # مقایسه بدون برچسب، در هر دو جهت
    return wanted.split(":")[0] == have.split(":")[0]


class OllamaProvider(AIProvider):
    """
    کلاینت سرویس محلی Ollama.

    مسیرها:
        POST {base_url}/api/chat
        GET  {base_url}/api/tags
    """

    provider_type = "ollama"

    def __init__(self, config: AIProviderConfig, api_key: str | None = None) -> None:
        # Ollama محلی است و کلید نمی‌خواهد
        config.requires_api_key = False
        if not (config.base_url or "").strip():
            config.base_url = DEFAULT_OLLAMA_URL
        super().__init__(config, api_key)
        self._client: httpx.AsyncClient | None = None
        #: نشانی‌ای که واقعاً جواب داده است (پس از آزمون‌وخطا)
        self._resolved_url: str = ""
        #: مدلی که واقعاً استفاده می‌شود (ممکن است با تنظیمات فرق کند)
        self._resolved_model: str = ""
        #: سقف پنجرهٔ متن بر پایهٔ حافظهٔ دستگاه (یک‌بار تشخیص، سپس کش)
        self._context_ceiling: int = 0
        #: پنجره‌ای که مدل با آن بارگذاری شده است؛ تا پایان اجرا ثابت
        #: می‌ماند. صفر یعنی هنوز هیچ `num_ctx` صریحی نفرستاده‌ایم و
        #: مدل با پیش‌فرض خودش در حافظه نشسته است.
        self._session_ctx: int = 0
        #: اولاما به‌صورت پیش‌فرض همزمانی ندارد (OLLAMA_NUM_PARALLEL=1).
        #: دو درخواست همزمان — مثلاً چت کاربر و بازبینی خودکار سیگنال —
        #: در صف اولاما روی هم می‌افتند و حافظهٔ KV را دو برابر می‌کنند.
        #: این قفل تضمین می‌کند در هر لحظه فقط یک درخواست در راه است.
        self._request_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # اتصال
    # ------------------------------------------------------------------
    async def _resolve_base_url(self) -> str:
        """
        یافتن نشانی‌ای که سرویس روی آن پاسخ می‌دهد.

        نتیجه کش می‌شود تا هر درخواست دوباره جست‌وجو نکند.
        """
        if self._resolved_url:
            return self._resolved_url

        errors: list[str] = []
        for candidate in host_candidates(self._config.base_url):
            try:
                async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as probe:
                    response = await probe.get(f"{candidate}/api/tags")
                if response.status_code < 400:
                    self._resolved_url = candidate
                    if candidate != (self._config.base_url or "").rstrip("/"):
                        logger.info("Ollama reachable at %s (configured: %s)", candidate, self._config.base_url)
                    return candidate
                errors.append(f"{candidate} → HTTP {response.status_code}")
            except httpx.HTTPError as exc:
                errors.append(f"{candidate} → {exc.__class__.__name__}")

        raise AIProviderError(
            "Could not reach the local Ollama service",
            details={"tried": errors, "hint": "Run `ollama serve` and check the Base URL in Settings"},
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """ساخت یا استفاده مجدد از کلاینت HTTP روی نشانی حل‌شده."""
        base_url = await self._resolve_base_url()
        if self._client is None or self._client.is_closed or str(self._client.base_url).rstrip("/") != base_url:
            if self._client is not None and not self._client.is_closed:
                await self._client.aclose()
            read_timeout = max(float(self._config.timeout), MIN_READ_TIMEOUT)
            self._client = httpx.AsyncClient(
                base_url=base_url,
                # اتصال باید سریع باشد ولی تولید پاسخ می‌تواند طول بکشد
                timeout=httpx.Timeout(read_timeout, connect=PROBE_TIMEOUT),
            )
        return self._client

    # ------------------------------------------------------------------
    # مدل‌ها
    # ------------------------------------------------------------------
    async def installed_models(self) -> list[str]:
        """فهرست کامل مدل‌های نصب‌شده، با برچسب."""
        client = await self._get_client()
        response = await client.get("/api/tags", timeout=PROBE_TIMEOUT)
        if response.status_code >= 400:
            raise AIProviderError(f"Ollama returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise AIProviderError("Ollama returned an invalid model list") from exc
        return sorted(
            str(item.get("name"))
            for item in (payload.get("models") or [])
            if isinstance(item, dict) and item.get("name")
        )

    async def resolve_model(self) -> str:
        """
        انتخاب مدلی که واقعاً قابل استفاده است.

        اگر مدل تنظیم‌شده نصب باشد، همان برمی‌گردد. در غیر این صورت به‌جای
        شکست، اولین مدل نصب‌شده انتخاب می‌شود؛ این دقیقاً همان حالتی است
        که باعث می‌شد کاربر فکر کند «Ollama وصل نمی‌شود».
        """
        if self._resolved_model:
            return self._resolved_model

        installed = await self.installed_models()
        if not installed:
            raise AIProviderError(
                "Ollama is running but no model is installed",
                details={"hint": "ollama pull qwen2.5"},
            )

        wanted = (self._config.model or "").strip()
        for name in installed:
            if model_matches(wanted, name):
                self._resolved_model = name
                return name

        fallback = installed[0]
        self._resolved_model = fallback
        if wanted:
            logger.warning(
                "Ollama model '%s' is not installed; using '%s' instead", wanted, fallback
            )
        return fallback

    def update_config(self, config: AIProviderConfig) -> None:
        """با تغییر پیکربندی، نتایج کش‌شده باید دور ریخته شوند."""
        super().update_config(config)
        self._resolved_url = ""
        self._resolved_model = ""
        self._context_ceiling = 0

    @property
    def active_model(self) -> str:
        """مدلی که آخرین بار واقعاً استفاده شد."""
        return self._resolved_model or self._config.model

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    async def is_available(self) -> tuple[bool, str]:
        """
        بررسی اینکه سرویس Ollama در حال اجراست و دست‌کم یک مدل دارد.

        پیام بازگشتی طوری نوشته شده که کاربر بداند دقیقاً چه کاری باید بکند.
        نبودن *همان* مدل تنظیم‌شده دیگر خطا نیست؛ فقط اطلاع‌رسانی می‌شود.
        """
        try:
            installed = await self.installed_models()
        except AIProviderError as exc:
            return False, exc.message
        except httpx.TimeoutException:
            return False, "Ollama did not respond in time"
        except httpx.HTTPError:
            return False, "Ollama service is not running on this machine"

        if not installed:
            return False, "Ollama is running but no model is installed (try: ollama pull qwen2.5)"

        model = await self.resolve_model()
        if not model_matches(self._config.model, model):
            return True, f"Ollama is ready; using installed model '{model}'"
        return True, f"Local Ollama service is ready ({model})"

    # ------------------------------------------------------------------
    # تولید پاسخ
    # ------------------------------------------------------------------
    async def generate(
        self, messages: list[AIMessage], *, json_mode: bool = False, temperature: float | None = None
    ) -> AIResponse:
        """
        تولید پاسخ با مدل محلی — یکی در هر لحظه.

        اولاما به‌صورت پیش‌فرض همزمانی ندارد (`OLLAMA_NUM_PARALLEL=1`).
        اگر دو درخواست با هم برسند — مثلاً کاربر در حال چت باشد و
        بازبینی خودکار سیگنال هم در پس‌زمینه اجرا شود — اولاما برای هر
        کدام یک خانهٔ حافظهٔ KV جدا می‌گیرد و مصرف حافظه دو برابر
        می‌شود. روی دستگاه ۱۶ گیگابایتی همین کافی است تا اجراکننده وسط
        کار بمیرد؛ و چون یکی از دو درخواست پس‌زمینه‌ای است، کاربر فقط
        می‌بیند چتش بی‌دلیل شکست خورد.

        قفل، درخواست‌ها را پشت سر هم می‌کند. چند صد میلی‌ثانیه انتظار
        بیشتر، در برابر مرگ اجراکننده معاملهٔ خوبی است.
        """
        async with self._request_lock:
            return await self._generate_once(
                messages, json_mode=json_mode, temperature=temperature
            )

    async def _generate_once(
        self, messages: list[AIMessage], *, json_mode: bool = False, temperature: float | None = None
    ) -> AIResponse:
        """
        یک درخواست تولید، بدون مدیریت همزمانی.

        در حالت json_mode از پارامتر format=json خود Ollama استفاده می‌شود که
        مدل را وادار می‌کند خروجی JSON معتبر بدهد.
        """
        model = await self.resolve_model()
        options: dict[str, Any] = {
            "temperature": self._config.temperature if temperature is None else temperature,
        }

        # `num_ctx` و `num_predict` فقط وقتی فرستاده می‌شوند که واقعاً
        # لازم باشند.
        #
        # این مهم‌ترین تفاوت برنامه با `ollama run` در ترمینال بود.
        # ترمینال هیچ‌کدام را نمی‌فرستد و اولاما مدل را یک بار با
        # پنجرهٔ پیش‌فرض بارگذاری می‌کند و در حافظه نگه می‌دارد.
        #
        # برنامه اما برای هر درخواست مقدار متفاوتی می‌فرستاد: ۲۰۴۸ برای
        # یک پیام کوتاه چت، ۸۱۹۲ برای تحلیل. هر بار که `num_ctx` عوض
        # شود، اولاما مجبور است مدل را از حافظه تخلیه و با پنجرهٔ تازه
        # دوباره بارگذاری کند. روی مدل ۵ گیگابایتی این یعنی یک چرخهٔ
        # تخلیه/بارگذاری کامل وسط کار کاربر — و همان‌جاست که اجراکننده
        # می‌میرد و «forcibly closed» می‌دهد.
        #
        # به همین دلیل بود که همان مدل در ترمینال بی‌نقص کار می‌کرد و
        # در برنامه نه. ربطی به اندازهٔ مدل یا حافظهٔ کل نداشت.
        # پنجره «چسبنده» است: یک بار انتخاب، تا آخر همان.
        #
        # نکتهٔ حیاتی که در ۱٫۹٫۷ از قلم افتاد: یک نوبت چت چند دور دارد
        # و هر دور، نتیجهٔ ابزارها را به تاریخچه اضافه می‌کند. پس پرامپت
        # دور به دور بزرگ‌تر می‌شود. با شرط «فقط وقتی لازم شد بفرست»،
        # دور اول چیزی نمی‌فرستاد (مدل با ۴۰۹۶ بارگذاری می‌شد) و دور
        # سوم ۸۱۹۲ می‌فرستاد — یعنی تخلیه و بارگذاری دوبارهٔ مدل، وسط
        # همان نوبت. همان‌جا اجراکننده می‌مرد.
        #
        # حالا به‌محض نیاز به پنجرهٔ صریح، یک‌راست سقف امن دستگاه گرفته
        # می‌شود (نه اندازهٔ همین درخواست) و در `_session_ctx` قفل
        # می‌شود تا همهٔ درخواست‌های بعدی همان را بفرستند.
        window = self._sticky_context(messages)
        if window:
            options["num_ctx"] = window
        # `num_predict` پارامتر زمان تولید است نه زمان بارگذاری، پس
        # تغییرش مدل را دوباره بارگذاری نمی‌کند و فرستادنش بی‌خطر است.
        # بدون آن، سقف `ai.max_tokens` کاربر بی‌اثر می‌شد.
        options["num_predict"] = self._reply_budget(messages, self._effective_window())

        # پنجره ثابت است، پس پرامپت بزرگ‌تر از آن را باید خودمان
        # کوتاه کنیم. اگر نکنیم، اولاما بی‌صدا **ابتدای** پرامپت را
        # می‌برد — یعنی دستورالعمل سیستمی حذف می‌شود و مدل بدون اینکه
        # بفهمد، نصف داده‌ها را نمی‌بیند و جای خالی را حدس می‌زند.
        fitted = self._fit_messages(messages, self._effective_window())

        payload: dict[str, Any] = {
            "model": model,
            "messages": fitted,
            "stream": False,
            # مدل را بین درخواست‌ها در حافظه نگه می‌دارد.
            #
            # بدون این، اولاما مدل را پس از ۵ دقیقه بی‌کاری تخلیه
            # می‌کند و درخواست بعدی کاربر باید منتظر بارگذاری دوبارهٔ
            # چند گیگابایت بماند — که هم کند است و هم دقیقاً همان
            # لحظهٔ پرخطر برای مرگ اجراکننده.
            "keep_alive": KEEP_ALIVE,
            "options": options,
        }
        if json_mode:
            payload["format"] = "json"

        started_at = time.monotonic()
        try:
            client = await self._get_client()
            response = await client.post("/api/chat", json=payload)

            if response.status_code >= 500 and _is_runner_crash(response):
                # اجراکنندهٔ مدل وسط کار مُرد.
                #
                # نشانه‌اش روی ویندوز این است: «wsarecv: An existing
                # connection was forcibly closed». این با سرریز پنجره
                # فرق دارد — پنجره ممکن است کوچک باشد و باز هم رخ دهد،
                # چون علتش تمام‌شدن حافظهٔ کارت گرافیک وسط تولید پاسخ
                # است، یا خودِ اولاما که مدل را از حافظه بیرون انداخته.
                #
                # کاربر این را در چت دید، جایی که پنجره فقط ۲۰۴۸ بود و
                # نردبان کوچک‌کردن اصلاً فعال نمی‌شد. یک تلاش مجدد پس از
                # مکث کوتاه معمولاً جواب می‌دهد، چون اولاما مدل را از نو
                # بارگذاری می‌کند.
                # تلاش مجدد باید **پرامپت** را کوچک کند، نه فقط سقف پاسخ.
                #
                # نسخه‌های پیشین فقط `num_predict` را نصف می‌کردند. ابزار
                # `tools/ollama_doctor.py` روی همین الگو نشان داد که آنچه
                # اجراکننده را می‌کشد اندازهٔ **پرامپت** است: درخواست کوتاه
                # موفق می‌شود و همان درخواست با نتیجهٔ ابزار می‌شکند. نصف‌کردن
                # سقف پاسخ در آن حالت تقریباً بی‌اثر است، چون حافظهٔ اصلی را
                # پرامپت گرفته است.
                #
                # پس هر تلاش، پرامپت را هم به‌شکل محسوس کوچک می‌کند. این
                # تفاوت «پاسخ می‌گیرم ولی خلاصه‌تر» با «هیچ پاسخی نمی‌گیرم»
                # است — و روی کارت‌های کم‌حافظه همین تفاوت همه‌چیز است.
                for attempt in range(RUNNER_CRASH_RETRIES):
                    delay = RUNNER_CRASH_BACKOFF * (attempt + 1)
                    shrunk_window = max(
                        CRASH_MIN_CONTEXT,
                        self._effective_window() // (2 ** (attempt + 1)),
                    )
                    logger.warning(
                        "Ollama runner crashed (attempt %s/%s); retrying in %.1fs "
                        "with the prompt fitted to %s tokens",
                        attempt + 1,
                        RUNNER_CRASH_RETRIES,
                        delay,
                        shrunk_window,
                    )
                    await asyncio.sleep(delay)

                    payload["messages"] = self._fit_messages(
                        messages, shrunk_window, protect_system=False
                    )
                    current = int(
                        payload["options"].get("num_predict", self._config.max_tokens)
                    )
                    payload["options"]["num_predict"] = max(MIN_NUM_PREDICT, current // 2)
                    response = await client.post("/api/chat", json=payload)
                    if response.status_code < 500:
                        logger.info(
                            "Ollama recovered on attempt %s with a smaller prompt", attempt + 1
                        )
                        break

            current_ctx = int(payload["options"].get("num_ctx", DEFAULT_MODEL_CONTEXT))
            if response.status_code >= 500 and current_ctx > FALLBACK_NUM_CTX:
                # مهم‌ترین تفاوت برنامه با `ollama run` در ترمینال همین
                # است: ترمینال پنجرهٔ پیش‌فرض (۴۰۹۶) را می‌گیرد و برنامه
                # ۸۱۹۲ می‌خواست. روی کارت گرافیک با VRAM محدود، همان
                # مدلی که دستی کار می‌کند اینجا «HTTP 500» می‌دهد — حتی
                # وقتی رم سیستم فراوان است. پس به هر خطای سرور، یک بار با
                # پنجرهٔ محافظه‌کارانه دوباره تلاش می‌کنیم.
                logger.warning(
                    "Ollama failed with num_ctx=%s (%s); retrying with %s",
                    current_ctx,
                    _response_error(response) or f"HTTP {response.status_code}",
                    FALLBACK_NUM_CTX,
                )
                # پنجرهٔ جلسه هم پایین می‌آید، وگرنه درخواست بعدی دوباره
                # عدد بزرگ را می‌فرستد و مدلی که همین حالا با پنجرهٔ
                # کوچک بارگذاری شده، دوباره تخلیه می‌شود.
                self._session_ctx = FALLBACK_NUM_CTX
                payload["options"]["num_ctx"] = FALLBACK_NUM_CTX
                payload["options"]["num_predict"] = min(
                    int(self._config.max_tokens), FALLBACK_NUM_PREDICT
                )
                # کوچک‌کردن پنجره بدون کوچک‌کردن پرامپت، خطرناک‌تر از
                # خود خطاست: اولاما پرامپتِ بلندتر از پنجره را بی‌صدا از
                # ابتدا می‌برد. مدل بخشی از داده‌های بازار را نمی‌بیند،
                # جای خالی را با حدس پر می‌کند و سیگنالی می‌سازد که
                # درست به نظر می‌رسد ولی نیست. پس پیام‌ها را خودمان و
                # آگاهانه تا اندازهٔ امن کوتاه می‌کنیم.
                payload["messages"] = self._fit_messages(messages, FALLBACK_NUM_CTX)
                response = await client.post("/api/chat", json=payload)

            if response.status_code >= 500 and payload.get("format") == "json":
                # مدل‌های استدلالی (مثل deepseek-r1) با حالت اجباری JSON
                # گاهی در خود اولاما می‌شکنند. بدون آن دوباره می‌پرسیم و
                # JSON را از متن بیرون می‌کشیم؛ لایهٔ بالاتر این کار را
                # بلد است.
                logger.warning(
                    "Ollama rejected format=json for '%s'; retrying as plain text", model
                )
                payload.pop("format", None)
                response = await client.post("/api/chat", json=payload)
            if response.status_code == 404:
                # مدل بین resolve و ارسال حذف شده؛ یک‌بار دیگر با فهرست تازه
                self._resolved_model = ""
                model = await self.resolve_model()
                payload["model"] = model
                response = await client.post("/api/chat", json=payload)
            if response.status_code >= 400:
                raise AIProviderError(
                    self._describe_http_error(response, model),
                    details={
                        "provider": self.name,
                        "status": response.status_code,
                        "model": model,
                        "reason": _response_error(response),
                    },
                )
            data = response.json()
        except httpx.TimeoutException as exc:
            raise TimeoutErrorApp(
                f"Local model '{model}' timed out; a smaller model may be needed"
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("Could not reach the local Ollama service") from exc
        except ValueError as exc:
            raise AIProviderError("Ollama returned invalid JSON") from exc

        message = data.get("message") or {}
        raw_content = str(message.get("content") or "")
        # مدل‌های استدلالی (deepseek-r1 و هم‌خانواده) پاسخ را داخل
        # <think>…</think> می‌پیچند. بدون پاک‌سازی، هم `json.loads` روی
        # سیگنال می‌شکند و هم افکار خام مدل در چت به کاربر نشان داده
        # می‌شود. اگر بعد از پاک‌سازی چیزی نماند یعنی پاسخ وسط استدلال
        # قطع شده؛ آن‌وقت متن خام را برمی‌گردانیم تا لایهٔ بالا دست‌کم
        # چیزی برای نمایش داشته باشد.
        content = strip_reasoning_block(raw_content) or raw_content
        return AIResponse(
            content=content,
            provider=self.name,
            model=str(data.get("model") or model),
            finish_reason="stop" if data.get("done") else "",
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            completion_tokens=int(data.get("eval_count") or 0),
            latency_seconds=round(time.monotonic() - started_at, 3),
        )

    def _fit_messages(
        self,
        messages: list[AIMessage],
        context_window: int,
        *,
        protect_system: bool = True,
    ) -> list[dict[str, str]]:
        """
        کوتاه‌کردن آگاهانهٔ پیام‌ها تا جا شدن در پنجرهٔ داده‌شده.

        چرا خودمان و نه اولاما؟
            اولاما وقتی پرامپت از پنجره بزرگ‌تر باشد، **ابتدای** آن را
            بی‌صدا می‌برد — یعنی دستورالعمل سیستمی و بخش اول داده‌ها
            حذف می‌شوند و مدل حتی نمی‌فهمد چیزی کم شده است. ما برعکس
            عمل می‌کنیم: پیام سیستمی و انتهای پرامپت (که فرمت خروجی
            در آن است) دست‌نخورده می‌مانند و از **میانهٔ** داده‌ها
            برداشته می‌شود، با یک نشانهٔ صریح در جای بریدگی تا مدل
            بداند تصویرش ناقص است.

        `protect_system` چرا لازم شد؟
            پیام سیستمی برنامه با ۱۴ ابزار حدود ۱۲۲۲ توکن است. وقتی
            برای نجات از مرگ اجراکننده پنجره را به ۱۰۲۴ می‌رسانیم،
            همین پیام به‌تنهایی از کل پنجره بزرگ‌تر است — پس اگر
            دست‌نخورده بماند، کوچک‌سازی عملاً هیچ اثری ندارد. این را
            با اندازه‌گیری دیدم: پرامپت روی ۴٬۴۱۱ نویسه گیر کرده بود و
            هر دو تلاش نجات دقیقاً همان اندازه را می‌فرستادند.

            در مسیر عادی پیام سیستمی محترم است (`True`). فقط در مسیر
            نجات، که جایگزینش «هیچ پاسخی» است، اجازه می‌دهیم کوتاه شود.
        """
        from ai.prompt_budget import available_prompt_tokens

        budget = available_prompt_tokens(context_window)
        payload = [message.to_dict() for message in messages]
        total = sum(estimate_tokens(item["content"]) for item in payload)
        if total <= budget:
            return payload

        # پیام‌های سیستمی کوچک و حیاتی‌اند؛ در حالت عادی دست نمی‌خورند.
        system_items = [item for item in payload if item["role"] == "system"]
        system_tokens = sum(estimate_tokens(item["content"]) for item in system_items)

        if not protect_system and system_tokens > budget // 2:
            # حالت نجات: پیام سیستمی هم باید جا شود. نصف پنجره را به آن
            # می‌دهیم — کمتر از این، مدل نمی‌فهمد باید چه‌کار کند.
            allowed = max(256, budget // 2)
            for item in system_items:
                if estimate_tokens(item["content"]) > allowed:
                    item["content"] = item["content"][: allowed * 3]
            system_tokens = sum(estimate_tokens(item["content"]) for item in system_items)

        remaining = max(256, budget - system_tokens)

        user_items = [item for item in payload if item["role"] != "system"]
        if not user_items:
            return payload

        # کف ۲۵۶ توکنی در حالت نجات معنا ندارد: با چند پیام، حاصل‌جمع
        # کف‌ها از خود پنجره بیشتر می‌شود و کوچک‌سازی بی‌اثر می‌ماند.
        floor = 256 if protect_system else 64
        per_message = max(floor, remaining // len(user_items))
        marker = "\n\n[... part of the market data was omitted to fit the local model's context window; do not guess the missing values ...]\n\n"

        for item in user_items:
            text = item["content"]
            if estimate_tokens(text) <= per_message:
                continue
            allowed_chars = per_message * 3
            head = int(allowed_chars * 0.55)
            tail = allowed_chars - head - len(marker)
            if tail < 200:
                item["content"] = text[:allowed_chars]
            else:
                item["content"] = text[:head] + marker + text[-tail:]

        logger.warning(
            "Prompt exceeded the safe context window (%s tokens > %s); it was trimmed",
            total,
            budget,
        )
        return payload

    def _describe_http_error(self, response: Any, model: str) -> str:
        """
        پیام خطای خواندنی از پاسخ اولاما.

        «HTTP 500» به‌تنهایی هیچ چیز به کاربر نمی‌گوید؛ خود اولاما دلیل را
        در بدنهٔ پاسخ می‌نویسد (مثلاً کمبود حافظه یا مدل خراب) و دور
        ریختن آن یعنی عیب‌یابی ناممکن.
        """
        reason = _response_error(response)
        status = response.status_code
        if status >= 500 and _looks_like_memory(reason):
            return (
                f"Ollama could not load '{model}' — not enough memory. "
                f"Try a smaller model or lower ai.max_tokens ({reason})"
            )
        if status >= 500 and _is_runner_crash(response):
            # پیام خام اولاما («wsarecv…») برای کاربر بی‌معناست و
            # شبیه مشکل شبکه به نظر می‌رسد، در حالی که ربطی به شبکه
            # ندارد. پیام باید بگوید چه اتفاقی افتاده و کاربر چه کار
            # می‌تواند بکند.
            # پیام قبلی «مدل برای حافظه‌ات بزرگ است» را حدس می‌زد و
            # کاربر را دنبال نخ اشتباه می‌فرستاد — در حالی که همان مدل
            # در ترمینال بی‌نقص کار می‌کرد. وقتی دلیل را مطمئن نیستیم،
            # نباید وانمود کنیم هستیم.
            return (
                f"The local model '{model}' stopped unexpectedly while generating "
                f"(retried {RUNNER_CRASH_RETRIES} times). If the same model works in "
                f"'ollama run', this is not a size problem: check that no other tool "
                f"is querying Ollama at the same time, and see ollama's own log "
                f"(ollama serve) for the real cause ({reason})"
            )
        if reason:
            return f"Ollama returned HTTP {status}: {reason}"
        return f"Ollama returned HTTP {status}"

    def _is_memory_error(self, response: Any) -> bool:
        """آیا شکست به کمبود حافظه مربوط است؟"""
        return _looks_like_memory(_response_error(response))

    def _memory_ceiling(self) -> int:
        """
        بیشترین پنجرهٔ متنی که این دستگاه تحمل می‌کند.

        یک بار تشخیص داده و کش می‌شود. کاربر می‌تواند با کلید تنظیمات
        `ai.ollama_max_context` آن را دستی تعیین کند — مثلاً وقتی کارت
        گرافیک ضعیف‌تر از حافظهٔ سیستم است.
        """
        if self._context_ceiling:
            return self._context_ceiling

        override = 0
        try:
            override = int((self._config.extra or {}).get("max_context") or 0)
        except (TypeError, ValueError):
            override = 0

        if override > 0:
            self._context_ceiling = override
            logger.info("Ollama context ceiling set manually to %s", override)
        else:
            memory_gb = detect_total_memory_gb()
            self._context_ceiling = safe_context_for_memory(memory_gb)
            logger.info(
                "Ollama context ceiling %s (detected %.1f GB of system memory)",
                self._context_ceiling,
                memory_gb or 0.0,
            )
        return self._context_ceiling

    def prompt_token_budget(self) -> int:
        """
        چند توکن برای پرامپت آزاد است.

        لایهٔ تحلیل پیش از ساختن پرامپت این را می‌پرسد تا داده را از
        همان اول اندازهٔ درست بسازد. این تفاوت بنیادی با رفتار پیشین
        است: به‌جای فرستادن پرامپت بزرگ و امید به بهترین، اول می‌پرسیم
        چقدر جا هست.
        """
        from ai.prompt_budget import available_prompt_tokens

        return available_prompt_tokens(self._memory_ceiling())

    def _needed_context(self, messages: list[AIMessage] | None = None) -> int:
        """
        چند توکن پنجره برای این درخواست لازم است (پرامپت + پاسخ).

        اگر از پنجرهٔ پیش‌فرض مدل کمتر باشد، اصلاً `num_ctx` نمی‌فرستیم
        و مدل در حافظه دست‌نخورده می‌ماند.
        """
        prompt_tokens = 0
        for message in messages or ():
            prompt_tokens += estimate_tokens(str(getattr(message, "content", "")))
        return prompt_tokens + int(self._config.max_tokens) + REPLY_SAFETY_MARGIN

    def _reply_budget(
        self, messages: list[AIMessage] | None = None, window: int | None = None
    ) -> int:
        """
        چند توکن پاسخ از این مدل بخواهیم.

        این همان چیزی است که برنامه را از `ollama run` در ترمینال جدا
        می‌کرد. ترمینال هیچ `num_predict` نمی‌فرستد و اولاما تا هر جا
        که لازم باشد تولید می‌کند. برنامه اما `ai.max_tokens` را که
        پیش‌فرضش ۱۶۰۰ است مستقیم می‌فرستاد — بدون توجه به اینکه پنجرهٔ
        انتخاب‌شده چقدر است.

        نتیجه روی یک پیام کوتاه چت: پنجره ۲۰۴۸ و درخواست ۱۶۰۰ توکن
        پاسخ. یعنی ۷۸٪ کل پنجره فقط برای بافر تولید رزرو می‌شد. روی
        مدل‌های ۸ میلیاردی این بافر آن‌قدر بزرگ می‌شود که اجراکننده
        وسط کار حافظه کم می‌آورد و می‌میرد — همان
        «forcibly closed» که کاربر دید، در حالی که همان مدل در ترمینال
        بی‌نقص کار می‌کرد.

        حالا سقف پاسخ هرگز از سهم مجاز پنجره بیشتر نمی‌شود.
        """
        requested = int(self._config.max_tokens)
        if window is None:
            window = self._num_ctx(messages)

        prompt_tokens = 0
        for message in messages or ():
            prompt_tokens += estimate_tokens(str(getattr(message, "content", "")))

        # آنچه واقعاً باقی می‌ماند، منهای حاشیهٔ امن برای توکن‌های
        # قالب‌بندی گفت‌وگو که خود اولاما اضافه می‌کند.
        headroom = window - prompt_tokens - REPLY_SAFETY_MARGIN
        allowed = min(requested, headroom)

        # کف را نگه می‌داریم: پاسخ ۵۰ توکنی عملاً بی‌فایده است و بهتر
        # است به‌جایش پنجره بزرگ‌تر انتخاب شود (که `_num_ctx` می‌کند).
        return max(MIN_NUM_PREDICT, allowed)

    def _sticky_context(self, messages: list[AIMessage] | None = None) -> int:
        """
        پنجره‌ای که باید فرستاده شود — و پاسخ درست تقریباً همیشه «هیچ».

        تصحیح نسبت به ۱٫۹٫۸ (لاگ خود اولاما این را ثابت کرد):

            level=INFO source=types.go:32 msg="inference compute"
                library=Vulkan name="NVIDIA GeForce GT 740"
                total="2.0 GiB" available="1.7 GiB"
            level=INFO source=routes.go:2062
                msg="vram-based default context"
                total_vram="2.0 GiB" default_num_ctx=4096

        یعنی اولاما پنجرهٔ پیش‌فرض را از روی **حافظهٔ کارت گرافیک**
        حساب می‌کند، نه حافظهٔ سیستم. کارت کاربر ۲ گیگابایت دارد، پس
        اولاما ۴۰۹۶ انتخاب کرده بود.

        من اما ۸۱۹۲ می‌فرستادم، چون سقف را از ۱۶ گیگابایت **رم سیستم**
        درمی‌آوردم و اصلاً نمی‌دانستم کارت گرافیکی در کار است. آن ۸۱۹۲
        یعنی دو برابر کردن حافظهٔ KV روی کارتی که ۱٫۷ گیگابایت آزاد
        دارد — و همان‌جا اجراکننده می‌مرد.

        درس: اولاما خودش این محاسبه را بهتر از ما انجام می‌دهد، چون به
        سخت‌افزار دسترسی دارد و ما نداریم. پس **اصلاً `num_ctx`
        نمی‌فرستیم** و می‌گذاریم اولاما عدد درست همان دستگاه را انتخاب
        کند. این هم با ترمینال یکسان است و هم خودبه‌خود ثابت می‌ماند،
        پس هر دو ایراد نسخه‌های قبل با هم برطرف می‌شود.

        تنها استثنا: اگر کاربر آگاهانه `ai.ollama_max_context` را تنظیم
        کرده باشد. آن وقت همان عدد، ثابت و بدون تغییر، فرستاده می‌شود.
        """
        if self._session_ctx:
            return self._session_ctx

        override = self._context_override()
        if override <= 0:
            # مسیر عادی: هیچ. اولاما خودش از روی VRAM تصمیم می‌گیرد.
            return 0

        self._session_ctx = override
        logger.info(
            "Ollama context window pinned to %s by the user setting "
            "ai.ollama_max_context; it will not change during this session",
            self._session_ctx,
        )
        return self._session_ctx

    def _context_override(self) -> int:
        """عدد صریح کاربر از `ai.ollama_max_context`؛ صفر یعنی تنظیم نشده."""
        try:
            return int((self._config.extra or {}).get("max_context") or 0)
        except (TypeError, ValueError):
            return 0

    def _effective_window(self) -> int:
        """
        پنجره‌ای که *عملاً* در کار است، چه بفرستیم چه نفرستیم.

        برای کوتاه‌کردن پرامپت لازم است: اگر چیزی نفرستیم، اولاما از
        پنجرهٔ پیش‌فرض خودش استفاده می‌کند و ما باید پرامپت را در همان
        اندازه جا بدهیم، وگرنه اولاما بی‌صدا ابتدایش را می‌بُرد.

        وقتی عددی نفرستاده‌ایم، محافظه‌کارانه‌ترین پیش‌فرض ممکن اولاما
        (۴۰۹۶، همان که روی کارت ۲ گیگابایتی کاربر انتخاب شد) را فرض
        می‌کنیم. اگر دستگاهی بزرگ‌تر باشد، اولاما پنجرهٔ بزرگ‌تری
        می‌گیرد و پرامپتِ کوتاه‌شدهٔ ما راحت در آن جا می‌شود — یعنی
        خطای این فرض همیشه به سمت امن است.
        """
        return self._session_ctx or self._context_override() or DEFAULT_MODEL_CONTEXT

    def _num_ctx(self, messages: list[AIMessage] | None = None) -> int:
        """
        اندازهٔ پنجرهٔ متن، محدود به سقف واقعی دستگاه.

        فرمول پیشین فقط به طول پرامپت نگاه می‌کرد و تا ۳۲۷۶۸ بالا
        می‌رفت. روی دستگاه ۱۶ گیگابایتی کاربر، `deepseek-r1:8b` با
        پنجرهٔ ۱۶۳۸۴ اصلاً بارگذاری نمی‌شود: اجراکنندهٔ اولاما پیش از
        تولید پاسخ می‌میرد و «۵۰۰ با بدنهٔ خالی» برمی‌گرداند. حالا سقف
        از حافظهٔ دستگاه می‌آید و هرگز از آن رد نمی‌شویم.
        """
        prompt_tokens = 0
        for message in messages or ():
            prompt_tokens += estimate_tokens(str(getattr(message, "content", "")))

        return choose_context_window(
            prompt_tokens,
            int(self._config.max_tokens),
            ceiling=self._memory_ceiling(),
        )

    async def list_models(self) -> list[str]:
        """فهرست مدل‌های نصب‌شده روی دستگاه کاربر (قوی‌ترین اول)."""
        try:
            return sort_models(await self.installed_models())
        except (AIProviderError, httpx.HTTPError, ValueError):
            return []

    async def close(self) -> None:
        """بستن کلاینت HTTP."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
