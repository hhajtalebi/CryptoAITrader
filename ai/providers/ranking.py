"""
رتبه‌بندی مدل‌های هوش مصنوعی بر اساس توان تحلیل.

فهرستی که سرویس‌دهنده‌ها برمی‌گردانند مرتب‌سازی الفبایی دارد و بی‌معناست؛
کاربر در فهرست OpenRouter با صدها مدل روبه‌رو می‌شود و مدل‌های ضعیف یا
غیرمرتبط (تصویری، تعبیه‌سازی، صوتی) بالای فهرست می‌نشینند.

این ماژول هر شناسهٔ مدل را با تطبیق الگو امتیاز می‌دهد تا قوی‌ترین
مدل‌های تحلیلی بالا بیایند. امتیاز بالاتر یعنی جایگاه بالاتر.

قاعدهٔ کاربر: مدل‌های رایگان در رتبهٔ برابر جلوتر باشند، ولی یک مدل
پرچم‌دار نباید پشت یک مدل رایگان ضعیف پنهان شود.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# خانواده‌های پرچم‌دار: قوی‌ترین مدل‌های استدلالی و تحلیلی
# ---------------------------------------------------------------------------
FLAGSHIP_PATTERNS: tuple[tuple[str, int], ...] = (
    (r"\bo[34]\b|\bo1\b", 980),
    (r"gpt-5|gpt5", 1000),
    (r"claude.*opus", 990),
    (r"claude.*sonnet", 950),
    (r"gemini.*(2\.5|3).*pro", 960),
    (r"deepseek.*(r1|reasoner)", 940),
    (r"grok.*(4|3)", 930),
    (r"llama.*(405b|70b)", 900),
    (r"qwen.*(max|235b|72b)", 900),
    (r"mistral.*large", 880),
    (r"gpt-4o|gpt-4\.1|gpt-4-turbo", 920),
    (r"claude.*haiku", 830),
    (r"gemini.*flash", 830),
    (r"deepseek.*(v3|chat)", 870),
    (r"nex-n2\.5-pro", 860),
)

# پسوند/کلیدواژه‌هایی که نشان می‌دهند مدل برای تحلیل متنی مناسب نیست
IRRELEVANT_PATTERNS: tuple[str, ...] = (
    r"embed", r"rerank", r"whisper", r"tts", r"audio", r"speech",
    r"image", r"vision-only", r"dall-?e", r"stable-?diffusion", r"flux",
    r"moderation", r"guard", r"clip", r"bge-", r"sd-?xl", r"video",
)

# نشانه‌های مدل کوچک/سبک که برای تحلیل بازار ضعیف‌اند
WEAK_PATTERNS: tuple[tuple[str, int], ...] = (
    (r"\b(1|1\.5|2|3)b\b", -220),
    (r"tiny|nano|mini-?lite|micro", -140),
    (r"\b7b\b|\b8b\b", -60),
    (r"preview|alpha|experimental|beta", -25),
    (r"uncensored|roleplay|erp\b|waifu", -260),
    (r"instruct-?v0\.1", -40),
    # نسخه‌های جانبی یک خانواده نباید جای مدل‌های پرچم‌دار دیگر را بگیرند
    (r":batch\b", -120),
    (r"\bcodex\b", -90),
    (r"-mini\b|\bmini\b", -110),
    (r"\blite\b|\bflash-?8b\b", -90),
    (r"\bchat\b$", -20),
    (r"\boss\b|safeguard", -80),
)

# اندازهٔ پارامتر: بزرگ‌تر معمولاً تحلیل بهتری می‌دهد
SIZE_PATTERN = re.compile(r"(\d{2,4})\s*b\b")

FREE_BONUS = 30
"""مزیت کوچک مدل رایگان — فقط برای شکستن تساوی، نه غلبه بر کیفیت."""


def is_free_model(model_id: str) -> bool:
    """آیا این مدل رایگان است؟ (قرارداد OpenRouter پسوند ‎:free‎ است.)"""
    return model_id.strip().lower().endswith(":free")


def score_model(model_id: str) -> int:
    """
    امتیاز توان تحلیلی یک مدل.

    امتیاز مطلق معنا ندارد و فقط برای مقایسه استفاده می‌شود؛ مدل‌های
    نامرتبط عمداً امتیاز منفی بزرگ می‌گیرند تا ته فهرست بروند.
    """
    name = (model_id or "").strip().lower()
    if not name:
        return -10_000

    for pattern in IRRELEVANT_PATTERNS:
        if re.search(pattern, name):
            return -5_000

    score = 500
    for pattern, value in FLAGSHIP_PATTERNS:
        if re.search(pattern, name):
            score = max(score, value)

    for pattern, delta in WEAK_PATTERNS:
        if re.search(pattern, name):
            score += delta

    # اندازهٔ پارامتر را به‌صورت پلکانی اضافه کن
    match = SIZE_PATTERN.search(name)
    if match:
        try:
            billions = int(match.group(1))
        except ValueError:
            billions = 0
        if billions >= 200:
            score += 70
        elif billions >= 70:
            score += 50
        elif billions >= 30:
            score += 25

    if is_free_model(name):
        score += FREE_BONUS

    return score


def _vendor(model_id: str) -> str:
    """نام سازنده از شناسهٔ مدل (بخش پیش از اسلش)."""
    name = (model_id or "").strip().lower().lstrip("~")
    return name.split("/", 1)[0] if "/" in name else name


def sort_models(models: list[str]) -> list[str]:
    """
    مرتب‌سازی مدل‌ها از قوی‌ترین به ضعیف‌ترین، با تنوع سازنده.

    مرتب‌سازی صرفاً امتیازی نتیجهٔ بدی می‌دهد: یک سازنده ده‌ها نسخهٔ
    هم‌خانواده دارد و کل بالای فهرست را می‌گیرد، طوری‌که کاربر برای دیدن
    مدل قوی سازندهٔ دیگر باید ده‌ها ردیف پایین برود.

    پس مدل‌ها لایه‌لایه چیده می‌شوند: نخست بهترین مدل هر سازنده (به ترتیب
    امتیاز)، سپس دومین مدل هر سازنده و همین‌طور تا آخر. درون هر لایه
    ترتیب امتیازی و در امتیاز برابر ترتیب الفبایی حفظ می‌شود تا فهرست
    پایدار بماند.
    """
    unique = sorted({str(m).strip() for m in models if str(m).strip()})
    ranked = sorted(unique, key=lambda m: (-score_model(m), m.lower()))

    depth: dict[str, int] = {}
    layered: list[tuple[int, int, str]] = []
    for model in ranked:
        vendor = _vendor(model)
        layer = depth.get(vendor, 0)
        depth[vendor] = layer + 1
        layered.append((layer, -score_model(model), model))

    return [model for _, _, model in sorted(layered, key=lambda t: (t[0], t[1], t[2].lower()))]
