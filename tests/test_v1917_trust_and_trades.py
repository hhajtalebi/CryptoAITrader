"""
آزمون‌های نسخه ۱.۹.۱۷ — بازبینی اعتماد به سیگنال و معاملات زنده.

کاربر گزارش کرد:
    • سیگنال‌های با اطمینان ۸۰، ۹۰ و ۱۰۰ درصد ضرر دادند.
    • معامله باز می‌شود ولی تغییر نمی‌کند، بسته نمی‌شود و سود/زیانش
      معلوم نیست؛ دستی هم بسته نمی‌شود.
    • مرتب‌سازی سابقهٔ سیگنال‌ها لازم است.

مهم‌ترین یافته: فرمول قبلی اطمینان با **یک** رأی راهبرد عدد ۱۰۰٪
می‌ساخت. سامانه در کل ۳ راهبرد دارد، پس رسیدن به اعداد بالا بی‌معنا آسان
بود و آن اعداد هیچ ربطی به احتمال موفقیت نداشتند.
"""

from __future__ import annotations

import pytest

from signals import confidence as confidence_model
from trading.trade_monitor import (
    REASON_STOP_LOSS,
    REASON_TAKE_PROFIT,
    LivePosition,
    evaluate,
    position_from_record,
)


class TestConfidenceIsNowEarned:
    """ضریب اطمینان باید کمیاب باشد، نه رایگان."""

    def test_a_single_strategy_cannot_reach_high_confidence(self) -> None:
        """
        این دقیقاً همان ایرادی است که کاربر گزارش کرد.

        یک راهبرد با امتیاز کامل، پیش‌تر ۱۰۰٪ می‌ساخت.
        """
        result = confidence_model.compute(
            score=1.0, consensus=1.0, strategy_count=1, timeframe_count=1
        )
        assert result.final <= 45
        assert result.final < 100

    def test_confidence_grows_with_independent_evidence(self) -> None:
        """هرچه شواهد مستقل بیشتر، اطمینان بالاتر — ولی تدریجی."""
        one = confidence_model.compute(
            score=1.0, consensus=1.0, strategy_count=1, timeframe_count=1
        ).final
        two = confidence_model.compute(
            score=1.0, consensus=1.0, strategy_count=2, timeframe_count=2
        ).final
        three = confidence_model.compute(
            score=1.0, consensus=1.0, strategy_count=3, timeframe_count=3
        ).final
        assert one < two < three

    def test_one_hundred_percent_is_never_shown(self) -> None:
        """
        ۱۰۰٪ یعنی «قطعی» و در بازار هیچ‌چیز قطعی نیست.

        نمایش ۱۰۰٪ وعده‌ای است که هیچ سامانه‌ای نمی‌تواند به آن عمل کند.
        """
        result = confidence_model.compute(
            score=1.0, consensus=1.0, strategy_count=99, timeframe_count=99
        )
        assert result.final <= confidence_model.ABSOLUTE_CAP
        assert result.final < 100

    def test_no_evidence_means_no_confidence(self) -> None:
        """بدون هیچ رأیی، اطمینان صفر است."""
        result = confidence_model.compute(
            score=0.9, consensus=1.0, strategy_count=0, timeframe_count=0
        )
        assert result.final == 0

    def test_disagreement_lowers_confidence(self) -> None:
        """اجماع کمتر ⇒ اطمینان کمتر."""
        agree = confidence_model.compute(
            score=0.8, consensus=1.0, strategy_count=3, timeframe_count=3
        ).final
        conflict = confidence_model.compute(
            score=0.8, consensus=0.4, strategy_count=3, timeframe_count=3
        ).final
        assert conflict < agree

    def test_the_reason_is_explained_to_the_user(self) -> None:
        """کاربر باید بداند چرا سقف خورده است."""
        result = confidence_model.compute(
            score=1.0, consensus=1.0, strategy_count=1, timeframe_count=1
        )
        assert result.reasons
        assert any("راهبرد" in reason for reason in result.reasons)


class TestHistoricalCalibration:
    """اگر سیگنال‌های یک بازه در عمل ضرر داده‌اند، عدد باید پایین بیاید."""

    def test_a_bad_track_record_pulls_confidence_down(self) -> None:
        """
        این پاسخ مستقیم به «۹۰٪ گفت ولی ضرر داد» است: سامانه از نتایج
        واقعی خودش یاد می‌گیرد.
        """
        # مقدار پس از اعمال سقف در بازهٔ ۸۰ می‌افتد، پس آمار همان بازه
        # خوانده می‌شود.
        buckets = {
            "80-89": {"resolved": 50, "win_rate": 30.0},
        }
        plain = confidence_model.compute(
            score=0.9, consensus=0.95, strategy_count=3, timeframe_count=3
        )
        calibrated = confidence_model.compute(
            score=0.9,
            consensus=0.95,
            strategy_count=3,
            timeframe_count=3,
            buckets=buckets,
        )
        assert plain.final >= 80, "پیش‌شرط آزمون: عدد باید در بازهٔ ۸۰ بیفتد"
        assert calibrated.final < plain.final

    def test_a_good_track_record_is_rewarded(self) -> None:
        """نرخ برد بالا در عمل، اطمینان را بالا می‌برد."""
        buckets = {"80-89": {"resolved": 60, "win_rate": 99.0}}
        plain = confidence_model.compute(
            score=0.9, consensus=0.95, strategy_count=3, timeframe_count=3
        )
        calibrated = confidence_model.compute(
            score=0.9,
            consensus=0.95,
            strategy_count=3,
            timeframe_count=3,
            buckets=buckets,
        )
        assert calibrated.final > plain.final

    def test_a_tiny_sample_is_ignored(self) -> None:
        """
        با ۳ نمونه نمی‌توان نتیجه گرفت.

        حدس‌زدن از روی نمونهٔ کوچک، بدتر از استفاده‌نکردن از آن است.
        """
        buckets = {"80-89": {"resolved": 3, "win_rate": 0.0}}
        plain = confidence_model.compute(
            score=0.9, consensus=0.95, strategy_count=3, timeframe_count=3
        )
        calibrated = confidence_model.compute(
            score=0.9,
            consensus=0.95,
            strategy_count=3,
            timeframe_count=3,
            buckets=buckets,
        )
        assert calibrated.final == plain.final

    def test_missing_statistics_change_nothing(self) -> None:
        """نبود آمار نباید عدد را جابه‌جا کند."""
        plain = confidence_model.compute(
            score=0.7, consensus=0.8, strategy_count=2, timeframe_count=2
        )
        with_none = confidence_model.compute(
            score=0.7, consensus=0.8, strategy_count=2, timeframe_count=2, buckets=None
        )
        assert plain.final == with_none.final


class TestTheEngineUsesTheNewModel:
    """موتور سیگنال باید واقعاً از مدل تازه استفاده کند."""

    def test_one_vote_no_longer_yields_full_confidence(self) -> None:
        """آزمون سرتاسری روی خودِ موتور، نه فقط مدل."""
        from app.core.models import SignalDirection
        from signals.engine import SignalEngine
        from signals.strategies.base import StrategyVote

        engine = SignalEngine.__new__(SignalEngine)
        engine._calibration_source = None  # noqa: SLF001

        vote = StrategyVote(
            strategy="trend",
            direction=SignalDirection.LONG,
            score=1.0,
            weight=1.0,
            reasons=["r"],
            applicable=True,
        )
        _, alignment, _ = engine._aggregate({"4h": [vote]})  # noqa: SLF001
        assert round(alignment * 100) <= 45

    def test_broken_calibration_source_does_not_break_signals(self) -> None:
        """آمار خراب نباید تولید سیگنال را متوقف کند."""
        from app.core.models import SignalDirection
        from signals.engine import SignalEngine
        from signals.strategies.base import StrategyVote

        class _Broken:
            def confidence_buckets(self) -> dict:
                raise RuntimeError("database is gone")

        engine = SignalEngine.__new__(SignalEngine)
        engine._calibration_source = _Broken()  # noqa: SLF001
        vote = StrategyVote(
            strategy="trend",
            direction=SignalDirection.LONG,
            score=0.8,
            weight=1.0,
            reasons=["r"],
            applicable=True,
        )
        score, alignment, _ = engine._aggregate({"4h": [vote]})  # noqa: SLF001
        assert 0.0 <= alignment <= 1.0


class TestOpenTradesAreAlive:
    """معاملهٔ باز باید با بازار حرکت کند و سر موعد بسته شود."""

    def _long(self) -> LivePosition:
        return LivePosition(
            trade_id=1,
            symbol="BTC/USDT",
            side="long",
            quantity=0.01,
            entry_price=80_000.0,
            leverage=10.0,
            stop_loss=79_000.0,
            take_profit=82_000.0,
        )

    def test_profit_is_measured_against_margin_not_price(self) -> None:
        """
        با اهرم ۱۰، حرکت ۰٫۶۲٪ قیمت یعنی ۶٫۲۵٪ بازده سرمایه.

        نمایش درصدِ قیمت، عدد را ۱۰ برابر کوچک‌تر از واقعیت نشان می‌داد.
        """
        pnl, percent = self._long().unrealised(80_500.0)
        assert pnl == pytest.approx(5.0)
        assert percent == pytest.approx(6.25)

    def test_loss_is_negative(self) -> None:
        """حرکت خلاف جهت، زیان می‌سازد."""
        pnl, percent = self._long().unrealised(79_500.0)
        assert pnl == pytest.approx(-5.0)
        assert percent == pytest.approx(-6.25)

    def test_short_profits_when_price_falls(self) -> None:
        """موقعیت فروش با افت قیمت سود می‌دهد."""
        short = LivePosition(
            trade_id=2,
            symbol="BTC/USDT",
            side="short",
            quantity=0.01,
            entry_price=80_000.0,
            leverage=10.0,
        )
        pnl, _ = short.unrealised(79_000.0)
        assert pnl == pytest.approx(10.0)

    def test_take_profit_closes_the_trade(self) -> None:
        """رسیدن به حد سود یعنی بستن."""
        close, reason = self._long().should_close(82_000.0)
        assert close is True
        assert reason == REASON_TAKE_PROFIT

    def test_stop_loss_closes_the_trade(self) -> None:
        """رسیدن به حد ضرر یعنی بستن."""
        close, reason = self._long().should_close(78_900.0)
        assert close is True
        assert reason == REASON_STOP_LOSS

    def test_stop_loss_wins_when_both_are_hit(self) -> None:
        """
        اگر هر دو مرز در یک لحظه زده شوند، محتاطانه‌ترین فرض برنده است.

        فرض خوش‌بینانه باعث می‌شود آمار عملکرد دروغ بگوید.
        """
        position = LivePosition(
            trade_id=3,
            symbol="BTC/USDT",
            side="long",
            quantity=0.01,
            entry_price=80_000.0,
            stop_loss=81_000.0,
            take_profit=80_500.0,
        )
        close, reason = position.should_close(80_600.0)
        assert close is True
        assert reason == REASON_STOP_LOSS

    def test_a_quiet_market_keeps_the_trade_open(self) -> None:
        """قیمت میان دو مرز یعنی معامله باز می‌ماند."""
        close, _ = self._long().should_close(80_500.0)
        assert close is False

    def test_a_missing_price_is_skipped_not_zeroed(self) -> None:
        """
        نمادی که قیمتش نرسیده باید نادیده گرفته شود.

        نمایش «۰ دلار» اطلاعات غلط است و بدتر از نبودِ عدد.
        """
        updates, closures = evaluate([self._long()], {})
        assert updates == []
        assert closures == []

    def test_evaluate_reports_both_updates_and_closures(self) -> None:
        """یک دور پایش، هم سود/زیان می‌دهد هم فهرست بستن."""
        updates, closures = evaluate([self._long()], {"BTC/USDT": 82_000.0})
        assert len(updates) == 1
        assert updates[0]["pnl"] == pytest.approx(20.0)
        assert closures == [(1, 82_000.0, REASON_TAKE_PROFIT)]

    def test_a_broken_record_is_skipped(self) -> None:
        """ردیف ناقص نباید کل پایش را از کار بیندازد."""
        assert position_from_record({"id": 0, "entry_price": 0}) is None
        assert position_from_record({}) is None

    def test_a_valid_record_is_converted(self) -> None:
        """ردیف سالم درست تبدیل می‌شود."""
        position = position_from_record(
            {
                "id": 7,
                "symbol": "ETH/USDT",
                "side": "short",
                "quantity": 1.5,
                "entry_price": 3000.0,
                "leverage": 5.0,
                "stop_loss": 3100.0,
                "take_profit": 2800.0,
            }
        )
        assert position is not None
        assert position.trade_id == 7
        assert position.is_long is False
        assert position.leverage == pytest.approx(5.0)


class TestTheSignalHistoryCanBeSorted:
    """کاربر خواست سابقه بر اساس اطمینان و جهت مرتب شود."""

    @staticmethod
    def _rows() -> list[dict]:
        return [
            {"symbol": "A", "direction": "WAIT", "confidence": 90, "created_at": "3"},
            {"symbol": "B", "direction": "LONG", "confidence": 40, "created_at": "1"},
            {"symbol": "C", "direction": "SHORT", "confidence": 70, "created_at": "2"},
        ]

    def test_sort_keys_exist_in_both_languages(self) -> None:
        """کلیدهای ترجمهٔ مرتب‌سازی در هر دو زبان تعریف شده‌اند."""
        import json
        from pathlib import Path

        for language in ("fa", "en"):
            path = (
                Path(__file__).resolve().parents[1]
                / "localization"
                / language
                / "signals.json"
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            assert "sort_by" in data
            assert "group_by_direction" in data
            assert set(data["sort"]) >= {
                "confidence_desc",
                "confidence_asc",
                "direction",
                "newest",
                "symbol",
            }

    def test_close_reason_messages_exist(self) -> None:
        """پیام دلیل بسته‌شدن معامله باید ترجمه داشته باشد."""
        import json
        from pathlib import Path

        for language in ("fa", "en"):
            path = (
                Path(__file__).resolve().parents[1]
                / "localization"
                / language
                / "trades.json"
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            assert "closed_stop_loss" in data
            assert "closed_take_profit" in data


class TestTheAiIsAFuturesSpecialist:
    """کاربر خواست نقش هوش مصنوعی «متخصص ارشد فیوچرز» باشد."""

    def test_the_prompt_describes_a_senior_derivatives_analyst(self) -> None:
        """پرامپت باید نقش تخصصی را صریح بیان کند."""
        from ai.agent.autonomous_agent import SYSTEM_PROMPT

        assert "senior cryptocurrency derivatives analyst" in SYSTEM_PROMPT
        assert "PERPETUAL FUTURES" in SYSTEM_PROMPT

    def test_the_prompt_anchors_confidence_bands(self) -> None:
        """
        بدون لنگر عددی، مدل هر عددی را «اطمینان» می‌نامد.

        همان چیزی که باعث شد اعداد بالا بی‌معنا شوند.
        """
        from ai.agent.autonomous_agent import SYSTEM_PROMPT

        assert "HOW A PROFESSIONAL SIZES CONFIDENCE" in SYSTEM_PROMPT
        assert "80-92" in SYSTEM_PROMPT

    def test_the_prompt_covers_futures_specific_risk(self) -> None:
        """نکات ویژهٔ فیوچرز باید در پرامپت باشند."""
        from ai.agent.autonomous_agent import SYSTEM_PROMPT

        for topic in ("liquidation", "Liquidity", "spread", "leverage"):
            assert topic in SYSTEM_PROMPT


class TestUpgradingAnExistingDatabase:
    """
    ارتقای نسخه نباید پایگاه دادهٔ موجود کاربر را از کار بیندازد.

    `create_all` جدولِ نبوده را می‌سازد ولی جدول موجود را **دست نمی‌زند**.
    پس ستون تازه روی پایگاه دادهٔ کاربران فعلی وجود ندارد و برنامه با
    خطای «no such column» می‌افتد. این دقیقاً هنگام افزودن
    `paper_trades.last_price` رخ داد و پیش از انتشار گرفته شد.
    """

    def test_a_missing_column_is_added_to_an_existing_table(self, tmp_path) -> None:
        """ستون تازه باید روی جدول قدیمی ساخته شود."""
        import sqlalchemy as sa

        from app.database.session import DatabaseManager

        url = f"sqlite:///{tmp_path / 'legacy.db'}"
        # جدول را عمداً بدون ستون تازه می‌سازیم تا حالت «نسخهٔ قدیمی»
        # بازتولید شود.
        engine = sa.create_engine(url)
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "CREATE TABLE paper_trades ("
                    "id INTEGER PRIMARY KEY, symbol VARCHAR(30), "
                    "side VARCHAR(10), status VARCHAR(20), quantity FLOAT, "
                    "entry_price FLOAT)"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO paper_trades "
                    "(symbol, side, status, quantity, entry_price) "
                    "VALUES ('BTC/USDT', 'long', 'open', 0.01, 80000.0)"
                )
            )
        engine.dispose()

        DatabaseManager(url).create_all()

        inspector = sa.inspect(sa.create_engine(url))
        columns = {c["name"] for c in inspector.get_columns("paper_trades")}
        assert "last_price" in columns

    def test_existing_rows_survive_the_upgrade(self, tmp_path) -> None:
        """
        دادهٔ کاربر هرگز نباید در ارتقا از بین برود.

        قاعدهٔ همیشگی پروژه: پایگاه داده و تنظیمات کاربر بازنشانی نمی‌شوند.
        """
        import sqlalchemy as sa

        from app.database.session import DatabaseManager

        url = f"sqlite:///{tmp_path / 'legacy2.db'}"
        engine = sa.create_engine(url)
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "CREATE TABLE paper_trades ("
                    "id INTEGER PRIMARY KEY, symbol VARCHAR(30), "
                    "side VARCHAR(10), status VARCHAR(20), quantity FLOAT, "
                    "entry_price FLOAT)"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO paper_trades "
                    "(symbol, side, status, quantity, entry_price) "
                    "VALUES ('ETH/USDT', 'short', 'open', 2.0, 3000.0)"
                )
            )
        engine.dispose()

        DatabaseManager(url).create_all()

        engine = sa.create_engine(url)
        with engine.begin() as connection:
            row = connection.execute(
                sa.text("SELECT symbol, entry_price, last_price FROM paper_trades")
            ).fetchone()
        assert row[0] == "ETH/USDT"
        assert row[1] == 3000.0
        # ستون تازه برای ردیف قدیمی مقدار خنثی می‌گیرد، نه NULL.
        assert row[2] == 0.0

    def test_reconciliation_is_safe_to_run_twice(self, tmp_path) -> None:
        """اجرای دوباره نباید خطا بدهد یا چیزی را خراب کند."""
        from app.database.session import DatabaseManager

        url = f"sqlite:///{tmp_path / 'twice.db'}"
        manager = DatabaseManager(url)
        manager.create_all()
        manager.create_all()
