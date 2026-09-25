@echo off
chcp 65001 >nul 2>&1
REM ======================================================================
REM  ساخت نسخه اجرايي ويندوز - Crypto AI Trader
REM
REM  نسخه 2.5.3: همان ربات build_installer اجرا مي شود (خروجي زنده، گزارش
REM  در build_logs، بدون باز كردن پنجره هاي آزمون). اگر Inno Setup نصب
REM  نباشد فقط فايل اجرايي ساخته مي شود:
REM      dist\CryptoAITrader\CryptoAITrader.exe
REM ======================================================================
call "%~dp0build_installer.bat" %*
exit /b %ERRORLEVEL%
