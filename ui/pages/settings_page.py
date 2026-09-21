"""
صفحه تنظیمات.

نکته حیاتی (بند ۴۴ سند پروژه): تنظیمات کاربر هرگز با مقادیر پیش‌فرض
بازنویسی نمی‌شود. این صفحه فقط مقادیر ذخیره‌شده را می‌خواند و تغییرات
صریح کاربر را برمی‌گرداند.

کلیدهای API در این صفحه وارد می‌شوند ولی **در پایگاه داده ذخیره
نمی‌شوند**؛ مقصد آن‌ها `SecretStore` است.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSlider,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai.providers.catalog import PROVIDER_PRESETS, get_preset
from ai.providers.free_models import (
    TIER_FREE,
    classify_model,
    known_free_models,
    pick_default_model,
    sort_models,
)
from app.core.email_service import SMTP_PRESETS
from localization import Translator
from ui.pages.markets_page import SORT_MODES
from market.exchange_catalog import get_exchange, selectable_choices
from ui.pages.base_page import BasePage
from ui.themes import ThemeManager
from ui.themes.catalog import resolve_key as resolve_theme_key
from ui.themes.fonts import is_available as font_is_available, list_fonts, resolve_font_key
from ui.widgets.responsive_grid import ResponsiveGrid
from ui.widgets.theme_card import ThemeCard
from ui.widgets.theme_editor import ThemeEditor
from ui.widgets.theme_preview import ThemePreview
from ui.widgets import make_button


class SettingsPage(BasePage):
    """صفحه پیکربندی برنامه."""

    #: وقتی کاربر صرافی را عوض می‌کند (کلید صرافی)
    exchange_changed = Signal(str)
    #: کاربر خواست حساب صرافی تازه‌ای اضافه کند
    account_add_requested = Signal()
    #: آزمایش اتصال یک حساب (شناسه)
    account_test_requested = Signal(int)
    #: حذف یک حساب (شناسه)
    account_remove_requested = Signal(int)
    # انتخاب صرافیِ فعال برای کیف پول
    account_activate_requested = Signal(int)
    #: کاربر روی دکمه‌ای زد ولی هیچ حسابی انتخاب نشده بود
    account_selection_blocked = Signal()
    #: وقتی کاربر سرویس هوش مصنوعی را عوض می‌کند (کلید سرویس)
    ai_provider_changed = Signal(str)

    #: کاربر پوسته‌ای را برگزید — باید بی‌درنگ اعمال شود، نه پس از ذخیره
    theme_preview_requested = Signal(str)
    # این دو هم مثل پوسته باید بی‌درنگ دیده شوند، نه پس از «ذخیره»
    font_scale_changed = Signal(int)
    compact_mode_changed = Signal(bool)
    #: کاربر خانوادهٔ قلم را عوض کرد (شناسهٔ قلم) — بی‌درنگ اعمال می‌شود
    font_family_changed = Signal(str)
    #: توکن‌های پوسته در ویرایشگر تغییر کرد — پیش‌نمایش زنده
    theme_tokens_changed = Signal(dict)
    #: کاربر خواست پوستهٔ ویرایش‌شده را ذخیره کند
    custom_theme_save_requested = Signal()
    #: کاربر خواست پوستهٔ سفارشی فعال را حذف کند
    custom_theme_delete_requested = Signal()

    #: کلید ترجمهٔ زبانه‌ها به همان ترتیبی که ساخته می‌شوند.
    #: تنها منبع حقیقت؛ پیش‌تر فهرست بازترجمه از فهرست ساخت عقب مانده بود
    #: و برچسب‌ها با تغییر زبان یک واحد می‌لغزیدند.
    TAB_KEYS: tuple[str, ...] = (
        "settings.general",
        "settings.appearance.title",
        "settings.exchange",
        "settings.ai",
        "settings.risk",
        "settings.display",
        "settings.performance",
        "settings.security.title",
        "settings.backup",
    )
    #: درخواست تغییر رمز عبور: (رمز فعلی، رمز جدید، تکرار رمز جدید)
    password_change_requested = Signal(str, str, str)
    #: درخواست ذخیرهٔ پروفایل: (نام نمایشی، ایمیل)
    profile_save_requested = Signal(str, str)
    #: باطل‌کردن یک نشست مشخص
    session_revoke_requested = Signal(int)
    #: خروج از همهٔ دستگاه‌های دیگر
    revoke_others_requested = Signal()
    #: کاربر دکمهٔ پایان نشست را بدون انتخاب سطر زده است
    session_revoke_blocked = Signal()
    #: ذخیرهٔ تنظیمات ایمیل: دیکشنری مقادیر + رمز
    email_save_requested = Signal(dict, str)
    #: آزمایش اتصال به سرور ایمیل
    email_test_requested = Signal()

    title_key = "nav.settings"
    subtitle_key = "settings.subtitle"

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._labels: dict[str, QLabel] = {}
        #: فهرست خام مدل‌های سرویس جاری، پیش از فیلتر و مرتب‌سازی
        self._available_models: list[str] = []
        super().__init__(translator, parent)

    def build(self) -> None:
        """ساخت زبانه‌های تنظیمات."""
        self.save_button = make_button(self.tr_.tr("common.save"), primary=True)
        self.header.add_action(self.save_button)

        self.tabs = QTabWidget()
        builders = (
            self._build_general,
            self._build_appearance,
            self._build_exchange,
            self._build_ai,
            self._build_risk,
            self._build_display,
            self._build_performance,
            self._build_security,
            self._build_backup,
        )
        # ترتیب سازنده‌ها باید دقیقاً با TAB_KEYS بخواند؛ این ادعا اختلاف را
        # همان لحظهٔ ساخت لو می‌دهد نه بعداً موقع تغییر زبان.
        assert len(builders) == len(self.TAB_KEYS)
        for build, key in zip(builders, self.TAB_KEYS):
            self.tabs.addTab(build(), self.tr_.tr(key))
        self.layout_root().addWidget(self.tabs, 1)

        self.preserved_note = QLabel(self.tr_.tr("settings.settings_preserved"))
        self.preserved_note.setProperty("role", "muted")
        self.preserved_note.setWordWrap(True)
        self.layout_root().addWidget(self.preserved_note)

    def _form(self) -> tuple[QWidget, QFormLayout]:
        """ساخت یک ویجت فرم خالی."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        return widget, layout

    def _add_row(self, layout: QFormLayout, key: str, field: QWidget) -> QWidget:
        """افزودن سطر با برچسب ترجمه‌شده و ثبت آن برای تغییر زبان."""
        label = QLabel(self.tr_.tr(key))
        self._labels[key] = label
        layout.addRow(label, field)
        return field

    def _build_general(self) -> QWidget:
        """زبانه عمومی: زبان و پوسته."""
        widget, layout = self._form()
        self.language_combo = QComboBox()
        self.language_combo.addItem("فارسی", "fa")
        self.language_combo.addItem("English", "en")
        # انتخاب پوسته با نام. فهرست از خود سامانهٔ پوسته خوانده می‌شود،
        # پس افزودن پوستهٔ تازه نیازی به تغییر این صفحه ندارد.
        self.theme_combo = QComboBox()
        self._fill_theme_combo()

        self._add_row(layout, "settings.language", self.language_combo)
        self._add_row(layout, "settings.appearance.theme", self.theme_combo)

        self.theme_hint = QLabel(self.tr_.tr("settings.appearance.theme_hint"))
        self.theme_hint.setProperty("role", "faint")
        self.theme_hint.setWordWrap(True)
        layout.addRow("", self.theme_hint)

        # نوار پیش‌نمایش: کاربر پیش از تأیید، رنگ‌های پوسته را می‌بیند
        self.theme_preview = ThemePreview()
        self._add_row(layout, "settings.appearance.preview", self.theme_preview)
        self.theme_combo.currentIndexChanged.connect(self._update_theme_preview)
        self._update_theme_preview()

        # --- هشدارها ---
        #
        # اینجا و نه زبانهٔ جدا: دو گزینه است و زبانهٔ تازه برای دو کلید،
        # صفحه را شلوغ‌تر می‌کند بدون اینکه چیزی روشن‌تر شود. ساخت خود
        # هشدارها از صفحهٔ بازارها انجام می‌شود، جایی که نماد و قیمت
        # جلوی چشم کاربر است.
        self.alerts_enabled_check = QCheckBox()
        self.alerts_enabled_check.setChecked(True)
        self._add_row(layout, "alerts.enabled", self.alerts_enabled_check)

        self.alerts_sound_check = QCheckBox()
        self.alerts_sound_check.setChecked(True)
        self._add_row(layout, "settings.alerts_sound", self.alerts_sound_check)

        return widget

    def _fill_theme_combo(self) -> None:
        """
        پرکردن فهرست پوسته‌ها با نام محلی‌شده.

        نام از فهرست پوسته می‌آید و اگر ترجمه‌ای برایش تعریف شده باشد،
        ترجمه ترجیح داده می‌شود.
        """
        current = self.theme_combo.currentData()
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        for theme in ThemeManager.available():
            label = self.tr_.tr(f"settings.themes.{theme.key}", "")
            if not label or label.startswith("settings."):
                label = theme.name_fa if self.tr_.language == "fa" else theme.name_en
            self.theme_combo.addItem(label, theme.key)
        position = self.theme_combo.findData(current)
        if position >= 0:
            self.theme_combo.setCurrentIndex(position)
        self.theme_combo.blockSignals(False)

    def _fill_font_combo(self) -> None:
        """
        پرکردن فهرست قلم‌ها با نام محلی‌شده.

        هر گزینه با **قلم خودش** نمایش داده می‌شود تا کاربر پیش از انتخاب
        ببیند چه شکلی است؛ فهرست متنی ساده اینجا بی‌فایده بود.
        """
        current = self.font_family_combo.currentData()
        self.font_family_combo.blockSignals(True)
        self.font_family_combo.clear()
        for choice in list_fonts():
            label = self.tr_.tr(f"settings.fonts.{choice.key}", "")
            if not label or label.startswith("settings."):
                label = choice.name_fa if self.tr_.language == "fa" else choice.name_en
            # قلمی که همراه برنامه نیست (ایران‌سنس) ممکن است روی این
            # دستگاه نباشد. به‌جای گزینه‌ای که بی‌صدا کار نمی‌کند، صریح
            # می‌گوییم نصب نیست و راهنمایش را در tooltip می‌گذاریم.
            available = font_is_available(choice.key)
            if not available:
                label = f"{label} — {self.tr_.tr('settings.font_not_installed')}"
            self.font_family_combo.addItem(label, choice.key)
            index = self.font_family_combo.count() - 1
            if not available:
                self.font_family_combo.setItemData(
                    index,
                    self.tr_.tr("settings.font_missing_hint"),
                    Qt.ItemDataRole.ToolTipRole,
                )
            if choice.families and available:
                preview = QFont(choice.families[0])
                self.font_family_combo.setItemData(index, preview, Qt.ItemDataRole.FontRole)
        position = self.font_family_combo.findData(current)
        if position >= 0:
            self.font_family_combo.setCurrentIndex(position)
        self.font_family_combo.blockSignals(False)

    def _on_font_scale_changed(self, value: int) -> None:
        """
        همگام‌سازی اسلایدر و عدد اندازهٔ متن، سپس اعلام تغییر.

        هر دو کنترل به همین متد وصل‌اند، پس بدون `blockSignals` یکدیگر را
        بی‌پایان صدا می‌زدند. سیگنال‌ها موقتاً بسته می‌شوند و مقدار یک بار
        به بیرون اعلام می‌شود.
        """
        value = int(value)
        for widget in (self.font_scale_slider, self.font_scale_spin):
            if widget.value() == value:
                continue
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        self.font_scale_changed.emit(value)

    def _on_font_family_selected(self) -> None:
        """اعلام تغییر قلم تا کنترلر بی‌درنگ اعمالش کند."""
        key = self.font_family_combo.currentData()
        if key:
            self.font_family_changed.emit(str(key))

    def select_font_family(self, key: str) -> None:
        """نشان‌دادن قلم فعال در فهرست، بدون برانگیختن سیگنال."""
        index = self.font_family_combo.findData(resolve_font_key(key))
        if index < 0:
            return
        self.font_family_combo.blockSignals(True)
        self.font_family_combo.setCurrentIndex(index)
        self.font_family_combo.blockSignals(False)

    def _update_theme_preview(self) -> None:
        """نمایش رنگ‌های پوستهٔ انتخاب‌شده در نوار پیش‌نمایش."""
        key = self.theme_combo.currentData()
        if key:
            self.theme_preview.show_theme(ThemeManager.tokens_for(key))

    def _build_appearance(self) -> QWidget:
        """
        زبانهٔ «ظاهر برنامه»: انتخاب پوسته با نام و پیش‌نمایش.

        پیش‌تر انتخاب پوسته یک فهرست کشویی ته زبانهٔ «عمومی» بود و کاربر
        پیدایش نمی‌کرد. حالا هر پوسته یک کارت جداگانه با نام، توضیح و
        نمونهٔ رنگ دارد و کلیک روی آن **بی‌درنگ** اعمال می‌شود.
        """
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(12)

        self.appearance_title = QLabel(self.tr_.tr("settings.appearance.pick_theme"))
        self.appearance_title.setProperty("role", "cardTitle")
        outer.addWidget(self.appearance_title)

        self.appearance_hint = QLabel(self.tr_.tr("settings.appearance.theme_hint"))
        self.appearance_hint.setProperty("role", "faint")
        self.appearance_hint.setWordWrap(True)
        outer.addWidget(self.appearance_hint)

        # شبکهٔ کارت‌ها. پیش‌تر `QGridLayout` با `index % 2` بود، یعنی
        # همیشه دو ستون — در پنجرهٔ بزرگ نیمی از عرض هدر می‌رفت و
        # کارت‌ها کشیده و بزرگ می‌شدند. حالا شمار ستون‌ها با عرض پنجره
        # عوض می‌شود: تا چهار ستون در حالت بزرگ و دست‌کم دو ستون در
        # باریک‌ترین حالت، و خود کارت‌ها نسبت ابعاد ثابت دارند.
        self._theme_cards: dict[str, ThemeCard] = {}
        self.theme_grid = ResponsiveGrid(
            min_columns=2, max_columns=4, item_min_width=150, spacing=10
        )
        cards: list[ThemeCard] = []
        for theme in ThemeManager.available():
            card = ThemeCard(theme, self._theme_name(theme), self._theme_description(theme))
            card.setMinimumWidth(132)
            # سقف عرض لازم است وگرنه در پنجرهٔ عریض، چهار کارت تمام عرض
            # را بین خود پخش می‌کنند و هر کدام پهن و کم‌ارتفاع می‌شود —
            # درست همان «پالت بزرگ» که کاربر از آن گله داشت. با سقف،
            # کارت‌ها کوچک و نزدیک به مربع می‌مانند و فضای اضافی به
            # حاشیه می‌رود.
            card.setMaximumWidth(200)
            card.selected.connect(self._on_theme_card_selected)
            cards.append(card)
            self._theme_cards[theme.key] = card
        self.theme_grid.set_widgets(cards)
        outer.addWidget(self.theme_grid)

        # اندازهٔ قلم و حالت فشرده هم «ظاهر» هستند. پیش‌تر در زبانهٔ
        # «نمایش» پنهان بودند و کاربر برای یک کار واحد بین دو زبانه
        # جابه‌جا می‌شد. هر دو اینجا و بی‌درنگ اعمال می‌شوند.
        self.appearance_layout_title = QLabel(self.tr_.tr("settings.appearance.layout"))
        self.appearance_layout_title.setProperty("role", "cardTitle")
        outer.addSpacing(6)
        outer.addWidget(self.appearance_layout_title)

        density = QWidget()
        density_form = QFormLayout(density)
        density_form.setContentsMargins(0, 0, 0, 0)
        density_form.setSpacing(10)
        density_form.setFormAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignTop)
        density_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)

        # انتخاب خانوادهٔ قلم. فهرست از سامانهٔ قلم خوانده می‌شود، پس
        # افزودن قلم تازه نیازی به تغییر این صفحه ندارد.
        self.font_family_combo = QComboBox()
        self._fill_font_combo()
        self.font_family_combo.currentIndexChanged.connect(self._on_font_family_selected)

        # اندازهٔ متن. کاربر گفت این ورودی «خراب است» و علامت‌هایش اذیت
        # می‌کند: یک اسپین‌باکس تنها، هم فلش‌های ریز داشت و هم برای
        # رسیدن از ۱۰۰ به ۱۴۰ باید هشت بار کلیک می‌شد. حالا اسلایدر کار
        # اصلی را می‌کند و عدد کنارش فقط مقدار را نشان می‌دهد (و اگر
        # کسی بخواهد، دقیق واردش می‌کند). هر دو یک مقدار را نشان
        # می‌دهند و همگام می‌مانند.
        self.font_scale_spin = QSpinBox()
        self.font_scale_spin.setRange(80, 160)
        self.font_scale_spin.setSingleStep(5)
        self.font_scale_spin.setSuffix(" %")
        self.font_scale_spin.setValue(100)
        self.font_scale_spin.setFixedWidth(92)
        self.font_scale_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.font_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_scale_slider.setRange(80, 160)
        self.font_scale_slider.setSingleStep(5)
        self.font_scale_slider.setPageStep(10)
        self.font_scale_slider.setTickInterval(20)
        self.font_scale_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.font_scale_slider.setValue(100)
        self.font_scale_slider.setMinimumWidth(160)

        font_scale_row = QWidget()
        font_scale_layout = QHBoxLayout(font_scale_row)
        font_scale_layout.setContentsMargins(0, 0, 0, 0)
        font_scale_layout.setSpacing(10)
        font_scale_layout.addWidget(self.font_scale_slider, 1)
        font_scale_layout.addWidget(self.font_scale_spin, 0)

        self.font_scale_spin.valueChanged.connect(self._on_font_scale_changed)
        self.font_scale_slider.valueChanged.connect(self._on_font_scale_changed)

        self.compact_check = QCheckBox()
        self.compact_check.toggled.connect(
            lambda checked: self.compact_mode_changed.emit(bool(checked))
        )

        self._add_row(density_form, "settings.appearance.font_family", self.font_family_combo)
        self._add_row(density_form, "settings.font_scale", font_scale_row)
        self._add_row(density_form, "settings.compact_mode", self.compact_check)

        self.font_family_hint = QLabel(self.tr_.tr("settings.appearance.font_hint"))
        self.font_family_hint.setProperty("role", "faint")
        self.font_family_hint.setWordWrap(True)
        density_form.addRow(self.font_family_hint)
        outer.addWidget(density)

        # --- ویرایشگر پیشرفتهٔ پوسته ---
        # کاربر خواست «همهٔ جزئیات ظاهری» قابل تغییر باشد. این بخش
        # جمع‌شونده است تا کسی که فقط می‌خواهد پوسته را عوض کند با دیواری
        # از اسلایدر روبه‌رو نشود.
        outer.addSpacing(6)
        self.editor_toggle = make_button(
            self.tr_.tr("settings.appearance.editor_show"), role="ghost", checkable=True
        )
        self.editor_toggle.toggled.connect(self._on_editor_toggled)
        outer.addWidget(self.editor_toggle, 0, Qt.AlignmentFlag.AlignLeft)

        self.theme_editor = ThemeEditor(self.tr_)
        self.theme_editor.setVisible(False)
        self.theme_editor.setMinimumHeight(320)
        self.theme_editor.overrides_changed.connect(self.theme_tokens_changed.emit)
        self.theme_editor.save_requested.connect(self.custom_theme_save_requested.emit)
        self.theme_editor.reset_requested.connect(self._on_editor_reset)
        outer.addWidget(self.theme_editor)

        self.delete_theme_button = make_button(
            self.tr_.tr("settings.editor.delete"), role="danger"
        )
        self.delete_theme_button.clicked.connect(self.custom_theme_delete_requested.emit)
        self.delete_theme_button.setVisible(False)
        outer.addWidget(self.delete_theme_button, 0, Qt.AlignmentFlag.AlignLeft)

        outer.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(widget)
        return scroll

    def _on_editor_toggled(self, expanded: bool) -> None:
        """باز و بستهٔ کردن ویرایشگر پوسته."""
        self.theme_editor.setVisible(bool(expanded))
        self._sync_editor_texts()

    def _on_editor_reset(self) -> None:
        """بازگرداندن توکن‌ها به پوستهٔ پایه و اعلام آن."""
        self.theme_editor.clear_overrides()

    def load_theme_editor(self, tokens: Any, overrides: dict[str, Any] | None = None) -> None:
        """نشاندن پوستهٔ فعال در ویرایشگر (از سوی کنترلر)."""
        self.theme_editor.load_theme(tokens, overrides or {})

    def set_custom_theme_active(self, active: bool) -> None:
        """
        نمایش یا پنهان‌کردن دکمهٔ حذف.

        فقط پوستهٔ سفارشی خودِ کاربر حذف‌شدنی است؛ پوسته‌های داخلی نه.
        """
        self.delete_theme_button.setVisible(bool(active))

    def refresh_theme_cards(self) -> None:
        """
        ساخت دوبارهٔ کارت‌های پوسته.

        پس از ذخیره یا حذف یک پوستهٔ سفارشی لازم است، وگرنه پوستهٔ تازهٔ
        کاربر تا راه‌اندازی بعدی در فهرست دیده نمی‌شود.
        """
        selected = self.theme_combo.currentData() if hasattr(self, "theme_combo") else ""
        self._theme_cards = {}
        cards: list[ThemeCard] = []
        for theme in ThemeManager.available():
            card = ThemeCard(theme, self._theme_name(theme), self._theme_description(theme))
            card.setMinimumWidth(132)
            card.setMaximumWidth(200)
            card.selected.connect(self._on_theme_card_selected)
            cards.append(card)
            self._theme_cards[theme.key] = card
        self.theme_grid.set_widgets(cards)
        self._fill_theme_combo()
        if selected:
            self.select_theme(str(selected))

    def _sync_editor_texts(self) -> None:
        """
        متن دکمهٔ باز/بستهٔ ویرایشگر بر پایهٔ حالت فعلی.

        ملاک، وضعیت انتخاب دکمه است نه `isVisible()`: تا وقتی صفحه
        نمایش داده نشده، همهٔ فرزندانش نامرئی‌اند و برچسب برعکس می‌شود.
        """
        key = (
            "settings.appearance.editor_hide"
            if self.editor_toggle.isChecked()
            else "settings.appearance.editor_show"
        )
        self.editor_toggle.setText(self.tr_.tr(key))

    def _theme_name(self, theme: Any) -> str:
        """نام محلی‌شدهٔ یک پوسته."""
        label = self.tr_.tr(f"settings.themes.{theme.key}", "")
        if not label or label.startswith("settings."):
            label = theme.name_fa if self.tr_.language == "fa" else theme.name_en
        return label

    def _theme_description(self, theme: Any) -> str:
        """توضیح کوتاه یک پوسته، اگر ترجمه‌ای داشته باشد."""
        text = self.tr_.tr(f"settings.theme_descriptions.{theme.key}", "")
        return "" if text.startswith("settings.") else text

    def _on_theme_card_selected(self, key: str) -> None:
        """
        کلیک روی کارت پوسته.

        هم فهرست کشویی زبانهٔ عمومی هماهنگ می‌شود و هم درخواست اعمال
        بی‌درنگ منتشر می‌گردد تا کاربر لازم نباشد «ذخیره» بزند.
        """
        self.select_theme(key)
        self.theme_preview_requested.emit(key)

    def select_theme(self, key: str) -> None:
        """هماهنگ‌کردن کارت‌ها و فهرست کشویی با پوستهٔ داده‌شده."""
        for card_key, card in getattr(self, "_theme_cards", {}).items():
            card.set_selected(card_key == key)
        index = self.theme_combo.findData(key)
        if index >= 0 and self.theme_combo.currentIndex() != index:
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentIndex(index)
            self.theme_combo.blockSignals(False)
            self._update_theme_preview()

    def _build_exchange(self) -> QWidget:
        """
        زبانه صرافی: انتخاب صرافی و کلیدهای آن.

        کاربر خواست بتواند میان صرافی‌ها جابه‌جا شود و کلید هر کدام
        جداگانه ذخیره و خودکار بارگذاری شود.
        """
        widget, layout = self._form()

        self.exchange_combo = QComboBox()
        for key, label in selectable_choices():
            self.exchange_combo.addItem(label, key)
        self.exchange_combo.currentIndexChanged.connect(self._on_exchange_changed)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setEchoMode(QLineEdit.EchoMode.Password)

        self._add_row(layout, "settings.select_exchange", self.exchange_combo)
        self._add_row(layout, "settings.api_key", self.api_key_input)
        self._add_row(layout, "settings.api_secret", self.api_secret_input)

        self.exchange_status = QLabel("")
        self.exchange_status.setProperty("role", "muted")
        self.exchange_status.setWordWrap(True)
        layout.addRow(self.exchange_status)

        self.key_hint = QLabel(self.tr_.tr("settings.credentials_stored_note"))
        self.key_hint.setProperty("role", "muted")
        self.key_hint.setWordWrap(True)
        layout.addRow(self.key_hint)

        # --- حساب‌های صرافی هر کاربر ---
        layout.addRow(self._build_accounts_panel())

        self._on_exchange_changed()
        return widget

    def _build_accounts_panel(self) -> QWidget:
        """
        بخش «حساب‌های صرافی».

        کلید کامل هرگز اینجا نمایش داده نمی‌شود؛ فقط نسخهٔ پوشیده. سرویس
        زیرین مقدار واقعی را رمزنگاری‌شده نگه می‌دارد.
        """
        panel = QFrame()
        panel.setProperty("role", "card")
        box = QVBoxLayout(panel)
        box.setContentsMargins(16, 12, 16, 12)
        box.setSpacing(8)

        header = QHBoxLayout()
        self.accounts_title = QLabel(self.tr_.tr("settings.accounts.title"))
        self.accounts_title.setProperty("role", "section")
        header.addWidget(self.accounts_title)
        header.addStretch(1)

        self.account_add_button = make_button(self.tr_.tr("settings.accounts.add"))
        self.account_add_button.clicked.connect(self.account_add_requested)
        header.addWidget(self.account_add_button)

        self.account_test_button = make_button(self.tr_.tr("settings.accounts.test"))
        self.account_test_button.clicked.connect(self._emit_account_test)
        header.addWidget(self.account_test_button)

        self.account_activate_button = make_button(
            self.tr_.tr("settings.accounts.activate"), primary=True
        )
        self.account_activate_button.clicked.connect(self._emit_account_activate)
        header.addWidget(self.account_activate_button)

        self.account_remove_button = make_button(self.tr_.tr("settings.accounts.remove"))
        self.account_remove_button.clicked.connect(self._emit_account_remove)
        header.addWidget(self.account_remove_button)
        box.addLayout(header)

        self.accounts_table = QTableWidget(0, 6)
        self.accounts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.accounts_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.accounts_table.verticalHeader().setVisible(False)
        self.accounts_table.setMaximumHeight(170)
        box.addWidget(self.accounts_table)

        self.accounts_note = QLabel(self.tr_.tr("settings.accounts.security_note"))
        self.accounts_note.setProperty("role", "faint")
        self.accounts_note.setWordWrap(True)
        box.addWidget(self.accounts_note)

        self._retranslate_accounts_headers()
        self.set_accounts([])
        return panel

    def _retranslate_accounts_headers(self) -> None:
        """عنوان ستون‌های جدول حساب‌ها."""
        self.accounts_table.setHorizontalHeaderLabels(
            [
                self.tr_.tr("settings.accounts.exchange"),
                self.tr_.tr("settings.accounts.label"),
                self.tr_.tr("settings.accounts.api_key"),
                self.tr_.tr("settings.accounts.status"),
                self.tr_.tr("settings.accounts.last_sync"),
                self.tr_.tr("settings.accounts.active"),
            ]
        )

    def set_accounts(self, accounts: list[dict]) -> None:
        """
        پرکردن جدول حساب‌های صرافی.

        ورودی همان دیکشنری سرویس است که عمداً `secret_ref` ندارد.
        """
        self._accounts = list(accounts or [])
        table = self.accounts_table
        table.setRowCount(len(self._accounts))

        for row, item in enumerate(self._accounts):
            status_key = str(item.get("status", "disconnected"))
            cells = [
                str(item.get("exchange", "")).upper(),
                str(item.get("label", "")),
                str(item.get("api_key_masked", "")),
                self.tr_.tr(f"settings.accounts.statuses.{status_key}", status_key),
                str(item.get("last_sync_at") or "—"),
                # علامت روشن برای حسابی که کیف پول از آن می‌خواند
                "●" if item.get("is_default") else "",
            ]
            for column, text in enumerate(cells):
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, column, cell)

        if self._accounts:
            # روی حساب فعال بایست تا کاربر ببیند کیف پول از کدام می‌خواند
            active = next(
                (i for i, a in enumerate(self._accounts) if a.get("is_default")), 0
            )
            # setCurrentCell به‌جای selectRow: در چیدمان راست‌به‌چپ
            # selectRow سطر «جاری» را تنظیم نمی‌کند و selected_account_id
            # صفر برمی‌گرداند، یعنی دکمه‌های آزمایش/فعال‌سازی/حذف در حالت
            # فارسی بی‌اثر می‌شدند.
            table.setCurrentCell(active, 0)
        self.accounts_note.setText(
            self.tr_.tr("settings.accounts.security_note")
            if self._accounts
            else self.tr_.tr("settings.accounts.no_accounts")
        )

    def selected_account_id(self) -> int:
        """
        شناسهٔ حساب انتخاب‌شده؛ صفر یعنی چیزی انتخاب نشده.

        علاوه بر سطر جاری، مدلِ انتخاب هم بررسی می‌شود؛ در RTL این دو
        همیشه یکی نیستند.
        """
        row = self.accounts_table.currentRow()
        if row < 0:
            model = self.accounts_table.selectionModel()
            if model is not None:
                rows = model.selectedRows()
                if rows:
                    row = rows[0].row()
        if 0 <= row < len(getattr(self, "_accounts", [])):
            return int(self._accounts[row].get("id", 0))
        return 0

    def _emit_account_test(self) -> None:
        """
        درخواست آزمایش اتصال حساب انتخاب‌شده.

        اگر سطری انتخاب نشده باشد، به‌جای سکوت، سیگنال «انتخاب نشده»
        منتشر می‌شود؛ دکمهٔ بی‌صدا کاربر را سردرگم می‌کند.
        """
        account_id = self.selected_account_id()
        if account_id:
            self.account_test_requested.emit(account_id)
        else:
            self.account_selection_blocked.emit()

    def _emit_account_activate(self) -> None:
        """درخواست فعال‌کردن حساب انتخاب‌شده برای کیف پول."""
        account_id = self.selected_account_id()
        if account_id:
            self.account_activate_requested.emit(account_id)
        else:
            self.account_selection_blocked.emit()

    def _emit_account_remove(self) -> None:
        """درخواست حذف حساب انتخاب‌شده."""
        account_id = self.selected_account_id()
        if account_id:
            self.account_remove_requested.emit(account_id)
        else:
            self.account_selection_blocked.emit()

    def _on_exchange_changed(self) -> None:
        """
        نمایش وضعیت صرافی انتخاب‌شده.

        اگر صرافی هنوز پیاده‌سازی نشده یا از ایران بسته است، همین‌جا
        گفته می‌شود؛ بهتر از خطای مبهم شبکه هنگام اولین درخواست.
        """
        key = self.exchange_combo.currentData()
        if not key:
            return
        preset = get_exchange(str(key))
        if not preset.implemented:
            self.exchange_status.setText("⚠ " + self.tr_.tr("settings.exchange_not_implemented"))
        elif preset.geo_restricted:
            self.exchange_status.setText("⚠ " + self.tr_.tr("settings.exchange_geo_restricted"))
        else:
            # راهنمای ویژهٔ هر صرافی (مثلاً الزام فهرست IP مجاز در بیت‌پین)
            # همین‌جا نشان داده می‌شود تا کاربر پیش از تلاش ناموفق بداند
            # چه چیزی لازم است.
            hint_key = f"settings.exchange_hint.{preset.key}"
            if self.tr_.has(hint_key):
                self.exchange_status.setText("ℹ " + self.tr_.tr(hint_key))
            else:
                self.exchange_status.setText("")
        # کلیدهای هر صرافی جداست؛ ورودی‌ها هنگام تعویض پاک می‌شوند تا
        # کلید صرافی قبلی اشتباهاً برای صرافی جدید ذخیره نشود.
        self.api_key_input.clear()
        self.api_secret_input.clear()
        self.exchange_changed.emit(str(key))

    def _build_ai(self) -> QWidget:
        """
        زبانه هوش مصنوعی.

        کاربر خواست به «اکثر سرویس‌ها و مدل‌ها» وصل شود، پس فهرست
        سرویس‌ها از کاتالوگ می‌آید و مدل‌ها به‌صورت زنده از خود سرویس
        دریافت می‌شوند — نه فهرست ثابتی که زود کهنه شود.
        """
        widget, layout = self._form()

        self.ai_enabled_check = QCheckBox()
        self.ai_enabled_check.setChecked(True)

        self.ai_provider_combo = QComboBox()
        for preset in PROVIDER_PRESETS:
            self.ai_provider_combo.addItem(preset.display_name, preset.key)
        self.ai_provider_combo.currentIndexChanged.connect(self._on_ai_provider_changed)

        # مدل هم قابل انتخاب و هم قابل تایپ است: فهرست زنده پر می‌شود ولی
        # کاربر باید بتواند نام مدلی را که خودش می‌داند وارد کند.
        self.ai_model_combo = QComboBox()
        self.ai_model_combo.setEditable(True)
        self.ai_model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.ai_model_combo.setMinimumWidth(220)

        # کاربر خواست «اول مدل‌های رایگان، بعد مدل‌های پولی». این گزینه
        # فهرست را به مدل‌های بی‌هزینه محدود می‌کند و به‌صورت پیش‌فرض روشن
        # است تا کسی ناخواسته هزینه ندهد.
        self.ai_free_only_check = QCheckBox()
        self.ai_free_only_check.setChecked(True)
        self.ai_free_only_check.toggled.connect(self._refresh_model_list)

        self.ai_base_url_input = QLineEdit()
        self.ai_key_input = QLineEdit()
        self.ai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_fallback_check = QCheckBox()
        self.ai_fallback_check.setChecked(True)

        self._add_row(layout, "settings.ai_enable", self.ai_enabled_check)
        self._add_row(layout, "settings.ai_provider", self.ai_provider_combo)
        self._add_row(layout, "settings.ai_free_only", self.ai_free_only_check)
        self._add_row(layout, "settings.ai_model", self.ai_model_combo)

        # هشدار تناسب مدل محلی با حافظهٔ دستگاه.
        #
        # کاربر با `deepseek-r1:8b` روی دستگاه ۱۶ گیگابایتی روبه‌رو شد
        # با خطای «اتصال به‌زور بسته شد» — که در واقع مرگ زیرفرایند
        # مدل از کمبود حافظه بود. برنامه حالا آن مرگ را تشخیص می‌دهد و
        # دوباره تلاش می‌کند، ولی بهتر است کاربر پیش از انتخاب بداند.
        self.model_fit_label = QLabel("")
        self.model_fit_label.setWordWrap(True)
        self.model_fit_label.setVisible(False)
        layout.addRow("", self.model_fit_label)
        self.ai_model_combo.currentTextChanged.connect(self._refresh_model_fit)

        self._add_row(layout, "settings.ai_base_url", self.ai_base_url_input)
        self._add_row(layout, "settings.ai_api_key", self.ai_key_input)
        self._add_row(layout, "settings.ai_fallback", self.ai_fallback_check)

        buttons = QHBoxLayout()
        self.test_ai_button = make_button(self.tr_.tr("settings.test_connection"))
        self.load_models_button = make_button(self.tr_.tr("settings.load_models"))
        # «آزمایش اتصال» فقط می‌گوید سرویس بالاست یا نه؛ کاربری که مدلش
        # در ترمینال کار می‌کند ولی در برنامه نه، از آن چیزی نمی‌فهمد.
        # عیب‌یاب، بار واقعی را پله‌پله می‌آزماید و می‌گوید کجا می‌شکند.
        self.doctor_button = make_button(self.tr_.tr("settings.doctor.button"))
        buttons.addWidget(self.test_ai_button)
        buttons.addWidget(self.load_models_button)
        buttons.addWidget(self.doctor_button)
        buttons.addStretch(1)
        layout.addRow(buttons)

        self.ai_status = QLabel("")
        self.ai_status.setProperty("role", "muted")
        self.ai_status.setWordWrap(True)
        layout.addRow(self.ai_status)

        self.ai_hint = QLabel("")
        self.ai_hint.setProperty("role", "muted")
        self.ai_hint.setWordWrap(True)
        layout.addRow(self.ai_hint)

        self._on_ai_provider_changed()
        return widget

    def _on_ai_provider_changed(self) -> None:
        """پر کردن پیش‌فرض‌های سرویس انتخاب‌شده."""
        key = self.ai_provider_combo.currentData()
        if not key:
            return
        preset = get_preset(str(key))
        if preset is None:
            return
        self.ai_base_url_input.setText(preset.base_url)

        # فهرست خام: مدل‌های رایگان شناخته‌شده + پیشنهادهای خود سرویس
        self._available_models = list(
            dict.fromkeys(list(known_free_models(str(key))) + list(preset.suggested_models))
        )
        self._refresh_model_list()

        # سرویس‌هایی مثل OmniRoute کلید را «می‌پذیرند» بی‌آنکه «بخواهند»؛
        # کادر باید برایشان فعال بماند وگرنه کاربری که احراز هویت دروازه
        # را روشن کرده راهی برای وارد کردن کلیدش ندارد.
        self.ai_key_input.setEnabled(preset.key_field_enabled)
        if preset.requires_key:
            hint = preset.notes
        elif preset.accepts_optional_key:
            hint = f"{preset.notes}\n{self.tr_.tr('settings.ai_optional_key')}".strip()
        else:
            hint = self.tr_.tr("settings.no_key_needed")
        if str(key) == "ollama":
            hint = f"{hint}\n{self.tr_.tr('settings.ai_ollama_hint')}"
        elif str(key) == "omniroute":
            hint = f"{hint}\n{self.tr_.tr('settings.ai_omniroute_hint')}"
        # نشانی گرفتن کلید تا امروز فقط در کاتالوگ ذخیره می‌شد و هیچ‌جا
        # دیده نمی‌شد؛ کاربر باید حدس می‌زد کلید را از کجا بگیرد.
        if preset.signup_url:
            hint = f"{hint}\n{self.tr_.tr('settings.ai_get_key_at', url=preset.signup_url)}"
        self.ai_hint.setText(hint)
        self.ai_status.setText("")
        self.ai_provider_changed.emit(str(key))

    def _refresh_model_fit(self, model: str = "") -> None:
        """
        هشدار «این مدل روی دستگاه شما جا نمی‌شود».

        فقط برای اولاما معنا دارد؛ مدل ابری روی حافظهٔ دستگاه کاربر
        اجرا نمی‌شود. و فقط هشدار می‌دهد — انتخاب را مسدود نمی‌کند،
        چون تشخیص خودکار ممکن است کارت گرافیک قدرتمندی را نبیند.
        """
        from ai.local_model_fit import FITS, evaluate_fit, suggest_models
        from ai.prompt_budget import detect_total_memory_gb

        provider = self.ai_provider_combo.currentData()
        name = (model or self.ai_model_combo.currentText()).strip()
        if provider != "ollama" or not name:
            self.model_fit_label.setVisible(False)
            return

        memory = detect_total_memory_gb()
        fit = evaluate_fit(name, memory)
        if not fit.is_risky:
            if fit.status == FITS:
                self.model_fit_label.setText(
                    self.tr_.tr("settings.model_fit.fits", gb=fit.required_gb)
                )
                self.model_fit_label.setStyleSheet("")
                self.model_fit_label.setProperty("role", "muted")
                self.model_fit_label.setVisible(True)
                return
            self.model_fit_label.setVisible(False)
            return

        suggestions = ", ".join(suggest_models(memory)) or "—"
        self.model_fit_label.setText(
            self.tr_.tr(
                fit.reason_key,
                model=fit.model,
                required=fit.required_gb,
                available=fit.available_gb,
                suggestions=suggestions,
            )
        )
        self.model_fit_label.setProperty("role", "")
        self.model_fit_label.setStyleSheet("color: #e0a030; font-size: 12px;")
        self.model_fit_label.setVisible(True)

    def _refresh_model_list(self) -> None:
        """
        بازچینش فهرست مدل‌ها: رایگان‌ها اول.

        اگر «فقط رایگان» روشن باشد ولی هیچ مدل رایگانی شناخته نشده باشد،
        به‌جای فهرست خالی، همه مدل‌ها نشان داده می‌شوند و دلیلش گفته می‌شود.
        """
        models = list(getattr(self, "_available_models", []))
        provider = str(self.ai_provider_combo.currentData() or "")
        current = self.ai_model_combo.currentText().strip()

        ordered = sort_models(models, provider)
        if self.ai_free_only_check.isChecked():
            free = [info for info in ordered if info.tier == TIER_FREE]
            if free:
                ordered = free
            elif models:
                self.ai_hint.setText(self.tr_.tr("settings.ai_no_free_model"))

        self.ai_model_combo.blockSignals(True)
        self.ai_model_combo.clear()
        for info in ordered:
            self.ai_model_combo.addItem(info.label(self.tr_.language), info.name)
        # اگر انتخاب قبلی هنوز در فهرست هست، حفظش کن
        index = self.ai_model_combo.findData(current)
        if index >= 0:
            self.ai_model_combo.setCurrentIndex(index)
        elif current:
            self.ai_model_combo.setCurrentText(current)
        self.ai_model_combo.blockSignals(False)

    def set_model_list(self, models: list[str]) -> None:
        """نمایش مدل‌های دریافت‌شده زنده از سرویس."""
        self._available_models = list(models)
        self._refresh_model_list()

    def selected_model(self) -> str:
        """
        نام واقعی مدل انتخاب‌شده.

        متن نمایشی برچسب «— رایگان» دارد، پس نباید مستقیم ذخیره شود.
        """
        data = self.ai_model_combo.currentData()
        if data:
            return str(data)
        # کاربر نام مدل را دستی تایپ کرده است
        text = self.ai_model_combo.currentText().strip()
        return text.split(" — ")[0].strip()

    def auto_pick_free_model(self) -> str:
        """انتخاب خودکار رایگان‌ترین مدل موجود."""
        provider = str(self.ai_provider_combo.currentData() or "")
        models = list(getattr(self, "_available_models", []))
        chosen = pick_default_model(models, provider)
        if chosen:
            index = self.ai_model_combo.findData(chosen)
            if index >= 0:
                self.ai_model_combo.setCurrentIndex(index)
            else:
                self.ai_model_combo.setCurrentText(chosen)
        return chosen

    def free_model_count(self) -> int:
        """تعداد مدل‌های رایگان در فهرست فعلی."""
        provider = str(self.ai_provider_combo.currentData() or "")
        return sum(
            1
            for name in getattr(self, "_available_models", [])
            if classify_model(name, provider) == TIER_FREE
        )

    def set_ai_status(self, text: str, ok: bool | None = None) -> None:
        """نمایش نتیجه آزمایش اتصال."""
        prefix = "" if ok is None else ("✓ " if ok else "✗ ")
        self.ai_status.setText(prefix + text)
        self.ai_status.setProperty("role", "muted" if ok is None else ("bullish" if ok else "bearish"))
        self.ai_status.style().unpolish(self.ai_status)
        self.ai_status.style().polish(self.ai_status)

    def _build_risk(self) -> QWidget:
        """زبانه ریسک: پارامترهای محافظه‌کارانه پیش‌فرض."""
        widget, layout = self._form()
        self.balance_spin = QDoubleSpinBox()
        self.balance_spin.setRange(0, 100_000_000)
        self.balance_spin.setValue(1000)
        self.risk_percent_spin = QDoubleSpinBox()
        self.risk_percent_spin.setRange(0.1, 20.0)
        self.risk_percent_spin.setSingleStep(0.1)
        self.risk_percent_spin.setValue(1.0)
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 125)
        self.leverage_spin.setValue(5)
        self.min_rr_spin = QDoubleSpinBox()
        self.min_rr_spin.setRange(0.5, 10.0)
        self.min_rr_spin.setSingleStep(0.1)
        self.min_rr_spin.setValue(1.5)
        self.atr_spin = QDoubleSpinBox()
        self.atr_spin.setRange(0.5, 10.0)
        self.atr_spin.setSingleStep(0.1)
        self.atr_spin.setValue(1.5)

        self._add_row(layout, "settings.risk_balance", self.balance_spin)
        self._add_row(layout, "settings.risk_percent", self.risk_percent_spin)
        self._add_row(layout, "settings.max_leverage", self.leverage_spin)
        self._add_row(layout, "settings.min_rr", self.min_rr_spin)
        self._add_row(layout, "settings.atr_multiplier", self.atr_spin)
        return widget

    def _build_display(self) -> QWidget:
        """
        زبانهٔ نمایش.

        کاربر خواست «تنظیمات بیشتری روی نرم‌افزار داشته باشد و سیستم
        انعطاف بیشتری پیدا کند». این گزینه‌ها ظاهر و رفتار روزمرهٔ
        برنامه را بدون دست‌زدن به کد قابل تغییر می‌کنند.
        """
        widget, layout = self._form()

        # فهرست حالت‌ها از خود صفحهٔ بازارها خوانده می‌شود تا اگر روزی
        # حالت تازه‌ای اضافه شد، این دو فهرست از هم جدا نیفتند.
        self.markets_sort_combo = QComboBox()
        for mode, key in SORT_MODES:
            self.markets_sort_combo.addItem(self.tr_.tr(key), mode)

        # اندازهٔ قلم و حالت فشرده به زبانهٔ «ظاهر برنامه» منتقل شده‌اند
        # تا همهٔ تنظیمات ظاهری یک‌جا باشند.
        self.confirm_actions_check = QCheckBox()
        self.confirm_actions_check.setChecked(True)
        self.show_toman_check = QCheckBox()
        self.show_toman_check.setChecked(True)

        self._add_row(layout, "settings.markets_sort", self.markets_sort_combo)
        self._add_row(layout, "settings.confirm_actions", self.confirm_actions_check)
        self._add_row(layout, "settings.show_toman", self.show_toman_check)
        return widget

    def _build_performance(self) -> QWidget:
        """
        زبانهٔ کارایی.

        کاربر گزارش داد «سیستم خیلی کند است». این مقادیر مستقیماً روی
        سرعت اثر می‌گذارند: چند درخواست هم‌زمان برود، هر چند ثانیه
        تازه‌سازی شود و چقدر منتظر پاسخ بمانیم.
        """
        widget, layout = self._form()

        self.chat_history_limit_spin = QSpinBox()
        self.chat_history_limit_spin.setRange(10, 1000)
        self.chat_history_limit_spin.setSingleStep(10)
        self.chat_history_limit_spin.setValue(100)

        self.candle_cache_spin = QSpinBox()
        self.candle_cache_spin.setRange(0, 3600)
        self.candle_cache_spin.setSingleStep(10)
        self.candle_cache_spin.setSuffix(" s")
        self.candle_cache_spin.setSpecialValueText(self.tr_.tr("settings.cache_auto"))

        self.parallel_spin = QSpinBox()
        self.parallel_spin.setRange(1, 32)
        self.parallel_spin.setValue(8)

        self.dashboard_interval_spin = QSpinBox()
        self.dashboard_interval_spin.setRange(5, 600)
        self.dashboard_interval_spin.setSuffix(" s")
        self.dashboard_interval_spin.setValue(30)

        self.markets_interval_spin = QSpinBox()
        self.markets_interval_spin.setRange(5, 600)
        self.markets_interval_spin.setSuffix(" s")
        self.markets_interval_spin.setValue(20)

        self.http_timeout_spin = QSpinBox()
        self.http_timeout_spin.setRange(3, 120)
        self.http_timeout_spin.setSuffix(" s")
        self.http_timeout_spin.setValue(15)

        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(1, 10)
        self.max_retries_spin.setValue(3)

        self.signal_mode_combo = QComboBox()
        for mode, key in (
            ("hybrid", "settings.mode_hybrid"),
            ("ai_only", "settings.mode_ai_only"),
            ("engine", "settings.mode_engine"),
        ):
            self.signal_mode_combo.addItem(self.tr_.tr(key), mode)

        self.narrative_check = QCheckBox()
        self.narrative_check.setChecked(True)

        self.signal_ai_timeout_spin = QSpinBox()
        self.signal_ai_timeout_spin.setRange(10, 300)
        self.signal_ai_timeout_spin.setSuffix(" s")
        self.signal_ai_timeout_spin.setValue(45)

        self.save_chat_check = QCheckBox()
        self.save_chat_check.setChecked(True)

        # بازبینی خودکار سیگنال‌های بسته‌شده. تنها راهی که کاربر
        # می‌فهمد چرا سیگنالی سود نداد، پس پیش‌فرض روشن است.
        self.auto_review_check = QCheckBox()
        self.auto_review_check.setChecked(True)

        # سقف دستی پنجرهٔ متن مدل محلی.
        #
        # صفر یعنی «از حافظهٔ دستگاه تشخیص بده» که برای اکثر کاربران
        # درست است. این گزینه برای حالتی است که کارت گرافیک از حافظهٔ
        # سیستم ضعیف‌تر باشد؛ آن‌وقت تشخیص خودکار خوش‌بینانه می‌شود و
        # اولاما خطای ۵۰۰ می‌دهد.
        self.ollama_context_spin = QSpinBox()
        self.ollama_context_spin.setRange(0, 32768)
        self.ollama_context_spin.setSingleStep(2048)
        self.ollama_context_spin.setSpecialValueText(self.tr_.tr("settings.auto_detect"))
        self.ollama_context_spin.setValue(0)

        # پنهان‌کردن سیگنال سوخته از جدول‌ها
        self.hide_stale_check = QCheckBox()
        self.hide_stale_check.setChecked(False)

        # نمایش تدریجی پاسخ چت. اگر سرویس جریان ندهد، برنامه خودکار به
        # حالت عادی برمی‌گردد، پس روشن‌بودن پیش‌فرض بی‌خطر است.
        self.chat_streaming_check = QCheckBox()
        self.chat_streaming_check.setChecked(True)

        self._add_row(layout, "settings.signal_mode", self.signal_mode_combo)
        self._add_row(layout, "settings.narrative_enabled", self.narrative_check)
        self._add_row(layout, "settings.signal_ai_timeout", self.signal_ai_timeout_spin)
        self._add_row(layout, "review.auto_enabled", self.auto_review_check)
        self._add_row(layout, "settings.hide_stale_signals", self.hide_stale_check)
        self._add_row(layout, "settings.ollama_max_context", self.ollama_context_spin)
        self._add_row(layout, "settings.chat_streaming", self.chat_streaming_check)
        self._add_row(layout, "settings.save_chat_history", self.save_chat_check)
        self._add_row(layout, "settings.chat_history_limit", self.chat_history_limit_spin)
        self._add_row(layout, "settings.candle_cache_ttl", self.candle_cache_spin)
        self._add_row(layout, "settings.parallel_requests", self.parallel_spin)
        self._add_row(layout, "settings.dashboard_interval", self.dashboard_interval_spin)
        self._add_row(layout, "settings.markets_interval", self.markets_interval_spin)
        self._add_row(layout, "settings.http_timeout", self.http_timeout_spin)
        self._add_row(layout, "settings.max_retries", self.max_retries_spin)
        return widget

    def _build_security(self) -> QWidget:
        """
        زبانهٔ امنیت حساب: پروفایل، تغییر رمز عبور و مدیریت نشست‌ها.

        سرویس `AuthService` از ابتدا این توانایی‌ها را داشت ولی هیچ رابط
        کاربری‌ای به آن وصل نبود؛ این زبانه همان شکاف را می‌بندد.
        """
        widget = QWidget()
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(14)

        # ------------------------------ پروفایل
        self.profile_title = QLabel(self.tr_.tr("settings.security.profile"))
        self.profile_title.setProperty("role", "cardTitle")
        outer.addWidget(self.profile_title)

        profile_box = QFrame()
        profile_box.setProperty("role", "panel")
        profile_form = QFormLayout(profile_box)
        profile_form.setContentsMargins(14, 14, 14, 14)
        profile_form.setSpacing(10)
        self.display_name_input = QLineEdit()
        self.email_input = QLineEdit()
        self._add_row(profile_form, "settings.security.display_name", self.display_name_input)
        self._add_row(profile_form, "settings.security.email", self.email_input)
        self.profile_save_button = make_button(
            self.tr_.tr("settings.security.save_profile"), primary=True
        )
        self.profile_save_button.setMinimumHeight(34)
        self.profile_save_button.clicked.connect(
            lambda: self.profile_save_requested.emit(
                self.display_name_input.text().strip(),
                self.email_input.text().strip(),
            )
        )
        profile_actions = QHBoxLayout()
        profile_actions.addWidget(self.profile_save_button)
        profile_actions.addStretch(1)
        profile_form.addRow(profile_actions)
        outer.addWidget(profile_box)

        # ------------------------------ تغییر رمز عبور
        self.password_title = QLabel(self.tr_.tr("auth.change_password"))
        self.password_title.setProperty("role", "cardTitle")
        outer.addWidget(self.password_title)

        password_box = QFrame()
        password_box.setProperty("role", "panel")
        password_form = QFormLayout(password_box)
        password_form.setContentsMargins(14, 14, 14, 14)
        password_form.setSpacing(10)
        self.current_password_input = QLineEdit()
        self.current_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._add_row(password_form, "auth.current_password", self.current_password_input)
        self._add_row(password_form, "auth.new_password", self.new_password_input)
        self._add_row(
            password_form, "settings.security.confirm_password", self.confirm_password_input
        )
        self.password_hint = QLabel(self.tr_.tr("settings.security.password_hint"))
        self.password_hint.setProperty("role", "faint")
        self.password_hint.setWordWrap(True)
        password_form.addRow(self.password_hint)
        self.password_change_button = make_button(
            self.tr_.tr("auth.change_password"), primary=True
        )
        self.password_change_button.setMinimumHeight(34)
        self.password_change_button.clicked.connect(self._emit_password_change)
        password_actions = QHBoxLayout()
        password_actions.addWidget(self.password_change_button)
        password_actions.addStretch(1)
        password_form.addRow(password_actions)
        outer.addWidget(password_box)

        # ------------------------------ نشست‌ها
        self.sessions_title = QLabel(self.tr_.tr("settings.security.sessions"))
        self.sessions_title.setProperty("role", "cardTitle")
        outer.addWidget(self.sessions_title)

        self.sessions_table = QTableWidget(0, 4)
        self.sessions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sessions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sessions_table.verticalHeader().setVisible(False)
        self.sessions_table.setMaximumHeight(170)
        self.sessions_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.sessions_table.horizontalHeader().setStretchLastSection(True)
        outer.addWidget(self.sessions_table)

        session_buttons = QHBoxLayout()
        self.revoke_session_button = make_button(self.tr_.tr("auth.revoke_session"))
        self.revoke_session_button.clicked.connect(self._emit_revoke_selected)
        self.revoke_others_button = make_button(self.tr_.tr("auth.revoke_others"))
        self.revoke_others_button.clicked.connect(self.revoke_others_requested.emit)
        session_buttons.addWidget(self.revoke_session_button)
        session_buttons.addWidget(self.revoke_others_button)
        session_buttons.addStretch(1)
        outer.addLayout(session_buttons)

        # ------------------------------ ایمیل (برای بازیابی رمز)
        self.email_title = QLabel(self.tr_.tr("email.title"))
        self.email_title.setProperty("role", "cardTitle")
        outer.addWidget(self.email_title)

        email_box = QFrame()
        email_box.setProperty("role", "panel")
        email_outer = QVBoxLayout(email_box)
        email_outer.setContentsMargins(14, 14, 14, 14)
        email_outer.setSpacing(8)

        self.email_description = QLabel(self.tr_.tr("email.description"))
        self.email_description.setProperty("role", "faint")
        self.email_description.setWordWrap(True)
        email_outer.addWidget(self.email_description)

        email_form = QFormLayout()
        email_form.setSpacing(10)

        self.email_preset_combo = QComboBox()
        # ترتیب ثابت است تا اندیس‌ها با کلیدها بخوانند
        for key in SMTP_PRESETS:
            self.email_preset_combo.addItem(self.tr_.tr(f"email.presets.{key}"), key)
        self.email_preset_combo.currentIndexChanged.connect(self._apply_email_preset)
        self._add_row(email_form, "email.preset", self.email_preset_combo)

        self.smtp_host_input = QLineEdit()
        self.smtp_host_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._add_row(email_form, "email.smtp_host", self.smtp_host_input)

        self.smtp_port_input = QSpinBox()
        self.smtp_port_input.setRange(1, 65535)
        self.smtp_port_input.setValue(587)
        self._add_row(email_form, "email.smtp_port", self.smtp_port_input)

        self.smtp_username_input = QLineEdit()
        self.smtp_username_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.smtp_username_input.setPlaceholderText("you@gmail.com")
        self._add_row(email_form, "email.smtp_username", self.smtp_username_input)

        self.smtp_password_input = QLineEdit()
        self.smtp_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.smtp_password_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._add_row(email_form, "email.smtp_password", self.smtp_password_input)

        self.smtp_tls_check = QCheckBox()
        self._add_row(email_form, "email.smtp_tls", self.smtp_tls_check)

        self.email_sender_name_input = QLineEdit()
        self._add_row(email_form, "email.sender_name", self.email_sender_name_input)
        email_outer.addLayout(email_form)

        # راهنمای جیمیل: پرتکرارترین علت شکست، گذاشتن رمز اصلی به‌جای
        # «رمز عبور برنامه» است.
        self.email_gmail_hint = QLabel(self.tr_.tr("email.gmail_hint"))
        self.email_gmail_hint.setProperty("role", "faint")
        self.email_gmail_hint.setWordWrap(True)
        email_outer.addWidget(self.email_gmail_hint)

        self.email_status_label = QLabel("")
        self.email_status_label.setWordWrap(True)
        self.email_status_label.setVisible(False)
        email_outer.addWidget(self.email_status_label)

        email_actions = QHBoxLayout()
        self.email_test_button = make_button(self.tr_.tr("email.test"))
        self.email_test_button.clicked.connect(self.email_test_requested.emit)
        self.email_save_button = make_button(self.tr_.tr("common.save"), primary=True)
        self.email_save_button.setMinimumHeight(34)
        self.email_save_button.clicked.connect(self._emit_email_save)
        email_actions.addWidget(self.email_save_button)
        email_actions.addWidget(self.email_test_button)
        email_actions.addStretch(1)
        email_outer.addLayout(email_actions)
        outer.addWidget(email_box)

        self.security_note = QLabel(self.tr_.tr("settings.security.note"))
        self.security_note.setProperty("role", "faint")
        self.security_note.setWordWrap(True)
        outer.addWidget(self.security_note)
        outer.addStretch(1)

        self._retranslate_session_headers()
        self.set_sessions([])

        # محتوای این زبانه بلند است؛ بدون اسکرول، چیدمان در پنجره‌های کوتاه
        # سطرهای پایینی را فشرده می‌کند و متن دکمه بریده می‌شود.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        # فقط اسکرول عمودی؛ جدول نشست‌ها خودش را با عرض موجود جمع می‌کند
        # و نوار افقی جز به‌هم‌ریختگی چیزی اضافه نمی‌کند.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(widget)
        return scroll

    def _apply_email_preset(self) -> None:
        """
        پر کردن خودکار سرور و پورت با انتخاب سرویس.

        کاربر نباید بداند پورت جیمیل ۵۸۷ است؛ همین کوچک‌ترین مانع، اغلب
        باعث می‌شود کل قابلیت بلااستفاده بماند.
        """
        key = self.email_preset_combo.currentData()
        preset = SMTP_PRESETS.get(str(key or ""), None)
        if not preset or not preset.get("host"):
            return
        self.smtp_host_input.setText(str(preset["host"]))
        self.smtp_port_input.setValue(int(preset["port"]))
        self.smtp_tls_check.setChecked(bool(preset["tls"]))

    def _emit_email_save(self) -> None:
        """جمع‌کردن مقادیر فرم ایمیل و فرستادن به کنترلر."""
        values = {
            "email.preset": str(self.email_preset_combo.currentData() or "custom"),
            "email.smtp_host": self.smtp_host_input.text().strip(),
            "email.smtp_port": int(self.smtp_port_input.value()),
            "email.smtp_username": self.smtp_username_input.text().strip(),
            "email.smtp_tls": bool(self.smtp_tls_check.isChecked()),
            "email.sender": self.smtp_username_input.text().strip(),
            "email.sender_name": self.email_sender_name_input.text().strip(),
        }
        self.email_save_requested.emit(values, self.smtp_password_input.text())

    def set_email_settings(self, values: dict[str, Any], *, has_password: bool) -> None:
        """
        نشاندن تنظیمات ذخیره‌شده در فرم.

        رمز هرگز بازخوانده نمی‌شود؛ فقط با یک جای‌نگهدار نشان داده می‌شود
        که رمزی ذخیره شده است. نمایش رمز ذخیره‌شده، حتی به صاحب دستگاه،
        نشت بی‌دلیل است.
        """
        preset = str(values.get("email.preset", "gmail") or "gmail")
        index = self.email_preset_combo.findData(preset)
        if index >= 0:
            self.email_preset_combo.blockSignals(True)
            self.email_preset_combo.setCurrentIndex(index)
            self.email_preset_combo.blockSignals(False)

        self.smtp_host_input.setText(str(values.get("email.smtp_host", "") or ""))
        self.smtp_port_input.setValue(int(values.get("email.smtp_port", 587) or 587))
        self.smtp_username_input.setText(str(values.get("email.smtp_username", "") or ""))
        self.smtp_tls_check.setChecked(bool(values.get("email.smtp_tls", True)))
        self.email_sender_name_input.setText(str(values.get("email.sender_name", "") or ""))
        self.smtp_password_input.clear()
        self.smtp_password_input.setPlaceholderText("••••••••••••" if has_password else "")

    def set_email_status(self, text: str, *, error: bool = False) -> None:
        """نمایش نتیجهٔ آزمایش اتصال."""
        self.email_status_label.setText(text)
        self.email_status_label.setProperty("role", "danger" if error else "success")
        self.email_status_label.setVisible(bool(text))
        self.email_status_label.style().unpolish(self.email_status_label)
        self.email_status_label.style().polish(self.email_status_label)

    def _emit_password_change(self) -> None:
        """ارسال درخواست تغییر رمز به کنترلر."""
        self.password_change_requested.emit(
            self.current_password_input.text(),
            self.new_password_input.text(),
            self.confirm_password_input.text(),
        )

    def clear_password_inputs(self) -> None:
        """پاک‌کردن فیلدهای رمز پس از تغییر موفق."""
        self.current_password_input.clear()
        self.new_password_input.clear()
        self.confirm_password_input.clear()

    def _selected_session_row(self) -> int:
        """
        شمارهٔ سطر انتخاب‌شده در جدول نشست‌ها.

        `currentRow()` به‌تنهایی کافی نیست: در چیدمان راست‌به‌چپ ممکن است
        سطر «جاری» تنظیم نشده باشد در حالی که کاربر سطری را انتخاب کرده،
        پس مدلِ انتخاب هم بررسی می‌شود.
        """
        row = self.sessions_table.currentRow()
        if row >= 0:
            return row
        model = self.sessions_table.selectionModel()
        if model is not None:
            rows = model.selectedRows()
            if rows:
                return rows[0].row()
        return -1

    def _emit_revoke_selected(self) -> None:
        """باطل‌کردن نشست انتخاب‌شده در جدول."""
        row = self._selected_session_row()
        if row < 0:
            self.session_revoke_blocked.emit()
            return
        item = self.sessions_table.item(row, 0)
        if item is None:
            return
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id is not None:
            self.session_revoke_requested.emit(int(session_id))

    def _retranslate_session_headers(self) -> None:
        """عنوان ستون‌های جدول نشست‌ها."""
        self.sessions_table.setHorizontalHeaderLabels(
            [
                self.tr_.tr("auth.device"),
                self.tr_.tr("auth.created"),
                self.tr_.tr("auth.last_seen"),
                self.tr_.tr("settings.security.status"),
            ]
        )

    def set_profile(self, display_name: str, email: str) -> None:
        """پرکردن فیلدهای پروفایل با مقادیر کاربر جاری."""
        self.display_name_input.setText(display_name or "")
        self.email_input.setText(email or "")

    def set_sessions(self, rows: list[dict[str, Any]]) -> None:
        """نمایش نشست‌های فعال کاربر."""
        self.sessions_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            device = QTableWidgetItem(str(row.get("device", "")))
            device.setData(Qt.ItemDataRole.UserRole, row.get("id"))
            self.sessions_table.setItem(index, 0, device)
            self.sessions_table.setItem(
                index, 1, QTableWidgetItem(str(row.get("created", "")))
            )
            self.sessions_table.setItem(
                index, 2, QTableWidgetItem(str(row.get("last_seen", "")))
            )
            self.sessions_table.setItem(
                index, 3, QTableWidgetItem(str(row.get("status", "")))
            )
        header = self.sessions_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def set_security_enabled(self, enabled: bool) -> None:
        """
        غیرفعال‌کردن کنترل‌های امنیتی وقتی کاربر مهمان است.

        مهمان حساب کاربری ندارد، پس تغییر رمز و مدیریت نشست بی‌معناست.
        """
        for widget in (
            self.profile_save_button,
            self.password_change_button,
            self.revoke_session_button,
            self.revoke_others_button,
            self.display_name_input,
            self.email_input,
            self.current_password_input,
            self.new_password_input,
            self.confirm_password_input,
        ):
            widget.setEnabled(bool(enabled))
        self.security_note.setText(
            self.tr_.tr("settings.security.note")
            if enabled
            else self.tr_.tr("settings.security.guest_note")
        )

    def _build_backup(self) -> QWidget:
        """زبانه پشتیبان‌گیری."""
        widget, layout = self._form()
        self.auto_backup_check = QCheckBox()
        self.auto_backup_check.setChecked(True)
        self.backup_button = make_button(self.tr_.tr("settings.backup_now"))
        self.restore_button = make_button(self.tr_.tr("settings.restore"))
        self._add_row(layout, "settings.auto_backup", self.auto_backup_check)
        layout.addRow(self.backup_button)
        layout.addRow(self.restore_button)

        # ---- به‌روزرسانی برنامه ----
        # کنار پشتیبان‌گیری می‌نشیند چون هر دو «نگه‌داری» هستند و کاربر
        # پیش از به‌روزرسانی معمولاً پشتیبان می‌گیرد.
        title = QLabel(self.tr_.tr("settings.update.title"))
        title.setProperty("role", "section")
        layout.addRow(title)

        self.update_source_input = QLineEdit()
        self.update_source_input.setPlaceholderText(
            self.tr_.tr("settings.update.source_hint")
        )
        self._add_row(layout, "settings.update.source", self.update_source_input)

        self.update_auto_check = QCheckBox()
        self._add_row(layout, "settings.update.auto_check", self.update_auto_check)

        update_buttons = QHBoxLayout()
        self.check_update_button = make_button(self.tr_.tr("settings.update.check_button"))
        self.install_update_button = make_button(
            self.tr_.tr("settings.update.install_button"), primary=True
        )
        # تا وقتی نسخهٔ تازه‌ای پیدا نشده، دکمهٔ نصب معنا ندارد.
        self.install_update_button.setEnabled(False)
        update_buttons.addWidget(self.check_update_button)
        update_buttons.addWidget(self.install_update_button)
        update_buttons.addStretch(1)
        layout.addRow(update_buttons)

        self.update_status = QLabel("")
        self.update_status.setProperty("role", "muted")
        self.update_status.setWordWrap(True)
        layout.addRow(self.update_status)

        safety = QLabel(self.tr_.tr("settings.update.data_safe"))
        safety.setProperty("role", "muted")
        safety.setWordWrap(True)
        layout.addRow(safety)
        return widget

    def set_update_status(self, text: str, *, ok: bool | None = None) -> None:
        """نمایش وضعیت به‌روزرسانی."""
        self.update_status.setText(text)
        role = "muted" if ok is None else ("success" if ok else "danger")
        self.update_status.setProperty("role", role)
        style = self.update_status.style()
        if style is not None:
            style.unpolish(self.update_status)
            style.polish(self.update_status)

    # ------------------------------------------------------------------
    # خواندن و نوشتن مقادیر
    # ------------------------------------------------------------------
    def load_values(self, values: dict[str, Any]) -> None:
        """
        بارگذاری مقادیر ذخیره‌شده کاربر.

        فقط کلیدهای موجود اعمال می‌شوند؛ نبود یک کلید هرگز باعث بازنشانی
        بقیه مقادیر نمی‌شود.
        """
        if "ui.language" in values:
            index = self.language_combo.findData(values["ui.language"])
            if index >= 0:
                self.language_combo.setCurrentIndex(index)
        if "ui.theme" in values:
            # نام‌های نسخه‌های پیشین (dark/light/system) به پوستهٔ متناظر
            # نگاشت می‌شوند تا تنظیم ذخیره‌شدهٔ کاربر هرگز نادیده نماند.
            index = self.theme_combo.findData(resolve_theme_key(values["ui.theme"]))
            if index >= 0:
                self.theme_combo.setCurrentIndex(index)
        if "ui.font_family" in values:
            self.select_font_family(str(values["ui.font_family"]))
        if "exchange.active" in values:
            index = self.exchange_combo.findData(values["exchange.active"])
            if index >= 0:
                self.exchange_combo.setCurrentIndex(index)
        if "ai.enabled" in values:
            self.ai_enabled_check.setChecked(bool(values["ai.enabled"]))
        if "ai.provider" in values:
            index = self.ai_provider_combo.findData(values["ai.provider"])
            if index >= 0:
                self.ai_provider_combo.setCurrentIndex(index)
        if "ai.free_models_only" in values:
            self.ai_free_only_check.setChecked(bool(values["ai.free_models_only"]))
        if "ai.model" in values:
            model = str(values["ai.model"])
            index = self.ai_model_combo.findData(model)
            if index >= 0:
                self.ai_model_combo.setCurrentIndex(index)
            else:
                # مدل ذخیره‌شده در فهرست فعلی نیست (مثلاً فیلتر رایگان روشن
                # است)؛ به‌جای دور انداختن انتخاب کاربر، اضافه‌اش می‌کنیم.
                self.ai_model_combo.addItem(model, model)
                self.ai_model_combo.setCurrentIndex(self.ai_model_combo.count() - 1)
        if "ai.base_url" in values:
            self.ai_base_url_input.setText(str(values["ai.base_url"]))
        if "ai.fallback_enabled" in values:
            self.ai_fallback_check.setChecked(bool(values["ai.fallback_enabled"]))
        for key, widget in (
            ("risk.account_balance", self.balance_spin),
            ("risk.risk_percent", self.risk_percent_spin),
            ("risk.min_risk_reward", self.min_rr_spin),
            ("risk.atr_stop_multiplier", self.atr_spin),
        ):
            if key in values:
                widget.setValue(float(values[key]))
        if "risk.max_leverage" in values:
            self.leverage_spin.setValue(int(values["risk.max_leverage"]))

        # --- نمایش ---
        if "ui.markets_sort" in values:
            index = self.markets_sort_combo.findData(values["ui.markets_sort"])
            if index >= 0:
                self.markets_sort_combo.setCurrentIndex(index)
        for key, widget in (
            ("ui.font_scale", self.font_scale_spin),
            ("ai.chat_history_limit", self.chat_history_limit_spin),
            ("performance.candle_cache_ttl", self.candle_cache_spin),
            ("performance.parallel_requests", self.parallel_spin),
            ("performance.dashboard_refresh_seconds", self.dashboard_interval_spin),
            ("performance.markets_refresh_seconds", self.markets_interval_spin),
            ("performance.http_timeout", self.http_timeout_spin),
            ("performance.max_retries", self.max_retries_spin),
            ("signals.ai_timeout", self.signal_ai_timeout_spin),
            ("ai.ollama_max_context", self.ollama_context_spin),
        ):
            if key in values:
                try:
                    widget.setValue(int(values[key]))
                except (TypeError, ValueError):
                    continue
        for key, check in (
            ("ui.compact_mode", self.compact_check),
            ("ui.confirm_actions", self.confirm_actions_check),
            ("ui.show_toman", self.show_toman_check),
            ("ai.narrative_enabled", self.narrative_check),
            ("ai.save_chat_history", self.save_chat_check),
            ("ai.chat_streaming", self.chat_streaming_check),
            ("ai.auto_review", self.auto_review_check),
            ("signals.hide_stale", self.hide_stale_check),
        ):
            if key in values:
                check.setChecked(bool(values[key]))
        if "update.source" in values:
            self.update_source_input.setText(str(values["update.source"] or ""))
        if "update.auto_check" in values:
            self.update_auto_check.setChecked(bool(values["update.auto_check"]))
        if "alerts.enabled" in values:
            self.alerts_enabled_check.setChecked(bool(values["alerts.enabled"]))
        if "alerts.sound" in values:
            self.alerts_sound_check.setChecked(bool(values["alerts.sound"]))
        if "ai.signal_mode" in values:
            index = self.signal_mode_combo.findData(values["ai.signal_mode"])
            if index >= 0:
                self.signal_mode_combo.setCurrentIndex(index)

    def collect_values(self) -> dict[str, Any]:
        """
        جمع‌آوری مقادیر برای ذخیره.

        کلیدهای API عمداً در این خروجی نیستند — آن‌ها جداگانه و از طریق
        `SecretStore` ذخیره می‌شوند.
        """
        return {
            "ui.language": self.language_combo.currentData(),
            "ui.theme": self.theme_combo.currentData(),
            "ui.font_family": self.font_family_combo.currentData(),
            "exchange.active": self.exchange_combo.currentData(),
            "ai.enabled": self.ai_enabled_check.isChecked(),
            "ai.provider": self.ai_provider_combo.currentData(),
            "ai.model": self.selected_model(),
            "ai.free_models_only": self.ai_free_only_check.isChecked(),
            "ai.base_url": self.ai_base_url_input.text().strip(),
            "ai.fallback_enabled": self.ai_fallback_check.isChecked(),
            "risk.account_balance": self.balance_spin.value(),
            "risk.risk_percent": self.risk_percent_spin.value(),
            "risk.max_leverage": self.leverage_spin.value(),
            "risk.min_risk_reward": self.min_rr_spin.value(),
            "risk.atr_stop_multiplier": self.atr_spin.value(),
            "backup.auto_enabled": self.auto_backup_check.isChecked(),
            "alerts.enabled": self.alerts_enabled_check.isChecked(),
            "alerts.sound": self.alerts_sound_check.isChecked(),
            # نمایش
            "ui.markets_sort": self.markets_sort_combo.currentData(),
            "ui.font_scale": self.font_scale_spin.value(),
            "ui.compact_mode": self.compact_check.isChecked(),
            "ui.confirm_actions": self.confirm_actions_check.isChecked(),
            "ui.show_toman": self.show_toman_check.isChecked(),
            # هوش مصنوعی و سیگنال
            "ai.signal_mode": self.signal_mode_combo.currentData(),
            "update.source": self.update_source_input.text().strip(),
            "update.auto_check": self.update_auto_check.isChecked(),
            "ai.narrative_enabled": self.narrative_check.isChecked(),
            "ai.save_chat_history": self.save_chat_check.isChecked(),
            "ai.chat_streaming": self.chat_streaming_check.isChecked(),
            "signals.ai_timeout": self.signal_ai_timeout_spin.value(),
            "ai.auto_review": self.auto_review_check.isChecked(),
            "ai.ollama_max_context": self.ollama_context_spin.value(),
            "signals.hide_stale": self.hide_stale_check.isChecked(),
            # کارایی
            "ai.chat_history_limit": self.chat_history_limit_spin.value(),
            "performance.candle_cache_ttl": self.candle_cache_spin.value(),
            "performance.parallel_requests": self.parallel_spin.value(),
            "performance.dashboard_refresh_seconds": self.dashboard_interval_spin.value(),
            "performance.markets_refresh_seconds": self.markets_interval_spin.value(),
            "performance.http_timeout": self.http_timeout_spin.value(),
            "performance.max_retries": self.max_retries_spin.value(),
        }

    def collect_secrets(self) -> dict[str, str]:
        """جمع‌آوری کلیدهای محرمانه برای ذخیره در SecretStore."""
        exchange = str(self.exchange_combo.currentData() or "lbank")
        provider = str(self.ai_provider_combo.currentData() or "ollama")
        return {
            f"exchange.{exchange}.api_key": self.api_key_input.text().strip(),
            f"exchange.{exchange}.api_secret": self.api_secret_input.text().strip(),
            f"ai.{provider}.api_key": self.ai_key_input.text().strip(),
        }

    def open_tab(self, key: str) -> bool:
        """
        باز کردن یک زبانهٔ مشخص با کلید ترجمه‌اش.

        با کلید کار می‌کند نه شمارهٔ ثابت، تا جابه‌جاشدن زبانه‌ها در
        آینده این مسیر را بی‌صدا به زبانهٔ اشتباه نبرد.
        """
        if key not in self.TAB_KEYS:
            return False
        self.tabs.setCurrentIndex(self.TAB_KEYS.index(key))
        return True

    def retranslate(self) -> None:
        """بازسازی متن‌ها."""
        super().retranslate()
        self.save_button.setText(self.tr_.tr("common.save"))
        for index, key in enumerate(self.TAB_KEYS):
            self.tabs.setTabText(index, self.tr_.tr(key))
        self._fill_theme_combo()
        self._fill_font_combo()
        self.font_family_hint.setText(self.tr_.tr("settings.appearance.font_hint"))
        self.theme_editor.retranslate()
        self.delete_theme_button.setText(self.tr_.tr("settings.editor.delete"))
        self._sync_editor_texts()
        self._update_theme_preview()
        self.accounts_title.setText(self.tr_.tr("settings.accounts.title"))
        self.account_add_button.setText(self.tr_.tr("settings.accounts.add"))
        self.account_test_button.setText(self.tr_.tr("settings.accounts.test"))
        self.account_activate_button.setText(self.tr_.tr("settings.accounts.activate"))
        self.account_remove_button.setText(self.tr_.tr("settings.accounts.remove"))
        self._retranslate_accounts_headers()
        self.set_accounts(getattr(self, "_accounts", []))
        self.theme_hint.setText(self.tr_.tr("settings.appearance.theme_hint"))
        for key, label in self._labels.items():
            label.setText(self.tr_.tr(key))
        self.key_hint.setText(self.tr_.tr("settings.credentials_stored_note"))
        self.test_ai_button.setText(self.tr_.tr("settings.test_connection"))
        self.doctor_button.setText(self.tr_.tr("settings.doctor.button"))
        self.load_models_button.setText(self.tr_.tr("settings.load_models"))
        self._on_exchange_changed()
        self._on_ai_provider_changed()
        self.backup_button.setText(self.tr_.tr("settings.backup_now"))
        self.restore_button.setText(self.tr_.tr("settings.restore"))
        self.preserved_note.setText(self.tr_.tr("settings.settings_preserved"))
