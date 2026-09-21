@echo off
chcp 65001 >nul
title Crypto AI Trader
cd /d "%~dp0"

echo ================================================
echo   Crypto AI Trader - راه اندازی
echo ================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [خطا] پایتون روی این سیستم پیدا نشد.
    echo.
    echo لطفا پایتون 3.11 یا بالاتر را از نشانی زیر نصب کنید:
    echo     https://www.python.org/downloads/
    echo.
    echo هنگام نصب حتما گزینه "Add python.exe to PATH" را تیک بزنید.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo نسخه پایتون: %PYVER%
echo.

if not exist ".venv\Scripts\python.exe" (
    echo محیط مجازی ساخته می شود ...
    python -m venv .venv
    if errorlevel 1 (
        echo [خطا] ساخت محیط مجازی ناموفق بود.
        pause
        exit /b 1
    )
    echo.
    echo نصب بسته ها - بار اول چند دقیقه طول می کشد ...
    echo.
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [خطا] نصب بسته ها ناموفق بود. اتصال اینترنت را بررسی کنید.
        pause
        exit /b 1
    )
    echo.
    echo نصب کامل شد.
    echo.
)

echo برنامه اجرا می شود ...
echo.
".venv\Scripts\python.exe" main.py %*

if errorlevel 1 (
    echo.
    echo [خطا] برنامه با خطا بسته شد. متن بالا را برای پشتیبانی بفرستید.
    pause
    exit /b 1
)
