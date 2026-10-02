"""
مرکز لاگ — نسخهٔ ۲.۶.۰.

سه زبانه:
    • لاگ زنده: نمای بلادرنگ از بافر حافظه (`log_buffer`) با فیلتر دسته، سطح،
      نماد، شناسهٔ معامله، بازهٔ زمانی و جست‌وجو؛ پاک کردن، تازه‌سازی، خروجی،
      کپی و پیمایش خودکار. حالت «تاریخچه» همان فیلترها را روی فایل‌های
      `logs/<دسته>/` و پایگاه دادهٔ ممیزی اجرا می‌کند.
    • تشخیص پویش: Scanned / Raw / Rejected by … / Final / Opened برای آخرین
      پویش و جمع خلاصه‌های ذخیره‌شده، به‌همراه پرتکرارترین دلایل رد.
    • خط زمانی معامله: Signal → Candidate → Validation → Entry → Monitoring → Exit.

صفحه هیچ I/O سنگینی در رشتهٔ رابط کاربری انجام نمی‌دهد مگر با درخواست کاربر
(تازه‌سازی/تاریخچه) و همیشه با سقف تعداد رکورد. منطق فیلتر در
`app.logging.query` است تا بدون Qt آزمون شود.
"""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QDateTime, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.logging.audit import SUMMARY_BUCKETS, TIMELINE_STAGES
from app.logging.categories import LogCategory
from app.logging.query import (
    LogFilter,
    export_events,
    filter_events,
    format_event_line,
    summary_row,
    timeline_stages,
    total_summary,
)
from app.logging.structured import log_buffer, logs_dir as structured_logs_dir, read_log_files
from localization import Translator
from ui.pages.base_page import BasePage
from ui.widgets.common import configure_table, make_button

#: سطرهای قابل نمایش در جدول زنده (قدیمی‌ترها از بالا حذف می‌شوند)
MAX_ROWS = 2000
#: رکوردهای نگه‌داشته در حافظهٔ صفحه برای فیلتر دوباره
MAX_EVENTS = 10_000
#: سقف خواندن تاریخچه
HISTORY_LIMIT = 5000
#: فاصلهٔ خواندن بافر زنده (میلی‌ثانیه)
POLL_MS = 700

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LEVEL_COLORS = {"WARNING": "#d29922", "ERROR": "#f85149", "CRITICAL": "#ff4d6d", "DEBUG": "#8b949e"}
COLUMNS = ("time", "level", "category", "module", "event", "symbol", "trade", "reason", "message")
SCAN_METRICS: tuple[str, ...] = (
    "scans", "scanned_symbols", "raw_candidates",
    *(f"rejected_{bucket}" for bucket in SUMMARY_BUCKETS),
    "source_candidates", "final_candidates", "opened_trades",
)
ENGINES = ("", "ultra", "scan", "selected", "ai")


class LogCenterPage(BasePage):
    """مرکز لاگ: نمای زنده، تشخیص پویش و خط زمانی معامله."""

    title_key = "nav.logs"
    subtitle_key = "logs.subtitle"

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS)
        self._visible: list[dict[str, Any]] = []
        self._last_seq = 0
        self._history_mode = False
        self._audit_repository: Any = None
        self._logs_dir: Path | None = None
        self._timeline_events: list[dict[str, Any]] = []
        super().__init__(translator, parent)
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self.poll_live)

    # ------------------------------------------------------------------
    # منابع داده
    # ------------------------------------------------------------------
    def set_sources(self, *, audit_repository: Any = None, logs_dir: Path | str | None = None) -> None:
        """تزریق مخزن ممیزی و پوشهٔ لاگ (کنترلر یا آزمون)."""
        self._audit_repository = audit_repository
        self._logs_dir = Path(logs_dir) if logs_dir else None

    def _base_dir(self) -> Path | None:
        return self._logs_dir or structured_logs_dir()

    # ------------------------------------------------------------------
    # ساخت
    # ------------------------------------------------------------------
    def build(self) -> None:
        tr = self.tr_.tr
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_live(), tr("logs.tab_live"))
        self.tabs.addTab(self._build_scan(), tr("logs.tab_scan"))
        self.tabs.addTab(self._build_timeline(), tr("logs.tab_timeline"))
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.layout_root().addWidget(self.tabs, 1)

    def _build_live(self) -> QWidget:
        tr = self.tr_.tr
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(6)

        # ردیف ۱: دسته، سطح، نماد، شناسهٔ معامله، جست‌وجو
        row1 = QHBoxLayout()
        self.category_label = QLabel(tr("logs.category"))
        self.category_combo = QComboBox()
        self.category_combo.addItem(tr("logs.all"), "")
        for category in LogCategory:
            self.category_combo.addItem(tr(f"logs.cat_{category.value}"), category.value)
        self.level_label = QLabel(tr("logs.level"))
        self.level_combo = QComboBox()
        self.level_combo.addItem(tr("logs.all"), "")
        for level in LEVELS:
            self.level_combo.addItem(level, level)
        self.symbol_edit = QLineEdit()
        self.symbol_edit.setPlaceholderText(tr("logs.symbol"))
        self.symbol_edit.setMaximumWidth(140)
        self.trade_edit = QLineEdit()
        self.trade_edit.setPlaceholderText(tr("logs.trade_id"))
        self.trade_edit.setMaximumWidth(110)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("logs.search"))
        self.search_edit.setClearButtonEnabled(True)
        for item in (self.category_label, self.category_combo, self.level_label, self.level_combo,
                     self.symbol_edit, self.trade_edit):
            row1.addWidget(item)
        row1.addWidget(self.search_edit, 1)
        layout.addLayout(row1)

        # ردیف ۲: بازهٔ زمانی + دکمه‌ها
        row2 = QHBoxLayout()
        self.use_dates = QCheckBox(tr("logs.use_dates"))
        now = QDateTime.currentDateTime()
        self.start_edit = QDateTimeEdit(now.addSecs(-3600))
        self.end_edit = QDateTimeEdit(now.addSecs(3600))
        for edit in (self.start_edit, self.end_edit):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd HH:mm")
            edit.setEnabled(False)
        self.use_dates.toggled.connect(self.start_edit.setEnabled)
        self.use_dates.toggled.connect(self.end_edit.setEnabled)
        self.history_check = QCheckBox(tr("logs.history"))
        self.auto_scroll = QCheckBox(tr("logs.auto_scroll"))
        self.auto_scroll.setChecked(True)
        self.pause_check = QCheckBox(tr("logs.pause"))
        self.refresh_button = make_button(tr("logs.refresh"))
        self.clear_button = make_button(tr("logs.clear"))
        self.copy_button = make_button(tr("logs.copy"))
        self.export_button = make_button(tr("logs.export"), primary=True)
        for item in (self.use_dates, self.start_edit, self.end_edit, self.history_check):
            row2.addWidget(item)
        row2.addStretch(1)
        for item in (self.auto_scroll, self.pause_check, self.refresh_button, self.clear_button,
                     self.copy_button, self.export_button):
            row2.addWidget(item)
        layout.addLayout(row2)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("logCenterTable")
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setMinimumHeight(140)
        configure_table(self.table, stretch_column=len(COLUMNS) - 1)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText(tr("logs.details"))
        self.details.setMinimumHeight(60)
        splitter.addWidget(self.table)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        self._set_headers()

        # اتصال‌ها
        for combo in (self.category_combo, self.level_combo):
            combo.currentIndexChanged.connect(self.apply_filters)
        for edit in (self.symbol_edit, self.trade_edit, self.search_edit):
            edit.textChanged.connect(self.apply_filters)
        self.use_dates.toggled.connect(self.apply_filters)
        self.start_edit.dateTimeChanged.connect(self.apply_filters)
        self.end_edit.dateTimeChanged.connect(self.apply_filters)
        self.history_check.toggled.connect(self.set_history_mode)
        self.refresh_button.clicked.connect(self.refresh)
        self.clear_button.clicked.connect(self.clear_view)
        self.copy_button.clicked.connect(self.copy_selected)
        self.export_button.clicked.connect(self._export_dialog)
        self.table.itemSelectionChanged.connect(self._show_details)
        return widget

    def _build_scan(self) -> QWidget:
        tr = self.tr_.tr
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        row = QHBoxLayout()
        self.scan_engine_label = QLabel(tr("logs.scan_engine"))
        self.scan_engine_combo = QComboBox()
        for engine in ENGINES:
            self.scan_engine_combo.addItem(engine or tr("logs.all"), engine)
        self.scan_refresh_button = make_button(tr("logs.refresh"))
        row.addWidget(self.scan_engine_label)
        row.addWidget(self.scan_engine_combo)
        row.addStretch(1)
        row.addWidget(self.scan_refresh_button)
        layout.addLayout(row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.scan_table = QTableWidget(len(SCAN_METRICS), 3)
        self.scan_table.setObjectName("scanDiagnosticsTable")
        self.scan_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.scan_table.verticalHeader().setVisible(False)
        self.scan_table.setMinimumHeight(140)
        configure_table(self.scan_table, stretch_column=0)
        self.reason_table = QTableWidget(0, 2)
        self.reason_table.setObjectName("scanReasonsTable")
        self.reason_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.reason_table.verticalHeader().setVisible(False)
        self.reason_table.setMinimumHeight(140)
        configure_table(self.reason_table, stretch_column=0)
        splitter.addWidget(self.scan_table)
        splitter.addWidget(self.reason_table)
        layout.addWidget(splitter, 1)
        self.scan_status = QLabel("")
        self.scan_status.setWordWrap(True)
        layout.addWidget(self.scan_status)
        self._set_scan_headers()
        self.scan_engine_combo.currentIndexChanged.connect(self.refresh_scan)
        self.scan_refresh_button.clicked.connect(self.refresh_scan)
        return widget

    def _build_timeline(self) -> QWidget:
        tr = self.tr_.tr
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        row = QHBoxLayout()
        self.timeline_label = QLabel(tr("logs.timeline_trade"))
        self.timeline_combo = QComboBox()
        self.timeline_combo.setEditable(True)
        self.timeline_combo.setMinimumWidth(120)
        self.timeline_button = make_button(tr("logs.timeline_load"), primary=True)
        self.timeline_refresh = make_button(tr("logs.refresh"))
        row.addWidget(self.timeline_label)
        row.addWidget(self.timeline_combo)
        row.addWidget(self.timeline_button)
        row.addStretch(1)
        row.addWidget(self.timeline_refresh)
        layout.addLayout(row)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.stage_table = QTableWidget(len(TIMELINE_STAGES), 4)
        self.stage_table.setObjectName("timelineStageTable")
        self.stage_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stage_table.verticalHeader().setVisible(False)
        self.stage_table.setMinimumHeight(120)
        configure_table(self.stage_table, stretch_column=3)
        self.timeline_table = QTableWidget(0, 5)
        self.timeline_table.setObjectName("timelineEventTable")
        self.timeline_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.timeline_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.timeline_table.verticalHeader().setVisible(False)
        self.timeline_table.setMinimumHeight(120)
        configure_table(self.timeline_table, stretch_column=4)
        self.timeline_details = QPlainTextEdit()
        self.timeline_details.setReadOnly(True)
        self.timeline_details.setMinimumHeight(50)
        splitter.addWidget(self.stage_table)
        splitter.addWidget(self.timeline_table)
        splitter.addWidget(self.timeline_details)
        layout.addWidget(splitter, 1)
        self.timeline_status = QLabel("")
        layout.addWidget(self.timeline_status)
        self._set_timeline_headers()
        self.timeline_button.clicked.connect(lambda: self.load_timeline(self.timeline_combo.currentText()))
        self.timeline_combo.activated.connect(lambda _i: self.load_timeline(self.timeline_combo.currentText()))
        self.timeline_refresh.clicked.connect(self.refresh_trade_ids)
        self.timeline_table.itemSelectionChanged.connect(self._show_timeline_details)
        return widget

    # ------------------------------------------------------------------
    # سرستون‌ها و ترجمه
    # ------------------------------------------------------------------
    def _set_headers(self) -> None:
        self.table.setHorizontalHeaderLabels([self.tr_.tr(f"logs.col_{c}") for c in COLUMNS])

    def _set_scan_headers(self) -> None:
        tr = self.tr_.tr
        self.scan_table.setHorizontalHeaderLabels(["", tr("logs.tab_scan"), tr("logs.scan_total")])
        self.reason_table.setHorizontalHeaderLabels([tr("logs.scan_reasons"), "#"])
        for row, metric in enumerate(SCAN_METRICS):
            self.scan_table.setItem(row, 0, QTableWidgetItem(self._metric_label(metric)))

    def _set_timeline_headers(self) -> None:
        tr = self.tr_.tr
        self.stage_table.setHorizontalHeaderLabels(["", tr("logs.col_level"), tr("logs.col_time"), tr("logs.col_message")])
        self.timeline_table.setHorizontalHeaderLabels([
            tr("logs.col_time"), tr("logs.col_event"), tr("logs.col_category"), tr("logs.col_reason"), tr("logs.col_message"),
        ])
        for row, stage in enumerate(TIMELINE_STAGES):
            self.stage_table.setItem(row, 0, QTableWidgetItem(tr(f"logs.stage_{stage}")))

    def _metric_label(self, metric: str) -> str:
        if metric.startswith("rejected_"):
            return self.tr_.tr(f"logs.bucket_{metric[len('rejected_'):]}")
        return self.tr_.tr(f"logs.sum_{metric}")

    def retranslate(self) -> None:
        super().retranslate()
        tr = self.tr_.tr
        for index, key in enumerate(("logs.tab_live", "logs.tab_scan", "logs.tab_timeline")):
            self.tabs.setTabText(index, tr(key))
        self.category_label.setText(tr("logs.category"))
        self.level_label.setText(tr("logs.level"))
        self.category_combo.setItemText(0, tr("logs.all"))
        for index, category in enumerate(LogCategory, start=1):
            self.category_combo.setItemText(index, tr(f"logs.cat_{category.value}"))
        self.level_combo.setItemText(0, tr("logs.all"))
        self.scan_engine_combo.setItemText(0, tr("logs.all"))
        self.symbol_edit.setPlaceholderText(tr("logs.symbol"))
        self.trade_edit.setPlaceholderText(tr("logs.trade_id"))
        self.search_edit.setPlaceholderText(tr("logs.search"))
        self.details.setPlaceholderText(tr("logs.details"))
        for widget, key in ((self.use_dates, "logs.use_dates"), (self.history_check, "logs.history"),
                            (self.auto_scroll, "logs.auto_scroll"), (self.pause_check, "logs.pause"),
                            (self.refresh_button, "logs.refresh"), (self.clear_button, "logs.clear"),
                            (self.copy_button, "logs.copy"), (self.export_button, "logs.export"),
                            (self.scan_engine_label, "logs.scan_engine"), (self.scan_refresh_button, "logs.refresh"),
                            (self.timeline_label, "logs.timeline_trade"), (self.timeline_button, "logs.timeline_load"),
                            (self.timeline_refresh, "logs.refresh")):
            widget.setText(tr(key))
        self._set_headers()
        self._set_scan_headers()
        self._set_timeline_headers()
        self._update_status()

    # ------------------------------------------------------------------
    # چرخهٔ عمر
    # ------------------------------------------------------------------
    def on_activated(self) -> None:
        if not self._history_mode:
            self.poll_live()
        self._timer.start()
        self._on_tab_changed(self.tabs.currentIndex())

    def hideEvent(self, event: Any) -> None:  # noqa: N802 - پنهان: خواندن زنده متوقف
        self._timer.stop()
        super().hideEvent(event)

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self.refresh_scan()
        elif index == 2 and self.timeline_combo.count() == 0:
            self.refresh_trade_ids()

    # ------------------------------------------------------------------
    # فیلتر
    # ------------------------------------------------------------------
    def current_filter(self) -> LogFilter:
        category = self.category_combo.currentData() or ""
        start = end = None
        if self.use_dates.isChecked():
            start = self.start_edit.dateTime().toPython()
            end = self.end_edit.dateTime().toPython()
        return LogFilter(
            categories={category} if category else set(),
            min_level=self.level_combo.currentData() or "",
            symbol=self.symbol_edit.text().strip(),
            trade_id=self.trade_edit.text().strip(),
            start=start,
            end=end,
            search=self.search_edit.text().strip(),
        )

    def set_filter(self, *, category: str = "", level: str = "", symbol: str = "", trade_id: str = "",
                   search: str = "", start: datetime | None = None, end: datetime | None = None) -> None:
        """تنظیم برنامه‌ای فیلترها (پرش از صفحه‌های دیگر و آزمون)."""
        widgets = (self.category_combo, self.level_combo, self.symbol_edit, self.trade_edit,
                   self.search_edit, self.use_dates, self.start_edit, self.end_edit)
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self.category_combo.setCurrentIndex(max(0, self.category_combo.findData(category)))
            self.level_combo.setCurrentIndex(max(0, self.level_combo.findData(level.upper() if level else "")))
            self.symbol_edit.setText(symbol)
            self.trade_edit.setText(str(trade_id or ""))
            self.search_edit.setText(search)
            use = start is not None or end is not None
            self.use_dates.setChecked(use)
            self.start_edit.setEnabled(use)
            self.end_edit.setEnabled(use)
            if start is not None:
                self.start_edit.setDateTime(QDateTime(start))
            if end is not None:
                self.end_edit.setDateTime(QDateTime(end))
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        self.apply_filters()

    def apply_filters(self, *_args: Any) -> None:
        """بازسازی جدول از رکوردهای نگه‌داشته با فیلتر جاری."""
        self._visible = filter_events(self._events, self.current_filter())[-MAX_ROWS:]
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(0)
            self._append_rows(self._visible)
        finally:
            self.table.setUpdatesEnabled(True)
        self._update_status()

    def visible_events(self) -> list[dict[str, Any]]:
        return list(self._visible)

    # ------------------------------------------------------------------
    # زنده و تاریخچه
    # ------------------------------------------------------------------
    def poll_live(self) -> int:
        """رکوردهای تازهٔ بافر؛ بازگشت: تعداد رکورد جدید."""
        if self._history_mode:
            return 0
        try:
            items = log_buffer().since(self._last_seq)
        except Exception:  # noqa: BLE001
            return 0
        if not items:
            return 0
        self._last_seq = int(items[-1].get("seq", self._last_seq))
        self._events.extend(items)
        if self.pause_check.isChecked():
            self._update_status()
            return len(items)
        matched = filter_events(items, self.current_filter())
        if matched:
            self._visible.extend(matched)
            overflow = len(self._visible) - MAX_ROWS
            if overflow > 0:
                del self._visible[:overflow]
                for _ in range(min(overflow, self.table.rowCount())):
                    self.table.removeRow(0)
            self._append_rows(matched[-MAX_ROWS:])
        self._update_status()
        return len(items)

    def set_history_mode(self, enabled: bool) -> None:
        self._history_mode = bool(enabled)
        if self.history_check.isChecked() != self._history_mode:
            self.history_check.blockSignals(True)
            self.history_check.setChecked(self._history_mode)
            self.history_check.blockSignals(False)
        self.refresh()

    def refresh(self) -> None:
        """زنده: بازخوانی کامل بافر. تاریخچه: خواندن فایل‌ها + پایگاه داده."""
        self._events.clear()
        if self._history_mode:
            self._events.extend(self._load_history())
            self._last_seq = 0
        else:
            try:
                snapshot = log_buffer().snapshot()
            except Exception:  # noqa: BLE001
                snapshot = []
            self._events.extend(snapshot)
            self._last_seq = int(snapshot[-1].get("seq", 0)) if snapshot else 0
        self.apply_filters()

    def _load_history(self) -> list[dict[str, Any]]:
        criteria = self.current_filter()
        events: list[dict[str, Any]] = []
        base = self._base_dir()
        if base is not None:
            try:
                events.extend(read_log_files(base, categories=criteria.categories or None,
                                             start=criteria.start, end=criteria.end, limit=HISTORY_LIMIT))
            except Exception:  # noqa: BLE001
                pass
        if self._audit_repository is not None and not events:
            # فایل‌ها نبودند (مثلاً پاک شده‌اند): رویدادهای ممیزی از پایگاه داده
            try:
                trade_id = int(criteria.trade_id.lstrip("#")) if criteria.trade_id.strip().lstrip("#").isdigit() else None
                events.extend(self._audit_repository.query(
                    categories=criteria.categories or None, symbol=criteria.symbol or None, trade_id=trade_id,
                    start=criteria.start, end=criteria.end, search=criteria.search or None, limit=HISTORY_LIMIT,
                ))
            except Exception:  # noqa: BLE001
                pass
        events.sort(key=lambda e: float(e.get("epoch") or 0.0))
        return events[-MAX_EVENTS:]

    def clear_view(self) -> None:
        """فقط نمای صفحه پاک می‌شود؛ فایل‌ها و پایگاه داده دست‌نخورده‌اند."""
        self._events.clear()
        self._visible = []
        self.table.setRowCount(0)
        self.details.clear()
        try:
            self._last_seq = log_buffer().last_seq
        except Exception:  # noqa: BLE001
            pass
        self.status_label.setText(self.tr_.tr("logs.cleared"))

    # ------------------------------------------------------------------
    # جدول
    # ------------------------------------------------------------------
    def _append_rows(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        table = self.table
        start = table.rowCount()
        table.setRowCount(start + len(events))
        for offset, event in enumerate(events):
            row = start + offset
            ts = str(event.get("ts", ""))
            values = (
                ts[11:23] if len(ts) >= 23 else ts,
                str(event.get("level", "")),
                str(event.get("category", "")),
                str(event.get("module", "")),
                str(event.get("event", "") or ""),
                str(event.get("symbol", "") or ""),
                str(event.get("trade_id", "") or ""),
                str(event.get("reason_code", "") or ""),
                str(event.get("message", ""))[:400],
            )
            color = LEVEL_COLORS.get(values[1])
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setToolTip(ts)
                if color and column in (1, 8):
                    item.setForeground(_brush(color))
                table.setItem(row, column, item)
        if self.auto_scroll.isChecked():
            table.scrollToBottom()

    def _selected_events(self) -> list[dict[str, Any]]:
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        return [self._visible[row] for row in rows if 0 <= row < len(self._visible)]

    def _show_details(self) -> None:
        selected = self._selected_events()
        if not selected:
            return
        event = {k: v for k, v in selected[-1].items() if k not in ("persist",)}
        self.details.setPlainText(json.dumps(event, ensure_ascii=False, indent=2, default=str))

    def copy_selected(self) -> str:
        """کپی رکوردهای انتخاب‌شده (یا همهٔ رکوردهای نمایان) به کلیپ‌بورد."""
        events = self._selected_events() or self._visible
        text = "\n".join(format_event_line(event) for event in events)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        self.status_label.setText(self.tr_.tr("logs.copied", count=len(events)))
        return text

    def export_to(self, path: Path | str) -> int:
        """خروجی رکوردهای نمایان (فیلترشده) به CSV / JSONL / TXT."""
        try:
            count = export_events(self._visible, path)
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(self.tr_.tr("logs.export_failed", error=str(exc)))
            return 0
        self.status_label.setText(self.tr_.tr("logs.exported", count=count, path=str(path)))
        return count

    def _export_dialog(self) -> None:
        base = self._base_dir()
        folder = (base / "exports") if base is not None else Path.home()
        default = folder / f"logs-{datetime.now():%Y%m%d-%H%M%S}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr_.tr("logs.export_title"), str(default),
            "CSV (*.csv);;JSON Lines (*.jsonl);;Text (*.txt)",
        )
        if path:
            self.export_to(path)

    def _update_status(self) -> None:
        text = self.tr_.tr("logs.shown", shown=len(self._visible), total=len(self._events))
        try:
            from app.logging.structured import stats

            dropped = int(stats().get("dropped", 0))
        except Exception:  # noqa: BLE001
            dropped = 0
        if dropped:
            text += " — " + self.tr_.tr("logs.dropped", count=dropped)
        self.status_label.setText(text)

    # ------------------------------------------------------------------
    # تشخیص پویش
    # ------------------------------------------------------------------
    def refresh_scan(self, *_args: Any) -> dict[str, Any]:
        """آخرین پویش (بافر زنده) و جمع خلاصه‌های ذخیره‌شده (پایگاه داده/بافر)."""
        engine = self.scan_engine_combo.currentData() or ""
        latest: dict[str, Any] | None = None
        aggregated: list[dict[str, Any]] = []
        try:
            buffered = log_buffer().snapshot()
        except Exception:  # noqa: BLE001
            buffered = []
        for event in reversed(buffered):
            if event.get("event") != "scan_summary":
                continue
            context = event.get("context") or {}
            if engine and context.get("engine") != engine:
                continue
            if context.get("aggregated"):
                aggregated.append(event)
            elif latest is None:
                latest = event
        stored: list[dict[str, Any]] = []
        if self._audit_repository is not None:
            try:
                stored = self._audit_repository.scan_summaries(limit=200, engine=engine or None)
            except Exception:  # noqa: BLE001
                stored = []
        rows = [summary_row(e) for e in (stored or list(reversed(aggregated)))]
        total = total_summary(rows)
        latest_row = summary_row(latest) if latest is not None else None
        for row, metric in enumerate(SCAN_METRICS):
            last_value = "" if latest_row is None else str(latest_row.get(metric, latest_row.get("scans", "")))
            self.scan_table.setItem(row, 1, QTableWidgetItem(last_value))
            self.scan_table.setItem(row, 2, QTableWidgetItem(str(total.get(metric, 0)) if rows else ""))
        reasons = dict(total.get("reasons") or {})
        if not reasons and latest_row is not None:
            reasons = dict(latest_row.get("reasons") or {})
        self.reason_table.setRowCount(len(reasons))
        for row, (code, count) in enumerate(reasons.items()):
            self.reason_table.setItem(row, 0, QTableWidgetItem(code))
            self.reason_table.setItem(row, 1, QTableWidgetItem(str(count)))
        if latest_row is None and not rows:
            self.scan_status.setText(self.tr_.tr("logs.scan_empty"))
        else:
            self.scan_status.setText(
                f"{self.tr_.tr('logs.scan_rows')}: {len(rows)}"
                + (f" — {latest.get('ts', '')}" if latest is not None else "")
            )
        return {"latest": latest_row, "total": total if rows else None}

    # ------------------------------------------------------------------
    # خط زمانی معامله
    # ------------------------------------------------------------------
    def refresh_trade_ids(self) -> None:
        ids: list[int] = []
        if self._audit_repository is not None:
            try:
                ids = self._audit_repository.recent_trade_ids(limit=200)
            except Exception:  # noqa: BLE001
                ids = []
        current = self.timeline_combo.currentText()
        self.timeline_combo.blockSignals(True)
        self.timeline_combo.clear()
        for trade_id in ids:
            self.timeline_combo.addItem(f"#{trade_id}", trade_id)
        if current:
            self.timeline_combo.setEditText(current)
        self.timeline_combo.blockSignals(False)

    def load_timeline(self, trade_id: Any) -> list[dict[str, Any]]:
        """خط زمانی یک معامله؛ از پایگاه داده، وگرنه از بافر زنده."""
        text = str(trade_id or "").strip().lstrip("#")
        if not text.isdigit():
            return []
        number = int(text)
        events: list[dict[str, Any]] = []
        if self._audit_repository is not None:
            try:
                events = self._audit_repository.timeline(number)
            except Exception:  # noqa: BLE001
                events = []
        if not events:
            try:
                buffered = log_buffer().snapshot()
            except Exception:  # noqa: BLE001
                buffered = []
            correlation = {e.get("correlation_id") for e in buffered
                           if e.get("audit") and str(e.get("trade_id", "")) == text and e.get("correlation_id")}
            events = [e for e in buffered if e.get("audit") and (
                str(e.get("trade_id", "")) == text or (e.get("correlation_id") in correlation))]
        self._timeline_events = sorted(events, key=lambda e: float(e.get("epoch") or 0.0))
        tr = self.tr_.tr
        stages = timeline_stages(self._timeline_events)
        for row, stage in enumerate(stages):
            self.stage_table.setItem(row, 0, QTableWidgetItem(tr(f"logs.stage_{stage['stage']}")))
            status = QTableWidgetItem(tr(f"logs.stage_{stage['status']}"))
            status.setForeground(_brush("#3fb950" if stage["status"] == "done" else "#8b949e"))
            self.stage_table.setItem(row, 1, status)
            self.stage_table.setItem(row, 2, QTableWidgetItem(str(stage["ts"])[11:23] if stage["ts"] else ""))
            summary = "; ".join(str(e.get("message", "")) for e in stage["events"][:3])
            self.stage_table.setItem(row, 3, QTableWidgetItem(summary))
        self.timeline_table.setRowCount(len(self._timeline_events))
        for row, event in enumerate(self._timeline_events):
            ts = str(event.get("ts", ""))
            values = (ts[11:23] if len(ts) >= 23 else ts, str(event.get("event", "")), str(event.get("category", "")),
                      str(event.get("reason_code", "") or ""), str(event.get("message", "")))
            for column, value in enumerate(values):
                self.timeline_table.setItem(row, column, QTableWidgetItem(value))
        self.timeline_details.clear()
        self.timeline_status.setText(
            tr("logs.timeline_empty") if not events else tr("logs.shown", shown=len(events), total=len(events))
        )
        return stages

    def _show_timeline_details(self) -> None:
        rows = sorted({index.row() for index in self.timeline_table.selectedIndexes()})
        if not rows or rows[-1] >= len(self._timeline_events):
            return
        event = {k: v for k, v in self._timeline_events[rows[-1]].items() if k != "persist"}
        self.timeline_details.setPlainText(json.dumps(event, ensure_ascii=False, indent=2, default=str))


def _brush(color: str) -> Any:
    from PySide6.QtGui import QBrush, QColor

    return QBrush(QColor(color))


__all__ = ["LogCenterPage"]
