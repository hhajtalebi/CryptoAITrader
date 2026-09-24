"""
صفحه کیف پول.

نمایش دارایی‌های حساب صرافی متصل، سهم هر دارایی، منحنی رشد سرمایه و
معاملات اخیر.

اگر حساب صرافی متصل نباشد، به‌جای جدول خالی یک حالت راهنما نشان داده
می‌شود تا کاربر بداند چه باید بکند — همان الگوی «حالت خالی معنادار» که
در سراسر برنامه رعایت شده است.

این صفحه در همهٔ پوسته‌ها یکسان در دسترس است؛ پوسته فقط ظاهر آن را
تغییر می‌دهد.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from localization import Translator
from ui.pages.base_page import BasePage
from ui.widgets import (
    AreaChart,
    DonutChart,
    EmptyState,
    RefreshButton,
    SegmentedControl,
    StatCard,
    configure_table,
    make_button,
    set_role,
)

#: بازه‌های نمودار رشد سرمایه
RANGE_KEYS = ("7d", "30d", "90d", "1y")

#: شمار نقاط نمودار برای هر بازه — بازهٔ بلندتر، نقاط بیشتر
RANGE_POINTS = {"7d": 7, "30d": 30, "90d": 45, "1y": 52}

#: زبانه‌های کیف پول (v2.5.0 — خواستهٔ کاربر: نمای کلی | اسپات | فیوچرز)
WALLET_TABS = ("overview", "spot", "futures")

#: ستون‌های جدول اسپات
SPOT_COLUMNS = ("asset", "free", "locked", "total", "price", "value", "share", "change")

#: ستون‌های جدول فیوچرز
FUTURES_COLUMNS = (
    "asset", "equity", "wallet", "available", "margin", "frozen", "unrealized", "value",
)

#: خانه‌های نوار خلاصهٔ هر زبانه — ترتیب نمایش
SPOT_METRICS = ("value", "available_usdt", "locked_value", "assets")
FUTURES_METRICS = ("equity", "wallet", "available", "used_margin", "unrealized", "margin_ratio")
PAPER_METRICS = ("balance", "equity", "available", "realized", "unrealized", "used_margin", "start")


#: عدد درشت نوار خلاصه — QSS سراسری فونت QLabel را بازنویسی می‌کند
_METRIC_STYLE = "font-size: 16px; font-weight: 700;"


class MetricStrip(QFrame):
    """
    نوار فشردهٔ «برچسب / عدد» به سبک ترمینال صرافی (v2.5.0).

    هر خانه یک برچسب کم‌رنگ و یک عدد درشت دارد؛ رنگ عدد می‌تواند سبز/قرمز
    شود (برای سود/زیان). اعداد چپ‌به‌راست می‌مانند تا در چیدمان فارسی
    علامت‌ها جابه‌جا نشوند.
    """

    def __init__(self, keys: tuple[str, ...], columns: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        set_role(self, "card")
        self._keys = tuple(keys)
        grid = QGridLayout(self)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setHorizontalSpacing(22)
        grid.setVerticalSpacing(4)
        per_row = columns or len(self._keys)
        self.labels: dict[str, QLabel] = {}
        self.values: dict[str, QLabel] = {}
        for index, key in enumerate(self._keys):
            row, column = divmod(index, per_row)
            label = QLabel("", self)
            set_role(label, "muted")
            value = QLabel("—", self)
            set_role(value, "metric_small")
            font = value.font()
            font.setBold(True)
            font.setPointSizeF(max(font.pointSizeF(), 9.0) * 1.25)
            value.setFont(font)
            value.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setStyleSheet(_METRIC_STYLE)
            grid.addWidget(label, row * 2, column)
            grid.addWidget(value, row * 2 + 1, column)
            self.labels[key] = label
            self.values[key] = value
        for column in range(per_row):
            grid.setColumnStretch(column, 1)

    def set_labels(self, labels: dict[str, str]) -> None:
        for key, text in labels.items():
            if key in self.labels:
                self.labels[key].setText(text)

    def set_values(self, values: dict[str, Any], colors: dict[str, str] | None = None) -> None:
        for key, label in self.values.items():
            label.setText(str(values.get(key, "—") or "—"))
            color = (colors or {}).get(key, "")
            label.setStyleSheet(_METRIC_STYLE + (f" color: {color};" if color else ""))

    def value_text(self, key: str) -> str:
        label = self.values.get(key)
        return label.text() if label is not None else ""


class WalletPage(BasePage):
    """دارایی‌ها و عملکرد حساب کاربر."""

    title_key = "nav.wallet"
    subtitle_key = "wallet.subtitle"

    #: کاربر همگام‌سازی دارایی‌ها را خواست
    sync_requested = Signal()
    #: کاربر روی «اتصال حساب صرافی» زد (به تنظیمات می‌رود)
    connect_requested = Signal()
    #: بازهٔ نمودار عوض شد
    range_changed = Signal(str)
    #: کاربر روی یک دارایی کلیک کرد (نماد)
    asset_activated = Signal(str)
    #: کاربر «همگام‌سازی موجودی کاغذی با کیف پول» را زد (v2.5.0)
    paper_sync_requested = Signal()

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._assets: list[dict[str, Any]] = []
        self._spot_rows: list[dict[str, Any]] = []
        self._futures_rows: list[dict[str, Any]] = []
        self._theme: Any = None
        super().__init__(translator, parent)

    # ------------------------------------------------------------------
    # ساخت
    # ------------------------------------------------------------------
    def build(self) -> None:
        """ساخت کارت‌های آمار، نمودارها و جدول‌ها."""
        self.refresh_button = RefreshButton(
            self.tr_.tr("wallet.sync"),
            busy_text=self.tr_.tr("common.state.loading"),
            done_text=self.tr_.tr("wallet.sync"),
        )
        self.refresh_button.clicked.connect(self.sync_requested)
        self.header.add_action(self.refresh_button)

        self.sync_label = QLabel(self.tr_.tr("wallet.never_synced"))
        set_role(self.sync_label, "faint")
        self.header.add_action(self.sync_label)

        # پشتهٔ محتوا: حالت عادی یا حالت «حساب متصل نیست»
        self.stack = QStackedWidget(self)
        self.layout_root().addWidget(self.stack, 1)

        self.stack.addWidget(self._build_content())
        self.stack.addWidget(self._build_empty())
        self.stack.setCurrentIndex(1)
        self._retranslate_headers()

    def _build_content(self) -> QWidget:
        """
        نمای اصلی: سه زبانه — نمای کلی | اسپات | فیوچرز (v2.5.0).

        زبانهٔ «نمای کلی» همان چیدمان قبلی است به‌علاوهٔ پنل حساب کاغذی؛
        اسپات و فیوچرز هر کدام نوار خلاصه و جدول جزئیات خودشان را دارند.
        """
        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        # هر زبانه درون ناحیهٔ پیمایش است تا در نمایشگر لپ‌تاپ فشرده نشود
        self.tabs.addTab(self._scrollable(self._build_overview()), "")
        self.tabs.addTab(self._scrollable(self._build_spot_tab()), "")
        self.tabs.addTab(self._scrollable(self._build_futures_tab()), "")
        self._retranslate_tabs()
        return self.tabs

    @staticmethod
    def _scrollable(content: QWidget) -> QWidget:
        """پیچیدن محتوای یک زبانه در QScrollArea بی‌قاب."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidget(content)
        content.setMinimumHeight(max(content.minimumSizeHint().height(), 560))
        return area

    def _build_overview(self) -> QWidget:
        """زبانهٔ نمای کلی."""
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        # --- کارت‌های آمار ---
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.total_card = StatCard(icon="◎")
        self.available_card = StatCard(icon="◍")
        self.pnl_card = StatCard(icon="◈")
        self.paper_card = StatCard(icon="◇")
        for card in (self.total_card, self.available_card, self.pnl_card, self.paper_card):
            cards.addWidget(card)
        layout.addLayout(cards)

        # --- پنل حساب کاغذی (موجودی جعلی = کیف پول واقعی) ---
        paper = QFrame(page)
        set_role(paper, "card")
        paper_layout = QVBoxLayout(paper)
        paper_layout.setContentsMargins(16, 12, 16, 12)
        paper_layout.setSpacing(8)
        paper_header = QHBoxLayout()
        self.paper_title = QLabel("")
        set_role(self.paper_title, "section")
        self.paper_source_label = QLabel("")
        set_role(self.paper_source_label, "faint")
        self.paper_source_label.setWordWrap(True)
        self.paper_sync_button = make_button("")
        self.paper_sync_button.clicked.connect(self.paper_sync_requested)
        paper_header.addWidget(self.paper_title)
        paper_header.addWidget(self.paper_source_label, 1)
        paper_header.addWidget(self.paper_sync_button)
        paper_layout.addLayout(paper_header)
        self.paper_strip = MetricStrip(PAPER_METRICS, parent=paper)
        self.paper_strip.setProperty("role", "")
        paper_layout.addWidget(self.paper_strip)
        layout.addWidget(paper)

        # --- نمودار رشد + دونات سهم دارایی ---
        charts = QHBoxLayout()
        charts.setSpacing(12)

        growth = QFrame(page)
        set_role(growth, "card")
        growth_layout = QVBoxLayout(growth)
        growth_layout.setContentsMargins(16, 14, 16, 14)
        growth_layout.setSpacing(10)

        growth_header = QHBoxLayout()
        self.growth_title = QLabel(self.tr_.tr("wallet.growth"))
        set_role(self.growth_title, "section")
        self.range_bar = SegmentedControl(
            [(key, self.tr_.tr(f"wallet.range.{key}")) for key in RANGE_KEYS]
        )
        self.range_bar.set_current("30d", emit=False)
        self.range_bar.selection_changed.connect(self.range_changed)
        growth_header.addWidget(self.growth_title)
        growth_header.addStretch(1)
        growth_header.addWidget(self.range_bar)
        growth_layout.addLayout(growth_header)

        self.growth_chart = AreaChart(growth)
        growth_layout.addWidget(self.growth_chart, 1)
        charts.addWidget(growth, 2)

        share = QFrame(page)
        set_role(share, "card")
        share_layout = QVBoxLayout(share)
        share_layout.setContentsMargins(16, 14, 16, 14)
        share_layout.setSpacing(10)
        self.share_title = QLabel(self.tr_.tr("wallet.share"))
        set_role(self.share_title, "section")
        share_layout.addWidget(self.share_title)
        self.share_chart = DonutChart(share)
        share_layout.addWidget(self.share_chart, 1, Qt.AlignmentFlag.AlignCenter)
        self.share_legend = QVBoxLayout()
        self.share_legend.setSpacing(4)
        share_layout.addLayout(self.share_legend)
        charts.addWidget(share, 1)

        layout.addLayout(charts, 1)

        # --- جدول دارایی‌ها ---
        assets = QFrame(page)
        set_role(assets, "card")
        assets_layout = QVBoxLayout(assets)
        assets_layout.setContentsMargins(16, 14, 16, 14)
        assets_layout.setSpacing(8)
        self.assets_title = QLabel(self.tr_.tr("wallet.assets"))
        set_role(self.assets_title, "section")
        assets_layout.addWidget(self.assets_title)

        self.assets_table = QTableWidget(0, 6, assets)
        configure_table(self.assets_table, stretch_column=0)
        self.assets_table.setCursor(Qt.CursorShape.PointingHandCursor)
        self.assets_table.cellClicked.connect(self._on_asset_clicked)
        assets_layout.addWidget(self.assets_table)
        layout.addWidget(assets, 1)

        return page

    def _build_spot_tab(self) -> QWidget:
        """زبانهٔ اسپات: خلاصه + جدول آزاد/قفل/کل/ارزش."""
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)
        self.spot_strip = MetricStrip(SPOT_METRICS, parent=page)
        layout.addWidget(self.spot_strip)

        card = QFrame(page)
        set_role(card, "card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(8)
        self.spot_title = QLabel("")
        set_role(self.spot_title, "section")
        card_layout.addWidget(self.spot_title)
        self.spot_table = QTableWidget(0, len(SPOT_COLUMNS), card)
        configure_table(self.spot_table, stretch_column=0)
        self.spot_table.cellClicked.connect(lambda row, _c: self._emit_row_asset(self._spot_rows, row))
        card_layout.addWidget(self.spot_table)
        self.spot_empty = QLabel("")
        set_role(self.spot_empty, "faint")
        self.spot_empty.setWordWrap(True)
        self.spot_empty.setVisible(False)
        card_layout.addWidget(self.spot_empty)
        layout.addWidget(card, 1)
        return page

    def _build_futures_tab(self) -> QWidget:
        """زبانهٔ فیوچرز: equity/مارجین/سود شناور + جدول هر دارایی."""
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)
        self.futures_strip = MetricStrip(FUTURES_METRICS, parent=page)
        layout.addWidget(self.futures_strip)

        card = QFrame(page)
        set_role(card, "card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(8)
        self.futures_title = QLabel("")
        set_role(self.futures_title, "section")
        card_layout.addWidget(self.futures_title)
        self.futures_table = QTableWidget(0, len(FUTURES_COLUMNS), card)
        configure_table(self.futures_table, stretch_column=0)
        card_layout.addWidget(self.futures_table)
        self.futures_note = QLabel("")
        set_role(self.futures_note, "faint")
        self.futures_note.setWordWrap(True)
        self.futures_note.setVisible(False)
        card_layout.addWidget(self.futures_note)
        layout.addWidget(card, 1)
        return page

    def _build_empty(self) -> QWidget:
        """حالت «حساب صرافی متصل نیست»."""
        holder = QWidget(self)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)

        self.empty_state = EmptyState(holder)
        self.empty_state.configure(
            icon="◍",
            title=self.tr_.tr("wallet.no_account"),
            detail=self.tr_.tr("wallet.no_account_hint"),
            action=self.tr_.tr("wallet.connect_account"),
        )
        self.empty_state.action_clicked.connect(self.connect_requested)
        layout.addWidget(self.empty_state)
        return holder

    # ------------------------------------------------------------------
    # داده
    # ------------------------------------------------------------------
    def set_connected(self, connected: bool) -> None:
        """
        تعیین اینکه حساب صرافی متصل است یا نه.

        تنها این متد تصمیم می‌گیرد کدام نما دیده شود تا منطق در یک نقطه
        بماند.
        """
        self.stack.setCurrentIndex(0 if connected else 1)

    def set_busy(self, busy: bool) -> None:
        """
        غیرفعال‌کردن دکمهٔ همگام‌سازی هنگام دریافت داده.

        بدون این، کاربر چند بار پشت‌سرهم می‌زند و چند درخواست هم‌زمان به
        صرافی می‌رود.
        """
        self.refresh_button.setEnabled(not busy)

    def set_summary(
        self,
        *,
        total: str,
        available: str,
        pnl: str,
        pnl_delta: float | None = None,
        total_series: list[float] | None = None,
        toman: str = "",
        wallet_split: str = "",
    ) -> None:
        """
        به‌روزرسانی سه کارت بالای صفحه.

        `wallet_split` تفکیک اسپات/فیوچرز است؛ کاربری که سرمایه‌اش بین دو
        کیف پول صرافی پخش است باید بدون باز کردن جدول هم آن را ببیند.
        """
        self.total_card.set_data(
            title=self.tr_.tr("wallet.total_value"),
            value=total,
            caption=toman,
            series=total_series or [],
        )
        self.available_card.set_data(
            title=self.tr_.tr("wallet.available"),
            value=available,
            caption=wallet_split,
        )
        self.pnl_card.set_data(
            title=self.tr_.tr("wallet.profit_loss"), value=pnl, delta=pnl_delta
        )

    def set_assets(self, assets: list[dict[str, Any]]) -> None:
        """
        پرکردن جدول دارایی‌ها و دونات سهم.

        هر قلم: `{"asset","amount","value","share","change"}`.
        """
        self._assets = list(assets or [])
        table = self.assets_table
        table.setSortingEnabled(False)
        table.setRowCount(len(self._assets))

        for row, item in enumerate(self._assets):
            symbol = QTableWidgetItem(str(item.get("asset", "")))
            # نماد ارز نباید در چیدمان راست‌به‌چپ جابه‌جا شود
            symbol.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            table.setItem(row, 0, symbol)
            table.setItem(row, 1, self._cell(item.get("amount_text", "")))
            table.setItem(row, 2, self._cell(item.get("value_text", "")))
            table.setItem(row, 3, self._cell(item.get("share_text", "")))

            # ستون «نوع کیف پول»: اسپات، فیوچرز یا هر دو
            table.setItem(row, 5, self._cell(item.get("wallet_text", "")))

            change = item.get("change")
            change_item = self._cell(item.get("change_text", ""))
            if isinstance(change, (int, float)) and self._theme is not None:
                colors = self._theme.colors
                from PySide6.QtGui import QColor

                change_item.setForeground(
                    QColor(colors.success if change >= 0 else colors.danger)
                )
            table.setItem(row, 4, change_item)

        # دونات: پنج دارایی نخست، بقیه در «سایر»
        segments: list[tuple[str, float, str]] = []
        palette = ["primary", "accent", "success", "warning", "info"]
        top = self._assets[:5]
        for index, item in enumerate(top):
            segments.append(
                (str(item.get("asset", "")), float(item.get("share") or 0.0), palette[index % len(palette)])
            )
        remainder = sum(float(item.get("share") or 0.0) for item in self._assets[5:])
        if remainder > 0:
            segments.append((self.tr_.tr("common.all"), remainder, "neutral"))
        self.share_chart.set_segments(segments, center_label=str(len(self._assets)))
        self._render_legend(segments)

    def set_paper(self, values: dict[str, Any], *, source_text: str = "",
                  colors: dict[str, str] | None = None, card_value: str = "",
                  card_caption: str = "") -> None:
        """پنل حساب کاغذی (v2.5.0) و کارت چهارم نمای کلی."""
        self.paper_strip.set_values(values, colors)
        self.paper_source_label.setText(source_text)
        self.paper_card.set_data(
            title=self.tr_.tr("wallet.paper.card_title"),
            value=card_value or str(values.get("equity", "—")),
            caption=card_caption,
        )

    def set_spot(self, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        """
        زبانهٔ اسپات.

        هر ردیف: `asset` و متن‌های `free_text, locked_text, total_text,
        price_text, value_text, share_text, change_text` (+ `change` عددی).
        """
        self._spot_rows = list(rows or [])
        self.spot_strip.set_values(summary)
        self._fill_table(self.spot_table, SPOT_COLUMNS, self._spot_rows)
        self.spot_empty.setText(self.tr_.tr("wallet.spot_tab.empty"))
        self.spot_empty.setVisible(not self._spot_rows)

    def set_futures(self, rows: list[dict[str, Any]], summary: dict[str, Any],
                    *, note: str = "", colors: dict[str, str] | None = None) -> None:
        """
        زبانهٔ فیوچرز.

        هر ردیف: `asset` و متن‌های `equity_text, wallet_text, available_text,
        margin_text, frozen_text, unrealized_text, value_text` (+ `unrealized`).
        """
        self._futures_rows = list(rows or [])
        self.futures_strip.set_values(summary, colors)
        self._fill_table(self.futures_table, FUTURES_COLUMNS, self._futures_rows)
        self.futures_note.setText(note)
        self.futures_note.setVisible(bool(note))

    def _fill_table(self, table: QTableWidget, columns: tuple[str, ...],
                    rows: list[dict[str, Any]]) -> None:
        """پرکردن یک جدول جزئیات با رنگ سبز/قرمز برای ستون‌های تغییر/سود."""
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        colors = self._theme.colors if self._theme is not None else None
        for row_index, row in enumerate(rows):
            for column, name in enumerate(columns):
                if name == "asset":
                    item = QTableWidgetItem(str(row.get("asset", "")))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                else:
                    item = self._cell(row.get(f"{name}_text", "—") or "—")
                    signed = row.get(name) if name in ("change", "unrealized") else None
                    if colors is not None and isinstance(signed, (int, float)) and signed != 0:
                        item.setForeground(QColor(colors.success if signed > 0 else colors.danger))
                table.setItem(row_index, column, item)

    def _emit_row_asset(self, rows: list[dict[str, Any]], index: int) -> None:
        if 0 <= index < len(rows):
            self.asset_activated.emit(str(rows[index].get("asset", "")))

    def set_growth(self, values: list[float], labels: list[str] | None = None) -> None:
        """تنظیم منحنی رشد سرمایه."""
        self.growth_chart.set_series(values, labels=labels or [])

    def set_last_sync(self, text: str) -> None:
        """نمایش زمان آخرین همگام‌سازی."""
        self.sync_label.setText(
            self.tr_.tr("wallet.last_sync", time=text) if text else self.tr_.tr("wallet.never_synced")
        )

    def asset_row(self, index: int) -> dict[str, Any] | None:
        """داده یک ردیف جدول برای بازکردن جزئیات."""
        if 0 <= index < len(self._assets):
            return self._assets[index]
        return None

    # ------------------------------------------------------------------
    # پوسته و زبان
    # ------------------------------------------------------------------
    def apply_theme(self, theme: Any) -> None:
        """انتقال پوسته به اجزای نقاشی‌شده که QSS نمی‌گیرند."""
        self._theme = theme
        for card in (self.total_card, self.available_card, self.pnl_card, self.paper_card):
            card.apply_theme(theme)
        self.growth_chart.apply_theme(theme)
        self.share_chart.apply_theme(theme)
        # رنگ ستون تغییر با پوستهٔ تازه بازسازی می‌شود
        if self._assets:
            self.set_assets(self._assets)
        if self._spot_rows:
            self._fill_table(self.spot_table, SPOT_COLUMNS, self._spot_rows)
        if self._futures_rows:
            self._fill_table(self.futures_table, FUTURES_COLUMNS, self._futures_rows)

    def retranslate(self) -> None:
        """بازسازی متن‌ها پس از تغییر زبان."""
        super().retranslate()
        self.refresh_button.setText(self.tr_.tr("wallet.sync"))
        self.growth_title.setText(self.tr_.tr("wallet.growth"))
        self.share_title.setText(self.tr_.tr("wallet.share"))
        self.assets_title.setText(self.tr_.tr("wallet.assets"))
        self.range_bar.set_labels(
            {key: self.tr_.tr(f"wallet.range.{key}") for key in RANGE_KEYS}
        )
        self.empty_state.configure(
            icon="◍",
            title=self.tr_.tr("wallet.no_account"),
            detail=self.tr_.tr("wallet.no_account_hint"),
            action=self.tr_.tr("wallet.connect_account"),
        )
        self._retranslate_headers()
        self._retranslate_tabs()

    # ------------------------------------------------------------------
    # داخلی
    # ------------------------------------------------------------------
    def _retranslate_headers(self) -> None:
        """عنوان ستون‌های جدول دارایی‌ها."""
        self.assets_table.setHorizontalHeaderLabels(
            [
                self.tr_.tr("wallet.asset"),
                self.tr_.tr("wallet.amount"),
                self.tr_.tr("wallet.value"),
                self.tr_.tr("wallet.share"),
                self.tr_.tr("wallet.change_24h"),
                self.tr_.tr("wallet.wallet_type"),
            ]
        )
        self.spot_table.setHorizontalHeaderLabels(
            [self.tr_.tr(f"wallet.spot_tab.col_{name}") for name in SPOT_COLUMNS]
        )
        self.futures_table.setHorizontalHeaderLabels(
            [self.tr_.tr(f"wallet.futures_tab.col_{name}") for name in FUTURES_COLUMNS]
        )

    def _retranslate_tabs(self) -> None:
        """عنوان زبانه‌ها، نوارهای خلاصه و پنل کاغذی."""
        for index, key in enumerate(WALLET_TABS):
            self.tabs.setTabText(index, self.tr_.tr(f"wallet.tabs.{key}"))
        self.spot_strip.set_labels({k: self.tr_.tr(f"wallet.spot_tab.m_{k}") for k in SPOT_METRICS})
        self.futures_strip.set_labels(
            {k: self.tr_.tr(f"wallet.futures_tab.m_{k}") for k in FUTURES_METRICS}
        )
        self.paper_strip.set_labels({k: self.tr_.tr(f"wallet.paper.m_{k}") for k in PAPER_METRICS})
        self.paper_title.setText(self.tr_.tr("wallet.paper.title"))
        self.paper_sync_button.setText(self.tr_.tr("wallet.paper.sync"))
        self.paper_sync_button.setToolTip(self.tr_.tr("wallet.paper.sync_tip"))
        self.spot_title.setText(self.tr_.tr("wallet.spot_tab.title"))
        self.futures_title.setText(self.tr_.tr("wallet.futures_tab.title"))

    def _render_legend(self, segments: list[tuple[str, float, str]]) -> None:
        """ساخت راهنمای رنگ دونات."""
        while self.share_legend.count():
            item = self.share_legend.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for label, value, color_name in segments:
            row = QWidget(self)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            dot = QLabel("●", row)
            if self._theme is not None:
                color = getattr(self._theme.colors, color_name, "")
                dot.setStyleSheet(f"color: {color};")
            name = QLabel(label, row)
            share = QLabel(f"{value:.1f}%", row)
            set_role(share, "muted")

            row_layout.addWidget(dot)
            row_layout.addWidget(name)
            row_layout.addStretch(1)
            row_layout.addWidget(share)
            self.share_legend.addWidget(row)

    @staticmethod
    def _cell(text: str) -> QTableWidgetItem:
        """ساخت خانهٔ جدول با چینش مناسب اعداد."""
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def _on_asset_clicked(self, row: int, _column: int) -> None:
        """انتشار نماد دارایی هنگام کلیک."""
        data = self.asset_row(row)
        if data:
            self.asset_activated.emit(str(data.get("asset", "")))


__all__ = [
    "FUTURES_COLUMNS",
    "MetricStrip",
    "RANGE_KEYS",
    "SPOT_COLUMNS",
    "WALLET_TABS",
    "WalletPage",
]
