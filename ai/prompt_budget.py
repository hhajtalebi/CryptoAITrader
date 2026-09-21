"""
بودجه‌بندی اندازهٔ پرامپت بر پایهٔ توان واقعی مدل.

چرا وجود دارد؟
    کاربر گزارش کرد «`deepseek-r1:8b` در ترمینال کار می‌کند ولی برنامه
    می‌گوید `Ollama returned HTTP 500`». اندازه‌گیری نشان داد پرامپت
    تحلیل برنامه ۱۷ کیلوبایت (≈۵۸۰۰ توکن) است و برنامه از اولاما پنجرهٔ
    ۱۶۳۸۴ توکنی می‌خواست. روی دستگاه ۱۶ گیگابایتی، وزن مدل ۸ میلیاردی
    به‌علاوهٔ حافظهٔ نهان کلید/مقدار برای چنین پنجره‌ای جا نمی‌شود و
    فرایند اجراکنندهٔ اولاما پیش از تولید پاسخ می‌میرد؛ خروجی‌اش
    «۵۰۰ با بدنهٔ خالی» است، برای همین پیام خطا هیچ توضیحی نداشت.
    در ترمینال همان مدل سالم کار می‌کند چون `ollama run` پنجرهٔ
    پیش‌فرض و کوچک را می‌گیرد.

    ایراد دوم و خطرناک‌تر: راه جبرانی قبلی صرفاً پنجره را به ۴۰۹۶
    کاهش می‌داد و دوباره می‌فرستاد. پرامپت ۵۸۰۰ توکنی در پنجرهٔ ۴۰۹۶
    جا نمی‌شود، ولی اولاما خطا **نمی‌دهد** — بی‌صدا ابتدای پرامپت را
    می‌برد. مدل بخشی از داده‌های بازار را اصلاً نمی‌بیند و جای خالی را
    با حدس پر می‌کند. پاسخ می‌آید، معتبر به نظر می‌رسد و بر پایهٔ
    داده‌ای ناقص است. این یکی از دلایل مستقیم سیگنال‌های بی‌اعتماد بود.

راه‌حل این ماژول:
    به‌جای «هرچه داریم بفرست و امیدوار باش»، اول سقف امن دستگاه را
    تخمین می‌زنیم، بعد داده را **آگاهانه** تا همان اندازه کوچک می‌کنیم.
    کوچک‌کردن آگاهانه یعنی اول چیزهای کم‌ارزش حذف شوند (دفتر سفارش،
    کندل‌های خام، تایم‌فریم‌های فرعی) و هستهٔ تصمیم (اندیکاتورها و
    سطوح تایم‌فریم اصلی) تا آخرین لحظه بماند.

اصل حاکم: **بریدن آگاهانه بهتر از بریدن کور است.** اگر داده‌ای حذف شد،
مدل باید بداند چه چیزی را ندارد تا به‌جای حدس‌زدن، عدم قطعیت را اعلام
کند.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: نسبت تقریبی نویسه به توکن.
#: متن انگلیسی ≈۴، فارسی ≈۲.۵، JSON فشرده ≈۳. محافظه‌کارانه ۳ می‌گیریم؛
#: دست‌بالا گرفتن بی‌ضرر است، دست‌کم گرفتن یعنی بریده‌شدن بی‌صدا.
CHARS_PER_TOKEN = 3

#: پنجره‌هایی که اولاما کارآمد اجرا می‌کند (توان دو).
CONTEXT_STEPS: tuple[int, ...] = (2048, 4096, 8192, 16384, 32768)

#: سقف امن پنجره بر پایهٔ حافظهٔ دستگاه (گیگابایت) برای مدل‌های متوسط.
#: این اعداد از رفتار واقعی اولاما روی دستگاه‌های رایج آمده‌اند، نه از
#: فرمول نظری: حافظهٔ نهان کلید/مقدار تقریباً خطی با طول پنجره رشد
#: می‌کند و باید کنار وزن مدل جا شود.
MEMORY_TIERS: tuple[tuple[int, int], ...] = (
    (8, 4096),    # ۸ گیگ یا کمتر
    (16, 8192),   # ۱۶ گیگ — دستگاه کاربر
    (32, 16384),
    (999, 32768),
)

#: وقتی حافظهٔ دستگاه معلوم نیست، محافظه‌کارترین حالت مفید.
DEFAULT_SAFE_CONTEXT = 8192

#: بخشی از پنجره که باید برای پاسخ مدل خالی بماند.
#: مدل‌های استدلالی پیش از پاسخ، بلوک فکر تولید می‌کنند و اگر جا نباشد
#: پاسخ نیمه‌کاره قطع می‌شود.
RESERVED_FOR_REPLY_RATIO = 0.35

#: ترتیب حذف هنگام کمبود جا — از کم‌ارزش‌ترین به باارزش‌ترین.
#: این ترتیب یک تصمیم تحلیلی است: دفتر سفارش فقط عکس لحظه‌ای است و
#: تا رسیدن پاسخ مدل کهنه شده؛ اندیکاتورهای تایم‌فریم اصلی اما هستهٔ
#: تصمیم‌اند.
SHRINK_ORDER: tuple[str, ...] = (
    "orderbook",
    "raw_candles",
    "minor_timeframes",
    "secondary_fields",
)


@dataclass(slots=True)
class BudgetResult:
    """
    نتیجهٔ بودجه‌بندی یک بستهٔ داده.

    `dropped` برای شفافیت نگه داشته می‌شود: هم در پرامپت به مدل گفته
    می‌شود چه چیزی را ندارد، و هم در لاگ می‌نشیند تا اگر تحلیلی ضعیف
    بود بدانیم علتش کمبود داده بوده است.
    """

    data: dict[str, Any]
    estimated_tokens: int
    context_window: int
    dropped: list[str] = field(default_factory=list)
    truncated: bool = False

    @property
    def note(self) -> str:
        """جمله‌ای که به مدل می‌گوید چه چیزی در دسترسش نیست."""
        if not self.dropped:
            return ""
        items = ", ".join(self.dropped)
        return (
            "NOTE ON DATA COMPLETENESS: to fit the local model's context "
            f"window, the following were omitted: {items}. "
            "Do NOT guess their values. If a decision depends on omitted "
            "data, lower your confidence and say so in 'reason'."
        )


def estimate_tokens(text: str) -> int:
    """
    تخمین شمار توکن یک متن.

    دقیق نیست و قرار هم نیست باشد؛ فقط باید به‌طور پایدار **دست‌بالا**
    تخمین بزند تا هرگز به مرز پنجره نخوریم.
    """
    return len(text) // CHARS_PER_TOKEN + 8


def estimate_payload_tokens(payload: Any) -> int:
    """تخمین شمار توکن یک ساختار داده پس از تبدیل به JSON فشرده."""
    return estimate_tokens(compact_json(payload))


def compact_json(payload: Any) -> str:
    """
    تبدیل به JSON بدون فاصلهٔ اضافی.

    نسخهٔ پیشین با `indent=1` سریال می‌کرد که فقط برای چشم انسان مفید
    است. مدل از تورفتگی چیزی نمی‌فهمد، ولی حدود ۳۰٪ توکن بیشتر مصرف
    می‌شود — یعنی ۳۰٪ بیشتر احتمال سرریز پنجره.
    """
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def safe_context_for_memory(total_memory_gb: float | None) -> int:
    """
    بیشترین پنجرهٔ متنی که روی این دستگاه با اطمینان بالا می‌آید.

    اگر حافظه معلوم نباشد، حالت محافظه‌کارانه انتخاب می‌شود. شکست
    محافظه‌کارانه یعنی تحلیل کمی خلاصه‌تر؛ شکست خوش‌بینانه یعنی
    «HTTP 500» و هیچ تحلیلی.
    """
    if not total_memory_gb or total_memory_gb <= 0:
        return DEFAULT_SAFE_CONTEXT
    for ceiling_gb, window in MEMORY_TIERS:
        if total_memory_gb <= ceiling_gb:
            return window
    return CONTEXT_STEPS[-1]


def detect_total_memory_gb() -> float | None:
    """
    حافظهٔ کل دستگاه به گیگابایت.

    بدون وابستگی بیرونی پیاده شده تا `psutil` به نیازمندی‌های برنامه
    اضافه نشود. اگر تشخیص ممکن نبود `None` برمی‌گردد و فراخواننده به
    حالت امن می‌رود.
    """
    try:
        import os

        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if pages > 0 and page_size > 0:
            return (pages * page_size) / (1024**3)
    except (ValueError, OSError, AttributeError):
        pass

    # ویندوز: sysconf ندارد
    try:
        import ctypes

        class MemoryStatus(ctypes.Structure):
            """ساختار MEMORYSTATUSEX ویندوز."""

            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return status.ullTotalPhys / (1024**3)
    except (AttributeError, OSError, ValueError):
        pass

    return None


def choose_context_window(prompt_tokens: int, max_reply_tokens: int, *, ceiling: int) -> int:
    """
    کوچک‌ترین پنجرهٔ استاندارد که پرامپت و پاسخ در آن جا می‌شوند.

    هرگز از `ceiling` بالاتر نمی‌رود؛ آن سقف از حافظهٔ دستگاه می‌آید و
    عبور از آن یعنی همان خطای ۵۰۰ که کاربر دید.
    """
    needed = prompt_tokens + max_reply_tokens + 256
    for size in CONTEXT_STEPS:
        if size > ceiling:
            break
        if needed <= size:
            return size
    return min(ceiling, CONTEXT_STEPS[-1])


def available_prompt_tokens(context_window: int) -> int:
    """
    چند توکن از پنجره واقعاً برای پرامپت آزاد است.

    بقیه برای پاسخ مدل کنار گذاشته می‌شود. پر کردن کل پنجره با پرامپت
    یعنی مدل جایی برای جواب دادن ندارد.
    """
    return max(512, int(context_window * (1.0 - RESERVED_FOR_REPLY_RATIO)))


# ---------------------------------------------------------------------------
# کوچک‌کردن آگاهانهٔ بستهٔ داده
# ---------------------------------------------------------------------------


def shrink_market_data(
    data: dict[str, Any],
    *,
    budget_tokens: int,
    primary_timeframe: str = "",
) -> BudgetResult:
    """
    کوچک‌کردن بستهٔ دادهٔ بازار تا جا شدن در بودجهٔ توکن.

    مراحل به‌ترتیب اجرا می‌شوند و بعد از هر مرحله دوباره اندازه‌گیری
    می‌شود؛ به محض جا شدن، متوقف می‌شویم تا بیش از نیاز داده از دست
    نرود.

    آرگومان‌ها:
        data: بستهٔ کامل دادهٔ بازار.
        budget_tokens: سقف توکن مجاز برای بخش داده.
        primary_timeframe: تایم‌فریمی که نباید حذف شود.

    بازگشت:
        `BudgetResult` شامل دادهٔ کوچک‌شده و فهرست حذف‌شده‌ها.
    """
    working = json.loads(compact_json(data)) if data else {}
    dropped: list[str] = []

    current = estimate_payload_tokens(working)
    if current <= budget_tokens:
        return BudgetResult(working, current, 0, [], False)

    # مرحله ۱ — دفتر سفارش. حجیم است و تا رسیدن پاسخ مدل کهنه شده.
    if "orderbook" in working:
        working.pop("orderbook", None)
        dropped.append("order book depth")
        current = estimate_payload_tokens(working)
        if current <= budget_tokens:
            return BudgetResult(working, current, 0, dropped, True)

    frames: dict[str, Any] = working.get("timeframes") or {}

    # مرحله ۲ — کندل‌های خام. اندیکاتورها خلاصهٔ همین‌ها هستند و
    # اطلاعات را فشرده‌تر منتقل می‌کنند.
    trimmed_candles = False
    for frame in frames.values():
        action = frame.get("price_action")
        if isinstance(action, dict) and action.get("last_candles"):
            action["last_candles"] = action["last_candles"][-3:]
            trimmed_candles = True
    if trimmed_candles:
        dropped.append("older raw candles (kept the last 3 per timeframe)")
        current = estimate_payload_tokens(working)
        if current <= budget_tokens:
            return BudgetResult(working, current, 0, dropped, True)

    # مرحله ۳ — تایم‌فریم‌های فرعی، از کوچک‌ترین به بزرگ‌ترین.
    # تایم‌فریم اصلی و بزرگ‌ترین تایم‌فریم (تصویر کلان) نگه داشته می‌شوند.
    if len(frames) > 1:
        ordered = _timeframes_by_importance(list(frames), primary_timeframe)
        for name in ordered:
            if len(frames) <= 1:
                break
            frames.pop(name, None)
            dropped.append(f"{name} timeframe")
            current = estimate_payload_tokens(working)
            if current <= budget_tokens:
                return BudgetResult(working, current, 0, dropped, True)

    # مرحله ۴ — فیلدهای فرعی هر تایم‌فریم.
    for frame in frames.values():
        for key in ("volume", "structure"):
            frame.pop(key, None)
    dropped.append("volume and structure detail")
    current = estimate_payload_tokens(working)

    return BudgetResult(working, current, 0, dropped, True)


#: ترتیب زمانی تایم‌فریم‌ها از کوچک به بزرگ.
_TIMEFRAME_MINUTES: dict[str, int] = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "12h": 720,
    "1d": 1440, "3d": 4320, "1w": 10080,
}


def _timeframes_by_importance(names: list[str], primary: str) -> list[str]:
    """
    فهرست تایم‌فریم‌ها به‌ترتیب «اول این را حذف کن».

    منطق: تایم‌فریم اصلی هرگز حذف نمی‌شود. بزرگ‌ترین تایم‌فریم هم
    می‌ماند چون جهت کلان بازار را می‌دهد و بدون آن، تحلیل کوتاه‌مدت
    می‌تواند خلاف روند اصلی سیگنال بدهد. بقیه از کوچک‌ترین حذف می‌شوند.
    """
    keep = {primary} if primary else set()
    sortable = sorted(names, key=lambda n: _TIMEFRAME_MINUTES.get(n, 0))
    if sortable:
        keep.add(sortable[-1])
    return [name for name in sortable if name not in keep]


def strip_reasoning_block(text: str) -> str:
    """
    حذف بلوک استدلال مدل‌های reasoning از متن پاسخ.

    چرا لازم است؟
        `deepseek-r1` و هم‌خانواده‌هایش پاسخ را این‌گونه می‌دهند:

            <think>
            خب، کاربر سیگنال می‌خواهد. RSI روی ۶۱ است...
            </think>
            {"signal": "LONG", ...}

        برنامه این را پاک نمی‌کرد، پس `json.loads` روی کل متن شکست
        می‌خورد و در چت هم افکار خام مدل به کاربر نشان داده می‌شد.
        این یکی از دو دلیل اصلی «وصل نشدن» اولاما بود: اتصال برقرار
        می‌شد، مدل جواب می‌داد، ولی پاسخ غیرقابل استفاده بود.

    نکتهٔ مهم: اگر بلوک فکر باز شده ولی بسته نشده باشد (پاسخ نیمه‌کاره
    قطع شده)، کل متن فکر است و چیزی برای برداشت نمی‌ماند؛ در این حالت
    رشتهٔ خالی برمی‌گردد تا لایهٔ بالاتر بداند پاسخ ناقص است.
    """
    if not text:
        return ""

    cleaned = text
    for open_tag, close_tag in (
        ("<think>", "</think>"),
        ("<thinking>", "</thinking>"),
        ("<reasoning>", "</reasoning>"),
        ("<|begin_of_thought|>", "<|end_of_thought|>"),
    ):
        while True:
            start = cleaned.lower().find(open_tag)
            if start == -1:
                break
            end = cleaned.lower().find(close_tag, start)
            if end == -1:
                # بلوک باز ماند: پاسخ وسط استدلال قطع شده است
                cleaned = cleaned[:start]
                break
            cleaned = cleaned[:start] + cleaned[end + len(close_tag) :]

    return cleaned.strip()
