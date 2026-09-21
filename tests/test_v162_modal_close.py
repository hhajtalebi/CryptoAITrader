"""
آزمون‌های بسته‌شدن مطمئن مدال‌ها.

کاربر گزارش کرد: «مودال بازارها باید مطمئن بسته شود و هنگام بستن کرش
نکند». علت کرش این بود که کار پس‌زمینه پس از بسته‌شدن پنجره، نتیجه را
روی همان پنجره اعمال می‌کرد؛ شیء ++C نابود شده بود و Qt برنامه را با
«Internal C++ object already deleted» می‌بست.

این فایل سه چیز را تضمین می‌کند:
۱. `_dialog_alive` واقعاً نابودی شیء ++C را تشخیص می‌دهد.
۲. همهٔ مسیرهایی که از نخ پس‌زمینه به مدال دست می‌زنند محافظ دارند.
۳. بستن مکرر/با راه‌های مختلف، خطا نمی‌دهد.
"""

from __future__ import annotations

import pytest

pytest.importorskip("shiboken6")

from shiboken6 import delete  # noqa: E402

from localization import Translator  # noqa: E402
from ui.controllers.main_controller import _dialog_alive  # noqa: E402
from ui.dialogs.coin_detail_dialog import CoinDetailDialog  # noqa: E402

#: ردیف نمونه، همان چیزی که جدول بازارها می‌دهد
ROW = {
    "symbol": "BTC/USDT",
    "price": 77000.0,
    "change_percent": 1.2,
    "high": 78000.0,
    "low": 76000.0,
    "volume": 1234.5,
}


@pytest.fixture
def translator() -> Translator:
    """مترجم فارسی."""
    return Translator("fa")


def _dialog(translator: Translator, symbol: str = "BTC/USDT") -> CoinDetailDialog:
    """ساخت مدال جزئیات بدون والد."""
    return CoinDetailDialog(symbol, dict(ROW), translator, None)


# ---------------------------------------------------------------------------
# ۱) تشخیص نابودی شیء
# ---------------------------------------------------------------------------
def test_guard_accepts_a_live_dialog(qt_application, translator) -> None:
    """پنجرهٔ باز باید زنده تشخیص داده شود."""
    dialog = _dialog(translator)
    assert _dialog_alive(dialog) is True


def test_guard_rejects_none() -> None:
    """نبودِ پنجره یعنی زنده نیست."""
    assert _dialog_alive(None) is False


def test_guard_detects_a_destroyed_dialog(qt_application, translator) -> None:
    """
    پس از نابودی شیء ++C، محافظ باید False بدهد.

    این قلب رفع اشکال است: بدون آن، کار پس‌زمینه به حافظهٔ آزادشده دست
    می‌زند و برنامه بسته می‌شود.
    """
    dialog = _dialog(translator)
    dialog.accept()
    delete(dialog)
    assert _dialog_alive(dialog) is False


def test_touching_a_destroyed_dialog_really_raises(qt_application, translator) -> None:
    """
    اثبات اینکه خطر واقعی است، نه فرضی.

    اگر این آزمون روزی شکست بخورد یعنی رفتار Qt عوض شده و محافظ‌ها را
    باید بازبینی کرد.
    """
    dialog = _dialog(translator)
    dialog.accept()
    delete(dialog)

    with pytest.raises(RuntimeError):
        dialog.set_busy(False)


def test_guard_prevents_the_crash(qt_application, translator) -> None:
    """الگوی واقعیِ کد: با محافظ، هیچ خطایی رخ نمی‌دهد."""
    dialog = _dialog(translator)
    dialog.accept()
    delete(dialog)

    # همان کاری که `apply()` در کنترلر می‌کند
    if _dialog_alive(dialog):  # pragma: no cover - نباید وارد شود
        dialog.set_busy(False)
    # رسیدن به اینجا یعنی موفقیت


# ---------------------------------------------------------------------------
# ۲) راه‌های مختلف بستن
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("how", ["accept", "reject", "close"])
def test_every_close_path_works(qt_application, translator, how: str) -> None:
    """
    سه راه بستن (تأیید، انصراف، ضربدر پنجره) باید همگی کار کنند.

    کاربر ممکن است از هر کدام استفاده کند و هیچ‌کدام نباید خطا بدهد.
    """
    dialog = _dialog(translator)
    getattr(dialog, how)()
    assert dialog.isVisible() is False


def test_closing_twice_is_harmless(qt_application, translator) -> None:
    """
    بستن مکرر نباید خطا بدهد.

    دابل‌کلیک روی دکمهٔ بستن یا فشردن Esc هم‌زمان با کلیک، این حالت را
    می‌سازد.
    """
    dialog = _dialog(translator)
    dialog.accept()
    dialog.accept()
    dialog.close()
    dialog.reject()


def test_close_button_is_wired_to_accept(qt_application, translator) -> None:
    """دکمهٔ بستن باید واقعاً پنجره را ببندد."""
    dialog = _dialog(translator)
    dialog.close_button.click()
    assert dialog.isVisible() is False


# ---------------------------------------------------------------------------
# ۳) پوشش محافظ در کد کنترلر
# ---------------------------------------------------------------------------
def test_pdf_export_path_is_guarded() -> None:
    """
    مسیر خروجی PDF هم باید محافظ داشته باشد.

    ساخت PDF کند است و کاربر می‌تواند در همین فاصله پنجره را ببندد.
    این مسیر قبلاً فقط `is not None` را چک می‌کرد که کافی نیست: ارجاع
    پایتونی می‌ماند ولی شیء ++C نابود شده است.
    """
    import inspect

    from ui.controllers.main_controller import MainController

    source = inspect.getsource(MainController._export_analysis_pdf)
    assert "_dialog_alive(dialog)" in source, "PDF export must use the liveness guard"
    assert "if dialog is not None:\n                dialog.set_status" not in source


def test_coin_details_callbacks_are_guarded() -> None:
    """
    هر دو مسیر موفقیت و خطای مدال جزئیات باید محافظ داشته باشند.

    مسیر خطا هم مهم است: شکست شبکه پس از بستن پنجره همان‌قدر کرش
    می‌دهد که موفقیت.
    """
    import inspect

    from ui.controllers.main_controller import MainController

    source = inspect.getsource(MainController._load_coin_details)
    assert source.count("_dialog_alive") >= 2


def test_show_coin_details_cancels_its_background_job() -> None:
    """
    پس از بسته‌شدن مدال، کار پس‌زمینه باید لغو شود.

    فقط محافظ کافی نیست؛ کار بی‌فایده نباید ادامه دهد و پهنای باند و
    وقت پردازنده بگیرد.
    """
    import inspect

    from ui.controllers.main_controller import MainController

    source = inspect.getsource(MainController.show_coin_details)
    assert "finally:" in source
    assert "cancel" in source
