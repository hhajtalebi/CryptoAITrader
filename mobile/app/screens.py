"""
صفحه‌های برنامهٔ موبایل: بازار، سیگنال‌ها، دیدبان، تحلیل، تنظیمات.

اصل طراحی: هر صفحه **یک کار** را خوب انجام می‌دهد؛ اطلاعات ثانویه کوچک‌تر
و کم‌رنگ‌تر است؛ هیچ کاری روی نخ رابط کاربری شبکه نمی‌زند.
"""

from __future__ import annotations

from kivy.app import App
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from . import viewmodel as vm
from .store import REFRESH_CHOICES, SCAN_SIZES, TIMEFRAMES
from .widgets import (
    ACCENT,
    AMBER,
    BG,
    BORDER,
    DIRECTION_TONE,
    FAINT,
    GREEN,
    MUTED,
    RED,
    SURFACE,
    SURFACE2,
    TEXT,
    TONE,
    Card,
    Chip,
    ChipGroup,
    Icon,
    IconButton,
    Meter,
    Pill,
    RtlLabel,
    Spacer,
    Sparkline,
    Surface,
    Tappable,
    label,
    shape,
    tint,
)

TF_TITLES = {"15m": "۱۵ دقیقه", "1h": "۱ ساعت", "4h": "۴ ساعت", "1d": "روزانه"}


def app():  # noqa: ANN201
    return App.get_running_app()


# ================================================================ پایه
class BaseScreen(Screen):
    """صفحه با سرتیتر ثابت و بدنهٔ اسکرول‌شونده."""

    title = ""
    subtitle = ""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical")
        self.header = BoxLayout(size_hint_y=None, height=dp(64), padding=(dp(8), dp(8), dp(18), 0), spacing=dp(4))
        self.actions = BoxLayout(size_hint_x=None, width=dp(96), spacing=0)
        self.header.add_widget(self.actions)
        titles = BoxLayout(orientation="vertical", padding=(0, dp(4), 0, 0))
        self.title_label = label(self.title, 22, TEXT, auto_height=False, size_hint_y=0.62)
        self.subtitle_label = label(self.subtitle, 12, MUTED, auto_height=False, size_hint_y=0.38)
        titles.add_widget(self.title_label)
        titles.add_widget(self.subtitle_label)
        self.header.add_widget(titles)
        root.add_widget(self.header)
        self.body = BoxLayout(orientation="vertical", padding=(dp(14), dp(4), dp(14), 0), spacing=dp(10))
        root.add_widget(self.body)
        self.add_widget(root)

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.raw = text

    def scroll_column(self) -> tuple[ScrollView, BoxLayout]:
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3), bar_color=tint(MUTED, 0.5), bar_inactive_color=tint(MUTED, 0.15))
        column = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10), padding=(0, 0, 0, dp(16)))
        column.bind(minimum_height=column.setter("height"))
        scroll.add_widget(column)
        return scroll, column

    def refresh(self, force: bool = False) -> None:  # noqa: ARG002 — در زیرکلاس‌ها
        return


class StateView(BoxLayout):
    """حالت خالی/بارگذاری/خطا — همیشه با توضیح و راه بعدی."""

    def __init__(self, icon: str, text: str, hint: str = "", **kwargs) -> None:
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(220), padding=dp(24), spacing=dp(10), **kwargs)
        holder = BoxLayout(size_hint_y=None, height=dp(56))
        holder.add_widget(Widget())
        holder.add_widget(Icon(name=icon, color=FAINT, size=(dp(48), dp(48))))
        holder.add_widget(Widget())
        self.add_widget(holder)
        self.add_widget(label(text, 16, TEXT, align="center"))
        if hint:
            self.add_widget(label(hint, 13, MUTED, align="center"))


# ================================================================ بازار
class MarketRow(RecycleDataViewBehavior, Tappable):
    """یک ردیف بازار: نماد (راست)، قیمت و حجم، درصد تغییر (چپ)، ستاره."""

    def __init__(self, **kwargs) -> None:
        super().__init__(orientation="horizontal", padding=(dp(6), 0, dp(14), 0), spacing=dp(8),
                         radius=dp(14), bg=SURFACE, border=[0, 0, 0, 0], **kwargs)
        self.symbol = ""
        self.star = IconButton("star", color=FAINT)
        self.star.bind(on_release=self._toggle_star)
        self.change = Pill("+0.00%", "flat", size=13)
        change_box = BoxLayout(size_hint_x=None, width=dp(84), padding=(0, dp(20)))
        change_box.add_widget(self.change)
        prices = BoxLayout(orientation="vertical", padding=(0, dp(12)))
        self.price = label("", 15, TEXT, auto_height=False, align="right")
        self.volume = label("", 11, MUTED, auto_height=False, align="right")
        prices.add_widget(self.price)
        prices.add_widget(self.volume)
        names = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(104), padding=(0, dp(12)))
        self.base = label("", 16, TEXT, auto_height=False, align="right")
        self.quote = label("/USDT", 11, FAINT, auto_height=False, align="right")
        names.add_widget(self.base)
        names.add_widget(self.quote)
        for w in (self.star, change_box, prices, names):
            self.add_widget(w)

    def refresh_view_attrs(self, rv, index, data):  # noqa: ANN001, ANN201
        self.symbol = data["symbol"]
        self.base.raw = data["base"]
        self.price.raw = data["price_text"]
        self.volume.raw = f"Vol {data['volume_text']}"
        self.change.set(data["change_text"], data["trend"])
        self.change.x = self.change.parent.right - self.change.width if self.change.parent else 0
        self.star.icon.name = "star_fill" if data["watched"] else "star"
        self.star.icon.color = AMBER if data["watched"] else FAINT
        return True

    def _toggle_star(self, *_a) -> None:  # noqa: ANN002
        watched = app().store.toggle_watch(self.symbol)
        self.star.icon.name = "star_fill" if watched else "star"
        self.star.icon.color = AMBER if watched else FAINT
        app().toast(f"{self.symbol} {'به دیدبان اضافه شد' if watched else 'از دیدبان حذف شد'}")
        app().mark_watch_dirty()

    def on_release(self) -> None:
        app().open_analysis(self.symbol)


class MarketScreen(BaseScreen):
    title = "بازار"
    subtitle = "LBank · تغییرات ۲۴ ساعته"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        refresh = IconButton("refresh")
        refresh.bind(on_release=lambda *_: self.refresh(force=True))
        self.actions.add_widget(refresh)
        self.sort = "volume"
        self.query = ""
        self.rows: list[dict] = []

        # خلاصهٔ وضعیت بازار
        self.breadth = Card(padding=(dp(16), dp(12)), spacing=dp(8))
        top = BoxLayout(size_hint_y=None, height=dp(24))
        self.breadth_avg = Pill("—", "flat", size=12)
        top.add_widget(self.breadth_avg)
        top.add_widget(label("حال‌وهوای بازار", 14, TEXT, auto_height=False))
        self.breadth.add_widget(top)
        self.breadth_bar = Meter(height=dp(8), color=GREEN)
        with self.breadth_bar.canvas.before:
            pass
        self.breadth.add_widget(self.breadth_bar)
        self.breadth_text = label("در حال دریافت…", 12, MUTED)
        self.breadth.add_widget(self.breadth_text)
        self.body.add_widget(self.breadth)

        # جست‌وجو
        search = Surface(size_hint_y=None, height=dp(46), radius=dp(14), padding=(dp(12), 0, dp(8), 0), spacing=dp(6))
        self.search_input = TextInput(
            hint_text=shape("جست‌وجوی نماد، مثلاً BTC"), multiline=False, font_name="fa" if _has_fa() else "Roboto",
            background_color=[0, 0, 0, 0], foreground_color=TEXT, hint_text_color=FAINT, cursor_color=ACCENT,
            font_size=sp(15), padding=(dp(4), dp(12)), halign="right", write_tab=False,
        )
        self.search_input.bind(text=self._on_search)
        search.add_widget(self.search_input)
        icon_box = BoxLayout(size_hint_x=None, width=dp(28), padding=(0, dp(11)))
        icon_box.add_widget(Icon(name="search", color=FAINT, size=(dp(22), dp(22))))
        search.add_widget(icon_box)
        self.body.add_widget(search)

        self.sort_chips = ChipGroup([("حجم", "volume"), ("بیشترین رشد", "gainers"), ("بیشترین ریزش", "losers")],
                                    "volume", self._on_sort)
        self.body.add_widget(self.sort_chips)

        self.list = RecycleView(do_scroll_x=False, bar_width=dp(3), bar_color=tint(MUTED, 0.5))
        layout = RecycleBoxLayout(orientation="vertical", default_size=(None, dp(66)), default_size_hint=(1, None),
                                  size_hint_y=None, spacing=dp(6), padding=(0, 0, 0, dp(12)))
        layout.bind(minimum_height=layout.setter("height"))
        self.list.add_widget(layout)
        self.list.viewclass = MarketRow
        self.state = StateView("market", "در حال دریافت بازار…", "چند ثانیه صبر کنید")
        self.list_holder = BoxLayout()
        self.list_holder.add_widget(self.state)
        self.body.add_widget(self.list_holder)

    def _on_sort(self, value) -> None:  # noqa: ANN001
        self.sort = value
        self.render()

    def _on_search(self, _inst, text: str) -> None:
        self.query = text
        self.render()

    def refresh(self, force: bool = False) -> None:
        app().load_tickers(self._loaded, self._failed, force=force)

    def _loaded(self, rows: list[dict]) -> None:
        self.rows = rows
        self.render()

    def _failed(self, message: str) -> None:
        if not self.rows:
            self._show_state(StateView("market", message, "اتصال اینترنت را بررسی کنید و دوباره تلاش کنید."))
        app().toast(message)

    def _show_state(self, widget) -> None:  # noqa: ANN001
        self.list_holder.clear_widgets()
        self.list_holder.add_widget(widget)

    def render(self) -> None:
        if not self.rows:
            return
        b = vm.market_breadth(self.rows)
        self.breadth_avg.set(vm.format_change(b["avg"]), vm.trend_of(b["avg"]))
        total = (b["up"] + b["down"]) or 1
        self.breadth_bar.value = b["up"] / total * 100
        self.breadth_text.raw = f"{b['up']} نماد مثبت · {b['down']} نماد منفی  (از {b['count']} نماد نقدشونده)"
        store = app().store
        items = vm.filter_and_sort(self.rows, self.query, self.sort, limit=150)
        self.list.data = [
            {
                "symbol": r["symbol"], "base": r["base"], "price_text": vm.format_price(r["price"]),
                "change_text": vm.format_change(r["change"]), "trend": vm.trend_of(r["change"]),
                "volume_text": vm.format_volume(r["turnover"]), "watched": store.is_watched(r["symbol"]),
            }
            for r in items
        ]
        if not items:
            self._show_state(StateView("search", "نمادی پیدا نشد", "نام لاتین نماد را بنویسید، مثلاً ETH"))
        elif self.list.parent is None:
            self._show_state(self.list)


def _has_fa() -> bool:
    from .widgets import FONT  # noqa: PLC0415

    return FONT == "fa"


# ================================================================ کارت سیگنال
def level_row(title: str, value: str, extra: str, color) -> BoxLayout:  # noqa: ANN001
    row = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(6))
    row.add_widget(label(extra, 12, FAINT, auto_height=False, align="left", size_hint_x=0.3))
    row.add_widget(label(value, 14, color, auto_height=False, align="right", size_hint_x=0.4))
    row.add_widget(label(title, 13, MUTED, auto_height=False, align="right", size_hint_x=0.3))
    return row


class SignalCard(Tappable):
    """کارت فشردهٔ سیگنال؛ لمس ← صفحهٔ تحلیل."""

    def __init__(self, signal, compact: bool = True, **kwargs) -> None:  # noqa: ANN001
        super().__init__(orientation="vertical", size_hint_y=None, padding=(dp(16), dp(14)), spacing=dp(8), **kwargs)
        self.bind(minimum_height=self.setter("height"))
        self.signal = signal
        tone = DIRECTION_TONE.get(signal.direction, "flat")
        color = TONE[tone]

        head = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(8))
        head.add_widget(label(f"{signal.confidence:.0f}%", 18, color, auto_height=False, align="left", size_hint_x=0.3))
        head.add_widget(Widget())
        head.add_widget(Pill(vm.direction_label(signal.direction), tone, size=13))
        head.add_widget(label(signal.symbol.split("/")[0], 18, TEXT, auto_height=False, align="right",
                              size_hint_x=None, width=dp(86)))
        self.add_widget(head)
        meter = Meter(color=color)
        meter.value = signal.confidence
        self.add_widget(meter)
        sub = f"اطمینان {vm.confidence_level(signal.confidence)} · {TF_TITLES.get(signal.timeframe, signal.timeframe)} · قیمت {vm.format_price(signal.price)}"
        self.add_widget(label(sub, 12, MUTED))

        if signal.is_tradeable:
            entry = (signal.entry_low + signal.entry_high) / 2 or signal.price
            self.add_widget(level_row("ورود", f"{vm.format_price(signal.entry_low)} – {vm.format_price(signal.entry_high)}", "", TEXT))
            self.add_widget(level_row("حد ضرر", vm.format_price(signal.stop_loss), vm.percent_from(entry, signal.stop_loss), RED))
            targets = signal.take_profits if not compact else signal.take_profits[:1]
            for i, t in enumerate(targets, 1):
                self.add_widget(level_row(f"هدف {i}", vm.format_price(t), vm.percent_from(entry, t), GREEN))
            if not compact:
                self.add_widget(level_row("سود به زیان", f"{signal.risk_reward}", f"{signal.valid_minutes} دقیقه اعتبار", TEXT))
        elif signal.reasons:
            self.add_widget(label(signal.reasons[0], 13, FAINT))

    def on_release(self) -> None:
        app().open_analysis(self.signal.symbol)


# ================================================================ سیگنال‌ها
class SignalsScreen(BaseScreen):
    title = "سیگنال‌ها"
    subtitle = ""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        refresh = IconButton("refresh")
        refresh.bind(on_release=lambda *_: self.refresh(force=True))
        self.actions.add_widget(refresh)
        store = app().store
        self.tf_chips = ChipGroup([(TF_TITLES[t], t) for t in TIMEFRAMES], store.get("timeframe"), self._on_tf)
        self.body.add_widget(self.tf_chips)

        filters = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        self.only_chip = Chip("فقط قابل معامله", selected=store.get("tradeable_only"))
        self.only_chip.bind(on_release=self._toggle_only)
        self.counts = BoxLayout(spacing=dp(6))
        filters.add_widget(self.counts)
        filters.add_widget(self.only_chip)
        self.body.add_widget(filters)

        self.progress = Meter(height=dp(3), color=ACCENT)
        self.body.add_widget(self.progress)
        scroll, self.column = self.scroll_column()
        self.body.add_widget(scroll)
        self.signals: list = []
        self.column.add_widget(StateView("signals", "برای شروع، پویش را بزنید", "پرحجم‌ترین نمادهای بازار تحلیل می‌شوند."))
        self._update_subtitle()

    def _update_subtitle(self) -> None:
        store = app().store
        self.set_subtitle(f"{store.get('scan_size')} نماد پرحجم · {TF_TITLES[store.get('timeframe')]}")

    def _on_tf(self, tf: str) -> None:
        app().store.set("timeframe", tf)
        self._update_subtitle()
        self.refresh(force=True)

    def _toggle_only(self, chip: Chip) -> None:
        chip.selected = not chip.selected
        app().store.set("tradeable_only", chip.selected)
        self.render()

    def refresh(self, force: bool = False) -> None:
        store = app().store
        self.tf_chips.select(store.get("timeframe"))
        self.only_chip.selected = store.get("tradeable_only")
        self._update_subtitle()
        if self.signals and not force:
            return
        self.progress.value = 2
        app().scan(store.get("timeframe"), store.get("scan_size"), self._progress, self._done, self._failed)

    def _progress(self, done: int, total: int) -> None:
        self.progress.value = done / max(total, 1) * 100
        self.set_subtitle(f"در حال پویش… {done} از {total}")

    def _done(self, signals: list) -> None:
        self.signals = signals
        self.progress.value = 0
        self._update_subtitle()
        self.render()

    def _failed(self, message: str) -> None:
        self.progress.value = 0
        self._update_subtitle()
        if not self.signals:
            self.column.clear_widgets()
            self.column.add_widget(StateView("signals", message, "اتصال اینترنت را بررسی کنید."))
        app().toast(message)

    def render(self) -> None:
        self.counts.clear_widgets()
        n_long = sum(1 for s in self.signals if s.direction == "LONG" and s.is_tradeable)
        n_short = sum(1 for s in self.signals if s.direction == "SHORT" and s.is_tradeable)
        n_wait = len(self.signals) - n_long - n_short
        self.counts.add_widget(Widget())
        for text, tone in ((f"منتظر {n_wait}", "wait"), (f"فروش {n_short}", "down"), (f"خرید {n_long}", "up")):
            self.counts.add_widget(Pill(text, tone, size=12))
        self.column.clear_widgets()
        items = vm.sort_signals(self.signals, app().store.get("tradeable_only"))
        if not items:
            self.column.add_widget(StateView("signals", "فعلاً سیگنال قابل معامله‌ای نیست",
                                             "«منتظر» هم یک پاسخ است: یعنی عامل‌ها هم‌سو نیستند."))
            return
        for s in items:
            self.column.add_widget(SignalCard(s))


# ================================================================ دیدبان
class WatchRow(Tappable):
    def __init__(self, symbol: str, ticker: dict | None, signal, **kwargs) -> None:  # noqa: ANN001
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(72), padding=(dp(6), 0, dp(14), 0),
                         spacing=dp(8), radius=dp(14), border=[0, 0, 0, 0], **kwargs)
        self.symbol = symbol
        remove = IconButton("star_fill", color=AMBER)
        remove.bind(on_release=self._remove)
        self.add_widget(remove)
        right = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(90), padding=(0, dp(14)))
        if signal is not None:
            tone = DIRECTION_TONE.get(signal.direction, "flat") if signal.is_tradeable else "wait"
            text = vm.direction_label(signal.direction if signal.is_tradeable else "WAIT")
            holder = BoxLayout(size_hint_y=None, height=dp(26))
            holder.add_widget(Pill(f"{text} {signal.confidence:.0f}%", tone, size=12))
            right.add_widget(holder)
        else:
            right.add_widget(label("…", 12, FAINT, auto_height=False, align="left"))
        self.add_widget(right)
        mid = BoxLayout(orientation="vertical", padding=(0, dp(14)))
        if ticker:
            mid.add_widget(label(vm.format_price(ticker["price"]), 15, TEXT, auto_height=False, align="right"))
            color = TONE[vm.trend_of(ticker["change"])]
            mid.add_widget(label(vm.format_change(ticker["change"]), 12, color, auto_height=False, align="right"))
        else:
            mid.add_widget(label("—", 15, MUTED, auto_height=False, align="right"))
        self.add_widget(mid)
        name = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(96), padding=(0, dp(14)))
        name.add_widget(label(symbol.split("/")[0], 17, TEXT, auto_height=False, align="right"))
        name.add_widget(label("/" + symbol.split("/")[-1], 11, FAINT, auto_height=False, align="right"))
        self.add_widget(name)

    def _remove(self, *_a) -> None:  # noqa: ANN002
        app().store.toggle_watch(self.symbol)
        app().toast(f"{self.symbol} از دیدبان حذف شد")
        app().mark_watch_dirty()
        app().screens["watch"].render()

    def on_release(self) -> None:
        app().open_analysis(self.symbol)


class WatchlistScreen(BaseScreen):
    title = "دیدبان"
    subtitle = "نمادهای منتخب شما"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        refresh = IconButton("refresh")
        refresh.bind(on_release=lambda *_: self.refresh(force=True))
        self.actions.add_widget(refresh)
        scroll, self.column = self.scroll_column()
        self.body.add_widget(scroll)
        self.tickers: dict[str, dict] = {}
        self.signals: dict[str, object] = {}

    def refresh(self, force: bool = False) -> None:
        self.render()
        app().load_tickers(self._tickers, lambda m: app().toast(m), force=force)
        symbols = app().store.watchlist
        if symbols:
            app().analyse_many(symbols, app().store.get("timeframe"), self._signals, force=force)

    def _tickers(self, rows: list[dict]) -> None:
        self.tickers = {r["symbol"]: r for r in rows}
        self.render()

    def _signals(self, signals: list) -> None:
        self.signals = {s.symbol: s for s in signals}
        self.render()

    def render(self) -> None:
        self.column.clear_widgets()
        symbols = app().store.watchlist
        tf = TF_TITLES[app().store.get("timeframe")]
        self.set_subtitle(f"{len(symbols)} نماد · سیگنال {tf}")
        if not symbols:
            self.column.add_widget(StateView("star", "دیدبان خالی است",
                                             "در صفحهٔ بازار روی ستارهٔ هر نماد بزنید تا اینجا بیاید."))
            return
        for symbol in symbols:
            self.column.add_widget(WatchRow(symbol, self.tickers.get(symbol), self.signals.get(symbol)))


# ================================================================ تحلیل
class Tile(Surface):
    def __init__(self, title: str, value: str, tone: str, note: str, **kwargs) -> None:
        super().__init__(orientation="vertical", padding=(dp(14), dp(10)), spacing=dp(2), radius=dp(14),
                         size_hint_y=None, height=dp(84), **kwargs)
        self.add_widget(label(title, 12, MUTED, auto_height=False))
        self.add_widget(label(value, 19, TONE.get(tone, TEXT) if tone != "flat" else TEXT, auto_height=False))
        self.add_widget(label(note, 11, FAINT, auto_height=False))


class AnalysisScreen(BaseScreen):
    title = "تحلیل"
    subtitle = ""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.star = IconButton("star")
        self.star.bind(on_release=self._toggle_star)
        refresh = IconButton("refresh")
        refresh.bind(on_release=lambda *_: self.refresh(force=True))
        self.actions.add_widget(refresh)
        self.actions.add_widget(self.star)
        self.symbol = "BTC/USDT"
        self.timeframe = app().store.get("timeframe")

        quick = ScrollView(do_scroll_y=False, size_hint_y=None, height=dp(36), bar_width=0)
        self.quick_row = BoxLayout(size_hint_x=None, spacing=dp(8))
        self.quick_row.bind(minimum_width=self.quick_row.setter("width"))
        quick.add_widget(self.quick_row)
        self.body.add_widget(quick)

        scroll, self.column = self.scroll_column()
        self.body.add_widget(scroll)

        # قیمت
        self.price_card = Card(spacing=dp(6))
        row = BoxLayout(size_hint_y=None, height=dp(40))
        self.change_pill = Pill("—", "flat", size=13)
        holder = BoxLayout(size_hint_x=None, width=dp(90), padding=(0, dp(7)))
        holder.add_widget(self.change_pill)
        row.add_widget(holder)
        self.price_label = label("—", 28, TEXT, auto_height=False, align="right")
        row.add_widget(self.price_label)
        self.price_card.add_widget(row)
        self.range_label = label("", 12, MUTED)
        self.price_card.add_widget(self.range_label)
        self.tf_chips = ChipGroup([(TF_TITLES[t], t) for t in TIMEFRAMES], self.timeframe, self._on_tf)
        self.price_card.add_widget(self.tf_chips)
        self.chart = Sparkline(size_hint_y=None, height=dp(170))
        self.price_card.add_widget(self.chart)
        legend = BoxLayout(size_hint_y=None, height=dp(18), spacing=dp(12))
        legend.add_widget(Widget())
        legend.add_widget(label("— EMA20", 11, AMBER, auto_height=False, align="right", size_hint_x=None, width=dp(70)))
        legend.add_widget(label("— قیمت", 11, ACCENT, auto_height=False, align="right", size_hint_x=None, width=dp(60)))
        self.price_card.add_widget(legend)
        self.column.add_widget(self.price_card)

        self.signal_holder = BoxLayout(orientation="vertical", size_hint_y=None)
        self.signal_holder.bind(minimum_height=self.signal_holder.setter("height"))
        self.column.add_widget(self.signal_holder)

        self.tiles = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        self.tiles.bind(minimum_height=self.tiles.setter("height"))
        self.column.add_widget(self.tiles)

        self.reasons = Card()
        self.column.add_widget(self.reasons)
        self.column.add_widget(label("این تحلیل خودکار است و توصیهٔ مالی نیست. همیشه حد ضرر بگذارید.", 11, FAINT, align="center"))

    # ---- رفتار
    def show(self, symbol: str) -> None:
        self.symbol = symbol
        self.refresh(force=False)

    def _on_tf(self, tf: str) -> None:
        self.timeframe = tf
        self.refresh(force=False)

    def _toggle_star(self, *_a) -> None:  # noqa: ANN002
        watched = app().store.toggle_watch(self.symbol)
        app().toast(f"{self.symbol} {'به دیدبان اضافه شد' if watched else 'از دیدبان حذف شد'}")
        app().mark_watch_dirty()
        self._paint_star()
        self._build_quick()

    def _paint_star(self) -> None:
        watched = app().store.is_watched(self.symbol)
        self.star.icon.name = "star_fill" if watched else "star"
        self.star.icon.color = AMBER if watched else MUTED

    def _build_quick(self) -> None:
        self.quick_row.clear_widgets()
        symbols = list(dict.fromkeys([self.symbol, *app().store.watchlist]))
        for sym in reversed(symbols):
            chip = Chip(sym.split("/")[0], sym, selected=(sym == self.symbol))
            chip.bind(on_release=lambda c: self.show(c.value))
            self.quick_row.add_widget(chip)

    def refresh(self, force: bool = False) -> None:
        self.title_label.raw = self.symbol.split("/")[0]
        self.set_subtitle(f"{self.symbol} · {TF_TITLES[self.timeframe]}")
        self.tf_chips.select(self.timeframe)
        self._paint_star()
        self._build_quick()
        app().analyse_one(self.symbol, self.timeframe, self._loaded, lambda m: app().toast(m), force=force)
        app().load_tickers(self._ticker, lambda _m: None)

    def _ticker(self, rows: list[dict]) -> None:
        t = next((r for r in rows if r["symbol"] == self.symbol), None)
        if t:
            self.change_pill.set(vm.format_change(t["change"]), vm.trend_of(t["change"]))
            self.range_label.raw = f"بازهٔ ۲۴ ساعت: {vm.format_price(t['low'])} تا {vm.format_price(t['high'])} · حجم {vm.format_volume(t['turnover'])}"

    def _loaded(self, result: tuple) -> None:
        symbol, timeframe, signal, highs, lows, closes = result
        if symbol != self.symbol or timeframe != self.timeframe:
            return
        self.price_label.raw = vm.format_price(closes[-1] if closes else 0)
        snap = vm.indicator_snapshot(highs, lows, closes)
        window = 120
        tone = "up" if len(closes) > 1 and closes[-1] >= closes[-min(window, len(closes))] else "down"
        self.chart.color = GREEN if tone == "up" else RED
        self.chart.overlay = snap["ema20"][-window:]
        self.chart.values = closes[-window:]

        self.signal_holder.clear_widgets()
        self.signal_holder.add_widget(SignalCard(signal, compact=False))

        self.tiles.clear_widgets()
        for key, title in (("trend", "روند (EMA20/50)"), ("rsi", "RSI"), ("atr", "نوسان (ATR)"), ("macd", "مکدی")):
            value, t, note = snap[key]
            self.tiles.add_widget(Tile(title, value, t, note))

        self.reasons.clear_widgets()
        self.reasons.add_widget(label("دلیل‌ها", 15, TEXT))
        for reason in signal.reasons:
            self.reasons.add_widget(label(f"• {reason}", 13, MUTED))


# ================================================================ تنظیمات
class SettingsScreen(BaseScreen):
    title = "تنظیمات"
    subtitle = "شخصی‌سازی برنامه"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        store = app().store
        scroll, column = self.scroll_column()
        self.body.add_widget(scroll)

        def section(title: str, hint: str, chips: ChipGroup) -> Card:
            card = Card()
            card.add_widget(label(title, 15, TEXT))
            card.add_widget(label(hint, 12, MUTED))
            card.add_widget(chips)
            return card

        column.add_widget(section(
            "تایم‌فریم پیش‌فرض", "برای پویش سیگنال و دیدبان.",
            ChipGroup([(TF_TITLES[t], t) for t in TIMEFRAMES], store.get("timeframe"), lambda v: self._set("timeframe", v))))
        column.add_widget(section(
            "تعداد نمادهای پویش", "پرحجم‌ترین نمادها؛ عدد بزرگ‌تر = پویش طولانی‌تر و مصرف دادهٔ بیشتر.",
            ChipGroup([(f"{n} نماد", n) for n in SCAN_SIZES], store.get("scan_size"), lambda v: self._set("scan_size", v))))
        refresh_titles = {0: "خاموش", 30: "۳۰ ثانیه", 60: "۱ دقیقه", 120: "۲ دقیقه"}
        column.add_widget(section(
            "به‌روزرسانی خودکار", "قیمت‌های صفحهٔ باز به‌طور خودکار تازه می‌شوند.",
            ChipGroup([(refresh_titles[n], n) for n in REFRESH_CHOICES], store.get("refresh_seconds"),
                      lambda v: self._set("refresh_seconds", v))))
        column.add_widget(section(
            "فهرست سیگنال‌ها", "سیگنال‌های «منتظر» و کم‌اطمینان را پنهان کن.",
            ChipGroup([("همه", False), ("فقط قابل معامله", True)], store.get("tradeable_only"),
                      lambda v: self._set("tradeable_only", v))))

        about = Card()
        about.add_widget(label("دربارهٔ برنامه", 15, TEXT))
        from version import VERSION  # noqa: PLC0415

        for line in (
            f"نسخهٔ {VERSION}",
            "داده: API عمومی LBank — بدون کلید API؛ هیچ اطلاعات حسابی روی گوشی ذخیره نمی‌شود.",
            "موتور تحلیل همان فرمول‌های نسخهٔ دسکتاپ است (RSI، مکدی، EMA، بولینگر، ATR).",
            "این برنامه فقط تحلیل نشان می‌دهد و معامله انجام نمی‌دهد. توصیهٔ مالی نیست.",
            "تولیدکننده: حسین حاج طالبی",
        ):
            about.add_widget(label(line, 12, MUTED))
        column.add_widget(about)

    def _set(self, key: str, value) -> None:  # noqa: ANN001
        app().store.set(key, value)
        app().settings_changed(key)
        app().toast("ذخیره شد")


__all__ = [
    "AnalysisScreen", "MarketScreen", "SettingsScreen", "SignalsScreen", "WatchlistScreen",
    "BG", "BORDER", "SURFACE2",
]
