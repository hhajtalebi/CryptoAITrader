"""
آزمون‌های سامانهٔ هشدار.

هشدار قیمتی و هشدار سیگنالی: پیشنهاد شمارهٔ ۲ سند قابلیت‌های تازه.
هدف این است که کاربر مجبور نباشد به صفحه خیره شود.
"""

from __future__ import annotations

import inspect

import pytest

from signals.alerts import (
    ALERT_ABOVE,
    ALERT_BELOW,
    KIND_PRICE,
    KIND_SIGNAL,
    Alert,
    AlertBook,
)


class TestAlertValidation:
    """هشدار نامعتبر نباید بی‌سروصدا پذیرفته شود."""

    def test_valid_price_alert(self) -> None:
        """هشدار قیمتی درست پذیرفته می‌شود."""
        ok, _ = Alert(symbol="BTC/USDT", direction=ALERT_ABOVE, value=85_000).is_valid()
        assert ok

    def test_price_alert_needs_a_symbol(self) -> None:
        """بدون نماد، هشدار قیمتی بی‌معناست."""
        ok, reason = Alert(symbol="", value=100).is_valid()
        assert not ok
        assert reason

    def test_price_alert_rejects_zero(self) -> None:
        """قیمت صفر یعنی کاربر عدد وارد نکرده."""
        ok, _ = Alert(symbol="BTC/USDT", value=0).is_valid()
        assert not ok

    def test_price_alert_rejects_bad_direction(self) -> None:
        """جهت نامعتبر باید رد شود."""
        ok, _ = Alert(symbol="BTC/USDT", value=1, direction="sideways").is_valid()
        assert not ok

    def test_signal_alert_needs_confidence_in_range(self) -> None:
        """اطمینان باید بین ۱ تا ۱۰۰ باشد."""
        assert Alert(kind=KIND_SIGNAL, min_confidence=70).is_valid()[0]
        assert not Alert(kind=KIND_SIGNAL, min_confidence=0).is_valid()[0]
        assert not Alert(kind=KIND_SIGNAL, min_confidence=101).is_valid()[0]

    def test_unknown_kind_is_rejected(self) -> None:
        """نوع ناشناخته نباید ساخته شود."""
        assert not Alert(kind="telepathy").is_valid()[0]


class TestPriceMatching:
    """شرط فعال‌شدن هشدار قیمتی."""

    def test_above_fires_at_or_over_target(self) -> None:
        """رسیدن یا عبور از هدف، هشدار را فعال می‌کند."""
        alert = Alert(symbol="BTC/USDT", direction=ALERT_ABOVE, value=100)
        assert alert.matches_price(100)
        assert alert.matches_price(120)
        assert not alert.matches_price(99)

    def test_below_fires_at_or_under_target(self) -> None:
        """افت تا هدف یا پایین‌تر."""
        alert = Alert(symbol="BTC/USDT", direction=ALERT_BELOW, value=100)
        assert alert.matches_price(100)
        assert alert.matches_price(80)
        assert not alert.matches_price(101)

    def test_disabled_alert_never_fires(self) -> None:
        """هشدار خاموش نباید فعال شود."""
        alert = Alert(symbol="BTC/USDT", value=100, enabled=False)
        assert not alert.matches_price(200)

    def test_already_triggered_alert_does_not_refire(self) -> None:
        """
        مهم‌ترین قاعدهٔ کاربردپذیری.

        بدون این، هر تیک دوباره فعال می‌شود و کاربر زیر بار اعلان دفن
        می‌شود تا برنامه را ببندد.
        """
        alert = Alert(symbol="BTC/USDT", value=100, triggered=True)
        assert not alert.matches_price(200)

    def test_zero_price_is_ignored(self) -> None:
        """قیمت صفر یعنی داده نرسیده، نه اینکه بازار صفر شده."""
        alert = Alert(symbol="BTC/USDT", direction=ALERT_BELOW, value=100)
        assert not alert.matches_price(0)


class TestSignalMatching:
    """شرط فعال‌شدن هشدار سیگنالی."""

    def _alert(self, **kwargs) -> Alert:
        base = {"kind": KIND_SIGNAL, "min_confidence": 70}
        base.update(kwargs)
        return Alert(**base)

    def test_high_confidence_signal_fires(self) -> None:
        """سیگنال قوی باید خبر بدهد."""
        assert self._alert().matches_signal(
            {"symbol": "BTC/USDT", "direction": "LONG", "confidence": 80}
        )

    def test_low_confidence_signal_does_not_fire(self) -> None:
        """سیگنال ضعیف نباید کاربر را بیدار کند."""
        assert not self._alert().matches_signal(
            {"symbol": "BTC/USDT", "direction": "LONG", "confidence": 50}
        )

    def test_wait_signal_never_fires(self) -> None:
        """
        «انتظار» توصیهٔ معاملاتی نیست.

        حتی با اطمینان ۹۵٪، خبردادنش فقط مزاحمت است.
        """
        assert not self._alert().matches_signal(
            {"symbol": "BTC/USDT", "direction": "WAIT", "confidence": 95}
        )

    def test_symbol_filter_is_respected(self) -> None:
        """هشدار مخصوص یک نماد نباید برای نماد دیگر فعال شود."""
        alert = self._alert(symbol="BTC/USDT")
        assert not alert.matches_signal(
            {"symbol": "ETH/USDT", "direction": "LONG", "confidence": 90}
        )

    def test_empty_symbol_means_all_symbols(self) -> None:
        """هشدار بدون نماد یعنی «همهٔ نمادها»."""
        assert self._alert(symbol="").matches_signal(
            {"symbol": "DOGE/USDT", "direction": "SHORT", "confidence": 75}
        )

    def test_malformed_confidence_does_not_crash(self) -> None:
        """دادهٔ خراب نباید استثنا بدهد."""
        assert not self._alert().matches_signal(
            {"symbol": "BTC/USDT", "direction": "LONG", "confidence": "high"}
        )


class TestAlertBook:
    """مدیریت مجموعهٔ هشدارها."""

    def test_add_assigns_unique_ids(self) -> None:
        """هر هشدار شناسهٔ یکتا می‌گیرد."""
        book = AlertBook()
        book.add(Alert(symbol="BTC/USDT", value=1))
        book.add(Alert(symbol="ETH/USDT", value=2))
        assert [item.id for item in book.alerts] == [1, 2]

    def test_add_rejects_invalid(self) -> None:
        """هشدار نامعتبر اضافه نمی‌شود و دلیلش برمی‌گردد."""
        book = AlertBook()
        ok, reason = book.add(Alert(symbol="", value=0))
        assert not ok
        assert reason
        assert not book.alerts

    def test_remove_works(self) -> None:
        """حذف باید واقعاً حذف کند."""
        book = AlertBook()
        book.add(Alert(symbol="BTC/USDT", value=1))
        assert book.remove(1)
        assert not book.alerts
        assert not book.remove(99)

    def test_rearm_resets_triggered(self) -> None:
        """کاربر باید بتواند هشدار فعال‌شده را دوباره مسلح کند."""
        book = AlertBook()
        book.add(Alert(symbol="BTC/USDT", direction=ALERT_ABOVE, value=100))
        book.check_prices({"BTC/USDT": 150})
        assert book.alerts[0].triggered
        assert book.rearm(1)
        assert not book.alerts[0].triggered

    def test_active_symbols_only_lists_armed_price_alerts(self) -> None:
        """
        فقط نمادهایی که واقعاً هشدار مسلح دارند.

        گرفتن قیمت برای هشدار خاموش یا فعال‌شده، هدردادن پهنای باند است.
        """
        book = AlertBook()
        book.add(Alert(symbol="BTC/USDT", value=1))
        book.add(Alert(symbol="ETH/USDT", value=1, enabled=False))
        book.add(Alert(kind=KIND_SIGNAL, min_confidence=70))
        assert book.active_symbols() == ["BTC/USDT"]

    def test_check_prices_marks_triggered(self) -> None:
        """فعال‌شدن باید ثبت شود تا تکرار نشود."""
        book = AlertBook()
        book.add(Alert(symbol="BTC/USDT", direction=ALERT_ABOVE, value=100))
        assert len(book.check_prices({"BTC/USDT": 150})) == 1
        assert book.check_prices({"BTC/USDT": 160}) == []

    def test_missing_symbol_price_is_skipped(self) -> None:
        """نبودِ قیمت نباید خطا بدهد."""
        book = AlertBook()
        book.add(Alert(symbol="BTC/USDT", value=100))
        assert book.check_prices({"ETH/USDT": 5}) == []

    def test_round_trip_through_storage(self) -> None:
        """ذخیره و بازخوانی باید وضعیت را حفظ کند."""
        book = AlertBook()
        book.add(Alert(symbol="BTC/USDT", direction=ALERT_ABOVE, value=85_000))
        book.add(Alert(kind=KIND_SIGNAL, min_confidence=70))
        book.check_prices({"BTC/USDT": 90_000})

        restored = AlertBook.from_list(book.as_list())
        assert len(restored.alerts) == 2
        assert restored.alerts[0].triggered
        assert not restored.alerts[1].triggered

    def test_malformed_storage_is_tolerated(self) -> None:
        """دادهٔ خراب در تنظیمات نباید برنامه را از کار بیندازد."""
        restored = AlertBook.from_list(
            ["junk", None, 42, {"kind": KIND_PRICE, "symbol": "X/USDT", "value": 1}]
        )
        assert len(restored.alerts) == 1

    def test_non_list_storage_is_tolerated(self) -> None:
        """اگر تنظیمات چیز دیگری باشد، نباید استثنا بدهد."""
        assert AlertBook.from_list("nonsense").alerts == []
        assert AlertBook.from_list(None).alerts == []

    def test_describe_is_human_readable(self) -> None:
        """متن فهرست باید برای کاربر معنا داشته باشد."""
        price = Alert(symbol="BTC/USDT", direction=ALERT_ABOVE, value=85_000)
        assert "BTC/USDT" in price.describe()
        signal = Alert(kind=KIND_SIGNAL, min_confidence=70)
        assert "70" in signal.describe()


class TestWiring:
    """هشدارها باید واقعاً به برنامه وصل باشند."""

    def test_settings_define_alert_keys(self) -> None:
        """کلیدهای تنظیمات باید وجود داشته باشند."""
        from app.config.defaults import DEFAULT_SETTINGS, SettingKey

        assert SettingKey.ALERTS_ENABLED.value in DEFAULT_SETTINGS
        assert SettingKey.ALERTS_ITEMS.value in DEFAULT_SETTINGS
        assert DEFAULT_SETTINGS[SettingKey.ALERTS_ITEMS.value] == []

    def test_controller_checks_price_alerts(self) -> None:
        """کنترلر باید هشدارهای قیمتی را بررسی کند."""
        from ui.controllers.main_controller import MainController

        assert hasattr(MainController, "_run_alert_check")
        source = inspect.getsource(MainController._run_alert_check)
        assert "check_prices" in source

    def test_price_check_only_fetches_armed_symbols(self) -> None:
        """نباید برای کل بازار قیمت گرفته شود."""
        from ui.controllers.main_controller import MainController

        source = inspect.getsource(MainController._run_alert_check)
        assert "active_symbols" in source

    def test_controller_checks_signal_alerts(self) -> None:
        """هشدار سیگنالی باید هنگام تولید سیگنال بررسی شود."""
        from ui.controllers.main_controller import MainController

        assert hasattr(MainController, "check_signal_alerts")

    def test_triggered_state_is_persisted(self) -> None:
        """
        بدون ذخیره، هشدار با هر تیک دوباره فعال می‌شود.
        """
        from ui.controllers.main_controller import MainController

        source = inspect.getsource(MainController._run_alert_check)
        assert "_save_alert_book" in source

    def test_controller_can_create_an_alert(self) -> None:
        """کاربر باید بتواند از رابط کاربری هشدار بسازد."""
        from ui.controllers.main_controller import MainController

        assert hasattr(MainController, "create_price_alert")


@pytest.mark.usefixtures("qt_application")
class TestMarketsPageButton:
    """دکمهٔ ساخت هشدار روی صفحهٔ بازارها."""

    def test_markets_page_has_alert_button(self) -> None:
        """دکمه باید وجود داشته باشد."""
        from localization import Translator
        from ui.pages.markets_page import MarketsPage

        page = MarketsPage(Translator("fa"))
        assert hasattr(page, "alert_button")
        assert "alerts.add" not in page.alert_button.text()

    def test_alert_button_emits_selected_symbol(self) -> None:
        """کلیک باید نماد انتخاب‌شده را بفرستد."""
        from localization import Translator
        from ui.pages.markets_page import MarketsPage

        page = MarketsPage(Translator("fa"))
        seen: list[str] = []
        page.alert_requested.connect(seen.append)
        # بدون انتخاب نماد نباید چیزی فرستاده شود
        page.alert_button.click()
        assert seen == []
