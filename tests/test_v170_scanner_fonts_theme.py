"""
آزمون‌های نسخهٔ ۱٫۷٫۰.

پوشش:
    * پویشگر بازار (`signals/scanner.py`)
    * درجه‌بندی رنگی سیگنال‌ها (`ui/signal_grading.py`)
    * قلم‌ها: پیش‌فرض وزیرمتن، افزودن ایران‌سنس و ساحل
    * پوستهٔ تازهٔ «نئون کربنی»
    * شبکهٔ رسپانسیو کارت‌های پوسته
"""

from __future__ import annotations

import asyncio
import types

import pytest

from app.core.constants import SignalDirection
from app.core.models import TradingSignal
from signals.scanner import DEFAULT_SCAN_LIMIT, MarketScanner, ScanProgress, ScanResult
from ui.signal_grading import (
    CONFIDENCE_GOOD,
    CONFIDENCE_STRONG,
    confidence_grade,
    direction_grade,
    risk_grade,
    risk_level,
    signal_risk_level,
)


# ---------------------------------------------------------------------------
# کمکی‌ها
# ---------------------------------------------------------------------------
def _signal(symbol: str, confidence: int, direction: SignalDirection = SignalDirection.LONG,
            risk_reward: float = 2.0) -> TradingSignal:
    """ساخت یک سیگنال ساختگی برای آزمون."""
    return TradingSignal(
        symbol=symbol,
        exchange="test",
        direction=direction,
        confidence=confidence,
        risk_reward=risk_reward,
        leverage=3,
    )


class _Market:
    """موتور بازار ساختگی با گردش مالی نزولی."""

    def __init__(self, count: int = 10) -> None:
        self.count = count

    async def get_all_tickers(self):
        return [
            types.SimpleNamespace(symbol=f"S{i}/USDT", turnover_24h=float(1000 - i))
            for i in range(self.count)
        ]

    async def get_symbols(self):
        return [types.SimpleNamespace(symbol=f"S{i}/USDT") for i in range(self.count)]


class _Engine:
    """موتور سیگنال ساختگی؛ اطمینان از شمارهٔ نماد ساخته می‌شود."""

    def __init__(self, *, fail: set[str] | None = None) -> None:
        self.fail = fail or set()
        self.calls: list[str] = []
        self.frames_seen: list[list[str] | None] = []

    async def generate(self, symbol: str, frames=None):
        self.calls.append(symbol)
        self.frames_seen.append(frames)
        if symbol in self.fail:
            raise RuntimeError("boom")
        index = int(symbol[1 : symbol.index("/")])
        direction = SignalDirection.WAIT if index % 4 == 0 else SignalDirection.LONG
        return _signal(symbol, confidence=20 + index * 5, direction=direction)


# ---------------------------------------------------------------------------
# پویشگر
# ---------------------------------------------------------------------------
def test_scan_sorts_by_confidence_descending() -> None:
    """بالاترین ضریب اطمینان باید ردیف نخست باشد — خواستهٔ صریح کاربر."""
    scanner = MarketScanner(_Market(), _Engine(), concurrency=3)
    result = asyncio.run(scanner.scan(limit=8))

    confidences = [s.confidence for s in result.signals]
    assert confidences == sorted(confidences, reverse=True)
    assert result.signals[0].confidence == max(confidences)


def test_scan_ranks_candidates_by_turnover_not_volume() -> None:
    """نمادها باید بر پایهٔ گردش مالی انتخاب شوند، نه ترتیب دلخواه صرافی."""
    engine = _Engine()
    scanner = MarketScanner(_Market(count=10), engine, concurrency=1)
    asyncio.run(scanner.scan(limit=3))

    # گردش مالی نزولی است، پس S0 پرگردش‌ترین است.
    assert engine.calls == ["S0/USDT", "S1/USDT", "S2/USDT"]


def test_scan_survives_a_failing_symbol() -> None:
    """
    یک نماد خراب نباید کل پویش را بکشد.

    بازارهای بزرگ همیشه چند نماد تازه‌فهرست‌شده و بی‌کندل دارند.
    """
    engine = _Engine(fail={"S2/USDT", "S5/USDT"})
    scanner = MarketScanner(_Market(), engine, concurrency=4)
    result = asyncio.run(scanner.scan(limit=8))

    assert result.failed == 2
    assert result.scanned == 6
    assert all(s.symbol not in {"S2/USDT", "S5/USDT"} for s in result.signals)


def test_scan_excludes_wait_unless_requested() -> None:
    """«انتظار» به‌صورت پیش‌فرض در نتیجه نمی‌آید ولی با درخواست می‌آید."""
    scanner = MarketScanner(_Market(), _Engine(), concurrency=4)

    without = asyncio.run(scanner.scan(limit=8))
    assert all(s.direction is not SignalDirection.WAIT for s in without.signals)

    with_wait = asyncio.run(scanner.scan(limit=8, include_wait=True))
    assert any(s.direction is SignalDirection.WAIT for s in with_wait.signals)


def test_scan_applies_minimum_confidence() -> None:
    """فیلتر کمینهٔ اطمینان باید واقعاً ردیف‌ها را حذف کند."""
    scanner = MarketScanner(_Market(), _Engine(), concurrency=4)
    result = asyncio.run(scanner.scan(limit=10, min_confidence=50))

    assert result.signals, "دست‌کم یک سیگنال باید از فیلتر رد شود"
    assert all(s.confidence >= 50 for s in result.signals)


def test_scan_reports_progress_for_every_symbol() -> None:
    """کاربر باید پیشرفت را ببیند، نه یک دکمهٔ بی‌حرکت."""
    seen: list[ScanProgress] = []
    scanner = MarketScanner(_Market(), _Engine(), concurrency=2)
    asyncio.run(scanner.scan(limit=6, on_progress=seen.append))

    assert len(seen) == 6
    assert seen[-1].done == 6
    assert seen[-1].percent == 100
    assert [p.done for p in seen] == sorted(p.done for p in seen)


def test_scan_progress_callback_failure_does_not_break_scan() -> None:
    """پس‌فراخوان معیوب نباید پویش را از کار بیندازد."""
    def boom(_progress: ScanProgress) -> None:
        raise ValueError("callback exploded")

    scanner = MarketScanner(_Market(), _Engine(), concurrency=2)
    result = asyncio.run(scanner.scan(limit=4, on_progress=boom))

    assert result.scanned == 4


def test_scan_never_calls_ai() -> None:
    """
    پویش باید فقط موتور ریاضی را صدا بزند.

    کاربر صریح گفت این کار نباید توکن هوش مصنوعی بسوزاند. پویشگر هیچ
    ارجاعی به لایهٔ هوش مصنوعی ندارد و این آزمون همان را تضمین می‌کند.
    """
    import inspect

    import signals.scanner as scanner_module

    source = inspect.getsource(scanner_module)
    for forbidden in ("ai_analyst", "narrative", "chat_agent", "provider_manager"):
        assert forbidden not in source, f"پویشگر نباید به {forbidden} وابسته باشد"


def test_scan_result_helpers() -> None:
    """`top()` و `actionable` باید همان چیزی را بدهند که نامشان می‌گوید."""
    result = ScanResult(signals=[
        _signal("A/USDT", 80),
        _signal("B/USDT", 60, direction=SignalDirection.WAIT),
        _signal("C/USDT", 40),
    ])
    assert [s.symbol for s in result.top(2)] == ["A/USDT", "C/USDT"][:1] + ["B/USDT"]
    assert [s.symbol for s in result.actionable] == ["A/USDT", "C/USDT"]


def test_scan_falls_back_when_tickers_unavailable() -> None:
    """اگر تیکرها نیایند، پویش باید از فهرست خام نمادها ادامه دهد."""
    class Broken(_Market):
        async def get_all_tickers(self):
            raise RuntimeError("exchange down")

    scanner = MarketScanner(Broken(), _Engine(), concurrency=2)
    result = asyncio.run(scanner.scan(limit=4))
    assert result.scanned == 4


def test_default_scan_limit_is_sane() -> None:
    """سقف پیش‌فرض نه آن‌قدر کم که بی‌فایده باشد، نه آن‌قدر زیاد که کند شود."""
    assert 20 <= DEFAULT_SCAN_LIMIT <= 300


# ---------------------------------------------------------------------------
# درجه‌بندی رنگی
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("confidence", "expected", "token"),
    [
        (95, "strong", "success"),
        (60, "strong", "success"),
        (59, "good", "success"),
        (50, "good", "success"),
        (49, "fair", "warning"),
        (35, "fair", "warning"),
        (34, "weak", "neutral"),
        (0, "weak", "neutral"),
    ],
)
def test_confidence_grades_match_requested_thresholds(
    confidence: int, expected: str, token: str
) -> None:
    """کاربر خواست «۵۰ یا ۶۰ به بالا سبز» — هر دو مرز سبز می‌دهند."""
    grade = confidence_grade(confidence)
    assert grade.key == expected
    assert grade.token == token


def test_fifty_and_sixty_are_both_green() -> None:
    """تصریح همان خواسته، مستقل از جدول بالا."""
    assert confidence_grade(CONFIDENCE_GOOD).token == "success"
    assert confidence_grade(CONFIDENCE_STRONG).token == "success"
    # ۶۰ باید از ۵۰ متمایز باشد (پررنگ‌تر)، وگرنه «۵۰ یا ۶۰» معنا نداشت
    assert confidence_grade(CONFIDENCE_STRONG).emphasis
    assert not confidence_grade(CONFIDENCE_GOOD).emphasis


def test_confidence_grade_tolerates_bad_input() -> None:
    """یک ردیف خراب در جدول نباید صفحه را بیندازد."""
    assert confidence_grade(None).key == "weak"
    assert confidence_grade("nonsense").key == "weak"  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"stop_distance_percent": 1.0, "leverage": 2, "risk_reward": 3.0}, "low"),
        ({"stop_distance_percent": 4.0, "leverage": 5, "risk_reward": 2.0}, "medium"),
        ({"stop_distance_percent": 9.0, "leverage": 3, "risk_reward": 3.0}, "high"),
        ({"stop_distance_percent": 1.0, "leverage": 20, "risk_reward": 3.0}, "high"),
        ({"stop_distance_percent": 1.0, "leverage": 2, "risk_reward": 1.1}, "high"),
        ({}, "unknown"),
    ],
)
def test_risk_level_uses_worst_factor(kwargs: dict, expected: str) -> None:
    """
    بدترین عامل تعیین‌کننده است، نه میانگین.

    اهرم ۲۰ حتی با حد ضرر نزدیک و R/R عالی، معاملهٔ پرریسکی است؛
    میانگین‌گیری این خطر را پنهان می‌کرد.
    """
    assert risk_level(**kwargs) == expected


def test_risk_colours_follow_requested_scale() -> None:
    """کم‌ریسک سبز، پرریسک قرمز، میانه کهربایی."""
    assert risk_grade("low").token == "success"
    assert risk_grade("medium").token == "warning"
    assert risk_grade("high").token == "danger"
    assert risk_grade("nonsense").token == "neutral"


def test_wait_direction_has_its_own_colour() -> None:
    """کاربر خواست «انتظار هم رنگ مناسب» داشته باشد — نه سبز، نه قرمز."""
    wait = direction_grade("WAIT")
    assert wait.token not in {"success", "danger"}
    assert direction_grade("LONG").token == "success"
    assert direction_grade("SHORT").token == "danger"


def test_wait_rows_are_not_labelled_low_risk() -> None:
    """
    «انتظار» معامله نیست، پس نباید برچسب کم‌ریسک بگیرد.

    پیش‌تر چون اهرم پیش‌فرض ۱ بود، ردیف انتظار «کم‌ریسک» نشان داده
    می‌شد و کاربر آن را فرصت امن می‌پنداشت.
    """
    assert signal_risk_level({"direction": "WAIT", "leverage": 1}) == "unknown"


def test_signal_without_risk_data_is_unknown_not_low() -> None:
    """نبود داده یعنی نامشخص، نه کم‌ریسک."""
    assert signal_risk_level({"direction": "LONG", "leverage": 1}) == "unknown"
    assert signal_risk_level(
        {"direction": "LONG", "leverage": 2, "risk_reward": 3.0}
    ) == "low"


def test_signal_risk_level_reads_both_data_shapes() -> None:
    """داده هم از موتور (تودرتو) و هم از پایگاه داده (مسطح) می‌آید."""
    nested = {"direction": "LONG", "leverage": 3, "risk": {"stop_distance_percent": 1.0},
              "risk_reward": 3.0}
    flat = {"direction": "LONG", "leverage": 3, "stop_distance_percent": 1.0,
            "risk_reward": 3.0}
    assert signal_risk_level(nested) == signal_risk_level(flat) == "low"


# ---------------------------------------------------------------------------
# قلم‌ها
# ---------------------------------------------------------------------------
def test_default_font_is_vazirmatn() -> None:
    """کاربر گفت «فونت پیش‌فرض وزیرمتن باشه، این خوبه»."""
    from ui.themes.fonts import DEFAULT_FONT_KEY

    assert DEFAULT_FONT_KEY == "vazirmatn"


def test_default_setting_matches_default_font() -> None:
    """پیش‌فرض تنظیمات و پیش‌فرض ماژول قلم نباید از هم جدا بیفتند."""
    from app.config.defaults import DEFAULT_SETTINGS
    from ui.themes.fonts import DEFAULT_FONT_KEY

    assert DEFAULT_SETTINGS["ui.font_family"] == DEFAULT_FONT_KEY


def test_iransans_and_sahel_are_offered() -> None:
    """هر دو قلم خواسته‌شده باید در فهرست انتخاب باشند."""
    from ui.themes.fonts import FONT_MAP

    assert "iransans" in FONT_MAP
    assert "sahel" in FONT_MAP


def test_iransans_is_not_bundled_but_sahel_is() -> None:
    """
    ایران‌سنس قلم تجاری است و اجازهٔ توزیع مجدد ندارد.

    پس نباید فایلش همراه برنامه برود؛ ساحل پروانهٔ آزاد OFL دارد و
    همراه می‌رود.
    """
    from ui.themes.fonts import FONT_FILES, FONT_MAP

    assert FONT_MAP["iransans"].bundled is False
    assert FONT_MAP["sahel"].bundled is True
    assert not any("IRANSans" in name for name in FONT_FILES)
    assert "Sahel.ttf" in FONT_FILES


def test_bundled_font_files_exist_on_disk() -> None:
    """هر فایلی که در فهرست ثبت است باید واقعاً موجود باشد."""
    from ui.themes.fonts import FONTS_DIR, FONT_FILES

    missing = [name for name in FONT_FILES if not (FONTS_DIR / name).exists()]
    assert not missing, f"فایل قلم گم‌شده: {missing}"


def test_every_font_stack_ends_with_vazirmatn() -> None:
    """
    قاعدهٔ دیرین پروژه: نمادهای لاتین مثل BTC/USDT باید همیشه قلم
    پشتیبان داشته باشند، وگرنه مربع خالی دیده می‌شود.
    """
    from ui.themes.fonts import FONT_CHOICES

    for choice in FONT_CHOICES:
        assert "Vazirmatn" in choice.stack, choice.key


def test_user_font_directory_is_documented() -> None:
    """کاربر باید بداند ایران‌سنس را کجا بگذارد."""
    from ui.themes.fonts import USER_FONTS_DIR

    readme = USER_FONTS_DIR / "README.txt"
    assert readme.exists()
    assert "IRANSans" in readme.read_text(encoding="utf-8")


def test_font_names_are_translated_in_both_languages() -> None:
    """هیچ رشتهٔ رابط کاربری نباید بدون ترجمه بماند."""
    import json
    from pathlib import Path

    for language in ("fa", "en"):
        data = json.loads(
            Path(f"localization/{language}/settings.json").read_text(encoding="utf-8")
        )
        assert "iransans" in data["fonts"]
        assert "sahel" in data["fonts"]
        assert data["font_not_installed"]


# ---------------------------------------------------------------------------
# پوستهٔ تازه
# ---------------------------------------------------------------------------
def test_carbon_neon_theme_exists() -> None:
    """پوستهٔ مدرن تازه‌ای که کاربر خواست."""
    from ui.themes.catalog import THEME_CATALOG

    assert "carbon_neon" in THEME_CATALOG
    theme = THEME_CATALOG["carbon_neon"]
    assert theme.is_dark
    assert theme.effects.glass


def test_carbon_neon_is_translated_and_registered() -> None:
    """نام و توضیح پوسته در هر دو زبان و در enum ثبت شده باشد."""
    import json
    from pathlib import Path

    from app.core.constants import Theme

    assert Theme.CARBON_NEON.value == "carbon_neon"
    for language in ("fa", "en"):
        data = json.loads(
            Path(f"localization/{language}/settings.json").read_text(encoding="utf-8")
        )
        assert data["themes"]["carbon_neon"]
        assert data["theme_descriptions"]["carbon_neon"]


def test_adding_a_theme_does_not_change_the_default() -> None:
    """
    افزودن پوستهٔ تازه نباید پیش‌فرض را عوض کند.

    مقصود این آزمون «پیش‌فرض تصادفی جابه‌جا نشود» بود، نه «پیش‌فرض
    همیشه شیشه‌ای تیره بماند». کاربر بعداً صریحاً «سرمه‌ای اداری» را
    خواست، پس مقدار مورد انتظار به‌روز شد و خودِ محافظت سر جایش است.
    """
    from ui.themes.catalog import DEFAULT_THEME

    assert DEFAULT_THEME == "corporate_navy"


def test_carbon_neon_builds_a_complete_stylesheet() -> None:
    """پوستهٔ تازه نباید جای‌گیر پرنشده در QSS بگذارد."""
    import re

    from ui.themes.catalog import THEME_CATALOG
    from ui.themes.stylesheet import build_stylesheet

    qss = build_stylesheet(THEME_CATALOG["carbon_neon"])
    assert len(qss) > 10_000
    assert not re.findall(r"\{[a-z_]+\}", qss)


def test_spinbox_arrows_are_styled_per_theme() -> None:
    """
    ورودی عددی باید فلش خودمان را داشته باشد، نه فلش پیش‌فرض سیستم.

    این همان چیزی بود که کاربر «علامت‌های زیاد و اذیت‌کننده» خواندش.
    """
    from ui.themes.catalog import THEME_CATALOG
    from ui.themes.stylesheet import build_stylesheet

    dark = build_stylesheet(THEME_CATALOG["glass_dark"])
    light = build_stylesheet(THEME_CATALOG["minimal_light"])

    assert "QSpinBox::up-arrow" in dark
    assert "QSpinBox::down-button" in dark
    assert "data:image/svg+xml" in dark
    # رنگ فلش باید با پوسته عوض شود، وگرنه روی پوستهٔ روشن دیده نمی‌شود
    assert dark != light


def test_default_font_is_first_in_the_picker() -> None:
    """
    فهرست قلم باید با پیش‌فرض شروع شود.

    وگرنه وقتی هنوز چیزی ذخیره نشده، فهرست روی آیتم نخست می‌ایستد و
    نامی را نشان می‌دهد که برنامه واقعاً استفاده نمی‌کند — همان چیزی
    که در آزمون بصری دیده شد: قلم فعال وزیرمتن بود ولی فهرست «ب کودک»
    می‌گفت.
    """
    from ui.themes.fonts import DEFAULT_FONT_KEY, FONT_CHOICES

    assert FONT_CHOICES[0].key == DEFAULT_FONT_KEY


def test_font_hint_mentions_the_bundled_fonts_and_iransans() -> None:
    """
    متن راهنما باید با واقعیت بخواند.

    پیش‌تر می‌گفت «قلم ب کودک همراه برنامه توزیع می‌شود» و از وزیرمتن و
    ساحل و وضعیت ویژهٔ ایران‌سنس چیزی نمی‌گفت.
    """
    import json
    from pathlib import Path

    fa = json.loads(Path("localization/fa/settings.json").read_text(encoding="utf-8"))
    hint = fa["appearance"]["font_hint"]
    assert "وزیرمتن" in hint
    assert "ساحل" in hint
    assert "ایران‌سنس" in hint
