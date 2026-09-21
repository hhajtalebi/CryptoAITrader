"""
صفحه راهنما.

دو بخش دارد:
    • «راهنمای برنامه» — توضیح مفاهیم کلیدی، به‌ویژه معنای درست «میزان
      اطمینان» و اینکه برنامه معاملهٔ واقعی انجام نمی‌دهد.
    • «آموزش معامله‌گری» — آموزش کامل و مرحله‌به‌مرحله، از مفهوم فیوچرز
      تا مدیریت ریسک و روان‌شناسی معامله.

بخش دوم به‌صورت زبانهٔ جدا آمده نه ادامهٔ همان ستون، چون این دو کاربرد
متفاوتی دارند: یکی مرجع سریع است و دیگری متن خواندنی.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLabel, QScrollArea, QTabWidget, QVBoxLayout, QWidget

from localization import Translator
from ui.pages.base_page import BasePage
from ui.widgets import Card
from ui.widgets.tutorial_view import TutorialView


class HelpPage(BasePage):
    """صفحه راهنمای کاربر."""

    title_key = "nav.help"
    subtitle_key = "help.subtitle"

    #: بخش‌های راهنما: (کلید عنوان، کلید متن)
    SECTIONS = [
        ("help.about_title", "help.about_body"),
        ("help.signals_title", "help.signals_body"),
        ("help.confidence_title", "help.confidence_body"),
        ("help.risk_title", "help.risk_body"),
        ("help.ai_title", "help.ai_body"),
        ("help.chat_title", "help.chat_body"),
        ("help.free_models_title", "help.free_models_body"),
        ("help.security_title", "help.security_body"),
        ("help.disclaimer_title", "help.disclaimer_body"),
    ]

    #: کلیدهای عنوان زبانه‌ها، به همان ترتیب ساخت
    TAB_KEYS = ("help.tab_guide", "tutorial.title")

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._cards: list[tuple[Card, QLabel, str, str]] = []
        super().__init__(translator, parent)

    def build(self) -> None:
        """ساخت زبانه‌های راهنما و آموزش."""
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_guide(), self.tr_.tr("help.tab_guide"))

        self.tutorial = TutorialView(self.tr_, self)
        self.tabs.addTab(self.tutorial, self.tr_.tr("tutorial.title"))

        self.layout_root().addWidget(self.tabs, 1)

    def _build_guide(self) -> QWidget:
        """بخش مرجع: کارت‌های کوتاه دربارهٔ خود برنامه."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 8, 0)
        layout.setSpacing(12)

        for title_key, body_key in self.SECTIONS:
            card = Card(self.tr_.tr(title_key))
            body = QLabel(self.tr_.tr(body_key))
            body.setWordWrap(True)
            card.add(body)
            layout.addWidget(card)
            self._cards.append((card, body, title_key, body_key))

        layout.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def open_tutorial(self, chapter_key: str = "") -> None:
        """
        باز کردن زبانهٔ آموزش، در صورت نیاز روی فصلی مشخص.

        مسیرهای دیگر برنامه (مثلاً پیام خطای ریسک) می‌توانند کاربر را
        مستقیم به درس مربوط بفرستند.
        """
        self.tabs.setCurrentIndex(1)
        if chapter_key:
            self.tutorial.select_chapter(chapter_key)

    def retranslate(self) -> None:
        """بازسازی متن همه بخش‌ها."""
        super().retranslate()
        for index, key in enumerate(self.TAB_KEYS):
            self.tabs.setTabText(index, self.tr_.tr(key))
        for card, body, title_key, body_key in self._cards:
            card.set_title(self.tr_.tr(title_key))
            body.setText(self.tr_.tr(body_key))
        self.tutorial.reload()
