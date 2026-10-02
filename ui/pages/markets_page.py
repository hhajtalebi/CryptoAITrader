"""
صفحه بازارها.

فهرست کامل نمادهای صرافی با جست‌وجو، قیمت دلار و تومان، و نمایش زندهٔ
نوسان.

دو نکتهٔ طراحی که مستقیم از بازخورد کاربر آمده‌اند:

۱. **به‌روزرسانی نقطه‌ای، نه بازسازی جدول.** اگر با هر تیک قیمت کل جدول
   دوباره ساخته شود، انتخاب کاربر و موقعیت پیمایش می‌پرد و رنگ‌ها چشمک
   می‌زنند. پس فقط سلول‌های تغییرکرده به‌روز می‌شوند.

۲. **رنگ بر پایهٔ جهت حرکت.** سبز یعنی قیمت نسبت به تیک قبلی بالا رفته و
   قرمز یعنی پایین آمده — همان چیزی که کاربر خواست.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QMenu,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from localization import Translator
from market.market_rank import (
    USD_QUOTES,
    compact_number,
    price_decimals,
    quote_usdt_prices,
    sort_by_market_value,
    split_symbol,
    turnover_usdt,
)
from ui.pages.base_page import BasePage
from ui.widgets import (
    Card,
    ChipBar,
    RefreshButton,
    SegmentedControl,
    Sparkline,
    TrendCell,
    WatchlistPanel,
    configure_table,
    make_button,
)

#: کلید ترجمهٔ زبانه‌ها
TAB_KEYS: tuple[str, str] = ("markets.tab_all", "watchlist.title")

#: شماره ستون‌ها
COL_STAR = 0
COL_SYMBOL = 1
COL_PRICE_USD = 2
COL_PRICE_TOMAN = 3
COL_CHANGE = 4
COL_HIGH = 5
COL_VOLUME = 6
COL_TREND = 7

#: جفت‌ارزهای مرجع برای کلید بالای جدول
QUOTE_FILTERS = ("USDT", "BTC", "ETH")

#: تراشه‌های فیلتر سریع (چندانتخابی)
CHIP_FILTERS = ("gainers", "losers", "volume")

#: حالت‌های مرتب‌سازی. کاربر گفت «ارزها ابتدا باید بر اساس ارزش آن‌ها
#: دسته‌بندی بشه»، پس پیش‌فرض «ارزش معاملات» است نه ترتیب الفبایی صرافی.
#: v2.5.1 — پیش‌فرض «ارزش بازار + حجم»: BTC، ETH، XRP… اول، سپس پرمعامله‌ترین‌ها.
SORT_MODES: list[tuple[str, str]] = [
    ("market_cap", "markets.sort_market_cap"),
    ("value", "markets.sort_value"),
    ("volume", "markets.sort_volume"),
    ("gainers", "markets.sort_gainers"),
    ("losers", "markets.sort_losers"),
    ("price_desc", "markets.sort_price_desc"),
    ("price_asc", "markets.sort_price_asc"),
    ("name", "markets.sort_name"),
]


class NumericItem(QTableWidgetItem):
    """
    سلول جدول که بر پایهٔ **عدد** مرتب می‌شود، نه متن.

    چرا لازم است؟ متن سلول با جداکنندهٔ هزارگان و ارقام فارسی نمایش داده
    می‌شود. مرتب‌سازی متنی روی چنین رشته‌ای غلط است: «۹» را بزرگ‌تر از
    «۱۰» می‌داند. این کلاس مقدار عددی واقعی را نگه می‌دارد و مقایسه را
    روی آن انجام می‌دهد.
    """

    def __init__(self, text: str, value: float = 0.0) -> None:
        super().__init__(str(text))
        self._value = float(value or 0.0)

    def __lt__(self, other: object) -> bool:
        """مقایسهٔ عددی برای مرتب‌سازی ستون."""
        if isinstance(other, NumericItem):
            return self._value < other._value
        return super().__lt__(other)  # type: ignore[arg-type]

    @property
    def value(self) -> float:
        """مقدار عددی این سلول."""
        return self._value


class MarketsPage(BasePage):
    """صفحه مرور بازارها با قیمت زنده."""

    #: کاربر روی یک ارز کلیک کرد و جزئیات می‌خواهد (نماد)
    coin_activated = Signal(str)
    #: کاربر ستارهٔ یک نماد را زد: (نماد، در واچ‌لیست هست یا نه)
    watchlist_toggled = Signal(str, bool)
    #: کاربر خواست برای نماد انتخاب‌شده هشدار قیمتی بسازد
    alert_requested = Signal(str)
    #: منوی کلیک راست (v2.5.1): تحلیل / سیگنال برای نماد
    analyze_requested = Signal(str)
    signal_requested = Signal(str)

    title_key = "nav.markets"
    subtitle_key = "markets.subtitle"

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._sort_mode: str = "market_cap"
        self._quote_prices: dict[str, float] = {}
        self._all_rows: list[dict[str, Any]] = []
        self._watchlist: set[str] = set()
        self._quote_filter = "USDT"
        self._chip_filters: set[str] = set()
        self._theme: Any = None
        self._row_index: dict[str, int] = {}
        self._toman_rate: float | None = None
        self._palette: dict[str, str] = {}
        super().__init__(translator, parent)

    # ------------------------------------------------------------------
    # ساخت
    # ------------------------------------------------------------------
    def build(self) -> None:
        """ساخت نوار ابزار و جدول نمادها."""
        self.refresh_button = RefreshButton(
            self.tr_.tr("common.refresh"),
            busy_text=self.tr_.tr("markets.updating"),
            done_text=self.tr_.tr("common.refresh"),
        )
        self.header.add_action(self.refresh_button)

        self.live_pill = QLabel(self.tr_.tr("markets.live"))
        self.live_pill.setProperty("role", "badge")
        self.header.add_action(self.live_pill)

        self.card = Card()

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr_.tr("markets.search_placeholder"))
        self.search_input.textChanged.connect(self._filter)
        search_row.addWidget(self.search_input, 1)

        self.show_all_checkbox = QCheckBox(self.tr_.tr("common.all"))
        self.show_all_checkbox.setToolTip(self.tr_.tr("markets.all_symbols", count=0))
        self.show_all_checkbox.stateChanged.connect(lambda _: self._filter(self.search_input.text()))
        search_row.addWidget(self.show_all_checkbox)

        self.watchlist_only_checkbox = QCheckBox(self.tr_.tr("markets.watchlist_only"))
        self.watchlist_only_checkbox.stateChanged.connect(
            lambda _: self._filter(self.search_input.text())
        )
        search_row.addWidget(self.watchlist_only_checkbox)

        self.watchlist_button = make_button(self.tr_.tr("markets.add_to_watchlist"))
        search_row.addWidget(self.watchlist_button)

        # ساخت هشدار از همین‌جا: نماد و قیمتش جلوی چشم کاربر است، پس
        # طبیعی‌ترین جای تعریف هشدار همین صفحه است نه تنظیمات.
        self.alert_button = make_button("🔔  " + self.tr_.tr("alerts.add"))
        self.alert_button.clicked.connect(self._on_alert_clicked)
        search_row.addWidget(self.alert_button)
        self.card.body().addLayout(search_row)

        # کلید جفت‌ارز مرجع و تراشه‌های فیلتر سریع
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        self.quote_toggle = SegmentedControl(
            [(quote, quote) for quote in QUOTE_FILTERS]
        )
        self.quote_toggle.set_current("USDT", emit=False)
        self.quote_toggle.selection_changed.connect(self._on_quote_changed)
        filter_row.addWidget(self.quote_toggle)

        # چندانتخابی و بدون انتخاب اولیه: کاربر باید همهٔ بازارها را ببیند
        # مگر خودش فیلتری بزند.
        self.chip_bar = ChipBar(
            [(key, self.tr_.tr(f"markets.chips.{key}")) for key in CHIP_FILTERS],
            exclusive=False,
        )
        self.chip_bar.set_selection([])
        self.chip_bar.selection_changed.connect(self._on_chip_changed)
        filter_row.addWidget(self.chip_bar)
        filter_row.addStretch(1)
        self.card.body().addLayout(filter_row)

        sort_row = QHBoxLayout()
        self.sort_label = QLabel(self.tr_.tr("markets.sort_label"))
        self.sort_label.setProperty("role", "muted")
        sort_row.addWidget(self.sort_label)
        self.sort_combo = QComboBox()
        self.sort_combo.setMinimumWidth(200)
        for mode, key in SORT_MODES:
            self.sort_combo.addItem(self.tr_.tr(key), mode)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        sort_row.addWidget(self.sort_combo)
        self.click_hint = QLabel(self.tr_.tr("markets.click_hint"))
        self.click_hint.setProperty("role", "muted")
        sort_row.addWidget(self.click_hint)
        sort_row.addStretch(1)
        self.card.body().addLayout(sort_row)

        info_row = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setProperty("role", "muted")
        info_row.addWidget(self.count_label)
        info_row.addStretch(1)
        self.rate_label = QLabel(self.tr_.tr("markets.rate_unavailable"))
        self.rate_label.setProperty("role", "muted")
        info_row.addWidget(self.rate_label)
        self.card.body().addLayout(info_row)

        self.table = QTableWidget(0, 8)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # مرتب‌سازی خودکار Qt خاموش است؛ ترتیب را فهرست «ترتیب نمایش»
        # تعیین می‌کند. کلیک روی سرستون هم پشتیبانی می‌شود (پایین‌تر).
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.table.cellClicked.connect(self._on_cell_clicked)
        # v2.5.1: کلیک راست روی هر ردیف (نماد یا هر خانهٔ دیگر) ← منوی نماد
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.card.add(self.table)

        # دو زبانه: همهٔ بازارها، و مدیریت فهرست‌های دیده‌بانی. جدول
        # بازارها خودش فیلتر «فقط دیده‌بانی» دارد؛ زبانهٔ دوم برای
        # سازمان‌دادن فهرست‌هاست نه دیدن قیمت.
        self.tabs = QTabWidget(self)
        markets_tab = QWidget(self)
        markets_body = QVBoxLayout(markets_tab)
        markets_body.setContentsMargins(0, 8, 0, 0)
        markets_body.addWidget(self.card, 1)
        self.tabs.addTab(markets_tab, self.tr_.tr(TAB_KEYS[0]))

        self.watchlist_panel = WatchlistPanel(self.tr_, self)
        watchlist_tab = QWidget(self)
        watchlist_body = QVBoxLayout(watchlist_tab)
        watchlist_body.setContentsMargins(0, 8, 0, 0)
        watchlist_body.addWidget(self.watchlist_panel, 1)
        self.tabs.addTab(watchlist_tab, self.tr_.tr(TAB_KEYS[1]))

        self.layout_root().addWidget(self.tabs, 1)
        self._apply_headers()

    def show_watchlists(self) -> None:
        """باز کردن زبانهٔ فهرست‌های دیده‌بانی."""
        self.tabs.setCurrentIndex(1)

    def _apply_headers(self) -> None:
        """تنظیم سرستون‌ها."""
        self.table.setHorizontalHeaderLabels([
            "★",
            self.tr_.tr("common.symbol"),
            self.tr_.tr("markets.price_usdt"),
            self.tr_.tr("markets.price_toman"),
            self.tr_.tr("common.change"),
            self.tr_.tr("common.high"),
            self.tr_.tr("markets.turnover_usdt"),
            self.tr_.tr("markets.trend"),
        ])
        configure_table(self.table, stretch_column=COL_SYMBOL)
        header = self.table.horizontalHeader()
        header.resizeSection(COL_STAR, 34)
        # ستون روند ویجت دارد، نه متن. با حالت ResizeToContents پهنایش
        # از روی «محتوای متنی» حساب می‌شد و صفر درمی‌آمد، برای همین
        # نمودار و برچسب روی هم می‌افتادند. پهنای ثابت می‌دهیم.
        from PySide6.QtWidgets import QHeaderView

        header.setSectionResizeMode(COL_TREND, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_TREND, 200)
        # ردیف باید جا برای نمودار ۲۲ پیکسلی و حاشیه داشته باشد
        self.table.verticalHeader().setDefaultSectionSize(38)

    # ------------------------------------------------------------------
    # داده
    # ------------------------------------------------------------------
    def set_palette(self, palette: dict[str, str]) -> None:
        """دریافت پالت رنگ جاری برای رنگ‌آمیزی سلول‌ها."""
        self._palette = dict(palette or {})

    def apply_theme(self, theme: Any) -> None:
        """
        اعمال پوسته روی نمودارهای کوچک ستون روند.

        جدول دوباره ترسیم می‌شود تا رنگ ستاره و اسپارک‌لاین‌ها با پوستهٔ
        تازه بخوانند.
        """
        self._theme = theme
        self._palette = {
            "warning": theme.colors.warning,
            "success": theme.colors.success,
            "danger": theme.colors.danger,
            **self._palette,
        }
        if self._all_rows:
            self._filter(self.search_input.text())

    def set_toman_rate(self, rate: float | None, source: str = "") -> None:
        """
        تعیین نرخ تبدیل دلار به تومان.

        بدون نرخ، ستون تومان خالی می‌ماند؛ نشان‌دادن عدد ساختگی بدتر از
        نشان‌ندادن است.
        """
        self._toman_rate = rate if rate and rate > 0 else None
        if self._toman_rate is None:
            self.rate_label.setText(self.tr_.tr("markets.rate_unavailable"))
        else:
            label = self.tr_.tr("markets.rate_source", source=source or "—")
            self.rate_label.setText(
                f"{label} · ۱ USDT = {self.tr_.format_number(self._toman_rate, 0)}"
                if self.tr_.language == "fa"
                else f"{label} · 1 USDT = {self.tr_.format_number(self._toman_rate, 0)}"
            )
        self._filter(self.search_input.text())

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        """
        نمایش فهرست نمادها.

        اگر همان مجموعه نمادها دوباره بیاید (تازه‌سازی دوره‌ای)، جدول از
        نو ساخته **نمی‌شود** و فقط مقدارها به‌روز می‌گردند. بازسازی کامل،
        رنگ‌های نوسان زنده را پاک می‌کرد و انتخاب کاربر را می‌پراند.
        """
        new_rows = list(rows or [])
        new_symbols = [str(r.get("symbol", "")) for r in new_rows]
        same_set = bool(self._all_rows) and new_symbols == [
            str(r.get("symbol", "")) for r in self._all_rows
        ]

        self._all_rows = new_rows
        if same_set and not self.search_input.text().strip():
            self._update_values_in_place(new_rows)
            return
        self._filter(self.search_input.text())

    def _update_values_in_place(self, rows: list[dict[str, Any]]) -> None:
        """به‌روزرسانی مقدار سلول‌ها بدون بازسازی جدول."""
        for row in rows:
            symbol = str(row.get("symbol", ""))
            index = self._row_index.get(symbol)
            if index is None:
                continue
            change = float(row.get("change_percent", 0.0) or 0.0)
            usdt_price = self._usdt_price(row)

            usd = self.table.item(index, COL_PRICE_USD)
            if usd is not None:
                usd.setText(self._price_text(row))
            toman = self.table.item(index, COL_PRICE_TOMAN)
            if toman is not None:
                toman.setText(self._toman_text(usdt_price))
            change_item = self.table.item(index, COL_CHANGE)
            if change_item is not None:
                change_item.setText(f"\u200e{change:+.2f}%")
                self._tint(change_item, 1 if change > 0 else (-1 if change < 0 else 0))
            volume = self.table.item(index, COL_VOLUME)
            if volume is not None:
                volume.setText(self._turnover_text(row))

    def apply_price_updates(self, updates: dict[str, dict[str, Any]]) -> None:
        """
        اعمال به‌روزرسانی زندهٔ قیمت روی ردیف‌های موجود.

        `updates` نگاشت نماد به دیکشنری شامل `price`, `change_percent` و
        `tick_direction` است. فقط سلول‌های همان ردیف دست می‌خورند تا
        انتخاب و پیمایش کاربر حفظ شود.
        """
        if not updates or not self._row_index:
            return

        for symbol, update in updates.items():
            price = update.get("price")
            if price is None:
                continue
            base, quote = split_symbol(symbol)
            if quote == "USDT" and base:
                # قیمت مرجع جفت‌های غیرتتری (مثلاً ETH/BTC) هم زنده بماند —
                # حتی وقتی ردیف BTC/USDT در زبانهٔ فعلی دیده نمی‌شود.
                try:
                    self._quote_prices[base] = float(price)
                except (TypeError, ValueError):
                    pass
            row = self._row_index.get(symbol)
            if row is None:
                continue
            direction = int(update.get("tick_direction") or 0)

            # به‌روزرسانی دادهٔ پشتیبان تا فیلتر بعدی مقدار تازه را ببیند
            stored_row: dict[str, Any] = {"symbol": symbol, "price": price}
            for stored in self._all_rows:
                if stored.get("symbol") == symbol:
                    stored["price"] = price
                    if update.get("change_percent") is not None:
                        stored["change_percent"] = update["change_percent"]
                    stored_row = stored
                    break

            usd_item = self.table.item(row, COL_PRICE_USD)
            if usd_item is not None:
                usd_item.setText(self._price_text(stored_row))
                self._tint(usd_item, direction)

            toman_item = self.table.item(row, COL_PRICE_TOMAN)
            if toman_item is not None:
                toman_item.setText(self._toman_text(self._usdt_price(stored_row)))
                self._tint(toman_item, direction)

            change = update.get("change_percent")
            if change is not None:
                change_item = self.table.item(row, COL_CHANGE)
                if change_item is not None:
                    change_item.setText(f"{float(change):+.2f}%")
                    self._tint(change_item, 1 if float(change) > 0 else (-1 if float(change) < 0 else 0))

    # ------------------------------------------------------------------
    # فیلتر و ترسیم
    # ------------------------------------------------------------------
    def _on_sort_changed(self) -> None:
        """کاربر ترتیب نمایش را عوض کرد."""
        self._sort_mode = str(self.sort_combo.currentData() or "value")
        self._filter(self.search_input.text())

    def sort_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        مرتب‌سازی ردیف‌ها بر پایهٔ حالت انتخابی کاربر.

        «ارزش معاملات» = قیمت × حجم. این معیار بهتر از حجم خام نشان
        می‌دهد کدام بازار واقعاً بزرگ است؛ حجم خام یک ارز ارزان را
        به‌اشتباه بالای فهرست می‌برد.
        """
        mode = self._sort_mode

        def price_of(row: dict[str, Any]) -> float:
            try:
                return float(row.get("price") or 0.0)
            except (TypeError, ValueError):
                return 0.0

        def volume_of(row: dict[str, Any]) -> float:
            try:
                return float(row.get("volume") or 0.0)
            except (TypeError, ValueError):
                return 0.0

        def change_of(row: dict[str, Any]) -> float:
            try:
                return float(row.get("change_percent") or 0.0)
            except (TypeError, ValueError):
                return 0.0

        quotes = self._quote_prices

        def value_of(row: dict[str, Any]) -> float:
            """ارزش معاملات به تتر؛ اگر صرافی خودش داده بود، همان مبنا است."""
            _base, quote = split_symbol(str(row.get("symbol", "")))
            if quote and quote not in USD_QUOTES and quote not in quotes:
                # ارز مرجع بی‌قیمت: همان مبنای خام (بهتر از صفر)
                return turnover_usdt({**row, "symbol": _base}, None)
            return turnover_usdt(row, quotes.get(quote))

        def usdt_price_of(row: dict[str, Any]) -> float:
            return self._usdt_price(row) or price_of(row)

        if mode == "market_cap":
            return sort_by_market_value(rows, quotes)
        if mode == "value":
            return sorted(rows, key=value_of, reverse=True)
        if mode == "volume":
            return sorted(rows, key=volume_of, reverse=True)
        if mode == "gainers":
            return sorted(rows, key=change_of, reverse=True)
        if mode == "losers":
            return sorted(rows, key=change_of)
        if mode == "price_desc":
            return sorted(rows, key=usdt_price_of, reverse=True)
        if mode == "price_asc":
            return sorted(rows, key=usdt_price_of)
        if mode == "name":
            return sorted(rows, key=lambda r: str(r.get("symbol", "")).upper())
        return list(rows)

    def _on_header_clicked(self, column: int) -> None:
        """
        مرتب‌سازی با کلیک روی سرستون.

        هر کلیک ترتیب را برعکس می‌کند. چون سلول‌های عددی از NumericItem
        ساخته شده‌اند، مقایسه بر پایهٔ عدد انجام می‌شود نه متن.
        """
        if column in (COL_STAR, COL_TREND):
            # ستون ستاره و نمودار روند مقدار قابل مرتب‌سازی ندارند
            return
        current = getattr(self, "_header_sort", (None, False))
        ascending = not current[1] if current[0] == column else True
        self._header_sort = (column, ascending)
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.sortItems(
            column,
            Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder,
        )
        self._rebuild_index()

    def _on_cell_clicked(self, row: int, column: int) -> None:
        """
        کلیک روی سلول.

        ستون ستاره نماد را به واچ‌لیست می‌برد یا از آن درمی‌آورد؛ بقیهٔ
        ستون‌ها مدال جزئیات را باز می‌کنند.
        """
        item = self.table.item(row, COL_SYMBOL)
        if item is None or not item.text():
            return
        if column == COL_STAR:
            self._on_star_clicked(item.text())
            return
        self.coin_activated.emit(item.text())

    def row_data(self, symbol: str) -> dict[str, Any]:
        """دادهٔ خام یک نماد برای پر کردن مدال جزئیات."""
        for row in self._all_rows:
            if str(row.get("symbol", "")) == str(symbol):
                return dict(row)
        return {}

    def _filter(self, text: str) -> None:
        """فیلتر کردن، مرتب‌سازی و ترسیم دوبارهٔ جدول."""
        needle = (text or "").strip().upper()
        rows = (
            [r for r in self._all_rows if needle in str(r.get("symbol", "")).upper()]
            if needle
            else list(self._all_rows)
        )
        self._quote_prices = quote_usdt_prices(self._all_rows)
        rows = self._apply_quick_filters(rows)
        rows = self.sort_rows(rows)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        self._row_index = {}

        for index, row in enumerate(rows):
            symbol = str(row.get("symbol", ""))
            self._row_index[symbol] = index
            price = row.get("price", 0.0) or 0.0
            change = float(row.get("change_percent", 0.0) or 0.0)
            change_direction = 1 if change > 0 else (-1 if change < 0 else 0)

            usdt_price = self._usdt_price(row)
            cells = [
                (COL_SYMBOL, symbol, 0),
                (COL_PRICE_USD, self._price_text(row), 0),
                (COL_PRICE_TOMAN, self._toman_text(usdt_price), 0),
                # نشانگر چپ‌به‌راست: بدون آن، «+۲.۳۴٪» در چیدمان راست‌به‌چپ
                # به شکل «۲.۳۴٪+» نمایش داده می‌شود.
                (COL_CHANGE, f"\u200e{change:+.2f}%", change_direction),
                (COL_HIGH, self._high_text(row), 0),
                (COL_VOLUME, self._turnover_text(row), 0),
            ]
            numeric_values = {
                COL_PRICE_USD: float(usdt_price or price or 0.0),
                COL_PRICE_TOMAN: float(usdt_price or 0.0) * (self._toman_rate or 0.0),
                COL_CHANGE: change,
                COL_HIGH: float(row.get("high", 0.0) or 0.0),
                COL_VOLUME: self._turnover_value(row),
            }
            for column, value, tint in cells:
                if column in numeric_values:
                    # مرتب‌سازی ستون‌های عددی باید بر پایهٔ عدد باشد نه متن
                    item = NumericItem(str(value), numeric_values[column])
                else:
                    item = QTableWidgetItem(str(value))
                if column != COL_SYMBOL:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if tint:
                    self._tint(item, tint)
                if column == COL_PRICE_USD:
                    item.setToolTip(self._price_tooltip(row))
                self.table.setItem(index, column, item)

            # ستارهٔ واچ‌لیست
            starred = symbol in self._watchlist
            star = QTableWidgetItem("★" if starred else "☆")
            star.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            star.setToolTip(
                self.tr_.tr("markets.remove_from_watchlist")
                if starred
                else self.tr_.tr("markets.add_to_watchlist")
            )
            if starred and self._palette.get("warning"):
                star.setForeground(QColor(self._palette["warning"]))
            self.table.setItem(index, COL_STAR, star)

            # سلول روند: نمودار خطی + برچسب فارسی «صعودی/نزولی» + رنگ.
            # پیش‌تر فقط نمودار بود و چون تاریخچه معمولاً نمی‌رسید، ستون
            # خالی می‌ماند و کاربر روند را اصلاً نمی‌دید.
            history = row.get("history") or []
            cell = TrendCell(self.tr_)
            if self._theme is not None:
                cell.apply_theme(self._theme)
            cell.set_trend(change, [float(value) for value in history])
            self.table.setCellWidget(index, COL_TREND, cell)

        # توجه: مرتب‌سازی جدول عمداً روشن **نمی‌شود**. ترتیب ردیف‌ها را
        # خودمان با sort_rows تعیین کرده‌ایم؛ اگر setSortingEnabled(True)
        # صدا زده شود، Qt بی‌درنگ جدول را دوباره بر پایهٔ ستون نشانه‌دار
        # (به‌طور پیش‌فرض ستون نماد) مرتب می‌کند و انتخاب کاربر در فهرست
        # «ترتیب نمایش» بی‌اثر می‌شود.
        # کاربر همچنان می‌تواند روی سرستون کلیک کند؛ کلیک سرستون خودش
        # مرتب‌سازی را فعال می‌کند.
        self.table.horizontalHeader().setSortIndicatorShown(False)
        # نمایه باید **پس از** چیدن ردیف‌ها ساخته شود: جابه‌جایی ردیف‌ها
        # نمایهٔ ساخته‌شده هنگام پر کردن را به ردیف اشتباه می‌برد —
        # یعنی تیک بیت‌کوین روی ردیف ارز دیگری می‌نشست.
        self._rebuild_index()
        self.count_label.setText(self.tr_.tr("markets.updated", count=len(rows)))

    def _apply_quick_filters(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        اعمال کلید جفت‌ارز، تراشهٔ فیلتر و «فقط واچ‌لیست».

        همه روی هم اثر می‌گذارند تا کاربر بتواند مثلاً «فقط واچ‌لیست +
        صعودی‌ها» را ببیند.
        """
        result = list(rows)

        quote = self._quote_filter
        if quote:
            result = [
                row
                for row in result
                if str(row.get("symbol", "")).upper().endswith(f"/{quote}")
            ]

        if self.watchlist_only_checkbox.isChecked():
            result = [row for row in result if str(row.get("symbol", "")) in self._watchlist]

        chips = self._chip_filters
        # «صعودی» و «نزولی» با هم اجتماع می‌شوند تا انتخاب هر دو، همهٔ
        # بازارهای متحرک را نشان دهد نه یک فهرست خالی.
        if "gainers" in chips and "losers" not in chips:
            result = [row for row in result if float(row.get("change_percent") or 0.0) > 0]
        elif "losers" in chips and "gainers" not in chips:
            result = [row for row in result if float(row.get("change_percent") or 0.0) < 0]
        elif "gainers" in chips and "losers" in chips:
            result = [row for row in result if float(row.get("change_percent") or 0.0) != 0]

        if "volume" in chips:
            result = sorted(result, key=self._turnover_value, reverse=True)[:50]
        return result

    def _on_quote_changed(self, quote: str) -> None:
        """کاربر جفت‌ارز مرجع را عوض کرد."""
        self._quote_filter = quote
        self._filter(self.search_input.text())

    def _on_chip_changed(self, key: str) -> None:
        """کاربر تراشهٔ فیلتر را عوض کرد."""
        self._chip_filters: set[str] = set() if key == "all" else key
        self._filter(self.search_input.text())

    def set_watchlist(self, symbols: list[str]) -> None:
        """
        تعیین نمادهای واچ‌لیست تا ستارهٔ ردیف‌ها درست پر شود.

        بدون این، ستاره‌ها پس از تازه‌سازی خالی می‌شدند.
        """
        self._watchlist = set(symbols or [])
        self._filter(self.search_input.text())

    def _on_star_clicked(self, symbol: str) -> None:
        """تغییر وضعیت واچ‌لیست یک نماد."""
        if symbol in self._watchlist:
            self._watchlist.discard(symbol)
            self.watchlist_toggled.emit(symbol, False)
        else:
            self._watchlist.add(symbol)
            self.watchlist_toggled.emit(symbol, True)
        self._filter(self.search_input.text())

    def _rebuild_index(self) -> None:
        """ساخت نگاشت نماد به شمارهٔ ردیف از روی وضعیت واقعی جدول."""
        self._row_index = {}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_SYMBOL)
            if item is not None:
                self._row_index[item.text()] = row

    def _tint(self, item: QTableWidgetItem, direction: int) -> None:
        """
        رنگ‌آمیزی یک سلول بر پایهٔ جهت حرکت.

        اگر پالتی تنظیم نشده باشد، رنگ پیش‌فرض معقولی به کار می‌رود تا
        جدول در هر پوسته‌ای خوانا بماند.
        """
        if direction > 0:
            color = self._palette.get("success", "#26d07c")
        elif direction < 0:
            color = self._palette.get("danger", "#ff5c5c")
        else:
            return
        item.setForeground(QBrush(QColor(color)))

    def _toman_text(self, price: Any) -> str:
        """تبدیل قیمت دلاری به تومان."""
        if self._toman_rate is None:
            return "—"
        try:
            value = float(price) * self._toman_rate
        except (TypeError, ValueError):
            return "—"
        return self.tr_.format_number(value, 0)

    @staticmethod
    def _price_decimals(price: Any, precision: Any = None) -> int:
        """
        تعداد رقم اعشار متناسب با بزرگی قیمت (v2.5.1: دقت صرافی در اولویت).

        نمایش بیت‌کوین با ۸ رقم اعشار و شیبا با ۲ رقم، هر دو بی‌فایده‌اند؛
        قبلاً هر قیمت زیر ۱ با ۸ رقم ثابت نمایش داده می‌شد و قیمت ارزهای
        بسیار ارزان (۰٫۰۰۰۰۰۰۰۱۲) صفر یا گرد دیده می‌شد.
        """
        try:
            value = float(price)
        except (TypeError, ValueError):
            return 2
        return price_decimals(value, precision)

    # --------------------------------------------------- قیمت تتری (v2.5.1)
    def _usdt_price(self, row: dict[str, Any]) -> float:
        """
        قیمت تتری نماد.

        جفت‌های X/USDT همان قیمت؛ جفت‌های X/BTC یا X/ETH با قیمت تتری ارز
        مرجع تبدیل می‌شوند. قبلاً قیمت ETH/BTC (مثلاً ۰٫۰۳۸) زیر ستون «قیمت
        (USDT)» نمایش داده می‌شد و تومانش هم غلط بود.
        """
        try:
            price = float(row.get("price") or 0.0)
        except (TypeError, ValueError):
            return 0.0
        _base, quote = split_symbol(str(row.get("symbol", "")))
        if not quote or quote in USD_QUOTES:
            return price
        rate = self._quote_prices.get(quote)
        return price * rate if rate else 0.0

    def _price_text(self, row: dict[str, Any]) -> str:
        """متن ستون قیمت تتری با دقت صرافی/چهار رقم معنادار."""
        usdt = self._usdt_price(row)
        if usdt <= 0:
            return "—"
        _base, quote = split_symbol(str(row.get("symbol", "")))
        precision = row.get("price_precision") if (not quote or quote in USD_QUOTES) else None
        return self.tr_.format_number(usdt, self._price_decimals(usdt, precision))

    def _high_text(self, row: dict[str, Any]) -> str:
        """
        بیشترین قیمت ۲۴ ساعته با همان دقت قیمت (v2.5.1).

        قبلاً ثابت ۴ رقم اعشار بود و برای ارزهای ریز «0.0000» نشان می‌داد.
        بیشترین قیمت به ارز مرجع جفت است (همان واحد تیکر).
        """
        high = float(row.get("high", 0.0) or 0.0)
        if high <= 0:
            return "—"
        return self.tr_.format_number(high, self._price_decimals(high, row.get("price_precision")))

    def _price_tooltip(self, row: dict[str, Any]) -> str:
        """قیمت اصلی جفت‌های غیرتتری در راهنمای ابزار."""
        _base, quote = split_symbol(str(row.get("symbol", "")))
        if not quote or quote in USD_QUOTES:
            return ""
        try:
            native = float(row.get("price") or 0.0)
        except (TypeError, ValueError):
            return ""
        return f"{native:.{price_decimals(native)}f} {quote}"

    def _turnover_value(self, row: dict[str, Any]) -> float:
        """ارزش معاملات ۲۴ ساعته به تتر."""
        _base, quote = split_symbol(str(row.get("symbol", "")))
        return turnover_usdt(row, self._quote_prices.get(quote))

    def _turnover_text(self, row: dict[str, Any]) -> str:
        """۱٫۲۵B / ۳۴۰٫۱۲M — خوانا مثل صرافی‌ها."""
        value = self._turnover_value(row)
        if value <= 0:
            return "—"
        number, suffix = compact_number(value)
        return self.tr_.format_number(number, 2 if suffix else 0) + suffix

    # ------------------------------------------------ منوی کلیک راست (v2.5.1)
    def _show_context_menu(self, pos: QPoint) -> None:
        """کلیک راست روی ردیف ← منوی نماد (واچ‌لیست، جزئیات، تحلیل، …)."""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        item = self.table.item(row, COL_SYMBOL)
        if item is None or not item.text():
            return
        self.table.selectRow(row)
        menu = self.build_context_menu(item.text())
        menu.exec(self.table.viewport().mapToGlobal(pos))
        menu.deleteLater()

    def build_context_menu(self, symbol: str) -> QMenu:
        """
        ساخت منوی نماد (جدا از نمایش تا آزمون‌پذیر باشد).

        گزینهٔ اول همیشه افزودن/برداشتن از واچ‌لیست است — خواستهٔ اصلی
        کاربر — و بقیه میان‌بُر کارهای رایج روی همان نماد.
        """
        menu = QMenu(self.table)
        menu.setObjectName("marketsContextMenu")
        starred = symbol in self._watchlist
        watch = menu.addAction(
            ("☆  " + self.tr_.tr("markets.remove_from_watchlist"))
            if starred
            else ("★  " + self.tr_.tr("markets.add_to_watchlist"))
        )
        watch.setData("watchlist")
        watch.triggered.connect(lambda _c=False, s=symbol: self._on_star_clicked(s))
        menu.addSeparator()
        entries = (
            ("details", "🔍  " + self.tr_.tr("markets.menu.details"), lambda s=symbol: self.coin_activated.emit(s)),
            ("analyze", "📈  " + self.tr_.tr("markets.menu.analyze"), lambda s=symbol: self.analyze_requested.emit(s)),
            ("signal", "⚡  " + self.tr_.tr("markets.menu.signal"), lambda s=symbol: self.signal_requested.emit(s)),
            ("alert", "🔔  " + self.tr_.tr("alerts.add"), lambda s=symbol: self.alert_requested.emit(s)),
        )
        for key, text, handler in entries:
            action = menu.addAction(text)
            action.setData(key)
            action.triggered.connect(lambda _c=False, h=handler: h())
        menu.addSeparator()
        copy_symbol = menu.addAction("⧉  " + self.tr_.tr("markets.menu.copy_symbol"))
        copy_symbol.setData("copy_symbol")
        copy_symbol.triggered.connect(lambda _c=False, s=symbol: self._copy_text(s))
        row = self.row_data(symbol)
        copy_price = menu.addAction("⧉  " + self.tr_.tr("markets.menu.copy_price"))
        copy_price.setData("copy_price")
        copy_price.setEnabled(self._usdt_price(row) > 0)
        copy_price.triggered.connect(
            lambda _c=False, r=row: self._copy_text(
                f"{self._usdt_price(r):.{self._price_decimals(self._usdt_price(r), r.get('price_precision'))}f}"
            )
        )
        return menu

    @staticmethod
    def _copy_text(text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(text))

    def _on_alert_clicked(self) -> None:
        """درخواست ساخت هشدار برای نماد انتخاب‌شده."""
        symbol = self.selected_symbol()
        if symbol:
            self.alert_requested.emit(symbol)

    def selected_symbol(self) -> str:
        """
        نماد انتخاب‌شده در جدول.

        در چیدمان راست‌به‌چپ ممکن است سطر «جاری» تنظیم نشده باشد در حالی
        که کاربر سطری را انتخاب کرده؛ پس مدلِ انتخاب هم بررسی می‌شود.
        """
        row = self.table.currentRow()
        if row < 0:
            model = self.table.selectionModel()
            if model is not None:
                rows = model.selectedRows()
                if rows:
                    row = rows[0].row()
        if row < 0:
            return ""
        item = self.table.item(row, COL_SYMBOL)
        return item.text() if item else ""

    def retranslate(self) -> None:
        """بازسازی متن‌ها."""
        super().retranslate()
        self.refresh_button.set_texts(
            self.tr_.tr("common.refresh"),
            self.tr_.tr("markets.updating"),
            self.tr_.tr("common.refresh"),
        )
        self.live_pill.setText(self.tr_.tr("markets.live"))
        self.search_input.setPlaceholderText(self.tr_.tr("markets.search_placeholder"))
        self.show_all_checkbox.setText(self.tr_.tr("common.all"))
        self.watchlist_button.setText(self.tr_.tr("markets.add_to_watchlist"))
        self.sort_label.setText(self.tr_.tr("markets.sort_label"))
        self.click_hint.setText(self.tr_.tr("markets.click_hint"))
        # متن گزینه‌های مرتب‌سازی بدون تغییر انتخاب فعلی به‌روز می‌شود
        self.sort_combo.blockSignals(True)
        for index, (_mode, key) in enumerate(SORT_MODES):
            self.sort_combo.setItemText(index, self.tr_.tr(key))
        self.sort_combo.blockSignals(False)
        self.chip_bar.set_labels(
            {key: self.tr_.tr(f"markets.chips.{key}") for key in CHIP_FILTERS}
        )
        self.watchlist_only_checkbox.setText(self.tr_.tr("markets.watchlist_only"))
        for index, key in enumerate(TAB_KEYS):
            self.tabs.setTabText(index, self.tr_.tr(key))
        self.watchlist_panel.retranslate()
        self._apply_headers()
        self._filter(self.search_input.text())
