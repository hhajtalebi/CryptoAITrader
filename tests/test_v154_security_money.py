"""
آزمون‌های امنیت راز و مسیر پول.

این دو حوزه بیشترین هزینه را در صورت خرابی دارند: لو رفتن کلید صرافی، و
اشتباه در اندازهٔ موقعیت. هر دو اینجا رفتاری آزموده می‌شوند، نه با
خواندن کد.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

CANARY_KEY = "CANARY_APIKEY_zzz111"
CANARY_SECRET = "CANARY_APISECRET_zzz222"


@pytest.fixture()
def tmp_data_dir(tmp_path):  # type: ignore[no-untyped-def]
    """پوشهٔ دادهٔ ایزوله برای هر آزمون."""
    return tmp_path


@pytest.fixture()
def app_instance(tmp_data_dir):  # type: ignore[no-untyped-def]
    """
    نمونهٔ برنامه روی پوشهٔ دادهٔ موقت.

    مسیرها صریح تزریق می‌شوند و به متغیر محیطی تکیه نمی‌کنیم: شیء
    `app_paths` سطح ماژول است و در نخستین Import تثبیت می‌شود، پس
    تغییر متغیر محیطی بعد از آن اثری ندارد و آزمون‌ها به پایگاه دادهٔ
    یکدیگر وصل می‌شوند.
    """
    from app.core.paths import AppPaths

    from app.application import Application

    return Application(paths=AppPaths(tmp_data_dir))


# ---------------------------------------------------------------------------
# امنیت راز
# ---------------------------------------------------------------------------
def _make_account(app):  # type: ignore[no-untyped-def]
    """ساخت کاربر و حساب صرافی آزمایشی."""
    user, _ = app.auth.register("sec_probe", "StrongPass!234")
    uid = user["id"] if isinstance(user, dict) else user.id
    account = app.exchange_accounts.add_account(
        user_id=uid,
        exchange="lbank",
        label="probe",
        api_key=CANARY_KEY,
        api_secret=CANARY_SECRET,
    )
    aid = account["id"] if isinstance(account, dict) else account.id
    masked = (
        account["api_key_masked"] if isinstance(account, dict) else account.api_key_masked
    )
    return aid, masked


def test_secrets_are_never_stored_in_plain_text(app_instance, tmp_data_dir) -> None:  # type: ignore[no-untyped-def]
    """
    هیچ فایلی در پوشهٔ داده نباید کلید یا راز خام داشته باشد.

    قانون کاربر: کلید و راز هرگز به‌صورت متن ساده ذخیره نشوند.
    """
    _make_account(app_instance)

    leaks: list[str] = []
    for path in Path(tmp_data_dir).rglob("*"):
        if not path.is_file():
            continue
        blob = path.read_bytes()
        for secret in (CANARY_KEY, CANARY_SECRET):
            if secret.encode() in blob:
                leaks.append(f"{path.name}:{secret}")

    assert not leaks, f"راز خام روی دیسک پیدا شد: {leaks}"


def test_secret_roundtrip_and_masking(app_instance) -> None:  # type: ignore[no-untyped-def]
    """رمزگشایی باید دقیق باشد ولی آنچه نشان داده می‌شود ماسک‌شده."""
    aid, masked = _make_account(app_instance)

    creds = app_instance.exchange_accounts.credentials(aid)
    assert creds["api_key"] == CANARY_KEY
    assert creds["api_secret"] == CANARY_SECRET

    assert CANARY_KEY not in str(masked)
    assert "•" in str(masked)


def test_upstream_errors_do_not_leak_secrets(app_instance) -> None:  # type: ignore[no-untyped-def]
    """
    اگر صرافی خطایی برگرداند که راز داخلش باشد، نباید به کاربر یا لاگ برسد.

    این حالت واقعاً پیش می‌آید: بعضی APIها پارامترهای درخواست را در متن
    خطا تکرار می‌کنند.
    """
    aid, _ = _make_account(app_instance)

    class ExplodingProvider:
        """ارائه‌دهنده‌ای که خطایش راز را فاش می‌کند."""

        async def test_credentials(self):  # type: ignore[no-untyped-def]
            raise RuntimeError(f"rejected key={CANARY_KEY} secret={CANARY_SECRET}")

        async def close(self) -> None:
            return None

    ok, message = asyncio.run(
        app_instance.exchange_accounts.test_connection(aid, lambda *a, **k: ExplodingProvider())
    )

    assert ok is False
    assert CANARY_KEY not in str(message)
    assert CANARY_SECRET not in str(message)


# ---------------------------------------------------------------------------
# مسیر پول: معاملهٔ کاغذی
# ---------------------------------------------------------------------------
def test_live_trading_is_off_by_default(app_instance) -> None:  # type: ignore[no-untyped-def]
    """
    معاملهٔ واقعی باید پیش‌فرض خاموش باشد.

    قانون صریح کاربر: هیچ سفارش واقعی ثبت نشود.
    """
    from signals.paper_trader import PaperTrader

    assert PaperTrader(app_instance.settings).live_trading_enabled is False


def test_position_size_matches_allowed_risk(app_instance) -> None:  # type: ignore[no-untyped-def]
    """
    اندازهٔ موقعیت باید دقیقاً ریسک مجاز را بدهد.

    اشتباه اینجا یعنی کاربر چند برابر آنچه تصور می‌کند در خطر بگذارد.
    """
    from signals.paper_trader import PaperTrader

    risk = app_instance.risk_parameters()
    trader = PaperTrader(app_instance.settings)
    position = trader.open_from_signal(
        {
            "symbol": "BTC/USDT",
            "direction": "LONG",
            "confidence": 70,
            "entry": {"min": 100.0, "max": 102.0},
            "stop_loss": 95.0,
            "take_profit": [110.0],
            "leverage": 3,
        },
        balance=risk.account_balance,
        risk_percent=risk.risk_percent,
    )

    assert position is not None
    risked = position.size * abs(position.entry - position.stop_loss)
    expected = risk.account_balance * risk.risk_percent / 100.0
    assert risked == pytest.approx(expected, rel=1e-9)


def test_wait_signal_opens_no_position(app_instance) -> None:  # type: ignore[no-untyped-def]
    """روی «انتظار» هیچ موقعیتی باز نمی‌شود — انتظار یک تصمیم است."""
    from signals.paper_trader import PaperTrader

    trader = PaperTrader(app_instance.settings)
    assert trader.open_from_signal({"symbol": "ETH/USDT", "direction": "WAIT"}) is None


def test_positions_survive_a_new_instance(app_instance) -> None:  # type: ignore[no-untyped-def]
    """موقعیت‌ها باید ماندگار باشند، وگرنه سابقهٔ کاربر با هر بار باز کردن می‌پرد."""
    from signals.paper_trader import PaperTrader

    opener = PaperTrader(app_instance.settings)
    opener.open_from_signal(
        {
            "symbol": "SOL/USDT",
            "direction": "SHORT",
            "entry": 100.0,
            "stop_loss": 105.0,
        },
        balance=1000.0,
        risk_percent=1.0,
    )

    reopened = PaperTrader(app_instance.settings)
    assert len(reopened.open_positions()) == 1

    assert reopened.close_position(0, note="آزمون") is True
    assert len(reopened.open_positions()) == 0
    # بسته‌شده باید در سابقه بماند
    assert len(reopened.all_positions()) == 1
