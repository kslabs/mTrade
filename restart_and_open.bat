@echo off
echo ================================================
echo ПЕРЕЗАПУСК СЕРВЕРА И ОТКРЫТИЕ В ИНКОГНИТО
echo ================================================
echo.

echo [1/4] Останавливаем все процессы Python...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2/4] Очищаем кэш Flask...
if exist "__pycache__" rmdir /s /q "__pycache__" 2>nul
if exist "templates\__pycache__" rmdir /s /q "templates\__pycache__" 2>nul
if exist "static\__pycache__" rmdir /s /q "static\__pycache__" 2>nul

echo [3/4] Запускаем сервер...
start "mTrade Server" python mTrade.py
timeout /t 3 /nobreak >nul

echo [4/4] Открываем в режиме инкогнито Chrome...
timeout /t 2 /nobreak >nul

REM Попробуем найти Chrome
set CHROME=""
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set CHROME="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set CHROME="%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

if not %CHROME%=="" (
    echo Запускаем Chrome в режиме инкогнито...
    start "" %CHROME% --incognito http://localhost:5000
) else (
    echo Chrome не найден, попробуем Edge...
    start msedge --inprivate http://localhost:5000 2>nul
    if errorlevel 1 (
        echo Открываем в браузере по умолчанию...
        start http://localhost:5000
    )
)

echo.
echo ================================================
echo ГОТОВО!
echo ================================================
echo.
echo Сервер запущен, браузер открыт.
echo Если кнопка всё равно не видна:
echo   1. Нажмите F12 (DevTools)
echo   2. ПКМ на значке обновления
echo   3. "Empty Cache and Hard Reload"
echo.
pause
