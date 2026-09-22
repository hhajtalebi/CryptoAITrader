"""
صفحه گزارش‌ها.

انتخاب بازه و قالب خروجی، پیش‌نمایش آمار، و صدور گزارش.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
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
    Card,
    DonutChart,
    KeyValueRow,
    PerformanceView,
    StatCard,
    configure_table,
    make_button,
    set_role,
)

#: کلید کارت‌های آمار بالای صفحه
STAT_KEYS: tuple[str, ...] = ("total_signals", "average_confidence", "long_share", "wait_share")

#: کلید ترجمهٔ زبانه‌ها
TAB_KEYS: tuple[str, str, str] = (
    "reports.tab_export",
    "performance.title",
    "scorecard.title",
)


class ReportsPage(BasePage):
    """صفحه تولید گزارش."""

    title_key = "nav.reports"
    subtitle_key = "reports.subtitle"

    #: کاربر خواست دفترچهٔ نتیجهٔ پیش‌بینی‌ها دوباره محاسبه شود
    scorecard_refresh_requested = Signal()
    scorecard_auto_changed = Signal(bool)

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._summary_rows: dict[str, KeyValueRow] = {}
        self._last_summary: dict[str, Any] = {}
        self._last_preview: list[dict[str, Any]] = []
        super().__init__(translator, parent)

    def build(self) -> None:
        """
        ساخت دو زبانه: تولید گزارش، و عملکرد واقعی سیگنال‌ها.

        چرا زبانه و نه صفحهٔ یازدهم در نوار کناری؟
            نوار کناری ده صفحه دارد و میان‌برهایش `Ctrl+1` تا `Ctrl+0`
            است — یعنی ظرفیتش پر شده. از این گذشته، «گزارش» و «عملکرد»
            یک پرسش‌اند از دو زاویه: چه سیگنالی دادیم، و چه شد. جای
            طبیعی‌شان کنار هم است.
        """
        self.tabs = QTabWidget(self)
        # زبانهٔ گزارش هم مثل زبانهٔ عملکرد باید پیمایش داشته باشد؛
        # بدون آن، حداقل ارتفاعش (۸۶۶ پیکسل) به کل صفحه تحمیل می‌شد و
        # روی نمایشگر لپ‌تاپ پایین صفحه بیرون می‌زد.
        self.tabs.addTab(
            self._wrap_scroll(self._build_report_tab()), self.tr_.tr(TAB_KEYS[0])
        )

        self.performance = PerformanceView(self.tr_, self)
        self.tabs.addTab(self._wrap_scroll(self.performance), self.tr_.tr(TAB_KEYS[1]))

        self.tabs.addTab(
            self._wrap_scroll(self._build_scorecard_tab()), self.tr_.tr(TAB_KEYS[2])
        )

        self.layout_root().addWidget(self.tabs, 1)
        self._apply_headers()

    def _build_scorecard_tab(self) -> QWidget:
        """
        زبانهٔ دفترچهٔ نتیجهٔ پیش‌بینی‌ها.

        هر سیگنال یک بازهٔ قیمتی با اطمینان ۸۰٪ اعلام می‌کند. این جدول
        می‌گوید در عمل چند درصد مواقع قیمت واقعی داخل آن بازه افتاد —
        تنها سنجش صادقانهٔ اینکه عددهای اطمینان واقعی‌اند یا تبلیغاتی.
        """
        page = QWidget(self)
        body = QVBoxLayout(page)
        body.setContentsMargins(0, 8, 0, 0)
        body.setSpacing(12)

        intro = QLabel(self.tr_.tr("scorecard.intro"))
        intro.setWordWrap(True)
        set_role(intro, "muted")
        body.addWidget(intro)

        top = QHBoxLayout()
        self.scorecard_refresh_button = make_button(
            self.tr_.tr("scorecard.refresh"), primary=True
        )
        self.scorecard_refresh_button.clicked.connect(self.scorecard_refresh_requested)
        top.addWidget(self.scorecard_refresh_button)
        self.scorecard_auto_check = QCheckBox(self.tr_.tr("scorecard.auto"))
        self.scorecard_auto_check.setChecked(False)
        self.scorecard_auto_check.toggled.connect(self.scorecard_auto_changed.emit)
        top.addWidget(self.scorecard_auto_check)

        self.scorecard_verdict_label = QLabel(self.tr_.tr("scorecard.no_data"))
        self.scorecard_verdict_label.setWordWrap(True)
        set_role(self.scorecard_verdict_label, "chip_info")
        top.addWidget(self.scorecard_verdict_label, 1)
        body.addLayout(top)

        self.scorecard_table = QTableWidget(0, 5, page)
        self.scorecard_table.setHorizontalHeaderLabels([
            self.tr_.tr("scorecard.col_horizon"),
            self.tr_.tr("scorecard.col_checked"),
            self.tr_.tr("scorecard.col_hits"),
            self.tr_.tr("scorecard.col_rate"),
            self.tr_.tr("scorecard.col_miss"),
        ])
        configure_table(self.scorecard_table, stretch_column=0)
        body.addWidget(self.scorecard_table)

        self.scorecard_note = QLabel(self.tr_.tr("scorecard.pending_note", pending=0))
        self.scorecard_note.setWordWrap(True)
        set_role(self.scorecard_note, "faint")
        body.addWidget(self.scorecard_note)

        body.addStretch(1)
        return page

    def set_scorecard_auto(self, enabled: bool) -> None:
        """نشاندن تیک خودکار بدون اینکه دوباره سیگنال ذخیره بفرستد."""
        box = getattr(self, "scorecard_auto_check", None)
        if box is None:
            return
        box.blockSignals(True)
        box.setChecked(bool(enabled))
        box.blockSignals(False)

    def set_scorecard(self, report: dict[str, Any]) -> None:
        """نشاندن گزارش دفترچهٔ نتیجه روی جدول."""
        rows = list(report.get("rows") or [])
        self.scorecard_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = [
                str(row.get("horizon", "")),
                str(row.get("checked", 0)),
                str(row.get("hits", 0)),
                f"{float(row.get('hit_rate', 0)):.1f}%",
                f"{float(row.get('average_miss', 0)):,.6g}",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.scorecard_table.setItem(index, column, item)

        verdict = str(report.get("verdict") or "insufficient_data")
        checked = int(report.get("checked") or 0)
        if not checked:
            self.scorecard_verdict_label.setText(self.tr_.tr("scorecard.no_data"))
            set_role(self.scorecard_verdict_label, "chip_info")
        else:
            self.scorecard_verdict_label.setText(
                self.tr_.tr(
                    f"scorecard.verdict_{verdict}",
                    rate=f"{float(report.get('hit_rate', 0)):.1f}",
                    target=f"{float(report.get('target_rate', 80)):.0f}",
                    checked=checked,
                )
            )
            set_role(
                self.scorecard_verdict_label,
                "chip_up" if verdict == "calibrated" else "chip_warn",
            )
        self.scorecard_note.setText(
            self.tr_.tr("scorecard.pending_note", pending=int(report.get("pending") or 0))
        )

    @staticmethod
    def _wrap_scroll(widget: Any) -> QScrollArea:
        """
        قراردادن محتوا در ناحیهٔ پیمایش.

        نمای عملکرد سه جدول و چند کارت دارد و روی نمایشگر کوچک جا
        نمی‌شود؛ بدون پیمایش، جدول سابقه از پایین صفحه بیرون می‌زند.
        """
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setWidget(widget)
        return area

    def _build_report_tab(self) -> QWidget:
        """زبانهٔ تولید گزارش — همان محتوای پیشین صفحه."""
        page = QWidget(self)
        body = QVBoxLayout(page)
        body.setContentsMargins(0, 8, 0, 0)
        body.setSpacing(12)

        controls = QHBoxLayout()
        self.period_label = QLabel(self.tr_.tr("reports.period"))
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 3650)
        self.days_spin.setValue(30)
        self.days_spin.setSuffix(" " + self.tr_.tr("reports.days", "days"))

        self.format_label = QLabel(self.tr_.tr("reports.format"))
        self.format_combo = QComboBox()
        self._fill_format_combo()
        self.generate_button = make_button(self.tr_.tr("reports.generate"), primary=True)

        controls.addWidget(self.period_label)
        controls.addWidget(self.days_spin)
        controls.addWidget(self.format_label)
        controls.addWidget(self.format_combo)
        controls.addWidget(self.generate_button)
        controls.addStretch(1)
        body.addLayout(controls)

        # ---- کارت‌های آمار، مطابق تصاویر مرجع ----
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self._stat_cards: dict[str, StatCard] = {}
        for key in STAT_KEYS:
            card = StatCard(show_sparkline=False)
            card.set_data(title=self.tr_.tr(f"reports.{key}"), value="—")
            self._stat_cards[key] = card
            stats_row.addWidget(card, 1)
        body.addLayout(stats_row)

        # ---- نمودار سری زمانی و نمودار حلقه‌ای سهم جهت‌ها ----
        charts_row = QHBoxLayout()
        charts_row.setSpacing(12)

        self.trend_card = Card(self.tr_.tr("reports.confidence_trend"))
        self.area_chart = AreaChart()
        self.trend_card.add(self.area_chart)
        charts_row.addWidget(self.trend_card, 2)

        self.direction_card = Card(self.tr_.tr("reports.direction_share"))
        donut_row = QHBoxLayout()
        self.donut_chart = DonutChart()
        donut_row.addWidget(self.donut_chart, 1)
        self.donut_legend = QLabel("—")
        self.donut_legend.setProperty("role", "muted")
        donut_row.addWidget(self.donut_legend, 1)
        self.direction_card.body().addLayout(donut_row)
        charts_row.addWidget(self.direction_card, 1)

        body.addLayout(charts_row)

        self.summary_card = Card(self.tr_.tr("reports.title"))
        for key in ("total_signals", "by_direction", "average_confidence", "top_symbols"):
            row = KeyValueRow(self.tr_.tr(f"reports.{key}"))
            self._summary_rows[key] = row
            self.summary_card.add(row)
        body.addWidget(self.summary_card)

        self.preview_card = Card()
        self.preview_table = QTableWidget(0, 6)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_card.add(self.preview_table)
        body.addWidget(self.preview_card, 1)

        self.disclaimer = QLabel(self.tr_.tr("reports.disclaimer"))
        self.disclaimer.setProperty("role", "muted")
        self.disclaimer.setWordWrap(True)
        body.addWidget(self.disclaimer)

        return page

    def _apply_headers(self) -> None:
        """تنظیم سرستون‌های پیش‌نمایش."""
        self.preview_table.setHorizontalHeaderLabels([
            self.tr_.tr("signals.generated_at"), self.tr_.tr("common.symbol"),
            self.tr_.tr("signals.direction"), self.tr_.tr("signals.confidence"),
            self.tr_.tr("signals.risk_reward"), self.tr_.tr("signals.trend"),
        ])
        configure_table(self.preview_table, stretch_column=1)

    #: (کد صادرکننده، کلید ترجمه) — کد هرگز ترجمه نمی‌شود
    EXPORT_FORMATS: tuple[tuple[str, str], ...] = (
        ("csv", "reports.formats.csv"),
        ("xlsx", "reports.formats.excel"),
        ("json", "reports.formats.json"),
        ("pdf", "reports.formats.pdf"),
        ("html", "reports.formats.html"),
    )

    def _fill_format_combo(self) -> None:
        """
        پرکردن منوی قالب با نگهداشت انتخاب فعلی.

        کد قالب در `userData` می‌نشیند نه در متن؛ پیش‌تر انتخاب از روی
        متن نمایشی خوانده می‌شد و به‌محض ترجمهٔ گزینه‌ها `KeyError`
        می‌داد.
        """
        current = self.selected_format() if self.format_combo.count() else "csv"
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        for code, key in self.EXPORT_FORMATS:
            self.format_combo.addItem(self.tr_.tr(key), code)
        index = self.format_combo.findData(current)
        self.format_combo.setCurrentIndex(index if index >= 0 else 0)
        self.format_combo.blockSignals(False)

    def selected_format(self) -> str:
        """قالب انتخاب‌شده به‌صورت کد قابل استفاده در ReportExporter."""
        data = self.format_combo.currentData()
        if data:
            return str(data)
        return "csv"

    def set_summary(self, summary: dict[str, Any]) -> None:
        """نمایش آمار خلاصه."""
        self._last_summary = dict(summary or {})
        mapping = {
            "total_signals": self.tr_.format_number(summary.get("total", 0) or 0, 0),
            # جهت‌ها با برچسب زبان جاری نمایش داده می‌شوند، نه LONG/SHORT خام
            "by_direction": ", ".join(
                f"{self.tr_.tr('signals.' + str(key).lower(), str(key))}: "
                f"{self.tr_.format_number(value or 0, 0)}"
                for key, value in (summary.get("by_direction") or {}).items()
            ) or "—",
            "average_confidence": (
                f"{self.tr_.format_number(summary.get('average_confidence', 0) or 0, 1)}%"
            ),
            "top_symbols": ", ".join((summary.get("top_symbols") or {}).keys()) or "—",
        }
        for key, value in mapping.items():
            if key in self._summary_rows:
                self._summary_rows[key].set_value(str(value))

        self._update_visuals(summary)

    def _update_visuals(self, summary: dict[str, Any]) -> None:
        """
        به‌روزرسانی کارت‌های آمار و دو نمودار از روی همان خلاصه.

        داده‌ای که جدول خلاصه می‌سازد دوباره به کار می‌رود؛ هیچ فراخوانی
        تازه‌ای به شبکه یا پایگاه داده لازم نیست.
        """
        by_direction = {
            str(key).upper(): int(value or 0)
            for key, value in (summary.get("by_direction") or {}).items()
        }
        total = int(summary.get("total", 0) or 0)
        long_count = by_direction.get("LONG", 0)
        wait_count = by_direction.get("WAIT", 0)
        short_count = by_direction.get("SHORT", 0)

        def share(count: int) -> str:
            """درصد سهم یک جهت از کل سیگنال‌ها، با ارقام زبان جاری."""
            if not total:
                return "—"
            return f"{self.tr_.format_number(round(count * 100 / total), 0)}%"

        self._stat_cards["total_signals"].set_data(value=self.tr_.format_number(total, 0))
        self._stat_cards["average_confidence"].set_data(
            value=f"{self.tr_.format_number(summary.get('average_confidence', 0) or 0, 1)}%"
        )
        self._stat_cards["long_share"].set_data(value=share(long_count))
        self._stat_cards["wait_share"].set_data(value=share(wait_count))

        # نمودار حلقه‌ای سهم جهت‌ها
        self.donut_chart.set_segments(
            [
                (self.tr_.tr("signals.long"), float(long_count), "success"),
                (self.tr_.tr("signals.short"), float(short_count), "danger"),
                (self.tr_.tr("signals.wait"), float(wait_count), "muted"),
            ],
            center_label=self.tr_.format_number(total, 0) if total else "—",
        )
        self.donut_legend.setText(
            "\n".join(
                f"{label} — {self.tr_.format_number(count, 0)} ({share(count)})"
                for label, count in (
                    (self.tr_.tr("signals.long"), long_count),
                    (self.tr_.tr("signals.short"), short_count),
                    (self.tr_.tr("signals.wait"), wait_count),
                )
            )
        )

        # نمودار سری زمانی اطمینان
        series = [float(value) for value in (summary.get("confidence_series") or [])]
        self.area_chart.set_series(series, color_name="primary")

    def apply_theme(self, theme: Any) -> None:
        """اعمال پوسته روی ویجت‌های نقاشی‌شونده."""
        self.area_chart.apply_theme(theme)
        self.donut_chart.apply_theme(theme)
        for card in self._stat_cards.values():
            card.apply_theme(theme)
        self.performance.apply_theme(theme)

    def show_performance(self) -> None:
        """باز کردن زبانهٔ عملکرد (از میان‌بر یا پیوند صفحات دیگر)."""
        self.tabs.setCurrentIndex(1)

    def set_preview(self, rows: list[dict[str, Any]]) -> None:
        """نمایش پیش‌نمایش سطرهای گزارش."""
        self._last_preview = [dict(row) for row in rows]
        limited = rows[:200]
        self.preview_table.setRowCount(len(limited))
        for index, row in enumerate(limited):
            direction = str(row.get("direction", "") or "")
            values = [
                row.get("created_at", ""),
                row.get("symbol", ""),
                self.tr_.tr(f"signals.{direction.lower()}", direction) if direction else "",
                f"{self.tr_.format_number(row.get('confidence', 0) or 0, 0)}%",
                (
                    self.tr_.format_number(row.get("risk_reward"), 2)
                    if row.get("risk_reward")
                    else "—"
                ),
                row.get("trend", ""),
            ]
            for column, value in enumerate(values):
                self.preview_table.setItem(index, column, QTableWidgetItem(str(value)))

    def retranslate(self) -> None:
        """بازسازی متن‌ها."""
        super().retranslate()
        self.period_label.setText(self.tr_.tr("reports.period"))
        self.format_label.setText(self.tr_.tr("reports.format"))
        self._fill_format_combo()
        self.generate_button.setText(self.tr_.tr("reports.generate"))
        self.summary_card.set_title(self.tr_.tr("reports.title"))
        self.days_spin.setSuffix(" " + self.tr_.tr("reports.days", "days"))
        for key, row in self._summary_rows.items():
            row.set_key(self.tr_.tr(f"reports.{key}"))
        self.disclaimer.setText(self.tr_.tr("reports.disclaimer"))
        for index, key in enumerate(TAB_KEYS):
            self.tabs.setTabText(index, self.tr_.tr(key))
        self.performance.retranslate()
        self.trend_card.set_title(self.tr_.tr("reports.confidence_trend"))
        self.direction_card.set_title(self.tr_.tr("reports.direction_share"))
        for key, card in self._stat_cards.items():
            card.set_data(title=self.tr_.tr(f"reports.{key}"))
        if self._last_summary:
            self.set_summary(self._last_summary)
        if self._last_preview:
            self.set_preview(list(self._last_preview))
        self._apply_headers()
