"""
فهرست ارائه‌دهنده‌های هوش مصنوعی پشتیبانی‌شده.

بیشتر سرویس‌های امروزی از قرارداد «سازگار با OpenAI» استفاده می‌کنند، پس
افزودن یک سرویس تازه معمولاً فقط یک ردیف در این فهرست است و نیازی به کد
جدید ندارد.

هر ورودی می‌گوید: نشانی پایه کجاست، چه مدل‌هایی معمول‌اند، آیا کلید API
لازم دارد، و مدل‌هایش را چگونه می‌توان از خود سرویس پرسید.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProviderPreset:
    """
    پیکربندی آماده یک ارائه‌دهنده.

    فیلدها:
        key            : شناسه یکتای داخلی
        display_name   : نامی که در تنظیمات دیده می‌شود
        provider_type  : `ollama` یا `openai_compatible`
        base_url       : نشانی پایه API
        requires_key   : آیا بدون کلید کار نمی‌کند
        suggested_models: مدل‌های پرکاربرد برای پر کردن فهرست کشویی
        supports_model_listing: آیا می‌توان فهرست مدل‌ها را از خود سرویس گرفت
        signup_url     : جایی که کاربر کلید می‌گیرد
        notes          : توضیح کوتاه فارسی برای نمایش در رابط کاربری
    """

    key: str
    display_name: str
    provider_type: str
    base_url: str
    requires_key: bool = True
    suggested_models: tuple[str, ...] = field(default_factory=tuple)
    supports_model_listing: bool = True
    signup_url: str = ""
    notes: str = ""
    is_local: bool = False
    #: کلید اجباری نیست ولی اگر داده شود استفاده می‌شود.
    #: بدون این فیلد، فیلد کلید در تنظیمات «غیرفعال» می‌شد و کاربرِ
    #: دروازه‌ای که احراز هویت را روشن کرده راهی برای وارد کردن کلیدش
    #: نداشت. `requires_key=False` یعنی «بدون کلید هم کار می‌کند»، نه
    #: «کلید نمی‌پذیرد» — این دو تا اینجا با هم قاطی شده بودند.
    accepts_optional_key: bool = False

    @property
    def key_field_enabled(self) -> bool:
        """آیا کادر کلید API باید در تنظیمات قابل تایپ باشد؟"""
        return self.requires_key or self.accepts_optional_key


#: فهرست ارائه‌دهنده‌ها — ترتیب همان ترتیب نمایش در تنظیمات است
PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        key="ollama",
        display_name="Ollama (محلی)",
        provider_type="ollama",
        base_url="http://localhost:11434",
        requires_key=False,
        suggested_models=("llama3.1", "llama3.2", "qwen2.5", "mistral", "gemma2", "phi3", "deepseek-r1"),
        signup_url="https://ollama.com/download",
        notes="روی سیستم خودتان اجرا می‌شود؛ رایگان و بدون نیاز به کلید. حریم خصوصی کامل.",
        is_local=True,
    ),
    ProviderPreset(
        key="lmstudio",
        display_name="LM Studio (محلی)",
        provider_type="openai_compatible",
        base_url="http://localhost:1234/v1",
        requires_key=False,
        suggested_models=(),
        signup_url="https://lmstudio.ai",
        notes="سرور محلی سازگار با OpenAI؛ مدل را در خود LM Studio بارگذاری کنید.",
        is_local=True,
        accepts_optional_key=True,
    ),
    ProviderPreset(
        key="omniroute",
        display_name="OmniRoute (دروازه چندسرویسی)",
        provider_type="omniroute",
        base_url="http://localhost:20128/v1",
        # کلید اختیاری است: نصب تازهٔ OmniRoute تا وقتی REQUIRE_API_KEY را
        # روشن نکرده‌اید بدون کلید هم پاسخ می‌دهد. با علامت‌زدن «نیازمند
        # کلید»، کاربرِ نصب پیش‌فرض بی‌دلیل پشت یک فیلد اجباری گیر می‌کرد.
        requires_key=False,
        suggested_models=(
            "auto",
            "if/kimi-k2-thinking",
            "cc/claude-opus-4-6",
            "gg/gemini-2.5-pro",
            "glm/glm-4.7",
            "groq/llama-3.3-70b",
        ),
        signup_url="https://github.com/diegosouzapw/OmniRoute",
        notes=(
            "یک دروازه که کلید همهٔ سرویس‌های شما را یک‌جا نگه می‌دارد و "
            "درخواست را خودکار به سرویس در دسترس می‌فرستد. مدل «auto» را "
            "انتخاب کنید تا خود دروازه بهترین گزینه را بردارد. پیش از "
            "استفاده، دروازه را با فرمان omniroute اجرا کنید."
        ),
        is_local=True,
        accepts_optional_key=True,
    ),
    ProviderPreset(
        key="openai",
        display_name="OpenAI",
        provider_type="openai_compatible",
        base_url="https://api.openai.com/v1",
        suggested_models=("gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o3-mini"),
        signup_url="https://platform.openai.com/api-keys",
        notes="کیفیت بالا برای تحلیل؛ نیازمند کلید و اعتبار.",
    ),
    ProviderPreset(
        key="ashna",
        display_name="آشنا هوش مصنوعی (AshnaAI)",
        provider_type="openai_compatible",
        # نکتهٔ مهم: مسیر پایه `/v1/api` است، نه `/v1`. کلاینت خودش
        # `/chat/completions` و `/models` را به آن می‌چسباند. اگر کسی
        # `/v1` بگذارد، همهٔ درخواست‌ها ۴۰۴ می‌گیرند.
        base_url="https://api.ashna.ai/v1/api",
        suggested_models=(
            "ashna-x1",
            "gpt-4o-mini",
            "claude-sonnet-5",
            "gemini-3.1-Pro",
            "deepseek-v4-flash",
            "glm-5.3-flash",
            "kimi-k3",
            "grok-4.3",
        ),
        signup_url="https://app.ashna.ai/account?tab=api",
        notes=(
            "دروازهٔ چندمدلی سازگار با OpenAI. با یک کلید به مدل‌های "
            "OpenAI، Claude، Gemini، DeepSeek، GLM، Kimi و Grok دسترسی "
            "می‌دهد. می‌توانید شناسهٔ «ایجنت» ساختهٔ خودتان را هم به‌جای "
            "نام مدل بنویسید تا با همان دستورها و ابزارها اجرا شود."
        ),
    ),
    ProviderPreset(
        key="openrouter",
        display_name="OpenRouter",
        provider_type="openai_compatible",
        base_url="https://openrouter.ai/api/v1",
        suggested_models=(
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o",
            "google/gemini-2.0-flash-exp:free",
            "deepseek/deepseek-chat",
            "meta-llama/llama-3.3-70b-instruct",
        ),
        signup_url="https://openrouter.ai/keys",
        notes="با یک کلید به ده‌ها مدل مختلف دسترسی می‌دهد؛ چند مدل رایگان هم دارد.",
    ),
    ProviderPreset(
        key="deepseek",
        display_name="DeepSeek",
        provider_type="openai_compatible",
        base_url="https://api.deepseek.com/v1",
        suggested_models=("deepseek-chat", "deepseek-reasoner"),
        signup_url="https://platform.deepseek.com/api_keys",
        notes="ارزان و برای استدلال تحلیلی مناسب.",
    ),
    ProviderPreset(
        key="groq",
        display_name="Groq",
        provider_type="openai_compatible",
        base_url="https://api.groq.com/openai/v1",
        suggested_models=(
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ),
        signup_url="https://console.groq.com/keys",
        notes="بسیار سریع؛ سطح رایگان سخاوتمندانه دارد.",
    ),
    ProviderPreset(
        key="google",
        display_name="Google Gemini",
        provider_type="openai_compatible",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        suggested_models=("gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"),
        signup_url="https://aistudio.google.com/apikey",
        notes="سطح رایگان دارد و برای تحلیل چندتایم‌فریمی مناسب است.",
    ),
    ProviderPreset(
        key="anthropic",
        display_name="Anthropic Claude",
        provider_type="openai_compatible",
        base_url="https://api.anthropic.com/v1",
        suggested_models=("claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"),
        signup_url="https://console.anthropic.com/settings/keys",
        notes="در تحلیل متنی و استدلال دقیق قوی است.",
    ),
    ProviderPreset(
        key="mistral",
        display_name="Mistral AI",
        provider_type="openai_compatible",
        base_url="https://api.mistral.ai/v1",
        suggested_models=("mistral-large-latest", "mistral-small-latest", "open-mistral-nemo"),
        signup_url="https://console.mistral.ai/api-keys",
        notes="سرویس اروپایی با مدل‌های باز و تجاری.",
    ),
    ProviderPreset(
        key="together",
        display_name="Together AI",
        provider_type="openai_compatible",
        base_url="https://api.together.xyz/v1",
        suggested_models=(
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
        ),
        signup_url="https://api.together.xyz/settings/api-keys",
        notes="میزبان مدل‌های متن‌باز با قیمت مناسب.",
    ),
    ProviderPreset(
        key="xai",
        display_name="xAI Grok",
        provider_type="openai_compatible",
        base_url="https://api.x.ai/v1",
        suggested_models=("grok-2-latest", "grok-beta"),
        signup_url="https://console.x.ai",
        notes="مدل‌های Grok با قرارداد سازگار OpenAI.",
    ),
    ProviderPreset(
        key="avalai",
        display_name="AvalAI (ایران)",
        provider_type="openai_compatible",
        base_url="https://api.avalai.ir/v1",
        suggested_models=("gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet-20241022"),
        signup_url="https://avalai.ir",
        notes="واسط ایرانی برای دسترسی به مدل‌های جهانی بدون نیاز به تحریم‌شکن.",
    ),
    ProviderPreset(
        key="liara",
        display_name="Liara AI (ایران)",
        provider_type="openai_compatible",
        base_url="https://ai.liara.ir/api/v1",
        suggested_models=("openai/gpt-4o-mini", "google/gemini-2.0-flash"),
        signup_url="https://liara.ir/ai",
        notes="سرویس ابری ایرانی سازگار با OpenAI.",
    ),
    ProviderPreset(
        key="custom",
        display_name="سفارشی",
        provider_type="openai_compatible",
        base_url="",
        requires_key=False,
        suggested_models=(),
        notes="هر سرویس سازگار با OpenAI: نشانی و کلید را خودتان وارد کنید.",
        accepts_optional_key=True,
    ),
)

#: دسترسی سریع بر پایه کلید
PRESET_MAP: dict[str, ProviderPreset] = {preset.key: preset for preset in PROVIDER_PRESETS}


def get_preset(key: str) -> ProviderPreset | None:
    """دریافت پیکربندی آماده یک ارائه‌دهنده."""
    return PRESET_MAP.get((key or "").strip().lower())


def preset_keys() -> list[str]:
    """فهرست شناسه همه ارائه‌دهنده‌ها."""
    return [preset.key for preset in PROVIDER_PRESETS]


def local_presets() -> list[ProviderPreset]:
    """ارائه‌دهنده‌هایی که روی سیستم کاربر اجرا می‌شوند."""
    return [preset for preset in PROVIDER_PRESETS if preset.is_local]


def keyless_presets() -> list[ProviderPreset]:
    """ارائه‌دهنده‌هایی که بدون کلید API کار می‌کنند."""
    return [preset for preset in PROVIDER_PRESETS if not preset.requires_key]
