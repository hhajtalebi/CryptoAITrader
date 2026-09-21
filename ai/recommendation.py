"""
استخراج توصیهٔ صریح خرید/فروش از پاسخ هوش مصنوعی.

کاربر گفت: «هوش مصنوعی باید پیشنهاد خرید و فروش بدهد.» تحلیل متنی
هرچقدر هم دقیق باشد، این خواسته را برآورده نمی‌کند؛ کاربر باید بدون
خواندن چهار پاراگراف بفهمد جواب «بخر» است یا «نخر».

روش انتخاب‌شده: از مدل می‌خواهیم تحلیل متنی‌اش را بنویسد و در **آخرین
خط** یک ردیف ماشین‌خوان بگذارد:

    RECOMMENDATION: BUY | 72 | RSI و MACD هم‌جهت‌اند و ساختار صعودی است

چرا نه خروجی کاملاً JSON؟ چون آزمودیم: وقتی از مدل محلی ۸ میلیاردی
کاربر خواستیم کل تحلیل را در JSON بدهد، کیفیت متن به‌شدت افت کرد —
مدل انرژی‌اش را صرف ساختار می‌کرد نه محتوا. یک خط در انتهای متن آزاد،
هم برای مدل آسان است و هم برای ما قابل اتکا.

نکتهٔ مهم: اگر مدل آن خط را ننویسد، ما **حدس نمی‌زنیم**. نبود توصیه با
`None` برگردانده می‌شود و رابط کاربری چیزی نشان نمی‌دهد. استخراج
احساسات از متن («به نظر صعودی می‌آید») دقیقاً همان کاری است که سیگنال
بی‌اعتماد می‌سازد.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

#: عملی که کاربر باید انجام دهد.
BUY = "BUY"
SELL = "SELL"
WAIT = "WAIT"

VALID_ACTIONS = (BUY, SELL, WAIT)

#: مترادف‌هایی که مدل‌ها به‌جای کلمهٔ خواسته‌شده برمی‌گردانند.
#:
#: این فهرست از خروجی واقعی مدل‌ها ساخته شده، نه از حدس. مدل‌های کوچک
#: دستور را می‌فهمند ولی واژهٔ آشناتر خودشان را می‌نویسند.
_ALIASES: dict[str, str] = {
    "BUY": BUY,
    "LONG": BUY,
    "BULLISH": BUY,
    "ENTER LONG": BUY,
    "GO LONG": BUY,
    "خرید": BUY,
    "SELL": SELL,
    "SHORT": SELL,
    "BEARISH": SELL,
    "ENTER SHORT": SELL,
    "GO SHORT": SELL,
    "فروش": SELL,
    "WAIT": WAIT,
    "HOLD": WAIT,
    "NEUTRAL": WAIT,
    "NO TRADE": WAIT,
    "STAY OUT": WAIT,
    "انتظار": WAIT,
    "صبر": WAIT,
}

#: خط توصیه. برچسب ممکن است با «**» مارک‌داون احاطه شده باشد.
_LINE = re.compile(
    r"^\s*\**\s*RECOMMENDATION\s*\**\s*[:：]\s*(?P<body>.+?)\s*\**\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(slots=True)
class Recommendation:
    """
    توصیهٔ صریح مدل.

    `confidence` عمداً می‌تواند `None` باشد: مدلی که عدد نداده، نباید
    وانمود کنیم عددی داده است. صفر گذاشتن یعنی «اطمینان صفر» که معنای
    کاملاً متفاوتی دارد.
    """

    action: str
    confidence: int | None = None
    rationale: str = ""

    @property
    def is_actionable(self) -> bool:
        """آیا این توصیه به معامله می‌انجامد؟"""
        return self.action in (BUY, SELL)

    def to_dict(self) -> dict[str, Any]:
        """تبدیل برای ذخیره و انتقال به رابط کاربری."""
        return {
            "action": self.action,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


def normalize_action(raw: str) -> str | None:
    """
    تبدیل واژهٔ مدل به یکی از سه عمل معتبر.

    `None` یعنی نشناختیم — که با `WAIT` فرق دارد. `WAIT` تصمیم مدل است،
    `None` یعنی مدل تصمیمی که ما بفهمیم نگرفته.
    """
    text = str(raw or "").strip().upper()
    if not text:
        return None
    if text in _ALIASES:
        return _ALIASES[text]
    # مدل گاهی جمله می‌نویسد: «BUY — but wait for a retest»
    for alias, action in _ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return action
    return None


def _parse_confidence(raw: str) -> int | None:
    """
    خواندن عدد اطمینان و محدود کردنش به بازهٔ ۰ تا ۱۰۰.

    مدل‌ها گاهی «۰٫۷۲» می‌دهند و گاهی «72%». هر دو یک معنا دارند.
    """
    text = str(raw or "").strip().replace("%", "").replace("٪", "")
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if 0 < value <= 1:
        # کسری بین صفر و یک یعنی درصد اعشاری
        value *= 100
    return max(0, min(100, int(round(value))))


def parse_recommendation(content: str) -> Recommendation | None:
    """
    استخراج توصیه از پاسخ مدل.

    `None` یعنی مدل خط توصیه را ننوشت. در آن حالت رابط کاربری کارت
    توصیه را نمی‌سازد؛ جای خالی صادقانه‌تر از حدس است.
    """
    if not content:
        return None

    matches = list(_LINE.finditer(content))
    if not matches:
        return None

    # آخرین خط ملاک است: مدل‌های استدلالی گاهی وسط متن هم نمونه
    # می‌نویسند، ولی تصمیم نهایی همیشه آخرین چیزی است که می‌گویند.
    body = matches[-1].group("body")

    parts = [segment.strip() for segment in re.split(r"[|｜]", body)]
    action = normalize_action(parts[0] if parts else "")
    if action is None:
        return None

    confidence = _parse_confidence(parts[1]) if len(parts) > 1 else None
    rationale = parts[2].strip(" *") if len(parts) > 2 else ""

    return Recommendation(action=action, confidence=confidence, rationale=rationale)


def strip_recommendation_line(content: str) -> str:
    """
    حذف خط ماشین‌خوان از متنی که به کاربر نشان داده می‌شود.

    آن خط برای برنامه است، نه برای کاربر؛ کاربر همان اطلاعات را در
    کارت توصیه با قالب درست می‌بیند. نمایش هر دو، تکرار است.
    """
    if not content:
        return ""
    return _LINE.sub("", content).rstrip()
