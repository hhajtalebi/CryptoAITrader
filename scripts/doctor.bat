@echo off
chcp 65001 >nul 2>&1
REM ======================================================================
REM   عيب ياب سازنده ها - Crypto AI Trader
REM
REM   اگر سازنده اي كار نكرد، اول اين را اجرا كنيد. دقيقا مي گويد چه
REM   چيزي كم است و چطور درستش كنيد.
REM
REM   خروجي را در فايل doctor_report.txt هم ذخيره مي كند تا بتوانيد
REM   برايم بفرستيد.
REM ======================================================================
setlocal
cd /d "%~dp0.."

set "PY_CMD="
py -3 --version >nul 2>&1 && set "PY_CMD=py -3"
if not defined PY_CMD (
    python --version >nul 2>&1 && set "PY_CMD=python"
)
if not defined PY_CMD (
    echo.
    echo [خطا] پايتون پيدا نشد.
    echo   از python.org نسخه 3.11 يا بالاتر را نصب كنيد و هنگام نصب
    echo   گزينه "Add Python to PATH" را تيك بزنيد.
    echo.
    pause
    exit /b 1
)

%PY_CMD% tools\build_doctor.py
set "RESULT=%ERRORLEVEL%"

%PY_CMD% tools\build_doctor.py > doctor_report.txt 2>&1
echo.
echo گزارش در فايل doctor_report.txt ذخيره شد.
echo اين فايل را برايم بفرستيد تا دقيقا بدانم چه شده.
echo.
pause
endlocal & exit /b %RESULT%
