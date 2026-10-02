"""
اجرای برنامهٔ Kivy بدون نمایشگر/OpenGL — برای آزمون منطق و چیدمان رابط موبایل.

Kivy موقع import کردن `kivy.core.window` یک ارائه‌دهندهٔ پنجره انتخاب می‌کند؛
روی سرور بی‌نمایشگر هیچ‌کدام کار نمی‌کند. اینجا انتخاب را به یک پنجرهٔ
«بی‌سر» هدایت می‌کنیم که چیزی رسم نمی‌کند (GL = mock) ولی رویدادها، چیدمان
و Clock کامل کار می‌کنند.
"""

from __future__ import annotations

import os
import sys


def install(size: tuple[int, int] = (412, 900)) -> None:
    os.environ.setdefault("KIVY_GL_BACKEND", "mock")
    os.environ.setdefault("KIVY_TEXT", "pil")
    os.environ.setdefault("KIVY_NO_ARGS", "1")
    os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
    os.environ.setdefault("KIVY_NO_FILELOG", "1")
    os.environ.setdefault("KIVY_HOME", os.path.join(os.environ.get("TMPDIR", "/tmp"), "kivy_headless_home"))
    if "kivy.core.window" in sys.modules:
        return
    import kivy.core as core  # noqa: PLC0415

    original = core.core_select_lib

    def select(category, llist, create_instance=False, base="kivy.core", basemodule=None):  # noqa: ANN001, ANN202
        if category != "window":
            return original(category, llist, create_instance, base, basemodule)
        from kivy.core.window import WindowBase  # noqa: PLC0415 — ماژول نیمه‌بارگذاری‌شده

        class HeadlessWindow(WindowBase):
            def create_window(self, *args) -> None:  # noqa: ANN002
                self._size = size
                self.system_size = size
                super().create_window(*args)

            def flip(self) -> None:
                return

            def mainloop(self) -> None:
                return

            def close(self) -> None:
                return

            def _get_window_pos(self):  # noqa: ANN202
                return 0, 0

        return HeadlessWindow() if create_instance else HeadlessWindow

    core.core_select_lib = select
    import kivy.core.window  # noqa: F401, PLC0415

    core.core_select_lib = original
