"""
آزمون مسیر کامل «ورود به حساب صرافی» از دید کاربر.

این آزمون دقیقاً همان کاری را می‌کند که کاربر در برنامه انجام می‌دهد:
صرافی را انتخاب می‌کند، کلید و رمز را تایپ می‌کند، دکمهٔ افزودن را
می‌زند و سپس اتصال را آزمایش می‌کند — برای هر دو صرافی تازه.

هیچ تماس شبکه‌ای واقعی لازم نیست: ارائه‌دهنده با یک بدل جایگزین می‌شود
تا نتیجه قطعی و سریع باشد.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

pytest.importorskip("PySide6")

from app.application import Application  # noqa: E402
from app.core.paths import AppPaths  # noqa: E402
from localization import Translator  # noqa: E402
from ui.controllers.main_controller import MainController  # noqa: E402
from ui.themes.theme_manager import ThemeManager  # noqa: E402
from ui.windows.main_window import MainWindow  # noqa: E402

NEW_EXCHANGES = ("toobit", "bitpin")


class _FakeProvider:
    """ارائه‌دهندهٔ بدل که بدون شبکه، موفقیت یا شکست را شبیه‌سازی می‌کند."""

    def __init__(self, *, succeed: bool) -> None:
        self._succeed = succeed

    async def test_credentials(self) -> tuple[bool, str]:
        """نتیجهٔ از پیش تعیین‌شده."""
        if self._succeed:
            return True, "exchange.error.verified"
        return False, "exchange.error.bitpin_rejected"

    async def get_account_balance(self) -> dict[str, float]:
        """موجودی نمونه."""
        return {"USDT": 25.0}

    async def close(self) -> None:
        """بستن بدون کار."""


@pytest.fixture
def gui(tmp_path, qt_application):
    """
    ساخت پنجره و کنترلر آمادهٔ کار با کاربر واردشده.

    از فیکسچر مشترک `qt_application` استفاده می‌شود چون ساخت چند
    QApplication در یک فرایند مفسر را از پا درمی‌آورد. در پایان، نخِ
    اجراکنندهٔ پس‌زمینه و حلقهٔ رویداد بسته می‌شوند تا آزمون بعدی روی
    منابع نشتی‌شدهٔ آزمون قبلی اجرا نشود.
    """
    qt_app = qt_application

    # مسیر مستقیم داده می‌شود نه متغیر محیطی: هر آزمون پایگاه دادهٔ خود را
    # می‌گیرد و به ترتیب اجرا وابسته نمی‌شود.
    app = Application(AppPaths(tmp_path).ensure())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(app.start())

    translator = Translator("fa")
    theme_manager = ThemeManager()
    window = MainWindow(translator, theme_manager)
    controller = MainController(app, window, translator, theme_manager, qt_app)
    controller.start()

    app.auth.register("flowuser", "Str0ng-Pass!1", email="flow@example.com")
    try:
        yield app, window, controller, qt_app
    finally:
        runner = getattr(controller, "runner", None)
        if runner is not None and hasattr(runner, "stop"):
            runner.stop()
        window.close()
        window.deleteLater()
        qt_app.processEvents()
        # موتور بازار باید پیش از بستن حلقه متوقف شود، وگرنه تسکِ
        # «lbank-ws» معلق می‌ماند و پیام «Task was destroyed but it is
        # pending!» چاپ می‌شود.
        loop.run_until_complete(app.stop())
        loop.close()
        asyncio.set_event_loop(None)


def _settings(window: MainWindow):
    """دسترسی به صفحهٔ تنظیمات."""
    return window.pages["nav.settings"]


def _add_account(settings, exchange: str, key: str, secret: str) -> None:
    """شبیه‌سازی تایپ کاربر و زدن دکمهٔ افزودن."""
    index = settings.exchange_combo.findData(exchange)
    assert index >= 0, f"{exchange} is not selectable in Settings"
    settings.exchange_combo.setCurrentIndex(index)
    settings.api_key_input.setText(key)
    settings.api_secret_input.setText(secret)
    settings.account_add_button.click()


def test_user_can_add_accounts_for_both_new_exchanges(gui) -> None:
    """
    کاربر باید بتواند برای هر دو صرافی حساب بسازد.

    این همان خواستهٔ اصلی است: «کلید و رمز را بزنم وارد حساب بشم».
    """
    app, window, _controller, _qt = gui
    settings = _settings(window)

    for exchange in NEW_EXCHANGES:
        _add_account(settings, exchange, f"KEY-{exchange}-123", f"SECRET-{exchange}-456")

    accounts = app.exchange_accounts.list_accounts(app.auth.user_id)
    stored = {account["exchange"] for account in accounts}
    assert stored == set(NEW_EXCHANGES)


def test_inputs_are_cleared_so_the_key_does_not_stay_on_screen(gui) -> None:
    """پس از افزودن، کلید و رمز نباید روی صفحه بماند."""
    _app, window, _controller, _qt = gui
    settings = _settings(window)
    _add_account(settings, "toobit", "KEY-VISIBLE-1", "SECRET-VISIBLE-1")
    assert settings.api_key_input.text() == ""
    assert settings.api_secret_input.text() == ""


def test_stored_key_is_masked_in_the_table(gui) -> None:
    """جدول باید کلید را پوشیده نشان دهد، نه کامل."""
    _app, window, _controller, _qt = gui
    settings = _settings(window)
    secret_key = "ABCDEFGH-FULL-KEY-12345"
    _add_account(settings, "bitpin", secret_key, "SECRET-XYZ")

    table = settings.accounts_table
    assert table.rowCount() == 1
    shown = [
        table.item(0, column).text()
        for column in range(table.columnCount())
        if table.item(0, column)
    ]
    joined = " ".join(shown)
    assert secret_key not in joined
    assert "SECRET-XYZ" not in joined
    # باید نشانهٔ پوشاندن دیده شود
    assert "•" in joined


def test_secret_is_never_written_to_the_database_in_plain_text(gui, tmp_path) -> None:
    """رمز باید رمزنگاری‌شده ذخیره شود."""
    app, window, _controller, _qt = gui
    settings = _settings(window)
    secret = "PLAINTEXT-CANARY-SECRET-777"
    _add_account(settings, "toobit", "KEY-1", secret)

    # اعتبارنامه باید سالم برگردد
    accounts = app.exchange_accounts.list_accounts(app.auth.user_id)
    creds = app.exchange_accounts.credentials(accounts[0]["id"])
    assert creds["api_secret"] == secret

    # ولی در فایل پایگاه داده به‌صورت متن ساده نباشد
    for db_file in tmp_path.rglob("*.db"):
        assert secret.encode() not in db_file.read_bytes()


def test_test_button_without_selection_warns_instead_of_doing_nothing(gui) -> None:
    """
    دکمهٔ آزمایش بدون انتخاب سطر باید هشدار بدهد.

    دکمهٔ بی‌صدا کاربر را سردرگم می‌کند و باگ‌ها را پنهان نگه می‌دارد.
    """
    _app, window, controller, _qt = gui
    settings = _settings(window)
    _add_account(settings, "toobit", "KEY-1", "SECRET-1")

    seen: list[tuple[str, str]] = []
    controller._toast = lambda message, level="info", **_kw: seen.append((level, message))

    table = settings.accounts_table
    table.clearSelection()
    table.setCurrentCell(-1, -1)
    settings.account_test_button.click()

    assert seen, "the button was silent"
    assert seen[-1][0] == "warning"


def test_connection_test_uses_the_registry_and_reports_success(gui, monkeypatch) -> None:
    """
    آزمایش اتصال موفق باید وضعیت حساب را «متصل» کند.

    ارائه‌دهنده بدل می‌شود تا آزمون به شبکه وابسته نباشد.
    """
    app, window, controller, qt_app = gui
    settings = _settings(window)
    _add_account(settings, "bitpin", "KEY-OK", "SECRET-OK")
    account_id = app.exchange_accounts.list_accounts(app.auth.user_id)[0]["id"]

    monkeypatch.setattr(
        controller,
        "_build_private_provider",
        lambda exchange, api_key, api_secret: _FakeProvider(succeed=True),
    )

    ok, message = asyncio.run(
        app.exchange_accounts.test_connection(
            account_id, controller._build_private_provider
        )
    )
    assert ok is True
    assert message == "exchange.error.verified"

    refreshed = app.exchange_accounts.get_account(account_id)
    assert refreshed["status"] == "connected"


def test_failed_connection_message_is_localized(gui, monkeypatch) -> None:
    """پیام شکست باید به زبان رابط ترجمه شود، نه کلید خام."""
    app, window, controller, _qt = gui
    settings = _settings(window)
    _add_account(settings, "bitpin", "KEY-BAD", "SECRET-BAD")

    localized = controller._localize_exchange_message("exchange.error.bitpin_rejected")
    assert "exchange.error" not in localized
    assert "بیت‌پین" in localized

    # قالب «کلید|پارامتر» هم باید کار کند
    with_reason = controller._localize_exchange_message(
        "exchange.error.connection_failed|TimeoutErrorApp"
    )
    assert "exchange.error" not in with_reason
    assert "TimeoutErrorApp" in with_reason

    # متن ناشناخته باید دست‌نخورده بماند
    assert controller._localize_exchange_message("plain text") == "plain text"


def test_exchange_hint_is_shown_when_selecting_bitpin(gui) -> None:
    """
    انتخاب بیت‌پین باید راهنمای فهرست IP مجاز را نشان دهد.

    بدون این راهنما، کاربر علت رد شدن کلید درست را نمی‌فهمد.
    """
    _app, window, _controller, _qt = gui
    settings = _settings(window)

    settings.exchange_combo.setCurrentIndex(settings.exchange_combo.findData("bitpin"))
    hint = settings.exchange_status.text()
    assert hint
    assert "IP" in hint

    settings.exchange_combo.setCurrentIndex(settings.exchange_combo.findData("toobit"))
    assert settings.exchange_status.text()


def test_switching_exchange_clears_credentials_fields(gui) -> None:
    """تعویض صرافی باید ورودی‌ها را پاک کند تا کلید اشتباه ذخیره نشود."""
    _app, window, _controller, _qt = gui
    settings = _settings(window)

    settings.exchange_combo.setCurrentIndex(settings.exchange_combo.findData("toobit"))
    settings.api_key_input.setText("LEFTOVER-KEY")
    settings.api_secret_input.setText("LEFTOVER-SECRET")

    settings.exchange_combo.setCurrentIndex(settings.exchange_combo.findData("bitpin"))
    assert settings.api_key_input.text() == ""
    assert settings.api_secret_input.text() == ""
