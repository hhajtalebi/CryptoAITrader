@echo off
chcp 65001 >nul 2>&1
REM ======================================================================
REM   ربات ساخت APK - Crypto AI Trader Mobile
REM
REM   خروجي:  dist\apk\cryptoaitrader-<version>-debug.apk
REM
REM   نكته مهم:
REM     buildozer روي خود ويندوز اجرا نمي شود. اين اسكريپت فرمان را
REM     داخل WSL اجرا مي كند. اگر WSL نداريد، در PowerShell با دسترسي
REM     مدير اجرا كنيد:   wsl --install -d Ubuntu
REM
REM   اولين ساخت 40 تا 90 دقيقه طول مي كشد (دانلود NDK و SDK).
REM   ساخت هاي بعدي چند دقيقه اند.
REM
REM   نسخه 2.5.3: ساخت روي فايل سيستم لينوكس (~/cryptoaitrader-apk)،
REM   خروجي زنده و گزارش كامل در build_logs. اين فايل عمدا بدون BOM است.
REM ======================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

echo.
echo ======================================================================
echo   Crypto AI Trader - ساخت فايل APK
echo ======================================================================
echo.

set "PY_CMD="
REM  نسخه 2.5.3: پايتون محيط مجازي پروژه (numpy/pandas/pytest دارد) مقدم است.
if exist ".venv\Scripts\python.exe" set "PY_CMD=.venv\Scripts\python.exe"
if not defined PY_CMD (
    py -3 --version >nul 2>&1 && set "PY_CMD=py -3"
)
if not defined PY_CMD (
    python --version >nul 2>&1 && set "PY_CMD=python"
)
if not defined PY_CMD (
    echo [خطا] پايتون پيدا نشد. از python.org نصب كنيد.
    goto :fail
)

echo [1/2] بررسي WSL ...
wsl --status >nul 2>&1
if errorlevel 1 (
    echo.
    echo [خطا] WSL در دسترس نيست.
    echo.
    echo   buildozer روي خود ويندوز كار نمي كند. در PowerShell با
    echo   دسترسي مدير اين را اجرا كنيد و سپس ويندوز را ري استارت كنيد:
    echo.
    echo       wsl --install -d Ubuntu
    echo.
    echo   بعد از آن، يك بار داخل WSL اين ها را نصب كنيد:
    echo.
    echo       sudo apt update
    echo       sudo apt install -y python3-pip python3-venv openjdk-17-jdk zip unzip autoconf libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev git build-essential lld
    echo.
    echo   buildozer را خود ربات داخل WSL نصب مي كند.
    echo.
    goto :fail
)
echo       WSL موجود است.

echo [2/2] اجراي ربات ساخت APK ...
echo.
%PY_CMD% tools\build_apk.py %*
set "RESULT=%ERRORLEVEL%"

echo.
if "%RESULT%"=="0" (
    echo ======================================================================
    echo   ساخت با موفقيت تمام شد. فايل APK در پوشه:  dist\apk
    echo ======================================================================
    if exist "dist\apk" explorer "dist\apk"
) else (
    echo ======================================================================
    echo   ساخت با خطا تمام شد. پيام هاي بالا را بخوانيد.
    echo ======================================================================
)

echo.
pause
endlocal & exit /b %RESULT%

:fail
echo.
pause
endlocal & exit /b 1
