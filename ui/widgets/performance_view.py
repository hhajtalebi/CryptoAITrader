"""
نمای عملکرد واقعی سیگنال‌ها.

این بخش به سؤالی پاسخ می‌دهد که تا امروز بی‌پاسخ بود: «سیگنال‌هایی که
این برنامه داد، چقدرش درست از آب درآمد؟»

سه لایه اطلاعات دارد:

    ۱. **کارت‌های کلیدی** — نرخ برد، مجموع R، ضریب سود، تعداد باز.
    ۲. **تفکیک** — همان آمار به تفکیک بازهٔ اطمینان، نماد، تایم‌فریم و
       جهت. مهم‌ترینش «بازهٔ اطمینان» است: اگر نرخ برد با بالا رفتن
       ضریب اطمینان زیاد **نشود**، یعنی ضریب اطمینان ادعایی توخالی است.
    ۳. **سابقه** — تک‌تک سیگنال‌ها با نتیجهٔ واقعی‌شان.

نکتهٔ طراحی: هیچ عددی اینجا آرایش نمی‌شود. سیگنال بازنده با رنگ قرمز و
درصد منفی نشان داده می‌شود، حتی اگر خوشایند نباشد. ابزاری که آمار خودش
را زیبا کند بی‌ارزش است.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from localization import Translator
from ui.widgets.common import Card, configure_table, make_button
from ui.widgets.controls import SegmentedControl, StatCard, set_role

#: بازه‌های زمانی گزارش: (کلید، روز)
PERIODS: tuple[tuple[str, int], ...] = (
    ("7", 7),
    ("30", 30),
    ("90", 90),
    ("all", 0),
)

#: شیوه‌های تفکیک: (کلید گزینه، کلید داده در گزارش)
BREAKDOWNS: tuple[tuple[str, str], ...] = (
    ("confidence", "by_confidence"),
    ("symbol", "by_symbol"),
    ("timeframe", "by_timeframe"),
    ("direction", "by_direction"),
)

#: کارت‌های آمار بالای صفحه
STAT_KEYS: tuple[str, ...] = ("win_rate", "total_r", "profit_factor", "pending")

#: نشانگر چپ‌به‌راست. هر عدد یا عبارت ترکیبیِ لاتین باید با این
#: پیشوند بیاید وگرنه بازچینش دوسویه آن را به‌هم می‌ریزد: «۲ / ۴»
#: وارونه خوانده می‌شد و علامت منفی به انتهای عدد می‌پرید.
LTR = "\u200e"

#: نام نشانهٔ رنگ هر وضعیت در `ColorTokens` — کد رنگ ثابت نمی‌نویسیم
#: تا با هر پوسته‌ای که کاربر برگزیده هماهنگ بماند.
STATUS_COLORS: dict[str, str] = {
    "TARGET": "success",
    "STOP": "danger",
    "PENDING": "info",
    "EXPIRED": "text_muted",
    "CANCELLED": "text_muted",
}


class PerformanceView(QWidget):
    """نمای آمار عملکرد واقعی سیگنال‌ها."""

    #: کاربر بازهٔ زمانی را عوض کرد (روز؛ صفر یعنی همهٔ تاریخچه)
    period_changed = Signal(int)
    #: کاربر بررسی دوبارهٔ قیمت‌ها را خواست
    refresh_requested = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._report: dict[str, Any] = {}
        self._rows: list[dict[str, Any]] = []
        self._theme: Any = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        root.addLayout(self._build_controls())
        root.addLayout(self._build_stats())
        root.addWidget(self._build_breakdown())
        root.addWidget(self._build_history(), 1)

        self._apply_headers()

    # ------------------------------------------------------------- ساخت

    def _build_controls(self) -> QHBoxLayout:
        """نوار بالا: بازهٔ زمانی و دکمهٔ بررسی دوباره."""
        row = QHBoxLayout()
        row.setSpacing(8)

        self.period_label = QLabel(self.tr_.tr("performance.period"))
        self.period_control = SegmentedControl(
            [(key, self._period_label(key)) for key, _ in PERIODS]
        )
        self.period_control.set_current("30", emit=False)
        self.period_control.selection_changed.connect(self._on_period)

        self.refresh_button = make_button(self.tr_.tr("performance.refresh"))
        self.refresh_button.clicked.connect(self.refresh_requested)

        self.status_label = QLabel("")
        set_role(self.status_label, "muted")

        row.addWidget(self.period_label)
        row.addWidget(self.period_control)
        row.addWidget(self.refresh_button)
        row.addWidget(self.status_label)
        row.addStretch(1)
        return row

    def _build_stats(self) -> QHBoxLayout:
        """کارت‌های آمار کلیدی."""
        row = QHBoxLayout()
        row.setSpacing(12)
        self._stat_cards: dict[str, StatCard] = {}
        for key in STAT_KEYS:
            card = StatCard(show_sparkline=False)
            card.set_data(title=self.tr_.tr(f"performance.{key}"), value="—")
            self._stat_cards[key] = card
            row.addWidget(card, 1)
        return row

    def _build_breakdown(self) -> QWidget:
        """کارت تفکیک آمار."""
        self.breakdown_card = Card(self.tr_.tr("performance.breakdown"))

        self.breakdown_control = SegmentedControl(
            [(key, self.tr_.tr(f"performance.group_{key}")) for key, _ in BREAKDOWNS]
        )
        self.breakdown_control.set_current("confidence", emit=False)
        self.breakdown_control.selection_changed.connect(
            lambda _key: self._fill_breakdown()
        )
        self.breakdown_card.add(self.breakdown_control)

        self.breakdown_hint = QLabel(self.tr_.tr("performance.confidence_hint"))
        set_role(self.breakdown_hint, "muted")
        self.breakdown_hint.setWordWrap(True)
        self.breakdown_card.add(self.breakdown_hint)

        self.breakdown_table = QTableWidget(0, 6)
        self.breakdown_table.verticalHeader().setVisible(False)
        self.breakdown_table.setAlternatingRowColors(True)
        self.breakdown_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.breakdown_card.add(self.breakdown_table)
        return self.breakdown_card

    def _build_history(self) -> QWidget:
        """کارت سابقهٔ تک‌تک سیگنال‌ها."""
        self.history_card = Card(self.tr_.tr("performance.history"))
        self.history_table = QTableWidget(0, 8)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_card.add(self.history_table)

        self.empty_label = QLabel(self.tr_.tr("performance.empty"))
        set_role(self.empty_label, "muted")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_card.add(self.empty_label)
        return self.history_card

    def _apply_headers(self) -> None:
        """سرستون‌های هر دو جدول."""
        self.breakdown_table.setHorizontalHeaderLabels(
            [
                self.tr_.tr("performance.group"),
                self.tr_.tr("performance.total"),
                self.tr_.tr("performance.win_rate"),
                self.tr_.tr("performance.wins_losses"),
                self.tr_.tr("performance.average_r"),
                self.tr_.tr("performance.total_percent"),
            ]
        )
        configure_table(self.breakdown_table, stretch_column=0)

        self.history_table.setHorizontalHeaderLabels(
            [
                self.tr_.tr("common.symbol"),
                self.tr_.tr("signals.direction"),
                self.tr_.tr("signals.confidence"),
                self.tr_.tr("performance.timeframe"),
                self.tr_.tr("performance.status"),
                self.tr_.tr("performance.result"),
                self.tr_.tr("performance.r_value"),
                self.tr_.tr("performance.targets"),
            ]
        )
        configure_table(self.history_table, stretch_column=0)

    # ------------------------------------------------------------- داده

    def selected_period(self) -> int:
        """بازهٔ انتخاب‌شده بر حسب روز (صفر یعنی همهٔ تاریخچه)."""
        current = self.period_control.current()
        for key, days in PERIODS:
            if key == current:
                return days
        return 30

    def set_performance(self, report: dict[str, Any]) -> None:
        """نمایش گزارش عملکرد."""
        self._report = dict(report or {})
        summary = self._report.get("summary") or {}

        decided = int(summary.get("decided", 0) or 0)
        win_rate = float(summary.get("win_rate", 0) or 0)
        # نرخ برد بدون تعداد، گمراه‌کننده است: «۱۰۰٪» از یک معامله
        # هیچ معنایی ندارد. تعداد همیشه کنارش می‌آید.
        self._stat_cards["win_rate"].set_data(
            value=self._ltr(f"{self.tr_.format_number(win_rate, 1)}%") if decided else "—",
            caption=self.tr_.tr(
                "performance.decided_count",
                count=self.tr_.format_number(decided, 0),
            ),
        )

        total_r = float(summary.get("total_r", 0) or 0)
        self._stat_cards["total_r"].set_data(
            value=self._ltr(f"{self.tr_.format_number(total_r, 2)}R") if decided else "—"
        )

        factor = summary.get("profit_factor", 0)
        self._stat_cards["profit_factor"].set_data(
            value=self._format_factor(factor) if decided else "—"
        )

        self._stat_cards["pending"].set_data(
            value=self.tr_.format_number(summary.get("pending", 0) or 0, 0)
        )

        self._fill_breakdown()

    def _format_factor(self, factor: Any) -> str:
        """
        ضریب سود، با مراقبت از بی‌نهایت.

        وقتی هیچ معاملهٔ بازنده‌ای نبوده، ریاضیات «بی‌نهایت» می‌دهد؛
        نمایش عدد عظیم یا `inf` به کاربر بی‌معناست.
        """
        try:
            value = float(factor)
        except (TypeError, ValueError):
            return "—"
        if value == float("inf"):
            return "∞"
        return self._ltr(self.tr_.format_number(value, 2))

    def _fill_breakdown(self) -> None:
        """پرکردن جدول تفکیک بر پایهٔ گزینهٔ انتخاب‌شده."""
        current = self.breakdown_control.current() or "confidence"
        data_key = dict(BREAKDOWNS).get(current, "by_confidence")
        buckets: dict[str, Any] = self._report.get(data_key) or {}

        self.breakdown_hint.setVisible(current == "confidence")

        rows = list(buckets.items())
        self.breakdown_table.setRowCount(len(rows))
        for index, (label, stats) in enumerate(rows):
            decided = int(stats.get("decided", 0) or 0)
            values = [
                self._breakdown_label(current, label),
                self.tr_.format_number(stats.get("total", 0) or 0, 0),
                (
                    self._ltr(f"{self.tr_.format_number(stats.get('win_rate', 0) or 0, 1)}%")
                    if decided
                    else "—"
                ),
                self._ltr(
                    f"{self.tr_.format_number(stats.get('wins', 0) or 0, 0)} / "
                    f"{self.tr_.format_number(stats.get('losses', 0) or 0, 0)}"
                ),
                (
                    self._ltr(f"{self.tr_.format_number(stats.get('average_r', 0) or 0, 2)}R")
                    if decided
                    else "—"
                ),
                self._ltr(
                    f"{self.tr_.format_number(stats.get('total_percent', 0) or 0, 2)}%"
                ),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 5:
                    self._colourise(item, float(stats.get("total_percent", 0) or 0))
                self.breakdown_table.setItem(index, column, item)

    @staticmethod
    def _ltr(text: str) -> str:
        """
        مهار بازچینش دوسویه روی متن لاتین.

        بدون این، «۲ / ۴» وارونه دیده می‌شد و «‎-۰.۳۱R» به «۰.۳۱R-»
        تبدیل می‌شد — یعنی کاربر برد را باخت می‌خواند.
        """
        return f"{LTR}{text}" if text and text != "—" else text

    def _breakdown_label(self, group: str, label: str) -> str:
        """
        برچسب خوانا برای هر ردیف تفکیک.

        جهت‌ها ترجمه می‌شوند ولی نماد و تایم‌فریم هرگز: `BTC/USDT` و
        `4h` کد فنی‌اند و ترجمه‌شان معنا را خراب می‌کند.
        """
        if group == "direction":
            return self.tr_.tr(f"signals.{label.lower()}", label)
        if group == "confidence":
            return self._ltr(f"{label}%")
        return self._ltr(label)

    def set_history(self, rows: list[dict[str, Any]]) -> None:
        """نمایش سابقهٔ نتیجه‌ها."""
        self._rows = [dict(row) for row in rows or []]
        self.empty_label.setVisible(not self._rows)
        self.history_table.setVisible(bool(self._rows))

        self.history_table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            direction = str(row.get("direction", "") or "")
            status = str(row.get("status", "") or "")
            result = float(row.get("result_percent", 0) or 0)
            targets = int(row.get("targets_hit", 0) or 0)

            values = [
                self._ltr(str(row.get("symbol", ""))),
                self.tr_.tr(f"signals.{direction.lower()}", direction),
                self._ltr(f"{self.tr_.format_number(row.get('confidence', 0) or 0, 0)}%"),
                self._ltr(str(row.get("timeframe", "") or "—")),
                self.tr_.tr(f"performance.status_{status.lower()}", status),
                self._ltr(f"{self.tr_.format_number(result, 2)}%"),
                self._ltr(
                    f"{self.tr_.format_number(row.get('realized_r', 0) or 0, 2)}R"
                ),
                self.tr_.format_number(targets, 0),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column in (5, 6):
                    self._colourise(item, result)
                elif column == 4:
                    self._colour_status(item, status)
                self.history_table.setItem(index, column, item)

    def _colourise(self, item: QTableWidgetItem, value: float) -> None:
        """
        رنگ سود و زیان.

        رنگ از پوستهٔ فعال خوانده می‌شود نه کد ثابت، تا سبز و قرمز با
        هر پوسته‌ای که کاربر انتخاب کرده هماهنگ بماند.
        """
        if self._theme is None or value == 0:
            return
        colors = self._theme.colors
        item.setForeground(QColor(colors.success if value > 0 else colors.danger))

    def _colour_status(self, item: QTableWidgetItem, status: str) -> None:
        """رنگ ستون وضعیت بر پایهٔ نتیجه."""
        if self._theme is None:
            return
        name = STATUS_COLORS.get(status.upper(), "text_muted")
        colors = self._theme.colors
        item.setForeground(QColor(getattr(colors, name, colors.text_muted)))

    def set_status(self, text: str) -> None:
        """پیام کوتاه کنار دکمهٔ بررسی."""
        self.status_label.setText(text)

    # -------------------------------------------------------- رویدادها

    def _on_period(self, key: str) -> None:
        """کاربر بازه را عوض کرد."""
        for option, days in PERIODS:
            if option == key:
                self.period_changed.emit(days)
                return

    def _period_label(self, key: str) -> str:
        """برچسب دکمهٔ بازه."""
        if key == "all":
            return self.tr_.tr("performance.period_all")
        return self.tr_.tr("performance.period_days", days=self.tr_.format_number(int(key), 0))

    def apply_theme(self, theme: Any) -> None:
        """
        اعمال پوسته روی کارت‌ها و رنگ‌های جدول.

        فقط شیء توکن پذیرفته می‌شود؛ اگر کلید رشته‌ای پوسته فرستاده شود
        نادیده گرفته می‌شود تا رنگ‌آمیزی جدول با `AttributeError` نشکند.
        """
        self._theme = theme if hasattr(theme, "colors") else None
        for card in self._stat_cards.values():
            card.apply_theme(theme)
        # جدول‌ها با رنگ پوستهٔ قبلی رنگ شده‌اند؛ باید دوباره ساخته شوند
        if self._rows:
            self.set_history(list(self._rows))
        if self._report:
            self._fill_breakdown()

    def retranslate(self) -> None:
        """بازسازی متن‌ها پس از تغییر زبان."""
        self.period_label.setText(self.tr_.tr("performance.period"))
        self.period_control.set_labels(
            {key: self._period_label(key) for key, _ in PERIODS}
        )
        self.breakdown_control.set_labels(
            {key: self.tr_.tr(f"performance.group_{key}") for key, _ in BREAKDOWNS}
        )
        self.refresh_button.setText(self.tr_.tr("performance.refresh"))
        self.breakdown_card.set_title(self.tr_.tr("performance.breakdown"))
        self.breakdown_hint.setText(self.tr_.tr("performance.confidence_hint"))
        self.history_card.set_title(self.tr_.tr("performance.history"))
        self.empty_label.setText(self.tr_.tr("performance.empty"))
        for key, card in self._stat_cards.items():
            card.set_data(title=self.tr_.tr(f"performance.{key}"))
        self._apply_headers()
        if self._report:
            self.set_performance(self._report)
        if self._rows:
            self.set_history(list(self._rows))


__all__ = [
    "BREAKDOWNS",
    "LTR",
    "PERIODS",
    "STAT_KEYS",
    "STATUS_COLORS",
    "PerformanceView",
]
