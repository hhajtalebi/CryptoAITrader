# گزارش تحویل ۲.۵.۳ — ربات‌های ساخت فایل نصبی ویندوز و APK

تاریخ: ۲۰۲۶-۰۹-۲۵ · دسکتاپ `2.5.3` · موبایل `1.9.13` · commit نشده (آخرین commit: `511d2b5`)

## گزارش کاربر

1. **ویندوز:** ربات ساخت «تعداد زیادی پنجره از قسمت‌های مختلف نرم‌افزار باز می‌کند» و فایل نصبی ساخته نمی‌شود.
2. **اندروید:** از `C:\Users\mobocom\Downloads\251\CryptoAITrader` ساخت با «APK ساخته نشد. پیام‌های بالا را بخوانید»
   و «ساخت با خطا تمام شد» (RESULT=1) تمام می‌شود.

## علت‌ها

### فایل نصبی ویندوز

| علت | اثر |
|---|---|
| `build_installer.py` پیش از PyInstaller **کل ۲۵۰۰ آزمون** را روی دسکتاپ واقعی اجرا می‌کرد؛ آزمون‌های رابط هرکدام پنجرهٔ واقعی (داشبورد، کیف پول، سیگنال‌ها…) می‌ساختند | همان «پنجره‌های زیاد» |
| خروجی آزمون‌ها گرفته و پنهان می‌شد و فقط ۶ خط آخر نمایش داده می‌شد | به نظر می‌رسید ربات گیر کرده است |
| هر شکست آزمون (مثلاً وابسته به صفحه‌نمایش/فونت ویندوز) ساخت را **پیش از PyInstaller** متوقف می‌کرد | فایل نصبی هیچ‌وقت ساخته نمی‌شد |
| BOM (بایت‌های EF BB BF) در ابتدای `build_installer.bat` و `build_apk.bat` | `@echo off` شناخته نمی‌شد و همهٔ فرمان‌ها در کنسول تکرار می‌شدند |
| `installer/CryptoAITrader.iss` بدون BOM | Inno Setup 6 فایل را ANSI می‌خواند و متن فارسی نصب‌کننده خراب می‌شد |
| `upx=True` | اگر UPX نصب باشد، بعضی آنتی‌ویروس‌ها فایل فشرده را قرنطینه می‌کنند |

### APK

| علت | اثر |
|---|---|
| `buildozer.spec` به `assets/icon.png` و `assets/presplash.png` ارجاع می‌داد و `main.py` به `assets/Vazirmatn-Regular.ttf`؛ پوشهٔ `mobile/assets` وجود نداشت | buildozer در مرحلهٔ بسته‌بندی شکست می‌خورد؛ برنامه هم بدون قلم فارسی بالا نمی‌آمد |
| `android.accept_sdk_license` تنظیم نشده بود | buildozer منتظر پذیرش مجوز SDK می‌ماند و ورودی بسته بود ← شکست |
| `python-bidi` بدون نسخه | نسخه‌های جدید (۰٫۵+) با Rust ساخته می‌شوند و python-for-android آن را نمی‌سازد |
| آزمون هم‌ارزی ریاضی با پایتون سیستم اجرا می‌شد که numpy/pandas/pytest ندارد | شکست پیش از رسیدن به buildozer |
| ساخت روی `/mnt/c/...` (NTFS) | بسیار کند، مشکل مجوز فایل‌ها و symlink در NDK |
| `pip3 install --user buildozer` | در اوبونتو ۲۴٫۰۴ با «externally-managed-environment» رد می‌شود |

## تغییرها

### مشترک — `tools/build_common.py` (جدید)
- `run_streaming`: خروجی هر فرمان **زنده** در کنسول (با پیشوند `|`) و کامل در فایل گزارش؛ ورودی بسته (فرمانی منتظر
  کلید نمی‌ماند)؛ ۱۲۷ = فرمان پیدا نشد، ۱۲۴ = مهلت تمام شد.
- گزارش کامل هر ساخت: `build_logs\installer-<زمان>.log` و `build_logs\apk-<زمان>.log`؛ مسیرش در پایان چاپ می‌شود.
- `headless_env`: `QT_QPA_PLATFORM=offscreen` (هیچ پنجره‌ای روی صفحه نمی‌آید)، بدون استخر فرایند، UTF-8.

### فایل نصبی ویندوز — `scripts\build_installer.bat`
گام‌ها: نصب وابستگی‌ها ← **بررسی سلامت کد (بدون پنجره)** ← آزمون‌ها (پیش‌فرض رد) ← PyInstaller ← Inno Setup ← `latest.json`.
- «بررسی سلامت کد»: کامپایل همهٔ فایل‌های پایتون و بارگذاری ماژول‌های اصلی (رابط، کنترلر، صرافی، سیگنال) به‌صورت
  بی‌پنجره؛ چند ثانیه طول می‌کشد و خطای واقعی بسته‌بندی را زود نشان می‌دهد.
- آزمون کامل اختیاری است: `scripts\build_installer.bat --with-tests` (یا `set RUN_TESTS=1`)؛ آن هم بی‌پنجره.
  `--skip-tests` قدیمی همچنان پذیرفته می‌شود.
- اگر PyInstaller تمام شود ولی `CryptoAITrader.exe` ساخته نشده باشد، خطا گزارش می‌شود (نه «موفق»).
- `scripts\build_windows.bat` حالا همان `build_installer.bat` را صدا می‌زند.
- BOM از فایل‌های bat حذف شد؛ `.iss` با BOM؛ `upx=False`.
- `tests/conftest.py` پیش‌فرض offscreen دارد؛ اجرای دستی `pytest` هم دیگر پنجره باز نمی‌کند.

### APK — `scripts\build_apk.bat`
- `mobile/assets/`: `icon.png` (۵۱۲×۵۱۲)، `presplash.png` (۱۰۸۰×۱۹۲۰)، `Vazirmatn-Regular.ttf`.
- `buildozer.spec`: `android.accept_sdk_license = True`، `python-bidi==0.4.2`، `warn_on_root = 0`.
- گام جدید «بررسی ابزارهای ساخت اندروید داخل WSL»: جاوا ۱۷، autoconf، libtool، pkg-config، cmake… را می‌سنجد؛
  اگر چیزی نباشد **یک فرمان apt کامل** برای کپی نشان می‌دهد. buildozer را خودش در `~/.cai-buildozer` (venv) نصب می‌کند.
- ساخت در `~/cryptoaitrader-apk` داخل لینوکس WSL (کپی سورس بدون `.buildozer`/`bin`)؛ APK به `mobile\bin` و
  `dist\apk` برگردانده می‌شود. کش SDK/NDK در لینوکس می‌ماند.
- آزمون ریاضی اگر numpy/pandas/pytest نباشند «رد شد» می‌شود نه «شکست»؛ `build_apk.bat` اول پایتون `.venv` پروژه را
  امتحان می‌کند.
- موبایل `1.9.13`.

## روش استفاده

**فایل نصبی:** Inno Setup 6 را نصب کنید (jrsoftware.org/isdl.php)، سپس `scripts\build_installer.bat`.
خروجی: `dist\installer\CryptoAITrader-Setup-2.5.3.exe` (بدون Inno Setup فقط `dist\CryptoAITrader\CryptoAITrader.exe`).

**APK:** یک بار در PowerShell (مدیر): `wsl --install -d Ubuntu`، سپس داخل Ubuntu:

```
sudo apt update && sudo apt install -y autoconf cmake libffi-dev libncurses-dev libssl-dev libtool lld openjdk-17-jdk pkg-config python3-pip python3-venv zlib1g-dev build-essential git unzip zip
```

سپس `scripts\build_apk.bat`. ساخت نخست ۴۰ تا ۹۰ دقیقه (دانلود SDK/NDK حدود ۳ گیگابایت)؛ بعدی چند دقیقه.

## آزمون

- جدید: `tests/test_v253_build_tools.py` (BOM، زنجیرهٔ گام‌ها با `_run` جعلی، اجرای زندهٔ واقعی، ۱۲۷/۱۲۴، پرچم‌های
  خط فرمان، کلیدهای spec، وجود/اندازهٔ دارایی‌ها، اسکریپت WSL، گزارش apt، ردشدن آزمون ریاضی).
- اجرای واقعی در sandbox لینوکس: import سلامت بی‌پنجره ✓ (۱٫۹ ثانیه)، compileall ✓، بررسی ابزارها فرمان apt
  درست را ساخت و buildozer 1.5.0 را خودکار در venv نصب کرد ✓، PyInstaller با `CryptoAITrader.spec` کامل شد ✓
  (با کتابخانهٔ جایگزین libpython چون پایتون sandbox کتابخانهٔ اشتراکی ندارد؛ فقط تحلیل spec سنجیده شد).
- کل مجموعه: **2545 passed، 2 skipped، 0 failed (2547)**.

## محدودیت‌ها

- ساخت واقعی ویندوز (PyInstaller + Inno Setup روی ویندوز) و APK (SDK/NDK اندروید) در sandbox ممکن نیست؛ اگر باز هم
  شکست خورد، فایل `build_logs\installer-*.log` یا `build_logs\apk-*.log` را بفرستید.
- آیکون و صفحهٔ شروع موبایل ساده و تولیدشده با کد هستند؛ قابل جایگزینی با طرح دلخواه (همان نام و اندازه).
- هیچ تضمینی برای سود/بی‌ضرری وجود ندارد؛ حالت کاغذی و نگهبان سفارش واقعی دست نخورده‌اند.
