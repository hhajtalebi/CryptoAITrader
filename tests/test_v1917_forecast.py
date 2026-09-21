"""
آزمون‌های پیش‌بینی تایم‌فریم بعدی و راهبردهای تازه.

کاربر خواست: «از روی دادهٔ ۱۵ دقیقه‌ای، ۱۵ دقیقه / یک ساعت / چهار ساعت
آیندهٔ بازار پیش‌بینی شود.»

اصل حاکم بر این آزمون‌ها: پیش‌بینی باید **بازه** بدهد نه عدد قطعی، و
هرچه افق دورتر، بازه پهن‌تر. هر پیاده‌سازی‌ای که بازهٔ ثابت یا باریک‌شونده
بدهد، دارد اطمینان کاذب می‌فروشد.
"""

from __future__ import annotations

import pytest

from app.core.constants import SignalDirection
from signals.forecast import HORIZON_STEPS, MAX_PROBABILITY, forecast_next


class _Candle:
    """کندل ساده برای آزمون، بدون وابستگی به مدل‌های برنامه."""

    __slots__ = ("close", "high", "low", "open", "timestamp", "volume")

    def __init__(self, index: int, price: float, spread: float = 10.0) -> None:
        self.timestamp = 1_700_000_000 + index * 900
        self.open = price
        self.high = price + spread
        self.low = price - spread
        self.close = price
        self.volume = 100.0


def _series(
    count: int = 120,
    start: float = 1000.0,
    step: float = 0.0,
    spread: float = 10.0,
) -> list[_Candle]:
    """ساخت یک سری کندل با نوسان یکنواخت."""
    return [_Candle(i, start + i * step, spread=spread) for i in range(count)]


class TestTheForecastIsHonest:
    """پیش‌بینی باید محافظه‌کار و صادق باشد."""

    def test_it_produces_the_requested_horizons(self) -> None:
        """از دادهٔ ۱۵ دقیقه‌ای باید ۱۵ دقیقه، ۱ ساعت و ۴ ساعت بدهد."""
        result = forecast_next(symbol="BTC/USDT", timeframe="15m", candles=_series())
        horizons = [h.horizon for h in result.horizons]
        assert horizons == ["15m", "1h", "4h"]

    def test_the_range_widens_with_distance(self) -> None:
        """
        افق دورتر ⇒ عدم قطعیت بیشتر.

        اگر بازهٔ چهار ساعت به‌اندازهٔ پانزده دقیقه باریک باشد، پیش‌بینی
        دارد دروغ می‌گوید.
        """
        result = forecast_next(symbol="BTC/USDT", timeframe="15m", candles=_series())
        widths = [h.upper - h.lower for h in result.horizons]
        assert widths == sorted(widths)
        assert widths[-1] > widths[0]

    def test_the_probability_decays_with_distance(self) -> None:
        """اطمینان به افق دور باید کمتر از افق نزدیک باشد."""
        result = forecast_next(
            symbol="BTC/USDT",
            timeframe="15m",
            candles=_series(),
            direction=SignalDirection.LONG,
            confidence=80,
        )
        probabilities = [h.probability for h in result.horizons]
        assert probabilities == sorted(probabilities, reverse=True)

    def test_probability_never_exceeds_the_cap(self) -> None:
        """هیچ افقی نباید احتمال غیرواقعی اعلام کند."""
        result = forecast_next(
            symbol="BTC/USDT",
            timeframe="15m",
            candles=_series(),
            direction=SignalDirection.LONG,
            confidence=100,
        )
        for horizon in result.horizons:
            assert horizon.probability <= MAX_PROBABILITY

    def test_the_actual_price_sits_inside_the_range(self) -> None:
        """قیمت فعلی باید داخل بازهٔ پیش‌بینی باشد، وگرنه بازه بی‌معناست."""
        candles = _series()
        result = forecast_next(symbol="BTC/USDT", timeframe="15m", candles=candles)
        last = candles[-1].close
        for horizon in result.horizons:
            assert horizon.lower <= last <= horizon.upper

    def test_a_bullish_signal_shifts_the_centre_up(self) -> None:
        """تمایل صعودی، مرکز بازه را بالا می‌برد."""
        candles = _series()
        neutral = forecast_next(symbol="X", timeframe="15m", candles=candles)
        bullish = forecast_next(
            symbol="X",
            timeframe="15m",
            candles=candles,
            direction=SignalDirection.LONG,
            confidence=80,
        )
        assert bullish.horizons[0].expected_price > neutral.horizons[0].expected_price
        assert bullish.horizons[0].bias == "bullish"

    def test_a_bearish_signal_shifts_the_centre_down(self) -> None:
        """تمایل نزولی، مرکز بازه را پایین می‌آورد."""
        candles = _series()
        neutral = forecast_next(symbol="X", timeframe="15m", candles=candles)
        bearish = forecast_next(
            symbol="X",
            timeframe="15m",
            candles=candles,
            direction=SignalDirection.SHORT,
            confidence=80,
        )
        assert bearish.horizons[0].expected_price < neutral.horizons[0].expected_price
        assert bearish.horizons[0].bias == "bearish"

    def test_the_bias_never_collapses_the_range(self) -> None:
        """
        تمایل جهت‌دار فقط مرکز را جابه‌جا می‌کند، بازه را تنگ نمی‌کند.

        سیگنال قوی، عدم قطعیت بازار را کم نمی‌کند.
        """
        candles = _series()
        neutral = forecast_next(symbol="X", timeframe="15m", candles=candles)
        confident = forecast_next(
            symbol="X",
            timeframe="15m",
            candles=candles,
            direction=SignalDirection.LONG,
            confidence=92,
        )
        neutral_width = neutral.horizons[0].upper - neutral.horizons[0].lower
        confident_width = confident.horizons[0].upper - confident.horizons[0].lower
        assert confident_width == pytest.approx(neutral_width, rel=1e-6)

    def test_a_wait_signal_stays_neutral(self) -> None:
        """سیگنال انتظار نباید مرکز را جابه‌جا کند."""
        candles = _series()
        result = forecast_next(
            symbol="X",
            timeframe="15m",
            candles=candles,
            direction=SignalDirection.WAIT,
            confidence=45,
        )
        assert result.horizons[0].expected_price == pytest.approx(candles[-1].close)
        assert result.horizons[0].bias == "neutral"

    def test_a_calmer_market_gets_a_tighter_range(self) -> None:
        """نوسان کمتر ⇒ بازهٔ باریک‌تر. بازه باید از بازار بیاید."""
        calm = [_Candle(i, 1000.0, spread=1.0) for i in range(120)]
        wild = [_Candle(i, 1000.0, spread=50.0) for i in range(120)]
        calm_width = forecast_next(symbol="X", timeframe="15m", candles=calm).horizons[0]
        wild_width = forecast_next(symbol="X", timeframe="15m", candles=wild).horizons[0]
        assert (calm_width.upper - calm_width.lower) < (
            wild_width.upper - wild_width.lower
        )

    def test_the_price_is_never_negative(self) -> None:
        """قیمت منفی بی‌معناست، حتی با نوسان بسیار زیاد."""
        violent = [_Candle(i, 5.0, spread=4.9) for i in range(120)]
        result = forecast_next(symbol="X", timeframe="15m", candles=violent)
        for horizon in result.horizons:
            assert horizon.lower >= 0.0


class TestTheForecastRefusesToGuess:
    """وقتی داده نیست، پیش‌بینی نباید عدد بسازد."""

    def test_no_candles_means_no_forecast(self) -> None:
        """بدون کندل، هیچ عددی ساخته نمی‌شود."""
        result = forecast_next(symbol="X", timeframe="15m", candles=[])
        assert result.horizons == []
        assert result.note == "no_candles"

    def test_a_short_history_means_no_forecast(self) -> None:
        """با ۵ کندل نمی‌شود نوسان را برآورد کرد."""
        result = forecast_next(symbol="X", timeframe="15m", candles=_series(5))
        assert result.horizons == []
        assert result.note == "not_enough_history"

    def test_a_flat_market_means_no_forecast(self) -> None:
        """بازار کاملاً بی‌نوسان، بازه‌ای برای برآورد ندارد."""
        flat = [_Candle(i, 100.0, spread=0.0) for i in range(120)]
        result = forecast_next(symbol="X", timeframe="15m", candles=flat)
        assert result.horizons == []
        assert result.note == "flat_market"

    def test_an_unknown_timeframe_is_refused(self) -> None:
        """تایم‌فریم ناشناخته نباید با حدس پر شود."""
        result = forecast_next(symbol="X", timeframe="7s", candles=_series())
        assert result.horizons == []
        assert result.note == "unsupported_timeframe"

    def test_every_supported_timeframe_has_horizons(self) -> None:
        """هر تایم‌فریم پشتیبانی‌شده باید نگاشت افق داشته باشد."""
        for timeframe, mapping in HORIZON_STEPS.items():
            assert mapping, f"{timeframe} has no horizons"
            assert all(steps > 0 for steps in mapping.values())

    def test_the_result_serialises(self) -> None:
        """خروجی باید قابل ذخیره در پایگاه داده باشد."""
        result = forecast_next(symbol="X", timeframe="15m", candles=_series())
        payload = result.as_dict()
        assert payload["symbol"] == "X"
        assert len(payload["horizons"]) == 3
        assert {"horizon", "lower", "upper", "probability"} <= set(payload["horizons"][0])


class TestTheNewStrategiesAreRegistered:
    """دو راهبرد تازه باید واقعاً در موتور باشند."""

    def test_five_strategies_are_registered(self) -> None:
        """
        با سه راهبرد، در بازار روندی فقط یکی رأی می‌داد و اطمینان
        صادقانه هرگز از ۴۵٪ بالاتر نمی‌رفت.
        """
        from signals.strategies.registry import (
            StrategyRegistry,
            register_builtin_strategies,
        )

        registry = StrategyRegistry()
        count = register_builtin_strategies(registry)
        assert count == 5
        names = {strategy.name for strategy in registry.all()}
        assert {"momentum", "volatility_regime"} <= names

    def test_momentum_abstains_without_data(self) -> None:
        """
        بدون اندیکاتور، راهبرد باید کنار بکشد نه اینکه صفر رأی بدهد.

        «نظری ندارم» با «خنثی است» فرق دارد.
        """
        from signals.strategies.base import StrategyContext
        from signals.strategies.momentum import MomentumStrategy

        context = StrategyContext(
            symbol="X", timeframe="4h", candles=_series(), indicators={}
        )
        vote = MomentumStrategy().evaluate(context)
        assert vote.applicable is False

    def test_volatility_regime_abstains_without_a_trend(self) -> None:
        """بدون جهت، این راهبرد چیزی برای گفتن ندارد."""
        from app.core.constants import TrendDirection
        from signals.strategies.base import StrategyContext
        from signals.strategies.volatility_regime import VolatilityRegimeStrategy

        context = StrategyContext(
            symbol="X",
            timeframe="4h",
            candles=_series(),
            indicators={"ATR": {"latest": {"atr": 5.0}}},
            trend=TrendDirection.NEUTRAL,
        )
        vote = VolatilityRegimeStrategy().evaluate(context)
        assert vote.applicable is False

    def test_volatility_regime_prefers_a_compressed_market(self) -> None:
        """
        نوسان فشرده بهترین زمان ورود است: حد ضرر نزدیک می‌ماند.

        ورود در اوج نوسان، دلیل رایج «جهت درست بود ولی استاپ خورد» است.
        """
        from app.core.constants import TrendDirection
        from signals.strategies.base import StrategyContext
        from signals.strategies.volatility_regime import VolatilityRegimeStrategy

        candles = _series(spread=10.0)
        strategy = VolatilityRegimeStrategy()

        squeezed = strategy.evaluate(
            StrategyContext(
                symbol="X",
                timeframe="4h",
                candles=candles,
                indicators={"ATR": {"latest": {"atr": 8.0}}},
                trend=TrendDirection.BULLISH,
            )
        )
        expanded = strategy.evaluate(
            StrategyContext(
                symbol="X",
                timeframe="4h",
                candles=candles,
                indicators={"ATR": {"latest": {"atr": 40.0}}},
                trend=TrendDirection.BULLISH,
            )
        )
        assert squeezed.score > expanded.score

    def test_the_two_tools_are_exposed_to_the_ai(self) -> None:
        """مدل باید بتواند نظر موتور و پیش‌بینی را بپرسد."""
        from ai.tools.market_tools import MarketToolset

        names = {definition.name for definition in MarketToolset.get_definitions()}
        assert "get_engine_signal" in names
        assert "forecast_next_timeframe" in names

    def test_the_signal_model_carries_a_forecast_field(self) -> None:
        """پیش‌بینی باید همراه خود سیگنال ذخیره و منتقل شود."""
        from app.core.models import TradingSignal

        signal = TradingSignal(
            symbol="X", exchange="e", direction=SignalDirection.WAIT
        )
        assert signal.forecast == []
        assert "forecast" in signal.to_dict()


class TestForecastAccuracyCanBeMeasured:
    """
    پیش‌بینی‌ای که هرگز ارزیابی نشود، ادعای بی‌پشتوانه است.

    بازه با اطمینان ۸۰٪ ساخته می‌شود، پس در بلندمدت باید تقریباً ۸۰٪
    مواقع قیمت واقعی داخلش بیفتد. این سنجه تنها راه اثبات یا ردّ آن است.
    """

    @staticmethod
    def _horizons() -> list[dict]:
        return [
            {"horizon": "15m", "lower": 100.0, "upper": 110.0},
            {"horizon": "1h", "lower": 95.0, "upper": 115.0},
            {"horizon": "4h", "lower": 90.0, "upper": 120.0},
        ]

    def test_a_price_inside_the_range_counts_as_a_hit(self) -> None:
        """قیمت داخل بازه یعنی پیش‌بینی درست بوده."""
        from signals.forecast import score_forecast

        result = score_forecast(self._horizons(), {"15m": 105.0})
        assert result["checked"] == 1
        assert result["hits"] == 1
        assert result["hit_rate"] == 100.0

    def test_a_price_outside_the_range_counts_as_a_miss(self) -> None:
        """قیمت بیرون بازه یعنی پیش‌بینی اشتباه بوده."""
        from signals.forecast import score_forecast

        result = score_forecast(self._horizons(), {"15m": 130.0})
        assert result["hits"] == 0
        assert result["details"][0]["inside"] is False
        assert result["details"][0]["miss"] == pytest.approx(20.0)

    def test_the_boundary_counts_as_inside(self) -> None:
        """دقیقاً روی مرز، داخل حساب می‌شود."""
        from signals.forecast import score_forecast

        assert score_forecast(self._horizons(), {"15m": 110.0})["hits"] == 1
        assert score_forecast(self._horizons(), {"15m": 100.0})["hits"] == 1

    def test_a_missing_actual_price_is_not_counted(self) -> None:
        """
        افقی که قیمت واقعی‌اش نرسیده نباید شمرده شود.

        شمردنش به‌عنوان خطا، آمار را بی‌دلیل بد نشان می‌دهد.
        """
        from signals.forecast import score_forecast

        result = score_forecast(self._horizons(), {"1h": 100.0})
        assert result["checked"] == 1
        assert [d["horizon"] for d in result["details"]] == ["1h"]

    def test_no_data_yields_a_zero_sample(self) -> None:
        """بدون داده، نرخ اصابت ساختگی گزارش نمی‌شود."""
        from signals.forecast import score_forecast

        result = score_forecast(self._horizons(), {})
        assert result["checked"] == 0
        assert result["hit_rate"] == 0.0

    def test_the_target_rate_is_reported(self) -> None:
        """هدف باید کنار نتیجه باشد تا انحراف قابل قضاوت شود."""
        from signals.forecast import score_forecast

        assert score_forecast(self._horizons(), {"15m": 105.0})["target_rate"] == 80.0


class TestStaleSignalsCanBeHidden:
    """
    تنظیم `signals.hide_stale` تا امروز ذخیره می‌شد ولی خوانده نمی‌شد.

    تیکی که هیچ کاری نمی‌کند، بدترین نوع تنظیم است.
    """

    def test_the_not_enterable_set_defines_stale(self) -> None:
        """تعریف «سوخته» باید یکی باشد، نه دوتای موازی."""
        from signals.validity import NOT_ENTERABLE, Freshness

        assert Freshness.FRESH not in NOT_ENTERABLE
        assert Freshness.EXPIRED in NOT_ENTERABLE
        assert Freshness.STALE in NOT_ENTERABLE

    def test_the_setting_is_registered_with_a_safe_default(self) -> None:
        """پیش‌فرض باید «پنهان نکن» باشد تا چیزی بی‌خبر ناپدید نشود."""
        from app.config.defaults import DEFAULT_SETTINGS, SettingKey

        assert DEFAULT_SETTINGS[SettingKey.SIGNAL_HIDE_STALE.value] is False


class TestTheValidityWindowIsPersisted:
    """پنجرهٔ اعتبار و پیش‌بینی باید در پایگاه داده بمانند."""

    def test_the_signal_record_has_the_columns(self) -> None:
        """
        ستون‌ها وجود داشتند ولی هیچ‌وقت نوشته نمی‌شدند، پس سیگنالِ
        بازخوانده‌شده «بی‌تاریخ‌مصرف» به نظر می‌رسید.
        """
        from app.database.models import SignalRecord

        columns = set(SignalRecord.__table__.columns.keys())
        assert {"primary_timeframe", "enter_before", "valid_until", "forecast"} <= columns


class TestTheForecastIsVisibleInTheDetailDialog:
    """پیش‌بینی باید در پنجرهٔ جزئیات سیگنال هم دیده شود."""

    @staticmethod
    def _signal(**extra) -> dict:
        base = {
            "symbol": "BTC/USDT",
            "direction": "LONG",
            "confidence": 72,
            "stop_loss": 79_000.0,
            "take_profits": [82_000.0],
            "timeframes": ["1h", "4h"],
        }
        base.update(extra)
        return base

    def test_the_section_appears_when_a_forecast_exists(self, qt_application) -> None:
        """با پیش‌بینی معتبر، بخش ساخته می‌شود."""
        from localization import Translator
        from ui.dialogs.signal_detail_dialog import SignalDetailDialog

        signal = self._signal(
            forecast=[
                {
                    "horizon": "15m",
                    "lower": 80_100.0,
                    "upper": 80_900.0,
                    "bias": "bullish",
                    "probability": 60,
                }
            ]
        )
        dialog = SignalDetailDialog(signal, Translator("fa"))
        assert dialog._build_forecast() is not None  # noqa: SLF001

    def test_the_section_is_absent_for_older_signals(self, qt_application) -> None:
        """
        سیگنال‌های قدیمی پیش‌بینی ندارند و نباید بخش خالی بسازند.

        جای خالی بهتر از عدد ساختگی است.
        """
        from localization import Translator
        from ui.dialogs.signal_detail_dialog import SignalDetailDialog

        dialog = SignalDetailDialog(self._signal(), Translator("fa"))
        assert dialog._build_forecast() is None  # noqa: SLF001

    def test_malformed_rows_are_skipped(self, qt_application) -> None:
        """ردیف ناقص نباید «افق ؟ با بازهٔ ۰ تا ۰» بسازد."""
        from localization import Translator
        from ui.dialogs.signal_detail_dialog import SignalDetailDialog

        dialog = SignalDetailDialog(
            self._signal(forecast=[{"bad": "data"}]), Translator("fa")
        )
        assert dialog._build_forecast() is None  # noqa: SLF001

    def test_an_inverted_range_is_rejected(self, qt_application) -> None:
        """سقفِ کمتر از کف یعنی دادهٔ خراب."""
        from localization import Translator
        from ui.dialogs.signal_detail_dialog import SignalDetailDialog

        dialog = SignalDetailDialog(
            self._signal(forecast=[{"horizon": "1h", "lower": 9.0, "upper": 1.0}]),
            Translator("fa"),
        )
        assert dialog._build_forecast() is None  # noqa: SLF001

    def test_one_good_row_survives_a_bad_neighbour(self, qt_application) -> None:
        """یک ردیف خراب نباید ردیف سالم را هم از بین ببرد."""
        from localization import Translator
        from ui.dialogs.signal_detail_dialog import SignalDetailDialog

        dialog = SignalDetailDialog(
            self._signal(
                forecast=[
                    {
                        "horizon": "15m",
                        "lower": 80_100.0,
                        "upper": 80_900.0,
                        "bias": "bullish",
                        "probability": 60,
                    },
                    {"bad": 1},
                ]
            ),
            Translator("fa"),
        )
        assert dialog._build_forecast() is not None  # noqa: SLF001
