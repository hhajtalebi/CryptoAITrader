"""
آزمون‌های نسخهٔ ۲.۰ — ترمینال رویدادمحور معاملهٔ خودکار.

ماتریس تست خواسته‌شده:
    • حالت‌ها و چرخهٔ حیات: شروع/توقف، کاغذی، TP، SL، سر‌به‌سر،
      تریلینگ، تایم‌اوت، خروج اضطراری
    • پیش‌بینی: تازه‌سازی، تغییر نماد، افق‌ها، MTF، رژیم، سناریو،
      هشدار، دقت، نبودِ داده
    • دادهٔ زنده: تیک، Bid/Ask، مهرهای زمانی، تأخیر، تشخیص کهنگی،
      مسیر fallback
    • رابط کاربری: چهار رزولوشن، تغییر اندازهٔ زنده، اسکرول
      عمودی/افقی جدول‌ها، جدول هرگز له نمی‌شود

اصل طلایی این آزمون‌ها: هیچ دادهٔ نمایشی‌ای برای «موفق نشان دادن»
ساخته نمی‌شود؛ همهٔ ورودی‌ها یا از موتورهای واقعی می‌آیند یا از
داده‌ای که صراحةً «شبیه‌سازی آزمون» است و در محصول جایی ندارد.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from localization import Translator
from tests.conftest import destroy_window


# ---------------------------------------------------------------------------
# ابزار مشترک
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def translator() -> Translator:
    instance = Translator("fa")
    instance.load()
    return instance


@dataclass
class _Candidate:
    """نامزد حداقلی — همان پروتکل دو منبع موجود."""

    symbol: str
    direction: str = "LONG"
    score: float = 80.0
    turnover_24h: float = 9_000_000.0
    trend_ladder: Any = None
    margin: float = 0.0
    leverage: float = 0.0
    take_profit: float = 0.0
    stop_loss: float = 0.0


class _Repo:
    """مخزن ساختگی — فقط برای آزمون چرخهٔ حیات."""

    def __init__(self) -> None:
        self.opened: list[dict] = []
        self.closed: list[tuple[int, dict]] = []
        self._next_id = 1

    def open_trade(self, **kwargs: Any) -> dict:
        record = {"id": self._next_id, **kwargs}
        self._next_id += 1
        self.opened.append(record)
        return record

    def close_trade(self, trade_id: int, **kwargs: Any) -> dict:
        self.closed.append((trade_id, kwargs))
        return {"id": trade_id, "pnl": -1.0, "symbol": "BTC/USDT"}


def _report(direction: str = "bullish") -> dict:
    """گزارش پیش‌بینی با چندک‌های جهت‌دار — ساختار to_dict موتور."""
    quantiles = {
        "p10": 63000.0, "p25": 63700.0, "p50": 64000.0,
        "p75": 64500.0, "p90": 65000.0,
    }
    if direction == "bearish":
        quantiles = {
            "p10": 63000.0, "p25": 63500.0, "p50": 63800.0,
            "p75": 64000.0, "p90": 64100.0,
        }
    return {
        "horizons": [
            {
                "horizon": "15m",
                "direction": direction,
                "probability": 70,
                "confidence": 72,
                "quantiles": quantiles,
                "volatility": {"forecast_percent": 1.2},
            }
        ]
    }


def _bullish_ladder():
    from trading.trend_ladder import build_ladder

    return build_ladder(
        "BTC/USDT",
        regimes={
            "4h": {"direction": 1}, "1h": {"direction": 1},
            "15m": {"direction": 1}, "5m": {"direction": 1},
        },
    )


# ---------------------------------------------------------------------------
# ۱) کش تیک — سه مهر زمانی، تأخیر، کهنگی، Bid/Ask
# ---------------------------------------------------------------------------
class TestTickEngine:
    def test_record_sets_all_three_timestamps(self) -> None:
        """مهر صرافی/دریافت/پردازش هر سه ثبت می‌شوند (§۶)."""
        from trading.price_cache import TickEngine

        engine = TickEngine()
        engine.record(
            "BTC/USDT", 64000.0, source="websocket",
            exchange_ts=1_700_000_000_123, bid=63990.0, ask=64010.0,
        )
        quote = engine.get("BTC/USDT")
        assert quote.exchange_ts_ms == 1_700_000_000_123
        assert quote.received_ts_ms > 0
        assert quote.processed_ts_ms >= quote.received_ts_ms

    def test_latency_metrics_present(self) -> None:
        """تأخیر دریافت/پردازش از مهرها محاسبه می‌شود، نه حدس."""
        from trading.price_cache import TickEngine

        engine = TickEngine()
        engine.record(
            "BTC/USDT", 64000.0, source="websocket",
            exchange_ts=1_700_000_000_000, received_at_ms=1_700_000_000_050,
        )
        quote = engine.get("BTC/USDT")
        assert quote.receive_latency_ms == 50.0
        assert quote.processing_latency_ms >= 0
        assert quote.total_latency_ms >= 50.0

    def test_missing_exchange_ts_is_honest(self) -> None:
        """تیکر بدون زمان صرافی تأخیر کل را «نمی‌داند» (None)."""
        from trading.price_cache import TickEngine

        engine = TickEngine()
        engine.record("BTC/USDT", 64000.0, source="websocket")
        assert engine.get("BTC/USDT").total_latency_ms is None

    def test_entry_uses_ask_for_long_and_bid_for_short(self) -> None:
        """ورود LONG با Ask و SHORT با Bid — اسپرد واقعی (§۷)."""
        from trading.price_cache import TickEngine

        engine = TickEngine()
        engine.record("X", 100.0, source="ws", bid=99.0, ask=101.0)
        quote = engine.get("X")
        assert quote.entry_price("long") == 101.0
        assert quote.entry_price("short") == 99.0
        assert quote.exit_price("long") == 99.0
        assert quote.exit_price("short") == 101.0
        assert quote.spread == 2.0

    def test_stale_detection(self) -> None:
        """دادهٔ کهنه STALE است و نماد بدون تیک هم STALE."""
        from trading.price_cache import TickEngine

        engine = TickEngine(stale_after_seconds=1.0)
        engine.record("X", 100.0, source="ws")
        assert not engine.is_stale("X")
        assert engine.is_stale("NEVER-SEEN")
        engine._quotes["X"].processed_ts_ms -= 5_000
        assert engine.is_stale("X")

    def test_record_book_layers_bid_ask_only(self) -> None:
        """دفتر سفارش فقط بهترین Bid/Ask را روی تیک موجود لایه می‌کند."""
        from trading.price_cache import TickEngine

        @dataclass
        class _Book:
            best_bid: float = 98.0
            best_ask: float = 102.0
            bids: list = field(default_factory=lambda: [(98.0, 5.0)])
            asks: list = field(default_factory=lambda: [(102.0, 4.0)])

        engine = TickEngine()
        engine.record("X", 100.0, source="ws")
        assert engine.record_book("X", _Book()) is not None
        quote = engine.get("X")
        assert (quote.bid, quote.ask) == (98.0, 102.0)
        assert quote.spread_percent == pytest.approx(4.0, rel=0.01)
        # نماد بدون تیک قبلی: دفتر بی‌مصرف است
        assert engine.record_book("Y", _Book()) is None

    def test_dedupe_unchanged_tick(self) -> None:
        """تیک تکراری دوباره اعلام نمی‌شود ولی مهر تازه می‌گیرد."""
        from trading.price_cache import TickEngine

        engine = TickEngine()
        notified: list[str] = []
        engine.add_listener(lambda quote: notified.append(quote.symbol))
        engine.record("X", 100.0, source="ws", bid=99.0, ask=101.0)
        engine.record("X", 100.0, source="ws", bid=99.0, ask=101.0)
        assert len(notified) == 1
        assert engine.stats()["ticks"] == 2  # مهرها تازه شدند


# ---------------------------------------------------------------------------
# ۲) نردبان روند — 4H رژیم، 1H روند، 15m ساختار، 5m ستاپ، 1m ورود
# ---------------------------------------------------------------------------
class TestTrendLadder:
    def test_weighted_direction_prefers_higher_timeframes(self) -> None:
        from trading.trend_ladder import build_ladder

        ladder = build_ladder(
            "X",
            regimes={
                "4h": {"direction": 1}, "1h": {"direction": 1},
                "15m": {"direction": -1}, "5m": {"direction": -1},
            },
        )
        assert ladder.weighted_direction > 0  # وزن 4h/1h بیشتر است
        ladder_bear = build_ladder(
            "X",
            regimes={
                "4h": {"direction": -1}, "1h": {"direction": -1},
                "15m": {"direction": 1}, "5m": {"direction": 1},
            },
        )
        assert ladder_bear.weighted_direction < 0

    def test_serious_conflict_blocks(self) -> None:
        """تضاد با 4H یا 1H = منع ورود (§۴)."""
        from trading.trend_ladder import build_ladder, conflict_verdict

        ladder = build_ladder(
            "X", regimes={"4h": {"direction": 1}, "1h": {"direction": -1}}
        )
        verdict, reason = conflict_verdict(ladder, "SHORT")
        assert verdict == "block"
        assert "4h" in reason  # 4h صعودی با SHORT ناسازگار است
        # هر دو پلهٔ بالا مخالف باشند، هر دو گزارش می‌شوند
        ladder2 = build_ladder(
            "X", regimes={"4h": {"direction": 1}, "1h": {"direction": 1}}
        )
        verdict2, reason2 = conflict_verdict(ladder2, "SHORT")
        assert verdict2 == "block" and "4h" in reason2 and "1h" in reason2

    def test_minor_friction_penalizes_not_blocks(self) -> None:
        """اختلاف 15m/5m جریمه است، نه منع."""
        from trading.trend_ladder import build_ladder, conflict_verdict

        ladder = build_ladder(
            "X",
            regimes={
                "4h": {"direction": 1}, "1h": {"direction": 1},
                "15m": {"direction": -1},
            },
        )
        verdict, reason = conflict_verdict(ladder, "LONG")
        assert (verdict, reason) == ("penalty", "minor_friction")

    def test_no_data_is_unknown_not_zero(self) -> None:
        from trading.trend_ladder import build_ladder

        ladder = build_ladder("X", regimes={})
        assert not ladder.has_data
        assert ladder.step("4h").direction is None

    def test_1m_direction_from_live_ticks(self) -> None:
        """پلهٔ ورود (1m) از تیک‌های زنده ساخته می‌شود."""
        from trading.trend_ladder import build_ladder

        # پلهٔ ±۲۰ واحد روی ۶۴هزار یعنی ~۰٫۱۴٪ — از نوار خنثی (۰٫۰۲٪) بزرگ‌تر
        rising = [(float(i), 64000.0 + i * 20) for i in range(10)]
        falling = [(float(i), 64000.0 - i * 20) for i in range(10)]
        assert build_ladder("X", regimes={}, tick_history=rising).step("1m").direction == 1
        assert build_ladder("X", regimes={}, tick_history=falling).step("1m").direction == -1
        # دادهٔ کم یعنی نامعلوم — حدس زده نمی‌شود
        assert build_ladder("X", regimes={}, tick_history=rising[:3]).step("1m").direction is None


# ---------------------------------------------------------------------------
# ۳) تصمیم‌ساز AI — NO TRADE با دلیل صریح
# ---------------------------------------------------------------------------
class TestAIDecider:
    def _decide(self, tick_engine, **overrides):
        from trading.ai_decider import PortfolioState, decide

        kwargs = dict(
            symbol="BTC/USDT",
            report=_report(),
            ladder=_bullish_ladder(),
            quote=tick_engine.get("BTC/USDT"),
            turnover_24h=9_000_000.0,
            portfolio=PortfolioState(balance=1000.0),
        )
        kwargs.update(overrides)
        return decide(**kwargs)

    def _fresh_engine(self, stale_after: float = 30.0):
        from trading.price_cache import TickEngine

        engine = TickEngine(stale_after_seconds=stale_after)
        engine.record("BTC/USDT", 64000.0, source="ws", bid=63990.0, ask=64010.0)
        return engine

    def test_full_decision_has_quantile_tp_sl(self) -> None:
        """TP/SL از چندک‌های پیش‌بینی می‌آیند و Notional ≠ Margin."""
        decision = self._decide(self._fresh_engine())
        assert decision.ok, decision.reason
        assert decision.take_profit == 64500.0  # p75
        assert decision.stop_loss == 63700.0  # p25
        assert decision.entry_price == 64010.0  # Ask
        assert decision.notional == decision.margin * decision.leverage
        assert decision.risk_reward >= 1.2

    def test_no_trade_when_trend_conflicts(self) -> None:
        """تضاد 4H/1H هرگز با اطمینان بالا جبران نمی‌شود (§۴)."""
        from trading.trend_ladder import build_ladder

        bear_ladder = build_ladder(
            "BTC/USDT", regimes={"4h": {"direction": -1}, "1h": {"direction": -1}}
        )
        decision = self._decide(self._fresh_engine(), ladder=bear_ladder)
        assert not decision.ok
        assert decision.reason.startswith("trend_conflict")

    def test_no_trade_when_stale(self) -> None:
        engine = self._fresh_engine()
        engine._quotes["BTC/USDT"].processed_ts_ms -= 60_000
        decision = self._decide(engine)
        assert decision.reason == "stale_data"

    def test_no_trade_when_spread_abnormal(self) -> None:
        from trading.price_cache import TickEngine

        engine = TickEngine()
        engine.record("BTC/USDT", 100.0, source="ws", bid=99.0, ask=101.0)
        decision = self._decide(engine)
        assert decision.reason.startswith("wide_spread")

    def test_no_trade_when_low_liquidity(self) -> None:
        decision = self._decide(self._fresh_engine(), turnover_24h=1000.0)
        assert decision.reason == "low_liquidity"

    def test_no_trade_when_capacity_full(self) -> None:
        from trading.ai_decider import PortfolioState

        decision = self._decide(
            self._fresh_engine(),
            portfolio=PortfolioState(balance=1000.0, open_count=3, max_concurrent=3),
        )
        assert decision.reason == "max_concurrent_reached"

    def test_no_trade_when_neutral_prediction(self) -> None:
        decision = self._decide(self._fresh_engine(), report=_report("neutral"))
        assert decision.reason == "prediction_neutral"

    def test_leverage_scales_inverse_with_volatility(self) -> None:
        from trading.ai_decider import suggest_leverage

        assert suggest_leverage(volatility_percent=1.0) == 30.0
        assert suggest_leverage(volatility_percent=3.0) == 10.0
        assert suggest_leverage(volatility_percent=0) == 3.0  # نامعلوم = محافظه‌کار

    def test_allocation_modes(self) -> None:
        from trading.ai_decider import PortfolioState, size_margin

        portfolio = PortfolioState(balance=1000.0)
        assert size_margin(allocation_mode="fixed", base_margin=10, portfolio=portfolio) == 10
        assert size_margin(allocation_mode="percent", base_margin=5, portfolio=portfolio) == 50
        # confidence: ۱۰ × (۰٫۵ + ۰٫۳) = ۸
        assert size_margin(
            allocation_mode="confidence", base_margin=10, portfolio=portfolio, confidence=30
        ) == 8
        # سقف مارجین آزاد رعایت می‌شود
        tight = PortfolioState(balance=1000.0, used_margin=995.0)
        assert size_margin(allocation_mode="percent", base_margin=5, portfolio=tight) == 5.0


# ---------------------------------------------------------------------------
# ۴) موتور معاملهٔ خودکار — چرخهٔ حیات و خروج‌های هوشمند
# ---------------------------------------------------------------------------
class TestAutoTraderLifecycle:
    def _trader(self, tick_engine, **config_overrides):
        from trading.auto_trader import AutoTradeConfig, AutoTrader

        repo = _Repo()

        async def price_source(symbol: str) -> float:
            quote = tick_engine.get(symbol)
            if quote is not None and quote.last > 0:
                return quote.last
            return 0.0

        config = AutoTradeConfig(
            margin_per_trade=10.0, target_profit=2.0, max_loss=3.0,
            leverage=10.0, poll_seconds=0.25,
        )
        for key, value in config_overrides.items():
            setattr(config, key, value)
        trader = AutoTrader(
            config=config, price_source=price_source, repository=repo
        )
        trader.attach_tick_engine(tick_engine)
        return trader, repo

    def test_stop_loss_exits_on_tick_immediately(self) -> None:
        """SL با خودِ تیک بسته می‌شود — نه با تایمر چندثانیه‌ای (§۶)."""
        from trading.price_cache import TickEngine

        tick_engine = TickEngine(stale_after_seconds=30)
        trader, repo = self._trader(tick_engine)

        async def scenario() -> None:
            ok, message = await trader.start()
            assert ok, message
            tick_engine.record("BTC/USDT", 64000.0, source="ws", bid=63990.0, ask=64010.0)
            managed = await trader.open_trade(_Candidate("BTC/USDT"))
            assert managed is not None
            assert managed.entry_ask == 64010.0  # ورود با Ask واقعی
            entry = managed.entry_price
            # پرش به زیر SL → خروج در همان چرخهٔ رویداد
            tick_engine.record("BTC/USDT", entry * 0.9, source="ws",
                               bid=entry * 0.9, ask=entry * 0.9)
            await asyncio.sleep(0.4)
            assert len(trader.open_trades) == 0
            assert repo.closed and repo.closed[0][0] == managed.trade_id
            note = repo.closed[0][1].get("note", "")
            assert "stop_loss" in note or "بسته" in note
            await trader.stop()

        asyncio.run(scenario())

    def test_take_profit_exits_on_tick(self) -> None:
        from trading.price_cache import TickEngine

        tick_engine = TickEngine(stale_after_seconds=30)
        trader, repo = self._trader(tick_engine)

        async def scenario() -> None:
            await trader.start()
            tick_engine.record("BTC/USDT", 64000.0, source="ws", bid=63990.0, ask=64010.0)
            managed = await trader.open_trade(_Candidate("BTC/USDT"))
            entry = managed.entry_price
            tick_engine.record("BTC/USDT", entry * 1.05, source="ws",
                               bid=entry * 1.05, ask=entry * 1.05)
            await asyncio.sleep(0.4)
            assert len(trader.open_trades) == 0
            await trader.stop()

        asyncio.run(scenario())

    def test_break_even_moves_stop_after_trigger(self) -> None:
        """بعد از پوشش هزینه‌ها حد ضرر به ورود می‌رود (§۱۲)."""
        from trading.auto_trader import AutoTradeConfig, ManagedTrade

        config = AutoTradeConfig(break_even_trigger=1.0)
        trade = ManagedTrade(
            trade_id=1, symbol="X", side="long", entry_price=100.0,
            quantity=1.0, leverage=10, target_price=102.0, stop_price=97.0,
            opened_at=datetime.now(UTC), extra={"round_trip_fee": 0.12},
        )
        events = trade.mark(101.5, config)
        assert "break_even_armed" in events
        assert trade.effective_stop >= 100.0  # سر‌به‌سر واقعی: ورود + کارمزد

    def test_trailing_follows_price_and_never_recedes(self) -> None:
        from trading.auto_trader import AutoTradeConfig, ManagedTrade

        config = AutoTradeConfig(trailing_enabled=True, trailing_offset=0.4)
        trade = ManagedTrade(
            trade_id=1, symbol="X", side="long", entry_price=100.0,
            quantity=1.0, leverage=10, target_price=105.0, stop_price=97.0,
            opened_at=datetime.now(UTC),
        )
        trade.mark(102.0, config)
        first_stop = trade.effective_stop
        trade.mark(101.0, config)  # عقب‌نشینی قیمت
        assert trade.effective_stop == first_stop  # حد ضرر عقب نمی‌رود
        trade.mark(103.0, config)
        assert trade.effective_stop >= 102.6

    def test_timeout_fallback_without_ticks(self) -> None:
        """مسیر fallback (بدون تیک) تایم‌اوت را می‌بندد."""
        from trading.price_cache import TickEngine

        tick_engine = TickEngine(stale_after_seconds=30)
        trader, repo = self._trader(tick_engine, max_hold_seconds=1)

        async def scenario() -> None:
            await trader.start()
            tick_engine.record("BTC/USDT", 64000.0, source="ws", bid=63990.0, ask=64010.0)
            managed = await trader.open_trade(_Candidate("BTC/USDT"))
            # validated() حداقلِ max_hold را ۳۰ ثانیه نگه می‌دارد
            managed.opened_at = datetime.now(UTC) - timedelta(seconds=60)
            await trader.check_open_trades()
            assert len(trader.open_trades) == 0
            await trader.stop()

        asyncio.run(scenario())

    def test_emergency_exit_closes_all(self) -> None:
        from trading.price_cache import TickEngine

        tick_engine = TickEngine(stale_after_seconds=30)
        trader, repo = self._trader(tick_engine)

        async def scenario() -> None:
            await trader.start()
            tick_engine.record("BTC/USDT", 64000.0, source="ws", bid=63990.0, ask=64010.0)
            await trader.open_trade(_Candidate("BTC/USDT"))
            records = await trader.emergency_exit_all("emergency")
            assert records
            assert len(trader.open_trades) == 0
            await trader.stop()

        asyncio.run(scenario())

    def test_signal_invalidation_closes_on_reversal(self) -> None:
        """برگشت جهت پیش‌بینی = بستن، چون دلیل ورود رفته (§۱۲)."""
        from trading.price_cache import TickEngine

        tick_engine = TickEngine(stale_after_seconds=30)
        trader, repo = self._trader(tick_engine)

        async def scenario() -> None:
            await trader.start()
            tick_engine.record("BTC/USDT", 64000.0, source="ws", bid=63990.0, ask=64010.0)
            await trader.open_trade(_Candidate("BTC/USDT"))
            trader._invalidation_source = lambda symbol: "SHORT"
            await trader.check_signal_invalidation()
            assert len(trader.open_trades) == 0
            await trader.stop()

        asyncio.run(scenario())

    def test_entry_guards_reject_with_reason(self) -> None:
        """هر رد، با دلیل ثبت می‌شود — سکوت ممنوع (§۳)."""
        from trading.price_cache import TickEngine

        tick_engine = TickEngine(stale_after_seconds=30)
        trader, repo = self._trader(tick_engine)

        async def scenario() -> None:
            await trader.start()
            # نماد بدون تیک → STALE
            assert await trader.open_trade(_Candidate("ETH/USDT")) is None
            rows = trader.opportunities()
            assert any(row["reason"] == "stale_data" for row in rows)
            # تیک هست ولی گردشِ صریح صفر → low_liquidity
            tick_engine.record("ETH/USDT", 3000.0, source="ws", bid=2999.0, ask=3001.0)
            rejected = _Candidate("ETH/USDT", turnover_24h=0.0)
            assert await trader.open_trade(rejected) is None
            rows = trader.opportunities()
            assert any(row["reason"] == "low_liquidity" for row in rows)
            await trader.stop()

        asyncio.run(scenario())

    def test_trend_conflict_blocks_entry(self) -> None:
        """نامزد با نردبان مخالف، ورود نمی‌گیرد حتی با امتیاز بالا (§۴)."""
        from trading.price_cache import TickEngine
        from trading.trend_ladder import build_ladder

        bear_ladder = build_ladder(
            "BTC/USDT", regimes={"4h": {"direction": -1}, "1h": {"direction": -1}}
        )
        tick_engine = TickEngine(stale_after_seconds=30)
        trader, repo = self._trader(tick_engine)

        async def scenario() -> None:
            await trader.start()
            tick_engine.record("BTC/USDT", 64000.0, source="ws", bid=63990.0, ask=64010.0)
            candidate = _Candidate("BTC/USDT", score=99.0, trend_ladder=bear_ladder)
            assert await trader.open_trade(candidate) is None
            rows = trader.opportunities()
            assert any(
                str(row["reason"]).startswith("trend_conflict") for row in rows
            ), rows
            await trader.stop()

        asyncio.run(scenario())

    def test_ai_candidate_keeps_quantile_levels(self) -> None:
        """نامزد AI: مارجین/اهرم/TP/SL خودش را نگه می‌دارد."""
        from trading.ai_decider import AICandidate
        from trading.price_cache import TickEngine

        tick_engine = TickEngine(stale_after_seconds=30)
        trader, repo = self._trader(tick_engine)

        async def scenario() -> None:
            await trader.start()
            tick_engine.record("BTC/USDT", 64000.0, source="ws", bid=63990.0, ask=64010.0)
            candidate = AICandidate(
                symbol="BTC/USDT", price=64000.0, direction="LONG", score=72,
                turnover_24h=9e8, entry_price=64010.0, margin=12.2,
                leverage=25.0, take_profit=64500.0, stop_loss=63700.0,
                trend_ladder=_bullish_ladder(),
            )
            managed = await trader.open_trade(candidate)
            assert managed is not None
            assert managed.target_price == 64500.0
            assert managed.stop_price == 63700.0
            assert managed.leverage == 25.0
            assert managed.margin == 12.2
            # Notional = مارجین × اهرم — هرگز برابر مارجین (§۱۲)
            assert managed.margin * managed.leverage == 305.0
            await trader.stop()

        asyncio.run(scenario())

    def test_selected_mode_filters_symbols(self) -> None:
        """حالت Selected فقط نمادهای کاربر؛ خالی یعنی هیچ."""
        from trading.auto_trader import AutoTradeConfig

        config = AutoTradeConfig(engine_mode="selected", selected_symbols="")
        assert config.selected_symbol_list == []
        config2 = AutoTradeConfig(
            engine_mode="selected", selected_symbols="btc/usdt, ETH/USDT ,BTC/USDT"
        )
        assert config2.selected_symbol_list == ["BTC/USDT", "ETH/USDT"]

    def test_paper_mode_is_default_and_live_needs_phrase(self) -> None:
        from trading.auto_trader import (
            LIVE_CONFIRMATION_PHRASE, AutoTradeConfig,
        )

        config = AutoTradeConfig(mode="live", live_confirmation="اشتباه")
        assert not config.is_live
        config.live_confirmation = LIVE_CONFIRMATION_PHRASE
        assert config.is_live
        assert AutoTradeConfig().mode == "paper"


# ---------------------------------------------------------------------------
# ۵) صفحهٔ معاملات — ترمینال
# ---------------------------------------------------------------------------
class TestTradesTerminalUI:
    @pytest.fixture()
    def page(self, qt_app, translator):
        from ui.pages.trades_page import TradesPage

        instance = TradesPage(translator)
        try:
            yield instance
        finally:
            destroy_window(instance, qt_app)

    def test_tabs_built(self, page) -> None:
        """دو زبانه: ترمینال خودکار + تاریخچه."""
        assert page.tabs.count() == 2

    def test_info_cards_exist(self, page) -> None:
        """۹ کارت اطلاعاتی مرجع UI (§۲) همه ساخته شده‌اند."""
        for key in (
            "balance", "available", "used", "daily_pnl", "open_count",
            "opportunities", "win_rate", "drawdown", "risk_status",
        ):
            assert key in page._dashboard_cells, key
        page.set_auto_dashboard({"balance": "۱٬۰۰۰", "drawdown": "۲٪"})
        assert page._dashboard_cells["balance"][1].text() == "۱٬۰۰۰"
        assert page._dashboard_cells["drawdown"][1].text() == "۲٪"

    def test_terminal_header_pills(self, page) -> None:
        """قرص‌های هدر: موتور، Paper/Live، وب‌سوکت، آخرین تیک، تأخیر (§۱)."""
        page.set_auto_state(True)
        assert page.auto_state_label.text()
        page.set_paper_live(False)
        assert page.auto_paper_live_label.text()
        page.set_tick_status(
            {
                "websocket": True,
                "avg_total_latency_ms": 42.0,
                "last_tick_text": "آخرین تیک: 12:01:01.235",
                "stale": False,
            }
        )
        assert "آنلاین" in page.auto_ws_label.text()
        assert "۴۲" in page.auto_latency_label.text()  # ارقام فارسی
        assert "12:01" in page.auto_tick_label.text()
        page.set_tick_status({"websocket": False, "stale": True})
        assert "آفلاین" in page.auto_ws_label.text()

    def test_opportunity_table_search_and_filter(self, page) -> None:
        """جدول ۱۷ ستونهٔ فرصت‌ها + جست‌وجو + فیلتر (§۵)."""
        assert page.opportunity_table.columnCount() == 17
        page.set_opportunities(
            [
                {"symbol": "BTC/USDT", "direction": "LONG", "confidence": 80,
                 "probability": 70, "expected_move": 0.8, "trend": "+0.90",
                 "mtf": "aligned", "risk": 1.6, "spread": 0.03, "score": 80,
                 "entry": 64010.0, "tp": 64500.0, "sl": 63700.0, "leverage": 25.0,
                 "margin": 12.2, "prediction": "bullish 70%", "decision": "enter",
                 "reason": "", "actionable": False},
                {"symbol": "ETH/USDT", "direction": "SHORT", "confidence": 40,
                 "probability": 55, "expected_move": None, "trend": "-0.20",
                 "mtf": "", "risk": None, "spread": 0.10, "score": 40,
                 "entry": None, "tp": None, "sl": None, "leverage": None,
                 "margin": None, "prediction": "bearish 55%", "decision": "skip",
                 "reason": "low_confidence:40", "actionable": True},
            ]
        )
        assert page.opportunity_table.rowCount() == 2
        # مرتب‌سازی Qt ردیف‌ها را جابه‌جا می‌کند → جست‌وجوی ستونی
        def symbols_visible() -> set[str]:
            return {
                page.opportunity_table.item(r, 0).text()
                for r in range(page.opportunity_table.rowCount())
            }

        # ستون‌های عددی اختیاری: مقدار نیست یعنی «—» نه صفر
        entry_texts = {
            page.opportunity_table.item(r, 0).text(): page.opportunity_table.item(r, 10).text()
            for r in range(page.opportunity_table.rowCount())
        }
        assert entry_texts["ETH/USDT"] == "—"
        assert "۶۴" in entry_texts["BTC/USDT"]
        # جست‌وجو
        page.opportunity_search.setText("BTC")
        assert page.opportunity_table.rowCount() == 1
        assert symbols_visible() == {"BTC/USDT"}
        page.opportunity_search.setText("")
        assert page.opportunity_table.rowCount() == 2
        # فیلتر: فقط قابل ورود
        page.opportunity_filter_combo.setCurrentIndex(1)
        assert symbols_visible() == {"ETH/USDT"}
        # فیلتر: فقط رد‌شده‌ها
        page.opportunity_filter_combo.setCurrentIndex(2)
        assert symbols_visible() == {"ETH/USDT"}
        page.opportunity_filter_combo.setCurrentIndex(0)
        assert symbols_visible() == {"BTC/USDT", "ETH/USDT"}

    def test_opportunity_manual_enter_signal(self, page) -> None:
        """دوبار کلیک روی فرصتِ قابل‌ورود → سیگنال ورود دستی (§۵)."""
        page.set_opportunities(
            [
                {"symbol": "ETH/USDT", "direction": "SHORT", "confidence": 40,
                 "score": 40, "decision": "skip", "reason": "low_confidence",
                 "actionable": True},
                {"symbol": "BTC/USDT", "direction": "LONG", "confidence": 80,
                 "score": 80, "decision": "enter", "reason": "",
                 "actionable": False},
            ]
        )
        captured: list[str] = []
        page.opportunity_enter_requested.connect(captured.append)
        page._on_opportunity_activated(0, 0)  # قابل ورود
        assert captured == ["ETH/USDT"]
        page._on_opportunity_activated(1, 0)  # ورود‌شده — سیگنال نمی‌دهد
        assert captured == ["ETH/USDT"]

    def test_positions_table_never_shrinks(self, page) -> None:
        """جدول ۱۹ ستونه (با ستون اکشن v2.2) — له نمی‌شود (§۹/§۱۲)."""
        assert page.positions_table.columnCount() == 19
        assert page.positions_table.verticalHeader().minimumSectionSize() >= 30
        assert page.positions_table.horizontalHeader().minimumSectionSize() >= 70
        page.set_open_positions(
            [
                {
                    "id": 1, "symbol": "BTC/USDT", "side": "long",
                    "side_text": "خرید", "quantity_text": "۰٫۰۰۱۵۶۲",
                    "entry_text": "۶۴٬۰۰۰", "current_text": "۶۴٬۱۰۰",
                    "bid_text": "۶۴٬۰۹۰", "ask_text": "۶۴٬۱۱۰", "margin_text": "۱۰",
                    "notional_text": "۱۰۰", "leverage_text": "۱۰×", "tp_text": "—",
                    "sl_text": "—", "pnl": 1.5, "pnl_text": "+۱.۵",
                    "pnl_percent_text": "+۱۵٪", "duration_text": "0:12",
                    "data_age_text": "۴۵ ms", "exit_reason_text": "—",
                    "status_text": "کاغذی",
                }
            ]
        )
        assert page.positions_table.rowCount() == 1
        assert page.positions_note.isVisibleTo(page) is False

    def test_close_selected_position_signal(self, page, qt_app) -> None:
        """انتخاب + دکمهٔ بستن → سیگنال با شناسهٔ درست."""
        page.set_open_positions(
            [
                {"id": 42, "symbol": "BTC/USDT", "side_text": "خرید", "pnl": 0.0,
                 "pnl_text": "0", "pnl_percent_text": "0", "entry_text": "",
                 "current_text": "", "bid_text": "", "ask_text": "", "margin_text": "",
                 "notional_text": "", "leverage_text": "", "tp_text": "", "sl_text": "",
                 "duration_text": "", "data_age_text": "", "exit_reason_text": "",
                 "status_text": ""},
            ]
        )
        # تعیین صریح سلول جاری ( selectRow روی ویجت مخفی در برخی
        # ترتیب‌های اجرای مجموعه پایدار نیست)
        page.positions_table.setCurrentCell(0, 0)
        qt_app.processEvents()
        captured: list[int] = []
        page.close_position_requested.connect(captured.append)
        page._emit_close_position()
        assert captured == [42]

    def test_prediction_summary_and_ladder(self, page) -> None:
        """پنل خلاصهٔ تصمیم: جهت/اطمینان/نردبان 1m..4h (§۲)."""
        payload = {
            "live_price": 64000.0,
            "horizons": [
                {"horizon": "15m", "direction": "bullish", "probability": 70,
                 "confidence": 72, "quantiles": {"p10": 63000, "p50": 64000, "p90": 65000},
                 "model_agreement": 0.8}
            ],
            "regimes": {
                "4h": {"regime": "trend_up", "direction": 1},
                "1h": {"regime": "trend_up", "direction": 1},
                "15m": {"regime": "trend_down", "direction": -1},
                "5m": {"regime": "trend_up", "direction": 1},
                "1m": {"regime": "live_tick", "direction": 1},
            },
            "market_stage": "MARKUP",
            "multi_timeframe": {"alignment": "aligned"},
            "data_quality": {"ratio": 0.99},
            "warnings": ["نوسان بالا"],
            "generated_at": "2026-09-23T10:00:00+00:00",
        }
        page.update_prediction_summary(payload)
        assert page.prediction_widgets["direction"].text()  # جهت ترجمه‌شده
        assert page._ladder_labels["4h"].text() == "▲"
        assert page._ladder_labels["15m"].text() == "▼"
        assert page._ladder_labels["1m"].text() == "▲"
        assert page.prediction_warning_label.isVisibleTo(page)
        # نبود داده → همه «—» و برچسب هشدار پنهان
        page.update_prediction_summary(None)
        assert page.prediction_widgets["price"].text() == "—"
        assert not page.prediction_warning_label.isVisibleTo(page)

    def test_tick_status_display(self, page) -> None:
        """قرص‌های هدر: تأخیر عددی، تیک کهنه = هشدار (§۱/§۹)."""
        page.set_tick_status(
            {"websocket": True, "avg_total_latency_ms": 42.5, "last_tick_text": "تیک: ۱"}
        )
        assert "ms" in page.auto_latency_label.text()
        assert page.auto_tick_label.text() == "تیک: ۱"
        page.set_tick_status(
            {"websocket": False, "last_tick_text": "تیک: ۱", "stale": True}
        )
        assert "آفلاین" in page.auto_ws_label.text()
        # تیک بدون متن → برچسب خالی نمی‌شود
        assert page.auto_tick_label.text() == "تیک: ۱"

    def test_close_selected_position_signal(self, page, qt_app) -> None:
        """انتخاب + دکمهٔ بستن → سیگنال با شناسهٔ درست."""
        page.set_open_positions(
            [
                {"id": 42, "symbol": "BTC/USDT", "side_text": "خرید", "pnl": 0.0,
                 "pnl_text": "0", "pnl_percent_text": "0", "entry_text": "",
                 "current_text": "", "bid_text": "", "ask_text": "", "margin_text": "",
                 "notional_text": "", "leverage_text": "", "tp_text": "", "sl_text": "",
                 "duration_text": "", "data_age_text": "", "exit_reason_text": "",
                 "status_text": ""},
            ]
        )
        # تعیین صریح سلول جاری ( selectRow روی ویجت مخفی در برخی
        # ترتیب‌های اجرای مجموعه پایدار نیست)
        page.positions_table.setCurrentCell(0, 0)
        qt_app.processEvents()
        captured: list[int] = []
        page.close_position_requested.connect(captured.append)
        page._emit_close_position()
        assert captured == [42]

    def test_prediction_summary_and_ladder(self, page) -> None:
        """پنل خلاصهٔ تصمیم: جهت/اطمینان/نردبان 1m..4h (§۲)."""
        payload = {
            "live_price": 64000.0,
            "horizons": [
                {"horizon": "15m", "direction": "bullish", "probability": 70,
                 "confidence": 72, "quantiles": {"p10": 63000, "p50": 64000, "p90": 65000},
                 "model_agreement": 0.8}
            ],
            "regimes": {
                "4h": {"regime": "trend_up", "direction": 1},
                "1h": {"regime": "trend_up", "direction": 1},
                "15m": {"regime": "trend_down", "direction": -1},
                "5m": {"regime": "trend_up", "direction": 1},
                "1m": {"regime": "live_tick", "direction": 1},
            },
            "market_stage": "MARKUP",
            "multi_timeframe": {"alignment": "aligned"},
            "data_quality": {"ratio": 0.99},
            "warnings": ["نوسان بالا"],
            "generated_at": "2026-09-23T10:00:00+00:00",
        }
        page.update_prediction_summary(payload)
        assert page.prediction_widgets["direction"].text()  # جهت ترجمه‌شده
        assert page._ladder_labels["4h"].text() == "▲"
        assert page._ladder_labels["15m"].text() == "▼"
        assert page._ladder_labels["1m"].text() == "▲"
        assert page.prediction_warning_label.isVisibleTo(page)
        # نبود داده → همه «—» و برچسب هشدار پنهان
        page.update_prediction_summary(None)
        assert page.prediction_widgets["price"].text() == "—"
        assert not page.prediction_warning_label.isVisibleTo(page)

    def test_mode_combo_and_selected_input(self, page) -> None:
        """سه حالت + ورودی نمادهای Selected (§۳)."""
        values = [page.auto_engine_mode_combo.itemData(i) for i in range(3)]
        assert values == ["selected", "scan", "ai"]
        page.load_auto_settings(
            {"scalp.engine_mode": "ai", "scalp.selected_symbols": "BTC/USDT,SOL/USDT"}
        )
        assert page.auto_engine_mode_combo.currentData() == "ai"
        assert page.auto_selected_input.text() == "BTC/USDT,SOL/USDT"
        collected = page.collect_auto_settings()
        assert collected["scalp.engine_mode"] == "ai"
        assert collected["scalp.selected_symbols"] == "BTC/USDT,SOL/USDT"

    def test_responsive_reflow(self, page) -> None:
        """
        پهن = خلاصه|نمودار؛ باریک = زیر هم (§۹).

        جدول‌ها حداقل عرض دارند، پس در پنجرهٔ باریک صفحه از ۹۰۰ پیکسل
        هم باریک‌تر نمی‌شود و به‌جای فشردگی اسکرول افقی می‌گیرد —
        چیدمان ستونی از عرضِ بدنه تعیین می‌شود، نه پنجره.
        """
        page.resize(1920, 1080)
        assert page.chart_row._stacked is False
        # سازوکار چینش در عرض کم:
        page.chart_row.reflow(900)
        assert page.chart_row._stacked is True
        page.chart_row.reflow(1400)
        assert page.chart_row._stacked is False
        # جدول‌ها هرگز فشرده نمی‌شوند: عرض کمینه > ۹۰۰ → اسکرول افقی
        assert page.positions_table.minimumWidth() > 900

    @pytest.mark.parametrize("width,height", [(1280, 720), (1366, 768), (1600, 900), (1920, 1080)])
    def test_four_resolutions(self, page, qt_app, width, height) -> None:
        """در هر چهار رزولوشن: بدون کرش، جدول‌ها با حداقل عرض."""
        page.resize(width, height)
        qt_app.processEvents()
        for table in (page.opportunity_table, page.positions_table, page.table):
            assert table.minimumWidth() > 0
            assert table.verticalHeader().minimumSectionSize() >= 30

    def test_chart_card_with_real_candles(self, page) -> None:
        """کارت نمودار: کندل/حجم واقعی + خطوط موقعیت + وضعیت (§۳)."""
        from app.core.models import Candle

        candles = [
            Candle(timestamp=1_700_000_000 + i * 900, open=100.0 + i,
                   high=101.0 + i, low=99.0 + i, close=100.5 + i, volume=10.0 + i)
            for i in range(30)
        ]
        page.set_chart_candles(candles, "15m", "BTC/USDT")
        assert page.price_chart.candles_item.candles, "کندل‌ها باید رسم شوند"
        page.set_chart_live_price(105.0)
        page.mark_chart_position(100.0, 97.0, [102.0])
        page.set_chart_status("۱۰۵", "هم‌راستا", "۴۵ ms")
        assert page.chart_price_label.text() == "۱۰۵"

    def test_timeframe_selector_signal(self, page) -> None:
        """انتخاب تایم‌فریم 1m..4h → سیگنال با کلید درست (§۳)."""
        assert list(page.timeframe_bar._buttons) == [
            "1m", "5m", "15m", "1h", "4h"
        ]
        captured: list[str] = []
        page.auto_timeframe_changed.connect(captured.append)
        page.timeframe_bar.set_current("1m")
        assert captured == ["1m"]

    def test_risk_panel_renders(self, page) -> None:
        """پنل ریسک ۱۰ خانه + حکم نهایی (§۱۱)."""
        assert len(page._risk_cells) == 10
        page.set_risk_panel(
            {
                "daily_loss": "-3.20$ / 20$",
                "max_drawdown": "۴٫۲٪",
                "exposure": "۳۰۵$",
                "margin_usage": "۳۰٪ / ۶۰٪",
                "open_trades": "1 / 3",
                "risk_per_trade": "3$",
                "leverage": "10×",
                "spread_risk": "۰٫۰۳۱٪",
                "liquidity_risk": "OK",
                "data_risk": "آنلاین",
                "verdict": "ریسک در محدودهٔ مجاز",
                "verdict_role": "chip_up",
            }
        )
        assert page._risk_cells["daily_loss"][1].text() == "-3.20$ / 20$"
        assert page.risk_verdict_label.text() == "ریسک در محدودهٔ مجاز"

    def test_config_panel_collapsible(self, page) -> None:
        """پنل تنظیمات پیش‌فرض جمع است و دکمهٔ هدر آن را باز/بسته می‌کند."""
        assert page.config_panel.isVisibleTo(page) is False
        page._toggle_config_panel()
        assert page.config_panel.isVisibleTo(page) is True
        page._toggle_config_panel()
        assert page.config_panel.isVisibleTo(page) is False

    def test_terminal_tabs_with_counts(self, page) -> None:
        """زبانه‌های پایین ترمینال: فرصت‌ها | موقعیت‌ها با شمار زنده."""
        assert page.terminal_tabs.count() == 2
        page.set_opportunities([{"symbol": "BTC/USDT", "decision": "skip"}])
        assert "(1)" in page.terminal_tabs.tabText(0)
        assert "(0)" in page.terminal_tabs.tabText(1)
        page.set_open_positions(
            [{"id": 1, "symbol": "BTC/USDT", "side": "long", "status": "open"}]
        )
        assert "(1)" in page.terminal_tabs.tabText(1)

    def test_auto_symbols_population_selects_first(self, page) -> None:
        """
        پرشدن کمبوی نماد نمودار — نخستین نماد با سیگنال انتخاب
        می‌شود تا نمودار همان لحظه زنده شود (رفع «کمبوی خالی»).
        """
        captured: list[str] = []
        page.auto_symbol_changed.connect(captured.append)
        page.set_auto_symbols(["BTC/USDT", "ETH/USDT", "SOL/USDT"])
        assert page.auto_symbol_combo.count() == 3
        assert page.auto_symbol_combo.currentText() == "BTC/USDT"
        assert captured == ["BTC/USDT"]
        assert page.prediction_symbol_label.text() == "BTC/USDT"
        # پرکردن دوباره: انتخاب فعلی حفظ و سیگنال تکراری نمی‌دهد
        page.set_auto_symbols(["ETH/USDT", "BTC/USDT", "SOL/USDT", "XRP/USDT"])
        assert page.auto_symbol_combo.currentText() == "BTC/USDT"
        assert captured == ["BTC/USDT"]

    def test_set_auto_symbol_adds_missing_and_emits(self, page) -> None:
        """نمادِ خارج از فهرست هم افزوده و با سیگنال انتخاب می‌شود."""
        captured: list[str] = []
        page.auto_symbol_changed.connect(captured.append)
        page.set_auto_symbols(["ETH/USDT"])
        captured.clear()
        page.set_auto_symbol("BTC/USDT")  # در کمبو نیست
        assert page.auto_symbol_combo.currentText() == "BTC/USDT"
        assert captured == ["BTC/USDT"]

    def test_history_tab_preserved(self, page) -> None:
        """زبانهٔ تاریخچه همان رفتار قبل: فیلتر/معیار/صفحه‌بندی."""
        assert page.side_combo.count() == 3
        assert page.status_combo.count() == 4
        assert hasattr(page, "pagination")
        assert hasattr(page, "empty_state")

    def test_tables_have_toolbars(self, page) -> None:
        """هر سه جدول نوار ابزار (تمام‌صفحه/CSV) دارند — بدون نسخهٔ دوم."""
        toolbars = page.table_toolbars()
        assert len(toolbars) == 3

    def test_scroll_envelopes_terminal(self, page) -> None:
        """صفحه پیمایش عمودی/افقی دارد؛ محتوا فشرده نمی‌شود (§۹)."""
        assert page.scrollable is True
        assert page._scroll is not None


# ---------------------------------------------------------------------------
# ۶) صفحهٔ پیش‌بینی — داشبورد تحلیلی
# ---------------------------------------------------------------------------
class TestPredictionDashboard:
    @pytest.fixture()
    def page(self, qt_app, translator):
        from ui.pages.prediction_page import PredictionPage

        instance = PredictionPage(translator)
        try:
            yield instance
        finally:
            destroy_window(instance, qt_app)

    def _payload(self) -> dict:
        return {
            "symbol": "BTC/USDT",
            "generated_at": "2026-09-23T12:00:00+00:00",
            "last_price": 64000.0,
            "horizons": [
                {
                    "horizon": "1h", "direction": "bullish", "probability": 63,
                    "confidence": 58,
                    "quantiles": {"p10": 63500, "p25": 63700, "p50": 64000,
                                  "p75": 64300, "p90": 64600},
                    "expected_range": {"low": 63500, "high": 64600},
                    "method": "empirical", "samples": 480,
                    "volatility": {"forecast_percent": 1.4},
                    "model_agreement": 0.83, "conflict": False,
                    "scenarios": {"scenarios": [
                        {"name": "bull", "probability": 0.38, "low": 64300, "high": 64800},
                        {"name": "base", "probability": 0.44, "low": 63800, "high": 64300},
                        {"name": "bear", "probability": 0.18, "low": 63300, "high": 63800},
                    ]},
                    "event_pressure": None,
                    "reasons": ["رژیم روندی صعودی"],
                }
            ],
            "disabled_horizons": [{"horizon": "7d", "reason": "insufficient_history_1d"}],
            "regimes": {"1h": {"regime": "strong_trend_up", "confidence": 72, "direction": 1}},
            "market_stage": {"stage": "MARKUP", "confidence": 66},
            "multi_timeframe": {"alignment": "aligned", "per_timeframe": {}},
            "breakout": {"state": "none"},
            "false_breakout": {},
            "anomalies": {},
            "warnings": ["نوسان بالا"],
            "timeline": [
                {"created_at": "2026-09-23T11:00", "direction": "bullish", "probability": 61}
            ],
            "what_changed": {
                "probability_delta": -8, "direction_changed": False,
                "changed_factors": [
                    {"name": "momentum", "before": 12.0, "after": 3.0, "direction": "down"}
                ],
            },
            "accuracy": {"resolved": 12, "direction_accuracy": 58.3,
                         "range_accuracy": 41.6, "brier": 0.21},
            "model_health": {"statistical": {"accuracy": 60.0, "status": "good", "samples": 12}},
            "data_quality": {"ratio": 0.99},
        }

    def test_dashboard_renders_all_sections(self, page) -> None:
        """همهٔ بخش‌ها: خلاصه، بادبزن، جدول، رژیم، سناریو، هشدار، دقت، تغییرات، خط زمانی."""
        page.update_report(self._payload())
        assert page.horizons_table.rowCount() == 1
        assert page.fan_chart._points, "نمودار بادبزن باید از چندک‌ها پر شود"
        assert page.summary_direction_label.text()
        assert page.ring._label  # حلقهٔ اطمینان مقدار دارد
        assert page.disabled_label.isVisibleTo(page)
        assert "7d" in page.disabled_label.text()
        assert page._rows["market"] and page._rows["scenarios"]
        assert page._rows["warnings"] and page._rows["accuracy"]
        assert page._rows["changed"] and page._rows["timeline"]

    def test_fan_chart_ignores_bad_points(self, page) -> None:
        """نقاط نامعتبر (ترتیب نادرست چندک) رسم نمی‌شوند."""
        page.fan_chart.set_points(
            [("ok", 1.0, 2.0, 3.0, 4.0, 5.0), ("bad", 5.0, 4.0, 3.0, 2.0, 1.0)]
        )
        assert len(page.fan_chart._points) == 1

    def test_horizons_table_columns(self, page) -> None:
        """جدول افق‌ها همان فیلدهای قبلی را دارد — هیچ فیلدی حذف نشده (§۱)."""
        page.update_report(self._payload())
        expected = {
            "افق", "جهت", "احتمال", "اطمینان", "P10", "P50", "P90",
            "نوسان", "توافق مدل‌ها", "نمونه‌ها", "روش", "وضعیت",
        }
        headers = {
            page.horizons_table.horizontalHeaderItem(i).text()
            for i in range(page.horizons_table.columnCount())
        }
        assert expected <= headers, headers

    def test_no_data_shows_empty_honestly(self, page) -> None:
        page.update_report(self._payload())
        page.update_report(None)
        assert page.empty_label.isVisibleTo(page)
        assert not page.horizons_card.isVisibleTo(page)

    def test_responsive_rows_reflow(self, page) -> None:
        """چهار ردیف واکنش‌گرا همه در عرض کم زیر هم می‌روند (§۱۰)."""
        page.update_report(self._payload())
        page.resize(1920, 1080)
        for row in (page.summary_row, page.market_row, page.warn_row, page.changed_row):
            assert row._stacked is False
        for row in (page.summary_row, page.market_row, page.warn_row, page.changed_row):
            row.reflow(950)
            assert row._stacked is True

    def test_retranslate_keeps_data(self, page) -> None:
        page.update_report(self._payload())
        page.retranslate()
        assert page.horizons_table.rowCount() == 1
        assert page._payload is not None


# ---------------------------------------------------------------------------
# ۷) اتصال کنترلر — سبک، بدون شبکه
# ---------------------------------------------------------------------------
class TestControllerWiring:
    @pytest.fixture()
    def controller(self, qt_app, translator):
        """کنترلر سبک با همان الگوی آزمون‌های موجود (`__new__`)."""
        from ui.controllers.main_controller import MainController
        from ui.pages.trades_page import TradesPage

        instance = MainController.__new__(MainController)
        instance.tr_ = translator
        instance.trades = TradesPage(translator)

        class _Settings:
            def __init__(self) -> None:
                self._values = {"scalp.stale_after_seconds": 10.0}

            def get(self, key, default=None):
                return self._values.get(key, default)

        class _Market:
            is_online = False
            websocket_status = None
            _ticker_listeners: list = []

            def add_ticker_listener(self, callback):
                self._ticker_listeners.append(callback)

            async def get_orderbook(self, symbol, depth=20):
                return None

        class _App:
            market = _Market()
            settings = _Settings()
            prediction_engine = None
            trade_repository = None
            auth = None
            exchange_accounts = None

        instance.app = _App()
        instance.window = None  # QTimer ساخت نمی‌شود؛ فقط در محیط واقعی
        try:
            yield instance
        finally:
            destroy_window(instance.trades, qt_app)

    def test_ensure_tick_engine_is_singleton(self, controller) -> None:
        engine1 = controller._ensure_tick_engine()
        engine2 = controller._ensure_tick_engine()
        assert engine1 is engine2

    def test_market_ticker_flows_into_cache(self, controller) -> None:
        """تیکر صرافی → کش تیک (سه مهر زمانی)."""
        engine = controller._ensure_tick_engine()

        class _Ticker:
            symbol = "BTC/USDT"
            last_price = 64000.0
            timestamp = 1_700_000_000_000
            change_percent = 1.2

        controller._on_market_ticker(_Ticker())
        quote = engine.get("BTC/USDT")
        assert quote is not None and quote.last == 64000.0
        assert quote.exchange_ts_ms == 1_700_000_000_000
        assert quote.change_percent == 1.2

    def test_enrich_auto_prediction_injects_1m(self, controller) -> None:
        """پلهٔ 1m از تیک‌های زنده به گزارش تزریق می‌شود."""
        engine = controller._ensure_tick_engine()
        for i in range(10):
            engine.record("BTC/USDT", 64000.0 + i * 20, source="ws")
        payload = controller._enrich_auto_prediction("BTC/USDT", {"regimes": {}})
        assert payload["regimes"]["1m"]["direction"] == 1
        assert payload["live_price"] == 64180.0

    def test_prediction_direction_from_cached_report(self, controller) -> None:
        class _Report:
            def to_dict(self):
                return _report("bearish")

        class _Engine:
            def report(self, symbol):
                return _Report()

        controller.app.prediction_engine = _Engine()
        assert controller._prediction_direction("BTC/USDT") == "SHORT"
        controller.app.prediction_engine = None
        assert controller._prediction_direction("BTC/USDT") == ""

    def test_terminal_refresh_is_safe_without_market(self, controller) -> None:
        """تازه‌سازی ترمینال بدون بازار/موتور نباید کرش کند."""
        controller._terminal_stats_tick = 4
        controller._refresh_auto_terminal()
        assert controller.trades._dashboard_cells["balance"][1].text()

    def test_auto_timeframe_roundtrip(self, controller) -> None:
        """تایم‌فریم نامعتبر رد می‌شود؛ معتبر ذخیره و نمودار خالی می‌ماند."""
        controller.on_auto_timeframe_changed("8h")  # نامعتبر → بی‌اثر
        assert controller._auto_timeframe() == "15m"
        controller.on_auto_timeframe_changed("1m")
        assert controller._auto_timeframe() == "1m"

    def test_opportunity_enter_without_engine_is_safe(self, controller) -> None:
        """ورود دستی بدون موتور/نامزد → فقط پیام، بدون کرش."""
        toasts: list[tuple] = []
        controller._toast = lambda message, level="info": toasts.append((message, level))
        controller.on_opportunity_enter("BTC/USDT")
        assert toasts and toasts[0][1] == "warning"
