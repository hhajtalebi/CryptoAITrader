"""
آزمون‌های پیکربندی بسته‌بندی ویندوزی.

این‌ها بدون اجرای PyInstaller، محتوای فایل spec را بررسی می‌کنند تا
داده‌های حیاتی از بسته جا نمانند. جاماندن آن‌ها فقط در نسخهٔ نصبی
خودش را نشان می‌دهد — جایی که دیگر دیر است.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SPEC_PATH = Path(__file__).resolve().parent.parent / "CryptoAITrader.spec"


@pytest.fixture(scope="module")
def spec_text() -> str:
    """متن فایل spec."""
    assert SPEC_PATH.exists(), "فایل spec باید کنار پروژه باشد"
    return SPEC_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "needle",
    [
        "localization",
        "ai" + '" / "' + "prompts",
        "assets",
        "migrations",
        "alembic.ini",
    ],
)
def test_critical_data_is_bundled(spec_text: str, needle: str) -> None:
    """داده‌هایی که در زمان اجرا از دیسک خوانده می‌شوند باید در بسته باشند."""
    assert needle in spec_text, f"{needle} در datas نیست"


def test_persian_font_is_bundled(spec_text: str) -> None:
    """
    قلم فارسی باید در بسته باشد.

    نقص واقعی: قلم بسته‌بندی نمی‌شد و خروجی PDF فارسی در نسخهٔ نصبی به
    قلم پیش‌فرض برمی‌گشت و حروف به‌هم‌ریخته چاپ می‌شد.
    """
    assert "fonts" in spec_text, "پوشهٔ قلم در datas نیست"

    fonts_dir = SPEC_PATH.parent / "assets" / "fonts"
    assert (fonts_dir / "Vazirmatn-Regular.ttf").exists()
    assert (fonts_dir / "Vazirmatn-Bold.ttf").exists()
    # قلم «ب کودک» هم باید همراه بسته برود؛ رابط کاربری از نسخهٔ ۱٫۶٫۱
    # به‌صورت پیش‌فرض با همین قلم فارسی را نشان می‌دهد و نبودش یعنی
    # بازگشت خاموش به قلم سیستم.
    assert (fonts_dir / "BKoodakBd.ttf").exists()
    assert (fonts_dir / "Koodak.ttf").exists()


def test_pandas_submodules_are_not_excluded(spec_text: str) -> None:
    """
    زیرماژول‌های pandas نباید حذف شوند.

    آزموده شد: حذفشان برنامه را هنگام بالا آمدن با
    `ModuleNotFoundError: pandas.io.stata` می‌شکند، چون
    `pandas.api.typing` آن‌ها را بی‌قیدوشرط وارد می‌کند.
    """
    for forbidden in ('"pandas.io.stata"', '"pandas.io.html"', '"pandas.io.sas"'):
        assert forbidden not in spec_text, f"{forbidden} نباید در excludes باشد"


def test_dynamic_registries_are_hidden_imports(spec_text: str) -> None:
    """رجیستری‌های پویا در تحلیل ایستا دیده نمی‌شوند."""
    for module in ("market.providers", "indicators", "signals.strategies", "ai.providers"):
        assert module in spec_text, f"{module} در hiddenimports نیست"


def test_gui_app_has_no_console_window(spec_text: str) -> None:
    """برنامهٔ گرافیکی نباید پنجرهٔ کنسول باز کند."""
    assert "console=False" in spec_text


def test_version_is_consistent() -> None:
    """نسخه در همه‌جا یکی باشد، وگرنه گزارش خطای کاربر گمراه‌کننده می‌شود."""
    import tomllib

    from app.core.constants import APP_VERSION

    root = SPEC_PATH.parent
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == APP_VERSION
    assert APP_VERSION in (root / "BUILD_INFO.txt").read_text(encoding="utf-8")
