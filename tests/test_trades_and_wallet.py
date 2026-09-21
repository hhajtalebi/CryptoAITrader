"""
آزمون معاملات کاغذی و صفحه‌های تازه (تاریخچهٔ معاملات و کیف پول).

نکتهٔ کلیدی: محاسبهٔ سود/زیان باید جهت‌آگاه باشد — در موقعیت فروش، افت
قیمت سود است. اشتباه در همین یک علامت، همهٔ گزارش‌ها را بی‌اعتبار می‌کند.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.database.models import Base
from app.database.repositories import PaperTradeRepository, UserRepository
from app.database.session import DatabaseManager


@pytest.fixture()
def trades(tmp_path: Path) -> PaperTradeRepository:
    """
    مخزن معاملات روی پایگاه دادهٔ موقت.

    دو کاربر واقعی ساخته می‌شود چون `paper_trades.user_id` کلید خارجی
    دارد؛ آزمون باید همان قیدهای پایگاه دادهٔ واقعی را تحمل کند.
    """
    manager = DatabaseManager(f"sqlite:///{tmp_path / 'trades.db'}")
    Base.metadata.create_all(manager.engine)
    users = UserRepository(manager)
    users.create_user(username="first", password="Strong!pass1")
    users.create_user(username="second", password="Strong!pass2")
    return PaperTradeRepository(manager)


# ---------------------------------------------------------------------------
# چرخهٔ معامله
# ---------------------------------------------------------------------------
def test_trade_defaults_to_paper_mode(trades: PaperTradeRepository) -> None:
    """
    هر معامله باید در حالت کاغذی ثبت شود.

    کاربر صریحاً خواسته است هیچ سفارش واقعی ارسال نشود.
    """
    trade = trades.open_trade(
        symbol="BTC/USDT", side="long", quantity=0.1, entry_price=60_000
    )
    assert trade["mode"] == "paper"
    assert trade["status"] == "open"


def test_long_profit_is_positive_when_price_rises(trades: PaperTradeRepository) -> None:
    """خرید + بالا رفتن قیمت = سود."""
    trade = trades.open_trade(
        symbol="BTC/USDT", side="long", quantity=0.1, entry_price=60_000
    )
    closed = trades.close_trade(trade["id"], exit_price=63_000)
    assert closed["pnl"] == pytest.approx(300.0)
    assert closed["pnl_percent"] == pytest.approx(5.0)
    assert closed["status"] == "closed"


def test_short_profits_when_price_falls(trades: PaperTradeRepository) -> None:
    """فروش + پایین آمدن قیمت = سود (علامت باید برعکس خرید باشد)."""
    trade = trades.open_trade(
        symbol="ETH/USDT", side="short", quantity=2.0, entry_price=3_000
    )
    closed = trades.close_trade(trade["id"], exit_price=2_900)
    assert closed["pnl"] == pytest.approx(200.0)
    assert closed["pnl_percent"] > 0


def test_short_loses_when_price_rises(trades: PaperTradeRepository) -> None:
    """فروش + بالا رفتن قیمت = زیان."""
    trade = trades.open_trade(
        symbol="ETH/USDT", side="short", quantity=1.0, entry_price=3_000
    )
    closed = trades.close_trade(trade["id"], exit_price=3_100)
    assert closed["pnl"] == pytest.approx(-100.0)
    assert closed["pnl_percent"] < 0


def test_leverage_multiplies_percent_not_absolute(trades: PaperTradeRepository) -> None:
    """اهرم باید در درصد سود ضرب شود، نه در مبلغ خام."""
    trade = trades.open_trade(
        symbol="BTC/USDT", side="long", quantity=0.1, entry_price=60_000, leverage=5
    )
    closed = trades.close_trade(trade["id"], exit_price=63_000)
    assert closed["pnl"] == pytest.approx(300.0)
    assert closed["pnl_percent"] == pytest.approx(25.0)


def test_fee_is_deducted_from_profit(trades: PaperTradeRepository) -> None:
    """کارمزد باید از سود کم شود."""
    trade = trades.open_trade(
        symbol="BTC/USDT", side="long", quantity=0.1, entry_price=60_000, fee=1.0
    )
    closed = trades.close_trade(trade["id"], exit_price=63_000, fee=2.0)
    assert closed["fee"] == pytest.approx(3.0)
    assert closed["pnl"] == pytest.approx(297.0)


def test_closing_twice_is_rejected(trades: PaperTradeRepository) -> None:
    """معاملهٔ بسته‌شده نباید دوباره بسته شود."""
    trade = trades.open_trade(
        symbol="BTC/USDT", side="long", quantity=0.1, entry_price=60_000
    )
    assert trades.close_trade(trade["id"], exit_price=61_000) is not None
    assert trades.close_trade(trade["id"], exit_price=62_000) is None


def test_cancel_leaves_no_profit(trades: PaperTradeRepository) -> None:
    """لغو معامله نباید سود یا زیانی ثبت کند."""
    trade = trades.open_trade(
        symbol="BTC/USDT", side="long", quantity=0.1, entry_price=60_000
    )
    assert trades.cancel_trade(trade["id"]) is True
    assert trades.list_trades(status="cancelled")[0]["pnl"] == 0.0


# ---------------------------------------------------------------------------
# فیلتر و آمار
# ---------------------------------------------------------------------------
def _seed(trades: PaperTradeRepository, user_id: int = 1) -> None:
    """چند معاملهٔ نمونه برای آزمون‌های فیلتر و آمار."""
    win = trades.open_trade(
        symbol="BTC/USDT", side="long", quantity=0.1, entry_price=60_000, user_id=user_id
    )
    trades.close_trade(win["id"], exit_price=63_000)  # +300
    loss = trades.open_trade(
        symbol="ETH/USDT", side="short", quantity=1.0, entry_price=3_000, user_id=user_id
    )
    trades.close_trade(loss["id"], exit_price=3_100)  # -100
    trades.open_trade(
        symbol="SOL/USDT", side="long", quantity=5.0, entry_price=150, user_id=user_id
    )


def test_filters_narrow_results(trades: PaperTradeRepository) -> None:
    """فیلتر نماد، جهت و وضعیت باید درست کار کند."""
    _seed(trades)
    assert len(trades.list_trades(user_id=1)) == 3
    assert len(trades.list_trades(user_id=1, side="long")) == 2
    assert len(trades.list_trades(user_id=1, status="open")) == 1
    assert len(trades.list_trades(user_id=1, symbol="BTC/USDT")) == 1
    assert trades.count_trades(user_id=1, side="short") == 1


def test_pagination_uses_limit_and_offset(trades: PaperTradeRepository) -> None:
    """صفحه‌بندی نباید ردیف تکراری یا جاافتاده بدهد."""
    for index in range(7):
        trades.open_trade(
            symbol=f"C{index}/USDT", side="long", quantity=1, entry_price=100, user_id=1
        )
    first = trades.list_trades(user_id=1, limit=3, offset=0)
    second = trades.list_trades(user_id=1, limit=3, offset=3)
    assert len(first) == 3 and len(second) == 3
    assert {row["id"] for row in first}.isdisjoint({row["id"] for row in second})


def test_statistics_are_consistent(trades: PaperTradeRepository) -> None:
    """آمار باید با معاملات ثبت‌شده بخواند."""
    _seed(trades)
    stats = trades.statistics(user_id=1)
    assert stats["total"] == 3
    assert stats["closed"] == 2
    assert stats["open"] == 1
    assert stats["wins"] == 1
    assert stats["losses"] == 1
    assert stats["win_rate"] == pytest.approx(50.0)
    assert stats["total_pnl"] == pytest.approx(200.0)
    assert stats["profit_factor"] == pytest.approx(3.0)


def test_statistics_on_empty_history_do_not_divide_by_zero(
    trades: PaperTradeRepository,
) -> None:
    """تاریخچهٔ خالی نباید باعث تقسیم بر صفر شود."""
    stats = trades.statistics(user_id=1)
    assert stats["total"] == 0
    assert stats["win_rate"] == 0.0
    assert stats["profit_factor"] == 0.0


def test_equity_curve_follows_closed_trades(trades: PaperTradeRepository) -> None:
    """منحنی سرمایه باید از موجودی اولیه شروع و با هر معامله جابه‌جا شود."""
    _seed(trades)
    curve = trades.equity_curve(user_id=1, starting_balance=1_000.0)
    assert curve[0] == 1_000.0
    assert curve[-1] == pytest.approx(1_200.0)
    assert len(curve) == 3  # موجودی اولیه + دو معاملهٔ بسته‌شده


def test_trades_are_isolated_per_user(trades: PaperTradeRepository) -> None:
    """معاملات یک کاربر نباید در فهرست کاربر دیگر دیده شود."""
    trades.open_trade(
        symbol="BTC/USDT", side="long", quantity=1, entry_price=100, user_id=1
    )
    trades.open_trade(
        symbol="ETH/USDT", side="long", quantity=1, entry_price=100, user_id=2
    )
    assert len(trades.list_trades(user_id=1)) == 1
    assert trades.list_trades(user_id=2)[0]["symbol"] == "ETH/USDT"


def test_clear_history_only_affects_target_user(trades: PaperTradeRepository) -> None:
    """پاک‌کردن تاریخچه نباید داده کاربر دیگر را حذف کند."""
    trades.open_trade(
        symbol="BTC/USDT", side="long", quantity=1, entry_price=100, user_id=1
    )
    trades.open_trade(
        symbol="ETH/USDT", side="long", quantity=1, entry_price=100, user_id=2
    )
    trades.clear_history(user_id=1)
    assert trades.list_trades(user_id=1) == []
    assert len(trades.list_trades(user_id=2)) == 1
