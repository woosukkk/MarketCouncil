@echo off
setlocal EnableExtensions
chcp 65001 >nul
pushd "%~dp0"

set "MARKETCOUNCIL_PYTHON=%~dp0venv\Scripts\python.exe"

if not exist "%MARKETCOUNCIL_PYTHON%" (
    echo [ERROR] Python virtual environment was not found.
    echo Expected: %MARKETCOUNCIL_PYTHON%
    goto :failed
)

echo [1/2] Starting regulatory filing and report collection...
"%MARKETCOUNCIL_PYTHON%" -m app.manual_collection
if errorlevel 1 (
    echo.
    echo [WARN] One or more collection tasks failed.
    echo Opening the review app for successfully collected documents.
)

echo.
echo [2/2] Opening the document review app...
"%MARKETCOUNCIL_PYTHON%" -m streamlit run "app\document_review.py" --server.headless false
if errorlevel 1 goto :failed

popd
endlocal
exit /b 0

:failed
echo.
echo [ERROR] The manual collection workflow could not be completed.
pause
popd
endlocal
exit /b 1
