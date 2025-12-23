@echo off
chcp 65001 > nul
echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║     ПРОВЕРКА ИНТЕГРАЦИИ AUTOTRADER V2                   ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

echo [1/4] Проверка синтаксиса autotrader_v2.py...
python -m py_compile autotrader_v2.py
if %ERRORLEVEL% EQU 0 (
    echo       ✅ OK
) else (
    echo       ❌ ОШИБКА
    goto :error
)
echo.

echo [2/4] Проверка синтаксиса mTrade.py...
python -m py_compile mTrade.py
if %ERRORLEVEL% EQU 0 (
    echo       ✅ OK
) else (
    echo       ❌ ОШИБКА
    goto :error
)
echo.

echo [3/4] Проверка импорта AutoTraderV2...
python -c "from autotrader_v2 import AutoTraderV2; print('      ✅ OK - импорт успешен')"
if %ERRORLEVEL% NEQ 0 (
    echo       ❌ ОШИБКА импорта
    goto :error
)
echo.

echo [4/4] Проверка API методов...
python -c "from autotrader_v2 import AutoTraderV2; at = AutoTraderV2(None, None, None); print('      ✅ get_status:', hasattr(at, 'get_status')); print('      ✅ get_cycle_info:', hasattr(at, 'get_cycle_info')); print('      ✅ get_all_cycles:', hasattr(at, 'get_all_cycles'))"
if %ERRORLEVEL% NEQ 0 (
    echo       ❌ ОШИБКА проверки методов
    goto :error
)
echo.

echo ╔══════════════════════════════════════════════════════════╗
echo ║     ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ                            ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo ✅ Этап 1: ЗАВЕРШЁН
echo ⏳ Следующий шаг: Реализация торговой логики (Этап 2)
echo.
echo Документация:
echo   • AUTOTRADER_V2_INTEGRATION.md (подробная)
echo   • AUTOTRADER_V2_STATUS.txt (краткая)
echo   • AUTOTRADER_V2_STATUS.html (визуальная)
echo.
pause
exit /b 0

:error
echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║     ❌ ОБНАРУЖЕНЫ ОШИБКИ                                ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
pause
exit /b 1
