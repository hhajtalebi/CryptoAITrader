"""
ابزار توسعه: گرفتن تصویر از پنجرهٔ برنامه با دادهٔ نمونه.

این فایل بخشی از برنامه نیست؛ فقط برای بازبینی چشمی طراحی به کار می‌رود.

    QT_QPA_PLATFORM=offscreen python3 tools/preview_shot.py <theme> <page> <out.png>

متغیر محیطی `SHOT_TAB` شمارهٔ زبانهٔ صفحهٔ تنظیمات را باز می‌کند.
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

qt = QApplication.instance() or QApplication([])

from app.application import Application  # noqa: E402
from localization import Translator  # noqa: E402
from ui.controllers import MainController  # noqa: E402
from ui.themes import ThemeManager  # noqa: E402
from ui.windows import MainWindow  # noqa: E402

theme_key = sys.argv[1] if len(sys.argv) > 1 else "glass_dark"
page_index = int(sys.argv[2]) if len(sys.argv) > 2 else 0
out_path = sys.argv[3] if len(sys.argv) > 3 else "/tmp/shot.png"
language = os.environ.get("SHOT_LANG", "fa")

app = Application()
translator = Translator(language)
translator.load()
themes = ThemeManager()
themes.apply(qt, theme_key)

window = MainWindow(translator, themes)
window.resize(1440, 900)
controller = MainController(app, window, translator, themes, qt)

user, _ = app.auth.register("hossein", "Strong!pass1", display_name="حسین حاج‌طالبی")
if user is not None:
    account = app.exchange_accounts.add_account(
        user_id=user["id"], exchange="lbank",
        api_key="ABCD1234567890WXYZ", api_secret="s" * 24,
    )
    app.exchange_account_repository.update_balances(
        account["id"],
        balances={"USDT": 8200.0, "BTC": 0.052, "ETH": 1.4, "SOL": 22.0},
        total_value_usdt=14350.0,
    )
    for symbol, side, entry, exit_price in [
        ("BTC/USDT", "long", 60000, 63000),
        ("ETH/USDT", "short", 3000, 2900),
        ("SOL/USDT", "long", 150, 141),
    ]:
        trade = app.trade_repository.open_trade(
            symbol=symbol, side=side, quantity=0.4,
            entry_price=entry, user_id=user["id"], leverage=5,
        )
        app.trade_repository.close_trade(trade["id"], exit_price=exit_price)
    app.trade_repository.open_trade(
        symbol="BNB/USDT", side="long", quantity=2,
        entry_price=610, user_id=user["id"], leverage=3,
    )

controller._sync_user_chrome()
window.set_connection_card(connected=True, exchange="LBank", detail="۱۳۹۰ بازار")
window.set_connection_indicator(True)
window.set_market_count(1390)
window.set_notification_count(3)
controller.refresh_trades()
controller.refresh_wallet()

random.seed(7)
rows = []
for symbol, price, change in [
    ("BTC/USDT", 77121.85, 2.34), ("ETH/USDT", 3012.4, -0.62),
    ("SOL/USDT", 151.2, 4.11), ("BNB/USDT", 612.5, 0.85),
    ("XRP/USDT", 0.5423, -1.24), ("ADA/USDT", 0.3811, 1.02),
    ("DOGE/USDT", 0.1122, -2.4), ("AVAX/USDT", 24.11, 3.02),
    ("LINK/USDT", 13.4, 0.44), ("ETH/BTC", 0.0391, 0.31),
]:
    history = [price * (1 + random.uniform(-0.03, 0.03)) for _ in range(24)]
    rows.append({
        "symbol": symbol, "price": price, "change_percent": change,
        "volume": random.uniform(1e7, 2e9), "high": price * 1.02,
        "low": price * 0.97, "history": history,
    })

markets = window.pages["nav.markets"]
markets.set_palette(themes.palette)
markets.apply_theme(themes.tokens)
markets.set_watchlist(["BTC/USDT", "ETH/USDT", "SOL/USDT"])
markets.set_toman_rate(112500.0, "nobitex")
markets.set_rows(rows)

controller._populate_indicator_catalog()
analysis = window.pages["nav.analysis"]
analysis.symbol_combo.addItems([row["symbol"] for row in rows])
analysis.symbol_combo.setCurrentText("BTC/USDT")

signals = window.pages["nav.signals"]
signals.apply_theme(themes.tokens)
signals.show_signal({
    "symbol": "BTC/USDT", "direction": "WAIT", "confidence": 78,
    "entry_min": 63200, "entry_max": 63500, "stop_loss": 61800,
    "take_profits": [67900], "risk_reward": 2.4, "leverage": 1,
})
signals.set_history([
    {"id": index + 1, "created_at": "۱۴۰۴/۰۶/۲۰ ۱۰:۵۳", "symbol": symbol,
     "direction": direction, "confidence": confidence,
     "risk_reward": risk_reward, "leverage": leverage}
    for index, (symbol, direction, confidence, risk_reward, leverage) in enumerate([
        ("BTC/USDT", "LONG", 78, 2.4, 3), ("ETH/USDT", "WAIT", 52, 0, 1),
        ("SOL/USDT", "SHORT", 66, 1.8, 5), ("BNB/USDT", "LONG", 71, 2.1, 2),
    ])
])

reports = window.pages["nav.reports"]
reports.apply_theme(themes.tokens)
reports.set_summary({
    "total": 48, "by_direction": {"LONG": 20, "SHORT": 15, "WAIT": 13},
    "average_confidence": 76.0, "top_symbols": {"BTC/USDT": 12, "ETH/USDT": 9},
    "confidence_series": [52, 58, 55, 63, 61, 68, 72, 70, 75, 74, 79, 76, 81, 78],
})
reports.set_preview([
    {"created_at": "۱۴۰۴/۰۶/۲۰", "symbol": "BTC/USDT", "direction": "LONG",
     "confidence": 78, "risk_reward": 2.4, "trend": "صعودی"}
] * 8)

dashboard = window.pages["nav.dashboard"]
dashboard.apply_theme(themes.tokens)
dashboard.set_ticker_items([
    {"symbol": row["symbol"], "price": row["price"], "change": row["change_percent"]}
    for row in rows[:8]
])
dashboard.set_market_rows(rows[:6])

settings_page = window.pages["nav.settings"]
settings_page.load_values(app.settings.export_all())

window.go_to_page(page_index)
tab = os.environ.get("SHOT_TAB")
if tab is not None and page_index == 8:
    settings_page.tabs.setCurrentIndex(int(tab))

window.show()
for _ in range(8):
    qt.processEvents()
window.grab().save(out_path)
print("saved", out_path)
