"""
شبکهٔ بازچینش‌شونده.

چرا لازم شد؟
    کارت‌های انتخاب پوسته در یک `QGridLayout` با تعداد ستون **ثابت**
    چیده می‌شدند. نتیجه این بود که در پنجرهٔ بزرگ فقط دو ستون دیده
    می‌شد و فضای راست خالی می‌ماند، و در پنجرهٔ باریک همان دو ستون
    له می‌شدند. کاربر خواست «در حالت بزرگ چهارتا و در کوچک‌ترین حالت
    دوتا» باشد و مربعی‌بودن کارت‌ها هم حفظ شود.

روش کار
    این ویجت در `resizeEvent` عرض موجود را بر «کمینه عرض کارت + فاصله»
    تقسیم می‌کند و شمار ستون‌ها را میان `min_columns` و `max_columns`
    محدود می‌کند. اگر شمار ستون‌ها عوض شده باشد، فقط آن وقت دوباره
    می‌چیند — بازچینش در هر پیکسل تغییر اندازه، پرش بصری می‌سازد.

    تعداد ستون هرگز از `min_columns` کمتر نمی‌شود؛ یعنی حتی در باریک‌ترین
    حالت هم دو کارت کنار هم می‌مانند، دقیقاً همان چیزی که خواسته شد.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QSizePolicy, QWidget


class ResponsiveGrid(QWidget):
    """شبکه‌ای که شمار ستون‌هایش را بر پایهٔ عرض در دسترس عوض می‌کند."""

    def __init__(
        self,
        *,
        min_columns: int = 2,
        max_columns: int = 4,
        item_min_width: int = 150,
        spacing: int = 10,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._min_columns = max(1, int(min_columns))
        self._max_columns = max(self._min_columns, int(max_columns))
        self._item_min_width = max(40, int(item_min_width))
        self._items: list[QWidget] = []
        self._columns = 0

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(int(spacing))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

    # ------------------------------------------------------------------ API
    def add_widget(self, widget: QWidget) -> None:
        """افزودن یک آیتم به شبکه و چیدن دوبارهٔ آن."""
        self._items.append(widget)
        self._relayout(force=True)

    def set_widgets(self, widgets: list[QWidget]) -> None:
        """جایگزینی کامل آیتم‌ها."""
        self._items = list(widgets)
        self._relayout(force=True)

    def items(self) -> list[QWidget]:
        """آیتم‌های فعلی به ترتیب چیده‌شدن."""
        return list(self._items)

    def column_count(self) -> int:
        """شمار ستون‌های فعلی — برای آزمون و اشکال‌زدایی."""
        return self._columns

    def columns_for_width(self, width: int) -> int:
        """
        شمار ستون‌های مناسب برای یک عرض مشخص.

        جدا از `resizeEvent` نوشته شده تا بدون نمایش واقعی پنجره هم
        بتوان رفتار رسپانسیو را آزمود.
        """
        spacing = self._grid.spacing()
        usable = max(0, int(width))
        # هر ستون به اندازهٔ کمینه‌عرض آیتم جا می‌خواهد؛ n ستون یعنی
        # n آیتم به‌علاوهٔ n-1 فاصله.
        fits = (usable + spacing) // (self._item_min_width + spacing)
        return max(self._min_columns, min(self._max_columns, int(fits)))

    # -------------------------------------------------------------- درونی
    def _relayout(self, *, force: bool = False) -> None:
        """چیدن دوبارهٔ آیتم‌ها در شمار ستون جاری."""
        columns = self.columns_for_width(self.width() or self.sizeHint().width())
        if columns == self._columns and not force:
            return
        self._columns = columns

        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)

        for index, widget in enumerate(self._items):
            widget.setParent(self)
            widget.show()
            self._grid.addWidget(widget, index // columns, index % columns)

        # ستون‌ها باید هم‌عرض بمانند وگرنه کارت آخرِ ردیف ناقص کش می‌آید
        # و مربعی‌بودن به هم می‌خورد.
        for column in range(self._grid.columnCount()):
            self._grid.setColumnStretch(column, 1 if column < columns else 0)

    def minimumSizeHint(self):  # noqa: N802 - نام Qt
        """
        کمینه‌پهنا بر پایهٔ **کمترین** شمار ستون، نه شمار فعلی.

        این نکته ظریف ولی تعیین‌کننده است: `QGridLayout` کمینه‌اندازه‌اش
        را از چیدمان فعلی می‌گیرد. وقتی شبکه چهارستونی است، کمینه‌پهنای
        چهار کارت را اعلام می‌کند و والد اجازه نمی‌دهد باریک‌تر شود —
        یعنی بازچینش هرگز رخ نمی‌دهد و ستون‌ها روی ۴ قفل می‌مانند.

        با اعلام کمینهٔ دوستونی، ویجت می‌تواند باریک شود، `resizeEvent`
        اجرا می‌شود و شمار ستون‌ها واقعاً کم می‌شود.
        """
        hint = super().minimumSizeHint()
        spacing = self._grid.spacing()
        # کف بر پایهٔ پهن‌ترین آیتم حساب می‌شود، نه `item_min_width`
        # تنها: اگر کارتی خودش کمینه‌پهنای بزرگ‌تری اعلام کند، شبکه
        # نمی‌تواند از آن باریک‌تر شود و ادعای دروغ فقط باعث بریدن
        # محتوا می‌شد.
        widest = max(
            [self._item_min_width]
            + [w.minimumSizeHint().width() for w in self._items]
            + [w.minimumWidth() for w in self._items]
        )
        floor = widest * self._min_columns + spacing * (self._min_columns - 1)
        hint.setWidth(min(hint.width(), floor))
        return hint

    def sizeHint(self):  # noqa: N802 - نام Qt
        """اندازهٔ پیشنهادی هم نباید شبکه را به عرض چهارستونی بچسباند."""
        hint = super().sizeHint()
        hint.setWidth(max(self.minimumSizeHint().width(), hint.width()))
        return hint

    def resizeEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """بازچینش هنگام تغییر اندازهٔ پنجره."""
        super().resizeEvent(event)
        self._relayout()


__all__ = ["ResponsiveGrid"]
