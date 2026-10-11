"""
ردیابی سرتاسریِ تولید سیگنال (الزام ۸) — نسخهٔ ۲.۷.۱.

هر اجرای `SignalEngine.generate` باید یک شناسهٔ ردیابی داشته باشد و در لاگ
این‌ها را ثبت کند: شروع اجرا و تایم‌فریم‌های درخواستی، وضعیت دریافت داده،
زمان هر مرحله، و نتیجهٔ نهایی **با دلیل تولید یا رد شدن**. بدون این، وقتی
کاربر می‌پرسد «چرا برای این نماد سیگنال نیامد؟» هیچ مدرکی در لاگ نیست.

این آزمون‌ها رویدادها را با جایگزینیِ تابع انتشار می‌گیرند، پس به فایل لاگ
یا پوشهٔ داده وابسته نیستند.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.constants import AnalysisStatus, SignalDirection
from app.core.models import RiskParameters
from indicators import IndicatorEngine
from signals import RiskEngine, SignalEngine
from signals import engine as engine_module
from tests.conftest import FakeMarketEngine, make_candles


class _Recorder:
    """گیرندهٔ رویدادهای ردیابی (جایگزینِ انتشار واقعی)."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, event: str, message: str, **fields: Any) -> bool:
        self.events.append({"event": event, "message": message, **fields})
        return True

    @property
    def names(self) -> list[str]:
        return [item["event"] for item in self.events]

    def first(self, name: str) -> dict[str, Any]:
        for item in self.events:
            if item["event"] == name:
                return item
        raise AssertionError(f"رویداد {name} منتشر نشد؛ رویدادهای موجود: {self.names}")


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    """جایگزینی انتشارِ ممیزی با گیرندهٔ درون‌حافظه‌ای."""

    sink = _Recorder()
    monkeypatch.setattr(engine_module, "audit_emit", sink)
    return sink


def _engine(data: dict, parameters: RiskParameters) -> SignalEngine:
    """ساخت موتور سیگنال با بازار ساختگی."""

    return SignalEngine(FakeMarketEngine(data), IndicatorEngine(), RiskEngine(parameters))


def _trending_data(drift: float = 0.006) -> dict:
    return {tf: make_candles(drift=drift, seed=s, volume_spike_at_end=True)
            for tf, s in (("1d", 1), ("4h", 2), ("1h", 3))}


@pytest.mark.asyncio
async def test_every_run_gets_a_unique_correlation_id(recorder: _Recorder, risk_parameters: RiskParameters) -> None:
    """هر اجرا شناسهٔ ردیابیِ یکتا دارد و همهٔ رویدادهایش همان را حمل می‌کنند."""

    engine = _engine(_trending_data(), risk_parameters)
    await engine.generate("TEST/USDT", ["1d", "4h", "1h"])
    await engine.generate("TEST/USDT", ["1d", "4h", "1h"])

    identifiers = {item["correlation_id"] for item in recorder.events}
    assert len(identifiers) == 2, f"دو اجرا شناسهٔ یکسان دارند: {identifiers}"
    assert all(len(str(value)) >= 8 for value in identifiers)
    assert all(item["correlation_id"] for item in recorder.events)


@pytest.mark.asyncio
async def test_generated_signal_logs_data_status_and_timing(
    recorder: _Recorder, risk_parameters: RiskParameters
) -> None:
    """لاگ باید وضعیت دریافت داده و زمان مراحل را داشته باشد."""

    signal = await _engine(_trending_data(), risk_parameters).generate(
        "TEST/USDT", ["1d", "4h", "1h"], primary_timeframe="1h"
    )
    assert signal.direction == SignalDirection.LONG

    start = recorder.first("signal_run_start")
    assert start["requested_timeframes"] == "1d,4h,1h"
    assert start["primary_timeframe"] == "1h"

    data = recorder.first("signal_data")
    assert data["ok_timeframes"] == "1d,1h,4h"
    assert float(data["data_seconds"]) >= 0.0

    generated = recorder.first("signal_generated")
    assert generated["direction"] == "LONG"
    assert generated["stop_loss"] is not None
    assert generated["take_profits"], "اهداف سود در لاگ نیستند"
    assert float(generated["total_seconds"]) >= 0.0
    assert generated["timeframes"], "تایم‌فریم‌های استفاده‌شده در لاگ نیستند"
    assert generated["indicators"], "اندیکاتورهای استفاده‌شده در لاگ نیستند"


@pytest.mark.asyncio
async def test_rejection_logs_the_real_reason(recorder: _Recorder) -> None:
    """رد شدنِ ستاپ باید با دلیل واقعی ثبت شود، نه فقط «سیگنالی نبود»."""

    parameters = RiskParameters(min_risk_reward=99.0)
    signal = await _engine(_trending_data(), parameters).generate("TEST/USDT", ["1d", "4h", "1h"])
    assert signal.direction == SignalDirection.WAIT

    rejected = recorder.first("signal_rejected")
    assert rejected["level"] == "WARNING", "رد شدن نباید در سطح DEBUG پنهان بماند"
    reason = str(rejected["rejection_reason"])
    assert "Risk/reward" in reason or "minimum" in reason, f"دلیل واقعی ثبت نشد: {reason}"
    assert rejected["stop_loss"] is not None


@pytest.mark.asyncio
async def test_insufficient_data_is_logged_as_a_warning_with_the_failing_timeframes(
    recorder: _Recorder, risk_parameters: RiskParameters
) -> None:
    """نبود داده باید با وضعیت INSUFFICIENT_DATA و نه به‌صورت بی‌صدا ثبت شود."""

    signal = await _engine({}, risk_parameters).generate("TEST/USDT", ["1h"])
    assert signal.status == AnalysisStatus.INSUFFICIENT_DATA

    result = recorder.first("signal_result")
    assert result["level"] == "WARNING"
    assert result["status"] == "INSUFFICIENT_DATA"
    assert "1h" in str(result["failed_timeframes"]), "تایم‌فریم شکست‌خورده ثبت نشد"


@pytest.mark.asyncio
async def test_wait_decision_records_the_score_against_the_threshold(
    recorder: _Recorder, risk_parameters: RiskParameters
) -> None:
    """وقتی عامل‌ها هم‌سو نیستند، امتیاز در برابر آستانه باید در لاگ باشد."""

    flat = {tf: make_candles(drift=0.0, seed=s) for tf, s in (("1d", 21), ("4h", 22), ("1h", 23))}
    signal = await _engine(flat, risk_parameters).generate("TEST/USDT", ["1d", "4h", "1h"])
    if signal.direction is not SignalDirection.WAIT:
        pytest.skip("این سری تصادفی اتفاقاً سیگنال داد؛ سناریوی انتظار رخ نداد")

    result = recorder.first("signal_result")
    assert result["direction"] == "WAIT"
    assert "total_score" in result and "threshold" in result, (
        "امتیاز و آستانه در لاگ نیستند؛ بدون آن‌ها دلیلِ انتظار قابل ردیابی نیست"
    )
    assert float(result["threshold"]) > 0


def test_trace_emission_never_breaks_signal_generation(
    monkeypatch: pytest.MonkeyPatch, risk_parameters: RiskParameters
) -> None:
    """اگر انتشار رویداد شکست بخورد، تولید سیگنال باید همچنان کار کند."""

    def boom(event: str, message: str, **_fields: Any) -> bool:
        raise RuntimeError("log backend is down")

    monkeypatch.setattr(engine_module, "audit_emit", boom)

    import asyncio

    async def run() -> Any:
        return await _engine(_trending_data(), risk_parameters).generate(
            "TEST/USDT", ["1d", "4h", "1h"]
        )

    signal = asyncio.run(run())
    assert signal.direction == SignalDirection.LONG
