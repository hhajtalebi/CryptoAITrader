"""آزمون بومی‌سازی — تضمین اینکه هیچ ترجمه‌ای جا نیفتاده است."""

from __future__ import annotations

import pytest

from localization import Translator


@pytest.fixture()
def fa() -> Translator:
    """مترجم فارسی."""
    return Translator("fa")


@pytest.fixture()
def en() -> Translator:
    """مترجم انگلیسی."""
    return Translator("en")


def test_both_languages_are_available(fa: Translator) -> None:
    """هر دو زبان باید در دسترس باشند."""
    assert set(fa.available_languages()) >= {"fa", "en"}


def test_persian_is_rtl_english_is_ltr(fa: Translator, en: Translator) -> None:
    """جهت چیدمان باید با زبان هماهنگ باشد."""
    assert fa.is_rtl and fa.direction == "rtl"
    assert not en.is_rtl and en.direction == "ltr"


def test_no_missing_keys_in_persian(fa: Translator) -> None:
    """هر کلیدی که در انگلیسی هست باید در فارسی هم باشد."""
    assert fa.missing_keys("en") == []


def test_no_missing_keys_in_english(en: Translator) -> None:
    """و برعکس — تا هیچ زبانی عقب نماند."""
    assert en.missing_keys("fa") == []


def test_navigation_keys_are_translated(fa: Translator, en: Translator) -> None:
    """کلیدهای ناوبری باید در هر دو زبان ترجمه شده باشند."""
    for key in ("dashboard", "markets", "analysis", "signals", "reports", "settings", "help"):
        assert fa.tr(f"nav.{key}") != f"nav.{key}"
        assert en.tr(f"nav.{key}") != f"nav.{key}"


def test_missing_key_falls_back_to_key_name(fa: Translator) -> None:
    """کلید ناموجود نباید خطا بدهد یا رشته خالی برگرداند."""
    assert fa.tr("this.key.does.not.exist") == "this.key.does.not.exist"


def test_variable_interpolation(fa: Translator) -> None:
    """جای‌گذاری متغیر باید کار کند."""
    text = fa.tr("errors.insufficient_data", symbol="BTC/USDT", timeframe="4h")
    assert "BTC/USDT" in text and "4h" in text


def test_language_switch_changes_output(fa: Translator) -> None:
    """تغییر زبان باید بلافاصله روی خروجی اثر بگذارد."""
    persian = fa.tr("nav.settings")
    fa.set_language("en")
    assert fa.tr("nav.settings") == "Settings"
    assert fa.tr("nav.settings") != persian


def test_persian_digits_round_trip(fa: Translator) -> None:
    """تبدیل ارقام باید برگشت‌پذیر باشد."""
    assert fa.to_latin_digits(fa.to_persian_digits("1402/06/17")) == "1402/06/17"


def test_number_formatting_uses_persian_digits(fa: Translator, en: Translator) -> None:
    """اعداد فارسی باید با ارقام فارسی نمایش داده شوند."""
    assert "۷" in fa.format_number(78412.5)
    assert "7" in en.format_number(78412.5)


def test_confidence_note_exists_in_both_languages(fa: Translator, en: Translator) -> None:
    """
    توضیح معنای «اطمینان» یک الزام ایمنی است و نباید در هیچ زبانی جا بیفتد.
    """
    assert fa.has("signals.confidence_note")
    assert "احتمال سود" in fa.tr("signals.confidence_note")
    assert "NOT a probability" in en.tr("signals.confidence_note")
