"""
تاب‌آوریِ حالت‌های خط فرمان — نسخهٔ ۲.۷.۱.

چرا این فایل وجود دارد؟
    `python main.py --check` ابزاری است که قرار است **علتِ خرابی را پیدا کند**.
    پیش از این، خودش زیرِ همان مشکلی که باید تشخیص می‌داد می‌شکست: اگر صرافی در
    دسترس نبود (اینترنت قطع، VPN خاموش، مسدودی جغرافیایی — دقیقاً همان چیزی که
    کاربر را به اجرای این دستور وا‌می‌دارد)، با یک ردپای استثنای مدیریت‌نشده
    از کار می‌افتاد و چون `application.stop()` در انتهای مسیر بود، موتور بازار
    و اتصال‌های شبکه باز می‌ماندند.

    ابزار تشخیص باید از خودِ مشکل تاب‌آورتر باشد. این آزمون‌ها همین را قفل
    می‌کنند: شکستِ هر بخش جداگانه گزارش شود، برنامه هرگز با ردپا نشکند،
    و خاموشیِ تمیز **همیشه** انجام شود.

بدل‌ها اینجا عمداً سبک‌اند (ساختِ Application واقعی در هر آزمون، مجموعه را
دقایق کند می‌کرد و به شبکه وابسته می‌شد).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import main as main_module


class _FakeMarket:
    """بدلِ موتور بازار که خراب‌بودنِ صرافی را شبیه‌سازی می‌کند."""

    def __init__(self, *, fail_symbols: bool = True, fail_price: bool = True) -> None:
        self.exchange_name = "lbank"
        self._fail_symbols = fail_symbols
        self._fail_price = fail_price

    async def get_symbols(self) -> list[str]:
        if self._fail_symbols:
            raise ConnectionError("all hosts unreachable")
        return ["BTC/USDT", "ETH/USDT"]

    async def get_current_price(self, symbol: str) -> float:
        if self._fail_price:
            raise ConnectionError("all hosts unreachable")
        return 60000.0


class _FakeApplication:
    """بدلِ Application با امکانِ وادارکردن هر بخش به شکست."""

    def __init__(
        self,
        *,
        fail_local: bool = False,
        market: Any = None,
        fail_signal: bool = False,
    ) -> None:
        self.paths = SimpleNamespace(
            data_dir="/tmp/data", database_file=SimpleNamespace(name="crypto_ai_trader.db")
        )
        self._fail_local = fail_local
        self._market = market if market is not None else _FakeMarket()
        self._fail_signal = fail_signal
        self.started = False
        self.stopped = False

    @property
    def settings_repository(self) -> Any:
        if self._fail_local:
            raise RuntimeError("database locked")
        return SimpleNamespace(get_all=lambda: {f"key{i}": i for i in range(184)})

    @property
    def indicators(self) -> Any:
        return SimpleNamespace(available_indicators=lambda: [f"ind{i}" for i in range(24)])

    def ai_enabled(self) -> bool:
        return True

    @property
    def market(self) -> Any:
        return self._market

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def generate_signal(self, symbol: str) -> Any:
        if self._fail_signal:
            raise RuntimeError("no market data")
        return SimpleNamespace(
            direction=SimpleNamespace(value="WAIT"), confidence=0,
            trend=SimpleNamespace(value="NEUTRAL"),
            market_structure=SimpleNamespace(value="UNDEFINED"),
            entry_min=0.0, entry_max=0.0, stop_loss=None, take_profits=[],
            risk_reward=None, leverage=1, reason="no data",
        )


def _install(monkeypatch: pytest.MonkeyPatch, app: _FakeApplication) -> None:
    """نصبِ یک بدلِ مشخص به‌جای Application."""

    monkeypatch.setattr(main_module, "Application", lambda *a, **k: app)


@pytest.mark.asyncio
async def test_check_reports_unreachable_exchange_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """صرافیِ در‌دسترس‌نبودن باید هشدار باشد، نه ردپای استثنا."""

    app = _FakeApplication(market=_FakeMarket(fail_symbols=True, fail_price=True))
    _install(monkeypatch, app)

    code = await main_module.run_check()

    out = capsys.readouterr().out
    assert code == 0, "نبودِ دسترسی به صرافی نباید شکستِ سلامت باشد"
    assert "unreachable" in out, f"وضعیت صرافی گزارش نشد: {out}"
    assert "warning" in out.lower(), f"هشدار اعلام نشد: {out}"
    assert "Traceback" not in out


@pytest.mark.asyncio
async def test_check_stops_the_application_even_when_every_step_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """خاموشیِ تمیز باید همیشه انجام شود — حتی اگر همه‌چیز شکست بخورد."""

    app = _FakeApplication(market=_FakeMarket(fail_symbols=True, fail_price=True))
    _install(monkeypatch, app)

    await main_module.run_check()

    assert app.started, "برنامه اصلاً شروع نشد"
    assert app.stopped, "خاموشیِ تمیز انجام نشد (نشتِ اتصال‌های شبکه)"


@pytest.mark.asyncio
async def test_check_reports_local_failure_as_a_real_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """شکستِ بخشِ محلی (مثلاً پایگاه داده) باید کد خروج ۱ بدهد."""

    app = _FakeApplication(fail_local=True, market=_FakeMarket(fail_symbols=False, fail_price=False))
    _install(monkeypatch, app)

    code = await main_module.run_check()

    out = capsys.readouterr().out
    assert code == 1, "شکستِ واقعی باید کد خروجِ غیرصفر بدهد"
    assert "FAILED" in out
    assert app.stopped, "حتی در شکست هم باید خاموشیِ تمیز انجام شود"


@pytest.mark.asyncio
async def test_check_passes_cleanly_when_everything_works(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """در وضعیت سالم، پیامِ موفقیتِ روشن باشد و کد خروج صفر."""

    app = _FakeApplication(market=_FakeMarket(fail_symbols=False, fail_price=False))
    _install(monkeypatch, app)

    code = await main_module.run_check()

    out = capsys.readouterr().out
    assert code == 0
    assert "Health check passed." in out
    assert "warning" not in out.lower()
    assert "2 symbols" in out and "60000.0" in out


@pytest.mark.asyncio
async def test_signal_failure_is_a_message_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """شکستِ تولید سیگنال باید پیامِ خوانا بدهد، نه ردپای استثنا."""

    app = _FakeApplication(fail_signal=True)
    _install(monkeypatch, app)

    code = await main_module.run_signal("BTC/USDT")

    out = capsys.readouterr().out
    assert code == 1
    assert "could not be generated" in out
    assert "No signal is fabricated" in out, "تعهدِ «سیگنال ساختگی نمی‌سازیم» باید دیده شود"
    assert "Traceback" not in out
    assert app.stopped, "خاموشیِ تمیز انجام نشد"
