"""
فهرست پوسته‌های نام‌دار برنامه.

هر پوسته از روی تصاویر مرجع استخراج شده است. افزودن پوستهٔ تازه فقط
یعنی افزودن یک ورودی در همین فایل؛ هیچ بخشی از منطق برنامه نباید تغییر
کند.

**نکتهٔ معماری:** پوسته هیچ‌گاه تعیین نمی‌کند که یک قابلیت وجود داشته
باشد یا نه — فقط تعیین می‌کند چگونه دیده شود.
"""

from __future__ import annotations

from ui.themes.tokens import ColorTokens, EffectTokens, MetricTokens, ThemeTokens

#: شناسهٔ پوستهٔ پیش‌فرض برنامه
# پوستهٔ پیش‌فرض برنامه.
#
# کاربر صریحاً خواست «سرمه‌ای اداری» همیشه پیش‌فرض باشد. این فقط
# پیش‌فرضِ نصب تازه است؛ هر کاربری که قبلاً پوسته‌ای انتخاب کرده،
# انتخابش در پایگاه داده محفوظ می‌ماند و بازنویسی نمی‌شود.
DEFAULT_THEME = "corporate_navy"


# ---------------------------------------------------------------------------
# ۱) شیشه‌ای تیره — پوستهٔ پیش‌فرض
# ---------------------------------------------------------------------------
GLASS_DARK = ThemeTokens(
    key="glass_dark",
    name_fa="شیشه‌ای تیره",
    name_en="Glass Dark",
    is_dark=True,
    colors=ColorTokens(
        bg="#0a0e1a",
        surface="#111726",
        surface_alt="#161d2f",
        surface_raised="#1b2338",
        border="#232c42",
        border_strong="#2f3a54",
        text="#e9eefb",
        text_muted="#8e9bb5",
        text_faint="#5f6b85",
        primary="#22d3ee",
        primary_hover="#38dcf2",
        primary_text="#05202b",
        accent="#a78bfa",
        success="#34d399",
        danger="#fb7185",
        warning="#fbbf24",
        neutral="#94a3b8",
        info="#60a5fa",
        success_soft="#0f3d33",
        danger_soft="#40202c",
        warning_soft="#3d3018",
        info_soft="#16304f",
        sidebar_bg="#0d121f",
        sidebar_text="#a8b4cc",
        sidebar_active_bg="#16304f",
        sidebar_active_text="#ffffff",
        sidebar_hover="#151d30",
        topbar_bg="#0b101c",
        topbar_border="#1c2439",
        selection="#1d3a5c",
        scroll="#2a3450",
        glow="#22d3ee",
        shadow="#00000066",
        chart_grid="#1e2740",
        chart_up="#34d399",
        chart_down="#fb7185",
    ),
    metrics=MetricTokens(radius_md=12, radius_lg=16, radius_xl=20),
    effects=EffectTokens(
        primary_gradient=(
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #22d3ee, stop:1 #818cf8)"
        ),
        sidebar_active_gradient=(
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #16304f, stop:1 #1b2b45)"
        ),
        glass=True,
        elevation=True,
    ),
)


# ---------------------------------------------------------------------------
# ۲) روشن مینیمال
# ---------------------------------------------------------------------------
MINIMAL_LIGHT = ThemeTokens(
    key="minimal_light",
    name_fa="روشن مینیمال",
    name_en="Minimal Light",
    is_dark=False,
    colors=ColorTokens(
        bg="#ffffff",
        surface="#ffffff",
        surface_alt="#fafafa",
        surface_raised="#f5f5f5",
        border="#ececec",
        border_strong="#d4d4d4",
        text="#111111",
        text_muted="#737373",
        text_faint="#a3a3a3",
        primary="#111111",
        primary_hover="#333333",
        primary_text="#ffffff",
        accent="#111111",
        success="#15803d",
        danger="#b91c1c",
        warning="#a16207",
        neutral="#737373",
        info="#1d4ed8",
        success_soft="#f0fdf4",
        danger_soft="#fef2f2",
        warning_soft="#fefce8",
        info_soft="#eff6ff",
        sidebar_bg="#ffffff",
        sidebar_text="#525252",
        sidebar_active_bg="#f5f5f5",
        sidebar_active_text="#111111",
        sidebar_hover="#fafafa",
        topbar_bg="#ffffff",
        topbar_border="#ececec",
        selection="#e5e5e5",
        scroll="#d4d4d4",
        glow="#00000000",
        shadow="#00000000",
        chart_grid="#f0f0f0",
        chart_up="#15803d",
        chart_down="#b91c1c",
    ),
    # مینیمال یعنی فاصلهٔ بیشتر و شعاع کمتر: تایپوگرافی حاکم است نه قاب
    metrics=MetricTokens(
        radius_sm=4, radius_md=6, radius_lg=8, radius_xl=10, space_lg=20, space_xl=28
    ),
    effects=EffectTokens(glass=False, elevation=False, row_divider=1),
)


# ---------------------------------------------------------------------------
# ۳) سرمه‌ای اداری
# ---------------------------------------------------------------------------
CORPORATE_NAVY = ThemeTokens(
    key="corporate_navy",
    name_fa="سرمه‌ای اداری",
    name_en="Corporate Navy",
    is_dark=False,
    colors=ColorTokens(
        bg="#eef1f6",
        surface="#ffffff",
        surface_alt="#f6f8fb",
        surface_raised="#eaeef5",
        border="#d8dfea",
        border_strong="#b9c4d6",
        text="#0f1e35",
        text_muted="#5b6b85",
        text_faint="#8b98ad",
        primary="#14315e",
        primary_hover="#1c4179",
        primary_text="#ffffff",
        accent="#c8a24a",
        success="#177245",
        danger="#b3261e",
        warning="#8a6100",
        neutral="#5b6b85",
        info="#14315e",
        success_soft="#e6f4ec",
        danger_soft="#fdeceb",
        warning_soft="#fdf5e3",
        info_soft="#e8eef7",
        sidebar_bg="#0f2347",
        sidebar_text="#c3cddd",
        sidebar_active_bg="#1c4179",
        sidebar_active_text="#ffffff",
        sidebar_hover="#173461",
        topbar_bg="#ffffff",
        topbar_border="#d8dfea",
        selection="#dce6f4",
        scroll="#c3cddd",
        glow="#00000000",
        shadow="#0f1e3522",
        chart_grid="#e4e9f1",
        chart_up="#177245",
        chart_down="#b3261e",
    ),
    metrics=MetricTokens(
        radius_sm=3, radius_md=5, radius_lg=6, radius_xl=8, card_top_accent=3
    ),
    effects=EffectTokens(glass=False, elevation=True),
)

# ---------------------------------------------------------------------------
# ۴) بنفش روشن
# ---------------------------------------------------------------------------
VIOLET_LIGHT = ThemeTokens(
    key="violet_light",
    name_fa="بنفش روشن",
    name_en="Violet Light",
    is_dark=False,
    colors=ColorTokens(
        bg="#faf9ff",
        surface="#ffffff",
        surface_alt="#f5f3ff",
        surface_raised="#ede9fe",
        border="#e9e4fb",
        border_strong="#d3c9f7",
        text="#1e1b33",
        text_muted="#6b6688",
        text_faint="#9b95b5",
        primary="#6d28d9",
        primary_hover="#7c3aed",
        primary_text="#ffffff",
        accent="#a78bfa",
        success="#15803d",
        danger="#dc2626",
        warning="#c2410c",
        neutral="#6b6688",
        info="#6d28d9",
        success_soft="#eafaf0",
        danger_soft="#fdeeee",
        warning_soft="#fdf1e7",
        info_soft="#f2ecfe",
        sidebar_bg="#ffffff",
        sidebar_text="#4c4766",
        sidebar_active_bg="#ede9fe",
        sidebar_active_text="#5b21b6",
        sidebar_hover="#f5f3ff",
        topbar_bg="#ffffff",
        topbar_border="#eee9fd",
        selection="#e6dcfd",
        scroll="#d3c9f7",
        glow="#00000000",
        shadow="#6d28d91f",
        chart_grid="#f1ecfd",
        chart_up="#15803d",
        chart_down="#dc2626",
    ),
    metrics=MetricTokens(radius_md=14, radius_lg=18, radius_xl=22),
    effects=EffectTokens(glass=False, elevation=True),
)


#: همهٔ پوسته‌ها به ترتیب نمایش در تنظیمات
# ---------------------------------------------------------------------------
# ۵) شفق نیمه‌شب — تیرهٔ گرم با لهجهٔ زمردی و طلایی
# ---------------------------------------------------------------------------
# چرا این پوسته: سه پوستهٔ تیرهٔ موجود همه آبی/بنفش سردند. این یکی پس‌زمینهٔ
# بنفشِ عمیق دارد با لهجهٔ زمردی و طلایی، تا هم چشم در کار طولانی کمتر خسته
# شود و هم سبز/قرمزِ بازار روی زمینه بهتر تفکیک شود.
MIDNIGHT_AURORA = ThemeTokens(
    key="midnight_aurora",
    name_fa="شفق نیمه‌شب",
    name_en="Midnight Aurora",
    is_dark=True,
    colors=ColorTokens(
        bg="#0b0a18",
        surface="#151329",
        surface_alt="#1c1936",
        surface_raised="#232045",
        border="#2c2851",
        border_strong="#3b3568",
        text="#f0edff",
        text_muted="#a49dc4",
        text_faint="#6f6894",
        primary="#5eead4",
        primary_hover="#7ff2de",
        primary_text="#04201c",
        accent="#fbbf24",
        success="#4ade80",
        danger="#fb7185",
        warning="#fbbf24",
        neutral="#a49dc4",
        info="#818cf8",
        success_soft="#10361f",
        danger_soft="#3f1d2b",
        warning_soft="#3b2f14",
        info_soft="#22224d",
        sidebar_bg="#0e0c1f",
        sidebar_text="#b4addb",
        sidebar_active_bg="#241f4a",
        sidebar_active_text="#ffffff",
        sidebar_hover="#191634",
        topbar_bg="#0c0a1b",
        topbar_border="#241f45",
        selection="#2a2455",
        scroll="#332c60",
        glow="#5eead4",
        shadow="#00000080",
        chart_grid="#241f45",
        chart_up="#4ade80",
        chart_down="#fb7185",
    ),
    metrics=MetricTokens(radius_md=14, radius_lg=18, radius_xl=24),
    effects=EffectTokens(
        primary_gradient=(
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #5eead4, stop:1 #818cf8)"
        ),
        sidebar_active_gradient=(
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #241f4a, stop:1 #2f2757)"
        ),
        glass=True,
        elevation=True,
    ),
)


# ---------------------------------------------------------------------------
# ۶) ابریشم سلطنتی — تیرهٔ لوکس با لهجهٔ طلایی و فیروزه‌ای
# ---------------------------------------------------------------------------
# چرا این پوسته: کاربر پوسته‌ای «زیباتر» خواست. پنج پوستهٔ موجود یا سردند
# (آبی/بنفش) یا روشن. این یکی پس‌زمینهٔ زغالی-آبی بسیار عمیق دارد با لهجهٔ
# طلایی گرم؛ ترکیبی که حس «پنل حرفه‌ای مالی» می‌دهد.
#
# دو تصمیم آگاهانه:
#   ۱. طلا فقط لهجه است نه رنگ اصلی دکمه‌ها، چون متن روی طلا کم‌کنتراست
#      می‌شود؛ رنگ اصلی فیروزه‌ای روشن است که روی زمینهٔ تیره خوانا است.
#   ۲. سبز/قرمز بازار عمداً از خانوادهٔ طلایی دور نگه داشته شده‌اند تا
#      سود و زیان با لهجهٔ پوسته اشتباه گرفته نشوند.
ROYAL_SILK = ThemeTokens(
    key="royal_silk",
    name_fa="ابریشم سلطنتی",
    name_en="Royal Silk",
    is_dark=True,
    colors=ColorTokens(
        bg="#070b12",
        surface="#0f151f",
        surface_alt="#151c2a",
        surface_raised="#1c2536",
        border="#243044",
        border_strong="#33425c",
        text="#eef3fb",
        text_muted="#94a3bd",
        text_faint="#64738d",
        primary="#2dd4bf",
        primary_hover="#5eead4",
        primary_text="#04231f",
        accent="#e0b155",
        success="#3ddc97",
        danger="#f4667c",
        warning="#e0b155",
        neutral="#94a3bd",
        info="#63a4ff",
        success_soft="#0d3a2b",
        danger_soft="#3d1c26",
        warning_soft="#3a2f16",
        info_soft="#14304f",
        sidebar_bg="#090e17",
        sidebar_text="#9fb0cb",
        sidebar_active_bg="#16283c",
        sidebar_active_text="#ffffff",
        sidebar_hover="#121a27",
        topbar_bg="#080d15",
        topbar_border="#1b2534",
        selection="#17304a",
        scroll="#2a3748",
        glow="#e0b155",
        shadow="#00000099",
        chart_grid="#1a2434",
        chart_up="#3ddc97",
        chart_down="#f4667c",
    ),
    metrics=MetricTokens(radius_md=14, radius_lg=18, radius_xl=24),
    effects=EffectTokens(
        primary_gradient=(
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #2dd4bf, stop:1 #63a4ff)"
        ),
        sidebar_active_gradient=(
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #16283c, stop:1 #1d3450)"
        ),
        glass=True,
        elevation=True,
    ),
)


# ---------------------------------------------------------------------------
# ۷) نیلی ارکیده — تیرهٔ گرم با لهجهٔ ارغوانی و مرجانی
# ---------------------------------------------------------------------------
# چرا این پوسته: هر سه پوستهٔ تیرهٔ موجود رنگ اصلی‌شان از خانوادهٔ
# فیروزه‌ای/سبزآبی است (‎#22d3ee‎، ‎#2dd4bf‎، ‎#5eead4‎) و کنار هم تقریباً
# یک‌شکل دیده می‌شوند. این پوسته عمداً از آن خانواده فاصله می‌گیرد: بنفشِ
# ارکیده به‌عنوان رنگ اصلی روی زمینهٔ نیلی عمیق.
#
# سه تصمیم آگاهانه:
#   ۱. زمینه خنثای خاکستری نیست بلکه ته‌مایهٔ نیلی دارد؛ همین کمی گرما
#      باعث می‌شود ساعت‌ها کار با آن خسته‌کننده نباشد.
#   ۲. لهجه مرجانی است، نه طلایی — تا با «ابریشم سلطنتی» اشتباه نشود.
#   ۳. سبز و قرمز بازار از خانوادهٔ ارغوانی و مرجانی دور نگه داشته شده‌اند:
#      قرمزِ زیان به‌سمت رُز و سبزِ سود به‌سمت زمردی برده شده تا هرگز با
#      رنگ لهجه قاطی نشوند. اگر قرمزِ زیان و مرجانیِ لهجه شبیه می‌شدند،
#      کاربر در یک نگاه نمی‌فهمید کدام عدد ضرر است.
ORCHID_INDIGO = ThemeTokens(
    key="orchid_indigo",
    name_fa="نیلی ارکیده",
    name_en="Orchid Indigo",
    is_dark=True,
    colors=ColorTokens(
        bg="#0c0a1f",
        surface="#151233",
        surface_alt="#1d1943",
        surface_raised="#262055",
        border="#302a63",
        border_strong="#413a80",
        text="#f3f0ff",
        text_muted="#a9a2d0",
        text_faint="#736c9e",
        primary="#c084fc",
        primary_hover="#d8b4fe",
        primary_text="#20073a",
        accent="#fb923c",
        success="#34d399",
        danger="#f43f5e",
        warning="#fbbf24",
        neutral="#a9a2d0",
        info="#60a5fa",
        success_soft="#0d3b2e",
        danger_soft="#3f1524",
        warning_soft="#3b2d12",
        info_soft="#182a52",
        sidebar_bg="#0f0c28",
        sidebar_text="#b3abdc",
        sidebar_active_bg="#2a2260",
        sidebar_active_text="#ffffff",
        sidebar_hover="#1a1640",
        topbar_bg="#0d0a23",
        topbar_border="#251f52",
        selection="#2e2668",
        scroll="#3a3277",
        glow="#c084fc",
        shadow="#00000099",
        chart_grid="#241e4e",
        chart_up="#34d399",
        chart_down="#f43f5e",
    ),
    metrics=MetricTokens(radius_md=14, radius_lg=20, radius_xl=26),
    effects=EffectTokens(
        primary_gradient=(
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #a855f7, stop:1 #f472b6)"
        ),
        sidebar_active_gradient=(
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #2a2260, stop:1 #3a2c74)"
        ),
        glass=True,
        elevation=True,
    ),
)


# ---------------------------------------------------------------------------
# ۸) نئون کربنی — پوستهٔ مدرن درخواستی کاربر
# ---------------------------------------------------------------------------
# طراحی این پوسته عمداً با بقیه فرق دارد: پس‌زمینهٔ خنثای زغالی (نه آبیِ
# سرد، نه بنفش) تا رنگ سبز/قرمزِ نمودار روی آن خالص دیده شود، کنتراست
# بالا، و گوشه‌های نرم‌تر از همهٔ پوسته‌های دیگر. لهجهٔ نعنایی-فیروزه‌ای
# همان زبان بصری داشبوردهای مدرن معاملاتی است.
CARBON_NEON = ThemeTokens(
    key="carbon_neon",
    name_fa="نئون کربنی",
    name_en="Carbon Neon",
    is_dark=True,
    colors=ColorTokens(
        bg="#0b0f10",
        surface="#131819",
        surface_alt="#181f21",
        surface_raised="#1f282a",
        border="#25302f",
        border_strong="#33413f",
        text="#ecfdf7",
        text_muted="#8fa5a1",
        text_faint="#5e716e",
        primary="#2dd4bf",
        primary_hover="#5eead4",
        primary_text="#04211d",
        accent="#f0abfc",
        success="#4ade80",
        danger="#f87171",
        warning="#facc15",
        neutral="#94a3b8",
        info="#38bdf8",
        success_soft="#0c3627",
        danger_soft="#3d1d1d",
        warning_soft="#3a3212",
        info_soft="#0e2f42",
        sidebar_bg="#0d1213",
        sidebar_text="#9db3af",
        sidebar_active_bg="#123330",
        sidebar_active_text="#ffffff",
        sidebar_hover="#151d1e",
        topbar_bg="#0a0e0f",
        topbar_border="#1d2726",
        selection="#134e48",
        scroll="#2b3836",
        glow="#2dd4bf",
        shadow="#000000aa",
        chart_grid="#1c2624",
        chart_up="#4ade80",
        chart_down="#f87171",
    ),
    metrics=MetricTokens(radius_md=16, radius_lg=22, radius_xl=28),
    effects=EffectTokens(
        primary_gradient=(
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #2dd4bf, stop:1 #22d3ee)"
        ),
        sidebar_active_gradient=(
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #123330, stop:1 #17423c)"
        ),
        glass=True,
        elevation=True,
    ),
)


# ---------------------------------------------------------------------------
# ۹) طلایی تاریک — پوستهٔ «اتاق معاملات»
# ---------------------------------------------------------------------------
# کاربر یک پوستهٔ فانتزی با «حال و هوای ترید حرفه‌ای» خواست و مشخصاً
# **خطوط مربعی** (گوشه‌های تیز). این تنها پوسته‌ای است که شعاع گردی‌اش
# صفر است؛ بقیه گوشهٔ گرد دارند.
#
# منطق رنگ: زغالی بسیار تیره تا نمودارها بدرخشند، طلایی برنزی برای
# تأکید (حس بورس لوکس)، و سبز/قرمز اشباع‌شده برای صعود و نزول که در
# پس‌زمینهٔ تیره بیشترین خوانایی را دارند.
GOLD_DARK = ThemeTokens(
    key="gold_dark",
    name_fa="طلایی تاریک",
    name_en="Gold Dark",
    is_dark=True,
    colors=ColorTokens(
        bg="#0c0a07",
        surface="#141110",
        surface_alt="#1b1715",
        surface_raised="#221d19",
        border="#2e2721",
        border_strong="#463a2c",
        text="#f5eee2",
        text_muted="#a89882",
        text_faint="#6f6355",
        primary="#d4a537",
        primary_hover="#e8bc50",
        primary_text="#1a1408",
        accent="#c77d3a",
        success="#3fbf7f",
        danger="#e0554f",
        warning="#e8a33d",
        neutral="#9a8e7c",
        info="#5fa8d3",
        success_soft="#10301f",
        danger_soft="#3a1a17",
        warning_soft="#3a2a12",
        info_soft="#14283a",
        sidebar_bg="#0a0806",
        sidebar_text="#b3a48f",
        sidebar_active_bg="#2a2114",
        sidebar_active_text="#f7d98a",
        sidebar_hover="#171310",
        topbar_bg="#0a0806",
        topbar_border="#272019",
        selection="#3a2d16",
        scroll="#3a3129",
        glow="#d4a537",
        shadow="#00000088",
        chart_grid="#241e18",
        chart_up="#3fbf7f",
        chart_down="#e0554f",
    ),
    # گوشه‌های کاملاً تیز — همان «خطوط مربعی» که کاربر خواست.
    # ردیف‌های بلندتر و فونت کمی بزرگ‌تر، حس ترمینال معاملاتی می‌دهد.
    metrics=MetricTokens(
        radius_sm=0,
        radius_md=0,
        radius_lg=0,
        radius_xl=0,
        radius_pill=0,
        border_width=1,
        row_height=44,
        font_metric=26,
    ),
    effects=EffectTokens(
        primary_gradient=(
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #d4a537, stop:1 #c77d3a)"
        ),
        sidebar_active_gradient=(
            "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #2a2114, stop:1 #1d1710)"
        ),
        glass=False,
        elevation=True,
    ),
)


THEME_CATALOG: dict[str, ThemeTokens] = {
    theme.key: theme
    for theme in (
        GLASS_DARK,
        GOLD_DARK,
        CARBON_NEON,
        ORCHID_INDIGO,
        ROYAL_SILK,
        MIDNIGHT_AURORA,
        MINIMAL_LIGHT,
        CORPORATE_NAVY,
        VIOLET_LIGHT,
    )
}

#: نگاشت نام‌های قدیمی به پوسته‌های تازه — تنظیمات کاربران فعلی نباید بشکند
LEGACY_ALIASES: dict[str, str] = {
    "dark": "glass_dark",
    "light": "minimal_light",
}


def resolve_key(key: str | None) -> str:
    """
    یافتن شناسهٔ معتبر پوسته.

    نام‌های نسخه‌های پیشین (`dark`/`light`) و مقادیر ناشناخته به پوستهٔ
    مناسب نگاشت می‌شوند تا تنظیمات ذخیره‌شدهٔ کاربر هرگز باعث خطا نشود.
    """
    if not key:
        return DEFAULT_THEME
    candidate = str(key).strip().lower()
    if candidate in THEME_CATALOG:
        return candidate
    if candidate in LEGACY_ALIASES:
        return LEGACY_ALIASES[candidate]
    return DEFAULT_THEME


def get_theme(key: str | None) -> ThemeTokens:
    """دریافت توکن‌های یک پوسته با نام آن."""
    return THEME_CATALOG[resolve_key(key)]


def list_themes() -> list[ThemeTokens]:
    """فهرست همهٔ پوسته‌ها برای نمایش در تنظیمات."""
    return list(THEME_CATALOG.values())
