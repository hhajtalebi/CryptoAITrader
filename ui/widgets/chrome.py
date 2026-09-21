"""
پوستهٔ بیرونی پنجره: نوار بالایی، نوار کناری آیکون‌دار، کارت وضعیت
اتصال و نوار ویژگی‌ها.

این‌ها در تصاویر مرجع در همهٔ پوسته‌ها حضور دارند و فقط ظاهرشان فرق
می‌کند؛ بنابراین یک پیاده‌سازی مشترک دارند که از QSS رنگ می‌گیرد.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.ai_status_card import AIStatusCard
from ui.widgets.avatar import Avatar
from ui.icons import icon as make_icon
from ui.icons import icon_pixmap
from ui.icons.registry import icon_size
from ui.themes import get_theme
from ui.widgets.controls import StatusDot, set_role


class SearchBox(QLineEdit):
    """
    جستجوی سراسری نوار بالا.

    میان‌بر `Ctrl+K` تمرکز را به اینجا می‌آورد (ثبت در سامانهٔ میان‌برها).
    سیگنال `submitted(str)` هنگام زدن Enter منتشر می‌شود.
    """

    submitted = Signal(str)
    #: کاربر یک پیشنهاد را از فهرست انتخاب کرد: (نوع، مقدار)
    suggestion_activated = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        set_role(self, "search")
        self.setClearButtonEnabled(True)
        self.setMinimumWidth(240)
        self.setMaximumWidth(420)
        self.returnPressed.connect(self._on_return)

        # آیکون ذره‌بین داخل کادر
        self._search_action = self.addAction(
            make_icon("search", "#94a3b8"), QLineEdit.ActionPosition.LeadingPosition
        )

        # فهرست پیشنهادها: کاربر خواست با نوشتن هر حرف، گزینه‌ها
        # فهرست شوند. از QCompleter استفاده می‌کنیم چون جای‌گذاری،
        # پیمایش با کلید و بستن خودکار را درست انجام می‌دهد.
        self._model = QStandardItemModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setMaxVisibleItems(10)
        self._completer.activated[str].connect(self._on_suggestion_chosen)
        self.setCompleter(self._completer)

        #: نگاشت متن نمایش‌داده‌شده به (نوع، مقدار)
        self._entries: dict[str, tuple[str, str]] = {}

    def set_icon_color(self, color: str) -> None:
        """هماهنگ‌کردن رنگ ذره‌بین با پوسته."""
        self._search_action.setIcon(make_icon("search", color))

    def set_suggestions(self, entries: Sequence[tuple[str, str, str]]) -> None:
        """
        تنظیم فهرست پیشنهادها.

        هر قلم: `(kind, value, label)` — مثلاً
        `("symbol", "BTC/USDT", "BTC/USDT · بیت‌کوین")` یا
        `("page", "nav.settings", "تنظیمات")`. نگاشت برچسب به مقدار نگه
        داشته می‌شود تا هنگام انتخاب، مقدار واقعی منتشر شود نه متن نمایشی.
        """
        self._model.clear()
        self._entries = {}
        for kind, value, label in entries:
            text = str(label)
            self._entries[text] = (str(kind), str(value))
            self._model.appendRow(QStandardItem(text))

    def _on_suggestion_chosen(self, text: str) -> None:
        """انتشار پیشنهاد انتخاب‌شده."""
        kind, value = self._entries.get(text, ("query", text))
        self.suggestion_activated.emit(kind, value)

    def _on_return(self) -> None:
        """
        زدن Enter.

        اگر متن دقیقاً یکی از پیشنهادها باشد همان را باز می‌کنیم، وگرنه
        جست‌وجوی آزاد منتشر می‌شود.
        """
        text = self.text().strip()
        if text in self._entries:
            self._on_suggestion_chosen(text)
            return
        self.submitted.emit(text)

    def focus_and_select(self) -> None:
        """گرفتن تمرکز و انتخاب متن موجود — رفتار مورد انتظار از Ctrl+K."""
        self.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.selectAll()


class NotificationButton(QToolButton):
    """
    زنگ اعلان‌ها با نشانگر قرمز تعداد خوانده‌نشده.

    شمار صفر یعنی نقطهٔ قرمز پنهان می‌شود.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._count = 0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        set_role(self, "icon")

        # نقطهٔ کوچک گوشه — نباید روی خود آیکون بیفتد
        self._badge = QLabel(self)
        self._badge.setFixedSize(8, 8)
        self._badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._badge.setVisible(False)

    def set_count(self, count: int) -> None:
        """تنظیم شمار اعلان‌های خوانده‌نشده."""
        self._count = max(0, int(count))
        self._badge.setVisible(self._count > 0)
        self._badge.setToolTip(str(self._count))
        self._place_badge()

    def set_badge_color(self, color: str) -> None:
        """رنگ نقطه از پوسته می‌آید تا در هر پوسته دیده شود."""
        self._badge.setStyleSheet(
            f"background-color: {color}; border-radius: 4px; border: none;"
        )

    def _place_badge(self) -> None:
        """جای‌گذاری نقطه در گوشهٔ بالای دکمه."""
        self._badge.move(self.width() - 12, 5)
        self._badge.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """جابه‌جایی نقطه هنگام تغییر اندازه."""
        super().resizeEvent(event)
        self._place_badge()


class UserMenuButton(QToolButton):
    """
    دکمهٔ حساب کاربری با منوی کشویی.

    سیگنال‌ها: `profile_requested`, `settings_requested`, `login_requested`,
    `logout_requested`.
    """

    profile_requested = Signal()
    settings_requested = Signal()
    login_requested = Signal()
    logout_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        set_role(self, "user_chip")

        self._menu = QMenu(self)
        self._profile_action = self._menu.addAction("")
        self._settings_action = self._menu.addAction("")
        self._menu.addSeparator()
        self._login_action = self._menu.addAction("")
        self._logout_action = self._menu.addAction("")
        self.setMenu(self._menu)

        self._profile_action.triggered.connect(self.profile_requested)
        self._settings_action.triggered.connect(self.settings_requested)
        self._login_action.triggered.connect(self.login_requested)
        self._logout_action.triggered.connect(self.logout_requested)

        self._authenticated = False
        self._icon_color = "#94a3b8"
        # آواتار واقعی به‌جای آیکون ثابت: حرف اول نام + حلقهٔ وضعیت ورود
        self._avatar = Avatar(26, self)
        self.setIconSize(icon_size(1))  # آیکون داخلی حذف می‌شود
        self._sync_avatar_geometry()

    def apply_theme(self, theme) -> None:
        """رنگ‌آمیزی دوبارهٔ آواتار و اقلام منو با پوستهٔ جاری."""
        self._icon_color = theme.colors.text_muted
        self._avatar.apply_theme(theme)
        self._profile_action.setIcon(make_icon("user", self._icon_color))
        self._settings_action.setIcon(make_icon("settings", self._icon_color))
        self._login_action.setIcon(make_icon("lock", self._icon_color))
        self._logout_action.setIcon(make_icon("logout", self._icon_color))

    def _sync_avatar_geometry(self) -> None:
        """
        قراردادن آواتار در ابتدای دکمه، متناسب با جهت زبان.

        پدینگ هم همان‌جا آینه می‌شود؛ وگرنه در فارسی نام روی آواتار
        می‌افتد (در نسخهٔ قبل دقیقاً همین اتفاق افتاد).
        """
        size = self._avatar.height()
        margin = 6
        gap = size + margin * 2
        top = max(0, (self.height() - size) // 2)
        rtl = self.layoutDirection() == Qt.LayoutDirection.RightToLeft
        if rtl:
            self._avatar.move(self.width() - size - margin, top)
            padding = f"padding-right: {gap}px; padding-left: 14px;"
        else:
            self._avatar.move(margin, top)
            padding = f"padding-left: {gap}px; padding-right: 14px;"

        # نکتهٔ مهم: شیوه‌نامهٔ درون‌خطی در Qt بر قواعد پوسته اولویت دارد.
        # اگر پدینگ را بدون انتخابگر بنویسیم، کل قاعدهٔ حالت ورود/مهمان
        # خنثی می‌شود. با محدودکردن به همان حالتِ جاری، فقط پدینگ تحمیل
        # می‌شود و رنگ و قاب از پوسته می‌آید.
        state = self.property("state") or "guest"
        self.setStyleSheet(
            f'QToolButton[role="user_chip"][state="{state}"] {{ {padding} }}'
        )
        self._avatar.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """هم‌گام نگه‌داشتن جای آواتار با تغییر اندازه."""
        super().resizeEvent(event)
        self._sync_avatar_geometry()

    def set_labels(
        self,
        *,
        profile: str,
        settings: str,
        login: str,
        logout: str,
    ) -> None:
        """به‌روزرسانی متن منو هنگام تغییر زبان."""
        self._profile_action.setText(profile)
        self._settings_action.setText(settings)
        self._login_action.setText(login)
        self._logout_action.setText(logout)

    def set_user(self, display_name: str, *, authenticated: bool) -> None:
        """
        نمایش کاربر جاری.

        در حالت مهمان گزینهٔ «خروج» پنهان و «ورود» نمایان است.
        """
        self._authenticated = bool(authenticated)
        self._avatar.set_user(display_name, authenticated=authenticated)
        # فاصلهٔ ابتدایی جا برای آواتار باز می‌کند؛ در راست‌به‌چپ هم درست
        # می‌نشیند چون از چیدمان خود Qt استفاده می‌کنیم نه فاصلهٔ دستی.
        self.setText(f"   {display_name}")
        # حالت ورود و مهمان باید در یک نگاه از هم جدا باشند: کاربر
        # واردشده قاب برجسته و لهجه‌دار می‌گیرد، مهمان قاب خنثی. بدون این،
        # کاربر نمی‌فهمد با حساب خودش کار می‌کند یا نه.
        self.setProperty("state", "signed_in" if self._authenticated else "guest")
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self._sync_avatar_geometry()
        self._logout_action.setVisible(self._authenticated)
        self._login_action.setVisible(not self._authenticated)
        self._profile_action.setEnabled(self._authenticated)


class TopBar(QFrame):
    """
    نوار بالایی سراسری: عنوان صفحه، جستجو، تغییر سریع پوسته، حالت تمرکز،
    اعلان‌ها و منوی کاربر.

    این نوار در همهٔ پوسته‌ها هست؛ فقط رنگ و شعاعش تغییر می‌کند.
    """

    search_submitted = Signal(str)
    theme_toggle_requested = Signal()
    focus_mode_toggled = Signal(bool)
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        set_role(self, "topbar")
        self.setFixedHeight(58)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(10)

        self.page_title = QLabel("", self)
        set_role(self.page_title, "subtitle")

        self.page_hint = QLabel("", self)
        set_role(self.page_hint, "faint")

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(0)
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.page_hint)

        self.search = SearchBox(self)
        self.search.submitted.connect(self.search_submitted)

        self.refresh_button = QToolButton(self)
        set_role(self.refresh_button, "icon")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.clicked.connect(self.refresh_requested)

        self.theme_button = QToolButton(self)
        set_role(self.theme_button, "icon")
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.clicked.connect(self.theme_toggle_requested)

        self.focus_button = QToolButton(self)
        self.focus_button.setCheckable(True)
        set_role(self.focus_button, "icon")
        self.focus_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.focus_button.toggled.connect(self.focus_mode_toggled)

        self.notifications = NotificationButton(self)
        self.user_menu = UserMenuButton(self)

        self._icon_color = "#94a3b8"
        for button, name in (
            (self.refresh_button, "refresh"),
            (self.theme_button, "theme"),
            (self.focus_button, "eye"),
            (self.notifications, "bell"),
        ):
            button.setIcon(make_icon(name, self._icon_color))
            button.setIconSize(icon_size(18))

        layout.addLayout(title_box)
        layout.addStretch(1)
        layout.addWidget(self.search)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.theme_button)
        layout.addWidget(self.focus_button)
        layout.addWidget(self.notifications)
        layout.addWidget(self.user_menu)

    def set_page(self, title: str, hint: str = "") -> None:
        """به‌روزرسانی عنوان صفحهٔ جاری."""
        self.page_title.setText(title)
        self.page_hint.setText(hint)
        self.page_hint.setVisible(bool(hint))

    def apply_theme(self, theme) -> None:
        """
        انتقال پوسته به اجزایی که QSS نمی‌گیرند.

        آیکون دکمه‌های نوار بالا برداری است و باید با رنگ پوستهٔ تازه
        دوباره رسم شود.
        """
        self.notifications.set_badge_color(theme.colors.danger)
        color = theme.colors.text_muted
        self._icon_color = color
        for button, name in (
            (self.refresh_button, "refresh"),
            (self.theme_button, "theme"),
            (self.focus_button, "eye"),
        ):
            button.setIcon(make_icon(name, color))
            button.setIconSize(icon_size(18))
        self.notifications.setIcon(make_icon("bell", color))
        self.notifications.setIconSize(icon_size(18))
        self.search.set_icon_color(color)
        self.user_menu.apply_theme(theme)

    def set_placeholders(self, *, search: str, tooltips: dict[str, str] | None = None) -> None:
        """تنظیم متن راهنما و tooltipها هنگام تغییر زبان."""
        self.search.setPlaceholderText(search)
        for key, text in (tooltips or {}).items():
            button = {
                "refresh": self.refresh_button,
                "theme": self.theme_button,
                "focus": self.focus_button,
                "notifications": self.notifications,
            }.get(key)
            if button is not None:
                button.setToolTip(text)


class ConnectionCard(QFrame):
    """
    کارت وضعیت اتصال صرافی در پایین نوار کناری.

    نمایش: نقطهٔ رنگی + متن وضعیت + نام صرافی فعال + زمان آخرین همگام‌سازی.
    """

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        set_role(self, "connection")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme = get_theme(None)
        self._connected = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(7)
        self.dot = StatusDot(self)
        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("font-weight: 700;")
        self.exchange_label = QLabel("", self)
        self.exchange_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        set_role(self.exchange_label, "badge")

        row.addWidget(self.dot)
        row.addWidget(self.status_label)
        row.addStretch(1)
        row.addWidget(self.exchange_label)
        layout.addLayout(row)

        self.detail_label = QLabel("", self)
        set_role(self.detail_label, "faint")
        layout.addWidget(self.detail_label)

    def set_state(
        self, *, connected: bool, status_text: str, exchange: str = "", detail: str = ""
    ) -> None:
        """به‌روزرسانی وضعیت نمایش‌داده‌شده."""
        self._connected = bool(connected)
        colors = self._theme.colors
        self.dot.set_status(colors.success if connected else colors.danger)
        self.status_label.setText(status_text)
        self.exchange_label.setText(exchange.upper())
        self.exchange_label.setVisible(bool(exchange))
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))

    def apply_theme(self, theme) -> None:
        """گرفتن رنگ نقطه از پوسته."""
        self._theme = theme
        colors = theme.colors
        self.dot.set_status(colors.success if self._connected else colors.danger)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """کلیک روی کارت کاربر را به صفحهٔ تنظیمات اتصال می‌برد."""
        self.clicked.emit()
        super().mousePressEvent(event)


class IconSidebar(QFrame):
    """
    نوار کناری با آیکون و برچسب.

    نمونه‌سازی:
        sidebar = IconSidebar()
        sidebar.set_items([("nav.dashboard", "◧", "داشبورد"), ...])
        sidebar.page_selected.connect(handler)

    سیگنال `page_selected(int)` شمارهٔ صفحه را می‌فرستد تا با
    `MainWindow.go_to_page(int)` سازگار بماند.
    """

    page_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        set_role(self, "sidebar")
        self.setFixedWidth(236)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self._buttons: list[QPushButton] = []
        self._collapsed = False
        self._icons: list[str] = []
        self._labels: list[str] = []
        self._icon_color = "#94a3b8"
        self._accent_color = "#22d3ee"

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 16, 12, 12)
        self._layout.setSpacing(6)

        brand = QHBoxLayout()
        brand.setSpacing(9)
        self.brand_icon = QLabel(self)
        self.brand_icon.setPixmap(icon_pixmap("signals", "#22d3ee", 20))
        self.brand_title = QLabel("", self)
        set_role(self.brand_title, "title")
        self.brand_title.setStyleSheet("font-size: 15px;")
        brand.addWidget(self.brand_icon)
        brand.addWidget(self.brand_title)
        brand.addStretch(1)
        self._layout.addLayout(brand)

        self.brand_subtitle = QLabel("", self)
        set_role(self.brand_subtitle, "faint")
        self._layout.addWidget(self.brand_subtitle)
        self._layout.addSpacing(10)

        self._nav_box = QVBoxLayout()
        self._nav_box.setSpacing(4)
        self._layout.addLayout(self._nav_box)
        self._layout.addStretch(1)

        # کارت وضعیت هوش مصنوعی بالای کارت اتصال صرافی می‌نشیند:
        # کاربر خواست ببیند کدام مدل وصل است، بدون رفتن به تنظیمات.
        self.ai_status = AIStatusCard(self)
        self._layout.addWidget(self.ai_status)

        self.connection = ConnectionCard(self)
        self._layout.addWidget(self.connection)

        self.disclaimer = QLabel("", self)
        set_role(self.disclaimer, "faint")
        self.disclaimer.setWordWrap(True)
        self._layout.addWidget(self.disclaimer)

    def apply_theme(self, theme) -> None:
        """
        انتقال پوسته به کارت اتصال و رنگ‌آمیزی دوبارهٔ آیکون‌ها.

        آیکون‌ها برداری‌اند، پس با هر پوسته دوباره و تمیز رسم می‌شوند.
        """
        self.connection.apply_theme(theme)
        self.ai_status.apply_theme(theme)
        self._icon_color = theme.colors.text_muted
        self._accent_color = theme.colors.primary
        self.brand_icon.setPixmap(
            icon_pixmap("signals", theme.colors.primary, 20)
        )
        self._render_labels()
        self._highlight_current()

    def set_brand(self, title: str, subtitle: str = "") -> None:
        """تنظیم نام و زیرعنوان برنامه."""
        self.brand_title.setText(title)
        self.brand_subtitle.setText(subtitle)
        self.brand_subtitle.setVisible(bool(subtitle))

    def set_items(self, items: Sequence[tuple[str, str]]) -> None:
        """
        ساخت دکمه‌های ناوبری.

        هر آیتم: `(icon, label)`. ترتیب همان ترتیب صفحه‌ها در
        `MainWindow.PAGES` است.
        """
        while self._nav_box.count():
            item = self._nav_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._buttons.clear()
        self._icons = [icon for icon, _ in items]
        self._labels = [label for _, label in items]

        for index, (icon_name, label) in enumerate(items):
            button = QPushButton(f"   {label}", self)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            set_role(button, "nav")
            button.setIcon(make_icon(icon_name, self._icon_color))
            button.setIconSize(icon_size(19))
            button.clicked.connect(lambda _c=False, i=index: self._on_clicked(i))
            self._nav_box.addWidget(button)
            self._buttons.append(button)

        if self._buttons:
            self._buttons[0].setChecked(True)

    def set_labels(self, labels: Sequence[str]) -> None:
        """به‌روزرسانی متن دکمه‌ها هنگام تغییر زبان."""
        self._labels = list(labels)
        self._render_labels()

    def set_collapsed(self, collapsed: bool) -> None:
        """
        جمع‌کردن نوار به حالت فقط‌آیکون.

        در حالت تمرکز یا پنجرهٔ باریک استفاده می‌شود.
        """
        self._collapsed = bool(collapsed)
        self.setFixedWidth(62 if self._collapsed else 236)
        self.brand_title.setVisible(not self._collapsed)
        self.brand_subtitle.setVisible(not self._collapsed and bool(self.brand_subtitle.text()))
        self.connection.setVisible(not self._collapsed)
        self.disclaimer.setVisible(not self._collapsed)
        self._render_labels()

    def is_collapsed(self) -> bool:
        """آیا نوار در حالت فقط‌آیکون است؟"""
        return self._collapsed

    def set_current(self, index: int) -> None:
        """هماهنگ‌کردن دکمهٔ فعال با صفحهٔ نمایش‌داده‌شده."""
        for position, button in enumerate(self._buttons):
            button.setChecked(position == index)
        self._highlight_current()

    def _highlight_current(self) -> None:
        """
        آیکون صفحهٔ فعال با رنگ تأکید رسم می‌شود.

        بدون این، آیکون فعال همرنگ بقیه می‌ماند و انتخاب جاری فقط از
        پس‌زمینهٔ دکمه دیده می‌شود.
        """
        for index, button in enumerate(self._buttons):
            name = self._icons[index] if index < len(self._icons) else ""
            color = self._accent_color if button.isChecked() else self._icon_color
            button.setIcon(make_icon(name, color))
            button.setIconSize(icon_size(19))

    def _render_labels(self) -> None:
        """
        بازنویسی متن و آیکون دکمه‌ها بر پایهٔ حالت جمع‌شده.

        در حالت جمع‌شده فقط آیکون می‌ماند و نام صفحه به راهنمای شناور
        منتقل می‌شود.
        """
        for index, button in enumerate(self._buttons):
            icon_name = self._icons[index] if index < len(self._icons) else ""
            label = self._labels[index] if index < len(self._labels) else ""
            button.setIcon(make_icon(icon_name, self._icon_color))
            button.setIconSize(icon_size(19))
            if self._collapsed:
                button.setText("")
                button.setToolTip(label)
            else:
                button.setText(f"   {label}")
                button.setToolTip("")

    def _on_clicked(self, index: int) -> None:
        """انتشار انتخاب صفحه."""
        self.set_current(index)
        self.page_selected.emit(index)


class FeatureStrip(QFrame):
    """
    نوار ویژگی‌ها بالای نوار وضعیت — همان چهار قلم تصاویر مرجع.

    محتوایش تبلیغاتی نیست؛ هر قلم به صفحهٔ مربوطه پیوند دارد.
    """

    feature_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        set_role(self, "featurebar")
        self.setFixedHeight(38)
        self._icon_color = "#94a3b8"
        self._features: list[tuple[str, str, str]] = []
        self._buttons: dict[str, QPushButton] = {}

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(18, 6, 18, 6)
        self._layout.setSpacing(26)

    def set_features(self, features: Sequence[tuple[str, str, str]]) -> None:
        """
        تنظیم اقلام نوار.

        هر قلم: `(key, icon, label)`؛ کلیک روی آن `feature_clicked(key)`
        را منتشر می‌کند.
        """
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._buttons.clear()

        self._features = list(features)
        self._layout.addStretch(1)
        for key, icon_name, label in features:
            button = QPushButton(f"  {label}", self)
            set_role(button, "ghost")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(make_icon(icon_name, self._icon_color))
            button.setIconSize(icon_size(16))
            button.clicked.connect(lambda _c=False, k=key: self.feature_clicked.emit(k))
            self._layout.addWidget(button)
            self._buttons[key] = button
        self._layout.addStretch(1)

    def apply_theme(self, theme) -> None:
        """رنگ‌آمیزی دوبارهٔ آیکون‌های نوار ویژگی‌ها با پوستهٔ جاری."""
        self._icon_color = theme.colors.text_muted
        for key, icon_name, _label in self._features:
            button = self._buttons.get(key)
            if button is not None:
                button.setIcon(make_icon(icon_name, self._icon_color))
                button.setIconSize(icon_size(16))


__all__ = [
    "ConnectionCard",
    "FeatureStrip",
    "IconSidebar",
    "NotificationButton",
    "SearchBox",
    "TopBar",
    "UserMenuButton",
]
