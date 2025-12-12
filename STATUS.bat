@echo off

chcp 65001 >nul

echo ========================================

echo    mTrade Server - STATUS

echo ========================================

echo.

setlocal
if exist "%~dp0.venv\Scripts\python.exe" (
	set "PY=%~dp0.venv\Scripts\python.exe"
) else (
	set "PY=python"
)

"%PY%" "%~dp0status.py"

pause

