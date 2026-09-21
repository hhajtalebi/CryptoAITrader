"""
پنجرهٔ نمایش تحلیل نوشتاری یک سیگنال.

کاربر خواست:

    «یک دکمه یا آیکن در همان جدول سابقهٔ سیگنال باشد که وقتی روی آن کلیک
     کردیم مدال باز شود و تحلیل قابل خواندن باشد و از تحلیل همیشه خروجی
     PDF فارسی گرفت»

متن تحلیل با نشانه‌گذاری سبک (عنوان‌های `## ...`) ذخیره می‌شود؛ اینجا به
HTML ساده تبدیل و با فاصله‌گذاری خوانا نمایش داده می‌شود.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from localization import Translator
from ui.widgets import make_button


class AnalysisDialog(QDialog):
    """
    نمایش متن تحلیل با امکان گرفتن خروجی PDF فارسی.

    مثال:
        dialog = AnalysisDialog(signal_dict, translator, parent)
        dialog.pdf_requested.connect(handler)
        dialog.exec()
    """

    #: کاربر خروجی PDF خواست (دادهٔ سیگنال)
    pdf_requested = Signal(dict)
    #: کاربر خواست تحلیل هوش مصنوعی روی همین سیگنال دوباره اجرا شود
    rerun_requested = Signal(dict)

    def __init__(
        self,
        signal: dict[str, Any],
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._signal = dict(signal or {})

        symbol = str(self._signal.get("symbol", ""))
        self.setWindowTitle(self.tr_.tr("signals.analysis_title", symbol=symbol))
        self.setMinimumSize(620, 620)
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if self.tr_.is_rtl else Qt.LayoutDirection.LeftToRight
        )
        self._build()

    # ------------------------------------------------------------------
    # ساخت رابط
    # ------------------------------------------------------------------
    def _build(self) -> None:
        """چیدمان پنجره."""
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        root.addWidget(self._build_header())

        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(False)
        self.viewer.setHtml(self._to_html(str(self._signal.get("analysis_text", ""))))
        root.addWidget(self.viewer, 1)

        # سیگنالی که هنوز تحلیل ندارد نباید پنجرهٔ خالی نشان دهد؛
        # کاربر باید بتواند همان‌جا تحلیل را بسازد.
        if not str(self._signal.get("analysis_text", "")).strip():
            self.viewer.setHtml(self._to_html(self.tr_.tr("signals.analysis_absent")))

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        buttons = QHBoxLayout()
        self.pdf_button = make_button(self.tr_.tr("signals.export_pdf"), primary=True)
        self.pdf_button.clicked.connect(lambda: self.pdf_requested.emit(dict(self._signal)))
        buttons.addWidget(self.pdf_button)

        self.copy_button = make_button(self.tr_.tr("signals.copy_text"))
        self.copy_button.clicked.connect(self._copy_text)
        buttons.addWidget(self.copy_button)

        # کاربر خواست بتواند روی سیگنالِ ساخته‌شده دوباره تحلیل بگیرد.
        self.rerun_button = make_button(self.tr_.tr("signals.rerun_ai"))
        self.rerun_button.clicked.connect(self._on_rerun)
        buttons.addWidget(self.rerun_button)

        buttons.addStretch(1)
        self.close_button = make_button(self.tr_.tr("common.close"))
        self.close_button.clicked.connect(self.accept)
        buttons.addWidget(self.close_button)
        root.addLayout(buttons)

    def _build_header(self) -> QWidget:
        """سربرگ: نماد، جهت و منبع تحلیل."""
        frame = QFrame()
        frame.setProperty("role", "card")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)

        left = QVBoxLayout()
        symbol = QLabel(str(self._signal.get("symbol", "—")))
        symbol.setProperty("role", "title")
        font = symbol.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 3)
        symbol.setFont(font)
        left.addWidget(symbol)

        source = str(self._signal.get("analysis_source", "") or "")
        if source:
            key = "signals.analysis_by_ai" if source == "ai" else "signals.analysis_by_template"
            source_label = QLabel(self.tr_.tr(key))
            source_label.setProperty("role", "muted")
            left.addWidget(source_label)
        layout.addLayout(left)
        layout.addStretch(1)

        direction = str(self._signal.get("direction", "WAIT")).upper()
        direction_label = QLabel(self.tr_.tr(f"signals.{direction.lower()}", direction))
        direction_font = direction_label.font()
        direction_font.setBold(True)
        direction_font.setPointSize(direction_font.pointSize() + 4)
        direction_label.setFont(direction_font)
        direction_label.setProperty(
            "role", {"LONG": "up", "SHORT": "down"}.get(direction, "muted")
        )
        layout.addWidget(direction_label)
        return frame

    # ------------------------------------------------------------------
    # کمکی
    # ------------------------------------------------------------------
    def _to_html(self, text: str) -> str:
        """
        تبدیل متن نشانه‌گذاری‌شده به HTML خوانا.

        فقط عنوان `## ...` و بندها پشتیبانی می‌شوند؛ متن ورودی از مدل
        می‌آید و نباید بتواند HTML دلخواه تزریق کند، پس همه‌چیز escape
        می‌شود.
        """
        raw = str(text or "").strip()
        if not raw:
            return f"<p style='color:#7a8296'>{html.escape(self.tr_.tr('signals.analysis_empty'))}</p>"

        direction = "rtl" if self.tr_.is_rtl else "ltr"
        align = "right" if self.tr_.is_rtl else "left"
        parts = [
            f"<div dir='{direction}' style='text-align:{align};"
            "font-size:14px;line-height:2.0;'>"
        ]
        for block in raw.split("\n\n"):
            chunk = block.strip()
            if not chunk:
                continue
            heading = re.match(r"^#{1,6}\s*(.+)$", chunk)
            if heading:
                parts.append(
                    "<h3 style='margin:16px 0 6px;color:#1f2b47;'>"
                    f"{html.escape(heading.group(1).strip())}</h3>"
                )
                continue
            escaped = html.escape(chunk).replace("\n", "<br/>")
            parts.append(f"<p style='margin:0 0 10px;'>{escaped}</p>")
        parts.append("</div>")
        return "".join(parts)

    def _copy_text(self) -> None:
        """کپی متن تحلیل در حافظهٔ سیستم."""
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(self._signal.get("analysis_text", "")))
            self.set_status(self.tr_.tr("signals.copied"))

    def _on_rerun(self) -> None:
        """درخواست اجرای دوبارهٔ تحلیل هوش مصنوعی."""
        self.set_busy(True)
        self.rerun_requested.emit(dict(self._signal))

    def set_busy(self, busy: bool) -> None:
        """
        قفل‌کردن دکمه در حین تحلیل.

        بدون این قفل، کاربر چند بار پشت‌سرهم می‌زند و چند درخواست
        موازی به مدل می‌رود — هم کند می‌شود هم سهمیه می‌سوزد.
        """
        self.rerun_button.setEnabled(not busy)
        self.rerun_button.setText(
            self.tr_.tr("signals.rerun_running") if busy
            else self.tr_.tr("signals.rerun_ai")
        )
        if busy:
            self.set_status(self.tr_.tr("signals.rerun_running"))

    def set_analysis_text(self, text: str, *, status: str = "") -> None:
        """نشاندن متن تحلیل تازه در همان پنجرهٔ باز."""
        clean = str(text or "").strip()
        self._signal["analysis_text"] = clean
        self.viewer.setHtml(
            self._to_html(clean or self.tr_.tr("signals.analysis_absent"))
        )
        self.set_busy(False)
        self.set_status(status or self.tr_.tr("signals.rerun_done"))

    def set_status(self, text: str) -> None:
        """نمایش پیام وضعیت (مثلاً مسیر فایل PDF ذخیره‌شده)."""
        self.status_label.setText(text or "")

    @property
    def analysis_text(self) -> str:
        """متن تحلیل این پنجره."""
        return str(self._signal.get("analysis_text", ""))
