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
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStackedWidget,
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

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._assets: list[dict[str, Any]] = []
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

    def _build_content(self) -> QWidget:
        """نمای اصلی صفحه."""
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # --- کارت‌های آمار ---
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.total_card = StatCard(icon="◎")
        self.available_card = StatCard(icon="◍")
        self.pnl_card = StatCard(icon="◈")
        for card in (self.total_card, self.available_card, self.pnl_card):
            cards.addWidget(card)
        layout.addLayout(cards)

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

        self._retranslate_headers()
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
        for card in (self.total_card, self.available_card, self.pnl_card):
            card.apply_theme(theme)
        self.growth_chart.apply_theme(theme)
        self.share_chart.apply_theme(theme)
        # رنگ ستون تغییر با پوستهٔ تازه بازسازی می‌شود
        if self._assets:
            self.set_assets(self._assets)

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


__all__ = ["RANGE_KEYS", "WalletPage"]
