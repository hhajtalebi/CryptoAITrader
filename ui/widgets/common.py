"""
ویجت‌های پایه مشترک.

هدف: جلوگیری از تکرار کد چیدمان در صفحات (اصل DRY) و یکدست ماندن ظاهر.
همه متن‌های ورودی این ویجت‌ها باید از پیش ترجمه شده باشند؛ خود ویجت‌ها
هیچ رشته ثابتی تولید نمی‌کنند.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,    QTableWidget,
)

from ui.widgets.charts_mini import ConfidenceRing


def make_title(text: str, role: str = "title") -> QLabel:
    """ساخت برچسب عنوان با نقش مشخص (برای اعمال سبک از QSS)."""
    label = QLabel(text)
    label.setProperty("role", role)
    return label


def make_button(
    text: str,
    *,
    primary: bool = False,
    checkable: bool = False,
    role: str = "",
) -> QPushButton:
    """
    ساخت دکمه با سبک استاندارد برنامه.

    `role` نقش رنگی دلخواه است (primary, success, danger, ghost) و بر
    `primary` اولویت دارد.
    """
    button = QPushButton(text)
    resolved = role or ("primary" if primary else "")
    if resolved:
        button.setProperty("role", resolved)
    button.setCheckable(checkable)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class RefreshButton(QPushButton):
    """
    دکمه‌ای که کار کردنش را نشان می‌دهد.

    کاربر گزارش داد دکمه‌های تازه‌سازی «انگار کار نمی‌کنند»: کلیک می‌شد و
    هیچ اتفاق دیدنی نمی‌افتاد، چون داده در پس‌زمینه می‌آمد و اگر هم عوض
    نمی‌شد، هیچ نشانه‌ای از تلاش برنامه دیده نمی‌شد.

    این دکمه سه حالت دارد:
        • عادی      : متن اصلی
        • مشغول     : غیرفعال + متن «در حال…» (کاربر می‌فهمد کلیکش رسید)
        • انجام شد  : علامت ✓ برای چند ثانیه، سپس بازگشت به عادی

    مثال:
        button = RefreshButton("تازه‌سازی", busy_text="در حال…", done_text="انجام شد")
        button.start_busy()
        button.finish_busy(success=True)
    """

    #: مدت نمایش حالت «انجام شد» بر حسب میلی‌ثانیه
    DONE_DURATION = 1600

    def __init__(
        self,
        text: str,
        *,
        busy_text: str = "",
        done_text: str = "",
        primary: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._idle_text = text
        self._busy_text = busy_text or text
        self._done_text = done_text or text
        if primary:
            self.setProperty("role", "primary")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._restore)

    def set_texts(self, idle: str, busy: str = "", done: str = "") -> None:
        """به‌روزرسانی متن‌ها پس از تغییر زبان."""
        self._idle_text = idle
        self._busy_text = busy or idle
        self._done_text = done or idle
        if not self._reset_timer.isActive() and self.isEnabled():
            self.setText(self._idle_text)

    def start_busy(self) -> None:
        """ورود به حالت مشغول."""
        self._reset_timer.stop()
        self.setEnabled(False)
        self.setText(self._busy_text)

    def finish_busy(self, *, success: bool = True) -> None:
        """
        خروج از حالت مشغول.

        در حالت موفق، تأیید کوتاهی نشان داده می‌شود تا کاربر مطمئن شود
        کار انجام شد — حتی وقتی داده تغییری نکرده باشد.
        """
        self.setEnabled(True)
        if success:
            self.setText(f"✓ {self._done_text}")
            self._reset_timer.start(self.DONE_DURATION)
        else:
            self.setText(self._idle_text)

    def _restore(self) -> None:
        """بازگشت به متن عادی."""
        self.setText(self._idle_text)


class Card(QFrame):
    """
    کارت محتوا با عنوان اختیاری.

    ساختار پایه همه بخش‌های صفحات است تا چیدمان یکدست بماند.
    """

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 12, 16, 12)
        self._layout.setSpacing(9)

        self.title_label: QLabel | None = None
        if title:
            self.title_label = make_title(title, "subtitle")
            self._layout.addWidget(self.title_label)

    def body(self) -> QVBoxLayout:
        """چیدمان داخلی کارت برای افزودن محتوا."""
        return self._layout

    def add(self, widget: QWidget) -> QWidget:
        """افزودن ویجت به بدنه کارت."""
        self._layout.addWidget(widget)
        return widget

    def set_title(self, text: str) -> None:
        """به‌روزرسانی عنوان (هنگام تغییر زبان)."""
        if self.title_label is not None:
            self.title_label.setText(text)


class KeyValueRow(QWidget):
    """سطر «برچسب: مقدار» برای نمایش جزئیات."""

    def __init__(self, key: str, value: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.key_label = QLabel(key)
        self.key_label.setProperty("role", "muted")
        self.value_label = QLabel(value)
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.value_label.setWordWrap(True)

        layout.addWidget(self.key_label)
        layout.addStretch(1)
        layout.addWidget(self.value_label)

    def set_value(self, value: str, role: str = "") -> None:
        """به‌روزرسانی مقدار و نقش رنگی آن (bullish/bearish/neutral)."""
        self.value_label.setText(value)
        self.value_label.setProperty("role", role)
        self.value_label.style().unpolish(self.value_label)
        self.value_label.style().polish(self.value_label)

    def set_key(self, key: str) -> None:
        """به‌روزرسانی برچسب هنگام تغییر زبان."""
        self.key_label.setText(key)


class StatusPill(QLabel):
    """
    نشانگر وضعیت اتصال.

    رنگ از روی نقش تعیین می‌شود تا با تغییر پوسته هماهنگ بماند.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("role", "muted")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def set_status(self, text: str, role: str = "neutral") -> None:
        """به‌روزرسانی متن و رنگ وضعیت."""
        self.setText(text)
        self.setProperty("role", role)
        self.style().unpolish(self)
        self.style().polish(self)


class SignalCard(Card):
    """
    کارت نمایش یک سیگنال.

    عمداً یادداشت «اطمینان = هم‌سویی عوامل» همیشه نمایش داده می‌شود تا
    کاربر آن را با احتمال سود اشتباه نگیرد.
    """

    def __init__(self, labels: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(labels.get("title", ""), parent)
        self._labels = labels
        self._rows: dict[str, KeyValueRow] = {}

        header = QHBoxLayout()
        self.symbol_label = make_title("—", "title")
        self.direction_label = make_title("—", "neutral")
        header.addWidget(self.symbol_label)
        header.addStretch(1)
        header.addWidget(self.direction_label)
        self._layout.addLayout(header)

        # بدنه: حلقهٔ اطمینان در یک سو، ردیف‌های عددی در سوی دیگر —
        # مطابق تصاویر مرجع که درصد اطمینان را برجسته نشان می‌دهند.
        body = QHBoxLayout()
        body.setSpacing(18)

        ring_box = QVBoxLayout()
        ring_box.setSpacing(4)
        self.confidence_ring = ConfidenceRing()
        self.confidence_ring.set_value(0, label="—", caption=labels.get("confidence", ""))
        ring_box.addWidget(self.confidence_ring, 0, Qt.AlignmentFlag.AlignCenter)
        ring_box.addStretch(1)
        body.addLayout(ring_box)

        rows_box = QVBoxLayout()
        rows_box.setSpacing(2)
        for key in ("entry", "stop_loss", "take_profit", "risk_reward", "leverage", "confidence"):
            row = KeyValueRow(labels.get(key, key))
            self._rows[key] = row
            rows_box.addWidget(row)
        rows_box.addStretch(1)
        body.addLayout(rows_box, 1)
        self._layout.addLayout(body)

        self.note_label = QLabel(labels.get("confidence_note", ""))
        self.note_label.setProperty("role", "muted")
        self.note_label.setWordWrap(True)
        self._layout.addWidget(self.note_label)

        # پیش‌بینی تایم‌فریم بعدی.
        #
        # کاربر خواست بداند «۱۵ دقیقه، یک ساعت و چهار ساعت بعد چه
        # می‌شود». پاسخ صادقانه یک بازه است نه یک عدد؛ بنابراین اینجا
        # کف و سقف محتمل نشان داده می‌شود، نه یک قیمت قطعی.
        self.forecast_title = QLabel(labels.get("forecast", ""))
        self.forecast_title.setProperty("role", "subtitle")
        self.forecast_title.hide()
        self._layout.addWidget(self.forecast_title)

        self.forecast_label = QLabel("")
        self.forecast_label.setProperty("role", "muted")
        self.forecast_label.setWordWrap(True)
        self.forecast_label.setTextFormat(Qt.TextFormat.RichText)
        self.forecast_label.hide()
        self._layout.addWidget(self.forecast_label)

    def apply_theme(self, theme: Any) -> None:
        """اعمال پوسته روی حلقهٔ اطمینان که خودش نقاشی می‌شود."""
        self.confidence_ring.apply_theme(theme)

    def set_labels(self, labels: dict[str, str]) -> None:
        """
        به‌روزرسانی برچسب‌ها هنگام تغییر زبان.

        بدون این، عنوان ردیف‌ها به زبان قبلی می‌ماند.
        """
        self._labels = labels
        self.set_title(labels.get("title", ""))
        for key, row in self._rows.items():
            row.set_key(labels.get(key, key))
        self.note_label.setText(labels.get("confidence_note", ""))
        self.forecast_title.setText(labels.get("forecast", ""))

    def show_signal(self, payload: dict[str, Any]) -> None:
        """
        نمایش داده یک سیگنال.

        payload همان خروجی `TradingSignal.to_dict()` است.
        """
        direction = str(payload.get("direction", "WAIT")).upper()
        role = {"LONG": "bullish", "SHORT": "bearish"}.get(direction, "neutral")

        self.symbol_label.setText(str(payload.get("symbol", "—")))
        self.direction_label.setText(self._labels.get(direction.lower(), direction))
        self.direction_label.setProperty("role", role)
        self.direction_label.style().unpolish(self.direction_label)
        self.direction_label.style().polish(self.direction_label)

        entry_min, entry_max = payload.get("entry_min"), payload.get("entry_max")
        entry_text = (
            f"{entry_min:,.6g} – {entry_max:,.6g}" if entry_min and entry_max else "—"
        )
        take_profits = payload.get("take_profits") or []

        self._rows["entry"].set_value(entry_text)
        self._rows["stop_loss"].set_value(
            f"{payload['stop_loss']:,.6g}" if payload.get("stop_loss") else "—", "bearish" if payload.get("stop_loss") else ""
        )
        self._rows["take_profit"].set_value(
            " / ".join(f"{t:,.6g}" for t in take_profits) if take_profits else "—",
            "bullish" if take_profits else "",
        )
        self._rows["risk_reward"].set_value(
            f"{payload['risk_reward']:.2f}" if payload.get("risk_reward") else "—"
        )
        self._rows["leverage"].set_value(f"×{payload.get('leverage', 1)}")
        confidence = payload.get("confidence", 0) or 0
        self._rows["confidence"].set_value(f"{confidence}%")
        self.confidence_ring.set_value(
            confidence,
            label=f"{confidence}%",
            caption=self._labels.get("confidence", ""),
        )
        self._render_forecast(payload.get("forecast") or [])

    def _render_forecast(self, horizons: list[dict[str, Any]]) -> None:
        """
        نمایش بازهٔ محتمل قیمت برای افق‌های بعدی.

        اگر پیش‌بینی در دسترس نباشد، بخش کاملاً پنهان می‌شود؛ جای خالی
        بهتر از عدد ساختگی است.
        """
        if not horizons:
            self.forecast_title.hide()
            self.forecast_label.hide()
            return

        arrow = {"bullish": "▲", "bearish": "▼", "neutral": "◆"}
        lines: list[str] = []
        for item in horizons:
            try:
                horizon = str(item.get("horizon", "?"))
                lower = float(item.get("lower", 0.0))
                upper = float(item.get("upper", 0.0))
                bias = str(item.get("bias", "neutral"))
                probability = int(item.get("probability", 0))
            except (TypeError, ValueError):
                continue
            lines.append(
                f"{arrow.get(bias, '◆')} <b>{horizon}</b>: "
                f"<span dir='ltr'>{lower:,.6g} … {upper:,.6g}</span> "
                f"({probability}%)"
            )

        if not lines:
            self.forecast_title.hide()
            self.forecast_label.hide()
            return

        self.forecast_label.setText("<br/>".join(lines))
        self.forecast_title.show()
        self.forecast_label.show()


class HeaderBar(QWidget):
    """نوار بالای هر صفحه: عنوان، توضیح و دکمه‌های کنش."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title_label = make_title(title, "title")
        self.subtitle_label = make_title(subtitle, "subtitle")
        texts.addWidget(self.title_label)
        if subtitle:
            texts.addWidget(self.subtitle_label)
        else:
            self.subtitle_label.hide()

        layout.addLayout(texts)
        layout.addStretch(1)
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(7)
        layout.addLayout(self.actions_layout)

    def add_action(self, widget: QWidget) -> QWidget:
        """افزودن دکمه یا کنترل به سمت کنش‌های نوار."""
        self.actions_layout.addWidget(widget)
        return widget

    def set_texts(self, title: str, subtitle: str = "") -> None:
        """به‌روزرسانی متن‌ها هنگام تغییر زبان."""
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setVisible(bool(subtitle))


def configure_table(table: "QTableWidget", stretch_column: int = -1) -> "QTableWidget":
    """
    تنظیم یکدست سرستون‌های جدول.

    ستون‌ها به اندازه محتوا کشیده می‌شوند و فضای باقی‌مانده به ستون
    انتخابی می‌رسد. بدون این کار عنوان‌های بلند (مثل «Risk / Reward»)
    بریده می‌شوند و کاربر نمی‌فهمد ستون چیست.
    """
    from PySide6.QtWidgets import QHeaderView

    header = table.horizontalHeader()
    header.setMinimumSectionSize(90)
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if 0 <= stretch_column < table.columnCount():
        header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)
    else:
        header.setStretchLastSection(True)
    table.setWordWrap(False)
    return table


#: ارتفاع ردیفی که دکمه دارد. خانه‌های جدول در شیوه‌نامه
#: `padding: 8px 6px` می‌گیرند؛ یعنی از یک ردیف ۳۰ پیکسلی فقط ۱۴ پیکسل
#: به ویجت درون خانه می‌رسد در حالی که یک دکمه دست‌کم ۲۸ پیکسل
#: می‌خواهد. نتیجه‌اش دکمه‌ای بود که تا ۱۲ پیکسل له می‌شد و متنش
#: دیده نمی‌شد — کاربر گزارش داد «دکمه‌ها خراب است».
#:
#: ۵۴ و نه ۴۶: با قلم فارسیِ جاسازی‌شدهٔ برنامه (وزیرمتن) که متریکِ
#: بزرگ‌تری از قلم جانشینِ محیط آزمون دارد، sizeHint دکمه ۳۳ پیکسل
#: است؛ ۴۶ − ۲×۸ پدینگ = ۳۰ پیکسل فضای ویجت و دکمه ۵ پیکسل له
#: می‌شد. آزمون v172 این را فقط وقتی می‌بیند که قلم واقعی بار شده
#: باشد — همان حالتی که هر کاربر واقعی دارد.
BUTTON_ROW_HEIGHT = 54

#: عرض ستونی که دکمه دارد
BUTTON_COLUMN_WIDTH = 150


def configure_button_column(
    table: "QTableWidget",
    column: int,
    *,
    width: int = BUTTON_COLUMN_WIDTH,
    row_height: int = BUTTON_ROW_HEIGHT,
) -> "QTableWidget":
    """
    آماده‌سازی ستونی که در هر خانه‌اش دکمه می‌نشیند.

    دو کار لازم است و فراموش‌کردن هرکدام ستون را خراب می‌کند:

    ۱. **عرض ثابت.** `ResizeToContents` عرض *آیتم* خانه را می‌سنجد نه
       ویجتی که با `setCellWidget` نشسته است؛ از نظرش خانه خالی است، پس
       ستون به کمینه می‌رسد و دکمه بریده می‌شود.

    ۲. **ارتفاع ردیف.** پدینگ خانه در شیوه‌نامه از ارتفاع ردیف کم
       می‌شود. با ارتفاع پیش‌فرض ۳۰ پیکسل، دکمه به ۱۲ پیکسل له می‌شد و
       عملاً نامرئی بود.

    بازگشتی خود جدول است تا بشود زنجیره‌ای نوشت.
    """
    from PySide6.QtWidgets import QHeaderView

    if not 0 <= column < table.columnCount():
        return table

    table.setColumnWidth(column, width)
    table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
    table.verticalHeader().setDefaultSectionSize(row_height)
    return table


def center_numeric_inputs(root: QWidget) -> int:
    """
    وسط‌چین‌کردن مقدار همهٔ ورودی‌های عددی زیرِ یک ویجت.

    چرا لازم است؟ کاربر گفت «مقدار را در این پوت‌های عددی سنتر کن».
    در چیدمان راست‌به‌چپ، `QSpinBox` عدد را به لبه می‌چسباند و چون
    دکمه‌های بالا/پایین سمت راست‌اند، عدد و فلش‌ها روی هم می‌افتند و
    ورودی شلوغ به‌نظر می‌رسد. وسط‌چینی هم این تداخل را برمی‌دارد و هم
    ظاهر همهٔ ورودی‌های عددی را یکدست می‌کند.

    چرا پیمایشی و نه تنظیم تک‌تک؟ ورودی عددی در ده‌ها جای برنامه ساخته
    می‌شود؛ تنظیم دستی یعنی فراموش‌کردن موردهای بعدی. این تابع یک بار
    پس از ساخت صفحه صدا زده می‌شود و هر ورودی تازه‌ای را هم می‌گیرد.

    بازگشتی: شمار ورودی‌هایی که تنظیم شدند (برای آزمون).
    """
    from PySide6.QtWidgets import QAbstractSpinBox

    count = 0
    for box in root.findChildren(QAbstractSpinBox):
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # دکمه‌های بالا/پایین در حالت وسط‌چین همچنان لازم‌اند، ولی
        # نمادهای اضافیِ پیش‌فرض Qt (مثل قاب دور دکمه) برداشته می‌شوند.
        box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        count += 1
    return count


# ----------------------------------------------------------------------
# جدول‌های مقاوم و ردیف واکنش‌گرا (v2.0 — صفحهٔ معاملهٔ خودکار و پیش‌بینی)
# ----------------------------------------------------------------------

def harden_table(
    table: "QTableWidget",
    *,
    min_row_height: int = 30,
    min_column_width: int = 72,
    min_table_height: int = 180,
    max_total_width: int = 2400,
) -> "QTableWidget":
    """
    مقاوم‌سازی جدول در برابر فشرده‌شدن (خواستهٔ §۹).

    قانون: جدول هرگز له نمی‌شود؛ اگر جا کم است، اسکرول عمودی و
    افقی فعال می‌شود:
      • حداقل ارتفاع ردیف و عرض ستون تضمین می‌شود
      • عرض کل جدول دست‌کم به اندازهٔ مجموع ستون‌ها می‌رسد تا
        اسکرول افقیِ صفحه کار کند، نه فشرده‌شدن ستون‌ها
      • مرتب‌سازی روشن است؛ جست‌وجو/تمام‌صفحه از TableToolbar موجود
        می‌آید (تکرار ساخته نمی‌شود)
    """
    from PySide6.QtWidgets import QAbstractItemView

    header = table.horizontalHeader()
    header.setMinimumSectionSize(min_column_width)
    header.setDefaultSectionSize(min_column_width)
    table.verticalHeader().setDefaultSectionSize(min_row_height)
    table.verticalHeader().setMinimumSectionSize(min_row_height)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSortingEnabled(True)
    table.setMinimumHeight(min_table_height)
    _fit_total_width(table, max_total_width=max_total_width)
    return table


def _fit_total_width(table: "QTableWidget", *, max_total_width: int) -> None:
    """حداقل عرض جدول = مجموع ستون‌ها (سقف‌دار) — اسکرول افقی، نه له‌شدن."""
    if table.columnCount() <= 0:
        return
    total = 0
    for column in range(table.columnCount()):
        total += max(table.columnWidth(column), table.horizontalHeader().minimumSectionSize())
    table.setMinimumWidth(min(int(total) + 24, max_total_width))


class ResponsiveRow(QWidget):
    """
    ردیف دو-پane‌ای که در عرض کم به‌صورت عمودی چیده می‌شود.

    خواستهٔ §۱۰/§۱۱: در صفحهٔ بزرگ دو ستون (خلاصه | نمودار)، در
    صفحهٔ کوچک زیر هم — بدون حذف هیچ داده‌ای.
    """

    def __init__(
        self,
        first: QWidget,
        second: QWidget,
        *,
        breakpoint: int = 1100,
        parent: QWidget | None = None,
        stretch: tuple[int, int] = (3, 2),
    ) -> None:
        super().__init__(parent)
        self._first = first
        self._second = second
        self._breakpoint = breakpoint
        self._stretch = stretch
        self._stacked: bool | None = None
        self._apply(stacked=False)

    def set_stacked(self, stacked: bool) -> None:
        """تغییر چیدمان به عمودی (True) یا افقی (False)."""
        self._apply(stacked=bool(stacked))

    def _apply(self, *, stacked: bool) -> None:
        """بازچینی بدون از دست رفتن ویجت‌ها."""
        if stacked == self._stacked:
            return
        self._stacked = stacked
        old = self.layout()
        if old is not None:
            while old.count():
                item = old.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
            QWidget().setLayout(old)  # حذف چیدمان قدیمی
        layout = QHBoxLayout(self) if not stacked else QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self._first, self._stretch[0])
        layout.addWidget(self._second, self._stretch[1])

    def reflow(self, width: int) -> None:
        """چیدمان را با عرض موجود هماهنگ کن."""
        self.set_stacked(width < self._breakpoint)


