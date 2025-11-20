@echo off
chcp 65001 >nul
echo ========================================
echo    mTrade Server - STOP
echo ========================================
echo.

python stop.py
pause
