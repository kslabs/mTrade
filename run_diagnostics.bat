@echo off
chcp 65001 >nul
echo ============================================================
echo  ДИАГНОСТИКА СИСТЕМЫ bGate.mTrade
echo ============================================================
echo.

echo [1/4] Проверка API параметров...
python test_params_loading.py
echo.

echo [2/4] Проверка HTML и элементов формы...
python diagnose_params_page.py
echo.

echo [3/4] Проверка кнопки старта цикла...
python test_start_button.py
echo.

echo [4/4] Комплексная проверка всех компонентов...
python run_all_tests.py
echo.

echo ============================================================
echo  ДИАГНОСТИКА ЗАВЕРШЕНА
echo ============================================================
echo.
echo Полезные ссылки:
echo   - Главная страница: http://127.0.0.1:5000/
echo   - Тестовая страница: http://127.0.0.1:5000/test_params
echo   - Отчёт диагностики: http://127.0.0.1:5000/diagnostic_report
echo.
echo Документация:
echo   - README_FIXES.md (основная инструкция)
echo   - DIAGNOSTIC_REPORT.md (полный отчёт)
echo   - FIXES_SUMMARY.md (краткое резюме)
echo.
pause
