"""
سنجش تناسب مدل محلی با حافظهٔ دستگاه.

کاربر گزارش داد که چت با پیام «اتصال به‌زور بسته شد» شکست می‌خورد.
ریشه‌اش این بود که `deepseek-r1:8b` روی دستگاه ۱۶ گیگابایتی، وسط تولید
پاسخ حافظه کم می‌آورد و زیرفرایند مدل می‌مرد.

نسخهٔ ۱.۹.۶ آن مرگ را تشخیص می‌دهد و دوباره تلاش می‌کند، ولی این
درمانِ نشانه است. درمان واقعی این است که کاربر **پیش از** انتخاب مدل
بداند کدام مدل روی دستگاهش جا می‌شود.

این ماژول عمداً هیچ مدلی را مسدود نمی‌کند. کاربر ممکن است کارت گرافیک
قدرتمندی داشته باشد که تشخیص خودکار نمی‌بیند، یا بخواهد با کندی
بسازد. کار ما اطلاع‌رسانی است، نه تصمیم‌گیری به‌جای او.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: تخمین حافظهٔ لازم (گیگابایت) به ازای هر میلیارد پارامتر.
#:
#: مدل‌های امروزی عمدتاً با کوانتیزاسیون ۴ بیتی توزیع می‌شوند، یعنی
#: حدود ۰٫۶ گیگابایت به ازای هر میلیارد پارامتر برای خود وزن‌ها. بقیه
#: فضای کار اجراکننده است: کش KV، بافر تولید، و سربار خود اولاما.
#:
#: **تصحیح نسخهٔ ۱.۹.۷:** این عدد یک بار از روی فرضیهٔ غلط بالا برده
#: شد. کاربر تصویر `ollama list` را فرستاد: مدل‌های ۸ میلیاردی‌اش روی
#: دیسک ۴٫۹ تا ۵٫۲ گیگابایت‌اند و همه در ترمینال بی‌نقص کار می‌کنند.
#: پس مرگ اجراکننده ربطی به اندازهٔ مدل نداشت — علت، بازتعریف مکرر
#: `num_ctx` بود که مدل را مجبور به بارگذاری دوباره می‌کرد.
#:
#: عدد به واقعیت برگردانده شد: حدود ۰٫۶۵ گیگابایت به ازای هر میلیارد
#: پارامتر برای وزن‌های ۴ بیتی، به‌علاوهٔ سربار کار.
GB_PER_BILLION_PARAMS = 0.7

#: ضریب اضافی برای مدل‌های استدلالی.
#:
#: این‌ها پیش از پاسخ یک بلوک `<think>` طولانی تولید می‌کنند که کش KV
#: را بزرگ‌تر می‌کند. ضریب ملایم است و فقط روی مرز تصمیم اثر می‌گذارد:
#: هدف «هشدار روی مدل واقعاً بزرگ» است، نه ترساندن کاربر از مدلی که
#: روی دستگاهش کار می‌کند.
REASONING_OVERHEAD = 1.15

#: نشانه‌های نام مدل‌های استدلالی.
REASONING_MARKERS = ("r1", "-o1", "qwq", "thinking", "reason", "marco-o1")

#: حافظه‌ای که برای سیستم‌عامل و خود برنامه کنار گذاشته می‌شود.
#:
#: ویندوز با مرورگر باز حدود ۳ تا ۴ گیگابایت می‌گیرد. عدد عمداً
#: محافظه‌کارانه نیست: هشداری که روی مدل سالم روشن شود، کاربر را
#: عادت می‌دهد نادیده‌اش بگیرد.
RESERVED_SYSTEM_GB = 3.5

#: وضعیت تناسب.
FITS = "FITS"

#: دستگاه اصلاً جایی برای مدل محلی ندارد.
NO_ROOM = "NO_ROOM"
TIGHT = "TIGHT"
TOO_BIG = "TOO_BIG"
UNKNOWN = "UNKNOWN"

#: الگوی استخراج اندازه از نام مدل: `llama3.2:3b`, `qwen2.5-7b-instruct`
_SIZE = re.compile(r"(\d+(?:\.\d+)?)\s*b\b", re.IGNORECASE)

#: مدل‌های سبک پیشنهادی، از سبک به سنگین.
#:
#: همه واقعاً در مخزن اولاما موجودند — پیشنهاد دادن مدلی که کاربر
#: نتواند بکشد، بدتر از پیشنهاد ندادن است.
LIGHT_MODELS: tuple[tuple[str, float], ...] = (
    ("qwen2.5:1.5b", 1.5),
    ("llama3.2:3b", 3.0),
    ("phi3.5:3.8b", 3.8),
    ("qwen2.5:7b", 7.0),
    ("llama3.1:8b", 8.0),
)


@dataclass(slots=True)
class ModelFit:
    """
    نتیجهٔ سنجش یک مدل در برابر حافظهٔ دستگاه.

    `status` برابر `UNKNOWN` یعنی اندازه از نام مدل قابل استخراج نبود؛
    در آن حالت هیچ ادعایی نمی‌کنیم.
    """

    model: str
    status: str
    params_billion: float = 0.0
    required_gb: float = 0.0
    available_gb: float = 0.0

    @property
    def is_risky(self) -> bool:
        """آیا باید به کاربر هشدار داده شود؟"""
        return self.status in (TIGHT, TOO_BIG, NO_ROOM)

    @property
    def reason_key(self) -> str:
        """کلید ترجمهٔ متناسب با وضعیت."""
        return f"settings.model_fit.{self.status.lower()}"


def is_reasoning_model(model: str) -> bool:
    """
    آیا این مدل پیش از پاسخ، بلوک استدلال تولید می‌کند؟

    مهم است چون حافظهٔ لازمش به‌مراتب بیشتر از اندازهٔ اسمی‌اش است.
    """
    name = str(model or "").lower()
    return any(marker in name for marker in REASONING_MARKERS)


def parse_model_size(model: str) -> float:
    """
    استخراج تعداد پارامتر (میلیارد) از نام مدل.

    صفر یعنی نشد — مثلاً `mistral:latest` که اندازه‌اش در نام نیست.
    حدس‌زدن در آن حالت بدتر از سکوت است.
    """
    if not model:
        return 0.0
    match = _SIZE.search(str(model))
    if not match:
        return 0.0
    try:
        value = float(match.group(1))
    except ValueError:
        return 0.0
    # عددهای بی‌معنا (مثل سال در نام) را رد می‌کنیم
    return value if 0 < value <= 500 else 0.0


def evaluate_fit(model: str, memory_gb: float | None) -> ModelFit:
    """
    آیا این مدل روی دستگاهی با این مقدار حافظه اجرا می‌شود؟

    سه حالت معنادار دارد: جا می‌شود، تنگ است (کار می‌کند ولی ممکن است
    وسط کار بمیرد — دقیقاً تجربهٔ کاربر)، و بزرگ‌تر از دستگاه است.
    """
    params = parse_model_size(model)
    if not params or not memory_gb or memory_gb <= 0:
        return ModelFit(model=model, status=UNKNOWN)

    required = params * GB_PER_BILLION_PARAMS
    if is_reasoning_model(model):
        required *= REASONING_OVERHEAD
    available = max(0.0, float(memory_gb) - RESERVED_SYSTEM_GB)

    # دستگاهی که پس از کسر سهم سیستم چیزی برایش نمی‌ماند، نمی‌تواند
    # هیچ مدل محلی‌ای اجرا کند. گفتن «۰ گیگابایت آزاد دارید» شبیه خطای
    # برنامه به نظر می‌رسد؛ حالت مخصوص خودش صادقانه‌تر است.
    if available <= 0:
        return ModelFit(
            model=model,
            status=NO_ROOM,
            params_billion=params,
            required_gb=round(required, 1),
            available_gb=0.0,
        )

    if required <= available * 0.7:
        status = FITS
    elif required <= available:
        status = TIGHT
    else:
        status = TOO_BIG

    return ModelFit(
        model=model,
        status=status,
        params_billion=params,
        required_gb=round(required, 1),
        available_gb=round(available, 1),
    )


def suggest_models(memory_gb: float | None, *, limit: int = 3) -> list[str]:
    """
    مدل‌های سبکی که روی این دستگاه راحت اجرا می‌شوند.

    فهرست از سنگین به سبک مرتب می‌شود: بزرگ‌ترین مدلی که جا می‌شود،
    معمولاً بهترین کیفیت را می‌دهد و باید اول پیشنهاد شود.
    """
    if not memory_gb or memory_gb <= 0:
        return []

    available = max(0.0, float(memory_gb) - RESERVED_SYSTEM_GB)
    fitting = [
        name
        for name, params in LIGHT_MODELS
        if params * GB_PER_BILLION_PARAMS <= available * 0.7
    ]
    # هیچ مدل استدلالی در فهرست پیشنهادها نیست و نباید باشد: آن‌ها
    # روی دستگاه‌های متوسط همان مشکلی را می‌سازند که کاربر داشت.
    return list(reversed(fitting))[:limit]
