"""
آزمون‌های لایه ارائه‌دهندگان هوش مصنوعی.

این آزمون‌ها سه ایراد واقعی گزارش‌شده را پوشش می‌دهند:
    ۱) «Ollama روی سیستم اجراست ولی برنامه وصل نمی‌شود»
    ۲) «مدل‌های رایگان اول، بعد مدل‌های پولی»
    ۳) پیام خطای سرویس باید واقعی و قابل فهم باشد، نه فقط یک کد HTTP

هیچ درخواست شبکه‌ای واقعی انجام نمی‌شود؛ همه چیز با انتقال‌دهنده ساختگی
httpx شبیه‌سازی می‌گردد تا آزمون‌ها آفلاین و سریع بمانند.
"""

from __future__ import annotations

import json

import httpx
import pytest

from ai.providers.base import AIMessage, AIProviderConfig
from ai.providers.free_models import (
    TIER_FREE,
    TIER_LOW_COST,
    TIER_PAID,
    classify_model,
    free_models,
    known_free_models,
    pick_default_model,
    sort_models,
)
from ai.providers.ollama_provider import (
    DEFAULT_OLLAMA_URL,
    OllamaProvider,
    host_candidates,
    model_matches,
)
from ai.providers.openai_compatible import OpenAICompatibleProvider, uses_completion_tokens
from app.exceptions import AIProviderError, AuthenticationError


# ======================================================================
# تفکیک مدل‌های رایگان
# ======================================================================
def test_local_provider_models_are_always_free() -> None:
    """مدل محلی هزینه‌ای ندارد، هر نامی که داشته باشد."""
    assert classify_model("llama3.1:70b", "ollama") == TIER_FREE
    assert classify_model("anything", "lmstudio") == TIER_FREE


def test_explicit_free_marker_wins() -> None:
    """پسوند :free اعلام خود سرویس است و بر هر حدسی مقدم است."""
    assert classify_model("google/gemma-4-31b-it:free", "openrouter") == TIER_FREE
    # همان مدل بدون پسوند، رایگان نیست
    assert classify_model("google/gemma-4-31b-it", "openrouter") != TIER_FREE


def test_expensive_models_are_marked_paid() -> None:
    """مدل‌های گران نباید در دسته رایگان بیفتند."""
    assert classify_model("gpt-5-pro", "openai") == TIER_PAID
    assert classify_model("claude-3-opus", "anthropic") == TIER_PAID


def test_cheap_models_are_low_cost_not_free() -> None:
    """
    مدل ارزان با مدل رایگان فرق دارد.

    اشتباه گرفتن این دو یعنی کاربر ناخواسته هزینه می‌دهد.
    """
    assert classify_model("gpt-4o-mini", "openai") == TIER_LOW_COST
    assert classify_model("gpt-5-nano", "openai") == TIER_LOW_COST


def test_free_tier_provider_small_models_are_free() -> None:
    """مدل‌های کوچک سرویس‌های دارای سطح رایگان، رایگان حساب می‌شوند."""
    assert classify_model("gemini-2.0-flash", "google") == TIER_FREE
    assert classify_model("llama-3.1-8b-instant", "groq") == TIER_FREE


def test_sorting_puts_free_models_first() -> None:
    """ترتیبی که کاربر خواست: اول رایگان، بعد پولی."""
    models = ["gpt-5-pro", "gpt-4o-mini", "google/gemma-4-31b-it:free"]
    ordered = [info.name for info in sort_models(models, "openrouter")]
    assert ordered[0] == "google/gemma-4-31b-it:free"
    assert ordered[-1] == "gpt-5-pro"


def test_pick_default_prefers_free() -> None:
    """انتخاب خودکار باید رایگان‌ترین گزینه را بردارد."""
    models = ["gpt-5-pro", "llama-3.1-8b-instant"]
    assert pick_default_model(models, "groq") == "llama-3.1-8b-instant"


def test_free_models_filter() -> None:
    """فیلتر رایگان فقط باید مدل‌های بی‌هزینه بدهد."""
    models = ["gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"]
    assert free_models(models, "google") == ["gemini-1.5-flash", "gemini-2.0-flash"]


def test_large_model_is_not_mistaken_for_small() -> None:
    """
    دام واقعی: رشته «31b» شامل «1b» است.

    بدون مقایسه کلمه‌ای، یک مدل ۳۱ میلیاردی «کوچک و رایگان» برچسب می‌خورد.
    """
    assert classify_model("google/gemma-4-31b-it", "openrouter") != TIER_FREE
    assert classify_model("qwen-72b", "together") != TIER_FREE
    # ولی مدل واقعاً کوچک باید تشخیص داده شود
    assert classify_model("llama-3.1-8b", "groq") == TIER_FREE


def test_known_free_models_exist_for_main_providers() -> None:
    """برای سرویس‌های اصلی باید پیشنهاد رایگان آماده داشته باشیم."""
    for provider in ("groq", "google", "openrouter", "ollama"):
        assert known_free_models(provider), f"no free models listed for {provider}"


def test_model_label_shows_tier() -> None:
    """برچسب فارسی باید کنار نام مدل بیاید."""
    info = sort_models(["gemini-2.0-flash"], "google")[0]
    assert "رایگان" in info.label("fa")
    assert "free" in info.label("en")


# ======================================================================
# Ollama — ایراد «اجرا هست ولی وصل نمی‌شود»
# ======================================================================
def test_model_matching_ignores_tag() -> None:
    """`llama3.1` و `llama3.1:8b` باید یکی حساب شوند."""
    assert model_matches("llama3.1", "llama3.1:8b")
    assert model_matches("qwen2.5:7b", "qwen2.5:7b")
    assert not model_matches("llama3.1", "gemma2:9b")


def test_host_candidates_include_loopback_swap() -> None:
    """
    روی ویندوز localhost گاهی به IPv6 می‌رود و Ollama آنجا گوش نمی‌دهد.

    پس هر دو نشانی باید امتحان شوند.
    """
    candidates = host_candidates("http://localhost:11434")
    assert "http://localhost:11434" in candidates
    assert "http://127.0.0.1:11434" in candidates


def test_host_candidates_handle_missing_scheme() -> None:
    """اگر کاربر فقط میزبان را بنویسد، باید اصلاح شود."""
    assert host_candidates("127.0.0.1:11434")[0].startswith("http://")


def test_empty_base_url_falls_back_to_default() -> None:
    """نشانی خالی نباید باعث خطای مبهم شود."""
    config = AIProviderConfig(name="ollama", base_url="", model="qwen2.5")
    OllamaProvider(config)
    assert config.base_url == DEFAULT_OLLAMA_URL


def _ollama_transport(installed: list[str], *, chat_ok: bool = True) -> httpx.MockTransport:
    """ساخت سرویس Ollama ساختگی."""

    def handler(request: httpx.Request) -> httpx.Response:
        """پاسخ به مسیرهای Ollama."""
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": name} for name in installed]})
        if request.url.path == "/api/chat":
            if not chat_ok:
                return httpx.Response(404, json={"error": "model not found"})
            payload = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "model": payload["model"],
                    "message": {"role": "assistant", "content": "PONG"},
                    "done": True,
                },
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


class _StubbedOllama(OllamaProvider):
    """نسخه‌ای از ارائه‌دهنده که به سرویس ساختگی وصل می‌شود."""

    def __init__(self, config: AIProviderConfig, transport: httpx.MockTransport) -> None:
        super().__init__(config)
        self._transport = transport

    async def _resolve_base_url(self) -> str:
        """در آزمون، جست‌وجوی میزبان لازم نیست."""
        return DEFAULT_OLLAMA_URL

    async def _get_client(self) -> httpx.AsyncClient:
        """کلاینت متصل به انتقال‌دهنده ساختگی."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=DEFAULT_OLLAMA_URL, transport=self._transport
            )
        return self._client


@pytest.mark.asyncio
async def test_missing_model_falls_back_to_installed_one() -> None:
    """
    ایراد اصلی گزارش‌شده.

    پیش‌فرض برنامه `llama3.1` بود؛ اگر کاربر مدل دیگری نصب کرده باشد،
    برنامه باید از همان استفاده کند نه اینکه شکست بخورد.
    """
    config = AIProviderConfig(name="ollama", base_url=DEFAULT_OLLAMA_URL, model="llama3.1")
    provider = _StubbedOllama(config, _ollama_transport(["qwen2.5:7b", "gemma2:9b"]))

    ok, detail = await provider.is_available()
    assert ok, detail
    # فهرست مرتب برمی‌گردد، پس نخستین مدل نصب‌شده انتخاب می‌شود
    assert await provider.resolve_model() == "gemma2:9b"

    response = await provider.generate([AIMessage(role="user", content="hi")])
    assert response.content == "PONG"
    await provider.close()


@pytest.mark.asyncio
async def test_configured_model_is_used_when_installed() -> None:
    """اگر مدل خواسته‌شده نصب باشد، نباید عوض شود."""
    config = AIProviderConfig(name="ollama", base_url=DEFAULT_OLLAMA_URL, model="gemma2:9b")
    provider = _StubbedOllama(config, _ollama_transport(["qwen2.5:7b", "gemma2:9b"]))
    assert await provider.resolve_model() == "gemma2:9b"
    await provider.close()


@pytest.mark.asyncio
async def test_no_installed_model_reports_actionable_message() -> None:
    """پیام باید بگوید کاربر دقیقاً چه کند."""
    config = AIProviderConfig(name="ollama", base_url=DEFAULT_OLLAMA_URL, model="llama3.1")
    provider = _StubbedOllama(config, _ollama_transport([]))
    ok, detail = await provider.is_available()
    assert not ok
    assert "pull" in detail.lower()
    await provider.close()


@pytest.mark.asyncio
async def test_ollama_never_requires_api_key() -> None:
    """سرویس محلی نباید کلید بخواهد."""
    config = AIProviderConfig(name="ollama", base_url=DEFAULT_OLLAMA_URL, model="x", requires_api_key=True)
    OllamaProvider(config)
    assert config.requires_api_key is False


# ======================================================================
# سرویس‌های سازگار با OpenAI
# ======================================================================
def test_new_models_need_completion_tokens() -> None:
    """مدل‌های نسل جدید پارامتر توکن متفاوتی می‌خواهند."""
    assert uses_completion_tokens("gpt-5-nano")
    assert uses_completion_tokens("o3-mini")
    assert not uses_completion_tokens("gpt-4o-mini")


def _openai_transport(status: int, payload: dict) -> httpx.MockTransport:
    """سرویس سازگار با OpenAI ساختگی."""

    def handler(request: httpx.Request) -> httpx.Response:
        """پاسخ ثابت به هر درخواست."""
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


class _StubbedOpenAI(OpenAICompatibleProvider):
    """ارائه‌دهنده متصل به انتقال‌دهنده ساختگی."""

    def __init__(self, config: AIProviderConfig, transport: httpx.MockTransport, key: str = "k") -> None:
        super().__init__(config, key)
        self._transport = transport

    async def _get_client(self) -> httpx.AsyncClient:
        """کلاینت آزمون."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._config.base_url, transport=self._transport
            )
        return self._client


@pytest.mark.asyncio
async def test_exhausted_credit_is_reported_distinctly() -> None:
    """
    «اعتبار تمام شده» با «محدودیت سرعت» فرق دارد.

    این دقیقاً وضعیت کلید فعلی کاربر است و پیام باید گویا باشد.
    """
    payload = {
        "error": {
            "message": "You have no credits remaining.",
            "type": "insufficient_quota",
            "code": "credit_balance_exhausted",
        }
    }
    config = AIProviderConfig(name="openai", base_url="https://api.openai.com/v1", model="gpt-4o-mini")
    provider = _StubbedOpenAI(config, _openai_transport(429, payload))

    with pytest.raises(AIProviderError) as info:
        await provider.generate([AIMessage(role="user", content="hi")])
    assert "credit" in str(info.value).lower()
    assert info.value.details.get("reason") == "insufficient_quota"
    await provider.close()


@pytest.mark.asyncio
async def test_invalid_key_raises_authentication_error() -> None:
    """کلید نامعتبر باید خطای احراز هویت بدهد، نه خطای عمومی."""
    payload = {"error": {"message": "Incorrect API key provided"}}
    config = AIProviderConfig(name="openai", base_url="https://api.openai.com/v1", model="gpt-4o-mini")
    provider = _StubbedOpenAI(config, _openai_transport(401, payload))

    with pytest.raises(AuthenticationError):
        await provider.generate([AIMessage(role="user", content="hi")])
    await provider.close()


@pytest.mark.asyncio
async def test_missing_key_is_caught_before_network() -> None:
    """بدون کلید نباید اصلاً درخواستی فرستاده شود."""
    config = AIProviderConfig(name="openai", base_url="https://api.openai.com/v1", model="gpt-4o-mini")
    provider = OpenAICompatibleProvider(config, None)
    ok, detail = await provider.is_available()
    assert not ok
    assert "key" in detail.lower()


@pytest.mark.asyncio
async def test_missing_base_url_is_reported() -> None:
    """سرویس سفارشی بدون نشانی باید پیام روشن بدهد."""
    config = AIProviderConfig(name="custom", base_url="", model="x", requires_api_key=False)
    provider = OpenAICompatibleProvider(config, None)
    ok, detail = await provider.is_available()
    assert not ok
    assert "base url" in detail.lower()


@pytest.mark.asyncio
async def test_successful_generation_is_parsed() -> None:
    """پاسخ موفق باید درست خوانده شود."""
    payload = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2},
    }
    config = AIProviderConfig(name="openai", base_url="https://api.openai.com/v1", model="gpt-4o-mini")
    provider = _StubbedOpenAI(config, _openai_transport(200, payload))
    response = await provider.generate([AIMessage(role="user", content="hi")])
    assert response.content == "hello"
    assert response.prompt_tokens == 5
    await provider.close()


@pytest.mark.asyncio
async def test_error_returned_with_status_200_is_detected() -> None:
    """برخی درگاه‌ها خطا را با کد ۲۰۰ برمی‌گردانند؛ نباید نادیده بماند."""
    config = AIProviderConfig(name="custom", base_url="https://x.test/v1", model="m")
    provider = _StubbedOpenAI(config, _openai_transport(200, {"error": {"message": "boom"}}))
    with pytest.raises(AIProviderError):
        await provider.generate([AIMessage(role="user", content="hi")])
    await provider.close()
