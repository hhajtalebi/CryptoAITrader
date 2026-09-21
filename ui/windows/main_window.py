"""
پنجره اصلی برنامه.

ساختار: نوار بالایی سراسری + نوار ناوبری کناری آیکون‌دار + ناحیه صفحات
(QStackedWidget) + نوار ویژگی‌ها + نوار وضعیت.

سه ویژگی که عمداً در این کلاس متمرکز شده‌اند:
    ۱) تغییر زبان در زمان اجرا: با فراخوانی `retranslate` روی همه صفحات و
       تغییر جهت چیدمان (RTL/LTR) بدون نیاز به راه‌اندازی مجدد.
    ۲) تغییر پوسته در زمان اجرا: با اعمال دوباره برگه سبک و انتقال
       توکن‌ها به اجزایی که QSS نمی‌گیرند (نمودارها).
    ۳) میان‌برهای صفحه‌کلید: در یک ثبت‌گاه متمرکز، نه پراکنده در صفحات.

**قاعدهٔ پوسته:** هیچ صفحه‌ای بر پایهٔ نام پوسته رفتار متفاوتی ندارد؛
پوسته فقط ظاهر است.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import APP_NAME, APP_VERSION, PRODUCER_NAME
from app.core.timeutil import format_time, now_local, utc_offset_label
from app.logging import get_logger
from localization import Translator
from ui.pages import (
    AnalysisPage,
    ChatPage,
    DashboardPage,
    HelpPage,
    MarketsPage,
    ReportsPage,
    SettingsPage,
    SignalsPage,
    TradesPage,
    WalletPage,
)
from ui.themes import ThemeManager
from ui.widgets import FeatureStrip, IconSidebar, StatusDot, TopBar, set_role

logger = get_logger(__name__)

#: نمادهای ناوبری — بخشی از پوسته نیستند و در همه پوسته‌ها یکسان‌اند
#: نام آیکون برداری هر صفحه (از مجموعهٔ ui.icons)
NAV_ICONS: dict[str, str] = {
    "nav.dashboard": "dashboard",
    "nav.markets": "markets",
    "nav.analysis": "analysis",
    "nav.signals": "signals",
    "nav.chat": "chat",
    "nav.trades": "trades",
    "nav.wallet": "wallet",
    "nav.reports": "reports",
    "nav.settings": "settings",
    "nav.help": "help",
}

#: پهنایی که زیر آن نوار کناری خودکار جمع می‌شود
RESPONSIVE_BREAKPOINT = 1180

#: ارتفاعی که زیر آن نوار ویژگی‌ها پنهان می‌شود
COMPACT_HEIGHT = 700

#: اقلام نوار ویژگی‌ها: (کلید، نماد، کلید ترجمه، صفحهٔ مقصد)
FEATURES: list[tuple[str, str, str, str]] = [
    ("ai", "robot", "common.features.ai", "nav.chat"),
    ("signals", "signals", "common.features.signals", "nav.signals"),
    ("risk", "shield", "common.features.risk", "nav.settings"),
    ("support", "chat", "common.features.support", "nav.help"),
]


class MainWindow(QMainWindow):
    """پنجره اصلی با ناوبری ده‌بخشی."""

    #: هنگام درخواست تغییر زبان از صفحه تنظیمات
    language_change_requested = Signal(str)
    #: هنگام درخواست تغییر پوسته
    theme_change_requested = Signal(str)
    #: جستجوی سراسری نوار بالا
    search_requested = Signal(str)
    #: کاربر پیشنهادی از فهرست جست‌وجو را برگزید: (نوع، مقدار)
    search_suggestion_activated = Signal(str, str)
    #: کاربر از نوار بالا تازه‌سازی خواست
    refresh_requested = Signal()
    #: درخواست ورود از منوی کاربر
    login_requested = Signal()
    #: درخواست خروج از منوی کاربر
    logout_requested = Signal()

    #: (کلید ترجمه، کلاس صفحه)
    PAGES: list[tuple[str, type]] = [
        ("nav.dashboard", DashboardPage),
        ("nav.markets", MarketsPage),
        ("nav.analysis", AnalysisPage),
        ("nav.signals", SignalsPage),
        ("nav.chat", ChatPage),
        ("nav.trades", TradesPage),
        ("nav.wallet", WalletPage),
        ("nav.reports", ReportsPage),
        ("nav.settings", SettingsPage),
        ("nav.help", HelpPage),
    ]

    def __init__(
        self,
        translator: Translator,
        theme_manager: ThemeManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._themes = theme_manager or ThemeManager()
        self.pages: dict[str, QWidget] = {}
        self._focus_mode = False
        self._market_count = 0

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1360, 840)
        self.setMinimumSize(1024, 660)

        self._build_ui()
        self._register_shortcuts()
        self.apply_direction()
        self.apply_theme_tokens()
        self._connect_signals()

    # ------------------------------------------------------------------
    # ساخت رابط
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """ساخت چیدمان کلی پنجره."""
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- نوار بالایی ---
        self.topbar = TopBar(central)
        outer.addWidget(self.topbar)

        # --- بدنه: نوار کناری + صفحات ---
        body = QWidget(central)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        from PySide6.QtWidgets import QHBoxLayout

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.sidebar = IconSidebar(body)
        self.sidebar.set_items(
            [(NAV_ICONS.get(key, "info"), self.tr_.tr(key)) for key, _ in self.PAGES]
        )
        self.sidebar.page_selected.connect(self.go_to_page)
        row.addWidget(self.sidebar)

        self.stack = QStackedWidget(body)
        row.addWidget(self.stack, 1)
        body_layout.addLayout(row)
        outer.addWidget(body, 1)

        for key, page_class in self.PAGES:
            page = page_class(self.tr_)
            self.pages[key] = page
            self.stack.addWidget(page)

        # --- نوار ویژگی‌ها ---
        self.feature_strip = FeatureStrip(central)
        self.feature_strip.feature_clicked.connect(self._on_feature_clicked)
        outer.addWidget(self.feature_strip)

        self.setCentralWidget(central)
        self._build_status_bar()

        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start()
        self._tick_clock()

        self.sidebar.set_current(0)
        self._sync_topbar_title(0)
        self._retranslate_chrome()

    def _build_status_bar(self) -> None:
        """نوار وضعیت پایین: پیام، شمار بازار، نشانگر اتصال، ساعت، سازنده."""
        self.status = QStatusBar()

        self.status_label = QLabel(self.tr_.tr("common.state.loading"))
        self.status.addWidget(self.status_label)

        self.market_count_label = QLabel("")
        set_role(self.market_count_label, "muted")
        self.status.addWidget(self.market_count_label)

        # نشانگر زندهٔ اتصال: کاربر باید بدون رفتن به داشبورد بفهمد
        # برنامه آنلاین است یا نه.
        self.connection_dot = StatusDot(self.status)
        self.status.addPermanentWidget(self.connection_dot)

        self.connection_label = QLabel(self.tr_.tr("common.disconnected"))
        set_role(self.connection_label, "muted")
        self.status.addPermanentWidget(self.connection_label)

        # ساعت، به وقت محلی کاربر. یکی از ایرادهای گزارش‌شده این بود که
        # زمان نمایش‌داده‌شده اشتباه بود، چون همه‌جا UTC نشان داده می‌شد.
        self.clock_label = QLabel("")
        set_role(self.clock_label, "muted")
        self.status.addPermanentWidget(self.clock_label)

        self.producer_label = QLabel(self._producer_text())
        set_role(self.producer_label, "muted")
        self.status.addPermanentWidget(self.producer_label)

        self.version_label = QLabel(f"v{APP_VERSION}")
        set_role(self.version_label, "muted")
        self.status.addPermanentWidget(self.version_label)

        self.setStatusBar(self.status)

    def _register_shortcuts(self) -> None:
        """
        ثبت‌گاه متمرکز میان‌برهای صفحه‌کلید.

        متمرکز بودن یعنی صفحهٔ راهنما می‌تواند همین فهرست را بخواند و
        هیچ میان‌بری از قلم نیفتد.
        """
        self.shortcuts: dict[str, str] = {}

        def bind(sequence: str, handler, description_key: str) -> None:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)
            self.shortcuts[sequence] = description_key

        bind("Ctrl+K", self.focus_search, "help.shortcuts.search")
        bind("Ctrl+R", self.refresh_requested.emit, "help.shortcuts.refresh")
        bind("Ctrl+B", self.toggle_sidebar, "help.shortcuts.sidebar")
        bind("Ctrl+Shift+F", self.toggle_focus_mode, "help.shortcuts.focus")
        bind("Ctrl+T", self._cycle_theme, "help.shortcuts.theme")
        # میان‌بر عددی برای ده صفحه: Ctrl+1 تا Ctrl+9 و Ctrl+0
        for index in range(len(self.PAGES)):
            key = (index + 1) % 10
            bind(f"Ctrl+{key}", lambda i=index: self.go_to_page(i), "help.shortcuts.pages")

    def _connect_signals(self) -> None:
        """اتصال کنترل‌های نوار بالا و صفحه تنظیمات."""
        self.topbar.search_submitted.connect(self.search_requested)
        self.topbar.search.suggestion_activated.connect(self.search_suggestion_activated)
        self.topbar.refresh_requested.connect(self.refresh_requested)
        self.topbar.theme_toggle_requested.connect(self._cycle_theme)
        self.topbar.focus_mode_toggled.connect(self.set_focus_mode)
        self.topbar.user_menu.login_requested.connect(self.login_requested)
        self.topbar.user_menu.logout_requested.connect(self.logout_requested)
        self.topbar.user_menu.settings_requested.connect(
            lambda: self.go_to_page(self.page_index("nav.settings"))
        )
        self.topbar.user_menu.profile_requested.connect(
            lambda: self.go_to_page(self.page_index("nav.settings"))
        )
        self.sidebar.connection.clicked.connect(
            lambda: self.go_to_page(self.page_index("nav.settings"))
        )

        settings_page = self.pages.get("nav.settings")
        if isinstance(settings_page, SettingsPage):
            settings_page.language_combo.currentIndexChanged.connect(
                lambda: self.language_change_requested.emit(
                    settings_page.language_combo.currentData()
                )
            )
            settings_page.theme_combo.currentIndexChanged.connect(
                lambda: self.theme_change_requested.emit(settings_page.theme_combo.currentData())
            )

        wallet_page = self.pages.get("nav.wallet")
        if isinstance(wallet_page, WalletPage):
            wallet_page.connect_requested.connect(
                lambda: self.go_to_page(self.page_index("nav.settings"))
            )

    # ------------------------------------------------------------------
    # ناوبری
    # ------------------------------------------------------------------
    def go_to_page(self, index: int) -> None:
        """رفتن به صفحه با نمایه مشخص."""
        if not 0 <= index < self.stack.count():
            return
        self.stack.setCurrentIndex(index)
        self.sidebar.set_current(index)
        self._sync_topbar_title(index)
        page = self.stack.widget(index)
        if hasattr(page, "on_activated"):
            page.on_activated()

    def page_index(self, key: str) -> int:
        """نمایهٔ یک صفحه بر پایهٔ کلید ناوبری آن."""
        for index, (page_key, _) in enumerate(self.PAGES):
            if page_key == key:
                return index
        return 0

    def page(self, key: str) -> QWidget | None:
        """دسترسی به یک صفحه بر اساس کلید ناوبری."""
        return self.pages.get(key)

    def focus_search(self) -> None:
        """بردن تمرکز به جستجوی سراسری (Ctrl+K)."""
        self.topbar.search.focus_and_select()

    def toggle_sidebar(self) -> None:
        """جمع/باز کردن نوار کناری (Ctrl+B)."""
        self.sidebar.set_collapsed(not self.sidebar.is_collapsed())

    def toggle_focus_mode(self) -> None:
        """کلید حالت تمرکز (Ctrl+Shift+F)."""
        self.topbar.focus_button.setChecked(not self._focus_mode)

    def set_focus_mode(self, enabled: bool) -> None:
        """
        حالت تمرکز: نوار کناری جمع و نوار ویژگی‌ها پنهان می‌شود.

        هیچ قابلیتی حذف نمی‌شود؛ فقط فضای بیشتری به محتوا می‌رسد.
        """
        self._focus_mode = bool(enabled)
        self.sidebar.set_collapsed(self._focus_mode)
        self.feature_strip.setVisible(not self._focus_mode)

    def resizeEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """
        رفتار واکنش‌گرا.

        روی نمایشگر کوچک (یا پنجرهٔ باریک) نوار کناری خودکار جمع می‌شود تا
        جدول‌ها جا بگیرند؛ با پهن شدن دوباره باز می‌گردد. اگر کاربر خودش
        حالت تمرکز را روشن کرده باشد، دست نمی‌خورد.
        """
        super().resizeEvent(event)
        if self._focus_mode:
            return
        narrow = self.width() < RESPONSIVE_BREAKPOINT
        if narrow != self.sidebar.is_collapsed():
            self.sidebar.set_collapsed(narrow)
        # نوار ویژگی‌ها در ارتفاع کم فقط فضا می‌گیرد
        self.feature_strip.setVisible(self.height() >= COMPACT_HEIGHT)

    # ------------------------------------------------------------------
    # زبان و پوسته
    # ------------------------------------------------------------------
    def apply_direction(self) -> None:
        """
        اعمال جهت چیدمان بر پایه زبان جاری.

        فارسی راست‌به‌چپ و انگلیسی چپ‌به‌راست چیده می‌شود.

        جهت روی خود برنامه Qt هم تنظیم می‌شود تا پنجره‌های گفت‌وگو (مانند
        انتخاب فایل و پیام‌ها) هم درست بچینند. سپس صفت «جهتِ صریح» از همه
        ویجت‌های فرزند برداشته می‌شود؛ بدون این کار، هر ویجتی که یک بار
        جهتش دستی تنظیم شده باشد، در تغییر زبان بعدی روی حالت قبلی
        می‌ماند و بخشی از پنجره برعکس بقیه دیده می‌شود.
        """
        direction = (
            Qt.LayoutDirection.RightToLeft if self.tr_.is_rtl else Qt.LayoutDirection.LeftToRight
        )
        application = QApplication.instance()
        if application is not None:
            application.setLayoutDirection(direction)

        for child in self.findChildren(QWidget):
            child.setAttribute(Qt.WidgetAttribute.WA_SetLayoutDirection, False)
        self.setLayoutDirection(direction)

        # نمادهای بازار مانند BTC/USDT هرگز نباید برعکس شوند
        self._force_ltr_widgets()
        self.update()

    def apply_theme_tokens(self) -> None:
        """
        انتقال توکن‌های پوسته به اجزایی که برگه سبک نمی‌گیرند.

        نمودارها و ویجت‌های نقاشی‌شده رنگشان را از اینجا می‌گیرند؛ بدون
        این فراخوانی، تغییر پوسته روی آن‌ها بی‌اثر می‌ماند.
        """
        tokens = self._themes.tokens
        self.topbar.apply_theme(tokens)
        self.sidebar.apply_theme(tokens)
        self.feature_strip.apply_theme(tokens)
        for page in self.pages.values():
            if hasattr(page, "apply_theme"):
                try:
                    page.apply_theme(tokens)
                except Exception:  # noqa: BLE001 - یک صفحه نباید بقیه را بخواباند
                    logger.exception("Theme application failed for a page")

    def retranslate(self) -> None:
        """
        بازسازی همه متن‌های پنجره و صفحات.

        پس از تغییر زبان فراخوانی می‌شود و نیازی به ساخت دوباره ویجت‌ها
        نیست.
        """
        self._retranslate_chrome()
        for page in self.pages.values():
            if hasattr(page, "retranslate"):
                page.retranslate()
        self.apply_direction()
        logger.info("UI retranslated to '%s'", self.tr_.language)

    def _retranslate_chrome(self) -> None:
        """بازسازی متن‌های پوستهٔ بیرونی پنجره."""
        self.sidebar.set_brand(
            self.tr_.tr("common.app_name"), self.tr_.tr("common.app_tagline", "")
        )
        self.sidebar.set_labels([self.tr_.tr(key) for key, _ in self.PAGES])
        self.sidebar.disclaimer.setText(self.tr_.tr("signals.not_financial_advice"))

        self.topbar.set_placeholders(
            search=self.tr_.tr("common.search_placeholder"),
            tooltips={
                "refresh": self.tr_.tr("common.refresh"),
                "theme": self.tr_.tr("common.toggle_theme"),
                "focus": self.tr_.tr("common.focus_mode"),
                "notifications": self.tr_.tr("common.notifications"),
            },
        )
        self.topbar.user_menu.set_labels(
            profile=self.tr_.tr("auth.profile"),
            settings=self.tr_.tr("nav.settings"),
            login=self.tr_.tr("auth.login"),
            logout=self.tr_.tr("auth.logout"),
        )
        self.feature_strip.set_features(
            [(key, icon, self.tr_.tr(label_key)) for key, icon, label_key, _ in FEATURES]
        )
        self.producer_label.setText(self._producer_text())
        self._sync_topbar_title(self.stack.currentIndex())
        self.set_market_count(self._market_count)

    def _force_ltr_widgets(self) -> None:
        """
        نگه‌داشتن جهت چپ‌به‌راست برای عناصر حاوی نماد بازار.

        نمادهایی مثل `BTC/USDT` در چیدمان راست‌به‌چپ به‌هم می‌ریزند؛ این
        ویجت‌ها صریحاً LTR می‌مانند.
        """
        for widget in self.findChildren(QWidget):
            if widget.property("force_ltr"):
                widget.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    def _cycle_theme(self) -> None:
        """
        چرخش میان پوسته‌ها با Ctrl+T یا دکمهٔ نوار بالا.

        درخواست منتشر می‌شود و کنترلر آن را ذخیره و اعمال می‌کند تا
        انتخاب کاربر ماندگار شود.
        """
        themes = [item.key for item in ThemeManager.available()]
        if not themes:
            return
        try:
            position = themes.index(self._themes.current)
        except ValueError:
            position = -1
        self.theme_change_requested.emit(themes[(position + 1) % len(themes)])

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    def set_connection_indicator(self, online: bool) -> None:
        """رنگی‌کردن نشانگر اتصال در نوار پایین."""
        colors = self._themes.tokens.colors
        self.connection_dot.set_status(colors.success if online else colors.danger)
        text = self.tr_.tr("common.connected" if online else "common.disconnected")
        self.connection_label.setText(text)
        self.connection_dot.setToolTip(text)

    def set_connection_card(
        self, *, connected: bool, exchange: str = "", detail: str = ""
    ) -> None:
        """به‌روزرسانی کارت اتصال در نوار کناری."""
        self.sidebar.connection.set_state(
            connected=connected,
            status_text=self.tr_.tr(
                "common.connected" if connected else "common.disconnected"
            ),
            exchange=exchange,
            detail=detail,
        )

    def set_market_count(self, count: int) -> None:
        """نمایش شمار بازارهای بارگذاری‌شده در نوار وضعیت."""
        self._market_count = int(count or 0)
        if self._market_count <= 0:
            self.market_count_label.setText("")
            return
        number = str(self._market_count)
        if self.tr_.language == "fa":
            number = self.tr_.to_persian_digits(number)
        self.market_count_label.setText(self.tr_.tr("common.market_count", count=number))

    def set_user(self, display_name: str, *, authenticated: bool) -> None:
        """به‌روزرسانی منوی کاربر در نوار بالا."""
        name = display_name
        if not authenticated:
            name = self.tr_.tr("auth.guest")
        self.topbar.user_menu.set_user(name, authenticated=authenticated)

    def set_notification_count(self, count: int) -> None:
        """تنظیم شمار اعلان‌های خوانده‌نشده."""
        self.topbar.notifications.set_count(count)

    def set_status(self, text: str) -> None:
        """به‌روزرسانی متن نوار وضعیت."""
        self.status_label.setText(text)

    # ------------------------------------------------------------------
    # داخلی
    # ------------------------------------------------------------------
    def _sync_topbar_title(self, index: int) -> None:
        """هماهنگ‌کردن عنوان نوار بالا با صفحهٔ فعال."""
        if not 0 <= index < len(self.PAGES):
            return
        key = self.PAGES[index][0]
        page = self.pages.get(key)
        subtitle = ""
        if page is not None and getattr(page, "subtitle_key", ""):
            subtitle = self.tr_.tr(page.subtitle_key)
        self.topbar.set_page(self.tr_.tr(key), subtitle)

    def _on_feature_clicked(self, key: str) -> None:
        """رفتن به صفحهٔ متناظر یک قلم نوار ویژگی‌ها."""
        for feature_key, _, _, target in FEATURES:
            if feature_key == key:
                self.go_to_page(self.page_index(target))
                return

    def _producer_text(self) -> str:
        """متن اعتبار سازنده در پایین برنامه."""
        return f"{self.tr_.tr('common.producer')}: {PRODUCER_NAME}"

    def _tick_clock(self) -> None:
        """
        به‌روزرسانی ساعت نوار پایین.

        زمان به وقت محلی کاربر نشان داده می‌شود نه UTC؛ نمایش UTC همان
        چیزی بود که کاربر آن را «ساعت اشتباه» گزارش کرده بود.
        """
        try:
            moment = now_local()
            clock = format_time(moment)
            # ارقام فارسی فقط در حالت فارسی؛ در انگلیسی باید لاتین بماند
            if self.tr_.language == "fa":
                clock = self.tr_.to_persian_digits(clock)
            self.clock_label.setText(f"{clock}  {utc_offset_label()}")
        except Exception:  # noqa: BLE001 - ساعت هرگز نباید برنامه را بخواباند
            self.clock_label.setText("")


__all__ = ["COMPACT_HEIGHT", "FEATURES", "NAV_ICONS", "RESPONSIVE_BREAKPOINT", "MainWindow"]
