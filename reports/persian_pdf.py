"""
تولید PDF فارسی با شکل‌دهی درست حروف.

چرا این فایل لازم است؟
    کتابخانهٔ reportlab به‌تنهایی فارسی را درست چاپ نمی‌کند. دو مشکل دارد:

    ۱. **حروف نمی‌چسبند.** در فارسی شکل هر حرف به جایگاهش بستگی دارد
       (آغازی، میانی، پایانی، تنها). reportlab این را نمی‌داند و حروف را
       جدا از هم می‌چیند: «س ل ا م» به‌جای «سلام».

    ۲. **جهت متن غلط است.** فارسی راست‌به‌چپ است ولی reportlab متن را
       چپ‌به‌راست می‌چیند و جمله وارونه می‌شود.

    راه‌حل: پیش از تحویل متن به reportlab، ابتدا با arabic_reshaper حروف
    را به شکل درست تبدیل می‌کنیم و سپس با الگوریتم bidi ترتیب راست‌به‌چپ
    را اعمال می‌کنیم. همچنین باید قلمی جاسازی شود که حروف فارسی دارد؛
    قلم‌های پیش‌فرض reportlab ندارند. از قلم آزاد «وزیرمتن» استفاده شده
    که مجوز SIL OFL دارد و توزیع آن با نرم‌افزار مجاز است.

اگر کتابخانه‌ها یا قلم در دسترس نباشند، برنامه از کار نمی‌افتد؛ متن به
شکل ساده چاپ می‌شود و در گزارش هشدار ثبت می‌گردد.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: مسیر پوشهٔ قلم‌ها نسبت به ریشهٔ پروژه
FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

REGULAR_FONT_FILE = FONTS_DIR / "Vazirmatn-Regular.ttf"
BOLD_FONT_FILE = FONTS_DIR / "Vazirmatn-Bold.ttf"

#: نام قلم پس از ثبت در reportlab
FONT_NAME = "Vazirmatn"
FONT_NAME_BOLD = "Vazirmatn-Bold"

#: آیا حروف فارسی/عربی در متن هست؟
_PERSIAN_PATTERN = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]")

#: حاشیهٔ ایمنی هنگام شکستن خط (نقطه).
#:
#: عرض متن شکل‌داده‌شده دقیقاً با آنچه reportlab هنگام چیدمان حساب
#: می‌کند یکی نیست (کرنینگ و پدینگ چند نقطه فرق می‌کنند). بدون این
#: حاشیه، خطی که «دقیقاً جا می‌شود» موقع چاپ سرریز می‌کرد.
LINE_SAFETY_MARGIN = 12.0

_fonts_registered: bool | None = None


def has_persian(text: str) -> bool:
    """آیا متن حرف فارسی یا عربی دارد؟"""
    return bool(_PERSIAN_PATTERN.search(str(text or "")))


def register_fonts() -> bool:
    """
    ثبت قلم فارسی در reportlab.

    فقط یک بار انجام می‌شود؛ نتیجه نگهداری می‌شود تا هر بار فایل قلم
    دوباره خوانده نشود.
    """
    global _fonts_registered
    if _fonts_registered is not None:
        return _fonts_registered

    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        if not REGULAR_FONT_FILE.exists():
            logger.warning("Persian font not found at %s; PDF will use a fallback font", REGULAR_FONT_FILE)
            _fonts_registered = False
            return False

        pdfmetrics.registerFont(TTFont(FONT_NAME, str(REGULAR_FONT_FILE)))
        if BOLD_FONT_FILE.exists():
            pdfmetrics.registerFont(TTFont(FONT_NAME_BOLD, str(BOLD_FONT_FILE)))
        else:
            pdfmetrics.registerFont(TTFont(FONT_NAME_BOLD, str(REGULAR_FONT_FILE)))

        from reportlab.lib.fonts import addMapping

        addMapping(FONT_NAME, 0, 0, FONT_NAME)
        addMapping(FONT_NAME, 1, 0, FONT_NAME_BOLD)
        _fonts_registered = True
        logger.info("Persian PDF font registered: %s", FONT_NAME)
    except Exception as exc:  # noqa: BLE001 - نبود قلم نباید گزارش‌گیری را متوقف کند
        logger.warning("Could not register Persian font: %s", exc)
        _fonts_registered = False
    return _fonts_registered


def shape(text: str) -> str:
    """
    آماده‌سازی متن فارسی برای چاپ در PDF.

    اگر متن فارسی نداشته باشد، بدون تغییر برمی‌گردد تا متن انگلیسی
    دست‌نخورده بماند.
    """
    raw = str(text or "")
    if not raw or not has_persian(raw):
        return raw
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(raw))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Persian shaping unavailable: %s", exc)
        return raw


def wrap_persian(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    """
    شکستن متن فارسی به خطوط، **پیش از** اعمال الگوریتم دوجهته.

    چرا این کار لازم است؟
        اگر متن را اول شکل‌دهی کنیم و بعد به reportlab بسپاریم تا خودش
        خط‌ها را بشکند، ترتیب خطوط وارونه می‌شود: جملهٔ دوم بالای جملهٔ
        اول چاپ می‌شود. علتش این است که پس از bidi، رشته به ترتیب
        «دیداری» درمی‌آید و reportlab آن را مثل متن چپ‌به‌راست می‌شکند.

        راه درست: اول در ترتیب منطقی (همان‌طور که نوشته شده) خطوط را
        بشکنیم، بعد هر خط را جداگانه شکل‌دهی کنیم.

    بازگشتی: فهرست خطوط، هرکدام آمادهٔ چاپ.
    """
    raw = str(text or "")
    if not raw:
        return []

    try:
        from reportlab.pdfbase import pdfmetrics

        def width_of(candidate: str) -> float:
            """پهنای واقعی متن پس از شکل‌دهی."""
            return pdfmetrics.stringWidth(shape(candidate), font_name, font_size)
    except Exception:  # noqa: BLE001
        def width_of(candidate: str) -> float:
            """تخمین تقریبی وقتی reportlab در دسترس نیست."""
            return len(candidate) * font_size * 0.5

    lines: list[str] = []
    for logical_line in raw.splitlines():
        words = logical_line.split()
        if not words:
            lines.append("")
            continue
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and width_of(candidate) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def shape_paragraph(text: str) -> str:
    """
    شکل‌دهی متن چندخطی، خط به خط.

    الگوریتم bidi روی کل متن یک‌جا، ترتیب خطوط را به هم می‌ریزد؛ به همین
    دلیل هر خط جداگانه پردازش می‌شود.
    """
    raw = str(text or "")
    if not raw or not has_persian(raw):
        return raw
    return "\n".join(shape(line) for line in raw.splitlines())


def build_analysis_pdf(
    path: str | Path,
    *,
    title: str,
    subtitle: str = "",
    sections: list[tuple[str, str]] | None = None,
    facts: list[tuple[str, str]] | None = None,
    footer: str = "",
) -> Path:
    """
    ساخت یک PDF فارسی از تحلیل نوشتاری.

    پارامترها:
        path      : مسیر فایل خروجی
        title     : عنوان اصلی
        subtitle  : زیرعنوان (مثلاً نماد و تاریخ)
        sections  : فهرست (عنوان بخش، متن بخش)
        facts     : فهرست (برچسب، مقدار) برای جدول خلاصه
        footer    : متن پانویس

    بازگشتی: مسیر فایل ساخته‌شده.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    registered = register_fonts()
    font = FONT_NAME if registered else "Helvetica"
    font_bold = FONT_NAME_BOLD if registered else "Helvetica-Bold"

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    base = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FaTitle",
        parent=base["Title"],
        fontName=font_bold,
        fontSize=18,
        leading=26,
        alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "FaSubtitle",
        parent=base["Normal"],
        fontName=font,
        fontSize=10,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#5b6478"),
    )
    heading_style = ParagraphStyle(
        "FaHeading",
        parent=base["Heading2"],
        fontName=font_bold,
        fontSize=13,
        leading=20,
        alignment=TA_RIGHT,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#1f2b47"),
    )
    body_style = ParagraphStyle(
        "FaBody",
        parent=base["Normal"],
        fontName=font,
        fontSize=11,
        leading=20,
        alignment=TA_RIGHT,
        # `wordWrap="RTL"` عمداً تنظیم **نشده** است. رشته‌ای که به اینجا
        # می‌رسد از پیش با الگوریتم bidi به ترتیب دیداری درآمده؛ اگر
        # reportlab هم دوباره ترتیب راست‌به‌چپ اعمال کند، نتیجه دوبار
        # وارونه می‌شود و کلمات جابه‌جا می‌افتند.
    )
    latin_style = ParagraphStyle(
        "LatinBody",
        parent=base["Normal"],
        fontName=font,
        fontSize=10,
        leading=17,
        alignment=TA_LEFT,
    )
    footer_style = ParagraphStyle(
        "FaFooter",
        parent=base["Normal"],
        fontName=font,
        fontSize=9,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#7a8296"),
    )

    document = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=str(title),
    )

    story: list[Any] = [Paragraph(shape(title), title_style)]
    if subtitle:
        story.append(Paragraph(shape(subtitle), subtitle_style))
    story.append(Spacer(1, 10))

    if facts:
        # جدول خلاصه: ستون راست برچسب، ستون چپ مقدار
        rows = [[Paragraph(shape(str(value)), body_style), Paragraph(shape(str(label)), body_style)] for label, value in facts]
        table = Table(rows, colWidths=[None, 45 * mm], hAlign="RIGHT")
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d7dbe4")),
                    ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#f2f4f8")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 12))

    for heading, text in sections or []:
        if heading:
            story.append(Paragraph(shape(heading), heading_style))
        for chunk in str(text or "").split("\n\n"):
            cleaned = chunk.strip()
            if not cleaned:
                continue
            if has_persian(cleaned):
                # خطوط را خودمان می‌شکنیم تا ترتیبشان وارونه نشود.
                #
                # هر خط **جداگانه** در Paragraph خودش می‌رود، نه همه با
                # `<br/>` در یک Paragraph. چرا؟ چون reportlab متن یک
                # Paragraph را دوباره کلمه‌بندی می‌کند و چون رشته پس از
                # bidi به ترتیب دیداری است، بازشکنیِ آن کلمهٔ آخر را به
                # خط بعد پرت می‌کرد — همان «کلمات در هم ریخته» که کاربر
                # گزارش کرد. Paragraph تک‌خطی چیزی برای بازشکنی ندارد.
                usable = document.width - LINE_SAFETY_MARGIN
                for line in wrap_persian(cleaned, font, body_style.fontSize, usable):
                    if line:
                        story.append(Paragraph(shape(line), body_style))
                    else:
                        story.append(Spacer(1, body_style.fontSize * 0.6))
            else:
                # متن کاملاً لاتین (مثل گزارش فنی موتور) باید چپ‌چین
                # باشد؛ راست‌چین‌کردنش خواندن را سخت می‌کند.
                for line in cleaned.splitlines():
                    story.append(Paragraph(line, latin_style))
            story.append(Spacer(1, 6))

    if footer:
        story.append(Spacer(1, 14))
        story.append(Paragraph(shape(footer), footer_style))

    document.build(story)
    logger.info("Persian analysis PDF written to %s", target)
    return target
