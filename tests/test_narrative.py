"""
آزمون‌های نویسندهٔ تحلیل نوشتاری فارسی.

مهم‌ترین نکته‌ای که این آزمون‌ها تضمین می‌کنند: **هیچ سیگنالی بدون تحلیل
نوشتاری نمی‌ماند**، حتی وقتی سرویس هوش مصنوعی خطا بدهد، کند باشد یا اصلاً
وجود نداشته باشد.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from ai.agent.narrative import NarrativeWriter, _fa, _is_mostly_latin


def make_signal(**overrides):
    """ساخت یک سیگنال نمونه برای آزمون."""
    data = {
        "symbol": "BTC/USDT",
        "direction": SimpleNamespace(value="LONG"),
        "confidence": 72,
        "entry_min": 78500.0,
        "entry_max": 79200.0,
        "stop_loss": 76400.0,
        "take_profits": [81000.0, 83000.0],
        "risk_reward": 2.4,
        "leverage": 3,
        "trend": SimpleNamespace(value="BULLISH"),
        "market_structure": SimpleNamespace(value="UPTREND"),
        "timeframes": ["1d", "4h", "1h"],
        "indicators_used": ["RSI", "MACD"],
        "reason": "دلیل فارسی موتور",
        "invalidation": "شکست حمایت",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


# ---------------------------------------------------------------------------
# متن قالبی
# ---------------------------------------------------------------------------
def test_template_has_all_four_sections() -> None:
    """متن قالبی همیشه هر چهار بخش را دارد."""
    text = NarrativeWriter(None).template_narrative(make_signal())
    for heading in ("## خلاصه", "## دلایل فنی", "## سطوح کلیدی و سناریوها", "## مدیریت ریسک"):
        assert heading in text


def test_template_uses_real_numbers() -> None:
    """اعداد واقعی سیگنال در متن می‌آیند، نه عدد ساختگی."""
    text = NarrativeWriter(None).template_narrative(make_signal())
    assert _fa(78500.0) in text
    assert _fa(76400.0) in text
    assert _fa(2.4) in text


def test_wait_signal_explains_waiting() -> None:
    """برای WAIT باید صادقانه دلیل صبر توضیح داده شود."""
    signal = make_signal(direction=SimpleNamespace(value="WAIT"), confidence=20)
    text = NarrativeWriter(None).template_narrative(signal)
    assert "انتظار" in text
    assert "صبر" in text


def test_english_engine_reason_moves_to_appendix() -> None:
    """
    دلیل انگلیسی موتور نباید وسط متن فارسی بیاید.

    باید در بخش «گزارش فنی موتور تحلیل» جدا شود تا متن فارسی روان بماند
    ولی هیچ اطلاعاتی هم گم نشود.
    """
    signal = make_signal(reason="Analytical factors are not aligned enough (score +0.15).")
    text = NarrativeWriter(None).template_narrative(signal)
    assert "## گزارش فنی موتور تحلیل" in text
    assert "Analytical factors" in text
    assert "Analytical factors" not in text.split("## گزارش فنی موتور تحلیل")[0]


def test_persian_engine_reason_stays_inline() -> None:
    """دلیل فارسی موتور مستقیم در بخش دلایل فنی می‌آید."""
    text = NarrativeWriter(None).template_narrative(make_signal(reason="روند صعودی تأیید شد"))
    assert "روند صعودی تأیید شد" in text
    assert "## گزارش فنی موتور تحلیل" not in text


def test_template_survives_empty_signal() -> None:
    """سیگنال بدون هیچ عددی هم باید متن معتبر بدهد."""
    text = NarrativeWriter(None).template_narrative(SimpleNamespace(symbol="X/USDT"))
    assert "## خلاصه" in text
    assert len(text) > 100


# ---------------------------------------------------------------------------
# مسیر هوش مصنوعی و بازگشت امن
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_write_without_provider_uses_template() -> None:
    """بدون سرویس هوش مصنوعی، متن قالبی برمی‌گردد."""
    text, source = await NarrativeWriter(None).write(make_signal(), {})
    assert source == "template"
    assert "## خلاصه" in text


@pytest.mark.asyncio
async def test_write_uses_ai_when_available() -> None:
    """اگر سرویس پاسخ خوب بدهد، همان متن استفاده می‌شود."""

    class Provider:
        async def generate(self, messages, **kwargs):
            return SimpleNamespace(content="## خلاصه\n\n" + "متن هوش مصنوعی. " * 20)

    text, source = await NarrativeWriter(Provider()).write(make_signal(), {})
    assert source == "ai"
    assert "متن هوش مصنوعی" in text


@pytest.mark.asyncio
async def test_ai_failure_falls_back_to_template() -> None:
    """خطای سرویس نباید سیگنال را بی‌تحلیل بگذارد."""

    class Broken:
        async def generate(self, messages, **kwargs):
            raise RuntimeError("no credit")

    text, source = await NarrativeWriter(Broken()).write(make_signal(), {})
    assert source == "template"
    assert "## خلاصه" in text


@pytest.mark.asyncio
async def test_ai_timeout_falls_back_to_template() -> None:
    """کندی سرویس نباید کاربر را معطل نگه دارد."""

    class Slow:
        async def generate(self, messages, **kwargs):
            await asyncio.sleep(5)
            return SimpleNamespace(content="دیر رسید")

    writer = NarrativeWriter(Slow(), timeout_seconds=0.2)
    text, source = await writer.write(make_signal(), {})
    assert source == "template"
    assert "## خلاصه" in text


@pytest.mark.asyncio
async def test_short_ai_reply_falls_back() -> None:
    """پاسخ خیلی کوتاه هوش مصنوعی قابل قبول نیست."""

    class Terse:
        async def generate(self, messages, **kwargs):
            return SimpleNamespace(content="باشه")

    text, source = await NarrativeWriter(Terse()).write(make_signal(), {})
    assert source == "template"


@pytest.mark.asyncio
async def test_none_response_falls_back() -> None:
    """پاسخ None هم باید امن مدیریت شود."""

    class Empty:
        async def generate(self, messages, **kwargs):
            return None

    _text, source = await NarrativeWriter(Empty()).write(make_signal(), {})
    assert source == "template"


@pytest.mark.asyncio
async def test_prefer_ai_false_skips_provider() -> None:
    """با prefer_ai=False اصلاً سراغ سرویس نمی‌رویم."""
    called = []

    class Provider:
        async def generate(self, messages, **kwargs):
            called.append(1)
            return SimpleNamespace(content="x" * 200)

    _text, source = await NarrativeWriter(Provider()).write(make_signal(), {}, prefer_ai=False)
    assert source == "template"
    assert called == []


# ---------------------------------------------------------------------------
# ساخت پرامپت
# ---------------------------------------------------------------------------
def test_prompt_contains_signal_facts() -> None:
    """پرامپت باید اعداد واقعی را به مدل بدهد تا چیزی از خودش نسازد."""
    prompt = NarrativeWriter(None).build_prompt(make_signal(), {})
    assert "BTC/USDT" in prompt
    assert "LONG" in prompt
    assert _fa(76400.0) in prompt


def test_prompt_includes_indicator_values() -> None:
    """مقادیر اندیکاتور از دادهٔ بازار وارد پرامپت می‌شوند."""
    market_data = {"timeframes": {"4h": {"indicators": {"rsi": 62.5, "adx": 28.0}}}}
    prompt = NarrativeWriter(None).build_prompt(make_signal(), market_data)
    assert "rsi=" in prompt
    assert "4h" in prompt


# ---------------------------------------------------------------------------
# کمکی‌ها
# ---------------------------------------------------------------------------
def test_is_mostly_latin() -> None:
    """تشخیص متن انگلیسی از فارسی."""
    assert _is_mostly_latin("Waiting is the safer choice") is True
    assert _is_mostly_latin("روند صعودی است") is False
    assert _is_mostly_latin("") is False
    assert _is_mostly_latin("۱۲۳ ۴۵۶") is False


def test_fa_converts_digits() -> None:
    """اعداد با ارقام فارسی نمایش داده می‌شوند."""
    assert _fa(1234.5) == "۱٬۲۳۴٫۵۰".replace("٬", ",").replace("٫", ".")
    assert _fa(0) == "۰"


def test_fa_handles_non_numeric() -> None:
    """ورودی غیرعددی باید سالم برگردد."""
    assert _fa("نامشخص") == "نامشخص"
