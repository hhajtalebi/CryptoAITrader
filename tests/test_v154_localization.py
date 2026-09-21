"""
آزمون‌های کامل‌بودن ترجمه و درستی راست‌به‌چپ.

قانون کاربر: هیچ متن رابط کاربری سخت‌کد نشود و فارسی/انگلیسی هر دو کامل
باشند. اما نمادهایی مثل `BTC/USDT` نباید در چیدمان راست‌به‌چپ به‌هم بریزند.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"


def _flatten(namespace: str, obj: dict, out: dict) -> None:
    """تخت‌کردن کلیدهای تودرتو به شکل `namespace.a.b`."""
    for key, value in obj.items():
        full = f"{namespace}.{key}"
        if isinstance(value, dict):
            _flatten(full, value, out)
        else:
            out[full] = value


def _load(lang: str) -> dict:
    """خواندن همهٔ فضای‌نام‌های یک زبان."""
    out: dict = {}
    for path in (ROOT / "localization" / lang).glob("*.json"):
        _flatten(path.stem, json.loads(path.read_text(encoding="utf-8")), out)
    return out


@pytest.fixture(scope="module")
def catalogs() -> tuple[dict, dict]:
    """کاتالوگ فارسی و انگلیسی."""
    return _load("fa"), _load("en")


def test_languages_have_identical_keys(catalogs) -> None:  # type: ignore[no-untyped-def]
    """
    هر کلید باید در هر دو زبان باشد.

    کلید یک‌طرفه یعنی کاربرِ یک زبان متن خام می‌بیند.
    """
    fa, en = catalogs
    assert sorted(set(fa) - set(en)) == []
    assert sorted(set(en) - set(fa)) == []


def test_no_empty_translations(catalogs) -> None:  # type: ignore[no-untyped-def]
    """ترجمهٔ خالی همان نبودِ ترجمه است."""
    fa, en = catalogs
    for name, catalog in (("fa", fa), ("en", en)):
        blanks = [k for k, v in catalog.items() if isinstance(v, str) and not v.strip()]
        assert not blanks, f"{name}: کلید بدون متن -> {blanks[:10]}"


def test_every_key_used_in_code_exists(catalogs) -> None:
    """
    هر کلیدی که کد صدا می‌زند باید ترجمه داشته باشد.

    نقص واقعی: `reports.exported` در هیچ زبانی نبود و کاربر پس از گرفتن
    خروجی، عبارت خام «reports.exported» را می‌دید.
    """
    fa, en = catalogs
    pattern = re.compile(r"""\.tr\(\s*['"]([a-z0-9_]+\.[a-z0-9_.]+)['"]""")

    used: set[str] = set()
    for folder in ("ui", "app"):
        for path in (ROOT / folder).rglob("*.py"):
            used |= set(pattern.findall(path.read_text(encoding="utf-8")))

    missing_fa = sorted(k for k in used if k not in fa)
    missing_en = sorted(k for k in used if k not in en)
    assert not missing_fa, f"کلید بدون ترجمهٔ فارسی: {missing_fa}"
    assert not missing_en, f"کلید بدون ترجمهٔ انگلیسی: {missing_en}"


@pytest.mark.parametrize(
    "key",
    ["reports.exported", "markets.toman", "common.app_tagline", "signals.wait_no_trade"],
)
def test_previously_missing_keys_resolve(key: str) -> None:
    """این چهار کلید قبلاً غایب بودند؛ نباید دوباره حذف شوند."""
    from localization import Translator

    for lang in ("fa", "en"):
        translator = Translator(lang)
        translator.load()
        rendered = translator.tr(key, direction="WAIT")
        assert rendered != key, f"{lang}: کلید خام برگشت"
        assert rendered.strip()


def test_wait_message_interpolates_direction() -> None:
    """
    جای‌گذاری باید با نام انجام شود.

    نقص واقعی: آرگومان دوم `tr` مقدار پیش‌فرض است نه متغیر، پس فراخوانی
    موضعی باعث می‌شد «{direction}» عیناً به کاربر نشان داده شود.
    """
    from localization import Translator

    translator = Translator("fa")
    translator.load()
    text = translator.tr("signals.wait_no_trade", direction="انتظار")
    assert "{direction}" not in text
    assert "انتظار" in text


def test_market_symbols_are_not_rtl_mangled(qt_application) -> None:  # type: ignore[no-untyped-def]
    """
    نماد بازار باید دقیقاً `BTC/USDT` بماند.

    قانون صریح کاربر: نمادها نباید در چیدمان راست‌به‌چپ به‌هم بریزند و
    رقم‌هایشان هم نباید فارسی شود.
    """
    from localization import Translator
    from ui.pages.markets_page import COL_CHANGE, COL_SYMBOL, MarketsPage

    translator = Translator("fa")
    translator.load()
    page = MarketsPage(translator)
    page.set_rows(
        [{"symbol": "BTC/USDT", "price": 77000.0, "change_percent": -2.5, "high": 1.0, "volume": 9.0}]
    )

    symbol = page.table.item(0, COL_SYMBOL).text()
    assert symbol == "BTC/USDT"
    assert not any(digit in symbol for digit in PERSIAN_DIGITS)

    # درصد تغییر باید نشانگر چپ‌به‌راست داشته باشد وگرنه «-۲.۵٪» وارونه دیده می‌شود
    assert "\u200e" in page.table.item(0, COL_CHANGE).text()
