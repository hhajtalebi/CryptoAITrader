"""
پنجرهٔ جزئیات کامل یک سیگنال.

کاربر خواست با کلیک روی نماد در جدول «آخرین سیگنال‌ها»، همهٔ جزئیات را
یک‌جا ببیند و بتواند از همان‌جا اقدام کند.

دربارهٔ دکمهٔ اقدام: این نسخه **سفارش واقعی ثبت نمی‌کند**. معامله به‌صورت
کاغذی (تمرینی) ثبت می‌شود و ساختار طوری چیده شده که بعداً با اتصال یک
`OrderExecutor` واقعی، همین دکمه سفارش زنده بفرستد. این تصمیم عمدی است:
دکمه‌ای که پول واقعی جابه‌جا کند نباید بدون آزمون کامل و تأیید صریح فعال
شود.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from localization import Translator
from ui.signal_share import (
    SHARE_TARGETS,
    copy_to_clipboard,
    format_signal_text,
    open_url,
    share_mode,
    share_url,
    signal_symbol,
)
from ui.widgets import make_button
from ui.widgets.position_calculator import PositionCalculator


#: وضعیت‌هایی که ورود تازه در آن‌ها مجاز نیست.
#: از `signals.validity` تکرار نمی‌شود تا لایهٔ رابط کاربری به لایهٔ
#: دامنه وابسته نشود؛ مقدارها رشته‌های ساده‌اند و قرارداد پایدار است.
NOT_ENTERABLE_STATES = frozenset({"STALE", "EXPIRED", "INVALIDATED"})


class _TokenOnly:
    """
    آداپتور کوچک برای `color_for` که یک شیء دارای `token` می‌خواهد.

    توصیه درجه‌بندی نیست — نشان و تأکید ندارد — ولی باید از همان
    سامانهٔ رنگ پوسته استفاده کند تا با تغییر پوسته هماهنگ بماند.
    رنگ سخت‌کدشده در پوستهٔ روشن ناخواناست.
    """

    __slots__ = ("token",)

    def __init__(self, token: str) -> None:
        self.token = token


class SignalDetailDialog(QDialog):
    """
    نمایش کامل یک سیگنال به‌همراه دکمهٔ اقدام.

    مثال:
        dialog = SignalDetailDialog(signal_dict, translator, parent)
        dialog.trade_requested.connect(handler)
        dialog.exec()
    """

    #: وقتی کاربر دکمهٔ اقدام را می‌زند، با دادهٔ سیگنال منتشر می‌شود
    trade_requested = Signal(dict)

    def __init__(
        self,
        signal: dict[str, Any],
        translator: Translator,
        parent: QWidget | None = None,
        *,
        theme: Any = None,
    ) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._signal = dict(signal or {})
        # پوسته برای رنگ‌های درجه‌بندی لازم است. `None` مجاز است:
        # `color_for` خودش به رنگ خنثی برمی‌گردد.
        self._theme = theme

        self.setWindowTitle(
            self.tr_.tr("signals.detail_title", symbol=self._signal.get("symbol", ""))
        )
        self.setMinimumSize(560, 620)
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if self.tr_.is_rtl else Qt.LayoutDirection.LeftToRight
        )
        self._build()

    # ------------------------------------------------------------------
    # ساخت رابط
    # ------------------------------------------------------------------
    def _build(self) -> None:
        """چیدمان بخش‌های پنجره."""
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(14)

        root.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)

        recommendation = self._build_recommendation()
        if recommendation is not None:
            body_layout.addWidget(recommendation)
        body_layout.addWidget(self._build_levels())
        validity = self._build_validity()
        if validity is not None:
            body_layout.addWidget(validity)
        forecast = self._build_forecast()
        if forecast is not None:
            body_layout.addWidget(forecast)
        body_layout.addWidget(self._build_calculator())
        body_layout.addWidget(self._build_meta())
        reasoning = self._build_reasoning()
        if reasoning is not None:
            body_layout.addWidget(reasoning)
        review = self._build_review()
        if review is not None:
            body_layout.addWidget(review)
        body_layout.addStretch(1)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        root.addWidget(self._build_disclaimer())
        root.addLayout(self._build_buttons())

    def _build_header(self) -> QWidget:
        """سربرگ: نماد، جهت و درجهٔ اطمینان."""
        frame = QFrame()
        frame.setProperty("role", "card")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)

        left = QVBoxLayout()
        symbol = QLabel(str(self._signal.get("symbol", "—")))
        symbol.setProperty("role", "title")
        left.addWidget(symbol)

        timeframe = self._signal.get("primary_timeframe") or self._signal.get("timeframe") or ""
        if timeframe:
            tf_label = QLabel(self.tr_.tr("signals.timeframe_label", timeframe=str(timeframe)))
            tf_label.setProperty("role", "muted")
            left.addWidget(tf_label)
        layout.addLayout(left)
        layout.addStretch(1)

        right = QVBoxLayout()
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        direction = str(self._signal.get("direction", "WAIT")).upper()
        direction_label = QLabel(self.tr_.tr(f"signals.{direction.lower()}", direction))
        direction_label.setProperty("role", self._direction_role(direction))
        font = direction_label.font()
        font.setPointSize(font.pointSize() + 6)
        font.setBold(True)
        direction_label.setFont(font)
        direction_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(direction_label)

        confidence = self._signal.get("confidence", 0)
        conf_label = QLabel(
            self.tr_.tr("signals.confidence") + f": {self.tr_.to_persian_digits(str(confidence))}%"
        )
        conf_label.setProperty("role", "muted")
        conf_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(conf_label)

        layout.addLayout(right)
        return frame

    def _build_levels(self) -> QWidget:
        """قیمت‌های ورود، حد ضرر و اهداف سود."""
        frame = QFrame()
        frame.setProperty("role", "card")
        layout = QGridLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(10)

        title = QLabel(self.tr_.tr("signals.levels"))
        title.setProperty("role", "subtitle")
        layout.addWidget(title, 0, 0, 1, 2)

        entry = self._entry_text()
        rows: list[tuple[str, str, str]] = [
            (self.tr_.tr("signals.entry"), entry, ""),
            (self.tr_.tr("signals.stop_loss"), self._price(self._signal.get("stop_loss")), "bearish"),
        ]

        take_profits = self._signal.get("take_profits") or self._signal.get("take_profit") or []
        if isinstance(take_profits, (int, float)):
            take_profits = [take_profits]
        for index, target in enumerate(list(take_profits)[:5], start=1):
            rows.append(
                (self.tr_.tr("signals.take_profit_n", index=index), self._price(target), "bullish")
            )

        risk_reward = self._signal.get("risk_reward")
        if risk_reward:
            rows.append(
                (self.tr_.tr("signals.risk_reward"), f"{float(risk_reward):.2f}", "")
            )
        leverage = self._signal.get("leverage")
        if leverage:
            rows.append((self.tr_.tr("signals.leverage"), f"×{leverage}", ""))

        for offset, (key, value, role) in enumerate(rows, start=1):
            key_label = QLabel(key)
            key_label.setProperty("role", "muted")
            value_label = QLabel(value)
            if role:
                value_label.setProperty("role", role)
            value_font = value_label.font()
            value_font.setBold(True)
            value_label.setFont(value_font)
            layout.addWidget(key_label, offset, 0)
            layout.addWidget(value_label, offset, 1)

        layout.setColumnStretch(1, 1)
        return frame

    def _build_forecast(self) -> QWidget | None:
        """
        جدول پیش‌بینی بازهٔ محتمل قیمت برای افق‌های بعدی.

        اگر سیگنال پیش‌بینی ندارد (سیگنال‌های قدیمی، یا داده ناکافی
        بوده) این بخش کلاً ساخته نمی‌شود — جای خالی بهتر از عدد ساختگی
        است.
        """
        horizons = self._signal.get("forecast") or []
        if not isinstance(horizons, list) or not horizons:
            return None

        frame = QFrame()
        frame.setProperty("role", "card")
        layout = QGridLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(10)

        title = QLabel(self.tr_.tr("signals.forecast"))
        title.setProperty("role", "subtitle")
        layout.addWidget(title, 0, 0, 1, 3)

        note = QLabel(self.tr_.tr("signals.forecast_note"))
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        layout.addWidget(note, 1, 0, 1, 3)

        arrow = {"bullish": "▲", "bearish": "▼", "neutral": "◆"}
        row = 2
        for item in horizons:
            if not isinstance(item, dict):
                continue
            # ردیف ناقص رد می‌شود؛ «افق ؟ با بازهٔ ۰ تا ۰» بدتر از
            # نشان‌ندادن است.
            if item.get("horizon") is None or item.get("lower") is None:
                continue
            try:
                horizon = str(item["horizon"])
                lower = float(item["lower"])
                upper = float(item["upper"])
                probability = int(item.get("probability", 0))
                bias = str(item.get("bias", "neutral"))
            except (KeyError, TypeError, ValueError):
                continue
            if upper < lower:
                continue

            name = QLabel(f"{arrow.get(bias, '◆')}  {horizon}")
            name.setProperty("role", "muted")

            # بازهٔ قیمت همیشه چپ‌به‌راست خوانده می‌شود، حتی در چیدمان
            # راست‌به‌چپ؛ وگرنه کف و سقف جابه‌جا دیده می‌شوند.
            band = QLabel(f"{self._price(lower)} … {self._price(upper)}")
            band.setTextFormat(Qt.TextFormat.PlainText)
            band.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

            chance = QLabel(f"{probability}%")
            chance.setProperty(
                "role", {"bullish": "bullish", "bearish": "bearish"}.get(bias, "")
            )

            layout.addWidget(name, row, 0)
            layout.addWidget(band, row, 1)
            layout.addWidget(chance, row, 2)
            row += 1

        if row == 2:
            return None
        return frame

    def _build_calculator(self) -> QWidget:
        """
        ماشین‌حساب حجم، از پیش پرشده با اعداد همین سیگنال.

        اینجا می‌آید نه در صفحه‌ای جدا، چون تصمیم «با چه حجمی وارد شوم»
        دقیقاً همین‌جا گرفته می‌شود. کاربر نباید عددها را جای دیگری
        دوباره تایپ کند.
        """
        frame = QFrame()
        frame.setProperty("role", "card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel(self.tr_.tr("sizing.title"))
        title.setProperty("role", "subtitle")
        layout.addWidget(title)

        hint = QLabel(self.tr_.tr("sizing.hint"))
        hint.setProperty("role", "faint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.calculator = PositionCalculator(self.tr_, frame)
        self.calculator.load_signal(self._signal)
        layout.addWidget(self.calculator)
        return frame

    def set_account_balance(
        self, amount: float, risk_percent: float = 0.0, source_text: str = ""
    ) -> None:
        """
        نشاندن سرمایه و درصد ریسک واقعی کاربر در ماشین‌حساب.

        کنترلر این را از کیف پول/موجودی کاغذی و تنظیمات ریسک می‌دهد؛ خود
        پنجره به پایگاه داده دسترسی ندارد و نباید داشته باشد.
        """
        if amount > 0:
            self.calculator.set_capital(amount)
        if risk_percent > 0:
            self.calculator.set_risk_percent(risk_percent)
        if source_text:
            self.calculator.set_capital_source(source_text)

    def trade_payload(self) -> dict[str, Any]:
        """
        سیگنال + اعداد فعلی ماشین‌حساب (v2.5.0).

        معامله با همان ورود/حد ضرر/TP1..TP3/اهرم/سرمایهٔ ماشین‌حساب باز
        می‌شود؛ اگر کاربر عددی را ویرایش کرده باشد، همان اعمال می‌شود.
        """
        payload = dict(self._signal)
        payload["plan"] = self.calculator.trade_values()
        return payload

    def trade_opened(self) -> None:
        """پس از باز شدن موفق معامله، پنجره بسته می‌شود (خواستهٔ کاربر)."""
        self.accept()

    def _build_meta(self) -> QWidget:
        """اطلاعات تکمیلی: روند، ساختار بازار، زمان و منبع."""
        frame = QFrame()
        frame.setProperty("role", "card")
        layout = QGridLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(10)

        title = QLabel(self.tr_.tr("signals.context"))
        title.setProperty("role", "subtitle")
        layout.addWidget(title, 0, 0, 1, 2)

        candidates: list[tuple[str, Any]] = [
            (self.tr_.tr("analysis.trend"), self._signal.get("trend")),
            (self.tr_.tr("analysis.structure"), self._signal.get("market_structure")),
            (self.tr_.tr("signals.generated_at"), self._signal.get("created_at")),
            (self.tr_.tr("dashboard.ai_provider"), self._signal.get("ai_provider")),
            (self.tr_.tr("settings.ai_model"), self._signal.get("ai_model")),
        ]

        row = 1
        for key, value in candidates:
            if value in (None, "", "—"):
                continue
            key_label = QLabel(key)
            key_label.setProperty("role", "muted")
            layout.addWidget(key_label, row, 0)
            layout.addWidget(QLabel(str(value)), row, 1)
            row += 1

        if row == 1:
            empty = QLabel(self.tr_.tr("common.no_data"))
            empty.setProperty("role", "muted")
            layout.addWidget(empty, 1, 0, 1, 2)

        layout.setColumnStretch(1, 1)
        return frame

    def _build_reasoning(self) -> QWidget | None:
        """متن دلیل و تحلیل، اگر موجود باشد."""
        text = ""
        for key in ("analysis_text", "reason", "rejection_reason", "notes"):
            value = self._signal.get(key)
            if value:
                text = str(value)
                break
        if not text:
            return None

        frame = QFrame()
        frame.setProperty("role", "card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)

        title = QLabel(self.tr_.tr("signals.reasoning"))
        title.setProperty("role", "subtitle")
        layout.addWidget(title)

        box = QTextEdit()
        box.setReadOnly(True)
        box.setPlainText(text)
        box.setMinimumHeight(140)
        layout.addWidget(box)
        return frame

    def _build_recommendation(self) -> QWidget | None:
        """
        کارت توصیهٔ صریح هوش مصنوعی — «بخر» یا «بفروش» یا «صبر کن».

        کاربر خواست هوش مصنوعی پیشنهاد خرید و فروش بدهد، نه فقط تحلیل
        بنویسد. این کارت بالای همهٔ بخش‌ها می‌نشیند چون پاسخ همان
        پرسشی است که کاربر با آن پنجره را باز کرده است.

        وقتی مدل خط توصیه را ننوشته باشد، کارت اصلاً ساخته نمی‌شود.
        ساختن کارت خالی یا حدس‌زدن جهت از روی متن، دقیقاً همان کاری
        است که اعتماد را از بین می‌برد.
        """
        payload = self._signal.get("recommendation")
        if not isinstance(payload, dict) or not payload.get("action"):
            return None

        action = str(payload["action"]).upper()

        # اگر سیگنال سوخته باشد، توصیه دیگر معتبر نیست.
        #
        # توصیه در لحظهٔ ساخت سیگنال درست بود، ولی کاربر ممکن است
        # ساعتی بعد این پنجره را باز کند. نمایش «خرید» با رنگ سبز
        # پررنگ، درست بالای کارتی که می‌گوید «سوخته»، کاربر را به
        # همان معاملهٔ بی‌سودی می‌کشاند که از آن شکایت داشت. پس در آن
        # حالت توصیه خاکستری و با برچسب «منقضی» نشان داده می‌شود.
        superseded = str(self._signal.get("freshness") or "") in NOT_ENTERABLE_STATES

        # نگاشت عمل به توکن رنگ. انتظار رنگ خنثای خودش را دارد تا با
        # خرید و فروش اشتباه گرفته نشود.
        token = (
            "muted"
            if superseded
            else {"BUY": "success", "SELL": "danger"}.get(action, "info")
        )

        from ui.signal_grading import color_for

        frame = QFrame()
        frame.setProperty("role", "card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QLabel(self.tr_.tr("recommendation.title"))
        header.setProperty("role", "subtitle")
        layout.addWidget(header)

        colour = color_for(_TokenOnly(token), self._theme)
        row = QHBoxLayout()
        row.setSpacing(10)

        verdict = QLabel(self.tr_.tr(f"recommendation.action_{action.lower()}"))
        style = f"color: {colour}; font-weight: 800; font-size: 19px;"
        if superseded:
            # خط روی متن: در یک نگاه معلوم می‌کند این توصیه گذشته است
            style += " text-decoration: line-through;"
        verdict.setStyleSheet(style)
        row.addWidget(verdict)

        if superseded:
            expired = QLabel(self.tr_.tr("recommendation.superseded"))
            expired.setStyleSheet(
                f"color: {colour}; border: 1px solid {colour}; border-radius: 4px;"
                " padding: 2px 8px; font-size: 12px;"
            )
            row.addWidget(expired)

        confidence = payload.get("confidence")
        if confidence is not None:
            chip = QLabel(
                self.tr_.tr("recommendation.confidence", percent=int(confidence))
            )
            chip.setStyleSheet(
                f"color: {colour}; border: 1px solid {colour}; border-radius: 4px;"
                " padding: 2px 8px; font-size: 12px;"
            )
            row.addWidget(chip)

        row.addStretch(1)
        layout.addLayout(row)

        rationale = str(payload.get("rationale") or "").strip()
        if rationale:
            label = QLabel(rationale)
            label.setWordWrap(True)
            label.setProperty("role", "muted")
            label.setMinimumHeight(label.sizeHint().height())
            layout.addWidget(label)

        return frame

    def _build_validity(self) -> QWidget | None:
        """
        کارت اعتبار سیگنال — مهم‌ترین چیزی که پیش از ورود باید دید.

        بالای ماشین‌حساب موقعیت می‌نشیند و نه پایین‌تر، عمداً: کاربری
        که دارد اندازهٔ موقعیتش را حساب می‌کند، باید همان لحظه بداند
        این سیگنال هنوز زنده است یا نه. اطلاعات درست در جای غلط، به
        اندازهٔ اطلاعات غلط بی‌فایده است.
        """
        freshness = str(self._signal.get("freshness") or "")
        if not freshness:
            return None

        from ui.signal_grading import color_for, freshness_grade

        grade = freshness_grade(freshness)
        frame = QFrame()
        frame.setProperty("role", "card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QLabel(self.tr_.tr("validity.title"))
        header.setProperty("role", "subtitle")
        layout.addWidget(header)

        status = QLabel(
            f"{grade.mark}  {self.tr_.tr(f'validity.{grade.key}_label')}"
        )
        status.setStyleSheet(
            f"color: {color_for(grade, self._theme)}; font-weight: 700; font-size: 15px;"
        )
        layout.addWidget(status)

        reason_key = str(self._signal.get("validity_reason") or "")
        if reason_key:
            reason = QLabel(self.tr_.tr(reason_key, **(self._signal.get("validity_args") or {})))
            reason.setWordWrap(True)
            reason.setProperty("role", "muted")
            # برچسب چندخطی ارتفاع لازمش را خودش گزارش نمی‌کند
            reason.setMinimumHeight(reason.sizeHint().height())
            layout.addWidget(reason)

        effective = self._signal.get("effective_risk_reward")
        if effective is not None:
            row = QLabel(
                f"{self.tr_.tr('validity.effective_rr')}: \u200e{float(effective):.2f}"
            )
            row.setProperty("role", "muted")
            layout.addWidget(row)

        if freshness in {"STALE", "EXPIRED", "INVALIDATED"}:
            warning = QLabel(self.tr_.tr("validity.not_enterable_warning"))
            warning.setWordWrap(True)
            warning.setStyleSheet(
                f"color: {color_for(grade, self._theme)}; font-weight: 600;"
            )
            warning.setMinimumHeight(warning.sizeHint().height())
            layout.addWidget(warning)

        return frame

    def _build_review(self) -> QWidget | None:
        """
        بازبینی هوش مصنوعی پس از بسته‌شدن معامله.

        فقط وقتی نشان داده می‌شود که واقعاً بازبینی‌ای وجود داشته باشد؛
        کارت خالی با نوشتهٔ «هنوز بازبینی نشده» فقط فضا می‌گیرد.
        """
        review_text = str(self._signal.get("review_text") or "")
        verdict = str(self._signal.get("review_verdict") or "")
        if not review_text and not verdict:
            return None

        frame = QFrame()
        frame.setProperty("role", "card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("🎓  " + self.tr_.tr("review.title"))
        title.setProperty("role", "subtitle")
        layout.addWidget(title)

        lesson = str(self._signal.get("review_lesson") or "")
        if lesson:
            chip = QLabel(self.tr_.tr(f"review.lesson.{lesson}"))
            chip.setProperty("role", "chip")
            layout.addWidget(chip)

        if verdict:
            head = QLabel(verdict)
            head.setWordWrap(True)
            head.setStyleSheet("font-weight: 600;")
            head.setMinimumHeight(head.sizeHint().height())
            layout.addWidget(head)

        if review_text:
            box = QTextEdit()
            box.setReadOnly(True)
            box.setPlainText(review_text)
            box.setMinimumHeight(110)
            layout.addWidget(box)

        return frame

    def _build_disclaimer(self) -> QWidget:
        """یادآوری اینکه این توصیهٔ مالی نیست."""
        label = QLabel(self.tr_.tr("signals.not_financial_advice"))
        label.setProperty("role", "muted")
        label.setWordWrap(True)
        return label

    def _build_buttons(self) -> QHBoxLayout:
        """دکمه‌های پایین پنجره."""
        layout = QHBoxLayout()

        direction = str(self._signal.get("direction", "WAIT")).upper()
        self.trade_button = make_button(self.tr_.tr("signals.act_on_trade"), primary=True)
        freshness = str(self._signal.get("freshness") or "")
        if direction == "WAIT":
            # روی سیگنال انتظار، اقدامی وجود ندارد که انجام شود
            self.trade_button.setEnabled(False)
            self.trade_button.setToolTip(self.tr_.tr("signals.no_action_on_wait"))
        elif freshness in NOT_ENTERABLE_STATES:
            # سیگنال سوخته یا منقضی: دکمه باید خاموش باشد.
            #
            # نمایش هشدار و باز گذاشتن دکمه، هشدار را به تشریفات تبدیل
            # می‌کند. کاربر گزارش کرد بعضی سیگنال‌ها سودی نداده‌اند و
            # یکی از راه‌های رسیدن به آن وضعیت، همین بود: ورود به
            # موقعیتی که فرصتش گذشته. جلوگیری بهتر از هشدار است.
            self.trade_button.setEnabled(False)
            reason_key = str(self._signal.get("validity_reason") or "")
            self.trade_button.setToolTip(
                self.tr_.tr(reason_key, **(self._signal.get("validity_args") or {}))
                if reason_key
                else self.tr_.tr("validity.not_enterable_warning")
            )
        self.trade_button.clicked.connect(self._on_trade_clicked)
        layout.addWidget(self.trade_button)

        # نسخهٔ ۲.۴.۲: کپی نام نماد و متن کامل سیگنال برای ارسال به جای دیگر
        self.copy_symbol_button = make_button(self.tr_.tr("signals.share.copy_symbol"))
        self.copy_symbol_button.setToolTip(self.tr_.tr("signals.share.copy_symbol_tip"))
        self.copy_symbol_button.setEnabled(bool(signal_symbol(self._signal)))
        self.copy_symbol_button.clicked.connect(self.copy_symbol)
        layout.addWidget(self.copy_symbol_button)

        self.copy_info_button = make_button(self.tr_.tr("signals.share.copy_info"))
        self.copy_info_button.setToolTip(self.tr_.tr("signals.share.copy_info_tip"))
        self.copy_info_button.clicked.connect(self.copy_info)
        layout.addWidget(self.copy_info_button)

        # نسخهٔ ۲.۵.۰: اشتراک در شبکه‌های اجتماعی و پیام‌رسان‌ها
        self.share_button = make_button(self.tr_.tr("signals.share.share"))
        self.share_button.setToolTip(self.tr_.tr("signals.share.share_tip"))
        self.share_menu = QMenu(self.share_button)
        self.share_actions: dict[str, Any] = {}
        for target, _mode in SHARE_TARGETS:
            action = self.share_menu.addAction(self.tr_.tr(f"signals.share.to_{target}"))
            action.triggered.connect(lambda _checked=False, t=target: self.share_to(t))
            self.share_actions[target] = action
        self.share_button.setMenu(self.share_menu)
        layout.addWidget(self.share_button)

        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self.tr_.tr("common.close"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        return layout

    # ------------------------------------------------------------------
    # کمکی
    # ------------------------------------------------------------------
    def share_text(self) -> str:
        """متن کامل سیگنال برای کپی/ارسال."""
        return format_signal_text(self._signal, self.tr_)

    def copy_symbol(self) -> bool:
        """کپی نام نماد در کلیپ‌بورد."""
        ok = copy_to_clipboard(signal_symbol(self._signal))
        if ok:
            self._flash_copied(self.copy_symbol_button, "signals.share.copy_symbol")
        return ok

    def copy_info(self) -> bool:
        """کپی متن کامل سیگنال در کلیپ‌بورد."""
        ok = copy_to_clipboard(self.share_text())
        if ok:
            self._flash_copied(self.copy_info_button, "signals.share.copy_info")
        return ok

    #: بازکنندهٔ نشانی؛ آزمون‌ها جایگزینش می‌کنند تا مرورگر باز نشود
    url_opener = staticmethod(open_url)

    def share_to(self, target: str) -> str:
        """
        اشتراک متن سیگنال در یک مقصد؛ نشانی بازشده را برمی‌گرداند.

        برای روبیکا/ایتا/بله که پیوند اشتراک متن ندارند، متن اول کپی
        می‌شود و پیامی کوتاه می‌گوید «در گفت‌وگو بچسبانید».
        """
        text = self.share_text()
        mode = share_mode(target)
        if not mode:
            return ""
        if mode == "copy":
            copy_to_clipboard(text)
            self.share_button.setText(self.tr_.tr("signals.share.copied_paste"))
            QTimer.singleShot(
                2500, lambda: _safe_set_text(self.share_button, self.tr_.tr("signals.share.share"))
            )
        url = share_url(
            target, text, subject=f"{signal_symbol(self._signal)} — {self.tr_.tr('signals.share.subject')}"
        )
        if url:
            self.url_opener(url)
        return url

    def _flash_copied(self, button: Any, restore_key: str) -> None:
        """نمایش کوتاه «کپی شد ✓» روی همان دکمه."""
        button.setText(self.tr_.tr("signals.share.copied"))

        def restore() -> None:
            try:
                button.setText(self.tr_.tr(restore_key))
            except RuntimeError:  # پنجره پیش‌تر بسته شده
                pass

        QTimer.singleShot(1500, restore)

    def _on_trade_clicked(self) -> None:
        """اعلام درخواست اقدام به کنترلر."""
        self.trade_requested.emit(self.trade_payload())

    def _entry_text(self) -> str:
        """قالب‌بندی محدودهٔ ورود که ممکن است تک‌قیمت یا بازه باشد."""
        entry_min = self._signal.get("entry_min")
        entry_max = self._signal.get("entry_max")
        if entry_min is None and entry_max is None:
            # `entry_price` کلیدی است که موتور سیگنال و پویشگر می‌سازند؛
            # نبودنش در این فهرست یعنی پنجره برای سیگنال‌های واقعی خط
            # تیره نشان می‌داد.
            entry = self._signal.get("entry")
            if entry is None:
                entry = self._signal.get("entry_price")
            if isinstance(entry, dict):
                entry_min, entry_max = entry.get("min"), entry.get("max")
            elif entry is not None:
                entry_min = entry_max = entry

        if entry_min is None and entry_max is None:
            return "—"
        if entry_min is not None and entry_max is not None and entry_min != entry_max:
            return f"{self._price(entry_min)} – {self._price(entry_max)}"
        return self._price(entry_min if entry_min is not None else entry_max)

    def _price(self, value: Any) -> str:
        """
        قالب‌بندی یک قیمت با ارقام محلی.

        صفرهای انتهایی **پیش از** محلی‌سازی حذف می‌شوند: پس از تبدیل به
        ارقام فارسی، صفر دیگر «0» نیست بلکه «۰» است و `rstrip("0")`
        هیچ کاری نمی‌کند — به همین دلیل قیمت‌ها با چهار صفر بی‌فایده
        نمایش داده می‌شدند.
        """
        if value in (None, ""):
            return "—"
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)

        text = f"{number:,.4f}".rstrip("0").rstrip(".") or "0"
        if getattr(self.tr_, "is_rtl", False):
            text = self.tr_.to_persian_digits(text)
        return text

    @staticmethod
    def _direction_role(direction: str) -> str:
        """نقش رنگی متناسب با جهت سیگنال."""
        if direction == "LONG":
            return "bullish"
        if direction == "SHORT":
            return "bearish"
        return "neutral"


def _safe_set_text(widget: Any, text: str) -> None:
    """تغییر متن ویجتی که شاید تا الان بسته شده باشد."""
    try:
        widget.setText(text)
    except RuntimeError:
        pass
