"""
آزمون‌های حالت «کاملاً هوش مصنوعی» و سرعت سیگنال‌گیری دستی (۱٫۹٫۱۱).

اشکالی که کاربر گزارش کرد:
    «اگر تحلیل با هوش مصنوعی فعال باشد، اصلاً سیگنال نمی‌دهد و
    می‌زند منتظر.»

علت دقیق: `_apply_ai_decision` صفتی به نام `decision.direction`
می‌خواند که روی `AnalysisResult` **وجود ندارد**. چون با
`getattr(..., None)` خوانده می‌شد، خطایی رخ نمی‌داد؛ شرط هرگز برقرار
نمی‌شد و کل پاسخ هوش مصنوعی بی‌صدا دور ریخته می‌شد. کاربر همیشه همان
WAIT موتور ریاضی را می‌دید.

درس: `getattr` با مقدار پیش‌فرض، قرارداد شکسته را پنهان می‌کند.
"""

from __future__ import annotations

import asyncio

import pytest

from ai.agent.analyst import AnalysisResult, AnalysisStatus
from app.application import Application
from app.core.constants import MarketStructureType, SignalDirection, TrendDirection
from app.core.models import TradingSignal


def _decision(**overrides) -> AnalysisResult:
    """پاسخ معتبر تحلیل‌گر، همان‌طور که پس از اعتبارسنجی درمی‌آید."""
    result = AnalysisResult(symbol="BTC/USDT", status=AnalysisStatus.OK)
    result.provider = "ollama"
    result.model = "llama3.1:8b"
    result.structured = {
        "signal": "LONG",
        "entry_zone": [76000, 76200],
        "stop_loss": 74800,
        "take_profits": [78000, 79500],
        "confidence": 72,
        "leverage": 3,
        "reason": "شکست مقاومت با حجم بالا",
        "invalidation": "بستن زیر ۷۴۸۰۰",
        "trend": "BULLISH",
        "market_structure": "BREAKOUT",
        **overrides,
    }
    return result


def _engine_wait() -> TradingSignal:
    """سیگنال موتور ریاضی وقتی عوامل هم‌راستا نیستند."""
    return TradingSignal(
        symbol="BTC/USDT",
        exchange="lbank",
        direction=SignalDirection.WAIT,
        confidence=20,
    )


def _app(decision: AnalysisResult | None, timeout: int = 45) -> Application:
    """برنامه‌ای که فقط برای آزمودن نگاشت تصمیم ساخته می‌شود."""
    app = Application.__new__(Application)

    class Analyst:
        async def generate_signal(self, request):  # noqa: ANN001, ANN202
            return decision

    class Settings:
        def get_int(self, key, default=0):  # noqa: ANN001, ANN202
            return timeout

    app.ai_analyst = lambda: Analyst()
    app.settings = Settings()
    return app


class TestTheAiDecisionActuallyReachesTheUser:
    """قلب اشکال: پاسخ مدل نباید بی‌صدا دور ریخته شود."""

    def test_a_long_from_the_ai_overrides_the_engine_wait(self) -> None:
        """
        مهم‌ترین آزمون این نسخه.

        این دقیقاً همان چیزی است که کاربر می‌دید: مدل LONG می‌گفت و
        روی صفحه «منتظر» می‌نشست.
        """
        app = _app(_decision())

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.direction is SignalDirection.LONG

    def test_every_price_level_is_carried_over(self) -> None:
        """جهت بدون قیمت‌ها بی‌فایده است؛ کاربر باید نقطهٔ ورود بداند."""
        app = _app(_decision())

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.entry_min == 76000
        assert result.entry_max == 76200
        assert result.stop_loss == 74800
        assert result.take_profits == [78000, 79500]

    def test_confidence_and_leverage_come_from_the_ai(self) -> None:
        """ضریب اطمینان موتور (۲۰) نباید باقی بماند."""
        app = _app(_decision())

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.confidence == 72
        assert result.leverage == 3

    def test_the_model_is_recorded_for_traceability(self) -> None:
        """کاربر باید بداند کدام مدل این تصمیم را گرفته است."""
        app = _app(_decision())

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.ai_provider == "ollama"
        assert result.ai_model == "llama3.1:8b"

    def test_trend_and_structure_are_mapped(self) -> None:
        """مقادیر معتبر باید به enum تبدیل شوند."""
        app = _app(_decision())

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.trend is TrendDirection.BULLISH
        assert result.market_structure is MarketStructureType.BREAKOUT

    def test_a_short_is_honoured_too(self) -> None:
        """فروش هم باید کار کند، نه فقط خرید."""
        app = _app(_decision(signal="SHORT"))

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.direction is SignalDirection.SHORT


class TestTheEngineResultSurvivesBadAiOutput:
    """
    وقتی هوش مصنوعی پاسخ قابل استفاده ندهد، کاربر نباید دست خالی بماند.

    این تضمین از قبل وجود داشت و نباید با رفع اشکال از بین برود.
    """

    def test_a_missing_direction_keeps_the_engine_signal(self) -> None:
        """خروجی بدون `signal` نباید سیگنال موتور را خراب کند."""
        decision = _decision()
        decision.structured.pop("signal")
        app = _app(decision)

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.direction is SignalDirection.WAIT

    def test_an_invalid_direction_is_refused(self) -> None:
        """جهت ناشناخته نباید به سیگنال راه پیدا کند."""
        app = _app(_decision(signal="MAYBE_LONG"))

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.direction is SignalDirection.WAIT

    def test_a_none_decision_is_safe(self) -> None:
        """شکست کامل تحلیل‌گر نباید استثنا بدهد."""
        app = _app(None)

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.direction is SignalDirection.WAIT

    def test_a_wait_from_the_ai_is_respected(self) -> None:
        """
        «منتظر» از سوی هوش مصنوعی یک تصمیم معتبر است، نه شکست.

        WAIT شهروند درجه‌یک است و نباید به زور به معامله تبدیل شود.
        """
        app = _app(_decision(signal="WAIT"))

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.direction is SignalDirection.WAIT

    def test_garbage_numbers_do_not_crash_the_mapping(self) -> None:
        """مقدار غیرعددی باید نادیده گرفته شود، نه اینکه برنامه بیفتد."""
        app = _app(_decision(stop_loss="خیلی پایین", confidence="زیاد"))

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.direction is SignalDirection.LONG


class TestZeroConfidenceIsARealValue:
    """
    دام کلاسیک: `if value:` مقدار صفر را رد می‌کند.

    کد قبلی از همین الگو استفاده می‌کرد. صفر یعنی «مدل هیچ اطمینانی
    ندارد» و این اطلاعات مهمی است که نباید بی‌صدا حذف شود.
    """

    def test_zero_confidence_is_not_silently_dropped(self) -> None:
        """اطمینان صفر باید ثبت شود، نه اینکه مقدار موتور بماند."""
        app = _app(_decision(signal="WAIT", confidence=0))

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.confidence == 0

    def test_confidence_is_clamped_to_a_sane_range(self) -> None:
        """مدل گاهی ۱۲۰ می‌دهد؛ نباید به کاربر نشان داده شود."""
        app = _app(_decision(confidence=140))

        result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

        assert result.confidence == 100


class TestManualSignalSpeed:
    """
    شکایت دوم کاربر: «سرعت سیگنال‌گیری دستی».

    سقف زمان هوش مصنوعی باید واقعاً اعمال شود، وگرنه کاربر پشت یک مدل
    محلی کند تا ابد منتظر می‌ماند.
    """

    def test_a_slow_model_does_not_block_forever(self) -> None:
        """پس از سقف زمان، سیگنال موتور برگردانده می‌شود."""
        app = Application.__new__(Application)

        class SlowAnalyst:
            async def generate_signal(self, request):  # noqa: ANN001, ANN202
                await asyncio.sleep(10)
                return _decision()

        class Settings:
            def get_int(self, key, default=0):  # noqa: ANN001, ANN202
                return 1  # یک ثانیه

        app.ai_analyst = lambda: SlowAnalyst()
        app.settings = Settings()

        started = asyncio.run(_timed(app))

        assert started < 5, f"سقف زمان اعمال نشد: {started:.1f}s"


async def _timed(app: Application) -> float:
    """اندازه‌گیری زمان واقعی اعمال تصمیم."""
    import time

    start = time.monotonic()
    await app._apply_ai_decision(_engine_wait(), ["1h"])  # noqa: SLF001
    return time.monotonic() - start


@pytest.mark.parametrize("direction", ["LONG", "SHORT", "WAIT"])
def test_all_valid_directions_round_trip(direction: str) -> None:
    """هر سه جهت معتبر باید بدون استثنا نگاشت شوند."""
    app = _app(_decision(signal=direction))

    result = asyncio.run(app._apply_ai_decision(_engine_wait(), ["1h"]))  # noqa: SLF001

    assert result.direction.value == direction
