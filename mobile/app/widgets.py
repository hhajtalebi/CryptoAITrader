"""
اجزای رابط موبایل — Kivy خالص (بدون KivyMD، تا ساخت APK ساده بماند).

* `RtlLabel`: متن فارسی که **اول** شکسته‌سطر و **بعد** شکل‌دهی/راست‌به‌چپ
  می‌شود؛ وگرنه ترتیب کلمه‌های سطرهای چندخطی برعکس می‌شود.
* آیکون‌ها با canvas کشیده می‌شوند (برداری، بدون فایل فونت آیکون).
"""

from __future__ import annotations

import math

from kivy.core.text import Label as CoreLabel
from kivy.core.text import LabelBase
from kivy.graphics import Color, Ellipse, Line, Mesh, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex as hexc

# ---------------------------------------------------------------- تم
BG = hexc("#0B1220")
SURFACE = hexc("#131C2E")
SURFACE2 = hexc("#1B263B")
BORDER = hexc("#25324C")
TEXT = hexc("#E8EEF8")
MUTED = hexc("#8A9AB5")
FAINT = hexc("#5D6B85")
ACCENT = hexc("#4F8CFF")
GREEN = hexc("#22C55E")
RED = hexc("#F04452")
AMBER = hexc("#F5B83D")

TONE = {"up": GREEN, "down": RED, "flat": MUTED, "wait": AMBER, "accent": ACCENT}
DIRECTION_TONE = {"LONG": "up", "SHORT": "down", "WAIT": "wait"}


def tint(color, alpha: float):  # noqa: ANN001, ANN201
    return [color[0], color[1], color[2], alpha]


try:
    LabelBase.register(name="fa", fn_regular="assets/Vazirmatn-Regular.ttf")
    FONT = "fa"
except OSError:  # پیش‌نمایش/آزمون بیرون از پوشهٔ mobile
    FONT = "Roboto"


def shape(text: str) -> str:
    """شکل‌دهی حروف فارسی + ترتیب نمایشی راست‌به‌چپ (برای یک سطر)."""
    try:
        import arabic_reshaper  # noqa: PLC0415
        from bidi.algorithm import get_display  # noqa: PLC0415
    except ImportError:
        return text
    return get_display(arabic_reshaper.reshape(text))


def has_rtl(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in text)


# ---------------------------------------------------------------- متن
class RtlLabel(Label):
    """
    برچسب هوشمند: فارسی ← راست‌چین و شکسته‌سطر صحیح؛ لاتین ← بدون دست‌کاری.

    `raw` متن منطقی است؛ `text` نسخهٔ نمایشی که خودکار ساخته می‌شود.
    `auto_height`: ارتفاع = ارتفاع متن (برای کارت‌های با محتوای پویا).
    """

    raw = StringProperty("")
    auto_height = BooleanProperty(True)
    align = StringProperty("auto")  # auto | right | left | center

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("font_name", FONT)
        kwargs.setdefault("color", TEXT)
        kwargs.setdefault("font_size", sp(14))
        super().__init__(**kwargs)
        if self.auto_height:
            self.size_hint_y = None
        self.bind(raw=self._relayout, width=self._relayout, font_size=self._relayout, align=self._relayout)
        self.bind(texture_size=self._fit)
        self._relayout()

    def _fit(self, *_a) -> None:  # noqa: ANN002
        if self.auto_height:
            self.height = max(self.texture_size[1], self.font_size * 1.2)

    def _relayout(self, *_a) -> None:  # noqa: ANN002
        raw = self.raw or ""
        rtl = has_rtl(raw)
        self.halign = ("right" if rtl else "left") if self.align == "auto" else self.align
        self.valign = "middle"
        width = max(self.width - 2, 10)
        self.text_size = (self.width, None) if self.auto_height else (self.width, self.height)
        if not rtl:
            self.text = raw
            return
        lines: list[str] = []
        for paragraph in raw.split("\n"):
            lines += self._wrap(paragraph, width)
        self.text = "\n".join(shape(line) for line in lines)

    def _wrap(self, paragraph: str, width: float) -> list[str]:
        words = paragraph.split(" ")
        probe = CoreLabel(font_name=self.font_name, font_size=self.font_size)
        out: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and probe.get_extents(shape(candidate))[0] > width:
                out.append(current)
                current = word
            else:
                current = candidate
        out.append(current)
        return out


def label(raw: str, size: float = 14, color=TEXT, **kw) -> RtlLabel:  # noqa: ANN001
    return RtlLabel(raw=raw, font_size=sp(size), color=color, **kw)


# ---------------------------------------------------------------- سطح‌ها
class Surface(BoxLayout):
    """جعبهٔ گوشه‌گرد با رنگ زمینه و حاشیهٔ ظریف."""

    bg = ListProperty(SURFACE)
    border = ListProperty(BORDER)
    radius = NumericProperty(dp(16))

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        with self.canvas.before:
            self._c_border = Color(rgba=self.border)
            self._r_border = RoundedRectangle(radius=[self.radius])
            self._c_bg = Color(rgba=self.bg)
            self._r_bg = RoundedRectangle(radius=[self.radius])
        self.bind(pos=self._redraw, size=self._redraw, bg=self._redraw, border=self._redraw)
        self._redraw()

    def _redraw(self, *_a) -> None:  # noqa: ANN002
        self._c_border.rgba = self.border
        self._c_bg.rgba = self.bg
        self._r_border.pos, self._r_border.size = self.pos, self.size
        self._r_border.radius = [self.radius]
        inset = dp(1) if self.border[3] > 0 else 0
        self._r_bg.pos = (self.x + inset, self.y + inset)
        self._r_bg.size = (self.width - 2 * inset, self.height - 2 * inset)
        self._r_bg.radius = [max(self.radius - inset, 0)]


class Card(Surface):
    """کارت با ارتفاع خودکار بر پایهٔ محتوا."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", (dp(16), dp(14)))
        kwargs.setdefault("spacing", dp(8))
        kwargs.setdefault("size_hint_y", None)
        super().__init__(**kwargs)
        self.bind(minimum_height=self.setter("height"))


class Tappable(ButtonBehavior, Surface):
    """سطح لمس‌پذیر با بازخورد فشردن."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._rest = list(self.bg)

    def on_state(self, _inst, value) -> None:  # noqa: ANN001
        if value == "down":
            self._rest = list(self.bg)
            self.bg = [min(c + 0.05, 1) for c in self._rest[:3]] + [self._rest[3]]
        else:
            self.bg = self._rest


class Chip(Tappable):
    """دکمهٔ گزینه (تایم‌فریم، مرتب‌سازی…)؛ حالت انتخاب با رنگ تأکیدی."""

    selected = BooleanProperty(False)
    value = ObjectProperty(None)

    def __init__(self, text: str, value=None, selected: bool = False, **kwargs) -> None:  # noqa: ANN001
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("height", dp(36))
        kwargs.setdefault("radius", dp(18))
        kwargs.setdefault("padding", (dp(14), 0))
        super().__init__(**kwargs)
        self.value = value if value is not None else text
        self._label = RtlLabel(raw=text, font_size=sp(13), auto_height=False, align="center")
        self._label.size_hint = (1, 1)
        self.add_widget(self._label)
        extents = CoreLabel(font_name=FONT, font_size=sp(13)).get_extents(shape(text))
        self.width = extents[0] + dp(30)
        self.bind(selected=self._paint)
        self.selected = selected
        self._paint()

    def _paint(self, *_a) -> None:  # noqa: ANN002
        if self.selected:
            self.bg, self.border = tint(ACCENT, 0.18), tint(ACCENT, 0.9)
            self._label.color = TEXT
        else:
            self.bg, self.border = SURFACE, BORDER
            self._label.color = MUTED
        self._rest = list(self.bg)


class ChipGroup(BoxLayout):
    """گروه تک‌انتخابی؛ `on_select(value)` هنگام تغییر."""

    def __init__(self, options: list[tuple[str, object]], current, on_select, **kwargs) -> None:  # noqa: ANN001
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(36))
        kwargs.setdefault("spacing", dp(8))
        super().__init__(**kwargs)
        self._on_select = on_select
        self.chips: list[Chip] = []
        # راست‌به‌چپ: نخستین گزینه سمت راست
        self.add_widget(Widget())
        for text, value in reversed(options):
            chip = Chip(text, value, selected=(value == current))
            chip.bind(on_release=self._clicked)
            self.chips.append(chip)
            self.add_widget(chip)

    def _clicked(self, chip: Chip) -> None:
        for c in self.chips:
            c.selected = c is chip
        self._on_select(chip.value)

    def select(self, value) -> None:  # noqa: ANN001
        for c in self.chips:
            c.selected = c.value == value


class Pill(Surface):
    """برچسب رنگی کوچک (درصد تغییر، جهت سیگنال)."""

    def __init__(self, text: str, tone: str = "flat", size: float = 13, **kwargs) -> None:
        color = TONE.get(tone, MUTED)
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("height", dp(26))
        kwargs.setdefault("radius", dp(8))
        super().__init__(bg=tint(color, 0.16), border=[0, 0, 0, 0], **kwargs)
        self._label = RtlLabel(raw=text, font_size=sp(size), color=color, auto_height=False, align="center")
        self.add_widget(self._label)
        self.width = CoreLabel(font_name=FONT, font_size=sp(size)).get_extents(shape(text))[0] + dp(18)

    def set(self, text: str, tone: str) -> None:
        color = TONE.get(tone, MUTED)
        self._label.raw, self._label.color = text, color
        self.bg = tint(color, 0.16)
        self.width = CoreLabel(font_name=FONT, font_size=self._label.font_size).get_extents(shape(text))[0] + dp(18)


class Meter(Widget):
    """نوار پیشرفت گرد (اطمینان سیگنال)."""

    value = NumericProperty(0)  # 0..100
    color = ListProperty(ACCENT)

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(6))
        super().__init__(**kwargs)
        with self.canvas:
            Color(rgba=SURFACE2)
            self._track = RoundedRectangle(radius=[dp(3)])
            self._c = Color(rgba=self.color)
            self._fill = RoundedRectangle(radius=[dp(3)])
        self.bind(pos=self._redraw, size=self._redraw, value=self._redraw, color=self._redraw)

    def _redraw(self, *_a) -> None:  # noqa: ANN002
        self._track.pos, self._track.size = self.pos, self.size
        w = self.width * max(0.0, min(self.value, 100.0)) / 100.0
        # راست‌به‌چپ: از راست پر می‌شود
        self._fill.pos, self._fill.size = (self.right - w, self.y), (w, self.height)
        self._c.rgba = self.color


# ---------------------------------------------------------------- آیکون‌ها
class Icon(Widget):
    """آیکون برداری. نام‌ها: market, signals, star, star_fill, chart, settings, search, refresh, back."""

    name = StringProperty("market")
    color = ListProperty(MUTED)

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(24), dp(24)))
        super().__init__(**kwargs)
        self.bind(pos=self.draw, size=self.draw, name=self.draw, color=self.draw)
        self.draw()

    def draw(self, *_a) -> None:  # noqa: ANN002, C901, PLR0915
        self.canvas.clear()
        s = min(self.width, self.height)
        x0 = self.center_x - s / 2
        y0 = self.center_y - s / 2
        w = max(dp(1.7), s / 13)

        def P(px: float, py: float) -> tuple[float, float]:  # noqa: N802 — مختصات ۰..۲۴
            return x0 + px / 24 * s, y0 + py / 24 * s

        def pts(*coords: float) -> list[float]:
            out: list[float] = []
            for i in range(0, len(coords), 2):
                out += list(P(coords[i], coords[i + 1]))
            return out

        with self.canvas:
            Color(rgba=self.color)
            n = self.name
            if n == "market":  # شمع‌ها
                for cx, lo, hi, b0, b1 in ((6, 5, 17, 8, 14), (12, 8, 21, 11, 18), (18, 3, 14, 6, 11)):
                    Line(points=pts(cx, lo, cx, hi), width=w / 1.4)
                    bx, by = P(cx - 2, b0)
                    RoundedRectangle(pos=(bx, by), size=(4 / 24 * s, (b1 - b0) / 24 * s), radius=[s / 40])
            elif n == "signals":  # صاعقه
                Line(points=pts(13, 22, 5, 11, 11.5, 11, 10, 2, 19, 13, 12.5, 13, 13, 22), width=w, joint="round", close=True)
            elif n in ("star", "star_fill"):
                coords: list[float] = []
                for i in range(10):
                    r = 9.5 if i % 2 == 0 else 4.2
                    a = math.pi / 2 + i * math.pi / 5
                    coords += [12 + r * math.cos(a), 12 + r * math.sin(a)]
                flat = pts(*coords)
                if n == "star_fill":
                    cx, cy = P(12, 12)
                    vertices: list[float] = [cx, cy, 0, 0]
                    for i in range(0, len(flat), 2):
                        vertices += [flat[i], flat[i + 1], 0, 0]
                    vertices += [flat[0], flat[1], 0, 0]
                    Mesh(vertices=vertices, indices=list(range(len(vertices) // 4)), mode="triangle_fan")
                Line(points=flat, width=w / 1.3, close=True, joint="round")
            elif n == "chart":  # خط نمودار
                Line(points=pts(3, 3, 3, 21), width=w / 1.4)
                Line(points=pts(3, 3, 21, 3), width=w / 1.4)
                Line(points=pts(6, 8, 10, 13, 13.5, 10, 20, 18), width=w, joint="round", cap="round")
            elif n == "settings":  # چرخ‌دنده
                cx, cy = P(12, 12)
                Line(circle=(cx, cy, s * 0.17), width=w)
                for i in range(8):
                    a = i * math.pi / 4
                    Line(points=pts(12 + 6.2 * math.cos(a), 12 + 6.2 * math.sin(a),
                                    12 + 9.6 * math.cos(a), 12 + 9.6 * math.sin(a)), width=w * 1.25, cap="round")
                Line(circle=(cx, cy, s * 0.29), width=w / 1.3)
            elif n == "search":
                cx, cy = P(10.5, 13.5)
                Line(circle=(cx, cy, s * 0.27), width=w)
                Line(points=pts(15.5, 8.5, 21, 3), width=w * 1.1, cap="round")
            elif n == "refresh":
                cx, cy = P(12, 12)
                Line(circle=(cx, cy, s * 0.33, 40, 330), width=w, cap="round")
                Line(points=pts(15.5, 21, 19.5, 19.5, 17.2, 15.8), width=w, joint="round", cap="round")
            elif n == "back":  # فلش به راست (بازگشت در راست‌به‌چپ)
                Line(points=pts(4, 12, 20, 12), width=w, cap="round")
                Line(points=pts(13, 19, 20, 12, 13, 5), width=w, joint="round", cap="round")
            elif n == "dot":
                cx, cy = P(12, 12)
                Ellipse(pos=(cx - s * 0.2, cy - s * 0.2), size=(s * 0.4, s * 0.4))


class IconButton(ButtonBehavior, Widget):
    """آیکون لمس‌پذیر با ناحیهٔ لمس بزرگ (۴۴dp — استاندارد دسترس‌پذیری)."""

    def __init__(self, name: str, color=MUTED, **kwargs) -> None:  # noqa: ANN001
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(44), dp(44)))
        super().__init__(**kwargs)
        self.icon = Icon(name=name, color=color)
        self.add_widget(self.icon)
        self.bind(pos=self._place, size=self._place)

    def _place(self, *_a) -> None:  # noqa: ANN002
        self.icon.center = self.center


# ---------------------------------------------------------------- ناوبری پایین
class NavItem(ButtonBehavior, BoxLayout):
    active = BooleanProperty(False)

    def __init__(self, key: str, icon: str, title: str, **kwargs) -> None:
        super().__init__(orientation="vertical", padding=(0, dp(8), 0, dp(6)), spacing=dp(2), **kwargs)
        self.key = key
        self.icon = Icon(name=icon, size=(dp(24), dp(24)))
        holder = BoxLayout(size_hint_y=None, height=dp(26))
        holder.add_widget(Widget())
        holder.add_widget(self.icon)
        holder.add_widget(Widget())
        self.add_widget(holder)
        self.title = RtlLabel(raw=title, font_size=sp(11), auto_height=False, align="center", size_hint_y=None, height=dp(18))
        self.add_widget(self.title)
        with self.canvas.before:
            self._c = Color(rgba=[0, 0, 0, 0])
            self._pill = RoundedRectangle(radius=[dp(14)])
        self.bind(active=self._paint, pos=self._paint, size=self._paint)
        self._paint()

    def _paint(self, *_a) -> None:  # noqa: ANN002
        color = ACCENT if self.active else FAINT
        self.icon.color = color
        self.title.color = TEXT if self.active else FAINT
        self._c.rgba = tint(ACCENT, 0.16) if self.active else [0, 0, 0, 0]
        pw, ph = dp(56), dp(30)
        self._pill.pos = (self.center_x - pw / 2, self.top - dp(4) - ph)
        self._pill.size = (pw, ph)


class BottomNav(Surface):
    def __init__(self, items: list[tuple[str, str, str]], on_select, **kwargs) -> None:  # noqa: ANN001
        super().__init__(size_hint_y=None, height=dp(66), radius=0, bg=SURFACE, border=BORDER, **kwargs)
        self._on_select = on_select
        self.items: dict[str, NavItem] = {}
        for key, icon, title in reversed(items):  # راست‌به‌چپ
            item = NavItem(key, icon, title)
            item.bind(on_release=lambda it: self._on_select(it.key))
            self.items[key] = item
            self.add_widget(item)

    def set_active(self, key: str) -> None:
        for k, item in self.items.items():
            item.active = k == key


# ---------------------------------------------------------------- نمودار
class Sparkline(Widget):
    """نمودار خطی سبک با سایهٔ زیر خط و خط EMA اختیاری."""

    values = ListProperty([])
    overlay = ListProperty([])
    color = ListProperty(ACCENT)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.bind(pos=self.draw, size=self.draw, values=self.draw, overlay=self.draw, color=self.draw)

    def draw(self, *_a) -> None:  # noqa: ANN002
        from .viewmodel import sparkline_points  # noqa: PLC0415

        self.canvas.clear()
        vals = [v for v in self.values if v is not None]
        if len(vals) < 2:
            return
        lo, hi = min(vals), max(vals)
        pad = dp(4)
        pts = sparkline_points(vals, self.width, self.height, pad)
        pts = [p + (self.x if i % 2 == 0 else self.y) for i, p in enumerate(pts)]
        with self.canvas:
            # خطوط راهنمای افقی
            Color(rgba=tint(BORDER, 0.6))
            for k in (0.25, 0.5, 0.75):
                y = self.y + pad + k * (self.height - 2 * pad)
                Line(points=[self.x, y, self.right, y], width=dp(0.6), dash_length=dp(4), dash_offset=dp(4))
            # سایه
            Color(rgba=tint(self.color, 0.14))
            vertices: list[float] = []
            for i in range(0, len(pts), 2):
                vertices += [pts[i], self.y, 0, 0, pts[i], pts[i + 1], 0, 0]
            Mesh(vertices=vertices, indices=list(range(len(vertices) // 4)), mode="triangle_strip")
            # EMA
            ov = self.overlay[-len(vals):] if self.overlay else []
            ov_pts: list[float] = []
            span = (hi - lo) or 1.0
            step = (self.width - 2 * pad) / (len(vals) - 1)
            for i, v in enumerate(ov):
                if v is None:
                    continue
                ov_pts += [self.x + pad + i * step, self.y + pad + (v - lo) / span * (self.height - 2 * pad)]
            if len(ov_pts) >= 4:
                Color(rgba=tint(AMBER, 0.85))
                Line(points=ov_pts, width=dp(1.1))
            Color(rgba=self.color)
            Line(points=pts, width=dp(1.6), joint="round")
            # نقطهٔ آخر
            Color(rgba=tint(self.color, 0.25))
            Ellipse(pos=(pts[-2] - dp(7), pts[-1] - dp(7)), size=(dp(14), dp(14)))
            Color(rgba=self.color)
            Ellipse(pos=(pts[-2] - dp(3.5), pts[-1] - dp(3.5)), size=(dp(7), dp(7)))


class Spacer(Widget):
    def __init__(self, h: float = 8, **kwargs) -> None:
        super().__init__(size_hint_y=None, height=dp(h), **kwargs)
