"""آزمون موتور ریسک — حساس‌ترین بخش از نظر ایمنی سرمایه."""

from __future__ import annotations

import pytest

from app.core.constants import SignalDirection
from app.core.models import RiskParameters, SupportResistanceLevel
from signals.risk_engine import RiskEngine


def test_long_stop_loss_is_below_entry(risk_parameters: RiskParameters) -> None:
    """در معامله خرید، حد ضرر باید زیر قیمت ورود باشد."""
    engine = RiskEngine(risk_parameters)
    stop, _ = engine.calculate_stop_loss(SignalDirection.LONG, entry=100.0, atr=2.0)
    assert stop < 100.0


def test_short_stop_loss_is_above_entry(risk_parameters: RiskParameters) -> None:
    """در معامله فروش، حد ضرر باید بالای قیمت ورود باشد."""
    engine = RiskEngine(risk_parameters)
    stop, _ = engine.calculate_stop_loss(SignalDirection.SHORT, entry=100.0, atr=2.0)
    assert stop > 100.0


def test_structural_stop_is_preferred_when_valid(risk_parameters: RiskParameters) -> None:
    """اگر حمایت معتبری وجود داشته باشد، حد ضرر باید آن‌سوی آن قرار گیرد."""
    engine = RiskEngine(risk_parameters)
    levels = [SupportResistanceLevel(price=95.0, kind="support", strength="major", source="swing", distance_percent=-5.0)]
    stop, method = engine.calculate_stop_loss(SignalDirection.LONG, entry=100.0, atr=1.0, levels=levels)
    assert stop < 95.0
    assert "structural" in method or "ATR" in method


def test_stop_distance_is_clamped_to_user_limit() -> None:
    """فاصله حد ضرر نباید از سقف تعیین‌شده کاربر بیشتر شود."""
    parameters = RiskParameters(max_stop_distance_percent=2.0, atr_stop_multiplier=10.0)
    engine = RiskEngine(parameters)
    stop, method = engine.calculate_stop_loss(SignalDirection.LONG, entry=100.0, atr=5.0)
    assert stop >= 98.0
    assert "clamped" in method


def test_take_profits_are_ordered_for_long(risk_parameters: RiskParameters) -> None:
    """اهداف خرید باید صعودی و بالاتر از ورود باشند."""
    engine = RiskEngine(risk_parameters)
    targets = engine.calculate_take_profits(SignalDirection.LONG, entry=100.0, stop_loss=98.0)
    assert targets == sorted(targets)
    assert all(t > 100.0 for t in targets)


def test_take_profits_are_ordered_for_short(risk_parameters: RiskParameters) -> None:
    """اهداف فروش باید نزولی و پایین‌تر از ورود باشند."""
    engine = RiskEngine(risk_parameters)
    targets = engine.calculate_take_profits(SignalDirection.SHORT, entry=100.0, stop_loss=102.0)
    assert targets == sorted(targets, reverse=True)
    assert all(t < 100.0 for t in targets)


def test_low_risk_reward_is_rejected(risk_parameters: RiskParameters) -> None:
    """نسبت ریسک به سود پایین‌تر از حد کاربر باید رد شود."""
    engine = RiskEngine(risk_parameters)
    assessment = engine.assess(SignalDirection.LONG, entry=100.0, stop_loss=98.0, take_profits=[100.5], atr=1.0)
    assert not assessment.approved
    assert "risk/reward" in assessment.rejection_reason.lower()


def test_stop_tighter_than_atr_is_rejected(risk_parameters: RiskParameters) -> None:
    """حد ضرری که از یک ATR تنگ‌تر است با نوسان عادی فعال می‌شود و باید رد شود."""
    engine = RiskEngine(risk_parameters)
    assessment = engine.assess(SignalDirection.LONG, entry=100.0, stop_loss=99.9, take_profits=[105.0], atr=2.0)
    assert not assessment.approved
    assert "atr" in assessment.rejection_reason.lower()


def test_wrong_side_stop_is_rejected(risk_parameters: RiskParameters) -> None:
    """حد ضرر در سمت اشتباه باید رد شود."""
    engine = RiskEngine(risk_parameters)
    assessment = engine.assess(SignalDirection.LONG, entry=100.0, stop_loss=102.0, take_profits=[110.0], atr=1.0)
    assert not assessment.approved


def test_valid_setup_is_approved(risk_parameters: RiskParameters) -> None:
    """ستاپ سالم باید تأیید شود و اندازه پوزیشن مثبت داشته باشد."""
    engine = RiskEngine(risk_parameters)
    assessment = engine.assess(SignalDirection.LONG, entry=100.0, stop_loss=98.0, take_profits=[104.0], atr=1.0)
    assert assessment.approved
    assert assessment.risk_reward == pytest.approx(2.0)
    assert assessment.position_size > 0


def test_leverage_never_exceeds_user_maximum() -> None:
    """اهرم پیشنهادی هرگز نباید از سقف کاربر بیشتر شود."""
    parameters = RiskParameters(max_leverage=3)
    engine = RiskEngine(parameters)
    assessment = engine.assess(SignalDirection.LONG, entry=100.0, stop_loss=99.5, take_profits=[103.0], atr=0.2)
    assert assessment.suggested_leverage <= 3


def test_position_size_respects_risk_percent() -> None:
    """اندازه پوزیشن باید دقیقاً معادل درصد ریسک تعیین‌شده باشد."""
    parameters = RiskParameters(account_balance=10_000.0, risk_percent=2.0, min_risk_reward=1.0)
    engine = RiskEngine(parameters)
    assessment = engine.assess(SignalDirection.LONG, entry=100.0, stop_loss=90.0, take_profits=[120.0], atr=5.0)
    # ریسک ۲۰۰ دلار تقسیم بر فاصله ۱۰ دلاری = ۲۰ واحد
    assert assessment.risk_amount == pytest.approx(200.0)
    assert assessment.position_size == pytest.approx(20.0)
