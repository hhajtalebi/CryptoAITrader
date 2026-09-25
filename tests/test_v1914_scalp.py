"""
آزمون‌های اسکلپ و معاملهٔ خودکار (۱٫۹٫۱۴).

دو موضوع حساس اینجا آزموده می‌شود:

۱. **پویشگر نباید تلهٔ نقدینگی پیشنهاد دهد.** روی دادهٔ زنده دیدیم که
   بیشترین نوسان‌گرها حجمی در حد چند دلار در روز دارند. وارد شدن ممکن
   است، خارج شدن نه.

۲. **معاملهٔ واقعی نباید تصادفی روشن شود.** سه گام جدا لازم است و هیچ
   کدام نباید با یک کلیک اشتباه رخ دهد.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from app.core.models import Candle, OrderBook, OrderBookLevel, Ticker
from trading.auto_trader import (
    HARD_MAX_CONCURRENT,
    HARD_MAX_LEVERAGE,
    LIVE_CONFIRMATION_PHRASE,
    AutoTradeConfig,
    AutoTrader,
    LiveOrderGateway,
    LiveTradingNotEnabledError,
    ManagedTrade,
)
from trading.scalp_scanner import (
    ROUND_TRIP_FEE_PERCENT,
    ScalpCandidate,
    feasibility_note,
    momentum_percent,
    passes_liquidity,
    prefilter_symbols,
    rank_candidates,
    recent_volatility,
    score_candidate,
    spread_from_orderbook,
)


def make_ticker(symbol: str, price: float = 100.0, turnover: float = 5_000_000.0,
                change: float = 2.0) -> Ticker:
    """یک تیکر نمونه."""
    return Ticker(
        symbol=symbol, last_price=price, high_24h=price * 1.05,
        low_24h=price * 0.95, volume_24h=turnover / price,
        turnover_24h=turnover, change_percent=change,
        timestamp=int(datetime.now(UTC).timestamp()),
    )


def make_candles(count: int = 60, base: float = 100.0, swing: float = 0.5,
                 drift: float = 0.0) -> list[Candle]:
    """کندل‌های نمونه با دامنه و روند مشخص."""
    candles = []
    now = int(datetime.now(UTC).timestamp())
    price = base
    for index in range(count):
        price *= 1 + drift / 100.0
        candles.append(
            Candle(
                timestamp=now - 300 * (count - index),
                open=price, high=price * (1 + swing / 100.0),
                low=price * (1 - swing / 100.0), close=price, volume=1000.0,
            )
        )
    return candles


def make_book(bid: float, ask: float) -> OrderBook:
    """دفتر سفارش نمونه."""
    return OrderBook(
        symbol="X/USDT",
        bids=[OrderBookLevel(price=bid, quantity=10.0)],
        asks=[OrderBookLevel(price=ask, quantity=10.0)],
        timestamp=int(datetime.now(UTC).timestamp()),
    )


class TestLiquidityIsTheHardFilter:
    """
    مهم‌ترین محافظ پویشگر.

    روی دادهٔ واقعی، بیشترین نوسان‌گرها این‌ها بودند:
        EXBT/USDT  +315%  حجم ۲۴ ساعته: ۶۷ دلار
        MYTH/USDT   -59%  حجم ۲۴ ساعته:  ۴ دلار
    این‌ها فرصت نیستند؛ تله‌اند.
    """

    def test_a_high_volatility_ghost_coin_is_rejected(self) -> None:
        """نوسان ۳۱۵ درصدی با حجم ۶۷ دلار باید رد شود."""
        ghost = make_ticker("EXBT/USDT", turnover=67.0, change=315.0)

        assert passes_liquidity(ghost) is False

    def test_a_four_dollar_market_is_rejected(self) -> None:
        """حجم چهار دلار در روز یعنی خروج غیرممکن."""
        assert passes_liquidity(make_ticker("MYTH/USDT", turnover=4.0)) is False

    def test_a_liquid_pair_passes(self) -> None:
        """نماد سالم نباید قربانی فیلتر شود."""
        assert passes_liquidity(make_ticker("BTC/USDT", turnover=50_000_000.0)) is True

    def test_prefilter_removes_the_traps_before_any_candle_fetch(self) -> None:
        """
        فیلتر باید **پیش از** گرفتن کندل اعمال شود.

        هم برای سرعت و هم برای اینکه صرافی ما را محدود نکند.
        """
        tickers = [
            make_ticker("TRAP/USDT", turnover=50.0, change=400.0),
            make_ticker("GOOD/USDT", turnover=8_000_000.0, change=3.0),
            make_ticker("ALSOTRAP/USDT", turnover=900.0, change=120.0),
        ]

        survivors = prefilter_symbols(tickers, min_turnover=2_000_000)

        assert [t.symbol for t in survivors] == ["GOOD/USDT"]

    def test_non_quote_pairs_are_excluded(self) -> None:
        """فقط جفت‌های USDT برای اسکلپ در نظر گرفته می‌شوند."""
        tickers = [
            make_ticker("ETH/BTC", turnover=9_000_000.0),
            make_ticker("ETH/USDT", turnover=9_000_000.0),
        ]

        survivors = prefilter_symbols(tickers, quote="USDT")

        assert [t.symbol for t in survivors] == ["ETH/USDT"]


class TestSpreadComesFromTheOrderBook:
    """
    اسپرد باید از دفتر سفارش بیاید، نه از تخمین.

    تخمین قبلی (بر پایهٔ دامنهٔ ۲۴ ساعته) روی دادهٔ زنده تا **۱۱ برابر**
    خطا داشت و یک نماد با اسپرد واقعی ۱۱٫۸٪ را سالم نشان می‌داد.
    """

    def test_a_tight_book_gives_a_tiny_spread(self) -> None:
        """جفت نقدشونده اسپرد بسیار کم دارد."""
        spread = spread_from_orderbook(make_book(bid=99.99, ask=100.01))

        assert spread == pytest.approx(0.02, abs=0.005)

    def test_a_wide_book_is_detected(self) -> None:
        """
        اسپرد ۱۱٫۸ درصدی باید دیده شود.

        این دقیقاً همان حالتی است که تخمین قدیمی از دست می‌داد.
        """
        spread = spread_from_orderbook(make_book(bid=94.0, ask=106.0))

        assert spread > 10.0

    def test_an_empty_book_is_treated_as_worst_case(self) -> None:
        """دفتر خالی یعنی نقدینگی نیست — نه اینکه اسپرد صفر است."""
        empty = OrderBook(
            symbol="X/USDT", bids=[], asks=[],
            timestamp=int(datetime.now(UTC).timestamp()),
        )

        assert spread_from_orderbook(empty) == 100.0

    def test_a_malformed_book_does_not_crash(self) -> None:
        """دادهٔ خراب نباید پویشگر را بشکند."""
        assert spread_from_orderbook(None) == 100.0

    def test_a_wide_spread_blocks_the_candidate(self) -> None:
        """نمادی با اسپرد پهن نباید پیشنهاد شود."""
        result = score_candidate(
            make_ticker("OAI/USDT"), make_candles(swing=1.0), spread=11.8
        )

        assert result is None


class TestScoringHonesty:
    """امتیازدهی باید هزینه‌های واقعی را حساب کند."""

    def test_a_calm_market_produces_nothing(self) -> None:
        """
        بازار آرام یعنی فرصتی نیست.

        این «شکست» نیست؛ مثل «منتظر» در موتور اصلی، یک نتیجهٔ درست است.
        """
        assert score_candidate(
            make_ticker("QUIET/USDT"), make_candles(swing=0.01), spread=0.02
        ) is None

    def test_a_chaotic_market_is_rejected(self) -> None:
        """نوسان بیش از حد یعنی حد ضرر بی‌معنا می‌شود."""
        assert score_candidate(
            make_ticker("WILD/USDT"), make_candles(swing=8.0), spread=0.02
        ) is None

    def test_fees_and_spread_are_subtracted_from_the_profit(self) -> None:
        """
        سود نمایش‌داده‌شده باید **خالص** باشد.

        نمایش سود ناخالص عددی می‌دهد که کاربر هرگز نمی‌بیند.
        """
        candidate = score_candidate(
            make_ticker("OK/USDT"), make_candles(swing=1.0, drift=0.05), spread=0.10
        )

        assert candidate is not None
        gross = candidate.volatility_5m * 0.6
        assert candidate.expected_net_percent < gross
        assert candidate.expected_net_percent == pytest.approx(
            gross - ROUND_TRIP_FEE_PERCENT - 0.10, abs=1e-4
        )

    def test_a_candidate_that_cannot_beat_fees_is_dropped(self) -> None:
        """اگر کارمزد سود را ببلعد، معامله از پیش بازنده است."""
        assert score_candidate(
            make_ticker("THIN/USDT"), make_candles(swing=0.2, drift=0.05), spread=0.24
        ) is None

    def test_direction_follows_momentum(self) -> None:
        """جهت باید با حرکت اخیر هم‌سو باشد."""
        up = score_candidate(
            make_ticker("UP/USDT"), make_candles(swing=1.0, drift=0.2), spread=0.02
        )
        down = score_candidate(
            make_ticker("DN/USDT"), make_candles(swing=1.0, drift=-0.2), spread=0.02
        )

        assert up is not None and up.direction == "LONG"
        assert down is not None and down.direction == "SHORT"

    def test_ranking_puts_the_best_first(self) -> None:
        """مرتب‌سازی باید نزولی باشد."""
        items = [
            ScalpCandidate("A", 1, 5.0, "LONG", 1, 1, 1, 1),
            ScalpCandidate("B", 1, 9.0, "LONG", 1, 1, 1, 1),
            ScalpCandidate("C", 1, 7.0, "LONG", 1, 1, 1, 1),
        ]

        assert [c.symbol for c in rank_candidates(items)] == ["B", "C", "A"]

    def test_volatility_of_empty_candles_is_zero(self) -> None:
        """دادهٔ خالی نباید استثنا بدهد."""
        assert recent_volatility([]) == 0.0
        assert momentum_percent([]) == 0.0


class TestTheHonestyCheck:
    """
    مهم‌ترین بخش برای کاربر.

    خواستهٔ «۱۰ دلار بگذار، ۲ دلار سود بگیر» یعنی ۲۰٪. کاربر باید
    **پیش از** ریختن پول بداند این یعنی چه.
    """

    def test_twenty_percent_without_leverage_is_called_unrealistic(self) -> None:
        """۲۰٪ در پنج دقیقه بدون اهرم، خیال است."""
        possible, message = feasibility_note(2.0, 10.0, 1.0, 0.4)

        assert possible is False
        assert "غیرواقع" in message

    def test_the_same_goal_becomes_reachable_with_leverage(self) -> None:
        """با اهرم ۱۰، همان هدف شدنی می‌شود."""
        possible, _ = feasibility_note(2.0, 10.0, 10.0, 0.4)

        assert possible is True

    def test_the_message_names_the_required_move(self) -> None:
        """
        پیام باید عدد دقیق بدهد، نه فقط «نشدنی».

        کاربر باید بفهمد چرا.
        """
        _, message = feasibility_note(3.0, 10.0, 1.0, 0.3)

        assert "٪" in message

    def test_zero_margin_is_handled(self) -> None:
        """تقسیم بر صفر نباید رخ دهد."""
        possible, _ = feasibility_note(2.0, 0.0, 10.0, 0.5)

        assert possible is False

    def test_required_move_includes_fees(self) -> None:
        """حرکت لازم باید کارمزد را هم بپوشاند."""
        candidate = ScalpCandidate("X", 100, 1, "LONG", 0.5, 1e7, 0.02, 0.1)
        needed = candidate.required_move_percent(2.0, 10.0, 10.0)

        assert needed == pytest.approx(2.0 + ROUND_TRIP_FEE_PERCENT, abs=1e-6)


class TestLiveTradingIsHardToTurnOn:
    """
    معاملهٔ واقعی نباید تصادفی روشن شود.

    قانون قدیمی پروژه «فقط کاغذی» بود؛ کاربر آن را با یک کلید تغییر
    داد، نه با برداشتن همهٔ محافظ‌ها.
    """

    def test_the_default_is_paper(self) -> None:
        """پیش‌فرض باید امن باشد."""
        assert AutoTradeConfig().is_live is False

    def test_live_mode_alone_is_not_enough(self) -> None:
        """
        فقط گذاشتن حالت روی `live` کافی نیست.

        عبارت تأیید هم لازم است.
        """
        assert AutoTradeConfig(mode="live").is_live is False

    def test_a_wrong_confirmation_phrase_is_rejected(self) -> None:
        """«بله» یا «yes» کافی نیست."""
        assert AutoTradeConfig(mode="live", live_confirmation="بله").is_live is False
        assert AutoTradeConfig(mode="live", live_confirmation="yes").is_live is False

    def test_the_exact_phrase_enables_live(self) -> None:
        """فقط عبارت دقیق."""
        config = AutoTradeConfig(mode="live", live_confirmation=LIVE_CONFIRMATION_PHRASE)

        assert config.is_live is True

    def test_starting_live_without_confirmation_fails_with_a_clear_message(self) -> None:
        """پیام باید بگوید دقیقاً چه باید تایپ شود."""
        trader = AutoTrader(
            config=AutoTradeConfig(mode="live"),
            price_source=_fixed_price(100.0),
            repository=_FakeRepo(),
        )

        started, message = asyncio.run(trader.start())

        assert started is False
        assert LIVE_CONFIRMATION_PHRASE in message

    def test_the_live_gateway_refuses_instead_of_pretending(self) -> None:
        """
        درگاه واقعی هنوز پیاده نشده و باید **صریح** شکست بخورد.

        مسیر شبه‌واقعی که در سکوت شکست بخورد از نبودش بدتر است: کاربر
        فکر می‌کند معامله باز شده در حالی که نشده.
        """
        gateway = LiveOrderGateway("lbank")

        with pytest.raises(LiveTradingNotEnabledError):
            asyncio.run(gateway.open_position(symbol="BTC/USDT"))


class TestHardCaps:
    """محافظ در برابر یک صفر اضافی هنگام تایپ."""

    def test_leverage_is_capped(self) -> None:
        """عددی بالاتر از سقف سخت باید به همان سقف برگردد."""
        assert AutoTradeConfig(leverage=500).validated().leverage == HARD_MAX_LEVERAGE

    def test_concurrency_is_capped(self) -> None:
        """تعداد معاملهٔ همزمان سقف سخت دارد."""
        config = AutoTradeConfig(max_concurrent=HARD_MAX_CONCURRENT + 50).validated()

        assert config.max_concurrent == HARD_MAX_CONCURRENT

    def test_leverage_never_drops_below_one(self) -> None:
        """اهرم صفر یعنی موقعیت صفر."""
        assert AutoTradeConfig(leverage=0).validated().leverage == 1.0

    def test_a_reckless_target_is_refused_at_preflight(self) -> None:
        """هدف سودی که نسبت به حد ضرر بی‌معناست باید رد شود."""
        trader = AutoTrader(
            config=AutoTradeConfig(target_profit=100.0, max_loss=1.0),
            price_source=_fixed_price(100.0),
            repository=_FakeRepo(),
        )
        ok, message = trader.preflight()

        assert ok is False
        assert message


class TestTradeLifecycle:
    """چرخهٔ کامل: باز شدن، رسیدن به هدف، حد ضرر، مهلت."""

    def test_a_trade_closes_at_the_profit_target(self) -> None:
        """رسیدن به هدف باید معامله را ببندد."""
        trader, repo, price = _trader()
        trade = asyncio.run(trader.open_trade(_Candidate("BTC/USDT")))
        assert trade is not None

        price["value"] = 102.5  # بالاتر از هدف ۲٪
        asyncio.run(trader.check_open_trades())

        assert trader.open_trades == []
        assert repo.rows[trade.trade_id]["status"] == "closed"
        assert trader.realised_today > 0

    def test_a_trade_closes_at_the_stop_loss(self) -> None:
        """حد ضرر باید عمل کند."""
        trader, _repo, price = _trader()
        asyncio.run(trader.open_trade(_Candidate("BTC/USDT")))

        price["value"] = 96.0  # پایین‌تر از حد ضرر ۳٪
        asyncio.run(trader.check_open_trades())

        assert trader.open_trades == []
        assert trader.realised_today < 0

    def test_the_stop_loss_wins_when_both_levels_are_crossed(self) -> None:
        """
        اگر قیمت در یک پرش از هر دو سطح رد شود، باید محافظه‌کارانه‌ترین
        نتیجه ثبت شود، نه خوش‌بینانه‌ترین.
        """
        trade = ManagedTrade(
            trade_id=1, symbol="X", side="long", entry_price=100.0, quantity=1.0,
            leverage=10.0, target_price=102.0, stop_price=97.0,
            opened_at=datetime.now(UTC),
        )

        assert trade.should_close(90.0, datetime.now(UTC), 900) == "stop_loss"

    def test_a_stale_trade_times_out(self) -> None:
        """اسکلپ نباید ساعت‌ها باز بماند."""
        trade = ManagedTrade(
            trade_id=1, symbol="X", side="long", entry_price=100.0, quantity=1.0,
            leverage=10.0, target_price=110.0, stop_price=90.0,
            opened_at=datetime.now(UTC) - timedelta(hours=2),
        )

        assert trade.should_close(100.0, datetime.now(UTC), 900) == "timeout"

    def test_a_short_profits_when_price_falls(self) -> None:
        """در فروش، افت قیمت سود است."""
        trade = ManagedTrade(
            trade_id=1, symbol="X", side="short", entry_price=100.0, quantity=1.0,
            leverage=10.0, target_price=98.0, stop_price=103.0,
            opened_at=datetime.now(UTC),
        )

        assert trade.unrealised(95.0) > 0
        assert trade.should_close(97.0, datetime.now(UTC), 900) == "take_profit"

    def test_concurrency_limit_is_respected(self) -> None:
        """نباید بیش از حد مجاز معامله باز شود."""
        trader, _repo, _price = _trader(max_concurrent=2)
        for symbol in ("A/USDT", "B/USDT", "C/USDT"):
            asyncio.run(trader.open_trade(_Candidate(symbol)))

        assert len(trader.open_trades) == 2

    def test_the_daily_loss_limit_halts_the_engine(self) -> None:
        """
        آخرین خط دفاع در برابر یک روز بد.

        پس از رد شدن از سقف، هیچ معاملهٔ تازه‌ای نباید باز شود.
        """
        trader, _repo, price = _trader(daily_loss_limit=1.0)
        asyncio.run(trader.open_trade(_Candidate("BTC/USDT")))
        price["value"] = 96.0
        asyncio.run(trader.check_open_trades())

        assert trader.realised_today < -1.0
        assert asyncio.run(trader.open_trade(_Candidate("ETH/USDT"))) is None
        assert trader.halted_reason

    def test_stopping_does_not_force_close_open_trades(self) -> None:
        """
        بستن ناگهانی همه با قیمت بازار می‌تواند زیان را قفل کند.

        کاربر خودش تصمیم می‌گیرد.
        """
        trader, _repo, _price = _trader()
        asyncio.run(trader.open_trade(_Candidate("BTC/USDT")))
        asyncio.run(trader.stop())

        assert len(trader.open_trades) == 1

    def test_close_all_closes_everything(self) -> None:
        """بستن دستی باید همه را ببندد."""
        trader, _repo, _price = _trader()
        asyncio.run(trader.open_trade(_Candidate("A/USDT")))
        asyncio.run(trader.open_trade(_Candidate("B/USDT")))

        asyncio.run(trader.close_all())

        assert trader.open_trades == []

    def test_a_listener_error_does_not_break_trading(self) -> None:
        """خطای یک شنونده نباید موتور معاملات را از کار بیندازد."""
        trader, _repo, _price = _trader()
        trader.add_listener(lambda _e, _p: (_ for _ in ()).throw(RuntimeError("boom")))

        assert asyncio.run(trader.open_trade(_Candidate("BTC/USDT"))) is not None


# ---- ابزارهای کمکی ---------------------------------------------------


@dataclass
class _Candidate:
    """نامزد ساختگی."""

    symbol: str
    direction: str = "LONG"
    score: float = 9.0


class _FakeRepo:
    """انبارهٔ ساختگی با همان قرارداد انبارهٔ واقعی."""

    def __init__(self) -> None:
        self.counter = 0
        self.rows: dict[int, dict] = {}

    def open_trade(self, **kwargs):  # noqa: ANN003, ANN201
        self.counter += 1
        row = dict(kwargs)
        row["id"] = self.counter
        row["status"] = "open"
        self.rows[self.counter] = row
        return row

    def close_trade(self, trade_id, *, exit_price, fee=0.0, note=""):  # noqa: ANN001, ANN201, ARG002
        row = self.rows[trade_id]
        direction = 1.0 if row["side"] == "long" else -1.0
        row["pnl"] = (exit_price - row["entry_price"]) * direction * row["quantity"]
        row["status"] = "closed"
        return row


def _fixed_price(value: float):  # noqa: ANN201
    async def _get(_symbol: str) -> float:
        return value

    return _get


def _trader(**overrides):  # noqa: ANN003, ANN201
    """یک موتور آماده با قیمت قابل تغییر."""
    price = {"value": 100.0}

    async def price_source(_symbol: str) -> float:
        return price["value"]

    config = AutoTradeConfig(
        margin_per_trade=10.0, target_profit=2.0, max_loss=3.0, leverage=10.0,
        **overrides,
    )
    repo = _FakeRepo()
    return AutoTrader(config=config, price_source=price_source, repository=repo), repo, price


class TestScalpServiceAiReview:
    """
    هوش مصنوعی اینجا **مشاور** است، نه دروازه‌بان.

    اگر مدل خاموش، کند یا خراب باشد، پویش ریاضی باید کار کند. هرگز
    نباید کاربر به‌خاطر نبود مدل، بی‌نتیجه بماند.
    """

    @staticmethod
    def _service(ai_content: str | None = None, *, fail: bool = False):  # noqa: ANN205
        from trading.scalp_service import ScalpService

        class _Response:
            content = ai_content or ""

        class _Provider:
            async def generate(self, _messages, **_kwargs):  # noqa: ANN001, ANN202
                if fail:
                    raise RuntimeError("model down")
                return _Response()

        class _App:
            class settings:  # noqa: N801
                @staticmethod
                def get(_key, fallback):  # noqa: ANN001, ANN205
                    return fallback

            ai_provider = None if ai_content is None and not fail else _Provider()

        return ScalpService(_App())

    @staticmethod
    def _candidates() -> list[ScalpCandidate]:
        return [
            ScalpCandidate("AAA/USDT", 1.0, 20.0, "LONG", 1.0, 9e6, 0.02, 0.5),
            ScalpCandidate("BBB/USDT", 1.0, 10.0, "LONG", 1.0, 9e6, 0.02, 0.5),
        ]

    def test_a_missing_model_leaves_the_ranking_untouched(self) -> None:
        """بدون هوش مصنوعی، ریاضی به‌تنهایی کافی است."""
        service = self._service(None)
        result = asyncio.run(service._ai_review(self._candidates()))

        assert [c.symbol for c in result] == ["AAA/USDT", "BBB/USDT"]

    def test_a_broken_model_does_not_break_the_scan(self) -> None:
        """
        خطای مدل نباید پویش را از بین ببرد.

        این همان درسی است که در ماجرای اولاما گرفتیم.
        """
        service = self._service(fail=True)
        result = asyncio.run(service._ai_review(self._candidates()))

        assert len(result) == 2

    def test_a_skip_verdict_demotes_but_does_not_delete(self) -> None:
        """
        رد هوش مصنوعی نامزد را پایین می‌برد، نه اینکه پنهانش کند.

        تصمیم نهایی با کاربر است.
        """
        payload = (
            '{"picks":[{"symbol":"AAA/USDT","verdict":"skip","reason":"اسپرد پهن"}]}'
        )
        service = self._service(payload)
        result = asyncio.run(service._ai_review(self._candidates()))

        assert len(result) == 2
        assert result[-1].symbol == "AAA/USDT"

    def test_the_ai_reason_is_shown_to_the_user(self) -> None:
        """کاربر باید بداند چرا مدل این نظر را داد."""
        payload = (
            '{"picks":[{"symbol":"AAA/USDT","verdict":"good","reason":"شتاب قوی"}]}'
        )
        service = self._service(payload)
        result = asyncio.run(service._ai_review(self._candidates()))
        top = next(c for c in result if c.symbol == "AAA/USDT")

        assert any("شتاب قوی" in reason for reason in top.reasons)

    def test_json_wrapped_in_prose_is_still_parsed(self) -> None:
        """مدل‌های محلی اغلب JSON را داخل متن می‌پیچند."""
        from trading.scalp_service import ScalpService

        verdicts = ScalpService._parse_ai_verdicts(
            'حتما! {"picks":[{"symbol":"X/USDT","verdict":"skip","reason":"ب"}]} موفق باشید'
        )

        assert verdicts["X/USDT"]["verdict"] == "skip"

    @pytest.mark.parametrize("junk", ["", "سلام", "{broken", "[]", "null"])
    def test_malformed_ai_output_is_ignored_safely(self, junk: str) -> None:
        """خروجی خراب مدل نباید استثنا بدهد."""
        from trading.scalp_service import ScalpService

        assert ScalpService._parse_ai_verdicts(junk) == {}
