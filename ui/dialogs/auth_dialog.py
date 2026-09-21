"""
گفت‌وگوی ورود و ثبت‌نام.

یک پنجره با دو حالت (ورود / ثبت‌نام) که با یک پیوند جابه‌جا می‌شوند؛ دو
پنجرهٔ جدا لازم نیست و کاربر رشتهٔ کار را گم نمی‌کند.

نکتهٔ امنیتی: این گفت‌وگو هرگز رمز را نگه نمی‌دارد یا لاگ نمی‌کند؛ فقط
آن را به `AuthService` می‌دهد و پاک می‌کند.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.core.email_service import is_valid_email
from app.security.passwords import password_strength
from localization import Translator
from ui.widgets import make_button, set_role


class AuthDialog(QDialog):
    """
    ورود یا ثبت‌نام کاربر.

    نمونه‌سازی:
        dialog = AuthDialog(translator, auth_service, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            ...
    """

    #: کاربر با موفقیت وارد یا ثبت‌نام شد
    authenticated = Signal(dict)

    def __init__(
        self,
        translator: Translator,
        auth_service: Any,
        parent: QWidget | None = None,
        *,
        register_mode: bool = False,
        reset_service: Any = None,
    ) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._auth = auth_service
        self._reset_service = reset_service
        self._register_mode = bool(register_mode)

        self.setWindowTitle(self.tr_.tr("auth.login"))
        self.setModal(True)
        self.setMinimumWidth(420)
        self._build()
        self._apply_mode()

    # ------------------------------------------------------------------
    # ساخت
    # ------------------------------------------------------------------
    def _build(self) -> None:
        """ساخت فرم."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        self.title_label = QLabel(self.tr_.tr("auth.login"))
        set_role(self.title_label, "title")
        layout.addWidget(self.title_label)

        self.hint_label = QLabel(self.tr_.tr("auth.guest_hint"))
        set_role(self.hint_label, "faint")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        form = QFormLayout()
        form.setSpacing(9)

        self.username_input = QLineEdit(self)
        self.username_input.setText(
            str(self._auth.preference("auth.last_username", "") or "")
        )
        # برچسب این فیلد بین دو حالت فرق می‌کند: هنگام ثبت‌نام «نام
        # کاربری» ساخته می‌شود، ولی هنگام ورود ایمیل و نام هم پذیرفته است.
        self.username_label = QLabel(self.tr_.tr("auth.username"))
        form.addRow(self.username_label, self.username_input)

        self.display_name_input = QLineEdit(self)
        self.display_name_row = self.tr_.tr("auth.display_name")
        form.addRow(self.display_name_row, self.display_name_input)

        self.email_input = QLineEdit(self)
        self.email_input.setPlaceholderText("you@gmail.com")
        self.email_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.email_row = self.tr_.tr("auth.email")
        form.addRow(self.email_row, self.email_input)

        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.textChanged.connect(self._update_strength)
        form.addRow(self.tr_.tr("auth.password"), self.password_input)

        self.confirm_input = QLineEdit(self)
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_row = self.tr_.tr("auth.password_confirm")
        form.addRow(self.confirm_row, self.confirm_input)

        layout.addLayout(form)

        # نوار قدرت رمز — فقط در حالت ثبت‌نام معنا دارد
        self.strength_bar = QProgressBar(self)
        self.strength_bar.setRange(0, 4)
        self.strength_bar.setTextVisible(False)
        self.strength_bar.setFixedHeight(6)
        layout.addWidget(self.strength_bar)

        self.strength_label = QLabel("")
        set_role(self.strength_label, "faint")
        layout.addWidget(self.strength_label)

        remember_row = QHBoxLayout()
        self.remember_check = QCheckBox(self.tr_.tr("auth.remember_me"), self)
        self.remember_check.setChecked(True)
        remember_row.addWidget(self.remember_check)
        remember_row.addStretch(1)

        # بدون این پیوند، کاربری که رمزش را فراموش کرده هیچ راهی ندارد
        self.forgot_button = make_button(self.tr_.tr("auth.reset.forgot"))
        self.forgot_button.setFlat(True)
        self.forgot_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.forgot_button.clicked.connect(self.open_password_reset)
        remember_row.addWidget(self.forgot_button)
        layout.addLayout(remember_row)

        self.error_label = QLabel("")
        set_role(self.error_label, "danger")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        self.switch_button = make_button(self.tr_.tr("auth.no_account"))
        self.switch_button.setFlat(True)
        self.switch_button.clicked.connect(self._toggle_mode)
        buttons.addWidget(self.switch_button)
        buttons.addStretch(1)

        self.cancel_button = make_button(self.tr_.tr("common.cancel"))
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)

        self.submit_button = make_button(self.tr_.tr("auth.login"), primary=True)
        self.submit_button.setDefault(True)
        self.submit_button.clicked.connect(self._submit)
        buttons.addWidget(self.submit_button)
        layout.addLayout(buttons)

        self.password_input.returnPressed.connect(self._submit)
        self.username_input.returnPressed.connect(self._submit)

    # ------------------------------------------------------------------
    # حالت
    # ------------------------------------------------------------------
    def _apply_mode(self) -> None:
        """نمایش یا پنهان‌کردن فیلدهای مخصوص ثبت‌نام."""
        register = self._register_mode
        form = self.findChild(QFormLayout)

        for widget, visible in (
            (self.display_name_input, register),
            (self.email_input, register),
            (self.confirm_input, register),
        ):
            widget.setVisible(visible)
            label = form.labelForField(widget) if form else None
            if label is not None:
                label.setVisible(visible)

        self.strength_bar.setVisible(register)
        self.strength_label.setVisible(register)
        self.remember_check.setVisible(not register)
        # بازیابی رمز فقط در حالت ورود معنا دارد و فقط وقتی سرویسش هست
        self.forgot_button.setVisible(not register and self._reset_service is not None)

        # در حالت ورود بگو که ایمیل هم قبول است، وگرنه کاربر گمان می‌کند
        # فقط نام کاربری کار می‌کند و با اطلاعات درست هم وارد نمی‌شود.
        self.username_label.setText(
            self.tr_.tr("auth.username" if register else "auth.identifier")
        )
        self.username_input.setPlaceholderText(
            "" if register else self.tr_.tr("auth.identifier_hint")
        )

        title = self.tr_.tr("auth.register" if register else "auth.login")
        self.setWindowTitle(title)
        self.title_label.setText(title)
        self.submit_button.setText(title)
        self.switch_button.setText(
            self.tr_.tr("auth.have_account" if register else "auth.no_account")
        )
        self.error_label.setVisible(False)
        self.adjustSize()

    def _toggle_mode(self) -> None:
        """جابه‌جایی میان ورود و ثبت‌نام."""
        self._register_mode = not self._register_mode
        self._apply_mode()

    def _update_strength(self, value: str) -> None:
        """نمایش قدرت رمز هنگام تایپ."""
        if not self._register_mode:
            return
        score, key = password_strength(value)
        self.strength_bar.setValue(score)
        self.strength_label.setText(self.tr_.tr(key))

    # ------------------------------------------------------------------
    # ارسال
    # ------------------------------------------------------------------
    def _submit(self) -> None:
        """اعتبارسنجی و فراخوانی سرویس احراز هویت."""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username:
            self._show_error("auth.error.username_required")
            return

        if self._register_mode:
            if password != self.confirm_input.text():
                self._show_error("auth.error.password_mismatch")
                return
            # ایمیل هنگام ثبت‌نام اجباری است: بدون آن، بازیابی رمز در
            # آینده ناممکن می‌شود و کاربر برای همیشه از حسابش بیرون
            # می‌ماند.
            email = self.email_input.text().strip()
            if not email:
                self._show_error("auth.error.email_required")
                return
            if not is_valid_email(email):
                self._show_error("auth.error.invalid_email")
                return
            user, error = self._auth.register(
                username,
                password,
                email=email,
                display_name=self.display_name_input.text().strip(),
            )
        else:
            user, error = self._auth.login(
                username, password, remember=self.remember_check.isChecked()
            )

        # رمز بلافاصله از حافظهٔ فرم پاک می‌شود
        self.password_input.clear()
        self.confirm_input.clear()

        if user is None:
            self._show_error(error or "auth.error.invalid_credentials")
            return

        self.authenticated.emit(user)
        self.accept()

    def open_password_reset(self) -> None:
        """
        باز کردن پنجرهٔ بازیابی رمز.

        ایمیل یا نام کاربری که کاربر از قبل تایپ کرده منتقل می‌شود تا
        دوباره ننویسد.
        """
        if self._reset_service is None:
            return

        from ui.dialogs.password_reset_dialog import PasswordResetDialog

        typed = self.username_input.text().strip()
        dialog = PasswordResetDialog(
            self.tr_,
            self._reset_service,
            self,
            email=typed if is_valid_email(typed) else "",
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._show_message("auth.reset.success")

    def _show_message(self, key: str) -> None:
        """نمایش پیام موفقیت."""
        self.error_label.setText(self.tr_.tr(key))
        set_role(self.error_label, "success")
        self.error_label.setVisible(True)

    def _show_error(self, key: str) -> None:
        """نمایش پیام خطای محلی‌شده."""
        set_role(self.error_label, "danger")
        self.error_label.setText(self.tr_.tr(key))
        self.error_label.setVisible(True)


__all__ = ["AuthDialog"]
