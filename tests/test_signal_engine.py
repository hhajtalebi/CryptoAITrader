"""آزمون موتور سیگنال — با تأکید بر استقلال از هوش مصنوعی."""

from __future__ import annotations

import pytest

from app.core.constants import AnalysisStatus, SignalDirection
from app.core.models import RiskParameters
from indicators import IndicatorEngine
from signals import RiskEngine, SignalEngine
from tests.conftest import FakeMarketEngine, make_candles


def _engine(data: dict, parameters: RiskParameters) -> SignalEngine:
    """ساخت موتور سیگنال با بازار ساختگی."""
    return SignalEngine(FakeMarketEngine(data), IndicatorEngine(), RiskEngine(parameters))


@pytest.mark.asyncio
async def test_strong_uptrend_produces_long(risk_parameters: RiskParameters) -> None:
    """روند صعودی قوی و هم‌سو باید سیگنال خرید بدهد."""
    data = {tf: make_candles(drift=0.006, seed=s, volume_spike_at_end=True)
            for tf, s in (("1d", 1), ("4h", 2), ("1h", 3))}
    signal = await _engine(data, risk_parameters).generate("TEST/USDT", ["1d", "4h", "1h"])
    assert signal.direction == SignalDirection.LONG
    assert signal.stop_loss < signal.entry_min
    assert all(t > signal.entry_max for t in signal.take_profits)


@pytest.mark.asyncio
async def test_strong_downtrend_produces_short(risk_parameters: RiskParameters) -> None:
    """روند نزولی قوی باید سیگنال فروش بدهد."""
    data = {tf: make_candles(drift=-0.006, seed=s, volume_spike_at_end=True)
            for tf, s in (("1d", 11), ("4h", 12), ("1h", 13))}
    signal = await _engine(data, risk_parameters).generate("TEST/USDT", ["1d", "4h", "1h"])
    assert signal.direction == SignalDirection.SHORT
    assert signal.stop_loss > signal.entry_max
    assert all(t < signal.entry_min for t in signal.take_profits)


@pytest.mark.asyncio
async def test_no_data_returns_wait_not_crash(risk_parameters: RiskParameters) -> None:
    """نبود داده باید WAIT بدهد، نه خطا و نه سیگنال ساختگی."""
    signal = await _engine({}, risk_parameters).generate("TEST/USDT", ["1h"])
    assert signal.direction == SignalDirection.WAIT
    assert signal.status == AnalysisStatus.INSUFFICIENT_DATA
    assert signal.stop_loss is None
    assert signal.take_profits == []


@pytest.mark.asyncio
async def test_impossible_risk_reward_forces_wait() -> None:
    """اگر موتور ریسک ستاپ را رد کند، نتیجه باید WAIT شود."""
    parameters = RiskParameters(min_risk_reward=99.0)
    data = {tf: make_candles(drift=0.006, seed=s) for tf, s in (("1d", 1), ("4h", 2), ("1h", 3))}
    signal = await _engine(data, parameters).generate("TEST/USDT", ["1d", "4h", "1h"])
    assert signal.direction == SignalDirection.WAIT
    assert signal.risk is not None and not signal.risk.approved


@pytest.mark.asyncio
async def test_confidence_is_within_bounds(risk_parameters: RiskParameters) -> None:
    """میزان اطمینان همیشه باید بین ۰ و ۱۰۰ باشد."""
    data = {tf: make_candles(drift=0.004, seed=s) for tf, s in (("4h", 5), ("1h", 6))}
    signal = await _engine(data, risk_parameters).generate("TEST/USDT", ["4h", "1h"])
    assert 0 <= signal.confidence <= 100


@pytest.mark.asyncio
async def test_leverage_respects_user_limit() -> None:
    """اهرم سیگنال نباید از سقف کاربر فراتر رود."""
    parameters = RiskParameters(max_leverage=2, min_risk_reward=1.0)
    data = {tf: make_candles(drift=0.006, seed=s) for tf, s in (("1d", 1), ("4h", 2), ("1h", 3))}
    signal = await _engine(data, parameters).generate("TEST/USDT", ["1d", "4h", "1h"])
    assert signal.leverage <= 2


@pytest.mark.asyncio
async def test_signal_works_without_any_ai(risk_parameters: RiskParameters) -> None:
    """
    مهم‌ترین آزمون این ماژول: موتور سیگنال بدون هیچ هوش مصنوعی کار می‌کند.
    """
    data = {tf: make_candles(drift=0.006, seed=s) for tf, s in (("1d", 1), ("4h", 2), ("1h", 3))}
    signal = await _engine(data, risk_parameters).generate("TEST/USDT", ["1d", "4h", "1h"])
    assert signal.ai_provider is None
    assert signal.analysis_text == ""
    assert signal.direction in (SignalDirection.LONG, SignalDirection.SHORT, SignalDirection.WAIT)


@pytest.mark.asyncio
async def test_ai_failure_does_not_break_signal(risk_parameters: RiskParameters) -> None:
    """شکست هوش مصنوعی نباید سیگنال پایه را خراب کند."""
    data = {tf: make_candles(drift=0.006, seed=s) for tf, s in (("1d", 1), ("4h", 2), ("1h", 3))}
    engine = _engine(data, risk_parameters)
    signal = await engine.generate("TEST/USDT", ["1d", "4h", "1h"])
    before = (signal.direction, signal.stop_loss, list(signal.take_profits), signal.confidence)

    class BrokenAnalyst:
        """عامل هوش مصنوعی که همیشه خطا می‌دهد."""

        async def analyze(self, request):  # noqa: ANN001, ANN202
            raise RuntimeError("AI service is down")

    enriched = await engine.enrich_with_ai(signal, BrokenAnalyst())
    after = (enriched.direction, enriched.stop_loss, list(enriched.take_profits), enriched.confidence)
    assert before == after


@pytest.mark.asyncio
async def test_partial_timeframe_failure_is_tolerated(risk_parameters: RiskParameters) -> None:
    """اگر یک تایم‌فریم داده نداشته باشد، تحلیل با بقیه ادامه می‌یابد."""
    data = {"4h": make_candles(drift=0.005, seed=7), "1h": make_candles(drift=0.005, seed=8)}
    signal = await _engine(data, risk_parameters).generate("TEST/USDT", ["1d", "4h", "1h"])
    assert "1d" not in signal.timeframes
    assert signal.status == AnalysisStatus.OK
