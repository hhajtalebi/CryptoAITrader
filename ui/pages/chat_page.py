"""
صفحهٔ گفت‌وگو با دستیار هوش مصنوعی.

بازطراحی نسخهٔ ۱.۴ بر پایهٔ بازخورد کاربر:

    «ظاهر چت را مانند GPT کن … نوشته‌های کاربر و هوش مصنوعی کامل قابل
     خواندن باشد چون الان محدودیت است … چت‌ها همه ذخیره بشه و قابلیت حذف
     داشته باشه و کاربر بتونه به سابقهٔ چت‌ها دسترسی داشته باشه»

چه چیزی عوض شد و چرا:

۱. **جعبهٔ ورودی چندخطی.** پیش‌تر از QLineEdit استفاده می‌شد که ذاتاً
   تک‌خطی است؛ نوشتهٔ بلند از دید کاربر خارج می‌شد و معلوم نبود چه تایپ
   کرده. حالا جعبه چندخطی است و با تایپ کردن تا سقف مشخصی بزرگ می‌شود.
   Enter می‌فرستد و Shift+Enter خط تازه می‌سازد — همان رفتار ChatGPT.

۲. **حباب‌ها متن را کامل نشان می‌دهند.** عرض حباب به‌جای عدد ثابت،
   نسبتی از عرض پنجره است و متن هیچ‌گاه بریده نمی‌شود.

۳. **ستون تاریخچه.** فهرست گفت‌وگوها بر اساس زمان، با جست‌وجو، تغییر نام،
   حذف تکی و شروع گفت‌وگوی تازه.

۴. **متن قابل انتخاب و کپی** در هر دو سمت گفت‌وگو.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from localization import Translator
from market.timeframes import SUPPORTED_TIMEFRAMES
from ui.icons import icon_pixmap
from ui.pages.base_page import BasePage
from ui.widgets import make_button
from ui.widgets import ChipBar
from ui.widgets.tool_trail import ToolTrail

#: سهم حباب از عرض ناحیهٔ گفت‌وگو (۷۸٪ شبیه ChatGPT است)
BUBBLE_WIDTH_RATIO = 0.78

#: کمینه و بیشینهٔ ارتفاع جعبهٔ ورودی چندخطی
INPUT_MIN_HEIGHT = 44
INPUT_MAX_HEIGHT = 180


class ChatInput(QTextEdit):
    """
    جعبهٔ ورودی چندخطی با رفتار ChatGPT.

    • Enter پیام را می‌فرستد
    • Shift+Enter خط تازه می‌سازد
    • ارتفاع جعبه با مقدار متن بالا می‌رود و از سقف مشخصی بیشتر نمی‌شود

    متدهای `text()` و `clear()` عمداً نگه داشته شده‌اند تا بقیهٔ کد و
    آزمون‌ها که این صفحه را مثل یک جعبهٔ متن ساده می‌بینند، بدون تغییر
    کار کنند.
    """

    #: کاربر Enter زد (بدون Shift)
    returnPressed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(INPUT_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.textChanged.connect(self._auto_resize)

    def text(self) -> str:
        """متن جعبه — هم‌نام با QLineEdit تا جایگزینی بی‌دردسر باشد."""
        return self.toPlainText()

    def setText(self, text: str) -> None:  # noqa: N802 - هم‌نامی با Qt عمدی است
        """قرار دادن متن در جعبه."""
        self.setPlainText(str(text or ""))

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Enter می‌فرستد، Shift+Enter خط تازه می‌سازد."""
        is_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        has_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if is_enter and not has_shift:
            event.accept()
            self.returnPressed.emit()
            return
        super().keyPressEvent(event)

    def _auto_resize(self) -> None:
        """بزرگ شدن تدریجی جعبه با افزایش متن."""
        document = self.document()
        if document is None:
            return
        height = int(document.size().height()) + 12
        self.setFixedHeight(max(INPUT_MIN_HEIGHT, min(INPUT_MAX_HEIGHT, height)))


class ChatBubble(QFrame):
    """
    یک پیام در گفت‌وگو، به سبک ChatGPT.

    کاربر گفت: «ظاهر قسمت چت رو درست کن، قبلاً گفتم مانند chatgpt باشه».

    تفاوت با نسخهٔ پیشین:
        * هر پیام یک **ردیف تمام‌عرض** است، نه یک حباب شناور کوچک. پیام
          دستیار پس‌زمینهٔ ملایم می‌گیرد و پیام کاربر بدون پس‌زمینه است —
          دقیقاً الگوی ChatGPT.
        * کنار هر پیام یک نشان کوچک (آواتار) با حرف «شما» یا آیکن دستیار
          می‌آید تا گوینده در یک نگاه معلوم باشد.
        * ارتفاع بر پایهٔ متنِ پیچیده‌شده حساب می‌شود. پیش‌تر برچسب
          `QLabel` با `setWordWrap` ارتفاعش را به چیدمان اعلام نمی‌کرد و
          متن‌های بلند وسط جمله بریده می‌شدند — همان چیزی که در تصویر
          دیده می‌شد.
    """

    #: قطر نشان گوینده
    AVATAR_SIZE = 30

    def __init__(self, text: str, *, is_user: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_user = is_user
        self.setProperty("role", "chat_user" if is_user else "chat_ai")
        self.setFrameShape(QFrame.Shape.NoFrame)
        # ردیف تمام‌عرض؛ ارتفاع را خود محتوا تعیین می‌کند
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.avatar = QLabel("")
        self.avatar.setFixedSize(self.AVATAR_SIZE, self.AVATAR_SIZE)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setProperty("role", "chat_avatar_user" if is_user else "chat_avatar_ai")
        layout.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignTop)

        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)

        self.author = QLabel("")
        self.author.setProperty("role", "chat_author")
        column.addWidget(self.author)

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        # MinimumExpanding در محور عمودی: بدون آن، متن پیچیده‌شده ارتفاع
        # واقعی‌اش را به چیدمان نمی‌گفت و پیام بریده می‌شد.
        self.label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        self.label.setAlignment(
            Qt.AlignmentFlag.AlignTop
            | (Qt.AlignmentFlag.AlignRight if is_user else Qt.AlignmentFlag.AlignLeft)
        )
        column.addWidget(self.label)

        #: خط ابزارها؛ فقط وقتی چیزی برای گفتن باشد نمایش داده می‌شود.
        #: برای پاسخ‌های بازیابی‌شده از تاریخچه که فقط رشتهٔ خلاصه دارند
        #: همچنان به کار می‌آید؛ گفتگوی زنده از `tool_trail` استفاده
        #: می‌کند که وضعیت و نتیجهٔ هر گام را جدا نشان می‌دهد.
        self.tools_label = QLabel("")
        self.tools_label.setProperty("role", "caption")
        self.tools_label.setWordWrap(True)
        self.tools_label.hide()
        column.addWidget(self.tools_label)

        #: گام‌به‌گام اجرای ابزارها (زنده)
        self.tool_trail = ToolTrail(self)
        column.addWidget(self.tool_trail)

        layout.addLayout(column, 1)

    def set_author(self, author: str) -> None:
        """تعیین نام گوینده (پس از تغییر زبان هم صدا زده می‌شود)."""
        self.author.setText(author)

    def set_avatar_icon(self, name: str, color: str) -> None:
        """
        گذاشتن آیکن برداری روی نشان گوینده.

        از ایموجی استفاده نمی‌کنیم؛ ایموجی هم مثل گلیف‌های قبلی در فونت
        وزیرمتن وجود ندارد و به شکل مربع یا دایرهٔ خالی درمی‌آید.
        """
        self.avatar.setPixmap(icon_pixmap(name, color, 16))

    def set_text(self, text: str) -> None:
        """به‌روزرسانی متن (برای حباب «در حال نوشتن…»)."""
        self.label.setText(text)
        self.updateGeometry()

    def text(self) -> str:
        """متن فعلی حباب."""
        return self.label.text()

    def set_tools(self, tools: list[str]) -> None:
        """نمایش ابزارهایی که برای این پاسخ استفاده شده‌اند."""
        if not tools:
            self.tools_label.hide()
            return
        self.tools_label.setText(" · ".join(tools))
        self.tools_label.show()

    def apply_max_width(self, width: int) -> None:
        """
        تعیین بیشینهٔ عرض متن.

        در سبک ChatGPT خودِ ردیف تمام‌عرض است ولی ستون متن برای
        خوانایی محدود می‌شود؛ خط خیلی بلند سخت خوانده می‌شود.
        """
        limit = max(320, int(width))
        self.label.setMaximumWidth(limit)
        # گام‌های ابزار باید با ستون متن هم‌تراز بمانند؛ وگرنه کارت‌ها
        # تمام‌عرض کشیده می‌شوند و پاسخ به‌هم‌ریخته به نظر می‌رسد.
        self.tool_trail.setMaximumWidth(limit)
        self.updateGeometry()


#: نام فنی ابزارهایی که دستیار می‌تواند صدا بزند. برای نشان‌دادن نام
#: خوانا در فهرست گام‌ها به کار می‌رود. اگر ابزاری اینجا نباشد، نامش
#: خام نمایش داده می‌شود — چیزی پنهان نمی‌ماند، فقط زیبا نیست.
TOOL_NAME_KEYS: tuple[str, ...] = (
    "get_current_price",
    "get_ticker",
    "get_ohlcv",
    "get_multi_timeframe_data",
    "calculate_indicator",
    "calculate_multiple_indicators",
    "get_volume",
    "get_orderbook",
    "detect_trend",
    "detect_market_structure",
    "find_support_resistance",
    "calculate_risk",
    "get_engine_signal",
    "forecast_next_timeframe",
    "omniroute_status",
    "omniroute_models",
)


#: حالت‌های گفت‌وگو. کلید به مدل می‌رود، برچسب از فایل ترجمه می‌آید.
#: حالت روی «چه‌کاری» اثر می‌گذارد نه «چه‌قابلیتی» — همهٔ ابزارها در هر
#: حالت در دسترس‌اند؛ فقط لحن و تمرکز پاسخ عوض می‌شود.
CHAT_MODES: tuple[str, ...] = ("general", "analysis", "signal", "learn")

DEFAULT_CHAT_MODE = "general"


class ChatPage(BasePage):
    """صفحهٔ چت با دستیار هوش مصنوعی."""

    #: کاربر پیامی فرستاد (متن پیام)
    message_sent = Signal(str)
    #: کاربر روی دکمهٔ اقدام پیشنهادی کلیک کرد (دیکشنری اقدام)
    action_requested = Signal(dict)
    #: کاربر گفت‌وگو را پاک کرد
    chat_cleared = Signal()
    #: کاربر گفت‌وگویی را از تاریخچه انتخاب کرد (شناسه)
    conversation_selected = Signal(int)
    #: کاربر گفت‌وگویی را حذف کرد (شناسه)
    conversation_deleted = Signal(int)
    #: کاربر گفت‌وگوی تازه خواست
    new_conversation_requested = Signal()
    #: کاربر نام گفت‌وگو را عوض کرد (شناسه، عنوان تازه)
    conversation_renamed = Signal(int, str)

    title_key = "nav.chat"
    subtitle_key = "chat.subtitle"

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._bubbles: list[ChatBubble] = []
        self._theme: Any = None
        self._pending_bubble: ChatBubble | None = None
        #: متنی که تا این لحظه به‌صورت جریانی در حباب انتظار نشسته است
        self._streamed = ""
        self._pending_action: dict[str, Any] | None = None
        self._suggestion_buttons: list[Any] = []
        super().__init__(translator, parent)

    # ------------------------------------------------------------------
    # ساخت رابط
    # ------------------------------------------------------------------
    def build(self) -> None:
        """چیدمان: ستون تاریخچه در کنار ناحیهٔ گفت‌وگو."""
        self.clear_button = make_button(self.tr_.tr("chat.clear"), role="ghost")
        self.header.add_action(self.clear_button)
        self.clear_button.clicked.connect(self.clear_conversation)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self._build_history_panel())
        self.splitter.addWidget(self._build_chat_panel())
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([250, 750])
        self.layout_root().addWidget(self.splitter, 1)

        self._show_welcome()

    def _build_history_panel(self) -> QWidget:
        """ستون کناری: فهرست گفت‌وگوها مانند ChatGPT."""
        panel = QWidget()
        panel.setMinimumWidth(200)
        panel.setMaximumWidth(340)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)

        self.new_chat_button = make_button(self.tr_.tr("chat.new_chat"), primary=True)
        self.new_chat_button.clicked.connect(self.new_conversation_requested.emit)
        layout.addWidget(self.new_chat_button)

        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText(self.tr_.tr("chat.search_history"))
        self.history_search.setClearButtonEnabled(True)
        self.history_search.textChanged.connect(self._filter_history)
        layout.addWidget(self.history_search)

        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(False)
        self.history_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._show_history_menu)
        self.history_list.itemClicked.connect(self._on_history_clicked)
        layout.addWidget(self.history_list, 1)

        self.history_hint = QLabel(self.tr_.tr("chat.history_empty"))
        self.history_hint.setProperty("role", "muted")
        self.history_hint.setWordWrap(True)
        layout.addWidget(self.history_hint)
        return panel

    def _build_chat_panel(self) -> QWidget:
        """ناحیهٔ اصلی: نوار زمینه، پیام‌ها و جعبهٔ ورودی."""
        panel = QWidget()
        root = QVBoxLayout(panel)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # ---- نوار زمینه: نماد و تایم‌فریمی که گفت‌وگو دربارهٔ آن است ----
        context_row = QHBoxLayout()
        self.symbol_label = QLabel(self.tr_.tr("common.symbol"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.setEditable(True)
        self.symbol_combo.setMinimumWidth(180)
        self.symbol_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = self.symbol_combo.completer()
        if completer is not None:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)

        self.timeframe_label = QLabel(self.tr_.tr("common.timeframe"))
        self.timeframe_combo = QComboBox()
        for timeframe in SUPPORTED_TIMEFRAMES:
            self.timeframe_combo.addItem(timeframe.code, timeframe.code)
        default_index = self.timeframe_combo.findData("4h")
        if default_index >= 0:
            self.timeframe_combo.setCurrentIndex(default_index)

        context_row.addWidget(self.symbol_label)
        context_row.addWidget(self.symbol_combo)
        context_row.addWidget(self.timeframe_label)
        context_row.addWidget(self.timeframe_combo)
        context_row.addStretch(1)

        # ---- انتخاب سریع حالت گفت‌وگو ----
        mode_row = QHBoxLayout()
        self.mode_label = QLabel(self.tr_.tr("chat.mode"))
        self.mode_chips = ChipBar(exclusive=True)
        self.mode_chips.set_options([(key, self.tr_.tr(f"chat.mode_{key}")) for key in CHAT_MODES])
        self.mode_chips.set_selection([DEFAULT_CHAT_MODE])
        mode_row.addWidget(self.mode_label)
        mode_row.addWidget(self.mode_chips)
        mode_row.addStretch(1)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        context_row.addWidget(self.status_label)
        root.addLayout(context_row)
        root.addLayout(mode_row)

        # ---- ناحیهٔ پیام‌ها ----
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(0, 8, 0, 8)
        self.messages_layout.setSpacing(0)
        self.messages_layout.addStretch(1)
        self.scroll.setWidget(self.messages_widget)
        root.addWidget(self.scroll, 1)

        # ---- دکمهٔ اقدام پیشنهادی ----
        self.action_button = make_button("", role="success")
        self.action_button.hide()
        self.action_button.clicked.connect(self._on_action_clicked)
        root.addWidget(self.action_button)

        # ---- میان‌برها ----
        self.suggestions_row = QHBoxLayout()
        self.suggestions_row.setSpacing(6)
        self._build_suggestions()
        root.addLayout(self.suggestions_row)

        # ---- جعبهٔ ورودی ----
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.input = ChatInput()
        self.input.setPlaceholderText(self.tr_.tr("chat.placeholder"))
        self.input.returnPressed.connect(self.send_current)
        self.send_button = make_button(self.tr_.tr("chat.send"), primary=True)
        self.send_button.clicked.connect(self.send_current)
        self.send_button.setMinimumHeight(INPUT_MIN_HEIGHT)
        input_row.addWidget(self.input, 1)
        input_row.addWidget(self.send_button)
        root.addLayout(input_row)

        self.disclaimer = QLabel(self.tr_.tr("chat.disclaimer"))
        self.disclaimer.setProperty("role", "muted")
        self.disclaimer.setWordWrap(True)
        root.addWidget(self.disclaimer)
        return panel

    def _build_suggestions(self) -> None:
        """ساخت دکمه‌های پرسش آماده."""
        for button in self._suggestion_buttons:
            self.suggestions_row.removeWidget(button)
            button.deleteLater()
        self._suggestion_buttons.clear()

        for key in ("chat.suggest_price", "chat.suggest_trend", "chat.suggest_signal", "chat.suggest_risk"):
            text = self.tr_.tr(key)
            button = make_button(text, role="ghost")
            button.clicked.connect(lambda _=False, value=text: self._use_suggestion(value))
            self.suggestions_row.addWidget(button)
            self._suggestion_buttons.append(button)
        self.suggestions_row.addStretch(1)

    def _use_suggestion(self, text: str) -> None:
        """قرار دادن پرسش آماده در جعبهٔ ورودی و ارسال آن."""
        self.input.setText(text)
        self.send_current()

    # ------------------------------------------------------------------
    # تاریخچهٔ گفت‌وگوها
    # ------------------------------------------------------------------
    def set_conversations(self, conversations: list[dict[str, Any]]) -> None:
        """
        پر کردن ستون تاریخچه.

        هر ردیف عنوان گفت‌وگو و زمان آخرین به‌روزرسانی را نشان می‌دهد.
        شناسهٔ گفت‌وگو در دادهٔ ردیف نگهداری می‌شود.
        """
        self.history_list.clear()
        for conversation in conversations or []:
            title = conversation.get("title") or self.tr_.tr("chat.untitled")
            if conversation.get("pinned"):
                title = f"📌  {title}"
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, int(conversation.get("id", 0)))
            item.setToolTip(title)
            item.setSizeHint(QSize(0, 34))
            self.history_list.addItem(item)
        self.history_hint.setVisible(self.history_list.count() == 0)
        self._filter_history(self.history_search.text())

    def select_conversation(self, conversation_id: int) -> None:
        """برجسته کردن گفت‌وگوی فعال در فهرست."""
        for index in range(self.history_list.count()):
            item = self.history_list.item(index)
            if int(item.data(Qt.ItemDataRole.UserRole) or 0) == int(conversation_id):
                self.history_list.setCurrentItem(item)
                return
        self.history_list.clearSelection()

    def _filter_history(self, text: str) -> None:
        """پنهان کردن ردیف‌هایی که با عبارت جست‌وجو نمی‌خوانند."""
        needle = (text or "").strip().casefold()
        for index in range(self.history_list.count()):
            item = self.history_list.item(index)
            item.setHidden(bool(needle) and needle not in item.text().casefold())

    def _on_history_clicked(self, item: QListWidgetItem) -> None:
        """باز کردن گفت‌وگوی انتخاب‌شده."""
        conversation_id = int(item.data(Qt.ItemDataRole.UserRole) or 0)
        if conversation_id:
            self.conversation_selected.emit(conversation_id)

    def _show_history_menu(self, position: Any) -> None:
        """منوی راست‌کلیک: تغییر نام و حذف."""
        item = self.history_list.itemAt(position)
        if item is None:
            return
        conversation_id = int(item.data(Qt.ItemDataRole.UserRole) or 0)
        if not conversation_id:
            return

        menu = QMenu(self)
        rename_action = menu.addAction(self.tr_.tr("chat.rename"))
        delete_action = menu.addAction(self.tr_.tr("chat.delete"))
        chosen = menu.exec(self.history_list.mapToGlobal(position))
        if chosen == delete_action:
            self.conversation_deleted.emit(conversation_id)
        elif chosen == rename_action:
            self._start_rename(item, conversation_id)

    def _start_rename(self, item: QListWidgetItem, conversation_id: int) -> None:
        """گرفتن نام تازه از کاربر."""
        from PySide6.QtWidgets import QInputDialog

        title, accepted = QInputDialog.getText(
            self,
            self.tr_.tr("chat.rename"),
            self.tr_.tr("chat.rename_prompt"),
            text=item.text().replace("📌  ", ""),
        )
        if accepted and title.strip():
            self.conversation_renamed.emit(conversation_id, title.strip())

    def load_messages(self, messages: list[dict[str, Any]]) -> None:
        """
        نمایش پیام‌های یک گفت‌وگوی ذخیره‌شده.

        صفحه ابتدا پاک می‌شود، سپس پیام‌ها بدون ارسال دوباره به مدل روی
        صفحه چیده می‌شوند.
        """
        self._remove_all_bubbles()
        for message in messages or []:
            role = str(message.get("role", "user"))
            if role == "system":
                continue
            bubble = self.add_message(str(message.get("content", "")), is_user=role == "user")
            tools = message.get("tools") or []
            if tools:
                bubble.set_tools([str(t) for t in tools])
        if not self._bubbles:
            self._show_welcome()
        self.hide_action()

    # ------------------------------------------------------------------
    # پیام‌ها
    # ------------------------------------------------------------------
    def _bubble_alignment(self, is_user: bool) -> Qt.AlignmentFlag:
        """
        تعیین سمت حباب بر اساس جهت زبان.

        در فارسی پیام کاربر سمت راست است و در انگلیسی هم سمت راست — ولی
        «راست» در چیدمان RTL معنای معکوس دارد، پس صریح تعیین می‌شود.
        """
        if self.tr_.language == "fa":
            return Qt.AlignmentFlag.AlignLeft if is_user else Qt.AlignmentFlag.AlignRight
        return Qt.AlignmentFlag.AlignRight if is_user else Qt.AlignmentFlag.AlignLeft

    def add_message(self, text: str, *, is_user: bool) -> ChatBubble:
        """افزودن یک پیام به گفت‌وگو."""
        bubble = ChatBubble(text, is_user=is_user)
        self._label_bubble(bubble, is_user)
        bubble.apply_max_width(self._bubble_width())
        # ردیف‌ها تمام‌عرض‌اند (سبک ChatGPT)، پس دیگر تراز چپ/راست نمی‌دهیم
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        self._bubbles.append(bubble)
        self._scroll_to_bottom()
        return bubble

    def _label_bubble(self, bubble: ChatBubble, is_user: bool) -> None:
        """نوشتن نام گوینده و نشان او روی یک ردیف پیام."""
        key = "chat.you" if is_user else "chat.assistant"
        bubble.set_author(self.tr_.tr(key))
        bubble.set_avatar_icon("user" if is_user else "robot", self._avatar_color(is_user))

    def _avatar_color(self, is_user: bool) -> str:
        """رنگ نشان گوینده از پوستهٔ جاری."""
        theme = getattr(self, "_theme", None)
        if theme is None:
            return "#e2e8f0"
        colors = theme.colors
        return colors.primary_text if is_user else colors.accent

    def _bubble_width(self) -> int:
        """عرض مجاز حباب بر اساس عرض فعلی ناحیهٔ گفت‌وگو."""
        available = self.scroll.viewport().width() if hasattr(self, "scroll") else 0
        if available <= 0:
            available = 760
        # ستون متن؛ کمی از عرض کل کمتر تا خطوط بیش از حد بلند نشوند
        return int(available * BUBBLE_WIDTH_RATIO)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        """با تغییر اندازهٔ پنجره، عرض حباب‌ها هم به‌روز می‌شود."""
        super().resizeEvent(event)
        width = self._bubble_width()
        for bubble in self._bubbles:
            bubble.apply_max_width(width)

    def _scroll_to_bottom(self) -> None:
        """پیمایش خودکار به آخرین پیام."""
        bar = self.scroll.verticalScrollBar()
        if bar is not None:
            # با تأخیر یک چرخهٔ رویداد، چون ارتفاع حباب هنوز محاسبه نشده
            QTimer.singleShot(0, lambda: bar.setValue(bar.maximum()))

    def _show_welcome(self) -> None:
        """پیام خوش‌آمد اولیه."""
        self.add_message(self.tr_.tr("chat.welcome"), is_user=False)

    def send_current(self) -> None:
        """ارسال محتوای جعبهٔ ورودی."""
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.add_message(text, is_user=True)
        self.hide_action()
        self.message_sent.emit(text)

    def begin_reply(self) -> None:
        """نمایش حباب «در حال فکر کردن…» تا رسیدن پاسخ."""
        self.set_busy(True)
        # بافر جریانِ نوبت قبل باید خالی شود وگرنه پاسخ‌ها به هم می‌چسبند
        self._streamed = ""
        self._pending_bubble = self.add_message(self.tr_.tr("chat.thinking"), is_user=False)

    def update_progress(self, text: str) -> None:
        """به‌روزرسانی حباب در حال انتظار با نام ابزار در حال اجرا."""
        if self._pending_bubble is not None:
            self._pending_bubble.set_text(text)
            self._scroll_to_bottom()

    def tool_started(self, name: str, arguments: dict[str, Any] | None = None) -> None:
        """
        اعلام شروع اجرای یک ابزار روی حباب انتظار.

        تا وقتی هیچ متنی جریان نیافته، خودِ فهرست گام‌ها نقش نشانگر
        زنده‌بودن را بازی می‌کند؛ پیش‌تر کاربر در همین فاصله فقط یک
        «در حال فکر کردن…» بی‌حرکت می‌دید.
        """
        if self._pending_bubble is None:
            return
        trail = self._pending_bubble.tool_trail
        trail.set_display_names(self._tool_display_names())
        trail.begin_step(name, arguments)
        self._scroll_to_bottom()

    def tool_finished(
        self,
        name: str,
        *,
        ok: bool,
        observation: str = "",
        arguments: dict[str, Any] | None = None,
    ) -> None:
        """ثبت نتیجهٔ یک ابزار روی حباب انتظار."""
        if self._pending_bubble is None:
            return
        trail = self._pending_bubble.tool_trail
        trail.set_display_names(self._tool_display_names())
        trail.finish_step(name, ok=ok, observation=observation, arguments=arguments)
        self._scroll_to_bottom()

    def _tool_display_names(self) -> dict[str, str]:
        """
        نام خوانای ابزارها از فایل ترجمه.

        کلید غایب یعنی ابزار تازه‌ای اضافه شده که هنوز ترجمه ندارد؛ در
        آن حالت نام فنی نمایش داده می‌شود تا چیزی پنهان نماند.
        """
        names: dict[str, str] = {}
        for key in TOOL_NAME_KEYS:
            label = self.tr_.tr(f"chat.tools.{key}")
            if label and not label.endswith(f"tools.{key}"):
                names[key] = label
        return names

    def stream_delta(self, delta: str, replace: bool = False) -> None:
        """
        افزودن تکه‌ای از پاسخ در حال تایپ به حباب انتظار.

        `replace=True` یعنی «هرچه نوشته‌ای را پاک کن» — وقتی زنجیرهٔ
        جایگزینی سراغ سرویس دیگری می‌رود لازم است، وگرنه پاسخ دو مدل به
        هم می‌چسبد.

        این متد باید فقط از نخ رابط کاربری صدا زده شود؛ کنترلر با تایمر
        این را تضمین می‌کند.
        """
        if self._pending_bubble is None:
            return
        if replace:
            self._streamed = delta
        else:
            self._streamed += delta
        # تا پیش از رسیدن اولین تکه، همان «در حال فکر کردن…» بماند
        if self._streamed:
            self._pending_bubble.set_text(self._streamed)
            self._scroll_to_bottom()

    @property
    def streamed_text(self) -> str:
        """متنی که تا این لحظه به‌صورت جریانی نمایش داده شده است."""
        return self._streamed

    def finish_reply(self, text: str, tools: list[str] | None = None) -> None:
        """
        جایگزینی حباب انتظار با پاسخ نهایی.

        اگر فهرست گام‌های زنده پر شده باشد، خط متنی ابزارها نوشته
        نمی‌شود؛ وگرنه همان اطلاعات دو بار زیر پاسخ تکرار می‌شد.
        """
        self._streamed = ""
        if self._pending_bubble is not None:
            self._pending_bubble.set_text(text)
            if not self._pending_bubble.tool_trail.steps():
                self._pending_bubble.set_tools(tools or [])
            self._pending_bubble = None
        else:
            bubble = self.add_message(text, is_user=False)
            bubble.set_tools(tools or [])
        self.set_busy(False)
        self._scroll_to_bottom()

    def fail_reply(self, message: str) -> None:
        """نمایش خطا در همان حباب انتظار."""
        self.finish_reply(message)

    def set_busy(self, busy: bool) -> None:
        """قفل کردن ورودی هنگام انتظار پاسخ."""
        self.input.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        self.send_button.setText(
            self.tr_.tr("chat.sending") if busy else self.tr_.tr("chat.send")
        )
        for button in self._suggestion_buttons:
            button.setEnabled(not busy)

    # ------------------------------------------------------------------
    # اقدام پیشنهادی
    # ------------------------------------------------------------------
    def show_action(self, action: dict[str, Any]) -> None:
        """
        نمایش دکمهٔ اقدامی که دستیار پیشنهاد داده است.

        هیچ اقدامی خودکار اجرا نمی‌شود؛ این تصمیم عمدی است تا مدل نتواند
        بدون تأیید کاربر کاری انجام دهد.
        """
        if not action or not action.get("type"):
            self.hide_action()
            return
        self._pending_action = action
        label = action.get("label") or self.tr_.tr("chat.run_action")
        self.action_button.setText(f"▶  {label}")
        self.action_button.show()

    def hide_action(self) -> None:
        """پنهان کردن دکمهٔ اقدام."""
        self._pending_action = None
        self.action_button.hide()

    def _on_action_clicked(self) -> None:
        """اجرای اقدام پس از تأیید کاربر."""
        if not self._pending_action:
            return
        action = dict(self._pending_action)
        self.hide_action()
        self.action_requested.emit(action)

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    def set_status(self, text: str) -> None:
        """نمایش نام سرویس و مدل فعال در بالای صفحه."""
        self.status_label.setText(text)

    def set_symbols(self, symbols: list[str]) -> None:
        """پر کردن فهرست نمادها برای زمینهٔ گفت‌وگو."""
        current = self.symbol_combo.currentText()
        self.symbol_combo.blockSignals(True)
        self.symbol_combo.clear()
        self.symbol_combo.addItems(symbols)
        if current and current in symbols:
            self.symbol_combo.setCurrentText(current)
        self.symbol_combo.blockSignals(False)

    def set_context(self, symbol: str = "", timeframe: str = "") -> None:
        """تعیین نماد و تایم‌فریم گفت‌وگو از بیرون (مثلاً از مدال ارز)."""
        if symbol:
            self.symbol_combo.setCurrentText(symbol)
        if timeframe:
            index = self.timeframe_combo.findData(timeframe)
            if index >= 0:
                self.timeframe_combo.setCurrentIndex(index)

    def current_context(self) -> dict[str, str]:
        """زمینهٔ فعلی گفت‌وگو برای ارسال به مدل."""
        return {
            "symbol": self.symbol_combo.currentText().strip(),
            "timeframe": str(self.timeframe_combo.currentData() or ""),
            "mode": self.current_mode(),
        }

    def current_mode(self) -> str:
        """حالت انتخاب‌شدهٔ گفت‌وگو (همیشه یک مقدار معتبر)."""
        selection = self.mode_chips.selection()
        return selection[0] if selection else DEFAULT_CHAT_MODE

    def _remove_all_bubbles(self) -> None:
        """برداشتن همهٔ حباب‌ها از صفحه."""
        for bubble in self._bubbles:
            self.messages_layout.removeWidget(bubble)
            bubble.deleteLater()
        self._bubbles.clear()
        self._pending_bubble = None

    def clear_conversation(self) -> None:
        """پاک کردن همهٔ پیام‌ها و شروع گفت‌وگوی تازه."""
        self._remove_all_bubbles()
        self.hide_action()
        self._show_welcome()
        self.chat_cleared.emit()

    @property
    def message_count(self) -> int:
        """تعداد حباب‌های نمایش‌داده‌شده."""
        return len(self._bubbles)

    def apply_theme(self, theme: Any) -> None:
        """
        هم‌رنگ‌کردن نشان گویندگان با پوستهٔ جاری.

        آواتارها آیکن برداری‌اند، پس با هر تعویض پوسته باید دوباره با رنگ
        تازه ترسیم شوند؛ وگرنه در پوستهٔ روشن محو می‌شوند.
        """
        self._theme = theme
        for bubble in self._bubbles:
            is_user = bubble.property("role") == "chat_user"
            bubble.set_avatar_icon("user" if is_user else "robot", self._avatar_color(is_user))
            # رنگ نشانهٔ گام‌ها با QSS نمی‌آید (روی برچسب نشسته است) و
            # باید دستی تازه شود، درست مثل رنگ سلول‌های جدول سیگنال‌ها.
            bubble.tool_trail.apply_theme(theme)

    def retranslate(self) -> None:
        """بازسازی متن‌ها پس از تغییر زبان."""
        super().retranslate()
        self.mode_label.setText(self.tr_.tr("chat.mode"))
        self.mode_chips.set_labels({key: self.tr_.tr(f"chat.mode_{key}") for key in CHAT_MODES})
        self.clear_button.setText(self.tr_.tr("chat.clear"))
        self.symbol_label.setText(self.tr_.tr("common.symbol"))
        self.timeframe_label.setText(self.tr_.tr("common.timeframe"))
        self.input.setPlaceholderText(self.tr_.tr("chat.placeholder"))
        self.send_button.setText(self.tr_.tr("chat.send"))
        self.disclaimer.setText(self.tr_.tr("chat.disclaimer"))
        self.new_chat_button.setText(self.tr_.tr("chat.new_chat"))
        self.history_search.setPlaceholderText(self.tr_.tr("chat.search_history"))
        self.history_hint.setText(self.tr_.tr("chat.history_empty"))
        # نام خوانای ابزارها هم ترجمه است و با تغییر زبان باید عوض شود
        names = self._tool_display_names()
        for bubble in self._bubbles:
            bubble.tool_trail.set_display_names(names)
        self._build_suggestions()
