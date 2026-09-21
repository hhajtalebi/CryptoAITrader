"""
معامله‌گر هوشمند رمزارز — نسخهٔ موبایل (اندروید).

این یک برنامهٔ مستقل است: روی گوشی اجرا می‌شود، خودش داده می‌گیرد و
خودش تحلیل می‌کند. به کامپیوتر یا سرور نیازی ندارد.

چرا Kivy و نه PySide6؟
    Qt for Python روی اندروید بسته‌بندی رسمی و پایداری ندارد. Kivy تنها
    مسیر آزموده‌شده برای APK پایتونی است. بنابراین **رابط** از نو نوشته
    شده ولی **موتور** همان است: همان فرمول‌ها، همان آستانه‌ها، همان
    منطق «منتظر».

چه چیزی عمداً اینجا نیست؟
    کلید API و معاملهٔ واقعی. روی گوشیِ گم‌شدنی، نگه‌داشتن کلید صرافی
    ریسکی است که ارزشش را ندارد. نسخهٔ موبایل فقط می‌خواند و تحلیل
    می‌کند.
"""

from __future__ import annotations

import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.utils import get_color_from_hex

from app.market_lite import MarketError, fetch_candles
from app.signal_lite import analyse

# پالت «سرمه‌ای اداری» — همان تم پیش‌فرض نسخهٔ دسکتاپ.
BG = get_color_from_hex("#0F1724")
CARD = get_color_from_hex("#16213A")
TEXT = get_color_from_hex("#E6EDF7")
MUTED = get_color_from_hex("#8FA3C0")
GREEN = get_color_from_hex("#2ECC71")
RED = get_color_from_hex("#E74C3C")
AMBER = get_color_from_hex("#F1C40F")
ACCENT = get_color_from_hex("#3B82F6")

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "BNB/USDT"]
TIMEFRAMES = ["15m", "1h", "4h", "1d"]

# فونت فارسی. اگر نبود، Kivy به فونت پیش‌فرض برمی‌گردد و برنامه
# نمی‌شکند — فقط ظاهر ضعیف‌تر می‌شود.
try:
    LabelBase.register(name="fa", fn_regular="assets/Vazirmatn-Regular.ttf")
    FONT = "fa"
except OSError:
    FONT = "Roboto"


def shape(text: str) -> str:
    """
    آماده‌سازی متن فارسی برای نمایش راست‌به‌چپ.

    Kivy خودش حروف فارسی را به هم نمی‌چسباند. اگر کتابخانه‌های شکل‌دهی
    در دسترس بودند استفاده می‌شوند، وگرنه متن خام برمی‌گردد.
    """
    try:
        import arabic_reshaper  # noqa: PLC0415
        from bidi.algorithm import get_display  # noqa: PLC0415

        return get_display(arabic_reshaper.reshape(text))
    except ImportError:
        return text


class SignalCard(BoxLayout):
    """کارت نمایش یک سیگنال."""

    def __init__(self, signal, **kwargs) -> None:  # noqa: ANN001
        super().__init__(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(12),
            spacing=dp(6),
            **kwargs,
        )
        colors = {"LONG": GREEN, "SHORT": RED, "WAIT": AMBER}
        labels = {"LONG": "خرید", "SHORT": "فروش", "WAIT": "منتظر"}
        color = colors.get(signal.direction, MUTED)

        # نماد لاتین است و نباید راست‌به‌چپ بشود.
        self._add(f"{signal.symbol}   {labels.get(signal.direction, '')}", color, 20, True)
        self._add(shape(f"قیمت: {signal.price:,.2f}"), TEXT, 15)
        self._add(shape(f"اطمینان: {signal.confidence:.0f}٪"), color, 15)

        if signal.is_tradeable:
            self._add(
                shape(f"ورود: {signal.entry_low:,.2f} تا {signal.entry_high:,.2f}"),
                TEXT,
                14,
            )
            self._add(shape(f"حد ضرر: {signal.stop_loss:,.2f}"), RED, 14)
            targets = "  ".join(f"{t:,.2f}" for t in signal.take_profits)
            self._add(shape(f"اهداف: {targets}"), GREEN, 14)
            self._add(
                shape(
                    f"سود به زیان: {signal.risk_reward}   "
                    f"اعتبار: {signal.valid_minutes} دقیقه"
                ),
                MUTED,
                13,
            )

        for reason in signal.reasons:
            self._add(shape(f"• {reason}"), MUTED, 13)

        self.bind(minimum_height=self.setter("height"))

    def _add(self, text: str, color, size: int, mono: bool = False) -> None:  # noqa: ANN001
        label = Label(
            text=text,
            color=color,
            font_size=dp(size),
            font_name="Roboto" if mono else FONT,
            size_hint_y=None,
            halign="right",
            valign="middle",
        )
        label.bind(
            width=lambda inst, value: setattr(inst, "text_size", (value, None)),
            texture_size=lambda inst, value: setattr(inst, "height", value[1] + dp(4)),
        )
        self.add_widget(label)


class TraderApp(App):
    """برنامهٔ اصلی."""

    def build(self):  # noqa: ANN201
        from kivy.core.window import Window

        Window.clearcolor = BG
        self.title = "معامله‌گر هوشمند رمزارز"

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        header = Label(
            text=shape("معامله‌گر هوشمند رمزارز"),
            color=TEXT,
            font_name=FONT,
            font_size=dp(22),
            size_hint_y=None,
            height=dp(46),
        )
        root.add_widget(header)

        controls = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.symbol_spinner = Spinner(
            text=SYMBOLS[0], values=SYMBOLS, background_color=CARD, color=TEXT
        )
        self.timeframe_spinner = Spinner(
            text="1h", values=TIMEFRAMES, background_color=CARD, color=TEXT,
            size_hint_x=0.4,
        )
        controls.add_widget(self.symbol_spinner)
        controls.add_widget(self.timeframe_spinner)
        root.add_widget(controls)

        self.analyse_button = Button(
            text=shape("تحلیل کن"),
            font_name=FONT,
            font_size=dp(17),
            size_hint_y=None,
            height=dp(52),
            background_color=ACCENT,
            color=TEXT,
        )
        self.analyse_button.bind(on_release=self.on_analyse)
        root.add_widget(self.analyse_button)

        self.scan_button = Button(
            text=shape("پویش همهٔ نمادها"),
            font_name=FONT,
            font_size=dp(16),
            size_hint_y=None,
            height=dp(46),
            background_color=CARD,
            color=TEXT,
        )
        self.scan_button.bind(on_release=self.on_scan)
        root.add_widget(self.scan_button)

        self.status = Label(
            text=shape("یک نماد انتخاب کنید"),
            color=MUTED,
            font_name=FONT,
            font_size=dp(14),
            size_hint_y=None,
            height=dp(30),
        )
        root.add_widget(self.status)

        self.results = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(10)
        )
        self.results.bind(minimum_height=self.results.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self.results)
        root.add_widget(scroll)

        credit = Label(
            text=shape("تولیدکننده: حسین حاج طالبی"),
            color=MUTED,
            font_name=FONT,
            font_size=dp(12),
            size_hint_y=None,
            height=dp(26),
        )
        root.add_widget(credit)
        return root

    # ---- عملیات ----------------------------------------------------
    # شبکه هرگز روی نخ رابط کاربری اجرا نمی‌شود، وگرنه اندروید برنامه را
    # «پاسخ نمی‌دهد» اعلام و می‌بندد.

    def _set_status(self, text: str) -> None:
        Clock.schedule_once(lambda _dt: setattr(self.status, "text", shape(text)))

    def _set_busy(self, busy: bool) -> None:
        def apply(_dt) -> None:  # noqa: ANN001
            self.analyse_button.disabled = busy
            self.scan_button.disabled = busy

        Clock.schedule_once(apply)

    def _show(self, signals: list) -> None:
        def apply(_dt) -> None:  # noqa: ANN001
            self.results.clear_widgets()
            for signal in signals:
                self.results.add_widget(SignalCard(signal))

        Clock.schedule_once(apply)

    def on_analyse(self, _button) -> None:  # noqa: ANN001
        symbol = self.symbol_spinner.text
        timeframe = self.timeframe_spinner.text
        self._set_busy(True)
        self._set_status(f"در حال تحلیل {symbol} ...")
        threading.Thread(
            target=self._work, args=([symbol], timeframe), daemon=True
        ).start()

    def on_scan(self, _button) -> None:  # noqa: ANN001
        timeframe = self.timeframe_spinner.text
        self._set_busy(True)
        self._set_status("در حال پویش همهٔ نمادها ...")
        threading.Thread(
            target=self._work, args=(SYMBOLS, timeframe), daemon=True
        ).start()

    def _work(self, symbols: list[str], timeframe: str) -> None:
        """کار شبکه و محاسبه، روی نخ پس‌زمینه."""
        signals = []
        errors = 0
        for symbol in symbols:
            try:
                highs, lows, closes = fetch_candles(symbol, timeframe, 200)
                signals.append(analyse(symbol, highs, lows, closes, timeframe))
            except MarketError:
                errors += 1
            except (ValueError, OSError):
                errors += 1

        # سیگنال‌های قابل معامله بالاتر بنشینند.
        signals.sort(key=lambda s: (s.is_tradeable, s.confidence), reverse=True)
        self._show(signals)
        if not signals:
            self._set_status("دریافت داده ناموفق بود. اینترنت را بررسی کنید.")
        else:
            suffix = f"  ({errors} ناموفق)" if errors else ""
            self._set_status(f"{len(signals)} نتیجه{suffix}")
        self._set_busy(False)


if __name__ == "__main__":
    TraderApp().run()
