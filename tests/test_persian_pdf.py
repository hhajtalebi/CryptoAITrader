"""
آزمون‌های خروجی PDF فارسی.

نکتهٔ کلیدی که این آزمون‌ها محافظت می‌کنند: reportlab به‌تنهایی فارسی را
جدا و وارونه چاپ می‌کند. باید حروف شکل‌دهی شوند، ترتیب راست‌به‌چپ اعمال
شود و **ترتیب خطوط** به‌هم نریزد.
"""

from __future__ import annotations

from pathlib import Path

from reports.persian_pdf import (
    FONT_NAME,
    REGULAR_FONT_FILE,
    build_analysis_pdf,
    has_persian,
    register_fonts,
    shape,
    shape_paragraph,
    wrap_persian,
)


# ---------------------------------------------------------------------------
# قلم
# ---------------------------------------------------------------------------
def test_font_file_ships_with_project() -> None:
    """قلم فارسی باید همراه پروژه باشد، وگرنه PDF فارسی ممکن نیست."""
    assert REGULAR_FONT_FILE.exists(), f"font missing: {REGULAR_FONT_FILE}"
    assert REGULAR_FONT_FILE.stat().st_size > 50_000


def test_register_fonts_succeeds() -> None:
    """ثبت قلم در reportlab باید موفق باشد."""
    assert register_fonts() is True


# ---------------------------------------------------------------------------
# تشخیص و شکل‌دهی
# ---------------------------------------------------------------------------
def test_has_persian() -> None:
    """تشخیص وجود حروف فارسی."""
    assert has_persian("سلام") is True
    assert has_persian("hello") is False
    assert has_persian("") is False
    assert has_persian("BTC/USDT قیمت") is True


def test_shape_changes_persian_text() -> None:
    """متن فارسی باید شکل‌دهی شود (رشتهٔ خروجی با ورودی فرق کند)."""
    source = "سلام دنیا"
    assert shape(source) != source


def test_shape_leaves_english_untouched() -> None:
    """متن انگلیسی نباید دست بخورد."""
    assert shape("Hello World 123") == "Hello World 123"


def test_shape_of_empty_text() -> None:
    """متن خالی خطا نمی‌دهد."""
    assert shape("") == ""


def test_shape_paragraph_keeps_line_count() -> None:
    """شکل‌دهی چندخطی نباید تعداد خطوط را عوض کند."""
    source = "خط اول\nخط دوم\nخط سوم"
    assert len(shape_paragraph(source).splitlines()) == 3


# ---------------------------------------------------------------------------
# شکستن خطوط
# ---------------------------------------------------------------------------
def test_wrap_persian_respects_width() -> None:
    """متن بلند به چند خط شکسته می‌شود."""
    text = "این یک جملهٔ بسیار بلند فارسی است که باید در چند خط جای بگیرد. " * 3
    lines = wrap_persian(text, FONT_NAME, 11, 200)
    assert len(lines) > 1
    assert all(line.strip() for line in lines)


def test_wrap_persian_preserves_word_order() -> None:
    """
    ترتیب واژه‌ها پس از شکستن باید حفظ شود.

    این همان اشکالی بود که در نسخهٔ اول دیده شد: خط دوم بالای خط اول
    چاپ می‌شد چون متن پیش از شکستن، دوجهته شده بود.
    """
    text = "اول دوم سوم چهارم پنجم ششم هفتم هشتم نهم دهم"
    lines = wrap_persian(text, FONT_NAME, 11, 120)
    rejoined = " ".join(lines)
    assert rejoined.split() == text.split()


def test_wrap_persian_keeps_explicit_newlines() -> None:
    """خطوطی که کاربر خودش شکسته، جدا می‌مانند."""
    lines = wrap_persian("خط اول\nخط دوم", FONT_NAME, 11, 500)
    assert len(lines) == 2


def test_wrap_empty_text() -> None:
    """متن خالی فهرست خالی می‌دهد."""
    assert wrap_persian("", FONT_NAME, 11, 200) == []


# ---------------------------------------------------------------------------
# ساخت فایل
# ---------------------------------------------------------------------------
def test_build_pdf_creates_file(tmp_path: Path) -> None:
    """فایل PDF ساخته می‌شود و محتوا دارد."""
    target = tmp_path / "out.pdf"
    result = build_analysis_pdf(
        target,
        title="تحلیل بیت‌کوین",
        subtitle="BTC/USDT — ۴ ساعته",
        facts=[("جهت", "خرید"), ("اطمینان", "۷۲٪")],
        sections=[("خلاصه", "روند صعودی است و حجم افزایش یافته."), ("ریسک", "حد ضرر را رعایت کنید.")],
        footer="حسین حاج طالبی",
    )
    assert result.exists()
    assert result.stat().st_size > 2000
    assert result.read_bytes().startswith(b"%PDF")


def test_build_pdf_without_optional_parts(tmp_path: Path) -> None:
    """بدون جدول و پانویس هم باید کار کند."""
    target = build_analysis_pdf(tmp_path / "min.pdf", title="عنوان تنها")
    assert target.exists()
    assert target.stat().st_size > 1000


def test_build_pdf_with_english_text(tmp_path: Path) -> None:
    """متن انگلیسی هم باید بدون خطا چاپ شود."""
    target = build_analysis_pdf(
        tmp_path / "en.pdf",
        title="Signal analysis",
        sections=[("Summary", "The trend is bullish and volume increased.")],
    )
    assert target.exists()


def test_build_pdf_with_mixed_text(tmp_path: Path) -> None:
    """متن ترکیبی فارسی و انگلیسی نباید خطا بدهد."""
    target = build_analysis_pdf(
        tmp_path / "mixed.pdf",
        title="تحلیل BTC/USDT",
        sections=[("خلاصه", "شاخص RSI برابر 62.5 است و روند bullish ارزیابی می‌شود.")],
    )
    assert target.exists()


def test_build_pdf_creates_parent_directory(tmp_path: Path) -> None:
    """اگر پوشهٔ مقصد نباشد، ساخته می‌شود."""
    target = build_analysis_pdf(tmp_path / "deep" / "nested" / "a.pdf", title="تست")
    assert target.exists()


def test_build_pdf_with_multiline_section(tmp_path: Path) -> None:
    """بخش چندبندی باید سالم چاپ شود."""
    body = "بند اول این تحلیل.\n\nبند دوم این تحلیل.\n\nبند سوم."
    target = build_analysis_pdf(tmp_path / "multi.pdf", title="تست", sections=[("متن", body)])
    assert target.exists()
