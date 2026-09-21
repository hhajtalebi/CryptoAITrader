"""
ساخت آیکون از روی مسیرهای برداری.

آیکون‌ها در حافظه نگه‌داری (cache) می‌شوند، چون یک آیکون ممکن است ده‌ها
بار با همان رنگ و اندازه خواسته شود و رندر دوبارهٔ SVG بی‌دلیل کند است.
کلید حافظه شامل رنگ است، پس تغییر پوسته خودبه‌خود نسخهٔ تازه می‌سازد.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ui.icons.paths import DEFAULT_STROKE_WIDTH, ICON_ALIASES, ICON_PATHS

#: نام همهٔ آیکون‌های موجود
ICON_NAMES: tuple[str, ...] = tuple(sorted(ICON_PATHS))

#: اندازهٔ پیش‌فرض آیکون بر حسب پیکسل منطقی
DEFAULT_SIZE = 20

#: رنگ پشتیبان وقتی رنگی داده نشده
FALLBACK_COLOR = "#e2e8f0"


def available_icons() -> tuple[str, ...]:
    """فهرست نام آیکون‌های ثبت‌شده."""
    return ICON_NAMES


def register_icon(name: str, body: str) -> None:
    """
    افزودن یا جایگزینی یک آیکون در زمان اجرا.

    برای افزونه‌ها مفید است؛ حافظهٔ نهان پاک می‌شود تا نسخهٔ تازه دیده شود.
    """
    ICON_PATHS[str(name)] = str(body)
    icon_svg.cache_clear()
    _render_pixmap.cache_clear()


def resolve_name(name: str) -> str:
    """
    تبدیل نام مستعار به نام اصلی آیکون.

    اگر آیکون پیدا نشود، «info» برگردانده می‌شود؛ نبودن یک آیکون نباید
    باعث خطای برنامه یا جای خالی در رابط شود.
    """
    key = str(name or "").strip()
    if key in ICON_PATHS:
        return key
    alias = ICON_ALIASES.get(key)
    if alias and alias in ICON_PATHS:
        return alias
    return "info"


@lru_cache(maxsize=512)
def icon_svg(name: str, color: str = FALLBACK_COLOR, stroke: float = DEFAULT_STROKE_WIDTH) -> str:
    """ساخت متن کامل SVG یک آیکون با رنگ دلخواه."""
    body = ICON_PATHS[resolve_name(name)]
    # «currentColor» را خودمان جایگزین می‌کنیم: QSvgRenderer آن را
    # نمی‌شناسد و بخش‌های پُرشده نامرئی می‌شدند.
    body = body.replace("currentColor", color)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="{stroke}" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>"
    )


@lru_cache(maxsize=512)
def _render_pixmap(
    name: str, color: str, size: int, stroke: float, ratio_x100: int
) -> QPixmap:
    """
    رندر آیکون روی یک نقشک.

    ضریب چگالی نمایشگر در کلید حافظه هست تا روی نمایشگر HiDPI آیکون تار
    نشود؛ رندر SVG در اندازهٔ فیزیکی واقعی انجام می‌شود.
    """
    ratio = max(1.0, ratio_x100 / 100.0)
    physical = max(1, int(round(size * ratio)))

    renderer = QSvgRenderer(QByteArray(icon_svg(name, color, stroke).encode("utf-8")))
    pixmap = QPixmap(physical, physical)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()

    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def icon_pixmap(
    name: str,
    color: str = FALLBACK_COLOR,
    size: int = DEFAULT_SIZE,
    *,
    stroke: float = DEFAULT_STROKE_WIDTH,
    ratio: float = 1.0,
) -> QPixmap:
    """نقشک آمادهٔ نشاندن روی QLabel."""
    return _render_pixmap(
        resolve_name(name), str(color or FALLBACK_COLOR), int(size), float(stroke),
        int(round(max(1.0, ratio) * 100)),
    )


def icon(
    name: str,
    color: str = FALLBACK_COLOR,
    size: int = DEFAULT_SIZE,
    *,
    stroke: float = DEFAULT_STROKE_WIDTH,
) -> QIcon:
    """
    آیکون آمادهٔ نشاندن روی دکمه.

    حالت غیرفعال هم ساخته می‌شود تا دکمهٔ ازکارافتاده کم‌رنگ دیده شود.
    """
    pixmap = icon_pixmap(name, color, size, stroke=stroke)
    result = QIcon(pixmap)
    result.addPixmap(pixmap, QIcon.Mode.Normal)
    result.addPixmap(pixmap, QIcon.Mode.Active)
    result.addPixmap(pixmap, QIcon.Mode.Selected)
    return result


def icon_size(size: int = DEFAULT_SIZE) -> QSize:
    """اندازهٔ آیکون به شکل QSize برای setIconSize."""
    return QSize(int(size), int(size))
