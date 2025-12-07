@echo off
echo ========================================
echo ОСТАНОВКА ВСЕХ ПРОЦЕССОВ PYTHON
echo ========================================
echo.

echo Убиваем все процессы python.exe...
taskkill /F /IM python.exe /T 2>nul

if %errorlevel% == 0 (
    echo.
    echo [OK] Все процессы Python остановлены!
) else (
    echo.
    echo [INFO] Процессы Python не найдены или уже остановлены
)

echo.
echo ========================================
echo ПРОВЕРКА
echo ========================================
echo.

timeout /t 2 /nobreak >nul

tasklist /FI "IMAGENAME eq python.exe" | find /I "python.exe"

if %errorlevel% == 0 (
    echo [WARN] Некоторые процессы Python все еще работают!
) else (
    echo [OK] Все процессы Python остановлены
)

echo.
echo Нажмите любую клавишу чтобы закрыть...
pause >nul
