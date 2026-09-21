"""
توکن‌های سیستم طراحی.

چرا توکن؟
    اگر رنگ‌ها و اندازه‌ها مستقیم داخل صفحه‌ها نوشته شوند، افزودن هر
    پوستهٔ تازه یعنی دست‌زدن به ده‌ها فایل. با توکن، هر پوسته فقط یک
    مجموعه مقدار است و منطق برنامه اصلاً نمی‌داند چند پوسته وجود دارد.

قاعدهٔ سخت پروژه:
    هیچ رنگ سخت‌کدشده‌ای در صفحه‌ها و مؤلفه‌ها نوشته نمی‌شود. هر مقدار
    بصری از همین‌جا می‌آید.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class ColorTokens:
    """رنگ‌های یک پوسته."""

    # سطوح
    bg: str
    surface: str
    surface_alt: str
    surface_raised: str
    border: str
    border_strong: str

    # متن
    text: str
    text_muted: str
    text_faint: str

    # رنگ اصلی و تأکید
    primary: str
    primary_hover: str
    primary_text: str
    accent: str

    # معنایی
    success: str
    danger: str
    warning: str
    neutral: str
    info: str

    # پس‌زمینهٔ ملایم برای تراشه‌ها و نشان‌ها
    success_soft: str
    danger_soft: str
    warning_soft: str
    info_soft: str

    # نوار کناری
    sidebar_bg: str
    sidebar_text: str
    sidebar_active_bg: str
    sidebar_active_text: str
    sidebar_hover: str

    # نوار بالایی
    topbar_bg: str
    topbar_border: str

    # متفرقه
    selection: str
    scroll: str
    glow: str
    shadow: str
    chart_grid: str
    chart_up: str
    chart_down: str


@dataclass(frozen=True)
class MetricTokens:
    """اندازه‌ها، فاصله‌ها و شعاع‌ها."""

    radius_sm: int = 6
    radius_md: int = 10
    radius_lg: int = 14
    radius_xl: int = 18
    radius_pill: int = 999

    space_xs: int = 4
    space_sm: int = 8
    space_md: int = 12
    space_lg: int = 16
    space_xl: int = 24

    border_width: int = 1
    card_top_accent: int = 0  # نوار رنگی بالای کارت (فقط پوستهٔ اداری)

    font_xs: int = 11
    font_sm: int = 12
    font_md: int = 13
    font_lg: int = 15
    font_xl: int = 21
    font_metric: int = 24

    sidebar_width: int = 232
    topbar_height: int = 56
    row_height: int = 40


@dataclass(frozen=True)
class EffectTokens:
    """جلوه‌ها: گرادیان، شفافیت، هاله."""

    #: گرادیان دکمهٔ اصلی؛ اگر خالی باشد رنگ تخت به کار می‌رود
    primary_gradient: str = ""
    #: گرادیان آیتم فعال نوار کناری
    sidebar_active_gradient: str = ""
    #: آیا کارت‌ها ظاهر شیشه‌ای دارند
    glass: bool = False
    #: آیا سایه/هاله فعال است
    elevation: bool = True
    #: ضخامت خط جداکنندهٔ ردیف‌های جدول
    row_divider: int = 1


@dataclass(frozen=True)
class ThemeTokens:
    """یک پوستهٔ کامل: فراداده + رنگ + اندازه + جلوه."""

    key: str
    name_fa: str
    name_en: str
    is_dark: bool
    colors: ColorTokens
    metrics: MetricTokens = field(default_factory=MetricTokens)
    effects: EffectTokens = field(default_factory=EffectTokens)

    def as_format_map(self) -> dict[str, Any]:
        """
        تبدیل توکن‌ها به نگاشت تخت برای قالب QSS.

        کلیدها بدون پیشوند می‌آیند تا قالب خوانا بماند: ``{bg}`` به‌جای
        ``{colors.bg}``.
        """
        data: dict[str, Any] = {}
        for token_group in (self.colors, self.metrics):
            data.update(vars(token_group))
        effects = vars(self.effects)
        data.update({f"fx_{key}": value for key, value in effects.items()})

        # مقدار آمادهٔ پس‌زمینهٔ دکمهٔ اصلی: گرادیان اگر تعریف شده باشد،
        # وگرنه رنگ تخت. این کار شرط‌گذاری داخل قالب QSS را حذف می‌کند.
        data["primary_bg"] = self.effects.primary_gradient or self.colors.primary
        data["sidebar_active_fill"] = (
            self.effects.sidebar_active_gradient or self.colors.sidebar_active_bg
        )
        return data

    def scaled(self, percent: int) -> ThemeTokens:
        """
        نسخهٔ بزرگ‌نمایی‌شدهٔ پوسته بر پایهٔ درصد اندازهٔ قلم.

        تنظیم «اندازهٔ قلم» در صفحهٔ تنظیمات از همین‌جا اثر می‌گذارد.
        """
        if percent == 100:
            return self
        factor = max(60, min(200, percent)) / 100.0

        def scale(value: int, minimum: int = 8) -> int:
            return max(minimum, round(value * factor))

        metrics = replace(
            self.metrics,
            font_xs=scale(self.metrics.font_xs),
            font_sm=scale(self.metrics.font_sm),
            font_md=scale(self.metrics.font_md),
            font_lg=scale(self.metrics.font_lg),
            font_xl=scale(self.metrics.font_xl),
            font_metric=scale(self.metrics.font_metric),
            row_height=scale(self.metrics.row_height, 24),
            topbar_height=scale(self.metrics.topbar_height, 40),
            sidebar_width=scale(self.metrics.sidebar_width, 160),
        )
        return replace(self, metrics=metrics)

    def compact(self) -> ThemeTokens:
        """نسخهٔ فشرده: فاصله‌ها و ارتفاع ردیف کمتر برای نمایش داده بیشتر."""
        metrics = replace(
            self.metrics,
            space_sm=max(4, self.metrics.space_sm - 2),
            space_md=max(6, self.metrics.space_md - 4),
            space_lg=max(8, self.metrics.space_lg - 5),
            space_xl=max(12, self.metrics.space_xl - 8),
            row_height=max(26, self.metrics.row_height - 8),
        )
        return replace(self, metrics=metrics)
