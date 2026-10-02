# -*- mode: python ; coding: utf-8 -*-
"""
پیکربندی PyInstaller برای ساخت نسخه ویندوزی.

اجرا:
    pyinstaller CryptoAITrader.spec --noconfirm

نکته‌های مهم:
    * فایل‌های داده (ترجمه‌ها، قالب‌های پرامپت، مستندات، مهاجرت‌ها) باید
      صریحاً اضافه شوند؛ PyInstaller فقط ماژول‌های پایتون را دنبال می‌کند
      و فایل‌های JSON و Markdown را خودش پیدا نمی‌کند.
    * ماژول‌هایی که با نام و در زمان اجرا بارگذاری می‌شوند (رجیستری‌های
      صرافی، اندیکاتور، استراتژی و ارائه‌دهنده هوش مصنوعی) در تحلیل ایستا
      دیده نمی‌شوند، پس در `hiddenimports` فهرست شده‌اند.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = Path(SPECPATH)  # noqa: F821 - توسط PyInstaller تزریق می‌شود

# --- فایل‌های داده -----------------------------------------------------
datas = [
    (str(PROJECT_ROOT / "localization" / "fa"), "localization/fa"),
    (str(PROJECT_ROOT / "localization" / "en"), "localization/en"),
    (str(PROJECT_ROOT / "ai" / "prompts"), "ai/prompts"),
    # قلم فارسی برای خروجی PDF. بدون این، گزارش فارسی در نسخهٔ بسته‌بندی‌شده
    # به قلم پیش‌فرض برمی‌گردد و حروف به‌هم‌ریخته چاپ می‌شود.
    (str(PROJECT_ROOT / "assets" / "fonts"), "assets/fonts"),
    (str(PROJECT_ROOT / "docs"), "docs"),
    (str(PROJECT_ROOT / "migrations"), "migrations"),
    (str(PROJECT_ROOT / "alembic.ini"), "."),
    (str(PROJECT_ROOT / "README.md"), "."),
    (str(PROJECT_ROOT / "README_EN.md"), "."),
]

icon_file = PROJECT_ROOT / "assets" / "icon.ico"
if icon_file.exists():
    datas.append((str(icon_file), "assets"))

# --- ماژول‌های پویا ----------------------------------------------------
hiddenimports = [
    *collect_submodules("market.providers"),
    *collect_submodules("indicators"),
    *collect_submodules("signals.strategies"),
    *collect_submodules("ai.providers"),
    "keyring.backends.Windows",
    "keyring.backends.SecretService",
    "keyring.backends.fail",
    "sqlalchemy.dialects.sqlite",
    "pandas",
    "numpy",
    "openpyxl",
    "reportlab.pdfgen",
    "reportlab.lib",
    "pyqtgraph",
]

# --- کتابخانه‌هایی که لازم نیستند --------------------------------------
# حذف این‌ها حجم خروجی را چند ده مگابایت کم می‌کند بدون اثر بر عملکرد.
excludes = [
    "tkinter",
    "matplotlib",
    # وابستگی‌های اختیاریِ pandas/pyqtgraph که برنامه هیچ‌جا وارد نمی‌کند
    # (بررسی شد: صفر import مستقیم). فقط PyInstaller آن‌ها را از روی
    # مسیرهای شرطیِ pandas برمی‌داشت و ~۲۸۰ مگابایت به خروجی می‌افزود.
    "numba",
    "llvmlite",
    "scipy",
    "lxml",
    "PIL",
    # زیرماژول‌های خود pandas را حذف نمی‌کنیم: `pandas.api.typing` آن‌ها
    # را بی‌قیدوشرط وارد می‌کند و حذفشان برنامه را در بالا آمدن می‌شکند
    # (آزموده شد: ModuleNotFoundError: pandas.io.stata).
    "IPython",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.Qt3DCore",
    "PySide6.QtMultimedia",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.QtBluetooth",
    "PySide6.QtDesigner",
    "PySide6.QtTest",
]

a = Analysis(  # noqa: F821
    ["main.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CryptoAITrader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # نسخهٔ ۲.۵.۳: UPX (اگر روی سیستم باشد) DLLهای Qt را خراب می‌کند و
    # برنامهٔ ساخته‌شده بالا نمی‌آید؛ فشرده‌سازی خاموش است.
    upx=False,
    console=False,  # برنامه گرافیکی است؛ پنجره کنسول نباید باز شود
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_file) if icon_file.exists() else None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CryptoAITrader",
)
