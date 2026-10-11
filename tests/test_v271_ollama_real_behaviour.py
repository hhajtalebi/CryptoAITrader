"""
نسخهٔ ۲.۷.۱ — آزمونِ اولاما در برابر **سرویس واقعی** (نه بدل).

چرا این فایل جدا است؟
    فایل `test_v271_ai_reliability.py` با یک سرویس HTTP ساختگی کار می‌کند که
    پروتکل اولاما را حرف می‌زند. آن آزمون‌ها همیشه اجرا می‌شوند ولی **نمی‌توانند**
    ثابت کنند اولامای واقعی روی دستگاه کاربر جواب می‌دهد. این فایل دقیقاً همان
    شکاف را هدف می‌گیرد: اگر اولاما روی دستگاه نصب و در حال اجرا باشد، این
    آزمون‌ها واقعاً به آن وصل می‌شوند و یک پاسخ واقعی می‌گیرند.

رفتار هنگام نبودِ سرویس:
    آزمون‌ها **نادیده گرفته (skip)** می‌شوند، نه «پاس» و نه «رد». این عمدی است:
    نبودِ اولاما نقصِ برنامه نیست و نباید در گزارشِ کاربر به‌عنوان موفقیت یا
    شکستِ کدِ برنامه دیده شود. پیامِ skip دقیق می‌گوید چه چیزی کم است.

نحوهٔ اجرا روی دستگاه خودتان (ویندوز)::

    ollama serve
    ollama pull qwen2.5:7b-instruct
    venv\\Scripts\\python -m pytest tests\\test_v271_ollama_real_behaviour.py -v -s

اگر مدلِ دیگری نصب دارید، نامش را با متغیر محیطی بدهید::

    set CAI_OLLAMA_MODEL=qwen2.5:7b          :: ویندوز
    export CAI_OLLAMA_MODEL=qwen2.5:7b       :: لینوکس/مک

نکتهٔ صداقت: این آزمون‌ها در محیط توسعهٔ ما اجرا **نشدند**، چون اولاما در آن
محیط نصب نبود. وجودشان به‌معنای تأییدِ رفتار روی دستگاه شما نیست؛ وسیله‌ای است
تا خودتان آن را تأیید کنید.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import pytest

from ai.agent.autonomous_agent import AutonomousAgent
from ai.providers.base import AIProviderConfig, AIMessage
from ai.providers.ollama_provider import OllamaProvider

#: نشانی پیش‌فرضِ اولاما؛ با متغیر محیطی قابل تغییر است
OLLAMA_URL = os.environ.get("CAI_OLLAMA_URL", "http://127.0.0.1:11434")
#: مدلی که انتظار داریم نصب باشد
MODEL = os.environ.get("CAI_OLLAMA_MODEL", "qwen2.5:7b-instruct")


def _provider(**kwargs: Any) -> OllamaProvider:
    """یک نمونهٔ اولاما با پیکربندیِ کمینه برای این آزمون‌ها."""
    config = AIProviderConfig(
        name="ollama",
        base_url=OLLAMA_URL,
        model=kwargs.pop("model", MODEL),
        timeout=kwargs.pop("timeout", 180),
        max_tokens=kwargs.pop("max_tokens", 800),
        extra=kwargs.pop("extra", {"max_context": 0}),
    )
    return OllamaProvider(config)


async def _require_ollama() -> OllamaProvider:
    """اگر اولاما در دسترس نباشد آزمون را نادیده بگیر و دلیلش را بگو."""
    provider = _provider(timeout=15)
    try:
        ok, message = await provider.is_available()
    except Exception as exc:  # noqa: BLE001 - هر خطایی یعنی سرویس در دسترس نیست
        pytest.skip(f"اولاما در دسترس نیست ({type(exc).__name__}: {exc})")
    if not ok:
        pytest.skip(f"اولاما آماده نیست: {message}")
    return provider


# ---------------------------------------------------------------------------
# ۱) سه پرسشِ جدا: سرویس بالاست؟ مدل نصب است؟ پاسخ واقعی می‌آید؟
# ---------------------------------------------------------------------------
class TestRealOllamaService:
    async def test_service_answers_and_lists_models(self) -> None:
        """/api/tags باید دست‌کم یک مدل نصب‌شده برگرداند."""
        provider = await _require_ollama()
        models = await provider.list_models()
        assert models, "سرویس بالاست ولی هیچ مدلی نصب نیست (ollama pull …)"

    async def test_probe_generation_reports_model_and_latency(self) -> None:
        """آزمایش اتصال باید یک پاسخ واقعی بگیرد و زمانش را گزارش کند.

        این همان چیزی است که دکمهٔ «آزمایش اتصال» در تنظیمات نشان می‌دهد.
        اگر زمان یا نام مدل در پیام نباشد، کاربر نمی‌تواند تشخیص دهد مدل
        واقعاً بارگذاری شده یا فقط پورت باز بوده است.
        """
        provider = await _require_ollama()
        ok, message = await provider.probe_generation()
        assert ok, f"تولیدِ آزمایشی شکست خورد: {message}"
        assert provider.active_model, "نام مدلِ واقعاً استفاده‌شده مشخص نیست"
        assert re.search(r"\d", message), f"زمان پاسخ در پیام نیست: {message}"

    async def test_real_generation_returns_non_empty_text(self) -> None:
        """یک پاسخ واقعی و غیرخالی از مدلِ نصب‌شده."""
        provider = await _require_ollama()
        response = await provider.generate(
            [AIMessage(role="user", content="Say exactly one word: OK")]
        )
        assert response.content.strip(), "مدل پاسخ خالی برگرداند"
        assert response.model, "نام مدل در پاسخ نبود"

    async def test_json_mode_yields_parseable_json(self) -> None:
        """در حالت JSON، خروجی باید قابل‌تجزیه باشد.

        شکستِ این آزمون با وجودِ سرویسِ سالم یعنی قالبِ JSON واقعاً به
        اولاما نمی‌رسد یا پارامتر نادیده گرفته می‌شود — همان چیزی که در
        ۲.۷.۱ با پیامِ وضعیت «قالب JSON فعال شد» قابل‌ردیابی شد.
        """
        provider = await _require_ollama()
        response = await provider.generate(
            [
                AIMessage(role="system", content="Answer with JSON only."),
                AIMessage(
                    role="user",
                    content='Return {"signal":"WAIT","confidence":40,"reason":"test"}',
                ),
            ],
            json_mode=True,
        )
        text = (response.content or "").strip()
        try:
            json.loads(text)
            return
        except json.JSONDecodeError:
            pass
        # مدل‌های کوچک گاهی توضیح دورِ JSON می‌نویسند؛ استخراجِ نخستین
        # شیء همان کاری است که عامل خودمختار انجام می‌دهد.
        parsed = AutonomousAgent._extract_first_json_object(text)
        assert parsed is not None, f"هیچ شیء JSON ی در پاسخ نبود: {text[:300]}"

    async def test_unknown_model_is_reported_not_silently_swapped(self) -> None:
        """اگر مدلِ درخواستی نصب نباشد، باید مدلِ جایگزین **اعلام** شود.

        پنهان‌کردنِ این تعویض همان چیزی است که باعث می‌شد کاربر گمان کند
        تحلیل با مدلِ انتخابیِ او انجام شده است.

        نخست سرویس را لازم می‌دانیم تا این آزمون در نبودِ اولاما بی‌صدا
        «پاس» نشود (در آن حالت اصلاً چیزی برای آزمودن نیست).
        """
        await _require_ollama()
        provider = _provider(model="definitely-not-installed-2.7.1", timeout=30)
        try:
            ok, message = await provider.is_available()
        except Exception:  # noqa: BLE001 - سرویس نبود؛ آزمون بی‌معناست
            pytest.skip("اولاما در دسترس نیست")
        if ok:
            assert "using installed model" in message.lower(), (
                f"تعویضِ مدل اعلام نشد: {message}"
            )

    async def test_changing_config_invalidates_sticky_state(self) -> None:
        """تغییرِ پیکربندی باید وضعیتِ چسبنده را پاک کند.

        این آزمون به سرویس نیاز ندارد (فقط حافظهٔ نمونه را می‌سنجد) ولی
        در این فایل است چون مکملِ رفتارِ واقعیِ اولاماست.
        """
        provider = await _require_ollama()
        provider._session_ctx = 4096  # noqa: SLF001 - حالتِ درونی برای آزمون
        provider._thinking_off.add("qwen2.5:7b")  # noqa: SLF001
        fresh = AIProviderConfig(
            name="ollama",
            base_url=OLLAMA_URL,
            model=MODEL,
            timeout=180,
            max_tokens=800,
        )
        provider.update_config(fresh)
        assert provider._session_ctx == 0  # noqa: SLF001
        assert not provider._thinking_off  # noqa: SLF001
        assert provider._resolved_model == ""  # noqa: SLF001
