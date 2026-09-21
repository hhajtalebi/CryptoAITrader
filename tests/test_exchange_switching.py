"""
آزمون تعویض زندهٔ صرافی فعال و ارزش‌گذاری دارایی تومانی.

باگی که این آزمون‌ها از آن محافظت می‌کنند: انتخاب صرافی در تنظیمات فقط
مقدار را ذخیره می‌کرد و موتور بازار تا اجرای بعدی برنامه روی صرافی قبلی
می‌ماند؛ یعنی کاربر بیت‌پین را انتخاب می‌کرد ولی داده از LBank می‌آمد.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

pytest.importorskip("PySide6")

from app.application import Application  # noqa: E402
from app.core.paths import AppPaths  # noqa: E402
from localization import Translator  # noqa: E402
from market.providers.base import ExchangeProvider, ProviderCapabilities  # noqa: E402
from market.providers.registry import exchange_registry  # noqa: E402
from ui.controllers.main_controller import MainController  # noqa: E402
from ui.themes.theme_manager import ThemeManager  # noqa: E402
from ui.windows.main_window import MainWindow  # noqa: E402


class _StubProvider(ExchangeProvider):
    """
    ارائه‌دهندهٔ ساختگی برای آزمون تعویض، بدون تماس شبکه.

    نامش از بیرون داده می‌شود تا بتوان تعویض میان دو «صرافی» را دید.
    """

    def __init__(self, name: str, **_kwargs: Any) -> None:
        self.name = name
        self.display_name = name
        self.closed = False

    @property
    def capabilities(self) -> ProviderCapabilities:
        """توانمندی‌های حداقلی."""
        return ProviderCapabilities(name=self.name, native_timeframes={"1h"})

    async def connect(self) -> None:
        """اتصال ساختگی."""

    async def close(self) -> None:
        """ثبت اینکه بسته شد."""
        self.closed = True

    async def ping(self) -> bool:
        """همیشه آنلاین."""
        return True

    async def get_symbols(self) -> list:
        """بدون نماد."""
        return []

    async def get_ticker(self, symbol: str):
        """استفاده نمی‌شود."""
        raise NotImplementedError

    async def get_all_tickers(self) -> list:
        """بدون تیکر."""
        return []

    async def get_current_price(self, symbol: str) -> float:
        """قیمت ثابت."""
        return 1.0

    async def get_ohlcv(self, symbol, timeframe, limit=300, end_time=None) -> list:
        """بدون کندل."""
        return []

    async def get_orderbook(self, symbol: str, depth: int = 20):
        """استفاده نمی‌شود."""
        raise NotImplementedError

    def to_exchange_symbol(self, symbol: str) -> str:
        """بدون تغییر."""
        return symbol

    def from_exchange_symbol(self, exchange_symbol: str) -> str:
        """بدون تغییر."""
        return exchange_symbol


@pytest.fixture
def app_with_stubs(tmp_path, monkeypatch):
    """برنامه‌ای که صرافی‌هایش ساختگی‌اند تا شبکه لازم نباشد."""
    # ترتیب مهم است: `Application.__init__` خودش
    # `register_builtin_providers()` را صدا می‌زند، پس بدل‌ها باید *پس از*
    # ساخت برنامه و *پیش از* `start()` ثبت شوند، وگرنه بازنویسی می‌شوند و
    # آزمون به شبکهٔ واقعی وصل می‌شود.
    application = Application(AppPaths(tmp_path).ensure())
    for key in ("lbank", "toobit", "bitpin"):
        exchange_registry.register(
            key, lambda _key=key, **kwargs: _StubProvider(_key, **kwargs)
        )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.start())
    try:
        yield application, loop
    finally:
        loop.run_until_complete(application.stop())
        loop.close()
        asyncio.set_event_loop(None)
        # ثبت‌های واقعی برگردانده می‌شوند تا آزمون‌های دیگر آسیب نبینند
        from market.providers.registry import register_builtin_providers

        register_builtin_providers()


def test_switch_exchange_replaces_the_market_engine(app_with_stubs) -> None:
    """
    تعویض صرافی باید موتور بازار را واقعاً عوض کند.

    این هستهٔ باگ بود: تنظیمات عوض می‌شد ولی موتور نه.
    """
    application, loop = app_with_stubs
    assert application.market.exchange_name == "lbank"

    active = loop.run_until_complete(application.switch_exchange("toobit"))
    assert active == "toobit"
    assert application.market.exchange_name == "toobit"
    assert application.settings.active_exchange == "toobit"

    loop.run_until_complete(application.switch_exchange("bitpin"))
    assert application.market.exchange_name == "bitpin"


def test_switch_rebuilds_the_signal_engine(app_with_stubs) -> None:
    """
    موتور سیگنال باید بازساخته شود.

    اگر نشود، سیگنال‌ها از صرافی قبلی تغذیه می‌شوند و کاربر بدون آنکه
    بفهمد روی داده اشتباه تصمیم می‌گیرد.
    """
    application, loop = app_with_stubs
    before = application.signals
    loop.run_until_complete(application.switch_exchange("bitpin"))
    assert application.signals is not before


def test_previous_provider_is_closed(app_with_stubs) -> None:
    """صرافی قبلی باید بسته شود تا اتصال نشت نکند."""
    application, loop = app_with_stubs
    old_provider = application.market._provider
    loop.run_until_complete(application.switch_exchange("toobit"))
    assert old_provider.closed is True


def test_switching_to_the_same_exchange_is_a_no_op(app_with_stubs) -> None:
    """تعویض به همان صرافی نباید موتور را بی‌دلیل دوباره بسازد."""
    application, loop = app_with_stubs
    engine = application.market
    loop.run_until_complete(application.switch_exchange("lbank"))
    assert application.market is engine


def test_unknown_exchange_keeps_the_current_engine(app_with_stubs) -> None:
    """
    صرافی ناشناخته نباید برنامه را بی‌موتور کند.

    بهتر است خطا داده شود ولی کاربر همچنان داده ببیند.
    """
    application, loop = app_with_stubs
    engine = application.market
    with pytest.raises(Exception):
        loop.run_until_complete(application.switch_exchange("does-not-exist"))
    assert application.market is engine
    assert application.market.exchange_name == "lbank"


class TestTomanValuation:
    """ارزش‌گذاری دارایی تومانی در کیف پول."""

    @pytest.fixture
    def controller(self, tmp_path, qt_application):
        """
        کنترلر آمادهٔ آزمون — بدون راه‌اندازی موتورها.

        این آزمون‌ها فقط `_wallet_price_lookup` و `_toman_rate` را می‌سنجند
        که محاسبهٔ محض‌اند و به موتور بازار یا شبکه نیازی ندارند. پیش‌تر
        اینجا `application.start()` و `ctrl.start()` صدا زده می‌شد؛ نتیجه
        دو موتور زنده در دو حلقهٔ متفاوت بود و تسک «lbank-ws» معلق می‌ماند
        («Task was destroyed but it is pending!»). حالا فقط کنترلر ساخته
        می‌شود: هم نشتی از بین می‌رود، هم اجرا از ۱۲ ثانیه به کمتر از یک
        ثانیه می‌رسد.
        """
        application = Application(AppPaths(tmp_path).ensure())
        translator = Translator("fa")
        theme_manager = ThemeManager()
        window = MainWindow(translator, theme_manager)
        ctrl = MainController(
            application, window, translator, theme_manager, qt_application
        )
        try:
            yield ctrl
        finally:
            window.close()
            window.deleteLater()
            qt_application.processEvents()

    def test_irt_is_valued_from_the_toman_rate(self, controller) -> None:
        """
        موجودی تومانی باید ارزش دلاری بگیرد.

        کاربران صرافی ایرانی موجودی IRT دارند؛ بدون این، ستون «ارزش»
        همیشه خط تیره می‌ماند و جمع کل کیف پول غلط است.
        """
        controller._toman_rate = 237700.0
        lookup = controller._wallet_price_lookup()

        price = asyncio.run(lookup("IRT"))
        assert price == pytest.approx(1.0 / 237700.0)
        # باید در نگاشت قیمت‌ها هم ثبت شود تا جدول آن را نشان دهد
        assert controller._asset_prices["IRT"] == pytest.approx(price)

    def test_rial_is_ten_times_cheaper_than_toman(self, controller) -> None:
        """ریال یک‌دهم تومان است و نباید با آن اشتباه گرفته شود."""
        controller._toman_rate = 237700.0
        lookup = controller._wallet_price_lookup()
        toman = asyncio.run(lookup("IRT"))
        rial = asyncio.run(lookup("IRR"))
        assert rial == pytest.approx(toman / 10.0)

    def test_without_a_rate_it_returns_zero_instead_of_crashing(self, controller) -> None:
        """نبود نرخ نباید استثنا بدهد؛ فقط ارزش صفر."""
        controller._toman_rate = None
        lookup = controller._wallet_price_lookup()
        assert asyncio.run(lookup("IRT")) == 0.0

    def test_usdt_is_always_one(self, controller) -> None:
        """تتر پایهٔ محاسبه است."""
        lookup = controller._wallet_price_lookup()
        assert asyncio.run(lookup("USDT")) == 1.0
