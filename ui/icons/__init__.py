"""
مجموعهٔ آیکون‌های برداری برنامه.

چرا این ماژول ساخته شد: پیش‌تر آیکون‌ها کاراکترهای یونیکد (مثل «◧» و
«⇄») بودند. هیچ‌کدام از این نویسه‌ها در فونت وزیرمتن وجود ندارد، پس
سیستم مجبور می‌شد از فونت جایگزین استفاده کند و نتیجه روی ویندوز مربع
خالی یا شکل نامربوط بود. حالا هر آیکون یک مسیر برداری SVG است که خودمان
رسم می‌کنیم؛ به هیچ فونت یا بستهٔ بیرونی وابسته نیست و رنگش با پوستهٔ
جاری هماهنگ می‌شود.

نمونهٔ استفاده:
    from ui.icons import icon, icon_pixmap

    button.setIcon(icon("refresh", "#22d3ee"))
    label.setPixmap(icon_pixmap("wallet", "#e2e8f0", 20))
"""

from __future__ import annotations

from ui.icons.registry import (
    ICON_NAMES,
    available_icons,
    icon,
    icon_pixmap,
    icon_svg,
    register_icon,
    resolve_name,
)

__all__ = [
    "ICON_NAMES",
    "available_icons",
    "icon",
    "icon_pixmap",
    "icon_svg",
    "register_icon",
    "resolve_name",
]
