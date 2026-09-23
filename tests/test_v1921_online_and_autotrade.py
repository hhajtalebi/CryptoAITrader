"""
آزمون‌های سه خواستهٔ کاربر در نسخهٔ ۱.۹.۲۱.

۱. «بازار خیلی آفلاین می‌زند» — تحمل قطعی‌های گذرا.
۲. «تنظیمات دستی برای معاملهٔ خودکار».
۳. «روی همهٔ ارزها تحلیل کن؛ بالای ۷۵٪ اطمینان معامله کن».
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from localization import Translator
from market.engine import REST_FAILURE_TOLERANCE
from trading.confidence_source import (
    ABSOLUTE_MIN_CONFIDENCE,
    ConfidenceCandidate,
    ConfidenceCandidateSource,
)
from trading.auto_trader import HARD_MAX_LEVERAGE
from ui.pages.trades_page import TradesPage


@pytest.fixture(scope="module")
def qt_application() -> QApplication:
    """یک نمونهٔ QApplication برای کل فایل."""
    return QApplication.instance() or QApplication([])


# ----------------------------------------------------------------------
# ۱. پایداری وضعیت اتصال
# ----------------------------------------------------------------------
class _StubProvider:
    """کمینه‌ترین ارائه‌دهنده‌ای که موتور برای ساخته‌شدن لازم دارد."""

    name = "stub"
    supports_websocket = False

    def create_websocket(self) -> None:
        """بدون سوکت؛ این آزمون‌ها فقط مسیر REST را می‌سنجند."""
        return None


@pytest.fixture()
def market_engine() -> Any:
    """
    موتور بازار بدون شبکه.

    `websocket_enabled=False` چون اینجا فقط رفتار شمارندهٔ شکست REST
    سنجیده می‌شود و سوکت زنده آزمون را غیرقطعی می‌کند.
    """
    from market.engine import MarketDataEngine

    return MarketDataEngine(_StubProvider(), websocket_enabled=False)


class TestOfflineTolerance:
    """
    کاربر گفت «سیستم خیلی قطع می‌شود و آفلاین می‌زند».

    علت: یک درخواست ناموفق بی‌درنگ وضعیت را آفلاین می‌کرد.
    """

    def test_tolerance_is_more_than_one(self) -> None:
        """اگر تحمل یک باشد، همان باگ قبلی برمی‌گردد."""
        assert REST_FAILURE_TOLERANCE > 1

    def test_a_single_blip_keeps_us_online(self, market_engine: Any) -> None:
        """یک قطعی گذرا نباید کاربر را آفلاین نشان دهد."""
        market_engine._mark_rest_alive(True)
        market_engine._mark_rest_alive(False)

        assert market_engine.is_online is True

    def test_repeated_failures_eventually_report_offline(self, market_engine: Any) -> None:
        """قطعی واقعی باید گزارش شود؛ پنهان‌کردنش هم دروغ است."""
        market_engine._mark_rest_alive(True)
        for _ in range(REST_FAILURE_TOLERANCE):
            market_engine._mark_rest_alive(False)

        assert market_engine.is_online is False

    def test_one_success_heals_immediately(self, market_engine: Any) -> None:
        """
        بدبینی کند، خوش‌بینی سریع.

        وقتی داده دوباره می‌آید، کاربر نباید منتظر چند موفقیت بماند.
        """
        for _ in range(REST_FAILURE_TOLERANCE + 2):
            market_engine._mark_rest_alive(False)
        assert market_engine.is_online is False

        market_engine._mark_rest_alive(True)
        assert market_engine.is_online is True

    def test_counter_resets_so_blips_do_not_accumulate(self, market_engine: Any) -> None:
        """
        دو قطعی جدا در فاصلهٔ چند ساعت نباید با هم جمع شوند.

        بدون صفر شدن شمارنده، برنامه بعد از مدتی الکی آفلاین می‌شد.
        """
        market_engine._mark_rest_alive(False)
        market_engine._mark_rest_alive(True)
        market_engine._mark_rest_alive(False)

        assert market_engine.is_online is True


# ----------------------------------------------------------------------
# ۲. انتخاب نماد بر پایهٔ اطمینان
# ----------------------------------------------------------------------
@dataclass
class _FakeDirection:
    """شبیه‌ساز `SignalDirection` که مقدارش در `.value` است."""

    value: str


@dataclass
class _FakeSignal:
    """
    سیگنال ساختگی با **همان نام فیلدهای واقعی**.

    نکتهٔ مهم: `TradingSignal` فیلدی به نام `entry_price` یا `reasons`
    ندارد؛ بازهٔ ورود است و `reason` تک‌رشته‌ای.
    """

    symbol: str
    confidence: int
    direction: Any
    entry_min: float = 100.0
    entry_max: float = 102.0
    reason: str = "هم‌راستایی روند"
    timeframes: list[str] = field(default_factory=lambda: ["15m"])
    primary_timeframe: str = "15m"


class _FakeSettings:
    """تنظیمات درون‌حافظه‌ای."""

    def __init__(self, values: dict[str, Any]) -> None:
        """نگه‌داشتن مقادیر."""
        self._values = values

    def get_int(self, key: str, default: int = 0) -> int:
        """خواندن عدد صحیح."""
        return int(self._values.get(key, default))

    def get(self, key: str, default: Any = None) -> Any:
        """خواندن مقدار خام."""
        return self._values.get(key, default)


class _FakeApp:
    """برنامهٔ ساختگی با یک `scan_market` کنترل‌شده."""

    def __init__(self, signals: list[Any], values: dict[str, Any] | None = None) -> None:
        """آماده‌سازی."""
        self.settings = _FakeSettings(values or {})
        self._signals = signals
        self.calls: list[dict[str, Any]] = []

    async def scan_market(self, **kwargs: Any) -> Any:
        """ثبت پارامترها و برگرداندن سیگنال‌های از پیش تعیین‌شده."""
        self.calls.append(kwargs)

        class _Result:
            signals = self._signals

        return _Result()


def _long(symbol: str, confidence: int) -> _FakeSignal:
    """ساخت سیگنال خرید با اطمینان دلخواه."""
    return _FakeSignal(symbol=symbol, confidence=confidence, direction=_FakeDirection("LONG"))


class TestConfidenceSelection:
    """خواستهٔ صریح: «بالای ۷۵٪ را معامله کن»."""

    @pytest.mark.asyncio
    async def test_only_signals_above_the_threshold_are_returned(self) -> None:
        """۷۴ درصد نباید وارد معامله شود وقتی حد ۷۵ است."""
        app = _FakeApp(
            [_long("AAA/USDT", 80), _long("BBB/USDT", 74), _long("CCC/USDT", 90)],
            {"scalp.min_confidence": 75},
        )
        candidates = await ConfidenceCandidateSource(app).scan()

        assert [c.symbol for c in candidates] == ["CCC/USDT", "AAA/USDT"]

    @pytest.mark.asyncio
    async def test_results_are_sorted_by_confidence(self) -> None:
        """اگر ظرفیت پر شود، بهترین‌ها باید زودتر باز شوند."""
        app = _FakeApp(
            [_long("AAA/USDT", 78), _long("BBB/USDT", 95), _long("CCC/USDT", 85)],
            {"scalp.min_confidence": 75},
        )
        scores = [c.score for c in await ConfidenceCandidateSource(app).scan()]

        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_wait_signals_never_become_trades(self) -> None:
        """«انتظار» توصیهٔ معاملاتی نیست، حتی با اطمینان بالا."""
        wait = _FakeSignal("AAA/USDT", 99, _FakeDirection("WAIT"))
        app = _FakeApp([wait], {"scalp.min_confidence": 75})

        assert await ConfidenceCandidateSource(app).scan() == []

    @pytest.mark.asyncio
    async def test_entry_price_is_the_middle_of_the_range(self) -> None:
        """
        `TradingSignal` قیمت ورود تکی ندارد.

        خواندن `entry_price` همیشه صفر می‌داد و نماد بی‌صدا رد می‌شد.
        """
        signal = _long("AAA/USDT", 80)
        signal.entry_min, signal.entry_max = 100.0, 110.0
        app = _FakeApp([signal], {"scalp.min_confidence": 75})

        candidates = await ConfidenceCandidateSource(app).scan()
        assert candidates[0].price == pytest.approx(105.0)

    @pytest.mark.asyncio
    async def test_signal_without_a_price_is_skipped(self) -> None:
        """بدون قیمت معتبر نمی‌شود حجم معامله را حساب کرد."""
        signal = _long("AAA/USDT", 80)
        signal.entry_min = signal.entry_max = 0.0
        app = _FakeApp([signal], {"scalp.min_confidence": 75})

        assert await ConfidenceCandidateSource(app).scan() == []

    @pytest.mark.asyncio
    async def test_threshold_is_passed_down_to_the_scanner(self) -> None:
        """پالایش باید در خود پویش هم اعمال شود، نه فقط بعد از آن."""
        app = _FakeApp([], {"scalp.min_confidence": 82})
        await ConfidenceCandidateSource(app).scan()

        assert app.calls[0]["min_confidence"] == 82
        assert app.calls[0]["include_wait"] is False

    @pytest.mark.asyncio
    async def test_a_failed_scan_does_not_kill_the_engine(self) -> None:
        """یک دور ناموفق نباید موتور معاملهٔ خودکار را متوقف کند."""

        class _Boom(_FakeApp):
            async def scan_market(self, **kwargs: Any) -> Any:
                """شبیه‌سازی قطعی شبکه."""
                raise RuntimeError("network down")

        assert await ConfidenceCandidateSource(_Boom([])).scan() == []

    def test_confidence_floor_cannot_be_bypassed(self) -> None:
        """زیر این حد موتور خودش هم مطمئن نیست."""
        app = _FakeApp([], {"scalp.min_confidence": 5})

        assert ConfidenceCandidateSource(app).min_confidence == ABSOLUTE_MIN_CONFIDENCE

    def test_user_can_be_stricter(self) -> None:
        """سخت‌گیرتر شدن همیشه مجاز است."""
        app = _FakeApp([], {"scalp.min_confidence": 90})

        assert ConfidenceCandidateSource(app).min_confidence == 90

    def test_candidate_exposes_the_fields_autotrader_reads(self) -> None:
        """
        `AutoTrader` با `getattr` این چهار فیلد را می‌خواند.

        اگر نامشان با `ScalpCandidate` یکی نباشد، موتور بی‌صدا هیچ
        معامله‌ای باز نمی‌کند.
        """
        candidate = ConfidenceCandidate(
            symbol="BTC/USDT", price=100.0, direction="LONG", score=80.0
        )

        for attribute in ("symbol", "price", "direction", "score"):
            assert hasattr(candidate, attribute)
        assert candidate.confidence == 80.0


# ----------------------------------------------------------------------
# ۳. تنظیم دستی روی صفحهٔ معاملات
# ----------------------------------------------------------------------
class TestManualAutoTradeControls:
    """خواستهٔ کاربر: «هم اتوماتیک بشه تنظیم کرد هم دستی»."""

    @pytest.fixture()
    def page(self, qt_application: QApplication) -> TradesPage:  # noqa: ARG002
        """صفحهٔ معاملات نمایش‌داده‌شده."""
        widget = TradesPage(Translator("fa"))
        widget.resize(1200, 900)
        widget.show()
        QApplication.processEvents()
        return widget

    def test_manual_inputs_exist(self, page: TradesPage) -> None:
        """هر عددی که کاربر نام برد باید ورودی داشته باشد."""
        for name in (
            "auto_margin_input",
            "auto_target_input",
            "auto_loss_input",
            "auto_leverage_input",
            "auto_concurrent_input",
            "auto_confidence_input",
            "auto_source_combo",
        ):
            assert hasattr(page, name), name

    def test_inputs_start_locked(self, page: TradesPage) -> None:
        """
        پیش‌فرض خودکار است.

        قفل‌بودن جلوی تغییر تصادفی عددهای پول واقعی را می‌گیرد.
        """
        assert page.auto_margin_input.isEnabled() is False

    def test_checkbox_unlocks_the_inputs(self, page: TradesPage) -> None:
        """با زدن تیک «تنظیم دستی» باید باز شوند."""
        page.auto_manual_check.setChecked(True)
        QApplication.processEvents()

        assert page.auto_margin_input.isEnabled() is True

    def test_values_load_from_settings(self, page: TradesPage) -> None:
        """کاربر باید عددهای واقعی را ببیند، نه صفر."""
        page.load_auto_settings(
            {
                "scalp.margin_per_trade": 25.0,
                "scalp.target_profit": 3.0,
                "scalp.max_loss": 4.0,
                "scalp.leverage": 8,
                "scalp.max_concurrent": 2,
                "scalp.min_confidence": 75,
                "scalp.candidate_source": "confidence",
            }
        )

        assert page.auto_margin_input.value() == pytest.approx(25.0)
        assert page.auto_confidence_input.value() == 75
        assert page.auto_source_combo.currentData() == "confidence"

    def test_collect_returns_the_scalp_keys(self, page: TradesPage) -> None:
        """
        کلیدها باید همان‌هایی باشند که صفحهٔ تنظیمات می‌نویسد.

        وگرنه دو صفحه از هم جدا می‌افتند و کاربر گیج می‌شود.
        """
        collected = page.collect_auto_settings()

        assert "scalp.margin_per_trade" in collected
        assert "scalp.min_confidence" in collected
        assert "scalp.candidate_source" in collected

    def test_apply_button_emits_the_values(self, page: TradesPage) -> None:
        """بدون این سیگنال، دکمه هیچ کاری نمی‌کند."""
        page.auto_manual_check.setChecked(True)
        QApplication.processEvents()
        received: dict = {}
        page.auto_settings_changed.connect(received.update)

        page.auto_apply_button.click()
        QApplication.processEvents()

        assert received.get("scalp.margin_per_trade") is not None

    def test_confidence_input_cannot_go_below_the_floor(self, page: TradesPage) -> None:
        """رابط کاربری هم نباید اجازهٔ عدد بی‌معنا بدهد."""
        page.auto_confidence_input.setValue(1)

        assert page.auto_confidence_input.value() >= ABSOLUTE_MIN_CONFIDENCE

    def test_collapsed_box_does_not_steal_height(self, page: TradesPage) -> None:
        """
        پنل بسته نباید ارتفاع صفحه را بگیرد.

        اولین پیاده‌سازی فقط ورودی‌ها را غیرفعال می‌کرد؛ صفحه ۶۸۷ پیکسل
        شد و از قد نمایشگر لپ‌تاپ (۶۶۰) گذشت.

        صفحه در v2.0 پیمایش‌دار شد؛ قدِ کل صفحه دیگر تابع محتواست،
        پس ارتفاعِ بدنهٔ پیمایش سنجیده می‌شود — همان چیزی که کاربر
        باید برای دیدن پنل بپیماید.
        """
        def body_height(page: TradesPage) -> int:
            scroll = getattr(page, "_scroll", None)
            target = scroll.widget() if scroll is not None else page
            return target.minimumSizeHint().height()

        # v2.1.1: پنل تنظیمات ترمینال پیش‌فرض جمع‌شده است؛ برای سنجش
        # جعبهٔ دستی، اول پنل را باز کن — هدفِ اصلی تست همین است که
        # «جعبهٔ باز ارتفاع اضافه بگیرد و جعبهٔ بسته نگیرد».
        if getattr(page, "_config_collapsed", False):
            page._toggle_config_panel()
        page.auto_manual_check.setChecked(False)
        QApplication.processEvents()
        collapsed = body_height(page)

        page.auto_manual_check.setChecked(True)
        QApplication.processEvents()
        expanded = body_height(page)

        assert collapsed < expanded

    def test_leverage_is_capped_in_the_ui(self, page: TradesPage) -> None:
        """سقف اهرم همان سقف سخت موتور است."""
        page.auto_leverage_input.setValue(999)

        assert page.auto_leverage_input.value() <= HARD_MAX_LEVERAGE
