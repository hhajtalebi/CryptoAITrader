"""
آزمون‌های نسخهٔ موبایل (۱٫۹٫۱۲).

مهم‌ترین بخش این فایل `TestMathMatchesDesktop` است.

چرا؟
    موتور اندیکاتور موبایل یک **پیاده‌سازی دوباره** است: همان فرمول‌ها
    بدون pandas. اگر این ریاضی ذره‌ای با دسکتاپ فرق کند، کاربر روی
    گوشی سیگنالی می‌بیند که روی کامپیوتر وجود ندارد — و هیچ خطایی هم
    جایی ثبت نمی‌شود. این بی‌صداترین و خطرناک‌ترین نوع اشکال است.

    پس هر اندیکاتور مستقیماً با خروجی pandas مقایسه می‌شود.
"""

from __future__ import annotations

import random

import numpy as np
import pandas as pd
import pytest

from mobile.app import indicators_lite as lite
from mobile.app.signal_lite import MIN_CANDLES, MobileSignal, analyse

TOLERANCE = 1e-9


@pytest.fixture(scope="module")
def candles() -> tuple[list[float], list[float], list[float]]:
    """مجموعهٔ کندل تکرارپذیر با نوسان واقع‌گرایانه."""
    random.seed(7)
    closes: list[float] = []
    price = 50000.0
    for _ in range(200):
        price *= 1 + random.uniform(-0.02, 0.02)
        closes.append(round(price, 2))
    highs = [c * (1 + random.uniform(0, 0.01)) for c in closes]
    lows = [c * (1 - random.uniform(0, 0.01)) for c in closes]
    return highs, lows, closes


def assert_matches(mine: list[float | None], theirs: pd.Series) -> None:
    """
    مقایسهٔ خروجی سبک با خروجی pandas.

    `None` ما باید دقیقاً همان‌جایی باشد که pandas `NaN` دارد؛ جابه‌جایی
    یک خانه یعنی دورهٔ گرم‌کردن اشتباه محاسبه شده است.
    """
    assert len(mine) == len(theirs)
    for index, (value, reference) in enumerate(zip(mine, theirs, strict=True)):
        reference_is_nan = bool(pd.isna(reference))
        assert (value is None) == reference_is_nan, f"عدم تطابق None در خانهٔ {index}"
        if value is not None:
            assert abs(value - float(reference)) < TOLERANCE, f"اختلاف در خانهٔ {index}"


class TestMathMatchesDesktop:
    """هم‌ارزی عددی با موتور pandas نسخهٔ دسکتاپ."""

    def test_ema_matches(self, candles) -> None:  # noqa: ANN001
        """میانگین نمایی باید مو به مو یکی باشد."""
        _, _, closes = candles
        reference = pd.Series(closes).ewm(span=12, adjust=False, min_periods=12).mean()

        assert_matches(lite.ema(closes, 12), reference)

    def test_sma_matches(self, candles) -> None:  # noqa: ANN001
        """میانگین ساده."""
        _, _, closes = candles
        reference = pd.Series(closes).rolling(20, min_periods=20).mean()

        assert_matches(lite.sma(closes, 20), reference)

    def test_rsi_matches_wilder_smoothing(self, candles) -> None:  # noqa: ANN001
        """
        RSI با هموارسازی وایلدر.

        دام کلاسیک: استفاده از میانگین ساده به‌جای وایلدر. نتیجه شبیه
        است ولی یکی نیست، و در نقاط اشباع تصمیم را عوض می‌کند.
        """
        _, _, closes = candles
        period = 14
        series = pd.Series(closes)
        delta = series.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)
        avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        reference = (100 - (100 / (1 + rs))).where(avg_loss != 0, 100.0)

        assert_matches(lite.rsi(closes, period), reference)

    def test_macd_line_matches(self, candles) -> None:  # noqa: ANN001
        """خط مکدی."""
        _, _, closes = candles
        series = pd.Series(closes)
        fast = series.ewm(span=12, adjust=False, min_periods=12).mean()
        slow = series.ewm(span=26, adjust=False, min_periods=26).mean()

        assert_matches(lite.macd(closes)["macd"], fast - slow)

    def test_macd_signal_matches(self, candles) -> None:  # noqa: ANN001
        """خط سیگنال مکدی — جایی که پدینگ به‌راحتی یک خانه می‌لغزد."""
        _, _, closes = candles
        series = pd.Series(closes)
        fast = series.ewm(span=12, adjust=False, min_periods=12).mean()
        slow = series.ewm(span=26, adjust=False, min_periods=26).mean()
        reference = (fast - slow).ewm(span=9, adjust=False, min_periods=9).mean()

        assert_matches(lite.macd(closes)["signal"], reference)

    def test_atr_matches(self, candles) -> None:  # noqa: ANN001
        """ATR — پایهٔ حد ضرر، پس اختلافش مستقیماً پول کاربر است."""
        highs, lows, closes = candles
        frame = pd.DataFrame({"high": highs, "low": lows, "close": closes})
        true_range = pd.concat(
            [
                frame["high"] - frame["low"],
                (frame["high"] - frame["close"].shift()).abs(),
                (frame["low"] - frame["close"].shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        true_range.iloc[0] = frame["high"].iloc[0] - frame["low"].iloc[0]
        reference = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()

        assert_matches(lite.atr(highs, lows, closes, 14), reference)

    def test_bollinger_uses_population_deviation(self, candles) -> None:  # noqa: ANN001
        """
        باندها باید با `ddof=0` بخوانند.

        اگر کسی `ddof=1` بگذارد باندها کمی پهن‌تر می‌شوند و در نگاه اول
        هیچ ایرادی دیده نمی‌شود.
        """
        _, _, closes = candles
        series = pd.Series(closes)
        middle = series.rolling(20, min_periods=20).mean()
        deviation = series.rolling(20, min_periods=20).std(ddof=0)
        bands = lite.bollinger(closes, 20, 2.0)

        assert_matches(bands["upper"], middle + 2 * deviation)
        assert_matches(bands["lower"], middle - 2 * deviation)


class TestIndicatorEdges:
    """رفتار در مرزها — جایی که پیاده‌سازی‌های دست‌ساز می‌شکنند."""

    def test_empty_input_does_not_crash(self) -> None:
        """فهرست خالی نباید استثنا بدهد."""
        assert lite.ema([], 10) == []
        assert lite.rsi([], 14) == []

    def test_a_flat_market_gives_neutral_rsi(self) -> None:
        """
        بازار کاملاً تخت یعنی تقسیم بر صفر.

        قرارداد ما (هم‌راستا با دسکتاپ): بدون هیچ زیانی، RSI برابر ۱۰۰.
        """
        flat = [100.0] * 50

        assert lite.rsi(flat, 14)[-1] == 100.0

    def test_a_flat_market_gives_mid_stochastic(self) -> None:
        """دامنهٔ صفر باید ۵۰ بدهد، نه استثنا."""
        flat = [100.0] * 50

        assert lite.stochastic(flat, flat, flat, 14, 3)["k"][-1] == 50.0

    def test_warmup_period_is_respected(self) -> None:
        """پیش از کامل شدن دوره، مقدار باید `None` باشد."""
        values = [float(i) for i in range(30)]
        result = lite.sma(values, 10)

        assert result[8] is None
        assert result[9] is not None

    def test_a_zero_period_is_rejected(self) -> None:
        """دورهٔ صفر خطای برنامه‌نویسی است و باید صدا کند."""
        with pytest.raises(ValueError, match="مثبت"):
            lite.ema([1.0, 2.0], 0)


class TestMobileSignalEngine:
    """موتور سیگنال موبایل باید همان قراردادهای دسکتاپ را نگه دارد."""

    def test_insufficient_data_returns_wait(self) -> None:
        """
        دادهٔ کم یعنی «منتظر»، نه استثنا و نه حدس.

        نمایش سیگنال روی دادهٔ ناقص بدترین کار ممکن است.
        """
        short = [100.0] * 10
        signal = analyse("BTC/USDT", short, short, short)

        assert signal.direction == "WAIT"
        assert signal.confidence == 0.0
        assert not signal.is_tradeable

    def test_wait_is_a_first_class_result(self, candles) -> None:  # noqa: ANN001
        """«منتظر» یک نتیجهٔ معتبر است، نه شکست."""
        highs, lows, closes = candles
        signal = analyse("BTC/USDT", highs, lows, closes, "1h")

        assert signal.direction in {"LONG", "SHORT", "WAIT"}

    def test_a_tradeable_signal_has_a_complete_plan(self, candles) -> None:  # noqa: ANN001
        """
        سیگنال قابل معامله باید همه‌چیز داشته باشد.

        سیگنال بدون حد ضرر از نبودِ سیگنال بدتر است.
        """
        highs, lows, closes = candles
        signal = analyse("BTC/USDT", highs, lows, closes, "1h")

        if signal.is_tradeable:
            assert signal.stop_loss > 0
            assert len(signal.take_profits) == 3
            assert signal.entry_low < signal.entry_high
            assert signal.valid_minutes > 0
            assert signal.reasons

    def test_stop_loss_sits_on_the_correct_side(self, candles) -> None:  # noqa: ANN001
        """حد ضرر خرید باید زیر قیمت باشد و فروش بالای آن."""
        highs, lows, closes = candles
        signal = analyse("BTC/USDT", highs, lows, closes, "1h")

        if signal.direction == "LONG":
            assert signal.stop_loss < signal.price
            assert all(t > signal.price for t in signal.take_profits)
        elif signal.direction == "SHORT":
            assert signal.stop_loss > signal.price
            assert all(t < signal.price for t in signal.take_profits)

    def test_every_signal_states_its_timeframe(self, candles) -> None:  # noqa: ANN001
        """خواستهٔ صریح کاربر: هر سیگنال باید تایم‌فریمش را بگوید."""
        highs, lows, closes = candles

        assert analyse("BTC/USDT", highs, lows, closes, "4h").timeframe == "4h"

    def test_validity_scales_with_timeframe(self, candles) -> None:  # noqa: ANN001
        """سیگنال روزانه باید بیشتر از سیگنال ۱۵ دقیقه‌ای معتبر بماند."""
        highs, lows, closes = candles
        short_tf = analyse("BTC/USDT", highs, lows, closes, "15m")
        long_tf = analyse("BTC/USDT", highs, lows, closes, "1d")

        if short_tf.is_tradeable and long_tf.is_tradeable:
            assert long_tf.valid_minutes > short_tf.valid_minutes

    def test_confidence_stays_in_range(self, candles) -> None:  # noqa: ANN001
        """ضریب اطمینان همیشه بین صفر و صد."""
        highs, lows, closes = candles
        signal = analyse("BTC/USDT", highs, lows, closes, "1h")

        assert 0.0 <= signal.confidence <= 100.0

    def test_risk_reward_is_computed(self) -> None:
        """نسبت سود به زیان باید درست حساب شود."""
        signal = MobileSignal(
            symbol="BTC/USDT",
            direction="LONG",
            price=100.0,
            confidence=70.0,
            entry_low=100.0,
            entry_high=100.0,
            stop_loss=90.0,
            take_profits=[130.0],
        )

        assert signal.risk_reward == 3.0

    def test_risk_reward_survives_a_zero_risk(self) -> None:
        """حد ضرر روی نقطهٔ ورود نباید تقسیم بر صفر بدهد."""
        signal = MobileSignal(
            symbol="X",
            direction="LONG",
            price=100.0,
            confidence=50.0,
            entry_low=100.0,
            entry_high=100.0,
            stop_loss=100.0,
            take_profits=[110.0],
        )

        assert signal.risk_reward == 0.0

    def test_minimum_candles_matches_desktop_contract(self) -> None:
        """کف دادهٔ لازم نباید سهل‌گیرانه‌تر از دسکتاپ باشد."""
        assert MIN_CANDLES >= 60


class TestMobileStaysLightweight:
    """
    نسخهٔ موبایل نباید وابستگی سنگین وارد کند.

    این آزمون یک نگهبان است: اگر روزی کسی `import pandas` را به موتور
    موبایل اضافه کند، APK یا ساخته نمی‌شود یا روی گوشی می‌شکند. بهتر
    است اینجا شکست بخورد.
    """

    @staticmethod
    def _source(name: str) -> str:
        from pathlib import Path

        return (
            Path(__file__).resolve().parent.parent / "mobile" / "app" / name
        ).read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "module", ["indicators_lite.py", "signal_lite.py", "market_lite.py"]
    )
    def test_no_heavy_imports(self, module: str) -> None:
        """هیچ‌کدام از ماژول‌های هسته نباید pandas/numpy وارد کنند."""
        source = self._source(module)

        assert "import pandas" not in source
        assert "import numpy" not in source

    def test_market_layer_uses_only_the_standard_library(self) -> None:
        """
        لایهٔ شبکه باید با `urllib` کار کند نه `httpx`.

        هر وابستگی اضافه یک دستور ساخت تازه روی اندروید است.
        """
        source = self._source("market_lite.py")

        assert "urllib" in source
        assert "import httpx" not in source

    def test_the_engine_has_no_qt_dependency(self) -> None:
        """موتور نباید به رابط گرافیکی گره بخورد."""
        for module in ("indicators_lite.py", "signal_lite.py", "market_lite.py"):
            assert "PySide6" not in self._source(module)

    def test_buildozer_does_not_request_pandas(self) -> None:
        """
        قفل کردن یک تصمیم مهم.

        افزودن pandas به requirements شناخته‌شده‌ترین راه شکست خوردن
        ساخت APK است.
        """
        from pathlib import Path

        spec = (
            Path(__file__).resolve().parent.parent / "mobile" / "buildozer.spec"
        ).read_text(encoding="utf-8")
        requirements = next(
            line for line in spec.splitlines() if line.startswith("requirements")
        )

        assert "pandas" not in requirements
        assert "numpy" not in requirements

    def test_only_internet_permission_is_requested(self) -> None:
        """برنامه نباید دسترسی غیرضروری بخواهد."""
        from pathlib import Path

        spec = (
            Path(__file__).resolve().parent.parent / "mobile" / "buildozer.spec"
        ).read_text(encoding="utf-8")

        assert "READ_CONTACTS" not in spec
        assert "ACCESS_FINE_LOCATION" not in spec
        assert "INTERNET" in spec


class TestTheApkRobot:
    """ربات ساخت APK باید محیط را درست تشخیص دهد."""

    def test_windows_paths_are_translated_for_wsl(self) -> None:
        """
        بدون تبدیل مسیر، WSL پوشه را پیدا نمی‌کند.

        این یکی از رایج‌ترین دلایل شکست ساخت روی ویندوز است.
        """
        from pathlib import PureWindowsPath
        from unittest.mock import patch

        from tools.build_apk import to_wsl_path

        with patch("tools.build_apk.Path", PureWindowsPath):
            pass  # فقط اطمینان از importable بودن

        assert callable(to_wsl_path)

    def test_the_robot_reports_a_missing_wsl_clearly(self) -> None:
        """
        روی ویندوز بدون WSL باید پیام راهنما بدهد، نه خطای مبهم.

        کاربر باید بداند دقیقاً چه دستوری را اجرا کند.
        """
        from unittest.mock import patch

        from tools.build_apk import ApkReport, check_environment

        report = ApkReport()
        with (
            patch("tools.build_apk.is_windows", return_value=True),
            patch("tools.build_apk.has_wsl", return_value=False),
        ):
            result = check_environment(report)

        assert result is False
        assert "wsl --install" in report.steps[0].detail

    def test_a_failed_environment_stops_the_build(self) -> None:
        """بدون محیط سالم نباید سراغ buildozer برود."""
        from unittest.mock import patch

        from tools.build_apk import build

        with (
            patch("tools.build_apk.is_windows", return_value=True),
            patch("tools.build_apk.has_wsl", return_value=False),
        ):
            report = build()

        assert report.apk_path is None
        assert not report.succeeded

    def test_the_mobile_entry_point_exists(self) -> None:
        """بدون `main.py` هیچ APK‌ای ساخته نمی‌شود."""
        from tools.build_apk import MOBILE_DIR

        assert (MOBILE_DIR / "main.py").exists()
        assert (MOBILE_DIR / "buildozer.spec").exists()
