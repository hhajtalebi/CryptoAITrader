"""
تفکیک مدل‌های رایگان از مدل‌های پولی.

چرا وجود دارد؟
    کاربر صریحاً خواست «اول مدل‌های رایگان، سپس مدل‌های قوی و پولی». برای
    اینکه این ترتیب در همه‌جای برنامه یکسان باشد — فهرست کشویی تنظیمات،
    انتخاب خودکار مدل، و پیام‌های راهنما — منطق آن در همین یک ماژول جمع
    شده است.

سه دسته داریم:
    FREE      : بدون هیچ هزینه‌ای کار می‌کند (مدل محلی یا سطح رایگان سرویس)
    LOW_COST  : هزینه دارد ولی بسیار ارزان است
    PAID      : مدل‌های قدرتمند و گران

نکته مهم درباره تشخیص: نام‌گذاری سرویس‌ها استاندارد نیست، پس تشخیص بر پایه
نشانه‌های نام است. اگر نشانه‌ای پیدا نشود، مدل «نامشخص» در نظر گرفته می‌شود
و در ترتیب، بعد از رایگان‌ها و پیش از پولی‌های شناخته‌شده می‌نشیند — یعنی
هرگز به‌اشتباه «رایگان» برچسب نمی‌خورد.
"""

from __future__ import annotations

from dataclasses import dataclass

#: رده‌های هزینه، به ترتیب اولویت نمایش
TIER_FREE = "free"
TIER_LOW_COST = "low_cost"
TIER_UNKNOWN = "unknown"
TIER_PAID = "paid"

#: وزن مرتب‌سازی: عدد کمتر یعنی بالاتر در فهرست
TIER_ORDER: dict[str, int] = {
    TIER_FREE: 0,
    TIER_LOW_COST: 1,
    TIER_UNKNOWN: 2,
    TIER_PAID: 3,
}

#: برچسب فارسی هر رده برای نمایش کنار نام مدل
TIER_LABELS_FA: dict[str, str] = {
    TIER_FREE: "رایگان",
    TIER_LOW_COST: "کم‌هزینه",
    TIER_UNKNOWN: "",
    TIER_PAID: "پولی",
}

TIER_LABELS_EN: dict[str, str] = {
    TIER_FREE: "free",
    TIER_LOW_COST: "cheap",
    TIER_UNKNOWN: "",
    TIER_PAID: "paid",
}

#: سرویس‌هایی که کل مدل‌هایشان روی دستگاه کاربر اجرا می‌شود ⇒ همیشه رایگان
ALWAYS_FREE_PROVIDERS: frozenset[str] = frozenset({"ollama", "lmstudio"})

#: سرویس‌هایی با سطح رایگان واقعی (بدون نیاز به کارت اعتباری)
FREE_TIER_PROVIDERS: frozenset[str] = frozenset({"groq", "google", "openrouter", "mistral"})

#: نشانه‌های صریح رایگان بودن در نام مدل
FREE_MARKERS: tuple[str, ...] = (":free", "-free", "/free", "free-")

#: نشانه‌های مدل‌های گران‌قیمت
PAID_MARKERS: tuple[str, ...] = (
    "-pro", "pro-", "opus", "-max", "ultra", "-405b", "-671b", "-large",
    "o1-preview", "gpt-4-turbo", "gpt-4.5",
)

#: نشانه‌های نامی مدل‌های ارزان (اما نه رایگان)
LOW_COST_MARKERS: tuple[str, ...] = (
    "mini", "nano", "flash", "haiku", "small", "lite", "instant", "tiny", "turbo",
)

#: اندازه‌های کوچک مدل، به‌صورت «کلمه کامل».
#: زیررشته‌ای مقایسه نمی‌شوند چون «31b» شامل «1b» است و یک مدل ۳۱ میلیاردی
#: را به‌اشتباه کوچک (و در نتیجه رایگان) نشان می‌داد.
SMALL_SIZE_MARKERS: frozenset[str] = frozenset({"1b", "2b", "3b", "4b", "7b", "8b", "9b"})

#: جداکننده‌های رایج در نام مدل‌ها
_TOKEN_SEPARATORS = str.maketrans({"-": " ", "_": " ", "/": " ", ":": " ", ".": " "})


def _tokens(name: str) -> set[str]:
    """شکستن نام مدل به اجزای مستقل، برای مقایسه دقیق اندازه."""
    return set(name.translate(_TOKEN_SEPARATORS).split())


def _is_small(name: str) -> bool:
    """آیا نام مدل نشان‌دهنده یک مدل کوچک/ارزان است؟"""
    if any(marker in name for marker in LOW_COST_MARKERS):
        return True
    return bool(_tokens(name) & SMALL_SIZE_MARKERS)


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """
    یک مدل به‌همراه رده هزینه‌اش.

    فیلد `label` همان چیزی است که در فهرست کشویی دیده می‌شود، مثلاً:
        gemini-2.0-flash — رایگان
    """

    name: str
    tier: str
    provider: str = ""

    @property
    def is_free(self) -> bool:
        """آیا استفاده از این مدل هیچ هزینه‌ای ندارد؟"""
        return self.tier == TIER_FREE

    def label(self, language: str = "fa") -> str:
        """نام قابل نمایش به‌همراه برچسب رده."""
        labels = TIER_LABELS_FA if language == "fa" else TIER_LABELS_EN
        suffix = labels.get(self.tier, "")
        return f"{self.name} — {suffix}" if suffix else self.name


def classify_model(model: str, provider: str = "") -> str:
    """
    تعیین رده هزینه یک مدل.

    ترتیب بررسی عمدی است: نشانه صریح «رایگان» در نام، بر هر حدس دیگری
    مقدم است؛ چون سرویس خودش آن را اعلام کرده.
    """
    name = (model or "").strip().lower()
    key = (provider or "").strip().lower()

    if not name:
        return TIER_UNKNOWN

    # مدل محلی: هزینه‌اش برق دستگاه خود کاربر است
    if key in ALWAYS_FREE_PROVIDERS:
        return TIER_FREE

    # اعلام صریح خود سرویس
    if any(marker in name for marker in FREE_MARKERS):
        return TIER_FREE

    # مدل گران، حتی روی سرویسی که سطح رایگان دارد، رایگان نیست
    if any(marker in name for marker in PAID_MARKERS):
        return TIER_PAID

    # سطح رایگان سرویس‌های شناخته‌شده، فقط برای مدل‌های کوچکشان
    if key in FREE_TIER_PROVIDERS and _is_small(name):
        return TIER_FREE

    if _is_small(name):
        return TIER_LOW_COST

    return TIER_UNKNOWN


def sort_models(models: list[str], provider: str = "") -> list[ModelInfo]:
    """
    مرتب‌سازی مدل‌ها: اول رایگان، بعد کم‌هزینه، بعد بقیه.

    داخل هر رده، ترتیب الفبایی حفظ می‌شود تا فهرست پایدار و قابل جست‌وجو
    بماند (کاربر نباید هر بار جای مدلی را عوض‌شده ببیند).
    """
    infos = [ModelInfo(name=name, tier=classify_model(name, provider), provider=provider) for name in models]
    return sorted(infos, key=lambda info: (TIER_ORDER.get(info.tier, 9), info.name.lower()))


def free_models(models: list[str], provider: str = "") -> list[str]:
    """فقط مدل‌های کاملاً رایگان."""
    return [info.name for info in sort_models(models, provider) if info.is_free]


def pick_default_model(models: list[str], provider: str = "") -> str:
    """
    انتخاب خودکار بهترین مدل پیش‌فرض.

    سیاست: رایگان‌ترین گزینهٔ موجود. اگر هیچ مدل رایگانی نبود، ارزان‌ترین.
    این همان چیزی است که کاربر خواست — شروع بدون هزینه، ارتقا در صورت نیاز.
    """
    ordered = sort_models(models, provider)
    return ordered[0].name if ordered else ""


#: مدل‌های رایگان شناخته‌شده هر سرویس، برای وقتی که فهرست زنده در دسترس نیست.
#: این‌ها فقط پیشنهاد اولیه‌اند؛ فهرست واقعی همیشه از خود سرویس گرفته می‌شود.
KNOWN_FREE_MODELS: dict[str, tuple[str, ...]] = {
    "groq": (
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "gemma2-9b-it",
    ),
    "google": (
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
    ),
    "openrouter": (
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "thinkingmachines/inkling:free",
        "liquid/lfm-2.5-2.6b:free",
        "nex-agi/nex-n2.5-pro:free",
    ),
    "mistral": (
        "open-mistral-nemo",
        "mistral-small-latest",
    ),
    "ollama": (
        "qwen2.5",
        "llama3.2",
        "gemma2",
        "phi3",
    ),
}


def known_free_models(provider: str) -> list[str]:
    """مدل‌های رایگان از پیش شناخته‌شده یک سرویس."""
    return list(KNOWN_FREE_MODELS.get((provider or "").strip().lower(), ()))
