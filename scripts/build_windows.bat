@echo off
REM ======================================================================
REM  ساخت نسخه اجرایی ویندوز — Crypto AI Trader
REM
REM  پیش‌نیاز: پایتون ۳٫۱۲ یا بالاتر روی PATH
REM  خروجی   : dist\CryptoAITrader\CryptoAITrader.exe
REM ======================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

echo.
echo [1/5] بررسی نسخه پایتون...
python --version >nul 2>&1
if errorlevel 1 (
    echo    خطا: پایتون پیدا نشد. آن را از python.org نصب کنید و گزینه Add to PATH را بزنید.
    exit /b 1
)

echo [2/5] ساخت محیط مجازی...
if not exist ".venv" (
    python -m venv .venv
    if errorlevel 1 exit /b 1
)
call .venv\Scripts\activate.bat

echo [3/5] نصب وابستگی‌ها...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo    خطا در نصب وابستگی‌ها.
    exit /b 1
)

echo [4/5] اجرای آزمون‌ها...
python -m pytest tests -q
if errorlevel 1 (
    echo    آزمون‌ها شکست خوردند — ساخت متوقف شد.
    echo    برای رد شدن از آزمون‌ها متغیر SKIP_TESTS=1 را تنظیم کنید.
    if not "%SKIP_TESTS%"=="1" exit /b 1
)

echo [5/5] بسته‌بندی با PyInstaller...
if exist "build" rmdir /s /q build
if exist "dist"  rmdir /s /q dist
python -m PyInstaller CryptoAITrader.spec --noconfirm --clean
if errorlevel 1 (
    echo    بسته‌بندی شکست خورد.
    exit /b 1
)

echo.
echo ساخت با موفقیت انجام شد:
echo    %CD%\dist\CryptoAITrader\CryptoAITrader.exe
echo.
endlocal
