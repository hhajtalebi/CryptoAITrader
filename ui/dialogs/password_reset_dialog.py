"""
بازیابی رمز عبور فراموش‌شده.

پنجره سه گام دارد و هر بار فقط گام جاری دیده می‌شود:
    ۱. نوشتن ایمیل و درخواست کد
    ۲. وارد کردن کد شش‌رقمی
    ۳. گذاشتن رمز تازه

چرا سه گام در یک پنجره و نه سه پنجره؟
    کاربر وسط کار باید بتواند ایمیلش را اصلاح کند یا کد را دوباره
    بخواهد؛ با پنجره‌های جدا این رفت‌وبرگشت آزاردهنده می‌شود.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.security.passwords import password_strength
from localization import Translator
from ui.widgets.common import make_button
from ui.widgets.controls import set_role

#: شمارش معکوس دکمهٔ «ارسال دوباره» بر حسب ثانیه
RESEND_SECONDS = 60


class PasswordResetDialog(QDialog):
    """
    پنجرهٔ بازیابی رمز.

    نمونه‌سازی:
        dialog = PasswordResetDialog(translator, reset_service, parent)
        dialog.exec()
    """

    #: رمز با موفقیت عوض شد؛ نام کاربری/ایمیل فرستاده می‌شود
    password_reset = Signal(str)

    STEP_EMAIL = 0
    STEP_CODE = 1
    STEP_PASSWORD = 2

    def __init__(
        self,
        translator: Translator,
        reset_service: Any,
        parent: QWidget | None = None,
        *,
        email: str = "",
    ) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._service = reset_service
        self._email = str(email or "")
        self._remaining = 0

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self.setWindowTitle(self.tr_.tr("auth.reset.title"))
        self.setModal(True)
        self.setMinimumWidth(440)
        self._build()
        self._show_step(self.STEP_EMAIL)

    # ------------------------------------------------------------------
    # ساخت
    # ------------------------------------------------------------------
    def _build(self) -> None:
        """ساخت سه گام."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        self.title_label = QLabel(self.tr_.tr("auth.reset.title"))
        set_role(self.title_label, "title")
        layout.addWidget(self.title_label)

        self.hint_label = QLabel("")
        set_role(self.hint_label, "faint")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.steps = QStackedWidget(self)
        self.steps.addWidget(self._build_email_step())
        self.steps.addWidget(self._build_code_step())
        self.steps.addWidget(self._build_password_step())
        # هر گام ارتفاع خودش را دارد؛ بدون این، پنجره به قد کوتاه‌ترین
        # صفحه می‌ماند و متن راهنمای گام کد بریده می‌شد.
        self.steps.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding
        )
        layout.addWidget(self.steps)

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.setVisible(False)
        layout.addWidget(self.message_label)

        buttons = QHBoxLayout()
        self.back_button = make_button(self.tr_.tr("common.back"))
        self.back_button.setFlat(True)
        self.back_button.clicked.connect(self._go_back)
        buttons.addWidget(self.back_button)
        buttons.addStretch(1)

        self.cancel_button = make_button(self.tr_.tr("common.cancel"))
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)

        self.next_button = make_button(self.tr_.tr("auth.reset.send_code"), primary=True)
        self.next_button.setDefault(True)
        self.next_button.clicked.connect(self._advance)
        buttons.addWidget(self.next_button)
        layout.addLayout(buttons)

    def _build_email_step(self) -> QWidget:
        """گام ۱: ایمیل."""
        page = QWidget(self)
        form = QFormLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(9)

        self.email_input = QLineEdit(page)
        self.email_input.setText(self._email)
        self.email_input.setPlaceholderText("you@gmail.com")
        self.email_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.email_input.returnPressed.connect(self._advance)
        form.addRow(self.tr_.tr("auth.email"), self.email_input)
        return page

    def _build_code_step(self) -> QWidget:
        """گام ۲: کد تأیید."""
        page = QWidget(self)
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(9)

        form = QFormLayout()
        form.setSpacing(9)
        self.code_input = QLineEdit(page)
        self.code_input.setMaxLength(6)
        self.code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.code_input.setPlaceholderText("------")
        self.code_input.returnPressed.connect(self._advance)
        # کد فقط رقم است؛ نگذاریم کاربر حرف تایپ کند
        self.code_input.setInputMask("999999")
        font = self.code_input.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        self.code_input.setFont(font)
        form.addRow(self.tr_.tr("auth.reset.code"), self.code_input)
        box.addLayout(form)

        self.resend_button = make_button(self.tr_.tr("auth.reset.resend"))
        self.resend_button.setFlat(True)
        self.resend_button.clicked.connect(self._resend)
        box.addWidget(self.resend_button, alignment=Qt.AlignmentFlag.AlignLeft)

        # وقتی SMTP تنظیم نشده باشد کد همین‌جا نشان داده می‌شود.
        # کد **جدا** از جملهٔ فارسی نمایش داده می‌شود: عدد لاتین داخل متن
        # راست‌به‌چپ جابه‌جا و ناخوانا می‌شود، و کاربر هم باید بتواند آن را
        # یک‌جا ببیند و کپی کند.
        self.offline_box = QWidget(page)
        offline_layout = QVBoxLayout(self.offline_box)
        offline_layout.setContentsMargins(0, 6, 0, 0)
        offline_layout.setSpacing(4)

        self.offline_hint = QLabel(self.tr_.tr("auth.reset.offline_hint"), self.offline_box)
        self.offline_hint.setWordWrap(True)
        set_role(self.offline_hint, "warning")
        offline_layout.addWidget(self.offline_hint)

        self.offline_code = QLineEdit(self.offline_box)
        self.offline_code.setReadOnly(True)
        self.offline_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.offline_code.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        code_font = self.offline_code.font()
        code_font.setPointSize(code_font.pointSize() + 5)
        code_font.setBold(True)
        self.offline_code.setFont(code_font)
        offline_layout.addWidget(self.offline_code)

        self.offline_box.setVisible(False)
        box.addWidget(self.offline_box)
        return page

    def _build_password_step(self) -> QWidget:
        """گام ۳: رمز تازه."""
        page = QWidget(self)
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(9)

        form = QFormLayout()
        form.setSpacing(9)
        self.password_input = QLineEdit(page)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.textChanged.connect(self._update_strength)
        form.addRow(self.tr_.tr("auth.reset.new_password"), self.password_input)

        self.confirm_input = QLineEdit(page)
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.returnPressed.connect(self._advance)
        form.addRow(self.tr_.tr("auth.password_confirm"), self.confirm_input)
        box.addLayout(form)

        self.strength_bar = QProgressBar(page)
        self.strength_bar.setRange(0, 4)
        self.strength_bar.setTextVisible(False)
        self.strength_bar.setFixedHeight(6)
        box.addWidget(self.strength_bar)

        self.strength_label = QLabel("")
        set_role(self.strength_label, "faint")
        box.addWidget(self.strength_label)
        return page

    # ------------------------------------------------------------------
    # جریان
    # ------------------------------------------------------------------
    def _show_step(self, index: int) -> None:
        """نمایش یک گام و به‌روزرسانی دکمه‌ها."""
        self.steps.setCurrentIndex(index)
        self.back_button.setVisible(index > self.STEP_EMAIL)
        self.message_label.setVisible(False)

        hints = {
            self.STEP_EMAIL: "auth.reset.hint_email",
            self.STEP_CODE: "auth.reset.hint_code",
            self.STEP_PASSWORD: "auth.reset.hint_password",
        }
        self.hint_label.setText(self.tr_.tr(hints[index]))

        labels = {
            self.STEP_EMAIL: "auth.reset.send_code",
            self.STEP_CODE: "auth.reset.verify",
            self.STEP_PASSWORD: "auth.reset.save",
        }
        self.next_button.setText(self.tr_.tr(labels[index]))

        focus = {
            self.STEP_EMAIL: self.email_input,
            self.STEP_CODE: self.code_input,
            self.STEP_PASSWORD: self.password_input,
        }
        focus[index].setFocus()

        # فقط صفحهٔ جاری باید در محاسبهٔ اندازه شرکت کند
        for position in range(self.steps.count()):
            page = self.steps.widget(position)
            policy = page.sizePolicy()
            policy.setVerticalPolicy(
                QSizePolicy.Policy.MinimumExpanding
                if position == index
                else QSizePolicy.Policy.Ignored
            )
            page.setSizePolicy(policy)

        self.steps.adjustSize()
        self.adjustSize()

    def _go_back(self) -> None:
        """بازگشت به گام پیشین."""
        index = self.steps.currentIndex()
        if index > self.STEP_EMAIL:
            self._show_step(index - 1)

    def _advance(self) -> None:
        """اجرای گام جاری."""
        index = self.steps.currentIndex()
        if index == self.STEP_EMAIL:
            self._request_code()
        elif index == self.STEP_CODE:
            self._verify_code()
        else:
            self._save_password()

    def _request_code(self) -> None:
        """گام ۱ → درخواست کد."""
        email = self.email_input.text().strip()
        ok, error, info = self._service.request_code(email)
        if not ok:
            retry = info.get("retry_after")
            if retry:
                self._show_message(
                    self.tr_.tr(error, seconds=retry), error=True
                )
            else:
                self._show_message(self.tr_.tr(error), error=True)
            return

        self._email = email
        offline = str(info.get("offline_code") or "")
        if offline:
            # بدون SMTP نمی‌توان ایمیل فرستاد؛ کد را همین‌جا نشان می‌دهیم
            # و صریح می‌گوییم چرا، تا کاربر گمان نکند ایمیل گم شده است.
            self.offline_code.setText(offline)
            self.offline_box.setVisible(True)
        else:
            self.offline_code.clear()
            self.offline_box.setVisible(False)

        self._show_step(self.STEP_CODE)
        self._show_message(
            self.tr_.tr("auth.reset.code_sent", email=info.get("masked", email)),
            error=False,
        )
        self._start_cooldown()

    def _verify_code(self) -> None:
        """گام ۲ → بررسی کد."""
        code = self.code_input.text().strip()
        ok, error = self._service.verify_code(self._email, code)
        if not ok:
            self._show_message(self.tr_.tr(error), error=True)
            if error in {
                "auth.error.reset_too_many_attempts",
                "auth.error.reset_expired",
            }:
                # کد سوخته؛ کاربر باید از اول شروع کند
                self.code_input.clear()
                self._show_step(self.STEP_EMAIL)
            return
        self._show_step(self.STEP_PASSWORD)

    def _save_password(self) -> None:
        """گام ۳ → نشاندن رمز تازه."""
        password = self.password_input.text()
        if password != self.confirm_input.text():
            self._show_message(self.tr_.tr("auth.error.password_mismatch"), error=True)
            return

        ok, error = self._service.reset_password(
            self._email, self.code_input.text().strip(), password
        )
        # رمز بی‌درنگ از فرم پاک می‌شود
        self.password_input.clear()
        self.confirm_input.clear()

        if not ok:
            self._show_message(self.tr_.tr(error), error=True)
            return

        self.password_reset.emit(self._email)
        self.accept()

    def _resend(self) -> None:
        """درخواست دوبارهٔ کد."""
        self._show_step(self.STEP_EMAIL)
        self._request_code()

    # ------------------------------------------------------------------
    # کمکی
    # ------------------------------------------------------------------
    def _start_cooldown(self) -> None:
        """
        غیرفعال‌کردن موقت دکمهٔ ارسال دوباره.

        سرویس هم سمت خودش محدودیت دارد؛ این فقط جلوی دیدن پیام خطای
        بی‌مورد را می‌گیرد.
        """
        self._remaining = RESEND_SECONDS
        self.resend_button.setEnabled(False)
        self._tick()
        self._timer.start()

    def _tick(self) -> None:
        """شمارش معکوس."""
        if self._remaining <= 0:
            self._timer.stop()
            self.resend_button.setEnabled(True)
            self.resend_button.setText(self.tr_.tr("auth.reset.resend"))
            return
        seconds = str(self._remaining)
        if getattr(self.tr_, "is_rtl", False):
            seconds = self.tr_.to_persian_digits(seconds)
        self.resend_button.setText(
            self.tr_.tr("auth.reset.resend_in", seconds=seconds)
        )
        self._remaining -= 1

    def _update_strength(self, value: str) -> None:
        """نمایش قدرت رمز تازه."""
        score, key = password_strength(value)
        self.strength_bar.setValue(score)
        self.strength_label.setText(self.tr_.tr(key))

    def _show_message(self, text: str, *, error: bool) -> None:
        """نمایش پیام موفقیت یا خطا."""
        self.message_label.setText(text)
        set_role(self.message_label, "danger" if error else "success")
        self.message_label.setVisible(bool(text))

    def closeEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """لغو درخواست در جریان هنگام بستن پنجره."""
        self._timer.stop()
        if self._email:
            self._service.cancel(self._email)
        super().closeEvent(event)


__all__ = ["PasswordResetDialog", "RESEND_SECONDS"]
