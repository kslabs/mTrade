@echo off
echo =====================================================
echo    ПЕРЕЗАПУСК СЕРВЕРА С НОВЫМИ ИСПРАВЛЕНИЯМИ
echo =====================================================
echo.
echo [1/3] Останавливаем все процессы Python...
taskkill /F /IM python.exe 2>nul
if %errorlevel% equ 0 (
    echo     ✓ Процессы Python остановлены
) else (
    echo     ℹ Процессы Python не найдены
)
echo.

echo [2/3] Ожидание 3 секунды...
timeout /t 3 /nobreak >nul
echo     ✓ Ожидание завершено
echo.

echo [3/3] Запускаем сервер...
echo     → Запуск start_server.bat
echo.
call start_server.bat
echo.

echo =====================================================
echo    ✅ СЕРВЕР ПЕРЕЗАПУЩЕН!
echo =====================================================
echo.
echo Проверьте логи:
echo   Get-Content autotrader.log -Tail 50 -Wait
echo.
echo Откройте веб-интерфейс и протестируйте:
echo   1. Quick Trade → Buy
echo   2. Проверьте баланс
echo   3. Проверьте логи на дубли
echo.
pause
