"""
چیدمان قابل جابه‌جایی صفحات.

کاربر خواست بتواند ترتیب کارت‌های داشبورد و دیگر صفحه‌ها را خودش تعیین
کند. این ماژول یک ظرف می‌دهد که بخش‌های نام‌دار را نگه می‌دارد و در
«حالت چیدمان» اجازهٔ جابه‌جایی و پنهان‌کردنشان را می‌دهد.

چرا دکمه به‌جای کشیدن و رها کردن؟
    کشیدن و رها کردن روی کارت‌هایی که خودشان جدول و نمودار تعاملی
    دارند، با رویدادهای همان اجزا تداخل می‌کند و کاربر هنگام تلاش برای
    انتخاب یک ردیف، ناخواسته کارت را جابه‌جا می‌کند. دکمه‌های صریح، که
    فقط در حالت چیدمان دیده می‌شوند، هم قابل‌اعتمادترند و هم با صفحه‌کلید
    کار می‌کنند.

ترتیب انتخابی کاربر در ترجیحات او ذخیره می‌شود، پس بین اجراها می‌ماند و
هرگز بازنویسی نمی‌گردد.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.common import make_button
from ui.widgets.controls import set_role

#: جداکنندهٔ ترتیب ذخیره‌شده در ترجیحات
ORDER_SEPARATOR = ","

#: پیشوند بخش پنهان‌شده در رشتهٔ ترتیب
HIDDEN_MARK = "-"


class LayoutBlock(QWidget):
    """
    یک بخش جابه‌جاشدنی: محتوا به‌علاوهٔ نوار کنترل چیدمان.

    نوار کنترل فقط در حالت چیدمان دیده می‌شود؛ در حالت عادی کاربر هیچ
    تفاوتی با قبل نمی‌بیند.
    """

    move_up_requested = Signal(str)
    move_down_requested = Signal(str)
    visibility_toggled = Signal(str, bool)

    def __init__(
        self,
        key: str,
        title: str,
        content: QWidget,
        translator: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._title = title
        self.tr_ = translator
        self.content = content
        self._content_visible = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.bar = QWidget(self)
        bar_layout = QHBoxLayout(self.bar)
        bar_layout.setContentsMargins(8, 3, 8, 3)
        bar_layout.setSpacing(6)

        self.title_label = QLabel(title, self.bar)
        set_role(self.title_label, "badge")
        bar_layout.addWidget(self.title_label)
        bar_layout.addStretch(1)

        self.visible_button = make_button("", role="ghost", checkable=True)
        self.visible_button.setChecked(True)
        self.visible_button.setFixedWidth(46)
        self.visible_button.toggled.connect(self._on_visible_toggled)
        bar_layout.addWidget(self.visible_button)

        self.up_button = make_button("▲", role="ghost")
        self.up_button.setFixedWidth(34)
        self.up_button.clicked.connect(lambda: self.move_up_requested.emit(self._key))
        bar_layout.addWidget(self.up_button)

        self.down_button = make_button("▼", role="ghost")
        self.down_button.setFixedWidth(34)
        self.down_button.clicked.connect(lambda: self.move_down_requested.emit(self._key))
        bar_layout.addWidget(self.down_button)

        self.bar.setVisible(False)
        layout.addWidget(self.bar)
        layout.addWidget(content, 1)

        self.retranslate()

    # ------------------------------------------------------------------ API
    @property
    def key(self) -> str:
        """شناسهٔ پایدار این بخش."""
        return self._key

    @property
    def content_visible(self) -> bool:
        """آیا کاربر این بخش را نمایان گذاشته است؟"""
        return self._content_visible

    def set_arrange_mode(self, enabled: bool) -> None:
        """نمایش یا پنهان‌کردن نوار کنترل چیدمان."""
        self.bar.setVisible(bool(enabled))
        # بخش پنهان باید در حالت چیدمان دیده شود، وگرنه کاربر راهی برای
        # برگرداندنش ندارد.
        if enabled:
            self.setVisible(True)
            self.content.setVisible(self._content_visible)
        else:
            self.setVisible(self._content_visible)

    def set_content_visible(self, visible: bool, *, emit: bool = True) -> None:
        """تعیین نمایان‌بودن محتوا."""
        value = bool(visible)
        self._content_visible = value
        self.visible_button.blockSignals(True)
        self.visible_button.setChecked(value)
        self.visible_button.blockSignals(False)
        self.content.setVisible(value)
        if not self.bar.isVisible():
            self.setVisible(value)
        self.retranslate()
        if emit:
            self.visibility_toggled.emit(self._key, value)

    def set_edges(self, *, first: bool, last: bool) -> None:
        """غیرفعال‌کردن دکمه‌های بی‌اثر در ابتدا و انتهای فهرست."""
        self.up_button.setEnabled(not first)
        self.down_button.setEnabled(not last)

    def retranslate(self) -> None:
        """بازسازی متن‌ها و راهنماها."""
        self.title_label.setText(self._title)
        self.up_button.setToolTip(self.tr_.tr("layout.move_up"))
        self.down_button.setToolTip(self.tr_.tr("layout.move_down"))
        key = "layout.hide" if self._content_visible else "layout.show"
        # نشانه‌های هندسی و نه ایموجی: قلم‌های همراه برنامه ایموجی
        # ندارند و دکمه خالی دیده می‌شود.
        self.visible_button.setText("●" if self._content_visible else "○")
        self.visible_button.setToolTip(self.tr_.tr(key))

    def set_title(self, title: str) -> None:
        """به‌روزرسانی عنوان هنگام تغییر زبان."""
        self._title = title
        self.title_label.setText(title)

    # -------------------------------------------------------------- درونی
    def _on_visible_toggled(self, checked: bool) -> None:
        """کلیک روی کلید نمایش."""
        self.set_content_visible(checked)


class ArrangeableContainer(QWidget):
    """
    ظرفی که بخش‌هایش را می‌توان جابه‌جا و پنهان کرد.

    نمونه‌سازی:
        box = ArrangeableContainer(translator)
        box.add_block("market", "بازار", market_card)
        box.set_order("signals,market")
    """

    #: ترتیب یا نمایانی بخش‌ها عوض شد (رشتهٔ قابل ذخیره)
    layout_changed = Signal(str)

    def __init__(self, translator: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._blocks: dict[str, LayoutBlock] = {}
        self._order: list[str] = []
        self._arrange_mode = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(12)

    # ------------------------------------------------------------------ API
    @property
    def order(self) -> list[str]:
        """ترتیب فعلی بخش‌ها."""
        return list(self._order)

    @property
    def blocks(self) -> dict[str, LayoutBlock]:
        """بخش‌های ثبت‌شده."""
        return dict(self._blocks)

    @property
    def arrange_mode(self) -> bool:
        """آیا حالت چیدمان فعال است؟"""
        return self._arrange_mode

    def add_block(self, key: str, title: str, content: QWidget, *, stretch: int = 0) -> LayoutBlock:
        """افزودن یک بخش تازه به انتهای چیدمان."""
        block = LayoutBlock(key, title, content, self.tr_, self)
        block.move_up_requested.connect(self.move_up)
        block.move_down_requested.connect(self.move_down)
        block.visibility_toggled.connect(self._on_visibility_changed)
        self._blocks[key] = block
        self._order.append(key)
        self._layout.addWidget(block, stretch)
        self._sync_edges()
        return block

    def set_arrange_mode(self, enabled: bool) -> None:
        """روشن/خاموش کردن حالت چیدمان برای همهٔ بخش‌ها."""
        self._arrange_mode = bool(enabled)
        for block in self._blocks.values():
            block.set_arrange_mode(self._arrange_mode)
        self._sync_edges()

    def move_up(self, key: str) -> bool:
        """یک پله بالا بردن یک بخش."""
        return self._move(key, -1)

    def move_down(self, key: str) -> bool:
        """یک پله پایین بردن یک بخش."""
        return self._move(key, 1)

    def serialise(self) -> str:
        """
        ترتیب و نمایانی فعلی به رشته‌ای قابل ذخیره.

        بخش پنهان با پیشوند «-» مشخص می‌شود؛ یعنی یک رشته هم ترتیب و هم
        نمایانی را نگه می‌دارد و نیازی به دو کلید ترجیح نیست.
        """
        parts = []
        for key in self._order:
            block = self._blocks[key]
            parts.append(key if block.content_visible else f"{HIDDEN_MARK}{key}")
        return ORDER_SEPARATOR.join(parts)

    def apply_state(self, state: str) -> None:
        """
        بازگرداندن ترتیب و نمایانی ذخیره‌شده.

        بخش‌های ناشناخته در رشته نادیده گرفته می‌شوند و بخش‌هایی که در
        رشته نیستند به انتها می‌روند؛ بنابراین افزودن کارت تازه در
        نسخه‌های بعدی، چیدمان ذخیره‌شدهٔ کاربر را نمی‌شکند.
        """
        text = str(state or "").strip()
        if not text:
            return

        seen: list[str] = []
        hidden: set[str] = set()
        for token in text.split(ORDER_SEPARATOR):
            item = token.strip()
            if not item:
                continue
            is_hidden = item.startswith(HIDDEN_MARK)
            key = item[1:] if is_hidden else item
            if key not in self._blocks or key in seen:
                continue
            seen.append(key)
            if is_hidden:
                hidden.add(key)

        # بخش‌های تازه‌ای که در ترجیح ذخیره‌شده نبوده‌اند
        for key in self._order:
            if key not in seen:
                seen.append(key)

        self._order = seen
        self._relayout()
        for key, block in self._blocks.items():
            block.set_content_visible(key not in hidden, emit=False)
        self._sync_edges()

    def reset(self, default_order: list[str] | None = None) -> None:
        """بازگرداندن چیدمان به حالت اولیه و نمایان‌کردن همه."""
        if default_order:
            known = [key for key in default_order if key in self._blocks]
            known += [key for key in self._blocks if key not in known]
            self._order = known
            self._relayout()
        for block in self._blocks.values():
            block.set_content_visible(True, emit=False)
        self._sync_edges()
        self.layout_changed.emit(self.serialise())

    def retranslate(self) -> None:
        """بازسازی متن‌های کنترل‌ها."""
        for block in self._blocks.values():
            block.retranslate()

    # -------------------------------------------------------------- درونی
    def _move(self, key: str, delta: int) -> bool:
        """جابه‌جایی یک بخش و اعلام تغییر."""
        if key not in self._order:
            return False
        index = self._order.index(key)
        target = index + delta
        if not (0 <= target < len(self._order)):
            return False
        self._order[index], self._order[target] = self._order[target], self._order[index]
        self._relayout()
        self._sync_edges()
        self.layout_changed.emit(self.serialise())
        return True

    def _relayout(self) -> None:
        """
        چیدن دوبارهٔ ویجت‌ها بر پایهٔ ترتیب فعلی.

        ویجت‌ها از چیدمان برداشته و به ترتیب تازه برگردانده می‌شوند؛
        خودِ شیء ویجت دست‌نخورده می‌ماند، پس داده و وضعیتش (ردیف‌های
        انتخاب‌شده، موقعیت پیمایش) از بین نمی‌رود.
        """
        stretches = {}
        for key in self._blocks:
            index = self._layout.indexOf(self._blocks[key])
            if index >= 0:
                stretches[key] = self._layout.stretch(index)

        for block in self._blocks.values():
            self._layout.removeWidget(block)
        for key in self._order:
            self._layout.addWidget(self._blocks[key], stretches.get(key, 0))

    def _sync_edges(self) -> None:
        """به‌روزرسانی فعال‌بودن دکمه‌های بالا/پایین."""
        for index, key in enumerate(self._order):
            self._blocks[key].set_edges(
                first=index == 0, last=index == len(self._order) - 1
            )

    def _on_visibility_changed(self, _key: str, _visible: bool) -> None:
        """اعلام تغییر نمایانی برای ذخیره‌شدن."""
        self.layout_changed.emit(self.serialise())


__all__ = ["HIDDEN_MARK", "ORDER_SEPARATOR", "ArrangeableContainer", "LayoutBlock"]
