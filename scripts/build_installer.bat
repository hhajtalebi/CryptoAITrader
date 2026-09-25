@echo off
chcp 65001 >nul 2>&1
REM ======================================================================
REM   ربات ساخت فایل نصبی ویندوز - Crypto AI Trader
REM
REM   خروجی:  dist\installer\CryptoAITrader-Setup-<version>.exe
REM
REM   پیش نیازها:
REM     * Python 3.11+  (هنگام نصب "Add Python to PATH" را بزنید)
REM     * Inno Setup 6  (https://jrsoftware.org/isdl.php)
REM
REM   آزمون هاي كامل پيش فرض اجرا نمي شوند (فقط بررسي سلامت بدون پنجره).
REM   اجراي آزمون هاي كامل (بي پنجره):  scripts\build_installer.bat --with-tests
REM   نكته: اين فايل عمدا بدون BOM ذخيره شده؛ BOM باعث مي شد @echo off اجرا نشود.
REM ======================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

echo.
echo ======================================================================
echo   Crypto AI Trader - ساخت فايل نصبي
echo ======================================================================
echo.

REM --- 1) پيدا كردن پايتون -------------------------------------------
REM  "python" روي ويندوز ممكن است ميانبر فروشگاه مايكروسافت باشد كه
REM  بي صدا خارج مي شود. پس "py" را اول امتحان مي كنيم.
set "PY_CMD="
py -3 --version >nul 2>&1 && set "PY_CMD=py -3"
if not defined PY_CMD (
    python --version >nul 2>&1 && set "PY_CMD=python"
)
if not defined PY_CMD (
    echo [خطا] پايتون پيدا نشد.
    echo.
    echo   از python.org نسخه 3.11 يا بالاتر را نصب كنيد و هنگام نصب
    echo   گزينه "Add Python to PATH" را حتما تيك بزنيد.
    echo.
    goto :fail
)
echo [1/3] پايتون: %PY_CMD%
%PY_CMD% --version

REM --- 2) محيط مجازي ---------------------------------------------------
REM  نكته مهم: اگر ساخت venv نيمه كاره رها شده باشد، پوشه .venv هست ولي
REM  activate.bat نيست. شرط "if not exist .venv" آن را سالم مي پنداشت و
REM  call روي فايل ناموجود، كل اسكريپت را بي صدا مي بست.
if not exist ".venv\Scripts\activate.bat" (
    echo [2/3] ساخت محيط مجازي ...
    if exist ".venv" rmdir /s /q ".venv"
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [خطا] ساخت محيط مجازي شكست خورد.
        goto :fail
    )
) else (
    echo [2/3] محيط مجازي موجود است.
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [خطا] فعال سازي محيط مجازي شكست خورد.
    goto :fail
)

REM --- 3) اجراي ربات ---------------------------------------------------
echo [3/3] اجراي ربات ساخت ...
echo.
".venv\Scripts\python.exe" tools\build_installer.py %*
set "RESULT=%ERRORLEVEL%"

echo.
if "%RESULT%"=="0" (
    echo ======================================================================
    echo   ساخت با موفقيت تمام شد.
    echo   فايل نصبي در پوشه:  dist\installer
    echo ======================================================================
    if exist "dist\installer" explorer "dist\installer"
) else (
    echo ======================================================================
    echo   ساخت با خطا تمام شد. پيام هاي بالا را بخوانيد.
    echo ======================================================================
)

echo.
REM  pause حياتي است: بدون آن، وقتي كاربر روي فايل دوبار كليك مي كند
REM  پنجره بلافاصله بسته مي شود و هيچ پيام خطايي ديده نمي شود.
pause
endlocal & exit /b %RESULT%

:fail
echo.
pause
endlocal & exit /b 1
