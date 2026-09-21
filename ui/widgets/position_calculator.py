"""
ماشین‌حساب حجم پوزیشن.

آموزش برنامه می‌گوید «حجم را از حد ضرر حساب کن»، ولی تا امروز کاربر باید
این کار را با ماشین‌حساب جداگانه انجام می‌داد. این ویجت همان فرمول را در
خود برنامه می‌آورد و — مهم‌تر — می‌تواند اعداد یک سیگنال را از پیش پر
کند تا کاربر فقط سرمایه‌اش را ببیند و تصمیم بگیرد.

هر تغییر ورودی بی‌درنگ محاسبه می‌شود؛ دکمهٔ «محاسبه» عمداً وجود ندارد،
چون یک کلیک اضافه بین کاربر و جوابی است که همین حالا می‌خواهد.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from signals.position_sizing import (
    DEFAULT_FEE_PERCENT,
    MAX_LEVERAGE,
    PositionPlan,
    calculate_position,
    required_win_rate,
)
from ui.widgets.controls import set_role

#: بیشترین رقم اعشار برای قیمت — ارزهای ارزان به دقت بالا نیاز دارند
PRICE_DECIMALS = 8

#: سطرهای جدول نتیجه، به همان ترتیبی که نمایش داده می‌شوند
RESULT_ROWS = (
    "quantity",
    "notional",
    "margin",
    "risk_amount",
    "liquidation",
    "reward",
    "risk_reward",
    "win_rate",
    "fee",
)


class PriceSpinBox(QDoubleSpinBox):
    """
    ورودی قیمت با دقت بالا اما نمایش تمیز.

    دقت هشت رقم برای ارزهای ارزان (مثل شیبااینو) لازم است، ولی نمایش
    «۶۰٬۰۰۰٫۰۰۰۰۰۰۰۰» برای بیت‌کوین فقط چشم را خسته می‌کند؛ پس مقدار با
    تمام دقت نگه داشته می‌شود و تنها صفرهای انتهایی از متن حذف می‌شوند.
    """

    def textFromValue(self, value: float) -> str:  # noqa: N802 - نام Qt
        text = super().textFromValue(value)
        if "." not in text:
            return text
        return text.rstrip("0").rstrip(".") or "0"


class PositionCalculator(QWidget):
    """
    ماشین‌حساب حجم، مارجین و فاصلهٔ لیکوییدیشن.

    نمونه‌سازی:
        calc = PositionCalculator(translator)
        calc.load_signal(signal_dict)
        calc.set_capital(1000)
    """

    #: هر بار که محاسبه به‌روز شد
    plan_changed = Signal(object)

    def __init__(self, translator: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._plan: PositionPlan | None = None
        self._updating = False
        self._result_rows: dict[str, tuple[QLabel, QLabel]] = {}
        self._form_labels: list[tuple[QLabel, str]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        root.addWidget(self._build_inputs())
        root.addWidget(self._build_results())

        self.warning_label = QLabel("", self)
        self.warning_label.setWordWrap(True)
        set_role(self.warning_label, "warning")
        self.warning_label.setVisible(False)
        root.addWidget(self.warning_label)

        self.retranslate()
        self.recalculate()

    # ------------------------------------------------------------- ساخت UI
    def _build_inputs(self) -> QWidget:
        """فرم ورودی‌ها."""
        frame = QFrame(self)
        frame.setProperty("role", "card")
        form = QFormLayout(frame)
        form.setContentsMargins(14, 12, 14, 12)
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.capital_input = self._money_input(maximum=1e12, value=1000.0)
        self.risk_input = self._percent_input(value=1.0, maximum=100.0, step=0.25)
        self.entry_input = self._money_input(maximum=1e12, value=0.0, decimals=PRICE_DECIMALS)
        self.stop_input = self._money_input(maximum=1e12, value=0.0, decimals=PRICE_DECIMALS)
        self.target_input = self._money_input(maximum=1e12, value=0.0, decimals=PRICE_DECIMALS)

        self.leverage_input = QSpinBox(frame)
        self.leverage_input.setRange(1, MAX_LEVERAGE)
        self.leverage_input.setValue(1)
        self.leverage_input.setPrefix("× ")
        self.leverage_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.fee_input = self._percent_input(value=DEFAULT_FEE_PERCENT, maximum=5.0, step=0.01)
        self.fee_input.setDecimals(3)

        for key, widget in (
            ("sizing.capital", self.capital_input),
            ("sizing.risk_percent", self.risk_input),
            ("sizing.entry", self.entry_input),
            ("sizing.stop_loss", self.stop_input),
            ("sizing.take_profit", self.target_input),
            ("sizing.leverage", self.leverage_input),
            ("sizing.fee_percent", self.fee_input),
        ):
            label = QLabel("", frame)
            self._form_labels.append((label, key))
            form.addRow(label, widget)
            widget.valueChanged.connect(self.recalculate)

        return frame

    def _money_input(
        self, *, maximum: float, value: float, decimals: int = 2
    ) -> QDoubleSpinBox:
        """ورودی عددی پول با مقدار وسط‌چین."""
        box = PriceSpinBox(self) if decimals > 2 else QDoubleSpinBox(self)
        box.setRange(0.0, maximum)
        box.setDecimals(decimals)
        box.setValue(value)
        box.setGroupSeparatorShown(True)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # گام ثابت برای قیمت بی‌معناست (بیت‌کوین و شیبااینو یک گام
        # ندارند)؛ کاربر عدد را تایپ می‌کند.
        box.setSingleStep(1.0 if decimals <= 2 else 0.0)
        return box

    def _percent_input(self, *, value: float, maximum: float, step: float) -> QDoubleSpinBox:
        """ورودی درصد."""
        box = QDoubleSpinBox(self)
        box.setRange(0.0, maximum)
        box.setDecimals(2)
        box.setValue(value)
        box.setSingleStep(step)
        box.setSuffix(" %")
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return box

    def _build_results(self) -> QWidget:
        """جدول نتیجه."""
        frame = QFrame(self)
        frame.setProperty("role", "card")
        grid = QGridLayout(frame)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(7)

        self.result_title = QLabel("", frame)
        set_role(self.result_title, "subtitle")
        grid.addWidget(self.result_title, 0, 0, 1, 2)

        for offset, name in enumerate(RESULT_ROWS, start=1):
            key_label = QLabel("", frame)
            set_role(key_label, "muted")
            value_label = QLabel("—", frame)
            font = value_label.font()
            font.setBold(True)
            value_label.setFont(font)
            # اعداد همیشه لاتین‌اند و در چیدمان راست‌به‌چپ نباید وارونه شوند
            value_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            grid.addWidget(key_label, offset, 0)
            grid.addWidget(value_label, offset, 1)
            self._result_rows[name] = (key_label, value_label)

        grid.setColumnStretch(1, 1)
        return frame

    # ------------------------------------------------------------------ API
    @property
    def plan(self) -> PositionPlan | None:
        """آخرین محاسبه."""
        return self._plan

    def set_capital(self, amount: float) -> None:
        """تعیین سرمایه (معمولاً از موجودی کیف پول)."""
        self._set_silently(self.capital_input, float(amount or 0))
        self.recalculate()

    def set_risk_percent(self, percent: float) -> None:
        """تعیین درصد ریسک از تنظیمات کاربر."""
        self._set_silently(self.risk_input, float(percent or 0))
        self.recalculate()

    def load_signal(self, signal: dict[str, Any]) -> None:
        """
        پر کردن ورودی‌ها از یک سیگنال.

        سرمایه و درصد ریسک دست‌نخورده می‌مانند: آن‌ها به کاربر تعلق دارند
        نه به سیگنال، و بازنویسی‌شان یعنی کاربر باید هر بار دوباره
        واردشان کند.
        """
        data = dict(signal or {})
        entry = _first_number(data.get("entry_price"), data.get("entry"))
        stop = _first_number(data.get("stop_loss"))

        targets = data.get("take_profits") or data.get("take_profit") or []
        if isinstance(targets, (int, float)):
            targets = [targets]
        target = _first_number(*(list(targets)[:1] or [0]))

        self._updating = True
        try:
            self.entry_input.setValue(entry)
            self.stop_input.setValue(stop)
            self.target_input.setValue(target)
            leverage = data.get("leverage")
            if leverage:
                self.leverage_input.setValue(max(1, min(MAX_LEVERAGE, int(leverage))))
        finally:
            self._updating = False
        self.recalculate()

    def recalculate(self) -> None:
        """محاسبهٔ دوباره و به‌روزرسانی نمایش."""
        if self._updating:
            return

        plan = calculate_position(
            capital=self.capital_input.value(),
            risk_percent=self.risk_input.value(),
            entry=self.entry_input.value(),
            stop_loss=self.stop_input.value(),
            leverage=self.leverage_input.value(),
            take_profit=self.target_input.value(),
            fee_percent=self.fee_input.value(),
        )
        self._plan = plan
        self._render(plan)
        self.plan_changed.emit(plan)

    def result_value(self, name: str) -> str:
        """متن نمایش‌دادهٔ یک سطر نتیجه (برای آزمون و صفحهٔ میزبان)."""
        row = self._result_rows.get(name)
        return row[1].text() if row else ""

    def retranslate(self, translator: Any | None = None) -> None:
        """
        بازسازی برچسب‌ها.

        مترجم تازه اختیاری است تا تعویض زبانِ برنامه بدون ساخت دوبارهٔ
        ویجت ممکن باشد.
        """
        if translator is not None:
            self.tr_ = translator
        for label, key in self._form_labels:
            label.setText(self.tr_.tr(key))
        self.result_title.setText(self.tr_.tr("sizing.result_title"))
        for name, (key_label, _value) in self._result_rows.items():
            key_label.setText(self.tr_.tr(f"sizing.row_{name}"))
        if self._plan is not None:
            self._render(self._plan)

    # -------------------------------------------------------------- درونی
    def _set_silently(self, widget: QDoubleSpinBox, value: float) -> None:
        """تغییر مقدار بدون راه‌انداختن محاسبهٔ زنجیره‌ای."""
        self._updating = True
        try:
            widget.setValue(value)
        finally:
            self._updating = False

    def _render(self, plan: PositionPlan) -> None:
        """نشاندن نتیجه روی برچسب‌ها."""
        if not plan.valid:
            for _key, value in self._result_rows.values():
                value.setText("—")
            self.warning_label.setText(self.tr_.tr(plan.error_key))
            self.warning_label.setVisible(True)
            return

        number = self._number
        self._result_rows["quantity"][1].setText(_trim(plan.quantity))
        self._result_rows["notional"][1].setText(number(plan.notional))
        self._result_rows["margin"][1].setText(number(plan.margin))
        self._result_rows["risk_amount"][1].setText(
            f"{number(plan.risk_amount)}  ({number(plan.stop_distance_percent)}%)"
        )

        if plan.liquidation_price > 0:
            self._result_rows["liquidation"][1].setText(
                f"{_trim(plan.liquidation_price)}  "
                f"({number(plan.liquidation_distance_percent)}%)"
            )
        else:
            self._result_rows["liquidation"][1].setText("—")

        if plan.reward_amount > 0:
            self._result_rows["reward"][1].setText(number(plan.reward_amount))
            self._result_rows["risk_reward"][1].setText(number(plan.risk_reward))
            self._result_rows["win_rate"][1].setText(
                f"{number(required_win_rate(plan.risk_reward))}%"
            )
        else:
            for name in ("reward", "risk_reward", "win_rate"):
                self._result_rows[name][1].setText("—")

        self._result_rows["fee"][1].setText(number(plan.fee_amount))

        if plan.warnings:
            lines = [f"• {self.tr_.tr(key)}" for key in plan.warnings]
            self.warning_label.setText("\n".join(lines))
            self.warning_label.setVisible(True)
        else:
            self.warning_label.setVisible(False)

    def _number(self, value: float) -> str:
        """قالب‌بندی عدد با ارقام زبان جاری."""
        formatter = getattr(self.tr_, "format_number", None)
        if callable(formatter):
            return str(formatter(value, 2))
        return f"{value:,.2f}"


def _trim(value: float) -> str:
    """
    نمایش عدد بدون صفرهای بی‌فایدهٔ انتهایی.

    مقدار ۰٫۰۰۸۳۳۳۳۳ باید خوانا بماند ولی ۵۰۰٫۰۰۰۰۰۰۰۰ مسخره است.
    ارقام لاتین می‌مانند چون این عدد را کاربر در صرافی کپی می‌کند.
    """
    if value == 0:
        return "0"
    text = f"{value:,.8f}".rstrip("0").rstrip(".")
    return text or "0"


def _first_number(*values: Any) -> float:
    """نخستین مقدار عددی معتبر میان ورودی‌ها."""
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return 0.0


__all__ = ["PRICE_DECIMALS", "PositionCalculator"]
