"""
پنجرهٔ جزئیات کامل یک ارز.

کاربر خواست با کلیک روی نام هر ارز — چه در داشبورد و چه در صفحهٔ بازارها —
یک مدال باز شود که همهٔ جزئیات آن ارز را نشان دهد و از همان‌جا بتواند اقدام
کند.

طراحی این پنجره سه اصل دارد:

۱. **بی‌درنگ باز می‌شود.** داده‌ای که همان لحظه در جدول موجود است فوراً
   نمایش داده می‌شود و بقیهٔ اطلاعات (اندیکاتورها، سطوح، عمق بازار) پس از
   دریافت پر می‌شوند. کاربر پشت یک پنجرهٔ خالی منتظر نمی‌ماند.

۲. **هیچ اقدامی خودکار نیست.** دکمه‌ها فقط با کلیک صریح کاربر کار می‌کنند.

۳. **بدون رشتهٔ سخت‌کدشده.** همهٔ متن‌ها از فایل‌های ترجمه می‌آیند تا
   فارسی (راست‌به‌چپ) و انگلیسی هر دو درست نمایش داده شوند.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from market.timeframes import SUPPORTED_TIMEFRAMES
from localization import Translator
from ui.widgets import make_button


class CoinDetailDialog(QDialog):
    """
    نمایش جزئیات یک ارز به‌همراه دکمه‌های اقدام.

    مثال:
        dialog = CoinDetailDialog("BTC/USDT", row_data, translator, parent)
        dialog.analyze_requested.connect(handler)
        dialog.exec()
    """

    #: درخواست تحلیل با هوش مصنوعی — (symbol, timeframe)
    analyze_requested = Signal(str, str)
    #: درخواست تولید سیگنال — (symbol, timeframe)
    signal_requested = Signal(str, str)
    #: درخواست رفتن به صفحهٔ بازارها با همین نماد
    open_market_requested = Signal(str)
    #: درخواست گفت‌وگو دربارهٔ این ارز در بخش چت
    chat_requested = Signal(str, str)
    #: افزودن/برداشتن از واچ‌لیست
    watchlist_toggled = Signal(str, bool)

    def __init__(
        self,
        symbol: str,
        snapshot: dict[str, Any] | None,
        translator: Translator,
        parent: QWidget | None = None,
        *,
        in_watchlist: bool = False,
    ) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._symbol = str(symbol or "")
        self._snapshot = dict(snapshot or {})
        self._in_watchlist = bool(in_watchlist)
        self._detail_rows: dict[str, QLabel] = {}

        self.setWindowTitle(self.tr_.tr("markets.detail_title", symbol=self._symbol))
        self.setMinimumSize(560, 640)
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if self.tr_.is_rtl else Qt.LayoutDirection.LeftToRight
        )
        self._build()
        self.apply_snapshot(self._snapshot)

    # ------------------------------------------------------------------
    # ساخت رابط
    # ------------------------------------------------------------------
    def _build(self) -> None:
        """چیدمان کلی پنجره."""
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        root.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)

        body_layout.addWidget(self._build_stats())
        body_layout.addWidget(self._build_details())
        body_layout.addStretch(1)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        root.addWidget(self._build_actions())

        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setTextVisible(False)
        self.busy.setFixedHeight(3)
        self.busy.hide()
        root.addWidget(self.busy)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

    def _build_header(self) -> QWidget:
        """سربرگ: نماد، قیمت لحظه‌ای و درصد تغییر."""
        frame = QFrame()
        frame.setProperty("role", "card")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)

        left = QVBoxLayout()
        self.symbol_label = QLabel(self._symbol or "—")
        self.symbol_label.setProperty("role", "title")
        font = self.symbol_label.font()
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        self.symbol_label.setFont(font)
        left.addWidget(self.symbol_label)

        self.toman_label = QLabel("")
        self.toman_label.setProperty("role", "muted")
        left.addWidget(self.toman_label)
        layout.addLayout(left)
        layout.addStretch(1)

        right = QVBoxLayout()
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.price_label = QLabel("—")
        price_font = self.price_label.font()
        price_font.setPointSize(price_font.pointSize() + 6)
        price_font.setBold(True)
        self.price_label.setFont(price_font)
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.price_label)

        self.change_label = QLabel("")
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.change_label)
        layout.addLayout(right)
        return frame

    def _build_stats(self) -> QWidget:
        """کارت آمار ۲۴ ساعته."""
        frame = QFrame()
        frame.setProperty("role", "card")
        grid = QGridLayout(frame)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)

        self._stat_labels: dict[str, QLabel] = {}
        keys = [
            ("high", "markets.high_24h"),
            ("low", "markets.low_24h"),
            ("volume", "markets.volume"),
            ("quote_volume", "markets.quote_volume"),
        ]
        for index, (key, tr_key) in enumerate(keys):
            row, column = divmod(index, 2)
            caption = QLabel(self.tr_.tr(tr_key))
            caption.setProperty("role", "muted")
            value = QLabel("—")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(caption, row * 2, column)
            grid.addWidget(value, row * 2 + 1, column)
            self._stat_labels[key] = value
        return frame

    def _build_details(self) -> QWidget:
        """کارت جزئیات تکمیلی که پس از دریافت داده پر می‌شود."""
        frame = QFrame()
        frame.setProperty("role", "card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel(self.tr_.tr("markets.technical_snapshot"))
        title.setProperty("role", "subtitle")
        layout.addWidget(title)

        self._details_grid = QGridLayout()
        self._details_grid.setHorizontalSpacing(18)
        self._details_grid.setVerticalSpacing(8)
        layout.addLayout(self._details_grid)

        self.details_hint = QLabel(self.tr_.tr("markets.loading_details"))
        self.details_hint.setProperty("role", "muted")
        self.details_hint.setWordWrap(True)
        layout.addWidget(self.details_hint)
        return frame

    def _build_actions(self) -> QWidget:
        """نوار دکمه‌های اقدام و انتخاب تایم‌فریم."""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        tf_row = QHBoxLayout()
        tf_caption = QLabel(self.tr_.tr("common.timeframe"))
        tf_caption.setProperty("role", "muted")
        tf_row.addWidget(tf_caption)
        self.timeframe_combo = QComboBox()
        for timeframe in SUPPORTED_TIMEFRAMES:
            self.timeframe_combo.addItem(timeframe.code, timeframe.code)
        default_index = self.timeframe_combo.findData("4h")
        self.timeframe_combo.setCurrentIndex(default_index if default_index >= 0 else 0)
        tf_row.addWidget(self.timeframe_combo)
        tf_row.addStretch(1)
        layout.addLayout(tf_row)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        self.analyze_button = make_button(self.tr_.tr("markets.action_analyze"), primary=True)
        self.analyze_button.clicked.connect(
            lambda: self.analyze_requested.emit(self._symbol, self.selected_timeframe())
        )
        buttons.addWidget(self.analyze_button)

        self.signal_button = make_button(self.tr_.tr("markets.action_signal"))
        self.signal_button.clicked.connect(
            lambda: self.signal_requested.emit(self._symbol, self.selected_timeframe())
        )
        buttons.addWidget(self.signal_button)

        self.chat_button = make_button(self.tr_.tr("markets.action_chat"))
        self.chat_button.clicked.connect(
            lambda: self.chat_requested.emit(self._symbol, self.selected_timeframe())
        )
        buttons.addWidget(self.chat_button)
        layout.addLayout(buttons)

        secondary = QHBoxLayout()
        secondary.setSpacing(8)

        self.market_button = make_button(self.tr_.tr("markets.action_open_market"))
        self.market_button.clicked.connect(lambda: self.open_market_requested.emit(self._symbol))
        secondary.addWidget(self.market_button)

        self.watchlist_button = make_button(self._watchlist_text())
        self.watchlist_button.clicked.connect(self._toggle_watchlist)
        secondary.addWidget(self.watchlist_button)

        secondary.addStretch(1)
        self.close_button = make_button(self.tr_.tr("common.close"))
        self.close_button.clicked.connect(self.accept)
        secondary.addWidget(self.close_button)
        layout.addLayout(secondary)
        return frame

    # ------------------------------------------------------------------
    # داده
    # ------------------------------------------------------------------
    def selected_timeframe(self) -> str:
        """تایم‌فریم انتخاب‌شدهٔ کاربر."""
        return str(self.timeframe_combo.currentData() or "4h")

    def apply_snapshot(self, snapshot: dict[str, Any]) -> None:
        """نمایش دادهٔ اولیه‌ای که هم‌اکنون در جدول موجود است."""
        if not snapshot:
            return
        self._snapshot.update(snapshot)
        price = snapshot.get("price")
        if price is not None:
            self.price_label.setText(self._format_number(price))
        change = snapshot.get("change_percent")
        if change is not None:
            self._apply_change(float(change))
        toman = snapshot.get("toman")
        if toman:
            self.toman_label.setText(str(toman))
        for key in ("high", "low", "volume", "quote_volume"):
            if snapshot.get(key) is not None:
                self._stat_labels[key].setText(self._format_number(snapshot[key]))

    def apply_details(self, details: dict[str, Any]) -> None:
        """
        پر کردن بخش «نمای فنی» پس از دریافت داده.

        کلیدها آزادند؛ هرچه بیاید نمایش داده می‌شود. عنوان هر ردیف از
        فایل ترجمه خوانده می‌شود و اگر کلید ترجمه نبود، خود کلید نمایش
        داده می‌شود تا چیزی گم نشود.
        """
        self.details_hint.hide()
        while self._details_grid.count():
            item = self._details_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._detail_rows.clear()

        for index, (key, value) in enumerate(details.items()):
            caption = QLabel(self.tr_.tr(f"markets.detail_{key}", key))
            caption.setProperty("role", "muted")
            label = QLabel(str(value))
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._details_grid.addWidget(caption, index, 0)
            self._details_grid.addWidget(label, index, 1)
            self._detail_rows[key] = label

    def set_busy(self, busy: bool) -> None:
        """نمایش نوار پیشرفت هنگام دریافت داده."""
        self.busy.setVisible(bool(busy))
        self.analyze_button.setEnabled(not busy)
        self.signal_button.setEnabled(not busy)

    def set_status(self, text: str) -> None:
        """نمایش پیام وضعیت یا خطا."""
        self.status_label.setText(text or "")

    def set_details_error(self, text: str) -> None:
        """اگر دریافت جزئیات شکست خورد، پنجره خالی نماند."""
        self.details_hint.setText(text)
        self.details_hint.show()

    @property
    def symbol(self) -> str:
        """نماد این پنجره."""
        return self._symbol

    # ------------------------------------------------------------------
    # کمکی
    # ------------------------------------------------------------------
    def _toggle_watchlist(self) -> None:
        """افزودن یا برداشتن نماد از واچ‌لیست."""
        self._in_watchlist = not self._in_watchlist
        self.watchlist_button.setText(self._watchlist_text())
        self.watchlist_toggled.emit(self._symbol, self._in_watchlist)

    def _watchlist_text(self) -> str:
        """متن دکمهٔ واچ‌لیست بر اساس وضعیت فعلی."""
        key = "markets.remove_watchlist" if self._in_watchlist else "markets.add_watchlist"
        return self.tr_.tr(key)

    def _apply_change(self, change: float) -> None:
        """رنگ و علامت درصد تغییر."""
        sign = "+" if change > 0 else ""
        text = f"{sign}{change:.2f}%"
        self.change_label.setText(self.tr_.to_persian_digits(text))
        role = "up" if change > 0 else "down" if change < 0 else "muted"
        self.change_label.setProperty("role", role)
        self.change_label.style().unpolish(self.change_label)
        self.change_label.style().polish(self.change_label)

    def _format_number(self, value: Any) -> str:
        """قالب‌بندی عدد با رقم‌های مناسب و ارقام فارسی در حالت RTL."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if number >= 1000:
            text = f"{number:,.2f}"
        elif number >= 1:
            text = f"{number:,.4f}"
        else:
            text = f"{number:.8f}".rstrip("0").rstrip(".")
        return self.tr_.to_persian_digits(text)

    def retranslate(self) -> None:
        """به‌روزرسانی متن‌ها پس از تغییر زبان."""
        self.setWindowTitle(self.tr_.tr("markets.detail_title", symbol=self._symbol))
        self.analyze_button.setText(self.tr_.tr("markets.action_analyze"))
        self.signal_button.setText(self.tr_.tr("markets.action_signal"))
        self.chat_button.setText(self.tr_.tr("markets.action_chat"))
        self.market_button.setText(self.tr_.tr("markets.action_open_market"))
        self.watchlist_button.setText(self._watchlist_text())
        self.close_button.setText(self.tr_.tr("common.close"))
