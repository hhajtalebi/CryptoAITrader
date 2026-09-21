# افزودن ارائه‌دهنده هوش مصنوعی جدید

این راهنما نشان می‌دهد چگونه یک سرویس هوش مصنوعی تازه به برنامه اضافه کنید،
**بدون آنکه حتی یک خط از کد اصلی برنامه تغییر کند**.

## ۱. آیا اصلاً نیاز به کد جدید دارید؟

قبل از نوشتن کلاس جدید، این پرسش را بررسی کنید:

| سرویس شما | راه‌حل |
|---|---|
| از قرارداد OpenAI پیروی می‌کند (`/chat/completions`) | نیازی به کد نیست؛ فقط در تنظیمات یک ارائه‌دهنده از نوع `openai_compatible` بسازید |
| Ollama محلی است | از پیش پشتیبانی می‌شود |
| قرارداد کاملاً متفاوتی دارد (مثلاً Anthropic یا Gemini) | باید کلاس جدید بنویسید — ادامه این راهنما |

بیشتر سرویس‌ها — OpenAI، OpenRouter، Together، Groq، DeepSeek، LM Studio،
vLLM، LocalAI — با گزینه اول کار می‌کنند و فقط به `base_url` و مدل نیاز دارند.

## ۲. ساختار لایه هوش مصنوعی

```
ai/providers/
├── base.py                  # قرارداد AIProvider (این را تغییر ندهید)
├── openai_compatible.py     # پیاده‌سازی سازگار با OpenAI
├── ollama_provider.py       # پیاده‌سازی محلی
├── manager.py               # زنجیره جایگزینی
└── my_provider.py           # ← فایل جدید شما
```

## ۳. نوشتن کلاس

فایل `ai/providers/my_provider.py` را بسازید و از `AIProvider` ارث‌بری کنید.
سه متد انتزاعی باید پیاده‌سازی شوند:

```python
"""ارائه‌دهنده نمونه — توضیح فارسی الزامی است."""

from __future__ import annotations

import time
import httpx

from ai.providers.base import AIMessage, AIProvider, AIResponse
from app.exceptions import AIProviderError, AuthenticationError
from app.logging import get_logger

logger = get_logger(__name__)


class MyProvider(AIProvider):
    """ارائه‌دهنده اختصاصی با قرارداد غیر استاندارد."""

    async def is_available(self) -> tuple[bool, str]:
        """
        بررسی در دسترس بودن سرویس.

        بازگشتی: (وضعیت، پیام قابل نمایش به کاربر)
        پیام باید راهنما باشد، نه فقط اعلام خطا.
        """
        if self.config.requires_api_key and not self._api_key:
            return False, "API key is not configured"
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return (True, "Ready") if response.status_code == 200 else (False, "Service error")
        except httpx.ConnectError:
            return False, "Cannot reach the service"

    async def generate(
        self,
        messages: list[AIMessage],
        *,
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> AIResponse:
        """ارسال درخواست و بازگرداندن پاسخ استاندارد."""
        started = time.perf_counter()
        client = await self._get_client()
        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature if temperature is not None else self.config.temperature,
        }
        response = await client.post("/v1/generate", json=payload)

        if response.status_code in (401, 403):
            raise AuthenticationError("Invalid API key", details={"provider": self.name})
        if response.status_code >= 400:
            raise AIProviderError(f"HTTP {response.status_code}", details={"provider": self.name})

        body = response.json()
        return AIResponse(
            content=body["output"]["text"],
            provider=self.name,
            model=self.config.model,
            finish_reason=body.get("stop_reason", ""),
            prompt_tokens=body.get("usage", {}).get("input_tokens", 0),
            completion_tokens=body.get("usage", {}).get("output_tokens", 0),
            latency_seconds=time.perf_counter() - started,
        )

    async def list_models(self) -> list[str]:
        """فهرست مدل‌های در دسترس، برای نمایش در تنظیمات."""
        client = await self._get_client()
        response = await client.get("/v1/models")
        return [item["id"] for item in response.json().get("models", [])]
```

## ۴. ثبت در کارخانه ارائه‌دهندگان

در `ai/providers/manager.py` یک سطر به نگاشت اضافه کنید:

```python
PROVIDER_TYPES: dict[str, type[AIProvider]] = {
    "ollama": OllamaProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "custom": OpenAICompatibleProvider,
    "my_provider": MyProvider,          # ← سطر جدید
}
```

و آن را در `ai/providers/__init__.py` صادر کنید.

## ۵. قواعدی که حتماً باید رعایت شوند

1. **کلید API هرگز در کد یا پایگاه داده ذخیره نمی‌شود.** کلید از
   `app.security.secret_store` می‌آید و در Windows داخل Credential Manager
   نگهداری می‌شود. کلاس شما فقط `self._api_key` را می‌خواند.
2. **کلید نباید در لاگ بیاید.** فیلتر `SensitiveDataFilter` فعال است، ولی
   خودتان هم هرگز `payload` یا هدرها را لاگ نکنید.
3. **خطاها باید به خطاهای استاندارد برنامه نگاشت شوند** (`AuthenticationError`،
   `AIProviderError`، `NetworkError`)؛ در غیر این صورت زنجیره جایگزینی و پیام
   فارسی خطا درست کار نمی‌کند.
4. **متد `close` را فراموش نکنید** (در کلاس پایه پیاده شده؛ اگر کلاینت
   جداگانه ساختید، بازنویسی کنید).
5. **هیچ‌گاه تحلیل بازار داخل ارائه‌دهنده انجام ندهید.** وظیفه این لایه فقط
   ارتباط با مدل است.

## ۶. تنظیم اولویت و جایگزینی

اولویت با عدد `priority` مشخص می‌شود؛ **عدد کوچک‌تر یعنی مهم‌تر**:

```python
AIProviderConfig(name="my_provider", model="my-model", priority=5)
```

`AIProviderManager` به‌ترتیب اولویت تلاش می‌کند و با نخستین پاسخ موفق متوقف
می‌شود. اگر همه شکست بخورند، خطای جامعی با شرح دلیل هر شکست بالا می‌آید.

## ۷. آزمودن

```python
import asyncio
from ai.providers import AIProviderConfig
from ai.providers.my_provider import MyProvider
from ai.providers.base import AIMessage

async def main():
    provider = MyProvider(AIProviderConfig(name="my_provider", model="my-model"), api_key="...")
    print(await provider.is_available())
    print((await provider.generate([AIMessage("user", "Say OK")])).content)
    await provider.close()

asyncio.run(main())
```

## چک‌لیست نهایی

- [ ] سه متد انتزاعی پیاده‌سازی شده‌اند
- [ ] در `PROVIDER_TYPES` ثبت شده است
- [ ] خطاها به خطاهای استاندارد نگاشت شده‌اند
- [ ] کلید API فقط از `SecretStore` خوانده می‌شود
- [ ] Docstring فارسی نوشته شده است
- [ ] با سرویس واقعی آزموده شده است
