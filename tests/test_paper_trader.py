"""
آزمون دفتر معاملهٔ تمرینی.

دکمهٔ «اقدام» باید کاری معنادار انجام دهد، ولی هرگز روی سیگنال بی‌اعتبار
موقعیت باز نکند.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from signals.paper_trader import PAPER_POSITIONS_KEY, PaperPosition, PaperTrader


class _FakeSettings:
    """تنظیمات ساختگی در حافظه."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value


LONG_SIGNAL = {
    "symbol": "BTC/USDT",
    "direction": "LONG",
    "confidence": 70,
    "entry_min": 78000,
    "entry_max": 78200,
    "stop_loss": 76500,
    "take_profits": [80000, 82000],
    "leverage": 5,
    "reason": "Higher lows",
}


@pytest.fixture()
def trader() -> PaperTrader:
    return PaperTrader(_FakeSettings())


def test_opens_position_from_long_signal(trader: PaperTrader) -> None:
    """سیگنال معتبر باید موقعیت باز کند."""
    position = trader.open_from_signal(LONG_SIGNAL, balance=1000, risk_percent=1)

    assert position is not None
    assert position.direction == "LONG"
    assert position.symbol == "BTC/USDT"
    # ورود، وسط بازه اعلام‌شده است
    assert position.entry == pytest.approx(78100)
    assert position.stop_loss == 76500
    assert position.take_profits == [80000, 82000]


def test_position_size_follows_risk_rule(trader: PaperTrader) -> None:
    """
    حجم موقعیت باید از قاعده ریسک پیروی کند.

    مبلغ در خطر تقسیم بر فاصله ورود تا حد ضرر.
    """
    position = trader.open_from_signal(LONG_SIGNAL, balance=1000, risk_percent=2)

    expected = (1000 * 2 / 100) / abs(78100 - 76500)
    assert position is not None
    assert position.size == pytest.approx(expected)


def test_wait_signal_opens_nothing(trader: PaperTrader) -> None:
    """روی سیگنال انتظار نباید معامله‌ای ثبت شود."""
    signal = {**LONG_SIGNAL, "direction": "WAIT"}

    assert trader.open_from_signal(signal, balance=1000) is None
    assert trader.open_positions() == []


def test_signal_without_entry_is_refused(trader: PaperTrader) -> None:
    """بدون قیمت ورود، معامله معنا ندارد."""
    signal = {"symbol": "BTC/USDT", "direction": "LONG", "confidence": 50}

    assert trader.open_from_signal(signal, balance=1000) is None


def test_positions_persist_and_reload(trader: PaperTrader) -> None:
    """موقعیت‌ها باید ذخیره و دوباره خوانده شوند."""
    trader.open_from_signal(LONG_SIGNAL, balance=1000, risk_percent=1)
    trader.open_from_signal({**LONG_SIGNAL, "symbol": "ETH/USDT"}, balance=1000)

    positions = trader.open_positions()
    assert len(positions) == 2
    assert {p.symbol for p in positions} == {"BTC/USDT", "ETH/USDT"}


def test_close_position_marks_it_closed(trader: PaperTrader) -> None:
    """بستن موقعیت باید وضعیتش را عوض کند، نه اینکه حذفش کند."""
    trader.open_from_signal(LONG_SIGNAL, balance=1000)

    assert trader.close_position(0, note="hit target")
    assert trader.open_positions() == []
    assert len(trader.all_positions()) == 1
    assert trader.all_positions()[0].status == "CLOSED"


def test_live_trading_is_off_by_default(trader: PaperTrader) -> None:
    """
    بدون اجراکنندهٔ سفارش، معاملهٔ واقعی نباید ممکن باشد.

    این محافظ عمدی است: دکمهٔ اقدام هرگز نباید ناخواسته پول واقعی
    جابه‌جا کند.
    """
    assert trader.live_trading_enabled is False


def test_corrupt_storage_does_not_crash() -> None:
    """داده خراب در تنظیمات نباید برنامه را از کار بیندازد."""
    settings = _FakeSettings()
    settings.set(PAPER_POSITIONS_KEY, "not json at all")
    trader = PaperTrader(settings)

    assert trader.all_positions() == []
    assert trader.open_from_signal(LONG_SIGNAL, balance=100) is not None


def test_short_signal_uses_correct_direction(trader: PaperTrader) -> None:
    """سیگنال فروش هم باید پشتیبانی شود."""
    signal = {
        "symbol": "ETH/USDT",
        "direction": "SHORT",
        "entry_min": 3100,
        "entry_max": 3100,
        "stop_loss": 3200,
        "take_profits": [3000],
    }
    position = trader.open_from_signal(signal, balance=500, risk_percent=1)

    assert position is not None
    assert position.direction == "SHORT"
    assert position.entry == pytest.approx(3100)


def test_position_round_trips_through_dict() -> None:
    """تبدیل به دیکشنری و برگشت نباید داده را خراب کند."""
    original = PaperPosition(
        symbol="BTC/USDT", direction="LONG", entry=78000,
        stop_loss=76000, take_profits=[80000], leverage=3, size=0.5, confidence=65,
    )
    restored = PaperPosition.from_dict(json.loads(json.dumps(original.to_dict())))

    assert restored.symbol == original.symbol
    assert restored.entry == original.entry
    assert restored.take_profits == original.take_profits
    assert restored.leverage == original.leverage
