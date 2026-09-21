"""
آزمون‌های نسخهٔ ۱.۹.۵ — کار روی هوش مصنوعی و اعتبار سیگنال.

کاربر شش چیز گزارش کرد که همه به هم مربوط‌اند:

۱. «هنوز به اولاما وصل نمی‌شود.»
۲. «سابقهٔ سیگنال باید تحلیل با هوش مصنوعی داشته باشد.»
۳. «هوش مصنوعی باید پیشنهاد خرید و فروش بدهد.»
۴. «باید مشخص باشد در چه زمان و تایم‌فریمی، تا سیگنال سوخته نباشد.»
۵. «باید بدانیم این سیگنال تا کی اعتبار دارد.»
۶. «بعضی سیگنال‌ها سودی نداده‌اند.»

ریشهٔ ۱، ۳ و ۶ یکی بود و با اندازه‌گیری پیدا شد، نه با حدس: پرامپت
تحلیل ۱۷ کیلوبایت بود و برنامه از اولاما پنجرهٔ ۱۶۳۸۴ توکنی می‌خواست.
روی ماشین ۱۶ گیگابایتی کاربر آن پنجره جا نمی‌شود و اجراکنندهٔ اولاما
پیش از تولید پاسخ می‌میرد؛ خروجی‌اش «۵۰۰ با بدنهٔ خالی» است. بدتر
اینکه راه جبرانی پنجره را به ۴۰۹۶ می‌آورد ولی پرامپت ۵۸۰۰ توکنی را
کوچک نمی‌کرد، و اولاما بی‌صدا ابتدای آن را می‌برید — مدل نصف داده‌ها
را نمی‌دید و جای خالی را با حدس پر می‌کرد.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtWidgets import QLabel


# ---------------------------------------------------------------------------
# ۱) بودجهٔ پرامپت — ریشهٔ خطای اولاما
# ---------------------------------------------------------------------------


class TestPromptBudget:
    """پرامپت باید اندازهٔ مدل باشد، نه مدل اندازهٔ پرامپت."""

    def test_memory_tiers_match_real_hardware(self) -> None:
        """
        سقف پنجره باید با حافظهٔ دستگاه بالا و پایین برود.

        عددها از رفتار واقعی اولاما آمده‌اند: ماشین ۱۶ گیگابایتی کاربر
        با مدل ۸ میلیاردی تا ۸۱۹۲ را تحمل می‌کند، نه بیشتر.
        """
        from ai.prompt_budget import safe_context_for_memory

        assert safe_context_for_memory(8) == 4096
        assert safe_context_for_memory(16) == 8192
        assert safe_context_for_memory(32) == 16384
        assert safe_context_for_memory(64) == 32768

    def test_unknown_memory_is_conservative(self) -> None:
        """
        وقتی حافظه معلوم نیست باید محافظه‌کار بود.

        شکست محافظه‌کارانه یعنی تحلیل کمی خلاصه‌تر؛ شکست خوش‌بینانه
        یعنی «HTTP 500» و هیچ تحلیلی.
        """
        from ai.prompt_budget import DEFAULT_SAFE_CONTEXT, safe_context_for_memory

        assert safe_context_for_memory(None) == DEFAULT_SAFE_CONTEXT
        assert safe_context_for_memory(0) == DEFAULT_SAFE_CONTEXT

    def test_context_never_exceeds_the_ceiling(self) -> None:
        """قید سخت: سقف حافظه شکسته نمی‌شود، هر چقدر پرامپت بزرگ باشد."""
        from ai.prompt_budget import choose_context_window

        assert choose_context_window(50_000, 2000, ceiling=8192) == 8192

    def test_window_is_the_smallest_that_fits(self) -> None:
        """
        پنجرهٔ بی‌جهت بزرگ، حافظه را بی‌دلیل مصرف می‌کند.

        یک پرسش کوتاه چت نباید همان پنجره‌ای را بگیرد که تحلیل کامل
        می‌گیرد.
        """
        from ai.prompt_budget import choose_context_window

        assert choose_context_window(100, 500, ceiling=32768) == 2048

    def test_reply_space_is_reserved(self) -> None:
        """
        بخشی از پنجره باید برای پاسخ خالی بماند.

        مدل‌های استدلالی پیش از پاسخ بلوک فکر تولید می‌کنند؛ بدون جای
        خالی، پاسخ وسط استدلال قطع می‌شود.
        """
        from ai.prompt_budget import available_prompt_tokens

        assert available_prompt_tokens(8192) < 8192
        assert available_prompt_tokens(8192) > 1000

    def test_compact_json_is_smaller_than_indented(self) -> None:
        """
        تورفتگی برای چشم انسان است، نه برای مدل.

        نسخهٔ پیشین با `indent=1` سریال می‌کرد که حدود ۳۰٪ توکن بیشتر
        مصرف می‌کند — یعنی ۳۰٪ بیشتر احتمال سرریز پنجره.
        """
        import json

        from ai.prompt_budget import compact_json

        payload = {"timeframes": {f"tf{i}": {"rsi": 61.5, "macd": 0.42} for i in range(20)}}

        assert len(compact_json(payload)) < len(json.dumps(payload, indent=1))


class TestMarketDataShrinking:
    """وقتی داده جا نمی‌شود، باید آگاهانه کوچک شود نه کور بریده."""

    @staticmethod
    def _market_data() -> dict:
        """بستهٔ دادهٔ نمونه با همان شکل واقعی."""
        return {
            "symbol": "BTC/USDT",
            "timeframes": {
                tf: {
                    "indicators": {f"ind{i}": {"value": 1.23} for i in range(24)},
                    "price_action": {
                        "last_candles": [{"o": 1, "h": 2, "l": 0.5, "c": 1.5} for _ in range(10)]
                    },
                    "volume": {"total": 1234},
                    "structure": {"type": "BULLISH"},
                }
                for tf in ("1d", "4h", "1h", "15m")
            },
            "orderbook": {"bids": [[1, 2]] * 20, "asks": [[3, 4]] * 20},
        }

    def test_nothing_is_dropped_when_it_already_fits(self) -> None:
        """کوچک‌کردن بی‌دلیل، دورانداختن اطلاعات است."""
        from ai.prompt_budget import shrink_market_data

        result = shrink_market_data({"symbol": "BTC/USDT"}, budget_tokens=10_000)

        assert result.dropped == []
        assert result.truncated is False

    def test_orderbook_goes_first(self) -> None:
        """
        دفتر سفارش کم‌ارزش‌ترین بخش است.

        عکس لحظه‌ای است و تا رسیدن پاسخ مدل کهنه شده؛ اندیکاتورها
        اما هستهٔ تصمیم‌اند.
        """
        from ai.prompt_budget import shrink_market_data

        result = shrink_market_data(self._market_data(), budget_tokens=700)

        assert "orderbook" not in result.data
        assert "order book depth" in result.dropped

    def test_the_primary_timeframe_survives(self) -> None:
        """
        تایم‌فریم اصلی هرگز حذف نمی‌شود.

        حذف آن یعنی تحلیل دربارهٔ چیزی که کاربر خواسته انجام نشود.
        """
        from ai.prompt_budget import shrink_market_data

        result = shrink_market_data(
            self._market_data(), budget_tokens=200, primary_timeframe="15m"
        )

        assert "15m" in result.data["timeframes"]

    def test_the_widest_timeframe_survives(self) -> None:
        """
        بزرگ‌ترین تایم‌فریم هم می‌ماند.

        بدون تصویر کلان، تحلیل کوتاه‌مدت می‌تواند خلاف روند اصلی
        سیگنال بدهد — دقیقاً همان سیگنالی که سود نمی‌دهد.
        """
        from ai.prompt_budget import shrink_market_data

        result = shrink_market_data(
            self._market_data(), budget_tokens=200, primary_timeframe="15m"
        )

        assert "1d" in result.data["timeframes"]

    def test_the_model_is_told_what_is_missing(self) -> None:
        """
        مدلی که نداند داده‌ای کم دارد، جای خالی را با حدس پر می‌کند.

        این همان مکانیزمی است که سیگنال‌های بی‌اعتماد می‌سازد: پاسخ
        معتبر به نظر می‌رسد ولی روی داده‌ای ناقص بنا شده است.
        """
        from ai.prompt_budget import shrink_market_data

        result = shrink_market_data(self._market_data(), budget_tokens=300)

        assert result.note
        assert "do not guess" in result.note.lower() or "Do NOT guess" in result.note

    def test_shrinking_stops_as_soon_as_it_fits(self) -> None:
        """بیش از نیاز نباید داده دور ریخته شود."""
        from ai.prompt_budget import estimate_payload_tokens, shrink_market_data

        data = self._market_data()
        # بودجه‌ای که فقط با حذف دفتر سفارش تأمین می‌شود
        without_orderbook = dict(data)
        without_orderbook.pop("orderbook")
        budget = estimate_payload_tokens(without_orderbook) + 10

        result = shrink_market_data(data, budget_tokens=budget)

        assert result.dropped == ["order book depth"]
        assert len(result.data["timeframes"]) == 4


# ---------------------------------------------------------------------------
# ۲) بلوک استدلال مدل‌های reasoning
# ---------------------------------------------------------------------------


class TestReasoningBlock:
    """`deepseek-r1` پاسخ را داخل <think> می‌پیچد."""

    def test_the_think_block_is_removed(self) -> None:
        """
        بدون پاک‌سازی، `json.loads` روی خروجی همیشه شکست می‌خورد.

        این دومین دلیل «وصل نشدن» اولاما بود: اتصال برقرار می‌شد، مدل
        جواب می‌داد، ولی پاسخ غیرقابل استفاده بود.
        """
        from ai.prompt_budget import strip_reasoning_block

        raw = '<think>\nLet me check the RSI...\n</think>\n{"signal": "LONG"}'

        assert strip_reasoning_block(raw) == '{"signal": "LONG"}'

    @pytest.mark.parametrize(
        "tags",
        [("<think>", "</think>"), ("<thinking>", "</thinking>"), ("<reasoning>", "</reasoning>")],
    )
    def test_other_reasoning_tag_styles(self, tags) -> None:
        """هر خانواده از مدل‌ها برچسب خودش را دارد."""
        from ai.prompt_budget import strip_reasoning_block

        open_tag, close_tag = tags

        assert strip_reasoning_block(f"{open_tag}x{close_tag}answer") == "answer"

    def test_an_unclosed_block_yields_nothing(self) -> None:
        """
        بلوک بازِ بسته‌نشده یعنی پاسخ وسط استدلال قطع شده است.

        برگرداندن افکار نیمه‌کارهٔ مدل به‌عنوان «پاسخ» بدتر از
        برنگرداندن چیزی است.
        """
        from ai.prompt_budget import strip_reasoning_block

        assert strip_reasoning_block("<think>I was thinking when I got cut") == ""

    def test_plain_text_is_untouched(self) -> None:
        """پاسخ مدل عادی نباید دست بخورد."""
        from ai.prompt_budget import strip_reasoning_block

        assert strip_reasoning_block('{"signal":"WAIT"}') == '{"signal":"WAIT"}'


# ---------------------------------------------------------------------------
# ۳) پنجرهٔ اعتبار — «سیگنال سوخته»
# ---------------------------------------------------------------------------


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

BASE_SIGNAL = {
    "direction": "LONG",
    "entry_min": 60000.0,
    "entry_max": 60200.0,
    "stop_loss": 58800.0,
    "take_profits": [62000.0, 63000.0],
    "timeframes": ["15m"],
}


def check(minutes_ago: float = 0, price: float | None = 60100.0, **overrides):
    """کمک‌کنندهٔ کوتاه برای ساخت و سنجش یک سیگنال."""
    from signals.validity import evaluate

    payload = {**BASE_SIGNAL, **overrides}
    return evaluate(
        created_at=NOW - timedelta(minutes=minutes_ago),
        current_price=price,
        now=NOW,
        **payload,
    )


class TestValidityWindow:
    """هر سیگنال تاریخ مصرف دارد؛ کاربر باید آن را ببیند."""

    def test_a_new_signal_is_fresh(self) -> None:
        """سیگنال تازه با قیمت سر جایش، قابل ورود است."""
        from signals.validity import Freshness

        window = check(minutes_ago=2)

        assert window.freshness is Freshness.FRESH
        assert window.is_enterable

    def test_the_window_closes_before_it_expires(self) -> None:
        """
        بین «هنوز می‌شود وارد شد» و «کاملاً بی‌اعتبار» یک مرحله هست.

        کاربر باید فرصت بداند دارد تمام می‌شود، نه اینکه ناگهان با
        سیگنال مرده روبه‌رو شود.
        """
        from signals.validity import Freshness

        assert check(minutes_ago=35).freshness is Freshness.AGING

    def test_a_late_signal_is_burned(self) -> None:
        """پس از پنجرهٔ ورود، سیگنال «سوخته» است — اصطلاح خود کاربر."""
        from signals.validity import Freshness

        window = check(minutes_ago=50)

        assert window.freshness is Freshness.STALE
        assert window.is_burned

    def test_expiry_follows_the_timeframe(self) -> None:
        """
        سیگنال ۱۵ دقیقه‌ای و سیگنال روزانه یک سرعت کهنه‌شدن ندارند.

        مهلت ثابت ساعتی برای یکی خیلی کوتاه و برای دیگری بی‌معنا
        می‌شد؛ مهلت بر پایهٔ تعداد کندل حساب می‌شود.
        """
        from signals.validity import Freshness

        # سه ساعت بعد: برای ۱۵ دقیقه‌ای منقضی، برای روزانه هنوز تازه
        assert check(minutes_ago=180).freshness is Freshness.EXPIRED
        assert check(minutes_ago=180, timeframes=["1d"]).freshness is Freshness.FRESH

    def test_the_fastest_timeframe_sets_the_pace(self) -> None:
        """
        در تحلیل چند تایم‌فریمی، کوچک‌ترین تایم‌فریم ملاک است.

        سیگنالی که به کندل ۱۵ دقیقه‌ای نگاه می‌کند با همان سرعت هم
        کهنه می‌شود، حتی اگر تصویر کلان روزانه باشد. انتخاب تایم‌فریم
        بزرگ‌تر یعنی به کاربر دروغ بگوییم سیگنال هنوز معتبر است.
        """
        from signals.validity import primary_timeframe

        assert primary_timeframe(["1d", "4h", "1h", "15m"]) == "15m"

    def test_a_stop_hit_invalidates_immediately(self) -> None:
        """
        رد شدن از حد ضرر مهم‌تر از هر سنجش دیگری است.

        سیگنالی که حد ضررش خورده، دیگر مهم نیست چقدر تازه است.
        """
        from signals.validity import Freshness

        window = check(minutes_ago=1, price=58700.0)

        assert window.freshness is Freshness.INVALIDATED

    def test_wait_signals_have_no_entry_deadline(self) -> None:
        """سیگنال انتظار ورودی ندارد که مهلتش تمام شود."""
        from signals.validity import Freshness

        window = check(minutes_ago=30, direction="WAIT")

        assert window.freshness is Freshness.FRESH


class TestBurnedByPriceMovement:
    """
    مهم‌ترین بخش: سیگنال تازه هم می‌تواند سوخته باشد.

    این دقیقاً همان چیزی است که کاربر تجربه کرد ولی نمی‌توانست ببیند.
    """

    def test_a_consumed_move_burns_a_brand_new_signal(self) -> None:
        """
        اگر قیمت پیش از ورود بیشتر مسیر را رفته باشد، معامله دیگر
        ارزش ریسکش را ندارد — حتی اگر سیگنال دو دقیقه پیش ساخته شده
        باشد.
        """
        from signals.validity import Freshness

        window = check(minutes_ago=2, price=61200.0)

        assert window.freshness is Freshness.STALE
        assert window.move_consumed_percent > 35

    def test_effective_risk_reward_collapses(self) -> None:
        """
        عددی که کاربر باید ببیند: نسبت ریسک به ریوارد در قیمت **فعلی**.

        سیگنالی که روی تابلو ۱٫۵ نشان می‌دهد، ممکن است با ورود دیرهنگام
        عملاً زیر ۰٫۵ باشد — یعنی دو برابر ریسک برای یک واحد سود.
        """
        fresh = check(minutes_ago=1, price=60100.0)
        late = check(minutes_ago=1, price=61200.0)

        assert fresh.effective_risk_reward > late.effective_risk_reward
        assert late.effective_risk_reward < 1.0

    def test_reaching_the_first_target_burns_it(self) -> None:
        """وقتی هدف اول خورده، فرصت ورود گذشته است."""
        from signals.validity import Freshness

        window = check(minutes_ago=1, price=62100.0)

        assert window.freshness is Freshness.STALE
        assert window.reason_key == "validity.target_reached"

    def test_an_adverse_move_raises_a_warning(self) -> None:
        """
        حرکت خلاف جهت، پیش از خوردن حد ضرر، هشدار است نه ابطال.

        سیگنال هنوز زنده است ولی کاربر باید بداند در حال بدتر شدن است.
        """
        from signals.validity import Freshness

        # بیش از نیمهٔ راه تا حد ضرر رفته، ولی هنوز آن را رد نکرده
        window = check(minutes_ago=1, price=59300.0)

        assert window.freshness is Freshness.AGING
        assert window.reason_key == "validity.adverse_move"

    def test_without_a_price_only_time_is_judged(self) -> None:
        """
        نبود قیمت لحظه‌ای نباید سنجش را از کار بیندازد.

        در این حالت فقط زمان سنجیده می‌شود — کمتر دقیق ولی درست.
        """
        from signals.validity import Freshness

        assert check(minutes_ago=2, price=None).freshness is Freshness.FRESH
        assert check(minutes_ago=50, price=None).freshness is Freshness.STALE


class TestValidityOnTheSignalItself:
    """پنجرهٔ اعتبار باید بخشی از خود سیگنال باشد، نه افزودنی بعدی."""

    def test_the_trading_signal_carries_its_deadlines(self) -> None:
        """
        سیگنالی بدون تاریخ مصرف به کاربر می‌گوید «همیشه معتبر است» که
        هرگز درست نیست.
        """
        from app.core.models import TradingSignal

        signal = TradingSignal(symbol="BTC/USDT", exchange="lbank", direction=None)  # type: ignore[arg-type]

        assert hasattr(signal, "enter_before")
        assert hasattr(signal, "expires_at")
        assert hasattr(signal, "primary_timeframe")

    def test_the_deadlines_are_serialised(self) -> None:
        """بدون سریال‌سازی، اعتبار پس از ذخیره گم می‌شود."""
        from app.core.constants import SignalDirection
        from app.core.models import TradingSignal

        signal = TradingSignal(
            symbol="BTC/USDT", exchange="lbank", direction=SignalDirection.LONG
        )
        signal.enter_before = NOW
        signal.expires_at = NOW + timedelta(hours=3)
        signal.primary_timeframe = "15m"

        payload = signal.to_dict()

        assert payload["enter_before"] == NOW.isoformat()
        assert payload["primary_timeframe"] == "15m"


# ---------------------------------------------------------------------------
# ۴) بازبینی هوش مصنوعی روی سابقه
# ---------------------------------------------------------------------------


class TestSignalReviewer:
    """سابقهٔ سیگنال باید تحلیل هوش مصنوعی داشته باشد — خواستهٔ کاربر."""

    @staticmethod
    def _signal():
        """سیگنال نمونه."""
        from types import SimpleNamespace

        return SimpleNamespace(
            id=1,
            symbol="BTC/USDT",
            direction="LONG",
            take_profits=[62000.0, 63000.0],
            reason="RSI 61 with a positive MACD histogram.",
            created_at=NOW - timedelta(hours=3),
        )

    @staticmethod
    def _outcome(status: str = "STOP"):
        """نتیجهٔ نمونه."""
        from types import SimpleNamespace

        return SimpleNamespace(
            status=status,
            entry_price=60100.0,
            stop_loss=58800.0,
            confidence=78,
            primary_timeframe="15m",
            result_percent=-2.16,
            realized_r=-1.0,
            max_favorable_percent=0.4,
            max_adverse_percent=2.16,
            closed_at=NOW,
        )

    @staticmethod
    def _providers(content: str):
        """ارائه‌دهندهٔ ساختگی با پاسخ دلخواه."""

        class FakeProviders:
            async def generate(self, messages, **kwargs):  # noqa: ANN001, ANN202, ARG002
                from types import SimpleNamespace

                return SimpleNamespace(
                    content=content, provider="ollama", model="deepseek-r1:8b"
                )

        return FakeProviders()

    def _reviewer(self, content: str):
        """بازبین با ارائه‌دهندهٔ ساختگی."""
        from ai.agent.reviewer import SignalReviewer
        from ai.prompts import PromptManager

        return SignalReviewer(self._providers(content), PromptManager())

    @pytest.mark.asyncio
    async def test_a_closed_signal_is_reviewed(self) -> None:
        """بازبینی باید متن، جمع‌بندی و دستهٔ درس بدهد."""
        reviewer = self._reviewer(
            '{"verdict":"مستقیم به حد ضرر رفت.","lesson":"BAD_TIMING","review":"توضیح."}'
        )

        result = await reviewer.review(self._signal(), self._outcome())

        assert result.ok
        assert result.lesson == "BAD_TIMING"
        assert result.verdict

    @pytest.mark.asyncio
    async def test_the_think_block_does_not_break_the_review(self) -> None:
        """
        مدل محلی کاربر استدلالی است.

        بدون پاک‌سازی، هر بازبینی با «مدل JSON معتبر نداد» شکست
        می‌خورد.
        """
        reviewer = self._reviewer(
            '<think>Let me analyse this trade...</think>'
            '{"verdict":"v","lesson":"GOOD_SETUP","review":"r"}'
        )

        result = await reviewer.review(self._signal(), self._outcome())

        assert result.ok
        assert result.lesson == "GOOD_SETUP"

    @pytest.mark.asyncio
    async def test_an_open_signal_is_not_reviewed(self) -> None:
        """
        بازبینی یعنی قضاوت گذشته، نه پیش‌بینی.

        سیگنال باز نتیجه‌ای ندارد که از آن درسی گرفته شود.
        """
        reviewer = self._reviewer("{}")

        result = await reviewer.review(self._signal(), self._outcome("PENDING"))

        assert not result.ok
        assert "not closed" in result.error

    @pytest.mark.asyncio
    async def test_a_missing_model_is_not_a_crash(self) -> None:
        """
        نبود هوش مصنوعی یک حالت کاملاً پشتیبانی‌شده است.

        بازبینی در پس‌زمینه اجرا می‌شود و شکستش نباید هیچ چیز را
        متوقف کند.
        """
        from ai.agent.reviewer import SignalReviewer
        from ai.prompts import PromptManager

        class BrokenProviders:
            async def generate(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202, ARG002
                raise RuntimeError("no provider")

        reviewer = SignalReviewer(BrokenProviders(), PromptManager())

        result = await reviewer.review(self._signal(), self._outcome())

        assert not result.ok
        assert result.error

    @pytest.mark.asyncio
    async def test_the_review_prompt_is_small(self) -> None:
        """
        بازبینی باید روی مدل محلی هم اجرا شود.

        پرامپت تحلیل ۱۷ کیلوبایت است و روی ماشین کاربر جا نمی‌شود؛
        بازبینی فقط چند عدد لازم دارد، پس باید یک مرتبه کوچک‌تر بماند.
        """
        reviewer = self._reviewer("{}")

        prompt = reviewer.build_prompt(self._signal(), self._outcome())

        assert len(prompt) < 5000

    @pytest.mark.asyncio
    async def test_the_prompt_includes_the_real_numbers(self) -> None:
        """
        مدل باید واقعیت را ببیند وگرنه بازبینی‌اش حدس است.

        بیشترین سود شناور مهم‌ترین عدد است: اگر بالا باشد ولی نتیجه
        منفی، یعنی هدف خیلی دور بود نه اینکه ایده غلط بود.
        """
        reviewer = self._reviewer("{}")

        prompt = reviewer.build_prompt(self._signal(), self._outcome())

        assert "0.40" in prompt  # max_favorable
        assert "-2.16" in prompt  # result
        assert "78" in prompt  # confidence

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("GOOD_SETUP", "GOOD_SETUP"),
            ("late-entry", "LATE_ENTRY"),
            ("stop too tight", "STOP_TOO_TIGHT"),
            ("چیز عجیب", "NOISE"),
            ("", "NOISE"),
            ("x", "NOISE"),
        ],
    )
    def test_lesson_labels_are_normalised(self, raw: str, expected: str) -> None:
        """
        مدل‌های کوچک برچسب را دقیقاً مثل خواسته برنمی‌گردانند.

        بدون نگاشت، صفحهٔ آمار پر از دسته‌های تک‌عضوی می‌شود و هیچ
        الگویی دیده نمی‌شود.
        """
        from ai.agent.reviewer import normalize_lesson

        assert normalize_lesson(raw) == expected


class TestReviewRepository:
    """بازبینی باید ذخیره و بازیابی شود."""

    @pytest.fixture()
    def repository(self, database):  # noqa: ANN001, ANN201
        """مخزن روی پایگاه دادهٔ موقت."""
        from app.database.repositories import SignalReviewRepository

        return SignalReviewRepository(database)

    @pytest.fixture()
    def signal_id(self, database) -> int:  # noqa: ANN001
        """یک سیگنال واقعی در پایگاه داده."""
        from app.database.models import SignalRecord

        with database.session_scope() as session:
            record = SignalRecord(
                symbol="BTC/USDT", exchange="lbank", direction="LONG", confidence=70
            )
            session.add(record)
            session.flush()
            return int(record.id)

    def test_a_review_is_saved_and_read_back(self, repository, signal_id) -> None:  # noqa: ANN001
        """پایه‌ای‌ترین رفتار."""
        repository.save(
            signal_id,
            outcome_status="STOP",
            verdict="v",
            lesson="LATE_ENTRY",
            review_text="متن کامل",
            ai_provider="ollama",
        )

        found = repository.for_signal(signal_id)

        assert found is not None
        assert found.lesson == "LATE_ENTRY"
        assert found.review_text == "متن کامل"

    def test_re_reviewing_replaces_instead_of_duplicating(
        self, repository, signal_id
    ) -> None:  # noqa: ANN001
        """
        هر سیگنال فقط یک بازبینی دارد.

        وگرنه کاربر با چند درس متناقض روی یک معامله روبه‌رو می‌شود.
        """
        repository.save(signal_id, outcome_status="STOP", verdict="a", lesson="NOISE", review_text="۱")
        repository.save(
            signal_id, outcome_status="STOP", verdict="b", lesson="GOOD_SETUP", review_text="۲"
        )

        assert repository.for_signal(signal_id).lesson == "GOOD_SETUP"
        assert len(repository.reviewed_ids()) == 1

    def test_lesson_counts_answer_the_users_question(
        self, repository, database
    ) -> None:  # noqa: ANN001
        """
        «چرا سیگنال‌ها سودی نمی‌دهند؟»

        اگر بیشتر درس‌ها `LATE_ENTRY` باشند، مشکل موتور نیست — سرعت
        واکنش است. این شمارش، تشخیص را ممکن می‌کند.
        """
        from app.database.models import SignalRecord

        with database.session_scope() as session:
            ids = []
            for _ in range(3):
                record = SignalRecord(symbol="X/USDT", exchange="l", direction="LONG")
                session.add(record)
                session.flush()
                ids.append(int(record.id))

        for index, identifier in enumerate(ids):
            repository.save(
                identifier,
                outcome_status="STOP",
                verdict="v",
                lesson="LATE_ENTRY" if index < 2 else "GOOD_SETUP",
                review_text="r",
            )

        counts = repository.lesson_counts()

        assert counts["LATE_ENTRY"] == 2
        assert counts["GOOD_SETUP"] == 1


# ---------------------------------------------------------------------------
# ۵) نمایش در رابط کاربری
# ---------------------------------------------------------------------------


class TestValidityInTheInterface:
    """اطلاعات درست در جای غلط، به اندازهٔ اطلاعات غلط بی‌فایده است."""

    def test_unknown_freshness_is_treated_as_expired(self) -> None:
        """
        محافظه‌کاری عمدی.

        اگر نمی‌دانیم سیگنال تازه است یا نه، نباید با رنگ سبز به کاربر
        بگوییم تازه است.
        """
        from ui.signal_grading import freshness_grade

        assert freshness_grade("").key == "expired"
        assert freshness_grade(None).key == "expired"

    def test_burned_and_fresh_look_different(self) -> None:
        """در نگاه اول باید از هم جدا باشند، وگرنه ستون بی‌فایده است."""
        from ui.signal_grading import freshness_grade

        fresh = freshness_grade("FRESH")
        stale = freshness_grade("STALE")

        assert fresh.token != stale.token
        assert fresh.mark != stale.mark

    @pytest.mark.parametrize("freshness", ["STALE", "EXPIRED", "INVALIDATED"])
    def test_the_trade_button_is_disabled_on_burned_signals(
        self, qt_application, freshness: str
    ) -> None:  # noqa: ANN001, ARG002
        """
        هشدار بدون جلوگیری، تشریفات است.

        یکی از راه‌هایی که کاربر به سیگنال بی‌سود می‌رسید همین بود:
        ورود به موقعیتی که فرصتش گذشته.
        """
        from localization import Translator
        from ui.dialogs.signal_detail_dialog import SignalDetailDialog

        dialog = SignalDetailDialog(
            {"symbol": "SOL/USDT", "direction": "LONG", "freshness": freshness},
            Translator("fa"),
        )

        assert not dialog.trade_button.isEnabled()

    @pytest.mark.parametrize("freshness", ["FRESH", "AGING"])
    def test_the_trade_button_stays_enabled_when_usable(
        self, qt_application, freshness: str
    ) -> None:  # noqa: ANN001, ARG002
        """سیگنال زنده نباید بی‌دلیل مسدود شود."""
        from localization import Translator
        from ui.dialogs.signal_detail_dialog import SignalDetailDialog

        dialog = SignalDetailDialog(
            {"symbol": "SOL/USDT", "direction": "LONG", "freshness": freshness},
            Translator("fa"),
        )

        assert dialog.trade_button.isEnabled()

    def test_both_signal_tables_have_a_validity_column(
        self, qt_application
    ) -> None:  # noqa: ANN001, ARG002
        """
        هم جدول پویش و هم سابقه باید اعتبار را نشان بدهند.

        کاربر از هر دو مسیر به سیگنال می‌رسد.
        """
        from localization import Translator
        from ui.pages.signals_page import SignalsPage

        page = SignalsPage(Translator("fa"))

        assert page.scan_table.columnCount() > SignalsPage.SCAN_COL_FRESHNESS
        assert page.history_table.columnCount() > SignalsPage.HISTORY_COL_FRESHNESS

    def test_translations_exist_in_both_languages(self) -> None:
        """قاعدهٔ پروژه: هیچ رشتهٔ سخت‌کدشده‌ای در رابط کاربری نیست."""
        from localization import Translator

        keys = [
            "validity.fresh_label",
            "validity.stale_label",
            "validity.not_enterable_warning",
            "validity.column",
            "review.title",
            "review.lesson.LATE_ENTRY",
            "review.lesson.GOOD_SETUP",
        ]
        for language in ("fa", "en"):
            translator = Translator(language)
            for key in keys:
                assert translator.tr(key) != key, f"{language}: {key}"


# ---------------------------------------------------------------------------
# ۶) تنظیمات تازه
# ---------------------------------------------------------------------------


class TestNewSettings:
    """هر رفتار تازه باید قابل خاموش‌کردن باشد."""

    def test_the_new_keys_have_defaults(self) -> None:
        """کلید بدون پیش‌فرض، در اولین خواندن خطا می‌دهد."""
        from app.config.defaults import DEFAULT_SETTINGS, SettingKey

        for key in (
            SettingKey.AI_OLLAMA_MAX_CONTEXT,
            SettingKey.AI_AUTO_REVIEW,
            SettingKey.SIGNAL_HIDE_STALE,
        ):
            assert key.value in DEFAULT_SETTINGS

    def test_stale_signals_are_labelled_not_hidden_by_default(self) -> None:
        """
        پنهان‌کردن پیش‌فرضی، اطلاعات را از کاربر دریغ می‌کند.

        او باید ببیند سیگنالی بود و سوخت، نه اینکه ردیف بی‌صدا ناپدید
        شود.
        """
        from app.config.defaults import DEFAULT_SETTINGS, SettingKey

        assert DEFAULT_SETTINGS[SettingKey.SIGNAL_HIDE_STALE.value] is False

    def test_context_override_is_off_by_default(self) -> None:
        """صفر یعنی «از حافظهٔ دستگاه خودت تشخیص بده»."""
        from app.config.defaults import DEFAULT_SETTINGS, SettingKey

        assert DEFAULT_SETTINGS[SettingKey.AI_OLLAMA_MAX_CONTEXT.value] == 0


# ---------------------------------------------------------------------------
# ۷) توصیهٔ صریح خرید/فروش
# ---------------------------------------------------------------------------


class TestExplicitRecommendation:
    """
    «هوش مصنوعی باید پیشنهاد خرید و فروش بدهد.»

    تحلیل متنی هرچقدر دقیق، این خواسته را برآورده نمی‌کند: کاربر نباید
    مجبور باشد چهار پاراگراف بخواند تا بفهمد جواب «بخر» است یا «نخر».
    """

    def test_a_plain_recommendation_line_is_read(self) -> None:
        """حالت پایه."""
        from ai.recommendation import parse_recommendation

        result = parse_recommendation("تحلیل...\n\nRECOMMENDATION: BUY | 72 | RSI در ۶۱")

        assert result is not None
        assert result.action == "BUY"
        assert result.confidence == 72
        assert result.is_actionable

    def test_markdown_bold_does_not_break_it(self) -> None:
        """
        مدل‌ها دستور را رعایت می‌کنند ولی مارک‌داون هم اضافه می‌کنند.

        شکست روی `**RECOMMENDATION:**` یعنی از دست دادن توصیه‌ای که
        مدل درست تولید کرده بود.
        """
        from ai.recommendation import parse_recommendation

        result = parse_recommendation("x\n**RECOMMENDATION:** SELL | 55 | شکست حمایت")

        assert result is not None
        assert result.action == "SELL"

    @pytest.mark.parametrize(
        ("word", "expected"),
        [
            ("LONG", "BUY"),
            ("BULLISH", "BUY"),
            ("خرید", "BUY"),
            ("SHORT", "SELL"),
            ("BEARISH", "SELL"),
            ("HOLD", "WAIT"),
            ("NO TRADE", "WAIT"),
            ("صبر", "WAIT"),
        ],
    )
    def test_synonyms_are_understood(self, word: str, expected: str) -> None:
        """
        مدل‌های کوچک واژهٔ آشنای خودشان را می‌نویسند.

        این فهرست از خروجی واقعی مدل‌ها ساخته شده، نه از حدس.
        """
        from ai.recommendation import normalize_action

        assert normalize_action(word) == expected

    @pytest.mark.parametrize(("raw", "expected"), [("72", 72), ("72%", 72), ("0.72", 72)])
    def test_confidence_formats(self, raw: str, expected: int) -> None:
        """درصد و کسر، هر دو یک معنا دارند."""
        from ai.recommendation import parse_recommendation

        result = parse_recommendation(f"x\nRECOMMENDATION: BUY | {raw} | y")

        assert result is not None
        assert result.confidence == expected

    def test_a_missing_confidence_is_none_not_zero(self) -> None:
        """
        صفر یعنی «هیچ اطمینانی ندارم» که با «عددی ندادم» فرق دارد.

        نمایش «اطمینان ۰٪» برای مدلی که فقط عدد را جا انداخته، دروغ
        است.
        """
        from ai.recommendation import parse_recommendation

        result = parse_recommendation("x\nRECOMMENDATION: WAIT")

        assert result is not None
        assert result.confidence is None

    def test_the_last_line_wins(self) -> None:
        """
        مدل استدلالی گاهی وسط متن نمونه می‌نویسد.

        تصمیم نهایی همیشه آخرین چیزی است که می‌گوید.
        """
        from ai.recommendation import parse_recommendation

        result = parse_recommendation(
            "RECOMMENDATION: BUY | 50 | اول\nمتن\nRECOMMENDATION: SELL | 90 | آخر"
        )

        assert result is not None
        assert result.action == "SELL"
        assert result.confidence == 90

    def test_no_line_means_no_guessing(self) -> None:
        """
        مهم‌ترین آزمون این بخش.

        وسوسه‌انگیز است که از متن «به نظر صعودی می‌آید» جهت استخراج
        کنیم. دقیقاً همین کار سیگنال بی‌اعتماد می‌سازد: خروجی معتبر
        به نظر می‌رسد ولی مدل هرگز آن تصمیم را نگرفته بود.
        """
        from ai.recommendation import parse_recommendation

        assert parse_recommendation("بازار صعودی به نظر می‌رسد و روند مثبت است.") is None
        assert parse_recommendation("") is None

    def test_an_unrecognised_action_is_rejected(self) -> None:
        """برچسب نامفهوم یعنی توصیه‌ای نیست، نه اینکه پیش‌فرض بگذاریم."""
        from ai.recommendation import parse_recommendation

        assert parse_recommendation("x\nRECOMMENDATION: MAYBE | 50 | y") is None

    def test_wait_is_not_actionable(self) -> None:
        """
        انتظار یک تصمیم معتبر است، ولی معامله نیست.

        قاعدهٔ پروژه: WAIT شهروند درجه‌یک است.
        """
        from ai.recommendation import parse_recommendation

        result = parse_recommendation("x\nRECOMMENDATION: WAIT | 40 | تایم‌فریم‌ها متناقض‌اند")

        assert result is not None
        assert not result.is_actionable

    def test_the_machine_line_is_hidden_from_the_user(self) -> None:
        """
        آن خط برای برنامه است، نه برای کاربر.

        کاربر همان اطلاعات را در کارت توصیه با قالب درست می‌بیند؛
        نمایش هر دو تکرار است.
        """
        from ai.recommendation import strip_recommendation_line

        cleaned = strip_recommendation_line("تحلیل کامل.\n\nRECOMMENDATION: BUY | 72 | دلیل")

        assert "RECOMMENDATION" not in cleaned
        assert cleaned == "تحلیل کامل."

    def test_the_prompt_demands_the_line(self) -> None:
        """بدون درخواست صریح در قالب، هیچ مدلی آن خط را نمی‌نویسد."""
        from ai.prompts import PromptManager

        content = PromptManager().get("technical_analysis").content

        assert "RECOMMENDATION:" in content
        assert "BUY" in content and "SELL" in content

    def test_the_prompt_permits_wait(self) -> None:
        """
        مدلی که مجبور به انتخاب جهت شود، جهت اختراع می‌کند.

        این یکی از ریشه‌های سیگنال بی‌سود است.
        """
        from ai.prompts import PromptManager

        assert "WAIT is a valid" in PromptManager().get("technical_analysis").content


class TestRecommendationInTheDialog:
    """توصیه باید دیده شود، و وقتی کهنه شد باید کهنه به نظر برسد."""

    @staticmethod
    def _dialog(**overrides):
        """پنجرهٔ جزئیات با داده‌های دلخواه."""
        from localization import Translator
        from ui.dialogs.signal_detail_dialog import SignalDetailDialog

        payload = {"symbol": "SOL/USDT", "direction": "LONG", **overrides}
        return SignalDetailDialog(payload, Translator("fa"))

    def test_the_card_appears_when_a_recommendation_exists(
        self, qt_application
    ) -> None:  # noqa: ANN001, ARG002
        """پایه‌ای‌ترین رفتار."""
        dialog = self._dialog(
            recommendation={"action": "BUY", "confidence": 72, "rationale": "دلیل"}
        )

        assert dialog._build_recommendation() is not None

    def test_no_card_without_a_recommendation(self, qt_application) -> None:  # noqa: ANN001, ARG002
        """
        کارت خالی بدتر از نبود کارت است.

        جای خالی صادقانه‌تر از قاب تزئینی بدون محتواست.
        """
        assert self._dialog()._build_recommendation() is None
        assert self._dialog(recommendation={})._build_recommendation() is None
        assert self._dialog(recommendation={"action": ""})._build_recommendation() is None

    def test_a_burned_signal_strikes_through_its_recommendation(
        self, qt_application
    ) -> None:  # noqa: ANN001, ARG002
        """
        تناقضی که باید حل می‌شد.

        توصیهٔ «خرید» با رنگ سبز پررنگ، درست بالای کارتی که می‌گوید
        «سوخته»، کاربر را به همان معاملهٔ بی‌سودی می‌کشاند که از آن
        شکایت داشت.
        """
        card = self._dialog(
            recommendation={"action": "BUY", "confidence": 72}, freshness="STALE"
        )._build_recommendation()

        assert any("line-through" in label.styleSheet() for label in card.findChildren(QLabel))

    def test_a_fresh_signal_keeps_its_recommendation_bold(
        self, qt_application
    ) -> None:  # noqa: ANN001, ARG002
        """توصیهٔ زنده نباید بی‌دلیل کم‌رنگ شود."""
        card = self._dialog(
            recommendation={"action": "BUY", "confidence": 72}, freshness="FRESH"
        )._build_recommendation()

        assert not any("line-through" in label.styleSheet() for label in card.findChildren(QLabel))

    def test_translations_exist(self) -> None:
        """قاعدهٔ پروژه: هیچ رشتهٔ سخت‌کدشده‌ای نیست."""
        from localization import Translator

        for language in ("fa", "en"):
            translator = Translator(language)
            for key in (
                "recommendation.title",
                "recommendation.action_buy",
                "recommendation.action_sell",
                "recommendation.action_wait",
                "recommendation.superseded",
            ):
                assert translator.tr(key) != key, f"{language}: {key}"


class TestAnalystWiring:
    """استخراج باید در مسیر واقعی تحلیل هم کار کند، نه فقط جداگانه."""

    def test_the_result_carries_a_recommendation_field(self) -> None:
        """بدون این فیلد، توصیه هرگز به رابط کاربری نمی‌رسد."""
        from ai.agent.analyst import AnalysisResult
        from app.core.constants import AnalysisStatus

        result = AnalysisResult(symbol="BTC/USDT", status=AnalysisStatus.OK)

        assert result.recommendation is None
        assert "recommendation" in result.to_dict()
