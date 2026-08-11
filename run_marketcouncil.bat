@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"

set "MARKETCOUNCIL_PYTHON=%~dp0venv\Scripts\python.exe"
if not exist "%MARKETCOUNCIL_PYTHON%" (
    echo [ERROR] Python virtual environment was not found.
    echo Expected: %MARKETCOUNCIL_PYTHON%
    goto :failed
)

echo Starting MarketCouncil and its Docker services...
echo.
"%MARKETCOUNCIL_PYTHON%" -m app.debate_main %*
if errorlevel 1 goto :failed

popd
endlocal
exit /b 0

:failed
echo.
echo MarketCouncil could not be started.
if /I "%~1"=="--check" goto :failed_no_pause
pause
:failed_no_pause
popd
endlocal
exit /b 1
