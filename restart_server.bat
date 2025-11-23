@echo off
chcp 65001 > nul
echo ================================================
echo ПЕРЕЗАПУСК СЕРВЕРА mTrade
echo ================================================
echo.

echo [1/3] Останавливаем все процессы Python...
taskkill /F /IM python.exe /T 2>nul
if %errorlevel% == 0 (
    echo ✓ Процессы остановлены
    timeout /t 2 /nobreak > nul
) else (
    echo ℹ Процессы не найдены или уже остановлены
)
echo.

echo [2/3] Очищаем кэш Python...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
echo ✓ Кэш очищен
echo.

echo [3/3] Запускаем сервер...
echo.
echo ================================================
echo СЕРВЕР ЗАПУЩЕН
echo ================================================
echo Откройте браузер: http://localhost:5000
echo Для остановки: Ctrl+C
echo ================================================
echo.

python mTrade.py

pause
