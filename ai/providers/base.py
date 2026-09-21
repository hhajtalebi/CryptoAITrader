"""
واسط انتزاعی ارائه‌دهنده هوش مصنوعی.

چرا وجود دارد؟
    کاربر باید بتواند بدون هیچ هزینه‌ای با مدل محلی شروع کند و بعداً کلید
    سرویس قوی‌تر را وارد نماید، بدون آنکه چیزی در کد تغییر کند. این واسط
    همان قرارداد مشترک است.

نکته امنیتی: کلید API هرگز در این کلاس‌ها ذخیره یا لاگ نمی‌شود؛ هنگام نیاز
از Secret Store خوانده می‌شود.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AIProviderConfig:
    """
    پیکربندی یک ارائه‌دهنده.

    priority عدد کمتر یعنی اولویت بالاتر در زنجیره Fallback.
    """

    name: str
    display_name: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.2
    max_tokens: int = 1600
    timeout: int = 90
    priority: int = 100
    enabled: bool = True
    requires_api_key: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AIMessage:
    """یک پیام در گفتگو با مدل."""

    role: str  # system | user | assistant | tool
    content: str

    def to_dict(self) -> dict[str, str]:
        """تبدیل به قالب مورد انتظار API."""
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class AIResponse:
    """
    پاسخ دریافتی از مدل.

    provider و model برای ثبت در سابقه تحلیل ضروری‌اند تا مشخص باشد هر
    تحلیل با چه مدلی تولید شده است (بند ۵۲ سند پروژه).
    """

    content: str
    provider: str
    model: str
    finish_reason: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_seconds: float = 0.0

    @property
    def is_empty(self) -> bool:
        """آیا پاسخ عملاً خالی است؟"""
        return not self.content.strip()


class AIProvider(ABC):
    """
    قرارداد مشترک تمام ارائه‌دهندگان مدل زبانی.

    پیاده‌سازی‌ها باید ناهمگام باشند تا رابط کاربری در حین تحلیل مسدود نشود.
    """

    provider_type: str = "abstract"

    def __init__(self, config: AIProviderConfig, api_key: str | None = None) -> None:
        self._config = config
        self._api_key = api_key or ""

    @property
    def name(self) -> str:
        """نام یکتای ارائه‌دهنده."""
        return self._config.name

    @property
    def model(self) -> str:
        """نام مدل فعال."""
        return self._config.model

    @property
    def config(self) -> AIProviderConfig:
        """پیکربندی فعلی."""
        return self._config

    @property
    def has_api_key(self) -> bool:
        """آیا کلید لازم تنظیم شده است؟"""
        return bool(self._api_key)

    def set_api_key(self, api_key: str) -> None:
        """به‌روزرسانی کلید در زمان اجرا (پس از تغییر در تنظیمات)."""
        self._api_key = api_key or ""

    def update_config(self, config: AIProviderConfig) -> None:
        """جایگزینی کامل پیکربندی."""
        self._config = config

    @abstractmethod
    async def is_available(self) -> tuple[bool, str]:
        """
        بررسی در دسترس بودن سرویس.

        بازگشتی: (در دسترس بودن، پیام توضیحی بدون افشای اطلاعات حساس)
        """

    @abstractmethod
    async def generate(
        self, messages: list[AIMessage], *, json_mode: bool = False, temperature: float | None = None
    ) -> AIResponse:
        """
        تولید پاسخ از مدل.

        json_mode درخواست می‌کند خروجی حتماً JSON معتبر باشد؛ اگر سرویس این
        قابلیت را نداشته باشد، دستور آن در Prompt گنجانده می‌شود.
        """

    @abstractmethod
    async def list_models(self) -> list[str]:
        """فهرست مدل‌های در دسترس (برای انتخاب در تنظیمات)."""

    # ------------------------------------------------------------------
    # پاسخ جریانی (اختیاری)
    # ------------------------------------------------------------------
    @property
    def supports_streaming(self) -> bool:
        """
        آیا این سرویس پاسخ را تکه‌تکه می‌فرستد؟

        پیش‌فرض «نه» است تا سرویس‌های قدیمی بدون تغییر کار کنند؛
        فراخواننده در این حالت به `generate()` برمی‌گردد.
        """
        return False

    async def stream(
        self,
        messages: list[AIMessage],
        on_chunk: Callable[[str], None],
        *,
        temperature: float | None = None,
    ) -> AIResponse:
        """
        تولید پاسخ به‌صورت جریانی.

        `on_chunk` برای هر تکه متن صدا زده می‌شود و در پایان، پاسخ کامل
        مثل `generate()` برگردانده می‌شود تا فراخواننده دو مسیر جداگانه
        برای ذخیره‌سازی نداشته باشد.

        پیاده‌سازی پیش‌فرض عمداً جریانی نیست: یک بار `generate()` را صدا
        می‌زند و کل متن را به‌عنوان یک تکه می‌دهد. این یعنی هر سرویسی —
        حتی بدون پشتیبانی از stream — از همین مسیر قابل استفاده است و
        لایهٔ بالاتر لازم نیست شرط بگذارد.
        """
        response = await self.generate(messages, temperature=temperature)
        if response.content:
            on_chunk(response.content)
        return response

    async def close(self) -> None:
        """آزادسازی منابع شبکه؛ پیاده‌سازی پیش‌فرض کاری نمی‌کند."""
        return None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} name={self.name} model={self.model}>"
