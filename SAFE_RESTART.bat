@echo off
chcp 65001 >nul
echo ========================================
echo    БЕЗОПАСНЫЙ ПЕРЕЗАПУСК СЕРВЕРА
echo ========================================
echo.

echo [1/3] Останавливаем все процессы Python...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 >nul

echo [2/3] Проверяем, что процессы остановлены...
tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /I "python.exe" >nul
if %ERRORLEVEL% EQU 0 (
    echo [WARN] Процессы Python ещё работают! Повторная попытка...
    taskkill /F /IM python.exe /T >nul 2>&1
    timeout /t 2 >nul
)

echo [3/3] Запускаем сервер...
echo.

setlocal
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY=%~dp0.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

start "mTrade Server" "%PY%" "%~dp0mTrade.py"

echo.
echo ========================================
echo    Сервер запущен!
echo ========================================
echo.
timeout /t 3

exit
