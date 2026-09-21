"""
آزمون ماشین‌حساب حجم پوزیشن (مورد ۲.۱ نقشهٔ راه).

سه لایه آزموده می‌شود: ریاضیاتِ ماژول خالص، رفتار ویجت هنگام تایپ
کاربر، و همسانی کلیدهای ترجمه در دو زبان. تأکید روی خطاهایی است که
واقعاً پول کاربر را می‌سوزاند: حجمی که تضمین را از سرمایه بیشتر کند،
حد ضرری که آن‌سوی قیمت لیکوییدیشن باشد، و خطای ورودی که وسط تایپ
برنامه را بیندازد.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from localization import Translator
from signals.position_sizing import (
    DEFAULT_FEE_PERCENT,
    MAX_LEVERAGE,
    breakeven_price,
    calculate_position,
    required_win_rate,
)

ARABIC_RANGE = re.compile(r"[\u0600-\u06ff]")
LOCALE_ROOT = Path(__file__).resolve().parents[1] / "localization"


# ---------------------------------------------------------------- ریاضیات


def test_worked_example_matches_the_tutorial() -> None:
    """
    همان مثالی که در آموزش برنامه آمده باید عیناً بازتولید شود.

    سرمایهٔ ۱۰۰۰ با ریسک ۱٪ یعنی ۱۰ دلار ریسک؛ فاصلهٔ حد ضرر ۲٪ یعنی
    حجم ۰٫۰۰۸۳۳۳۳۳ بیت‌کوین و ارزش ۵۰۰ دلار که با اهرم ۵ فقط ۱۰۰ دلار
    تضمین می‌خواهد. اگر این عددها عوض شوند، متن آموزش دروغ شده است.
    """
    plan = calculate_position(
        capital=1000.0,
        risk_percent=1.0,
        entry=60000.0,
        stop_loss=58800.0,
        leverage=5,
        take_profit=63600.0,
    )

    assert plan.valid
    assert plan.quantity == pytest.approx(0.00833333, abs=1e-8)
    assert plan.notional == pytest.approx(500.0, abs=0.01)
    assert plan.margin == pytest.approx(100.0, abs=0.01)
    assert plan.risk_amount == pytest.approx(10.0, abs=0.01)
    assert plan.risk_percent_actual == pytest.approx(1.0, abs=0.01)
    assert plan.stop_distance_percent == pytest.approx(2.0, abs=0.01)
    assert plan.reward_amount == pytest.approx(30.0, abs=0.01)
    assert plan.risk_reward == pytest.approx(3.0, abs=0.01)
    assert plan.warnings == ()


def test_direction_is_inferred_from_stop_placement() -> None:
    """کاربر نباید جهت را جداگانه انتخاب کند؛ جای حد ضرر گویاست."""
    long_plan = calculate_position(
        capital=1000.0, risk_percent=1.0, entry=100.0, stop_loss=95.0
    )
    short_plan = calculate_position(
        capital=1000.0, risk_percent=1.0, entry=100.0, stop_loss=105.0
    )

    assert long_plan.direction == "LONG"
    assert short_plan.direction == "SHORT"


def test_short_position_profits_when_price_falls() -> None:
    """در پوزیشن فروش، هدفِ پایین‌تر سود است نه زیان."""
    plan = calculate_position(
        capital=1000.0,
        risk_percent=1.0,
        entry=100.0,
        stop_loss=105.0,
        take_profit=90.0,
    )

    assert plan.direction == "SHORT"
    assert plan.reward_amount > 0
    assert plan.risk_reward == pytest.approx(2.0, abs=0.01)


def test_target_on_the_wrong_side_yields_no_reward() -> None:
    """هدفِ پشت حد ضرر نباید به‌عنوان سود شمرده شود."""
    plan = calculate_position(
        capital=1000.0,
        risk_percent=1.0,
        entry=100.0,
        stop_loss=95.0,
        take_profit=90.0,
    )

    assert plan.reward_amount == 0.0
    assert plan.risk_reward == 0.0


def test_risk_amount_is_independent_of_leverage() -> None:
    """
    اشتباه رایج معامله‌گران: گمان می‌کنند اهرم بالاتر یعنی ریسک بیشتر.

    ریسک را فاصلهٔ حد ضرر تعیین می‌کند؛ اهرم فقط وجه تضمین را کم می‌کند.
    """
    low = calculate_position(
        capital=1000.0, risk_percent=1.0, entry=100.0, stop_loss=98.0, leverage=2
    )
    high = calculate_position(
        capital=1000.0, risk_percent=1.0, entry=100.0, stop_loss=98.0, leverage=20
    )

    assert low.risk_amount == pytest.approx(high.risk_amount)
    assert low.quantity == pytest.approx(high.quantity)
    assert high.margin < low.margin


def test_liquidation_price_moves_against_the_position() -> None:
    """قیمت لیکوییدیشن خرید باید پایین‌تر و فروش بالاتر از ورود باشد."""
    long_plan = calculate_position(
        capital=1000.0, risk_percent=1.0, entry=100.0, stop_loss=98.0, leverage=10
    )
    short_plan = calculate_position(
        capital=1000.0, risk_percent=1.0, entry=100.0, stop_loss=102.0, leverage=10
    )

    assert long_plan.liquidation_price == pytest.approx(90.0, abs=0.01)
    assert short_plan.liquidation_price == pytest.approx(110.0, abs=0.01)


def test_spot_position_has_no_liquidation_price() -> None:
    """بدون اهرم لیکوییدیشنی در کار نیست؛ عدد جعلی نباید ساخته شود."""
    plan = calculate_position(
        capital=1000.0, risk_percent=1.0, entry=100.0, stop_loss=90.0, leverage=1
    )

    assert plan.liquidation_price == 0.0


def test_stop_beyond_liquidation_is_warned() -> None:
    """
    خطرناک‌ترین حالت: پیش از خوردن حد ضرر، پوزیشن لیکویید می‌شود.

    با اهرم ۲۵ فاصلهٔ لیکوییدیشن حدود ۴٪ است، پس حد ضرر ۱۰٪ یعنی کل
    وجه تضمین از دست می‌رود. این هشدار باید اول فهرست بیاید.
    """
    plan = calculate_position(
        capital=1000.0, risk_percent=1.0, entry=100.0, stop_loss=90.0, leverage=25
    )

    assert "sizing.warn_stop_beyond_liquidation" in plan.warnings
    assert plan.warnings[0] == "sizing.warn_stop_beyond_liquidation"


def test_margin_exceeding_capital_is_warned() -> None:
    """اگر وجه تضمین از سرمایه بیشتر شود، معامله اصلاً باز نمی‌شود."""
    plan = calculate_position(
        capital=100.0,
        risk_percent=50.0,
        entry=100.0,
        stop_loss=99.0,
        leverage=2,
    )

    assert plan.margin > plan.capital
    assert "sizing.warn_margin_exceeds_capital" in plan.warnings


def test_safe_plan_has_no_warnings() -> None:
    """برنامهٔ محافظه‌کارانه نباید کاربر را بی‌جهت بترساند."""
    plan = calculate_position(
        capital=5000.0,
        risk_percent=1.0,
        entry=100.0,
        stop_loss=98.0,
        leverage=3,
        take_profit=106.0,
    )

    assert plan.warnings == ()


def test_invalid_input_returns_error_instead_of_raising() -> None:
    """ماشین‌حساب وسط تایپ کاربر نباید استثنا پرتاب کند."""
    same = calculate_position(
        capital=1000.0, risk_percent=1.0, entry=100.0, stop_loss=100.0
    )
    no_capital = calculate_position(
        capital=0.0, risk_percent=1.0, entry=100.0, stop_loss=95.0
    )

    assert not same.valid
    assert same.error_key == "sizing.error_same_price"
    assert not no_capital.valid
    assert no_capital.error_key == "sizing.error_capital"


def test_leverage_is_clamped_to_the_exchange_maximum() -> None:
    """اهرم بی‌نهایت وجود ندارد؛ عدد باید به سقف چسبانده شود."""
    plan = calculate_position(
        capital=1000.0,
        risk_percent=1.0,
        entry=100.0,
        stop_loss=99.5,
        leverage=10_000,
    )

    assert plan.leverage == MAX_LEVERAGE


def test_fee_scales_with_notional_and_counts_both_sides() -> None:
    """کارمزد رفت‌وبرگشت است؛ یک‌طرفه حساب‌کردن سود را بزرگ‌نمایی می‌کند."""
    plan = calculate_position(
        capital=1000.0,
        risk_percent=1.0,
        entry=60000.0,
        stop_loss=58800.0,
        leverage=5,
        fee_percent=DEFAULT_FEE_PERCENT,
    )

    one_side = plan.notional * DEFAULT_FEE_PERCENT / 100
    assert plan.fee_amount == pytest.approx(one_side * 2, abs=1e-6)


def test_required_win_rate_matches_the_textbook_values() -> None:
    """نرخ برد لازم = ۱۰۰÷(۱+نسبت) — ستون فقرات بحث انتظار ریاضی."""
    assert required_win_rate(1.0) == pytest.approx(50.0, abs=0.01)
    assert required_win_rate(2.0) == pytest.approx(33.33, abs=0.01)
    assert required_win_rate(3.0) == pytest.approx(25.0, abs=0.01)
    # بدون هدف سود، هیچ نرخ بردی سربه‌سر نمی‌کند؛ ۱۰۰ درصد پاسخ صادقانه‌تری
    # از صفر است.
    assert required_win_rate(0.0) == 100.0


def test_breakeven_price_accounts_for_fees() -> None:
    """نقطهٔ سربه‌سر خرید باید کمی بالاتر از ورود باشد، نه برابر آن."""
    price = breakeven_price(entry=100.0, direction="LONG", fee_percent=0.1)
    short = breakeven_price(entry=100.0, direction="SHORT", fee_percent=0.1)

    # رفت‌وبرگشت: دو بار ۰٫۱ درصد
    assert price == pytest.approx(100.2, abs=0.01)
    assert short == pytest.approx(99.8, abs=0.01)


# ------------------------------------------------------------------ ویجت


@pytest.fixture()
def calculator(qt_application):  # noqa: ANN201, ARG001 - نیاز به QApplication
    """یک ماشین‌حساب فارسی تازه برای هر آزمون."""
    from ui.widgets.position_calculator import PositionCalculator

    return PositionCalculator(Translator("fa"))


def test_widget_recalculates_without_a_button(calculator) -> None:  # noqa: ANN001
    """کاربر نباید دنبال دکمهٔ «محاسبه» بگردد؛ تغییر عدد کافی است."""
    calculator.set_capital(1000.0)
    calculator.set_risk_percent(1.0)
    calculator.entry_input.setValue(60000.0)
    calculator.stop_input.setValue(58800.0)
    calculator.leverage_input.setValue(5)

    plan = calculator.plan
    assert plan is not None
    assert plan.valid
    assert plan.quantity == pytest.approx(0.00833333, abs=1e-8)


def test_widget_emits_plan_changed(calculator) -> None:  # noqa: ANN001
    """صفحهٔ میزبان باید بتواند به نتیجهٔ محاسبه واکنش نشان دهد."""
    received: list[object] = []
    calculator.plan_changed.connect(received.append)

    calculator.entry_input.setValue(100.0)
    calculator.stop_input.setValue(95.0)

    assert received
    assert received[-1].valid


def test_load_signal_keeps_the_user_capital(calculator) -> None:  # noqa: ANN001
    """
    سرمایه مال کاربر است نه سیگنال.

    اگر بارگذاری سیگنال سرمایه را بازنویسی کند، کاربر هر بار باید عدد
    حساب خود را دوباره وارد کند.
    """
    calculator.set_capital(2500.0)
    calculator.set_risk_percent(2.0)

    calculator.load_signal(
        {
            "entry_price": 60000.0,
            "stop_loss": 58800.0,
            "take_profits": [63600.0],
            "leverage": 5,
        }
    )

    assert calculator.capital_input.value() == pytest.approx(2500.0)
    assert calculator.risk_input.value() == pytest.approx(2.0)
    assert calculator.entry_input.value() == pytest.approx(60000.0)
    assert calculator.stop_input.value() == pytest.approx(58800.0)
    assert calculator.target_input.value() == pytest.approx(63600.0)
    assert calculator.leverage_input.value() == 5


def test_warnings_are_shown_as_translated_text(calculator) -> None:  # noqa: ANN001
    """هشدار باید فارسیِ خوانا باشد، نه کلید ترجمه."""
    calculator.set_capital(1000.0)
    calculator.set_risk_percent(5.0)
    calculator.entry_input.setValue(60000.0)
    calculator.stop_input.setValue(54000.0)
    calculator.leverage_input.setValue(25)

    text = calculator.warning_label.text()
    assert text
    assert "sizing." not in text
    assert ARABIC_RANGE.search(text)


def test_warnings_hidden_for_a_safe_plan(calculator) -> None:  # noqa: ANN001
    """برچسب هشدار نباید به‌صورت جعبهٔ خالی روی فرم بماند."""
    calculator.set_capital(5000.0)
    calculator.set_risk_percent(1.0)
    calculator.entry_input.setValue(100.0)
    calculator.stop_input.setValue(98.0)
    calculator.leverage_input.setValue(3)
    calculator.target_input.setValue(106.0)

    assert not calculator.warning_label.isVisibleTo(calculator)


def test_quantity_is_shown_in_latin_digits(calculator) -> None:  # noqa: ANN001
    """
    حجم را کاربر در صرافی کپی می‌کند.

    ارقام فارسی آنجا پذیرفته نمی‌شود، پس این یک سلول باید لاتین بماند
    حتی وقتی کل برنامه فارسی است.
    """
    calculator.set_capital(1000.0)
    calculator.entry_input.setValue(60000.0)
    calculator.stop_input.setValue(58800.0)

    text = calculator.result_value("quantity")
    assert "0.00833333" == text


def test_price_input_hides_trailing_zeros(calculator) -> None:  # noqa: ANN001
    """«۶۰۰۰۰٫۰۰۰۰۰۰۰۰» ورودی را ناخواناتر می‌کند بدون افزودن اطلاعات."""
    calculator.entry_input.setValue(60000.0)

    assert calculator.entry_input.text().replace(",", "") == "60000"


def test_price_input_keeps_small_coin_precision(calculator) -> None:  # noqa: ANN001
    """دقت برای ارزهای ارزان حیاتی است و نباید قربانی زیبایی شود."""
    calculator.entry_input.setValue(0.00002345)

    assert calculator.entry_input.value() == pytest.approx(0.00002345, abs=1e-10)
    assert "0.00002345" in calculator.entry_input.text()


def test_invalid_state_shows_a_message_not_a_crash(calculator) -> None:  # noqa: ANN001
    """ورود و حد ضرر برابر حالت طبیعیِ وسط تایپ است."""
    calculator.entry_input.setValue(100.0)
    calculator.stop_input.setValue(100.0)

    assert calculator.plan is not None
    assert not calculator.plan.valid
    assert calculator.warning_label.text()


def test_retranslate_switches_language(calculator) -> None:  # noqa: ANN001
    """تعویض زبان نباید برچسب فارسی جامانده بگذارد."""
    calculator.entry_input.setValue(100.0)
    calculator.stop_input.setValue(95.0)
    assert ARABIC_RANGE.search(calculator.result_title.text())

    calculator.retranslate(Translator("en"))

    assert not ARABIC_RANGE.search(calculator.result_title.text())
    labels = [label.text() for label, _key in calculator._form_labels]
    assert labels and not any(ARABIC_RANGE.search(text) for text in labels)


# ------------------------------------------------------------- ترجمه‌ها


def _load(language: str) -> dict[str, str]:
    return json.loads((LOCALE_ROOT / language / "sizing.json").read_text("utf-8"))


def test_sizing_locale_keys_match_across_languages() -> None:
    """کلید جامانده یعنی متن انگلیسیِ خام وسط رابط فارسی."""
    assert set(_load("fa")) == set(_load("en"))


def test_sizing_texts_are_in_the_right_script() -> None:
    """فارسیِ فارسی و انگلیسیِ انگلیسی؛ بدون جابه‌جایی."""
    for value in _load("fa").values():
        assert ARABIC_RANGE.search(value), value
    for value in _load("en").values():
        assert not ARABIC_RANGE.search(value), value


def test_every_warning_and_error_key_has_a_translation() -> None:
    """
    هشداری که ترجمه ندارد، به کاربر به‌شکل «sizing.warn_…» نشان داده
    می‌شود — یعنی دقیقاً در خطرناک‌ترین لحظه رابط خراب می‌شود.
    """
    from signals import position_sizing

    source = Path(position_sizing.__file__).read_text("utf-8")
    used = set(re.findall(r'"sizing\.((?:warn|error)_[a-z_]+)"', source))
    assert used, "هیچ کلید هشداری پیدا نشد؛ الگوی جست‌وجو کهنه شده است."

    for language in ("fa", "en"):
        available = set(_load(language))
        assert used <= available, sorted(used - available)


def test_calculator_rows_have_labels_in_both_languages() -> None:
    """هر سطر نتیجه باید در هر دو زبان عنوان داشته باشد."""
    from ui.widgets.position_calculator import RESULT_ROWS

    for language in ("fa", "en"):
        available = set(_load(language))
        for name in RESULT_ROWS:
            assert f"row_{name}" in available, (language, name)


# --------------------------------------------------- یکپارچگی با پنجرهٔ سیگنال


@pytest.fixture()
def detail_dialog(qt_application):  # noqa: ANN201, ARG001 - نیاز به QApplication
    """پنجرهٔ جزئیات با یک سیگنال واقعیِ موتور."""
    from ui.dialogs.signal_detail_dialog import SignalDetailDialog

    signal = {
        "symbol": "BTC/USDT",
        "direction": "LONG",
        "confidence": 72,
        "entry_price": 60000.0,
        "stop_loss": 58800.0,
        "take_profits": [63600.0, 66000.0],
        "risk_reward": 3.0,
        "leverage": 5,
        "primary_timeframe": "4h",
    }
    dialog = SignalDetailDialog(signal, Translator("fa"))
    yield dialog
    dialog.deleteLater()


def test_dialog_embeds_a_prefilled_calculator(detail_dialog) -> None:  # noqa: ANN001
    """
    تصمیم «با چه حجمی وارد شوم» همین‌جا گرفته می‌شود.

    اگر کاربر مجبور باشد اعداد را در صفحه‌ای دیگر دوباره تایپ کند،
    ماشین‌حساب عملاً بی‌استفاده می‌ماند.
    """
    calc = detail_dialog.calculator

    assert calc.entry_input.value() == pytest.approx(60000.0)
    assert calc.stop_input.value() == pytest.approx(58800.0)
    assert calc.target_input.value() == pytest.approx(63600.0)
    assert calc.leverage_input.value() == 5


def test_dialog_shows_the_entry_price(detail_dialog) -> None:
    """
    سیگنال‌های موتور کلید `entry_price` دارند، نه `entry`.

    پیش‌تر سطر «ورود» برای هر سیگنال واقعی خط تیره نشان می‌داد چون فقط
    کلید `entry` خوانده می‌شد.
    """
    text = detail_dialog._entry_text()

    assert text != "—"
    assert "60" in text or "۶۰" in text


def test_dialog_prices_have_no_padding_zeros(detail_dialog) -> None:
    """
    «۵۸٬۸۰۰٫۰۰۰۰» صفرهایش محلی‌سازی‌شده است و با rstrip لاتین پاک نمی‌شد.
    """
    text = detail_dialog._price(58800.0)

    assert not text.endswith("۰۰۰۰")
    assert "." not in text and "٫" not in text


def test_set_account_balance_overrides_the_default_capital(detail_dialog) -> None:
    """سرمایهٔ واقعی کاربر از تنظیمات می‌آید، نه عدد پیش‌فرض ۱۰۰۰."""
    detail_dialog.set_account_balance(2500.0, 2.0)

    assert detail_dialog.calculator.capital_input.value() == pytest.approx(2500.0)
    assert detail_dialog.calculator.risk_input.value() == pytest.approx(2.0)
    plan = detail_dialog.calculator.plan
    assert plan.risk_amount == pytest.approx(50.0, abs=0.01)


def test_zero_balance_does_not_wipe_the_calculator(detail_dialog) -> None:
    """
    کیف پول خالی یا هنوز بارگذاری‌نشده نباید سرمایه را صفر کند.

    وگرنه کاربر به‌جای نتیجه، پیام خطای «سرمایه نامعتبر» می‌بیند.
    """
    before = detail_dialog.calculator.capital_input.value()

    detail_dialog.set_account_balance(0.0, 0.0)

    assert detail_dialog.calculator.capital_input.value() == pytest.approx(before)


def test_controller_primes_the_calculator_from_settings() -> None:
    """
    کنترلر باید سرمایه را به هر دو محل ساخت پنجره بدهد.

    یکی از مسیرها (پویش انبوه) به‌راحتی از قلم می‌افتد.
    """
    from pathlib import Path

    source = Path("ui/controllers/main_controller.py").read_text("utf-8")

    assert "def _prime_calculator" in source
    assert source.count("self._prime_calculator(dialog)") == 2
    assert "risk.account_balance" in source
