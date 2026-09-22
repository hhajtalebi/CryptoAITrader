"""آزمون‌های نسخهٔ ۱.۹.۲۲ بدون وابستگی به PySide6.

سود خالص بعد از کارمزد، رد شدن سفارش واقعی بدون اجراکنندهٔ تأییدشده،
و پروفایل سرعت که پیش‌فرضش عددهای ذخیره‌شده را بازنویسی نمی‌کند.
"""

from __future__ import annotations

import asyncio

import pytest

from ai.speed_profile import limits_for, resolve_profile
from trading.auto_trader import (
    HARD_MAX_LEVERAGE,
    AutoTradeConfig,
    LiveOrderGateway,
    LiveTradingNotEnabledError,
)
from trading.execution import build_gateway
from trading.micro_plan import plan_levels


class _Settings(dict):
    """کمینهٔ شیء تنظیمات برای پروفایل سرعت."""

    def get(self, key, default=None):  # noqa: ANN001
        return super().get(key, default)


class _Executor:
    """اجراکنندهٔ ساختگی که نباید با حجم صفر صدا زده شود."""

    def __init__(self) -> None:
        self.calls = 0

    async def open_position(self, **_kwargs):  # noqa: ANN003, ANN201
        self.calls += 1
        return {"ok": True}

    async def close_position(self, **_kwargs):  # noqa: ANN003, ANN201
        self.calls += 1
        return {"ok": True}


class TestMicroEconomics:
    """۱۰ دلار در ۲۰۰ برابر، بعد از کارمزد ۰٫۰۶٪ هر طرف."""

    def test_ten_dollars_at_two_hundred_needs_five_forty_gross_for_three_net(self) -> None:
        plan = plan_levels(10, 200, 3, 3, 0.0006)

        assert plan.notional == pytest.approx(2000)
        assert plan.round_trip_fee == pytest.approx(2.40)
        assert plan.gross_target == pytest.approx(5.40)
        assert plan.entry_fee == pytest.approx(1.20)
        assert plan.stop_distance == pytest.approx(0.60)

    def test_existing_small_targets_still_clear_the_old_test_prices(self) -> None:
        """هدف ۲ و حد ۳ روی حجم ۱۰۰ دلاری باید هنوز با ۱۰۲٫۵ و ۹۶ بسته شود."""
        plan = plan_levels(10, 10, 2, 3, 0.0006)
        entry = 100.0
        quantity = plan.notional / entry
        target = entry + plan.gross_target / quantity
        stop = entry - plan.stop_distance / quantity

        assert target < 102.5
        assert stop > 96.0

    def test_poll_can_be_faster_than_one_second_but_not_reckless(self) -> None:
        assert AutoTradeConfig(poll_seconds=0.4).validated().poll_seconds == pytest.approx(0.4)
        assert AutoTradeConfig(poll_seconds=0.1).validated().poll_seconds == pytest.approx(0.25)

    def test_leverage_cap_is_the_requested_two_hundred(self) -> None:
        assert HARD_MAX_LEVERAGE == 200
        assert AutoTradeConfig(leverage=200).validated().leverage == 200


class TestLiveGateway:
    """زیرساخت واقعی هست؛ ارسال بدون اجراکنندهٔ تأییدشده ممنوع است."""

    def test_missing_executor_fails_loudly(self) -> None:
        gateway = build_gateway("lbank")

        with pytest.raises(LiveTradingNotEnabledError):
            asyncio.run(gateway.open_position(symbol="BTC/USDT", quantity=1))
        with pytest.raises(LiveTradingNotEnabledError):
            asyncio.run(gateway.close_position(symbol="BTC/USDT", quantity=1))

    def test_old_constructor_still_refuses(self) -> None:
        gateway = LiveOrderGateway("toobit")

        with pytest.raises(LiveTradingNotEnabledError):
            asyncio.run(gateway.open_position(symbol="BTC/USDT"))

    def test_zero_quantity_never_reaches_the_executor(self) -> None:
        executor = _Executor()
        gateway = build_gateway("lbank", executor)

        with pytest.raises(LiveTradingNotEnabledError):
            asyncio.run(gateway.open_position(symbol="BTC/USDT", quantity=0))

        assert executor.calls == 0

    def test_positive_quantity_can_use_an_injected_executor(self) -> None:
        executor = _Executor()
        gateway = LiveOrderGateway("lbank", executor)

        result = asyncio.run(gateway.open_position(symbol="BTC/USDT", quantity=0.01))

        assert result["ok"] is True
        assert executor.calls == 1


class TestSpeedProfile:
    """سریع واقعاً کوتاه است؛ متعادل تنظیم ذخیره‌شده را دور نمی‌ریزد."""

    def test_unknown_name_is_balanced_not_fast(self) -> None:
        assert resolve_profile("nope").key == "balanced"
        assert resolve_profile(None).agent_steps == 8

    def test_fast_uses_one_step(self) -> None:
        limits = limits_for(_Settings({"ai.speed_profile": "fast", "ai.max_agent_steps": 8}))

        assert limits.agent_steps == 1
        assert limits.chat_tools == 1
        assert limits.signal_timeout == 30

    def test_balanced_keeps_saved_numbers(self) -> None:
        limits = limits_for(
            _Settings(
                {
                    "ai.speed_profile": "balanced",
                    "ai.max_agent_steps": 3,
                    "ai.agent_timeout": 90,
                    "ai.chat_max_tools": 2,
                    "ai.chat_timeout": 60,
                    "signals.ai_timeout": 50,
                }
            )
        )

        assert limits.agent_steps == 3
        assert limits.agent_timeout == 90
        assert limits.chat_tools == 2
        assert limits.signal_timeout == 50
