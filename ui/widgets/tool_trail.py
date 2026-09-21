"""
نمایش گام‌های ابزار زیر پاسخ دستیار.

مسئله‌ای که حل می‌کند
    دستیار برای پاسخ‌دادن ابزار صدا می‌زند (قیمت لحظه‌ای، تحلیل روند،
    محاسبهٔ ریسک و…). پیش از این تنها نشانهٔ آن، یک خط متن خاکستری با
    نام ابزارها بود. کاربر نه می‌دید چه زمانی چه چیزی اجرا می‌شود و نه
    می‌توانست ببیند ابزار **چه جوابی** داده است. وقتی عدد پاسخ با
    انتظارش نمی‌خواند، هیچ راهی برای فهمیدن علت نداشت.

طراحی
    هر گام یک ردیف جمع‌وجور است: نشانهٔ وضعیت، نام خوانای ابزار،
    آرگومان‌ها، و — در صورت وجود — نتیجه‌ای که با کلیک باز و بسته
    می‌شود. جزئیات به‌صورت پیش‌فرض بسته است تا گفتگو شلوغ نشود؛ همان
    الگوی «کارت تاشو» که در `NEXT_TASK.md` برنامه‌ریزی شده بود.

    سه وضعیت دارد:
        running → در حال اجرا (هنوز نتیجه‌ای نیست)
        ok      → با موفقیت تمام شد
        failed  → شکست خورد

    رنگ‌ها از توکن پوستهٔ فعال می‌آیند، نه مقدار ثابت؛ پس در هر هشت
    پوسته خوانا می‌ماند.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.controls import set_role

#: بیشینهٔ طول متن نتیجه که نمایش داده می‌شود. خروجی خام یک ابزار گاهی
#: چند کیلوبایت است و ریختن همه‌اش در گفتگو، صفحه را غیرقابل استفاده
#: می‌کند.
MAX_OBSERVATION_CHARS = 600


class ToolStep(QFrame):
    """یک گام ابزار: نشانهٔ وضعیت، نام، آرگومان‌ها و نتیجهٔ تاشو."""

    #: نشانهٔ هر وضعیت و توکن رنگی متناظرش
    STATE_MARKS: dict[str, tuple[str, str]] = {
        "running": ("◐", "info"),
        "ok": ("✓", "success"),
        "failed": ("✗", "danger"),
    }

    def __init__(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name = str(name)
        self._arguments = dict(arguments or {})
        self._state = "running"
        self._observation = ""
        self._expanded = False
        self._theme: Any = None

        set_role(self, "toolStep")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.mark_label = QLabel(self)
        self.mark_label.setFixedWidth(14)
        self.mark_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.mark_label)

        self.title_label = QLabel(self)
        set_role(self.title_label, "toolStepTitle")
        header_layout.addWidget(self.title_label, 1)

        # نشانگر باز/بسته؛ فقط وقتی نتیجه‌ای برای دیدن باشد ظاهر می‌شود
        self.chevron_label = QLabel("▾", self)
        set_role(self.chevron_label, "faint")
        self.chevron_label.setVisible(False)
        header_layout.addWidget(self.chevron_label, 0)

        layout.addWidget(header)

        self.detail_label = QLabel(self)
        set_role(self.detail_label, "toolStepDetail")
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.detail_label.setVisible(False)
        layout.addWidget(self.detail_label)

        self._refresh()

    # ------------------------------------------------------------------ API
    @property
    def tool_name(self) -> str:
        """نام ابزار این گام."""
        return self._name

    @property
    def state(self) -> str:
        """وضعیت فعلی: running / ok / failed."""
        return self._state

    @property
    def expanded(self) -> bool:
        """آیا جزئیات باز است؟"""
        return self._expanded

    def set_result(self, *, ok: bool, observation: str = "") -> None:
        """ثبت نتیجهٔ اجرای ابزار و بستن حالت «در حال اجرا»."""
        self._state = "ok" if ok else "failed"
        self._observation = str(observation or "").strip()
        self._refresh()

    def set_arguments(self, arguments: dict[str, Any]) -> None:
        """به‌روزرسانی آرگومان‌ها (مدل گاهی در دور بعد دقیق‌ترشان می‌کند)."""
        self._arguments = dict(arguments or {})
        self._refresh()

    def set_display_name(self, label: str) -> None:
        """
        نام خوانای ابزار به زبان کاربر.

        نام فنی (`get_price`) برای کاربر فارسی‌زبان معنا ندارد؛ صفحه
        ترجمه‌اش را می‌دهد و اگر ترجمه‌ای نبود همان نام فنی می‌ماند.
        """
        self._display_name = str(label or self._name)
        self._refresh()

    def apply_theme(self, theme: Any) -> None:
        """گرفتن رنگ نشانه از پوستهٔ فعال."""
        self._theme = theme
        self._refresh()

    def toggle(self) -> None:
        """باز/بستن جزئیات."""
        if not self._observation:
            return
        self._expanded = not self._expanded
        self._refresh()

    # -------------------------------------------------------------- درونی
    def _refresh(self) -> None:
        """بازسازی متن‌ها و رنگ‌ها."""
        mark, token = self.STATE_MARKS.get(self._state, self.STATE_MARKS["running"])
        colour = self._colour(token)
        self.mark_label.setText(mark)
        self.mark_label.setStyleSheet(f"color: {colour};")

        name = getattr(self, "_display_name", self._name)
        if self._arguments:
            arguments = ", ".join(f"{k}={v}" for k, v in self._arguments.items())
            self.title_label.setText(f"{name} ({arguments})")
        else:
            self.title_label.setText(name)

        has_detail = bool(self._observation)
        self.chevron_label.setVisible(has_detail)
        self.chevron_label.setText("▴" if self._expanded else "▾")
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if has_detail else Qt.CursorShape.ArrowCursor
        )

        if has_detail and self._expanded:
            text = self._observation
            if len(text) > MAX_OBSERVATION_CHARS:
                text = text[:MAX_OBSERVATION_CHARS].rstrip() + " …"
            self.detail_label.setText(text)
            self.detail_label.setVisible(True)
        else:
            self.detail_label.setVisible(False)
        self.updateGeometry()

    def _colour(self, token: str) -> str:
        """رنگ یک توکن از پوستهٔ فعال، با پشتیبان امن."""
        colors = getattr(self._theme, "colors", None)
        fallback = {"success": "#34d399", "danger": "#fb7185", "info": "#60a5fa"}
        return str(getattr(colors, token, "") or fallback.get(token, "#94a3b8"))

    def mousePressEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """کلیک روی گام، جزئیاتش را باز و بسته می‌کند."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
        super().mousePressEvent(event)


class ToolTrail(QWidget):
    """
    مجموعهٔ گام‌های ابزار یک پاسخ.

    گام‌ها به ترتیب اجرا چیده می‌شوند و با نام ابزار پیدا می‌شوند، چون
    اعلام «شروع شد» و «تمام شد» دو رویداد جداگانه‌اند و باید به یک ردیف
    برسند.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._steps: list[ToolStep] = []
        self._theme: Any = None
        self._names: dict[str, str] = {}

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 0)
        self._layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.setVisible(False)

    # ------------------------------------------------------------------ API
    def set_display_names(self, names: dict[str, str]) -> None:
        """نگاشت نام فنی ابزار به نام خوانا (از فایل ترجمه)."""
        self._names = dict(names or {})
        for step in self._steps:
            step.set_display_name(self._names.get(step.tool_name, step.tool_name))

    def begin_step(self, name: str, arguments: dict[str, Any] | None = None) -> ToolStep:
        """
        افزودن گامی که **تازه شروع شده**.

        اگر همان ابزار پیش‌تر در همین نوبت اجرا شده باشد، ردیف تازه‌ای
        ساخته می‌شود؛ مدل ممکن است یک ابزار را با آرگومان متفاوت دو بار
        صدا بزند و ادغامشان، اطلاعات را پنهان می‌کرد.
        """
        step = ToolStep(name, arguments, self)
        step.set_display_name(self._names.get(name, name))
        step.apply_theme(self._theme)
        self._steps.append(step)
        self._layout.addWidget(step)
        self.setVisible(True)
        self.updateGeometry()
        return step

    def finish_step(self, name: str, *, ok: bool, observation: str = "",
                    arguments: dict[str, Any] | None = None) -> ToolStep:
        """
        بستن آخرین گامِ در حال اجرای این ابزار.

        اگر گام «شروع» گم شده باشد (مثلاً پاسخ از حافظهٔ نهان آمده و
        اجرایی در کار نبوده)، ردیف تازه‌ای ساخته و بی‌درنگ بسته می‌شود —
        وگرنه نتیجه بی‌صدا گم می‌شد.
        """
        for step in reversed(self._steps):
            if step.tool_name == name and step.state == "running":
                if arguments:
                    step.set_arguments(arguments)
                step.set_result(ok=ok, observation=observation)
                return step

        step = self.begin_step(name, arguments)
        step.set_result(ok=ok, observation=observation)
        return step

    def steps(self) -> list[ToolStep]:
        """گام‌های فعلی به ترتیب."""
        return list(self._steps)

    def clear(self) -> None:
        """پاک‌کردن همهٔ گام‌ها."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._steps.clear()
        self.setVisible(False)

    def apply_theme(self, theme: Any) -> None:
        """اعمال پوسته روی همهٔ گام‌ها."""
        self._theme = theme
        for step in self._steps:
            step.apply_theme(theme)


__all__ = ["MAX_OBSERVATION_CHARS", "ToolStep", "ToolTrail"]
