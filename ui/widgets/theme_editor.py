"""
ویرایشگر زندهٔ پوسته.

کاربر خواست «هر جزئیات ظاهری برنامه» قابل تغییر باشد. این ویجت توکن‌های
پوستهٔ فعال را به کنترل تبدیل می‌کند: رنگ‌ها با انتخابگر رنگ، سنجه‌ها با
اسلایدر، و جلوه‌ها با کلید. هر تغییر بی‌درنگ روی کل برنامه می‌نشیند تا
کاربر نتیجه را ببیند، نه اینکه حدس بزند.

چرا فقط زیرمجموعه‌ای از توکن‌ها؟
    ColorTokens حدود چهل رنگ دارد که بیشترشان مشتق‌اند. نمایش همه، یعنی
    دیواری از کنترل که هیچ‌کس در آن چیزی پیدا نمی‌کند. اینجا توکن‌ها در
    گروه‌های معنادار و با برچسب انسانی آمده‌اند، ولی ذخیره‌سازی همچنان
    هر توکنی را می‌پذیرد — ویرایشگر محدود است، قالب داده نیست.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.themes.custom import METRIC_LIMITS
from ui.widgets.common import make_button
from ui.widgets.controls import set_role

#: گروه‌های رنگی که در ویرایشگر نشان داده می‌شوند:
#: (کلید ترجمهٔ عنوان گروه، نام توکن‌ها)
COLOR_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("settings.editor.group_base", ("bg", "surface", "surface_alt", "border")),
    ("settings.editor.group_text", ("text", "text_muted", "text_faint")),
    ("settings.editor.group_brand", ("primary", "primary_hover", "primary_text", "accent")),
    ("settings.editor.group_semantic", ("success", "danger", "warning", "info")),
    (
        "settings.editor.group_sidebar",
        ("sidebar_bg", "sidebar_text", "sidebar_active_bg", "sidebar_active_text"),
    ),
    ("settings.editor.group_chart", ("chart_up", "chart_down", "chart_grid")),
)

#: سنجه‌هایی که کاربر واقعاً می‌خواهد تغییر دهد
METRIC_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("settings.editor.group_radius", ("radius_sm", "radius_md", "radius_lg", "radius_pill")),
    ("settings.editor.group_spacing", ("space_sm", "space_md", "space_lg", "row_height")),
    ("settings.editor.group_size", ("font_md", "font_lg", "font_metric", "border_width")),
)

#: جلوه‌های بولی
EFFECT_ROWS: tuple[str, ...] = ("glass", "elevation")


class ColorButton(QPushButton):
    """
    دکمه‌ای که رنگ فعلی را نشان می‌دهد و با کلیک، انتخابگر رنگ باز می‌کند.

    رنگ به‌صورت درون‌خطی روی خود دکمه می‌نشیند — این تنها جایی است که
    رنگ سخت‌کدشده مجاز است، چون خودِ مقدار همان چیزی است که نمایش داده
    می‌شود.
    """

    color_picked = Signal(str, str)  # نام توکن، رنگ تازه

    def __init__(self, token: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._token = token
        self._value = value
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(58, 26)
        self.clicked.connect(self._choose)
        self.set_color(value)

    @property
    def token(self) -> str:
        """نام توکنی که این دکمه ویرایش می‌کند."""
        return self._token

    @property
    def color(self) -> str:
        """رنگ فعلی."""
        return self._value

    def set_color(self, value: str) -> None:
        """نشاندن رنگ روی دکمه بدون انتشار سیگنال."""
        self._value = str(value or "")
        self.setToolTip(self._value)
        border = "#00000055" if QColor(self._value).lightness() > 128 else "#ffffff55"
        self.setStyleSheet(
            f"background-color: {self._value}; border: 1px solid {border};"
        )

    def _choose(self) -> None:
        """باز کردن انتخابگر رنگ سیستم."""
        initial = QColor(self._value)
        picked = QColorDialog.getColor(
            initial if initial.isValid() else QColor("#000000"),
            self,
            self.toolTip(),
        )
        if not picked.isValid():
            return
        value = picked.name()
        self.set_color(value)
        self.color_picked.emit(self._token, value)


class ThemeEditor(QWidget):
    """
    ویرایشگر توکن‌های پوسته با پیش‌نمایش زنده.

    سیگنال `overrides_changed` پس از هر تغییر منتشر می‌شود و شامل همهٔ
    مقادیر بازنویسی‌شده نسبت به پوستهٔ پایه است.
    """

    #: مقادیر بازنویسی تغییر کرد
    overrides_changed = Signal(dict)
    #: کاربر خواست پوستهٔ فعلی را به‌نام خودش ذخیره کند
    save_requested = Signal()
    #: کاربر خواست همه‌چیز به پوستهٔ پایه برگردد
    reset_requested = Signal()

    def __init__(self, translator: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._base: Any = None
        self._overrides: dict[str, dict[str, Any]] = {}
        self._color_buttons: dict[str, ColorButton] = {}
        self._metric_widgets: dict[str, QSlider] = {}
        self._metric_values: dict[str, QLabel] = {}
        self._effect_checks: dict[str, QCheckBox] = {}
        self._group_labels: list[tuple[QLabel, str]] = []
        self._token_labels: list[tuple[QLabel, str]] = []
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.hint = QLabel("", self)
        self.hint.setWordWrap(True)
        set_role(self.hint, "faint")
        root.addWidget(self.hint)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(0, 0, 8, 0)
        self._body_layout.setSpacing(12)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        self._build_colour_section()
        self._build_metric_section()
        self._build_effect_section()
        self._body_layout.addStretch(1)

        actions = QHBoxLayout()
        self.reset_button = make_button("", role="ghost")
        self.reset_button.clicked.connect(self.reset_requested.emit)
        self.save_button = make_button("", primary=True)
        self.save_button.clicked.connect(self.save_requested.emit)
        actions.addWidget(self.reset_button)
        actions.addStretch(1)
        actions.addWidget(self.save_button)
        root.addLayout(actions)

        self.retranslate()

    # ------------------------------------------------------------------ API
    @property
    def overrides(self) -> dict[str, dict[str, Any]]:
        """مقادیر بازنویسی‌شدهٔ فعلی."""
        return {group: dict(values) for group, values in self._overrides.items() if values}

    def load_theme(self, tokens: Any, overrides: dict[str, Any] | None = None) -> None:
        """
        نشاندن مقادیر یک پوسته در کنترل‌ها.

        `tokens` پوستهٔ پایه است و `overrides` تغییرهای ذخیره‌شدهٔ روی آن.
        در این مدت سیگنال منتشر نمی‌شود، وگرنه صرفِ بازکردن ویرایشگر،
        پوسته را دوباره اعمال می‌کند و سوسو می‌زند.
        """
        self._loading = True
        try:
            self._base = tokens
            self._overrides = {
                "colors": dict((overrides or {}).get("colors") or {}),
                "metrics": dict((overrides or {}).get("metrics") or {}),
                "effects": dict((overrides or {}).get("effects") or {}),
            }

            for token, button in self._color_buttons.items():
                value = self._overrides["colors"].get(
                    token, getattr(tokens.colors, token, "#000000")
                )
                button.set_color(str(value))

            for token, slider in self._metric_widgets.items():
                value = self._overrides["metrics"].get(
                    token, getattr(tokens.metrics, token, slider.minimum())
                )
                slider.setValue(int(value))
                self._metric_values[token].setText(str(int(value)))

            for token, check in self._effect_checks.items():
                value = self._overrides["effects"].get(
                    token, getattr(tokens.effects, token, False)
                )
                check.setChecked(bool(value))
        finally:
            self._loading = False

    def clear_overrides(self) -> None:
        """برگرداندن همهٔ مقادیر به پوستهٔ پایه."""
        if self._base is not None:
            self.load_theme(self._base, {})
        self._emit()

    def retranslate(self) -> None:
        """بازسازی برچسب‌ها پس از تغییر زبان."""
        self.hint.setText(self.tr_.tr("settings.editor.hint"))
        self.reset_button.setText(self.tr_.tr("settings.editor.reset"))
        self.save_button.setText(self.tr_.tr("settings.editor.save_as"))
        for label, key in self._group_labels:
            label.setText(self.tr_.tr(key))
        for label, token in self._token_labels:
            label.setText(self.tr_.tr(f"settings.editor.tokens.{token}", token))

    # ------------------------------------------------------------- ساخت UI
    def _add_group_title(self, key: str) -> None:
        """عنوان یک گروه از تنظیمات."""
        label = QLabel("", self)
        label.setProperty("role", "cardTitle")
        self._body_layout.addWidget(label)
        self._group_labels.append((label, key))

    def _new_form(self) -> QFormLayout:
        """فرم دوستونی برای ردیف‌های یک گروه."""
        holder = QWidget()
        form = QFormLayout(holder)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(7)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self._body_layout.addWidget(holder)
        return form

    def _token_label(self, token: str) -> QLabel:
        """برچسب یک توکن، با ترجمهٔ قابل بازسازی."""
        label = QLabel(token, self)
        self._token_labels.append((label, token))
        return label

    def _build_colour_section(self) -> None:
        """ردیف‌های رنگ، گروه‌بندی‌شده."""
        for group_key, tokens in COLOR_GROUPS:
            self._add_group_title(group_key)
            form = self._new_form()
            for token in tokens:
                button = ColorButton(token, "#000000", self)
                button.color_picked.connect(self._on_colour_picked)
                self._color_buttons[token] = button
                form.addRow(self._token_label(token), button)

    def _build_metric_section(self) -> None:
        """ردیف‌های سنجه: اسلایدر به‌همراه عدد."""
        for group_key, tokens in METRIC_GROUPS:
            self._add_group_title(group_key)
            form = self._new_form()
            for token in tokens:
                low, high = METRIC_LIMITS.get(token, (0, 40))
                slider = QSlider(Qt.Orientation.Horizontal, self)
                slider.setRange(low, high)
                slider.setMinimumWidth(150)
                value_label = QLabel("0", self)
                value_label.setMinimumWidth(34)
                value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)
                row_layout.addWidget(slider, 1)
                row_layout.addWidget(value_label, 0)

                slider.valueChanged.connect(
                    lambda value, name=token: self._on_metric_changed(name, value)
                )
                self._metric_widgets[token] = slider
                self._metric_values[token] = value_label
                form.addRow(self._token_label(token), row)

    def _build_effect_section(self) -> None:
        """کلیدهای جلوه‌های بصری."""
        self._add_group_title("settings.editor.group_effects")
        form = self._new_form()
        for token in EFFECT_ROWS:
            check = QCheckBox(self)
            check.toggled.connect(
                lambda checked, name=token: self._on_effect_changed(name, checked)
            )
            self._effect_checks[token] = check
            form.addRow(self._token_label(token), check)

    # ------------------------------------------------------------- رویدادها
    def _on_colour_picked(self, token: str, value: str) -> None:
        """ثبت رنگ تازه و اعلام تغییر."""
        if self._loading:
            return
        self._record("colors", token, value, getattr(self._base.colors, token, None))

    def _on_metric_changed(self, token: str, value: int) -> None:
        """ثبت سنجهٔ تازه و به‌روزرسانی عدد کنار اسلایدر."""
        self._metric_values[token].setText(str(int(value)))
        if self._loading:
            return
        self._record("metrics", token, int(value), getattr(self._base.metrics, token, None))

    def _on_effect_changed(self, token: str, value: bool) -> None:
        """ثبت جلوهٔ تازه."""
        if self._loading:
            return
        self._record("effects", token, bool(value), getattr(self._base.effects, token, None))

    def _record(self, group: str, token: str, value: Any, base_value: Any) -> None:
        """
        ثبت یک تغییر.

        اگر مقدار به همان چیزی برگردد که پوستهٔ پایه دارد، به‌جای ذخیرهٔ
        یک بازنویسیِ بی‌اثر، کلید حذف می‌شود. این کار پوستهٔ کاربر را
        کوچک و قابل ارتقا نگه می‌دارد.
        """
        bucket = self._overrides.setdefault(group, {})
        if base_value is not None and value == base_value:
            bucket.pop(token, None)
        else:
            bucket[token] = value
        self._emit()

    def _emit(self) -> None:
        """انتشار مجموعهٔ کامل بازنویسی‌ها."""
        self.overrides_changed.emit(self.overrides)


__all__ = ["COLOR_GROUPS", "EFFECT_ROWS", "METRIC_GROUPS", "ColorButton", "ThemeEditor"]
