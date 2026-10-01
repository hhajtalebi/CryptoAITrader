"""
پنجرهٔ «باز کردن معامله» — معاملهٔ دستی (نسخهٔ ۲.۵.۹).

خواستهٔ کاربر:
    نماد را خودم انتخاب کنم، مقداری از دارایی‌ام را بگذارم، نوع معامله
    (اسپات/فیوچرز) و اهرم (۱ تا ۱۰۰) را انتخاب کنم، حد سود و حد ضرر بدهم و
    معامله را باز کنم. از روی سیگنال (مقادیر پر شده، قابل تغییر یا تأیید) و
    از صفحهٔ تاریخچهٔ معاملات با دکمهٔ «باز کردن معامله».

این پنجره فقط «نمایش و انتخاب» است: محاسبه در `trading.manual_order` و ثبت
معامله در کنترلر انجام می‌شود (کاغذی؛ دروازهٔ اجرای واقعی دور زده نمی‌شود).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QCompleter,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from trading.manual_order import (
    AMOUNT_PRESETS,
    DEFAULT_FEE_RATE,
    MARKET_FUTURES,
    MARKET_SPOT,
    MAX_MANUAL_LEVERAGE,
    ManualOrderPlan,
    ManualOrderRequest,
    normalize_symbol,
    percent_from_price,
    plan_manual_order,
    price_from_percent,
)
from ui.widgets import make_button, set_role
from ui.widgets.position_calculator import PRICE_DECIMALS, PriceSpinBox

#: سطرهای خلاصه به ترتیب نمایش
SUMMARY_ROWS = ("quantity", "notional", "margin", "fees", "profit_at_tp", "loss_at_sl",
                "risk_reward", "liquidation")


class ManualTradeDialog(QDialog):
    """
    فرم کامل معاملهٔ دستی.

    نمونه:
        dialog = ManualTradeDialog(tr, symbols=[...], available=1000.0)
        dialog.prefill({"symbol": "BTC/USDT", "direction": "LONG", ...})
        dialog.order_requested.connect(handler)   # dict از ManualOrderPlan
        dialog.price_requested.connect(fetch)     # نماد؛ پاسخ با set_price
    """

    order_requested = Signal(dict)
    price_requested = Signal(str)

    def __init__(
        self,
        translator: Any,
        *,
        symbols: list[str] | None = None,
        available: float = 0.0,
        fee_rate: float = DEFAULT_FEE_RATE,
        source: str = "manual",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._available = max(0.0, float(available or 0.0))
        self._fee_rate = float(fee_rate or 0.0)
        self._source = source
        self._signal_id: Any = None
        self._syncing = False
        self._summary: dict[str, QLabel] = {}
        self.setObjectName("manualTradeDialog")
        self.setWindowTitle(self._t("title", "Open trade"))
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        notice = QLabel(self._t("paper_notice", "Paper trade with live prices — no real order is sent."), self)
        set_role(notice, "chip_info")
        notice.setWordWrap(True)
        root.addWidget(notice)

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)
        body_layout.addWidget(self._build_form(body))
        body_layout.addWidget(self._build_summary(body))
        self.message_label = QLabel("", body)
        self.message_label.setWordWrap(True)
        set_role(self.message_label, "warning")
        body_layout.addWidget(self.message_label)
        body_layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = QPushButton(self.tr_.tr("common.cancel"), self)
        self.cancel_button.clicked.connect(self.reject)
        actions.addWidget(self.cancel_button)
        self.open_button = make_button(self._t("open", "Open trade"), primary=True)
        self.open_button.setObjectName("manualTradeOpen")
        self.open_button.clicked.connect(self._on_open)
        actions.addWidget(self.open_button)
        root.addLayout(actions)

        self.set_symbols(symbols or [])
        self.set_available(self._available)
        self.recalculate()

    # ------------------------------------------------------------- ساخت
    def _t(self, key: str, default: str = "", **values: Any) -> str:
        """ترجمهٔ کلیدهای `trades.manual.*` با پیش‌فرض انگلیسی."""
        full = f"trades.manual.{key}"
        text = self.tr_.tr(full, **values) if values else self.tr_.tr(full)
        if not text or text == full:
            return default.format(**values) if values else default
        return text

    def _price_box(self, parent: QWidget) -> QDoubleSpinBox:
        box = PriceSpinBox(parent)
        box.setRange(0.0, 1e12)
        box.setDecimals(PRICE_DECIMALS)
        box.setSingleStep(0.0)
        box.setGroupSeparatorShown(True)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return box

    def _percent_box(self, parent: QWidget) -> QDoubleSpinBox:
        box = QDoubleSpinBox(parent)
        box.setRange(0.0, 1000.0)
        box.setDecimals(2)
        box.setSingleStep(0.5)
        box.setSuffix(" %")
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return box

    def _build_form(self, parent: QWidget) -> QWidget:
        frame = QFrame(parent)
        frame.setProperty("role", "card")
        form = QFormLayout(frame)
        form.setContentsMargins(14, 12, 14, 12)
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        # نماد: قابل تایپ + فهرست نمادهای بازار
        self.symbol_combo = QComboBox(frame)
        self.symbol_combo.setEditable(True)
        self.symbol_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.symbol_combo.setObjectName("manualSymbol")
        self.symbol_combo.lineEdit().setPlaceholderText("BTC/USDT")
        self.symbol_combo.currentTextChanged.connect(self.recalculate)
        self.symbol_combo.activated.connect(lambda _i: self.request_price())
        self.symbol_combo.lineEdit().editingFinished.connect(self.request_price)
        form.addRow(self._t("symbol", "Symbol"), self.symbol_combo)

        # نوع معامله
        self.market_combo = QComboBox(frame)
        self.market_combo.addItem(self._t("futures", "Futures"), MARKET_FUTURES)
        self.market_combo.addItem(self._t("spot", "Spot"), MARKET_SPOT)
        self.market_combo.currentIndexChanged.connect(self._on_market_changed)
        form.addRow(self._t("market_type", "Trade type"), self.market_combo)

        # جهت
        side_row = QHBoxLayout()
        self.long_button = make_button(self._t("long", "Long / Buy"), checkable=True)
        self.short_button = make_button(self._t("short", "Short / Sell"), checkable=True)
        self.long_button.setObjectName("manualLong")
        self.short_button.setObjectName("manualShort")
        self.side_group = QButtonGroup(self)
        self.side_group.setExclusive(True)
        self.side_group.addButton(self.long_button)
        self.side_group.addButton(self.short_button)
        self.long_button.setChecked(True)
        self.side_group.buttonToggled.connect(lambda *_a: self._on_side_changed())
        side_row.addWidget(self.long_button)
        side_row.addWidget(self.short_button)
        form.addRow(self._t("direction", "Direction"), side_row)

        # مبلغ از موجودی
        self.available_label = QLabel("", frame)
        set_role(self.available_label, "faint")
        form.addRow(self._t("available", "Available"), self.available_label)
        amount_row = QVBoxLayout()
        self.amount_input = QDoubleSpinBox(frame)
        self.amount_input.setRange(0.0, 1e12)
        self.amount_input.setDecimals(2)
        self.amount_input.setSingleStep(10.0)
        self.amount_input.setGroupSeparatorShown(True)
        self.amount_input.setSuffix(" USDT")
        self.amount_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.amount_input.valueChanged.connect(self.recalculate)
        amount_row.addWidget(self.amount_input)
        presets = QHBoxLayout()
        self.amount_preset_buttons: dict[int, QPushButton] = {}
        for percent in AMOUNT_PRESETS:
            button = QPushButton(f"{percent}%", frame)
            button.setProperty("role", "chip")
            button.clicked.connect(lambda _c=False, p=percent: self.apply_amount_percent(p))
            presets.addWidget(button)
            self.amount_preset_buttons[percent] = button
        amount_row.addLayout(presets)
        form.addRow(self._t("amount", "Amount (margin)"), amount_row)

        # اهرم ۱ تا ۱۰۰
        leverage_row = QHBoxLayout()
        self.leverage_slider = QSlider(Qt.Orientation.Horizontal, frame)
        self.leverage_slider.setRange(1, MAX_MANUAL_LEVERAGE)
        self.leverage_input = QSpinBox(frame)
        self.leverage_input.setRange(1, MAX_MANUAL_LEVERAGE)
        self.leverage_input.setPrefix("× ")
        self.leverage_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.leverage_slider.valueChanged.connect(self.leverage_input.setValue)
        self.leverage_input.valueChanged.connect(self.leverage_slider.setValue)
        self.leverage_input.valueChanged.connect(self.recalculate)
        leverage_row.addWidget(self.leverage_slider, 1)
        leverage_row.addWidget(self.leverage_input)
        form.addRow(self._t("leverage", "Leverage"), leverage_row)

        # قیمت ورود + قیمت لحظه‌ای
        entry_row = QHBoxLayout()
        self.entry_input = self._price_box(frame)
        self.entry_input.valueChanged.connect(self._on_entry_changed)
        self.price_button = QPushButton(self._t("live_price", "Live price"), frame)
        self.price_button.clicked.connect(self.request_price)
        entry_row.addWidget(self.entry_input, 1)
        entry_row.addWidget(self.price_button)
        form.addRow(self._t("entry", "Entry price"), entry_row)
        self.entry_hint = QLabel(
            self._t("entry_hint", "When opening, the live price replaces this if it is fresh."), frame
        )
        set_role(self.entry_hint, "faint")
        self.entry_hint.setWordWrap(True)
        form.addRow("", self.entry_hint)

        # حد سود و حد ضرر: قیمت ⇄ درصد
        self.tp_input = self._price_box(frame)
        self.tp_percent = self._percent_box(frame)
        self.sl_input = self._price_box(frame)
        self.sl_percent = self._percent_box(frame)
        for price_box, percent_box, kind, key, default in (
            (self.tp_input, self.tp_percent, "tp", "take_profit", "Take profit"),
            (self.sl_input, self.sl_percent, "sl", "stop_loss", "Stop loss"),
        ):
            row = QHBoxLayout()
            row.addWidget(price_box, 2)
            row.addWidget(percent_box, 1)
            price_box.valueChanged.connect(lambda _v, k=kind: self._on_level_price(k))
            percent_box.valueChanged.connect(lambda _v, k=kind: self._on_level_percent(k))
            form.addRow(self._t(key, default), row)
        return frame

    def _build_summary(self, parent: QWidget) -> QWidget:
        frame = QFrame(parent)
        frame.setProperty("role", "card")
        grid = QGridLayout(frame)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        title = QLabel(self._t("summary", "Summary"), frame)
        set_role(title, "subtitle")
        grid.addWidget(title, 0, 0, 1, 4)
        defaults = {
            "quantity": "Quantity", "notional": "Position size", "margin": "Margin",
            "fees": "Fees (round trip)", "profit_at_tp": "Profit at TP", "loss_at_sl": "Loss at SL",
            "risk_reward": "Reward / risk", "liquidation": "Liquidation (est.)",
        }
        for index, name in enumerate(SUMMARY_ROWS):
            caption = QLabel(self._t(f"row_{name}", defaults[name]), frame)
            set_role(caption, "muted")
            value = QLabel("—", frame)
            value.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            font = value.font()
            font.setBold(True)
            value.setFont(font)
            row, col = 1 + index // 2, (index % 2) * 2
            grid.addWidget(caption, row, col)
            grid.addWidget(value, row, col + 1)
            self._summary[name] = value
        return frame

    # ------------------------------------------------------------- API
    def set_symbols(self, symbols: list[str]) -> None:
        """فهرست نمادهای قابل انتخاب (متن فعلی حفظ می‌شود)."""
        current = self.symbol_combo.currentText()
        unique = sorted({normalize_symbol(s) for s in symbols if s})
        self.symbol_combo.blockSignals(True)
        self.symbol_combo.clear()
        self.symbol_combo.addItems(unique)
        self.symbol_combo.setEditText(current)
        self.symbol_combo.blockSignals(False)
        completer = QCompleter(unique, self.symbol_combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.symbol_combo.setCompleter(completer)

    def set_available(self, amount: float) -> None:
        """موجودی آزاد (سقف مبلغ)."""
        self._available = max(0.0, float(amount or 0.0))
        self.available_label.setText(
            f"{self._available:,.2f} USDT" if self._available > 0 else self._t("available_unknown", "unknown")
        )
        for button in self.amount_preset_buttons.values():
            button.setEnabled(self._available > 0)
        self.recalculate()

    def apply_amount_percent(self, percent: float) -> None:
        """مبلغ = درصدی از موجودی آزاد."""
        if self._available > 0:
            self.amount_input.setValue(round(self._available * float(percent) / 100.0, 2))

    def symbol(self) -> str:
        return normalize_symbol(self.symbol_combo.currentText())

    def direction(self) -> str:
        return "SHORT" if self.short_button.isChecked() else "LONG"

    def market_type(self) -> str:
        return str(self.market_combo.currentData() or MARKET_FUTURES)

    def request_price(self) -> None:
        """درخواست قیمت لحظه‌ای نماد از کنترلر (پاسخ با `set_price`)."""
        symbol = self.symbol()
        if symbol:
            self.price_requested.emit(symbol)

    def set_price(self, symbol: str, price: float) -> None:
        """قیمت لحظه‌ای رسید: فقط اگر هنوز همان نماد انتخاب شده باشد."""
        if price and price > 0 and normalize_symbol(symbol) == self.symbol():
            self.entry_input.setValue(float(price))

    def prefill(self, values: dict[str, Any]) -> None:
        """پر کردن فرم (مثلاً از سیگنال). کاربر می‌تواند همه را تغییر دهد."""
        data = dict(values or {})
        self._syncing = True
        try:
            if data.get("symbol"):
                self.symbol_combo.setEditText(normalize_symbol(data["symbol"]))
            index = self.market_combo.findData(str(data.get("market_type") or MARKET_FUTURES))
            if index >= 0:
                self.market_combo.setCurrentIndex(index)
            if str(data.get("direction") or "LONG").upper() == "SHORT":
                self.short_button.setChecked(True)
            else:
                self.long_button.setChecked(True)
            if data.get("leverage"):
                self.leverage_input.setValue(int(data["leverage"]))
            if data.get("amount"):
                self.amount_input.setValue(float(data["amount"]))
            self.entry_input.setValue(float(data.get("entry") or 0.0))
            self.tp_input.setValue(float(data.get("take_profit") or 0.0))
            self.sl_input.setValue(float(data.get("stop_loss") or 0.0))
            self._signal_id = data.get("signal_id")
            if data.get("source"):
                self._source = str(data["source"])
        finally:
            self._syncing = False
        self._refresh_percents()
        self._on_market_changed()

    def build_request(self) -> ManualOrderRequest:
        return ManualOrderRequest(
            symbol=self.symbol(),
            market_type=self.market_type(),
            direction=self.direction(),
            amount=float(self.amount_input.value()),
            leverage=int(self.leverage_input.value()),
            entry=float(self.entry_input.value()),
            take_profit=float(self.tp_input.value()),
            stop_loss=float(self.sl_input.value()),
            available=self._available,
            fee_rate=self._fee_rate,
        )

    def plan(self) -> ManualOrderPlan:
        return plan_manual_order(self.build_request())

    def payload(self) -> dict[str, Any]:
        """آنچه به کنترلر فرستاده می‌شود."""
        data = self.plan().to_dict()
        data["source"] = self._source
        data["signal_id"] = self._signal_id
        data["available"] = self._available
        return data

    def show_error(self, text: str) -> None:
        """پیام ردِ کنترلر (مثلاً قیمت زنده از حد ضرر گذشته است)."""
        set_role(self.message_label, "danger")
        self.message_label.setText(text)
        self.message_label.setVisible(bool(text))

    # ------------------------------------------------------------- رفتار
    def _on_market_changed(self, *_args: Any) -> None:
        spot = self.market_type() == MARKET_SPOT
        if spot:
            self.leverage_input.setValue(1)
            if self.short_button.isChecked():
                self.long_button.setChecked(True)
        self.leverage_input.setEnabled(not spot)
        self.leverage_slider.setEnabled(not spot)
        self.short_button.setEnabled(not spot)
        self.recalculate()

    def _on_side_changed(self) -> None:
        self._refresh_percents()
        self.recalculate()

    def _on_entry_changed(self, *_args: Any) -> None:
        self._refresh_percents()
        self.recalculate()

    def _on_level_price(self, kind: str) -> None:
        if self._syncing:
            return
        self._refresh_percents()
        self.recalculate()

    def _on_level_percent(self, kind: str) -> None:
        if self._syncing:
            return
        entry = float(self.entry_input.value())
        percent_box = self.tp_percent if kind == "tp" else self.sl_percent
        price_box = self.tp_input if kind == "tp" else self.sl_input
        price = price_from_percent(entry, float(percent_box.value()), self.direction(), kind)
        self._syncing = True
        try:
            price_box.setValue(price)
        finally:
            self._syncing = False
        self.recalculate()

    def _refresh_percents(self) -> None:
        entry = float(self.entry_input.value())
        self._syncing = True
        try:
            self.tp_percent.setValue(percent_from_price(entry, float(self.tp_input.value())))
            self.sl_percent.setValue(percent_from_price(entry, float(self.sl_input.value())))
        finally:
            self._syncing = False

    def recalculate(self, *_args: Any) -> None:
        """محاسبهٔ دوباره و نمایش خلاصه، خطا و هشدار."""
        if self._syncing or not hasattr(self, "open_button"):
            return
        plan = self.plan()

        def money(value: float, signed: bool = False) -> str:
            if not value:
                return "—"
            return f"{value:+,.2f} USDT" if signed else f"{value:,.2f} USDT"

        def price(value: float) -> str:
            if not value:
                return "—"
            return f"{value:,.8f}".rstrip("0").rstrip(".")

        base = plan.symbol.split("/")[0] if plan.symbol else ""
        values = {
            "quantity": f"{plan.quantity:,.6f}".rstrip("0").rstrip(".") + (f" {base}" if base else "")
            if plan.quantity else "—",
            "notional": money(plan.notional),
            "margin": money(plan.amount),
            "fees": money(plan.fees),
            "profit_at_tp": money(plan.profit_at_tp, signed=True) if plan.take_profit else "—",
            "loss_at_sl": money(plan.loss_at_sl, signed=True) if plan.stop_loss else "—",
            "risk_reward": f"{plan.risk_reward:.2f}" if plan.risk_reward else "—",
            "liquidation": price(plan.liquidation),
        }
        for name, label in self._summary.items():
            label.setText(values.get(name, "—"))

        messages = [self._t(f"error_{key}", key) for key in plan.errors]
        messages += [self._t(f"warn_{key}", key) for key in plan.warnings]
        set_role(self.message_label, "danger" if plan.errors else "warning")
        self.message_label.setText("\n".join(f"• {m}" for m in messages))
        self.message_label.setVisible(bool(messages))
        self.open_button.setEnabled(plan.valid)

    def _on_open(self) -> None:
        plan = self.plan()
        if not plan.valid:
            self.recalculate()
            return
        self.order_requested.emit(self.payload())

    def trade_opened(self) -> None:
        """کنترلر پس از ثبت موفق صدا می‌زند."""
        self.accept()


__all__ = ["ManualTradeDialog", "SUMMARY_ROWS"]
