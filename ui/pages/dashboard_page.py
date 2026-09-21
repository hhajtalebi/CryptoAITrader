"""
صفحه داشبورد.

نمای کلی: وضعیت اتصال، خلاصه بازار نمادهای منتخب، و آخرین سیگنال‌ها.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from localization import Translator
from ui.pages.base_page import BasePage
from ui.widgets.arrangeable import ArrangeableContainer
from ui.widgets import (
    Card,
    KeyValueRow,
    RefreshButton,
    SegmentedControl,
    Sparkline,
    StatCard,
    StatusPill,
    TickerStrip,
    configure_table,
    make_button,
)

#: تایم‌فریم‌های نوار بالای داشبورد (مطابق طرح‌ها)
TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d", "1w")

#: ترتیب پیش‌فرض بخش‌های داشبورد. کاربر می‌تواند این ترتیب را عوض کند و
#: انتخابش ذخیره می‌شود؛ این فقط نقطهٔ شروع است.
DEFAULT_BLOCK_ORDER = ("ticker", "stats", "overview", "signals")


class DashboardPage(BasePage):
    """صفحه نخست برنامه."""

    title_key = "nav.dashboard"
    subtitle_key = "dashboard.subtitle"

    #: کاربر روی نام یک ارز در جدول خلاصهٔ بازار کلیک کرد (نماد)
    coin_activated = Signal(str)
    #: تایم‌فریم فعال داشبورد عوض شد
    timeframe_changed = Signal(str)
    #: چیدمان کارت‌ها تغییر کرد (رشتهٔ قابل ذخیره)
    layout_changed = Signal(str)

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._market_rows: list[dict[str, Any]] = []
        self._status_rows: dict[str, KeyValueRow] = {}
        self._theme: Any = None
        super().__init__(translator, parent)

    def build(self) -> None:
        """ساخت کارت‌های وضعیت، بازار و سیگنال."""
        self.refresh_button = RefreshButton(
            self.tr_.tr("common.refresh"),
            busy_text=self.tr_.tr("markets.updating"),
            done_text=self.tr_.tr("common.refresh"),
        )
        self.header.add_action(self.refresh_button)

        self.status_pill = StatusPill(self.tr_.tr("common.disconnected"))
        self.header.add_action(self.status_pill)

        # دکمهٔ حالت چیدمان: کاربر خواست بتواند ترتیب کارت‌ها را خودش
        # تعیین کند. کنترل‌های جابه‌جایی تا وقتی این دکمه زده نشده پنهان
        # می‌مانند تا صفحهٔ عادی شلوغ نشود.
        self.arrange_button = make_button("", role="ghost", checkable=True)
        self.arrange_button.toggled.connect(self._on_arrange_toggled)
        self.header.add_action(self.arrange_button)

        # ظرف بخش‌های جابه‌جاشدنی
        self.blocks = ArrangeableContainer(self.tr_, self)
        self.blocks.layout_changed.connect(self.layout_changed)
        self.layout_root().addWidget(self.blocks, 1)

        # نوار قیمت زنده — نخستین چیزی که در طرح‌ها دیده می‌شود
        self.ticker = TickerStrip(self)
        self.ticker.symbol_clicked.connect(self.coin_activated)
        self.blocks.add_block("ticker", self.tr_.tr("dashboard.block_ticker"), self.ticker)

        # چهار کارت آمار
        stats_holder = QWidget()
        cards = QHBoxLayout(stats_holder)
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setSpacing(12)
        self.stat_cards: dict[str, StatCard] = {}
        # نکته: کلید `market_cap` به دلایل سازگاری حفظ شده ولی محتوای آن
        # «سهم بازارهای صعودی» است؛ برچسبش هم همین را می‌گوید.
        for key, icon in (
            ("market_cap", "◎"),
            ("volume", "◫"),
            ("signals_today", "◈"),
            ("win_rate", "✦"),
        ):
            card = StatCard(icon=icon)
            card.set_data(title=self.tr_.tr(f"dashboard.stats.{key}"), value="—")
            self.stat_cards[key] = card
            cards.addWidget(card)
        self.blocks.add_block("stats", self.tr_.tr("dashboard.block_stats"), stats_holder)

        # نوار تایم‌فریم
        self.timeframe_bar = SegmentedControl(
            [(value, value.upper()) for value in TIMEFRAMES]
        )
        self.timeframe_bar.set_current("1h", emit=False)
        self.timeframe_bar.selection_changed.connect(self.timeframe_changed)
        timeframe_holder = QWidget()
        timeframe_row = QHBoxLayout(timeframe_holder)
        timeframe_row.setContentsMargins(0, 0, 0, 0)
        timeframe_row.addWidget(self.timeframe_bar)
        timeframe_row.addStretch(1)
        self.layout_root().insertWidget(
            self.layout_root().indexOf(self.blocks), timeframe_holder
        )

        overview_holder = QWidget()
        grid = QGridLayout(overview_holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        # کارت وضعیت سامانه
        self.status_card = Card(self.tr_.tr("dashboard.system_status"))
        for key in ("exchange", "connection", "ai_provider", "last_update"):
            row = KeyValueRow(self.tr_.tr(f"dashboard.{key}"))
            self._status_rows[key] = row
            self.status_card.add(row)
        grid.addWidget(self.status_card, 0, 0)

        # کارت خلاصه بازار
        self.market_card = Card(self.tr_.tr("dashboard.market_overview"))
        self.market_table = QTableWidget(0, 5)
        self.market_table.setAlternatingRowColors(True)
        self.market_table.verticalHeader().setVisible(False)
        self.market_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.market_table.setCursor(Qt.CursorShape.PointingHandCursor)
        self.market_table.cellClicked.connect(self._on_market_cell_clicked)
        self.market_card.add(self.market_table)
        grid.addWidget(self.market_card, 0, 1)

        self.blocks.add_block(
            "overview", self.tr_.tr("dashboard.block_overview"), overview_holder
        )

        # کارت آخرین سیگنال‌ها
        self.signals_card = Card(self.tr_.tr("dashboard.recent_signals"))
        self.signals_table = QTableWidget(0, 5)
        self.signals_table.setAlternatingRowColors(True)
        self.signals_table.verticalHeader().setVisible(False)
        self.signals_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.signals_card.add(self.signals_table)
        self.blocks.add_block(
            "signals", self.tr_.tr("dashboard.block_signals"), self.signals_card, stretch=1
        )

        self._sync_arrange_button()

        self.disclaimer = QLabel(self.tr_.tr("signals.not_financial_advice"))
        self.disclaimer.setProperty("role", "muted")
        self.disclaimer.setWordWrap(True)
        self.layout_root().addWidget(self.disclaimer)

        self._apply_headers()

    def _apply_headers(self) -> None:
        """تنظیم سرستون‌های جدول‌ها بر پایه زبان جاری."""
        self.market_table.setHorizontalHeaderLabels([
            self.tr_.tr("common.symbol"), self.tr_.tr("common.price"),
            self.tr_.tr("common.change"), self.tr_.tr("common.volume"),
            self.tr_.tr("markets.trend"),
        ])
        self.signals_table.setHorizontalHeaderLabels([
            self.tr_.tr("common.symbol"), self.tr_.tr("signals.direction"),
            self.tr_.tr("signals.confidence"), self.tr_.tr("signals.risk_reward"),
            self.tr_.tr("signals.generated_at"),
        ])
        configure_table(self.market_table, stretch_column=0)
        configure_table(self.signals_table, stretch_column=4)

    # ------------------------------------------------------------------
    # به‌روزرسانی داده
    # ------------------------------------------------------------------
    def set_connection_status(self, status: str, role: str = "neutral") -> None:
        """به‌روزرسانی نشانگر وضعیت اتصال."""
        self.status_pill.set_status(status, role)

    def set_status_value(self, key: str, value: str, role: str = "") -> None:
        """به‌روزرسانی یک سطر از کارت وضعیت."""
        if key in self._status_rows:
            self._status_rows[key].set_value(value, role)

    def set_market_rows(self, rows: list[dict[str, Any]]) -> None:
        """
        پر کردن جدول خلاصه بازار.

        ستون آخر یک نمودار کوچک روند است؛ اگر تاریخچه‌ای نرسیده باشد خالی
        می‌ماند و ردیف همچنان درست نمایش داده می‌شود.
        """
        self._market_rows = [dict(r) for r in rows]
        self.market_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            change = float(row.get("change_percent", 0.0) or 0.0)
            values = [
                row.get("symbol", ""),
                self.tr_.format_number(row.get("price", 0.0), 2),
                f"\u200e{change:+.2f}%",
                self.tr_.format_number(row.get("volume", 0.0), 0),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    # نماد بازار نباید در چیدمان راست‌به‌چپ به‌هم بریزد
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 2 and self._theme is not None:
                    colors = self._theme.colors
                    item.setForeground(
                        QColor(colors.success if change >= 0 else colors.danger)
                    )
                self.market_table.setItem(index, column, item)

            history = row.get("history") or []
            if history:
                spark = Sparkline()
                if self._theme is not None:
                    spark.apply_theme(self._theme)
                spark.set_values([float(value) for value in history])
                self.market_table.setCellWidget(index, 4, spark)
            else:
                self.market_table.setCellWidget(index, 4, None)

    def set_ticker_items(self, items: list[dict[str, Any]]) -> None:
        """تنظیم اقلام نوار قیمت زنده."""
        self.ticker.set_items(items)

    def set_stat(self, key: str, value: str, *, delta: float | None = None,
                 caption: str = "", series: list[float] | None = None) -> None:
        """
        به‌روزرسانی یکی از چهار کارت آمار.

        کلیدهای معتبر: `market_cap`، `volume`، `signals_today`، `win_rate`.
        """
        card = self.stat_cards.get(key)
        if card is None:
            return
        card.set_data(
            title=self.tr_.tr(f"dashboard.stats.{key}"),
            value=value,
            delta=delta,
            caption=caption,
            series=series or [],
        )

    def apply_theme(self, theme: Any) -> None:
        """انتقال پوسته به کارت‌ها و نمودارهای کوچک."""
        self._theme = theme
        for card in self.stat_cards.values():
            card.apply_theme(theme)
        self.ticker.apply_theme(theme)
        if self._market_rows:
            self.set_market_rows(self._market_rows)

    def _on_market_cell_clicked(self, row: int, column: int) -> None:  # noqa: ARG002
        """کلیک روی هر ردیف، مدال جزئیات همان ارز را باز می‌کند."""
        item = self.market_table.item(row, 0)
        if item is not None and item.text():
            self.coin_activated.emit(item.text())

    def market_row_data(self, symbol: str) -> dict[str, Any]:
        """دادهٔ خام یک نماد برای پر کردن مدال جزئیات."""
        for row in self._market_rows:
            if str(row.get("symbol", "")) == str(symbol):
                return dict(row)
        return {}

    def set_signal_rows(self, rows: list[dict[str, Any]]) -> None:
        """پر کردن جدول آخرین سیگنال‌ها."""
        self.signals_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            direction = str(row.get("direction", "WAIT")).lower()
            values = [
                row.get("symbol", ""),
                self.tr_.tr(f"signals.{direction}", direction.upper()),
                f"{row.get('confidence', 0)}%",
                f"{row.get('risk_reward'):.2f}" if row.get("risk_reward") else "—",
                str(row.get("created_at", "")),
            ]
            for column, value in enumerate(values):
                self.signals_table.setItem(index, column, QTableWidgetItem(str(value)))

    # ------------------------------------------------------------------
    # چیدمان قابل تنظیم
    # ------------------------------------------------------------------
    def _arrange_text(self) -> str:
        """متن دکمهٔ حالت چیدمان بر پایهٔ وضعیت فعلی."""
        key = "layout.done" if self.arrange_button.isChecked() else "layout.arrange"
        return self.tr_.tr(key)

    def _sync_arrange_button(self) -> None:
        """هماهنگ‌کردن متن و راهنمای دکمه."""
        self.arrange_button.setText(self._arrange_text())
        self.arrange_button.setToolTip(self.tr_.tr("layout.arrange_hint"))

    def _on_arrange_toggled(self, enabled: bool) -> None:
        """ورود و خروج از حالت چیدمان."""
        self.blocks.set_arrange_mode(bool(enabled))
        self._sync_arrange_button()

    def layout_state(self) -> str:
        """چیدمان فعلی به رشته‌ای قابل ذخیره."""
        return self.blocks.serialise()

    def apply_layout_state(self, state: str) -> None:
        """اعمال چیدمان ذخیره‌شدهٔ کاربر."""
        self.blocks.apply_state(state)

    def reset_layout(self) -> None:
        """بازگرداندن چیدمان به ترتیب پیش‌فرض."""
        self.blocks.reset(list(DEFAULT_BLOCK_ORDER))

    def retranslate(self) -> None:
        """بازسازی همه متن‌های صفحه."""
        super().retranslate()
        self.refresh_button.set_texts(
            self.tr_.tr("common.refresh"),
            self.tr_.tr("markets.updating"),
            self.tr_.tr("common.refresh"),
        )
        self.arrange_button.setText(self._arrange_text())
        self.blocks.retranslate()
        for key, label_key in (
            ("ticker", "dashboard.block_ticker"),
            ("stats", "dashboard.block_stats"),
            ("overview", "dashboard.block_overview"),
            ("signals", "dashboard.block_signals"),
        ):
            block = self.blocks.blocks.get(key)
            if block is not None:
                block.set_title(self.tr_.tr(label_key))
        self.status_card.set_title(self.tr_.tr("dashboard.system_status"))
        self.market_card.set_title(self.tr_.tr("dashboard.market_overview"))
        self.signals_card.set_title(self.tr_.tr("dashboard.recent_signals"))
        for key, row in self._status_rows.items():
            row.set_key(self.tr_.tr(f"dashboard.{key}"))
        self.disclaimer.setText(self.tr_.tr("signals.not_financial_advice"))
        for key, card in self.stat_cards.items():
            card.set_data(title=self.tr_.tr(f"dashboard.stats.{key}"))
        self._apply_headers()
