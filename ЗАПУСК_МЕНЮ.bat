@echo off
cd /d "%~dp0"
if exist "%~dp0Unfit-Zapret.exe" (
    start "" "%~dp0Unfit-Zapret.exe"
    goto :eof
)
where pythonw >nul 2>&1
if %errorlevel% EQU 0 (
    start "" pythonw "%~dp0zapret_manager.py"
    goto :eof
)
python "%~dp0zapret_manager.py"
if %errorlevel% NEQ 0 (
    echo.
    echo [ERROR] No exe and no Python found!
    pause
)
