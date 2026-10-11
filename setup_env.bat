@echo off
REM =================================================================
REM  Crypto AI Trader 2.7.1 — ساخت خودکارِ محیط مجازی (ویندوز)
REM =================================================================
REM
REM  این فایل محیط مجازی را دقیقاً با همان نسخه‌هایی می‌سازد که نسخهٔ
REM  ۲٫۷٫۱ با آن‌ها آزموده شده است (requirements.lock.txt).
REM
REM  استفاده:  setup_env.bat
REM  بعد از آن: venv\Scripts\activate  و سپس  python main.py
REM
REM =================================================================
setlocal

echo.
echo  === Crypto AI Trader 2.7.1 - آماده‌سازی محیط ===
echo.

REM --- یافتن پایتون ---
where python >nul 2>nul
if errorlevel 1 (
    echo  [خطا] پایتون در PATH پیدا نشد.
    echo  لطفاً پایتون 3.11 یا بالاتر را نصب کنید و هنگام نصب گزینه‌ی
    echo  "Add python.exe to PATH" را تیک بزنید.
    echo  دانلود: https://www.python.org/downloads/
    goto :fail
)

for /f "tokens=2" %%V in ('python -c "import sys; print('%d.%d' %% sys.version_info[:2])"') do set PYVER=%%V
echo  پایتون شناسایی‌شده: %PYVER%

python -c "import sys; sys.exit(0 if sys.version_info>=(3,11) else 1)"
if errorlevel 1 (
    echo  [خطا] پایتون %PYVER% خیلی قدیمی است؛ نسخه‌ی 3.11 یا بالاتر لازم است.
    goto :fail
)

REM --- ساخت محیط مجازی ---
if exist venv (
    echo  پوشه‌ی venv از قبل وجود دارد؛ حذف و ساخت دوباره...
    rmdir /s /q venv
)
echo  در حال ساخت محیط مجازی...
python -m venv venv
if errorlevel 1 goto :fail

echo  در حال به‌روزرسانی pip...
venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :fail

REM --- نصبِ وابستگی‌ها با نسخه‌های قفل‌شده ---
if exist requirements.lock.txt (
    echo  نصب با نسخه‌های قفل‌شده (requirements.lock.txt)...
    venv\Scripts\python.exe -m pip install -r requirements.lock.txt
) else (
    echo  فایل قفل پیدا نشد؛ نصب با requirements.txt...
    venv\Scripts\python.exe -m pip install -r requirements.txt
)
if errorlevel 1 goto :fail

echo.
echo  === محیط آماده است ===
echo.
echo  برای اجرا:
echo      venv\Scripts\activate
echo      python main.py
echo.
echo  بررسی سلامت بدون باز کردن پنجره:
echo      venv\Scripts\python.exe main.py --check
echo.
echo  تولید یک سیگنال در خط فرمان:
echo      venv\Scripts\python.exe main.py --signal BTC/USDT
echo.
goto :end

:fail
echo.
echo  === آماده‌سازی ناموفق بود ===
echo  اگر هنگام نصب PySide6 خطا گرفتید، اینترنت/VPN را بررسی کنید
echo  و دوباره اجرا کنید. لاگِ کامل در بالا آمده است.
exit /b 1

:end
endlocal
