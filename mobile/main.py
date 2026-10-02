"""
معامله‌گر هوشمند رمزارز — نسخهٔ موبایل (اندروید).

برنامهٔ مستقل: روی گوشی داده می‌گیرد و تحلیل می‌کند؛ کامپیوتر یا سرور
لازم نیست. Kivy خالص (Qt for Python روی اندروید بسته‌بندی پایدار ندارد).
**رابط** مخصوص موبایل است ولی **موتور** همان فرمول‌های دسکتاپ است.

عمداً اینجا نیست: کلید API و معاملهٔ واقعی (روی گوشیِ گم‌شدنی، کلید
صرافی ریسکی است که ارزشش را ندارد). فقط خواندن و تحلیل.

پنج صفحه با نوار پایین: بازار، سیگنال‌ها، دیدبان، تحلیل، تنظیمات.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.animation import Animation  # noqa: E402
from kivy.app import App  # noqa: E402
from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.metrics import dp  # noqa: E402
from kivy.uix.boxlayout import BoxLayout  # noqa: E402
from kivy.uix.floatlayout import FloatLayout  # noqa: E402
from kivy.uix.screenmanager import FadeTransition, ScreenManager  # noqa: E402

from app import viewmodel as vm  # noqa: E402
from app.market_lite import MarketError, fetch_candles, fetch_tickers  # noqa: E402
from app.screens import AnalysisScreen, MarketScreen, SettingsScreen, SignalsScreen, WatchlistScreen  # noqa: E402
from app.signal_lite import analyse  # noqa: E402
from app.store import Store  # noqa: E402
from app.widgets import BG, FONT, SURFACE2, BottomNav, RtlLabel, Surface, TEXT  # noqa: E402,F401 — FONT: ثبت فونت

NAV = [
    ("market", "market", "بازار"),
    ("signals", "signals", "سیگنال‌ها"),
    ("watch", "star", "دیدبان"),
    ("analysis", "chart", "تحلیل"),
    ("settings", "settings", "تنظیمات"),
]
TICKER_TTL = 15.0
ANALYSIS_TTL = 45.0


def _friendly(exc: Exception) -> str:
    if isinstance(exc, MarketError):
        return str(exc)
    return "خطا در دریافت داده"


class TraderApp(App):
    title = "معامله‌گر هوشمند رمزارز"

    # ---------------------------------------------------------- ساخت
    def build(self):  # noqa: ANN201
        Window.clearcolor = BG
        self.store = Store(self.user_data_dir)
        self.pool = ThreadPoolExecutor(max_workers=4)
        self._tickers: list[dict] = []
        self._tickers_at = 0.0
        self._tickers_loading: list = []
        self._analysis: dict[tuple[str, str], tuple[float, tuple]] = {}
        self._watch_dirty = False
        self._scan_token = 0
        self._history: list[str] = []

        root = FloatLayout()
        column = BoxLayout(orientation="vertical")
        self.manager = ScreenManager(transition=FadeTransition(duration=0.12))
        self.screens = {
            "market": MarketScreen(name="market"),
            "signals": SignalsScreen(name="signals"),
            "watch": WatchlistScreen(name="watch"),
            "analysis": AnalysisScreen(name="analysis"),
            "settings": SettingsScreen(name="settings"),
        }
        for screen in self.screens.values():
            self.manager.add_widget(screen)
        column.add_widget(self.manager)
        self.nav = BottomNav(NAV, self.go)
        column.add_widget(self.nav)
        root.add_widget(column)

        self._toast = Surface(size_hint=(None, None), height=dp(42), radius=dp(21), bg=SURFACE2,
                              padding=(dp(18), 0), opacity=0)
        self._toast_label = RtlLabel(raw="", auto_height=False, align="center", color=TEXT)
        self._toast.add_widget(self._toast_label)
        root.add_widget(self._toast)

        Window.bind(on_keyboard=self._on_key)
        self._refresh_event = None
        self._schedule_refresh()
        Clock.schedule_once(lambda _dt: self.go("market"), 0)
        return root

    def on_stop(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)

    # ---------------------------------------------------------- ناوبری
    def go(self, key: str, remember: bool = True) -> None:
        current = self.manager.current
        if remember and current != key:
            self._history.append(current)
            self._history = self._history[-10:]
        self.manager.current = key
        self.nav.set_active(key)
        screen = self.screens[key]
        if key == "watch" or (key == "market" and self._watch_dirty):
            self._watch_dirty = False if key == "market" else self._watch_dirty
            if key == "market":
                screen.render()
        screen.refresh(force=False)

    def open_analysis(self, symbol: str) -> None:
        self.go("analysis")
        self.screens["analysis"].show(symbol)

    def _on_key(self, _window, key, *_args) -> bool:  # noqa: ANN001
        if key == 27:  # دکمهٔ بازگشت اندروید
            if self._history:
                self.go(self._history.pop(), remember=False)
                return True
            return False  # خروج
        return False

    def mark_watch_dirty(self) -> None:
        self._watch_dirty = True

    def settings_changed(self, key: str) -> None:
        if key == "refresh_seconds":
            self._schedule_refresh()
        if key in ("timeframe", "scan_size"):
            self.screens["signals"].signals = []

    def _schedule_refresh(self) -> None:
        if self._refresh_event is not None:
            self._refresh_event.cancel()
            self._refresh_event = None
        seconds = self.store.get("refresh_seconds")
        if seconds:
            self._refresh_event = Clock.schedule_interval(self._auto_refresh, seconds)

    def _auto_refresh(self, _dt) -> None:  # noqa: ANN001
        current = self.manager.current
        if current in ("market", "watch", "analysis"):
            self.screens[current].refresh(force=True)

    # ---------------------------------------------------------- پیام کوتاه
    def toast(self, text: str) -> None:
        from kivy.core.text import Label as CoreLabel  # noqa: PLC0415

        from app.widgets import shape  # noqa: PLC0415

        self._toast_label.raw = text
        width = CoreLabel(font_name=self._toast_label.font_name, font_size=self._toast_label.font_size).get_extents(shape(text))[0]
        self._toast.width = min(width + dp(40), Window.width - dp(32))
        self._toast.x = (Window.width - self._toast.width) / 2
        self._toast.y = dp(80)
        Animation.cancel_all(self._toast)
        (Animation(opacity=1, d=0.15) + Animation(d=1.8) + Animation(opacity=0, d=0.3)).start(self._toast)

    # ---------------------------------------------------------- داده (پس‌زمینه)
    def _bg(self, work, done, fail) -> None:  # noqa: ANN001
        """کار روی نخ پس‌زمینه؛ نتیجه روی نخ رابط."""
        def runner() -> None:
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001
                message = _friendly(exc)
                Clock.schedule_once(lambda _dt: fail(message))
                return
            Clock.schedule_once(lambda _dt: done(result))

        self.pool.submit(runner)

    def load_tickers(self, done, fail, force: bool = False) -> None:  # noqa: ANN001
        fresh = time.time() - self._tickers_at < TICKER_TTL
        if self._tickers and fresh and not force:
            done(self._tickers)
            return
        self._tickers_loading.append((done, fail))
        if len(self._tickers_loading) > 1:
            return  # یک درخواست در جریان است؛ همه منتظر همان می‌مانند

        def ok(rows: list[dict]) -> None:
            self._tickers, self._tickers_at = rows, time.time()
            waiting, self._tickers_loading = self._tickers_loading, []
            for d, _f in waiting:
                d(rows)

        def bad(message: str) -> None:
            waiting, self._tickers_loading = self._tickers_loading, []
            for _d, f in waiting:
                f(message)

        if force:
            from app import market_lite  # noqa: PLC0415

            market_lite._cache.clear()  # noqa: SLF001
        self._bg(fetch_tickers, ok, bad)

    def _analyse_sync(self, symbol: str, timeframe: str, force: bool = False) -> tuple:
        key = (symbol, timeframe)
        cached = self._analysis.get(key)
        if cached and not force and time.time() - cached[0] < ANALYSIS_TTL:
            return cached[1]
        highs, lows, closes = fetch_candles(symbol, timeframe, 200)
        result = (symbol, timeframe, analyse(symbol, highs, lows, closes, timeframe), highs, lows, closes)
        self._analysis[key] = (time.time(), result)
        return result

    def analyse_one(self, symbol: str, timeframe: str, done, fail, force: bool = False) -> None:  # noqa: ANN001
        self._bg(lambda: self._analyse_sync(symbol, timeframe, force), done, fail)

    def analyse_many(self, symbols: list[str], timeframe: str, done, force: bool = False) -> None:  # noqa: ANN001
        def work() -> list:
            out = []
            for symbol in symbols:
                try:
                    out.append(self._analyse_sync(symbol, timeframe, force)[2])
                except Exception:  # noqa: BLE001, S112
                    continue
            return out

        self._bg(work, done, lambda _m: None)

    def scan(self, timeframe: str, size: int, progress, done, fail) -> None:  # noqa: ANN001
        """پویش پرحجم‌ترین نمادها؛ پیشرفت زنده؛ پویش تازه، قبلی را بی‌اثر می‌کند."""
        self._scan_token += 1
        token = self._scan_token

        def work() -> list:
            rows = self._tickers if time.time() - self._tickers_at < 60 and self._tickers else fetch_tickers()
            self._tickers, self._tickers_at = rows, time.time()
            symbols = vm.scan_universe(rows, size)
            results: list = []
            lock = threading.Lock()
            counter = [0]

            def one(symbol: str) -> None:
                try:
                    signal = self._analyse_sync(symbol, timeframe)[2]
                    with lock:
                        results.append(signal)
                except Exception:  # noqa: BLE001, S110
                    pass
                with lock:
                    counter[0] += 1
                    n = counter[0]
                if token == self._scan_token:
                    Clock.schedule_once(lambda _dt: progress(n, len(symbols)))

            with ThreadPoolExecutor(max_workers=4) as inner:
                list(inner.map(one, symbols))
            if not results:
                raise MarketError("دریافت داده ناموفق بود")
            return results

        def finished(results: list) -> None:
            if token == self._scan_token:
                done(results)

        self._bg(work, finished, fail)


if __name__ == "__main__":
    TraderApp().run()
