@echo off
setlocal
pushd "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment was not found.
    echo Expected: %~dp0venv\Scripts\python.exe
    pause
    exit /b 1
)

"venv\Scripts\python.exe" -m streamlit run "app\document_review.py"

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start the report review app.
    pause
)

popd
endlocal
