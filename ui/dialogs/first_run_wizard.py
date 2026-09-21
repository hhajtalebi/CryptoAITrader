"""
ویزارد اولین اجرا.

طبق بند ۴۳ سند پروژه، کاربر در نخستین اجرا باید بتواند زبان، پوسته،
صرافی و هوش مصنوعی را انتخاب کند.

اصل مهم:
    خروجی ویزارد فقط شامل مقادیری است که کاربر **صریحاً** انتخاب کرده؛
    این مقادیر روی تنظیمات موجود نوشته می‌شوند ولی هیچ تنظیم دیگری را
    بازنشانی نمی‌کنند.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from app.core.constants import APP_NAME
from app.logging import get_logger
from localization import Translator

logger = get_logger(__name__)


class _Page(QWizardPage):
    """صفحه پایه ویزارد با چیدمان عمودی ساده."""

    def __init__(self, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.setTitle(title)
        if subtitle:
            self.setSubTitle(subtitle)
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(11)

    def add(self, widget: QWidget) -> QWidget:
        """افزودن ویجت به صفحه."""
        self._layout.addWidget(widget)
        return widget

    def add_stretch(self) -> None:
        """افزودن فضای خالی انتهایی."""
        self._layout.addStretch(1)


class FirstRunWizard(QWizard):
    """
    ویزارد راه‌اندازی اولیه.

    نمونه‌سازی:
        wizard = FirstRunWizard(translator)
        if wizard.exec():
            settings.set_many(wizard.collected_settings())
    """

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tr_ = translator

        self.setWindowTitle(f"{APP_NAME} — {translator.tr('wizard.title')}")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.resize(620, 460)

        self.addPage(self._build_welcome())
        self.addPage(self._build_appearance())
        self.addPage(self._build_exchange())
        self.addPage(self._build_ai())
        self.addPage(self._build_risk())
        self.addPage(self._build_finish())

    # ------------------------------------------------------------------
    # صفحات
    # ------------------------------------------------------------------
    def _build_welcome(self) -> QWizardPage:
        """صفحه خوش‌آمد و هشدار."""
        page = _Page(self.tr_.tr("wizard.welcome_title"), self.tr_.tr("wizard.welcome_subtitle"))
        body = QLabel(self.tr_.tr("wizard.welcome_body"))
        body.setWordWrap(True)
        page.add(body)

        warning = QLabel(self.tr_.tr("signals.not_financial_advice"))
        warning.setWordWrap(True)
        warning.setProperty("role", "muted")
        page.add(warning)
        page.add_stretch()
        return page

    def _build_appearance(self) -> QWizardPage:
        """انتخاب زبان و پوسته."""
        page = _Page(self.tr_.tr("wizard.appearance_title"), self.tr_.tr("wizard.appearance_subtitle"))

        page.add(QLabel(self.tr_.tr("settings.language")))
        self.language_combo = QComboBox()
        self.language_combo.addItem("فارسی", "fa")
        self.language_combo.addItem("English", "en")
        self.language_combo.setCurrentIndex(0 if self.tr_.language == "fa" else 1)
        page.add(self.language_combo)

        page.add(QLabel(self.tr_.tr("settings.theme")))
        self.theme_combo = QComboBox()
        self.theme_combo.addItem(self.tr_.tr("settings.theme_dark"), "dark")
        self.theme_combo.addItem(self.tr_.tr("settings.theme_light"), "light")
        self.theme_combo.addItem(self.tr_.tr("settings.theme_system"), "system")
        page.add(self.theme_combo)
        page.add_stretch()
        return page

    def _build_exchange(self) -> QWizardPage:
        """انتخاب صرافی؛ کلید API اختیاری است."""
        page = _Page(self.tr_.tr("wizard.exchange_title"), self.tr_.tr("wizard.exchange_subtitle"))

        page.add(QLabel(self.tr_.tr("settings.exchange")))
        self.exchange_combo = QComboBox()
        self.exchange_combo.addItem("LBank", "lbank")
        page.add(self.exchange_combo)

        note = QLabel(self.tr_.tr("wizard.exchange_note"))
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        page.add(note)
        page.add_stretch()
        return page

    def _build_ai(self) -> QWizardPage:
        """پیکربندی هوش مصنوعی؛ کاملاً اختیاری."""
        page = _Page(self.tr_.tr("wizard.ai_title"), self.tr_.tr("wizard.ai_subtitle"))

        self.ai_enabled_check = QCheckBox(self.tr_.tr("wizard.ai_enable"))
        self.ai_enabled_check.setChecked(False)
        page.add(self.ai_enabled_check)

        page.add(QLabel(self.tr_.tr("settings.ai_provider")))
        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItem("Ollama (local, free)", "ollama")
        self.ai_provider_combo.addItem("OpenAI-compatible", "openai_compatible")
        page.add(self.ai_provider_combo)

        page.add(QLabel(self.tr_.tr("settings.ai_model")))
        self.ai_model_input = QLineEdit("llama3.1")
        page.add(self.ai_model_input)

        note = QLabel(self.tr_.tr("wizard.ai_note"))
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        page.add(note)
        page.add_stretch()
        return page

    def _build_risk(self) -> QWizardPage:
        """پارامترهای ریسک با پیش‌فرض محافظه‌کارانه."""
        from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox

        page = _Page(self.tr_.tr("wizard.risk_title"), self.tr_.tr("wizard.risk_subtitle"))

        page.add(QLabel(self.tr_.tr("settings.risk_balance")))
        self.balance_spin = QDoubleSpinBox()
        self.balance_spin.setRange(0, 100_000_000)
        self.balance_spin.setValue(1000)
        page.add(self.balance_spin)

        page.add(QLabel(self.tr_.tr("settings.risk_percent")))
        self.risk_spin = QDoubleSpinBox()
        self.risk_spin.setRange(0.1, 20.0)
        self.risk_spin.setSingleStep(0.1)
        self.risk_spin.setValue(1.0)
        page.add(self.risk_spin)

        page.add(QLabel(self.tr_.tr("settings.max_leverage")))
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 125)
        self.leverage_spin.setValue(5)
        page.add(self.leverage_spin)

        note = QLabel(self.tr_.tr("wizard.risk_note"))
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        page.add(note)
        page.add_stretch()
        return page

    def _build_finish(self) -> QWizardPage:
        """صفحه پایانی."""
        page = _Page(self.tr_.tr("wizard.finish_title"), self.tr_.tr("wizard.finish_subtitle"))
        body = QLabel(self.tr_.tr("wizard.finish_body"))
        body.setWordWrap(True)
        page.add(body)
        page.add_stretch()
        return page

    # ------------------------------------------------------------------
    # خروجی
    # ------------------------------------------------------------------
    def collected_settings(self) -> dict[str, Any]:
        """
        تنظیمات انتخاب‌شده توسط کاربر.

        فقط همین کلیدها ذخیره می‌شوند؛ سایر تنظیمات دست‌نخورده می‌مانند.
        """
        return {
            "ui.language": self.language_combo.currentData(),
            "ui.theme": self.theme_combo.currentData(),
            "exchange.active": self.exchange_combo.currentData(),
            "ai.enabled": self.ai_enabled_check.isChecked(),
            "ai.provider": self.ai_provider_combo.currentData(),
            "ai.model": self.ai_model_input.text().strip(),
            "risk.account_balance": self.balance_spin.value(),
            "risk.risk_percent": self.risk_spin.value(),
            "risk.max_leverage": self.leverage_spin.value(),
        }
