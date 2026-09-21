"""
نمای آموزش معامله‌گری.

چرا این‌طور ساخته شده؟
    آموزش کامل، متن بلندی است. ریختن همهٔ آن در یک ستون قابل پیمایش،
    عملاً یعنی کسی آن را نمی‌خواند. اینجا فهرست فصل‌ها در یک ستون است و
    متن فصلِ انتخاب‌شده در ستون دیگر؛ به‌علاوهٔ جست‌وجو، تا کاربری که
    دنبال «حد ضرر» می‌گردد در سه ثانیه به آن برسد.

محتوا از فایل‌های ترجمه می‌آید نه از کد؛ بنابراین نسخهٔ انگلیسی و فارسی
هر دو کامل‌اند و هیچ رشته‌ای در کد سفت نشده است.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.common import make_button
from ui.widgets.controls import set_role

#: سطح دشواری هر فصل → کلید ترجمهٔ برچسب
LEVEL_KEYS = {
    "basic": "tutorial.level_basic",
    "intermediate": "tutorial.level_intermediate",
    "advanced": "tutorial.level_advanced",
}


class TutorialView(QWidget):
    """آموزش چندفصلی با فهرست، جست‌وجو و پیمایش."""

    def __init__(self, translator: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._chapters: list[dict[str, str]] = []
        self._visible: list[int] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.search = QLineEdit(self)
        self.search.setClearButtonEnabled(True)
        set_role(self.search, "search")
        self.search.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        self.chapter_list = QListWidget(splitter)
        self.chapter_list.setMinimumWidth(220)
        self.chapter_list.currentRowChanged.connect(self._on_row_changed)

        reader = QWidget(splitter)
        reader_layout = QVBoxLayout(reader)
        reader_layout.setContentsMargins(14, 0, 14, 0)
        reader_layout.setSpacing(8)

        self.level_label = QLabel("", reader)
        set_role(self.level_label, "badge")
        reader_layout.addWidget(self.level_label, 0, Qt.AlignmentFlag.AlignLeft)

        self.title_label = QLabel("", reader)
        self.title_label.setWordWrap(True)
        set_role(self.title_label, "title")
        reader_layout.addWidget(self.title_label)

        scroll = QScrollArea(reader)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.body_label = QLabel("")
        self.body_label.setWordWrap(True)
        self.body_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignJustify
        )
        self.body_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        # متن آموزشی باید فاصلهٔ سطر راحتی داشته باشد؛ متن فشرده خوانده
        # نمی‌شود. این تنها سبک درون‌خطی اینجاست و رنگی تعیین نمی‌کند تا
        # با پوسته‌ها درگیر نشود.
        self.body_label.setStyleSheet("line-height: 190%;")
        scroll.setWidget(self.body_label)
        self.body_scroll = scroll
        reader_layout.addWidget(scroll, 1)

        nav = QHBoxLayout()
        self.prev_button = make_button("", role="ghost")
        self.prev_button.clicked.connect(self.go_previous)
        self.progress_label = QLabel("", reader)
        set_role(self.progress_label, "faint")
        self.next_button = make_button("", role="ghost")
        self.next_button.clicked.connect(self.go_next)
        nav.addWidget(self.prev_button)
        nav.addStretch(1)
        nav.addWidget(self.progress_label)
        nav.addStretch(1)
        nav.addWidget(self.next_button)
        reader_layout.addLayout(nav)

        splitter.addWidget(self.chapter_list)
        splitter.addWidget(reader)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([250, 680])
        layout.addWidget(splitter, 1)

        self.reload()

    # ------------------------------------------------------------------ API
    @property
    def chapters(self) -> list[dict[str, str]]:
        """فصل‌های بارگذاری‌شده."""
        return list(self._chapters)

    def current_index(self) -> int:
        """شمارهٔ فصل فعلی در فهرست کامل (نه فهرست فیلترشده)."""
        row = self.chapter_list.currentRow()
        if 0 <= row < len(self._visible):
            return self._visible[row]
        return -1

    def select_chapter(self, key: str) -> bool:
        """باز کردن فصلی مشخص با کلیدش."""
        for index, chapter in enumerate(self._chapters):
            if chapter.get("key") == key:
                if index in self._visible:
                    self.chapter_list.setCurrentRow(self._visible.index(index))
                    return True
                return False
        return False

    def go_next(self) -> None:
        """رفتن به فصل بعدی در فهرست نمایش‌داده‌شده."""
        row = self.chapter_list.currentRow()
        if row + 1 < self.chapter_list.count():
            self.chapter_list.setCurrentRow(row + 1)

    def go_previous(self) -> None:
        """بازگشت به فصل قبلی."""
        row = self.chapter_list.currentRow()
        if row > 0:
            self.chapter_list.setCurrentRow(row - 1)

    def reload(self) -> None:
        """
        خواندن دوبارهٔ محتوا از فایل ترجمه.

        هنگام تغییر زبان صدا زده می‌شود؛ فصل فعلی تا جای ممکن حفظ
        می‌شود تا کاربر جای خودش را در آموزش گم نکند.
        """
        previous_key = ""
        index = self.current_index()
        if 0 <= index < len(self._chapters):
            previous_key = self._chapters[index].get("key", "")

        raw = self.tr_.raw("tutorial.chapters", [])
        self._chapters = [dict(item) for item in raw if isinstance(item, dict)]

        self.search.setPlaceholderText(self.tr_.tr("tutorial.search_placeholder"))
        self.prev_button.setText(self.tr_.tr("tutorial.previous"))
        self.next_button.setText(self.tr_.tr("tutorial.next"))

        self._apply_filter(self.search.text())
        if previous_key:
            self.select_chapter(previous_key)

    # -------------------------------------------------------------- درونی
    def _apply_filter(self, needle: str) -> None:
        """
        ساخت دوبارهٔ فهرست بر پایهٔ عبارت جست‌وجو.

        جست‌وجو هم در عنوان و هم در متن انجام می‌شود، چون کاربر معمولاً
        دنبال یک اصطلاح است نه نام فصل.
        """
        text = (needle or "").strip().casefold()
        self.chapter_list.blockSignals(True)
        self.chapter_list.clear()
        self._visible = []

        for index, chapter in enumerate(self._chapters):
            haystack = f"{chapter.get('title', '')}\n{chapter.get('body', '')}".casefold()
            if text and text not in haystack:
                continue
            item = QListWidgetItem(chapter.get("title", ""))
            item.setToolTip(chapter.get("title", ""))
            self.chapter_list.addItem(item)
            self._visible.append(index)

        self.chapter_list.blockSignals(False)

        if self._visible:
            self.chapter_list.setCurrentRow(0)
        else:
            self._show_empty()

    def _show_empty(self) -> None:
        """حالت «چیزی پیدا نشد» — کاربر نباید با صفحهٔ سفید روبه‌رو شود."""
        self.level_label.setText("")
        self.level_label.setVisible(False)
        self.title_label.setText(self.tr_.tr("tutorial.no_results"))
        self.body_label.setText("")
        self.progress_label.setText("")
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)

    def _on_row_changed(self, row: int) -> None:
        """نمایش فصل انتخاب‌شده."""
        if not (0 <= row < len(self._visible)):
            return
        chapter = self._chapters[self._visible[row]]

        level_key = LEVEL_KEYS.get(str(chapter.get("level", "")), "")
        self.level_label.setText(self.tr_.tr(level_key) if level_key else "")
        self.level_label.setVisible(bool(level_key))

        self.title_label.setText(chapter.get("title", ""))
        self.body_label.setText(chapter.get("body", ""))
        self.body_scroll.verticalScrollBar().setValue(0)

        self.progress_label.setText(
            self.tr_.tr(
                "tutorial.progress",
                current=self._localised_number(row + 1),
                total=self._localised_number(len(self._visible)),
            )
        )
        self.prev_button.setEnabled(row > 0)
        self.next_button.setEnabled(row + 1 < len(self._visible))

    def _localised_number(self, value: int) -> str:
        """عدد با ارقام زبان جاری."""
        to_persian = getattr(self.tr_, "to_persian_digits", None)
        if getattr(self.tr_, "is_rtl", False) and callable(to_persian):
            return str(to_persian(str(value)))
        return str(value)


__all__ = ["LEVEL_KEYS", "TutorialView"]
