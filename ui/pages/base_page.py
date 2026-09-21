"""
کلاس پایه صفحات.

هر صفحه باید بتواند متن‌های خود را هنگام تغییر زبان بازسازی کند؛ به همین
دلیل متد `retranslate` اجباری است. این تضمین می‌کند تغییر زبان در زمان
اجرا واقعاً کار کند و رشته‌ای جا نماند.
"""

from __future__ import annotations

from abc import abstractmethod

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from localization import Translator
from ui.widgets import HeaderBar
from ui.widgets.common import center_numeric_inputs
from ui.widgets.table_toolbar import attach_table_toolbars


class BasePage(QWidget):
    """پایه مشترک همه صفحات."""

    #: کلید ترجمه عنوان صفحه
    title_key: str = ""
    #: کلید ترجمه توضیح صفحه
    subtitle_key: str = ""

    #: آیا محتوای صفحه در ناحیهٔ پیمایش عمودی قرار بگیرد؟
    #:
    #: صفحه‌ای که مجموع حداقل‌ ارتفاع بخش‌هایش از ارتفاع پنجره بیشتر
    #: می‌شود، بدون پیمایش محتوایش را له می‌کند: جدول‌ها به چند پیکسل
    #: می‌رسند و متن‌های چندخطی بریده می‌شوند. چنین صفحه‌ای باید این را
    #: `True` کند. سرآیند بیرون از ناحیهٔ پیمایش می‌ماند تا عنوان صفحه
    #: همیشه دیده شود.
    scrollable: bool = False

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tr_ = translator

        self.header = HeaderBar(self.tr_.tr(self.title_key), self.tr_.tr(self.subtitle_key) if self.subtitle_key else "")

        if self.scrollable:
            # چیدمان بیرونی فقط سرآیند و ناحیهٔ پیمایش را نگه می‌دارد؛
            # `layout_root()` همچنان چیدمان محتواست، پس زیرکلاس‌ها و
            # کدی که از بیرون به صفحه وصل می‌شود تغییری نمی‌بینند.
            outer = QVBoxLayout(self)
            outer.setContentsMargins(18, 16, 18, 16)
            outer.setSpacing(12)
            outer.addWidget(self.header)

            self._scroll = QScrollArea()
            self._scroll.setWidgetResizable(True)
            self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            self._scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            body = QWidget()
            self._root = QVBoxLayout(body)
            self._root.setContentsMargins(0, 0, 0, 0)
            self._root.setSpacing(12)
            self._scroll.setWidget(body)
            outer.addWidget(self._scroll, 1)
        else:
            self._scroll = None
            self._root = QVBoxLayout(self)
            self._root.setContentsMargins(18, 16, 18, 16)
            self._root.setSpacing(12)
            self._root.addWidget(self.header)

        self.build()

        # همهٔ ورودی‌های عددیِ ساخته‌شده در `build()` وسط‌چین می‌شوند.
        # اینجا انجام می‌شود نه در تک‌تک صفحه‌ها، چون در این حالت صفحهٔ
        # تازه‌ای که بعداً اضافه شود هم خودبه‌خود درست است و کسی یادش
        # نمی‌رود.
        center_numeric_inputs(self)

        # کنترل تمام‌صفحه روی هر جدولی که `build()` ساخته است. مانند
        # بالا اینجا انجام می‌شود تا هیچ جدولی — از جمله جدول‌هایی که
        # بعداً اضافه می‌شوند — از قلم نیفتد.
        self._table_toolbars = attach_table_toolbars(self, self.tr_)

    def table_toolbars(self) -> list:
        """نوارهای ابزار جدول‌های این صفحه (برای ترجمهٔ دوباره و تست)."""
        return list(getattr(self, "_table_toolbars", []))

    def layout_root(self) -> QVBoxLayout:
        """چیدمان اصلی صفحه برای افزودن محتوا."""
        return self._root

    @abstractmethod
    def build(self) -> None:
        """ساخت محتوای صفحه (در زیرکلاس‌ها پیاده‌سازی می‌شود)."""

    def retranslate(self) -> None:
        """
        بازسازی متن‌ها پس از تغییر زبان.

        زیرکلاس‌ها باید این متد را فراخوانی کرده و متن‌های خود را نیز
        به‌روزرسانی کنند.
        """
        self.header.set_texts(
            self.tr_.tr(self.title_key),
            self.tr_.tr(self.subtitle_key) if self.subtitle_key else "",
        )
        for toolbar in getattr(self, "_table_toolbars", []):
            toolbar.retranslate()

    def on_activated(self) -> None:
        """
        هنگام باز شدن صفحه فراخوانی می‌شود.

        صفحات سنگین می‌توانند بارگذاری داده را تا این لحظه به تأخیر
        بیندازند تا شروع برنامه سریع بماند.
        """
