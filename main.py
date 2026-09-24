"""
نقطه ورود برنامه Crypto AI Trader.

اجرا:
    python main.py                 اجرای رابط گرافیکی
    python main.py --check         بررسی سلامت اجزا بدون باز کردن پنجره
    python main.py --signal BTC/USDT   تولید یک سیگنال در خط فرمان

چرا حالت خط فرمان؟
    برای آزمودن منطق بدون نیاز به محیط گرافیکی و برای اجرای خودکار در
    سامانه‌های بدون نمایشگر.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.application import Application  # noqa: E402
from app.core.constants import APP_NAME, APP_VERSION  # noqa: E402
from app.logging import configure_logging, get_logger  # noqa: E402

logger = get_logger(__name__)


async def run_check() -> int:
    """بررسی سلامت اجزای اصلی بدون رابط گرافیکی."""
    application = Application()
    print(f"{APP_NAME} v{APP_VERSION}")
    print(f"  data dir      : {application.paths.data_dir}")
    print(f"  database      : {application.paths.database_file.name}")
    print(f"  settings      : {len(application.settings_repository.get_all())} keys")
    print(f"  indicators    : {len(application.indicators.available_indicators())}")

    from signals.strategies.registry import strategy_registry

    print(f"  strategies    : {strategy_registry.available()}")
    print(f"  ai enabled    : {application.ai_enabled()}")

    await application.start()
    assert application.market is not None
    symbols = await application.market.get_symbols()
    print(f"  exchange      : {application.market.exchange_name} ({len(symbols)} symbols)")

    price = await application.market.get_current_price("BTC/USDT")
    print(f"  BTC/USDT      : {price}")
    await application.stop()
    print("Health check passed.")
    return 0


async def run_signal(symbol: str) -> int:
    """تولید یک سیگنال در خط فرمان."""
    application = Application()
    await application.start()
    try:
        signal = await application.generate_signal(symbol)
        print(f"\n{symbol} → {signal.direction.value} (confidence {signal.confidence}%)")
        print(f"  trend      : {signal.trend.value} | structure: {signal.market_structure.value}")
        if signal.stop_loss:
            print(f"  entry      : {signal.entry_min:.6g} – {signal.entry_max:.6g}")
            print(f"  stop loss  : {signal.stop_loss:.6g}")
            print(f"  targets    : {', '.join(f'{t:.6g}' for t in signal.take_profits)}")
            print(f"  R/R        : {signal.risk_reward} | leverage ×{signal.leverage}")
        print(f"  reason     : {signal.reason[:300]}")
        print("\n  Note: confidence is factor alignment, not a probability of profit.")
    finally:
        await application.stop()
    return 0


def run_gui() -> int:
    """
    اجرای رابط گرافیکی.

    ترتیب کار: ساخت برنامه Qt → خواندن تنظیمات کاربر → ساخت پنجره →
    ویزارد اولین اجرا (در صورت نیاز) → اتصال کنترلر به موتورها.
    """
    from PySide6.QtWidgets import QApplication

    from app.core.constants import Language
    from localization import Translator
    from ui.controllers import MainController
    from ui.themes import ThemeManager
    from ui.themes.fonts import DEFAULT_FONT_KEY
    from ui.windows import MainWindow

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(APP_NAME)
    qt_app.setApplicationVersion(APP_VERSION)

    application = Application()
    language = application.settings.get("ui.language", Language.FA.value)
    theme = application.settings.get("ui.theme", "dark")

    translator = Translator(language)
    theme_manager = ThemeManager()
    # قلم پیش از پوسته تنظیم می‌شود تا اولین برگهٔ سبک همان ابتدا با قلم
    # درست ساخته شود و کاربر «پرش قلم» هنگام باز شدن پنجره نبیند.
    theme_manager.set_font_family(application.settings.get("ui.font_family", DEFAULT_FONT_KEY))
    theme_manager.apply(qt_app, theme)

    window = MainWindow(translator, theme_manager)

    # ویزارد اولین اجرا — پیش از ساخت کنترلر، تا تنظیمات انتخابی کاربر
    # همان ابتدا اعمال شوند و لازم نباشد چیزی دوباره بارگذاری شود.
    if not application.settings.is_first_run_completed:
        from ui.dialogs import FirstRunWizard

        wizard = FirstRunWizard(translator)
        if wizard.exec():
            values = wizard.collected_settings()
            application.settings.set_many(values)
            translator.set_language(values.get("ui.language", language))
            theme_manager.apply(qt_app, values.get("ui.theme", theme))
            application.apply_risk_settings()
            window.retranslate()
        application.settings.mark_first_run_completed()

    controller = MainController(application, window, translator, theme_manager, qt_app)
    # خاموشی تمیز: بستن اتصال‌های شبکه پیش از پایان برنامه
    qt_app.aboutToQuit.connect(controller.shutdown)

    window.show()
    controller.start()
    return qt_app.exec()


def main() -> int:
    """تحلیل آرگومان‌ها و اجرای حالت خواسته‌شده."""
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    parser.add_argument("--check", action="store_true", help="Run a health check and exit")
    parser.add_argument("--signal", metavar="SYMBOL", help="Generate a signal for a symbol and exit")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()

    configure_logging(level=args.log_level)

    if args.check:
        return asyncio.run(run_check())
    if args.signal:
        return asyncio.run(run_signal(args.signal))
    return run_gui()


if __name__ == "__main__":
    # نسخهٔ ۲.۴.۲: استخر فرایند محاسبهٔ پویش در نسخهٔ ساخته‌شده (exe)
    # بدون این خط، هر کارگر یک پنجرهٔ تازهٔ برنامه باز می‌کرد.
    import multiprocessing

    multiprocessing.freeze_support()
    sys.exit(main())
