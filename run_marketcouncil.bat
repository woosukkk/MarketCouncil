@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"

set "MARKETCOUNCIL_PYTHON=%~dp0venv\Scripts\python.exe"
set "MARKETCOUNCIL_DOCKER_DESKTOP=C:\Program Files\Docker\Docker\Docker Desktop.exe"
set "MARKETCOUNCIL_COMPOSE=%~dp0infra\searxng\docker-compose.yml"

if not exist "%MARKETCOUNCIL_PYTHON%" (
    echo [ERROR] Python virtual environment was not found.
    echo Expected: %MARKETCOUNCIL_PYTHON%
    goto :failed
)

where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker CLI was not found. Install Docker Desktop first.
    goto :failed
)

if not exist "%MARKETCOUNCIL_COMPOSE%" (
    echo [ERROR] SearXNG Docker configuration was not found.
    echo Expected: %MARKETCOUNCIL_COMPOSE%
    goto :failed
)

echo [1/4] Checking Docker engine...
docker info >nul 2>&1
if not errorlevel 1 goto :docker_ready

if not exist "%MARKETCOUNCIL_DOCKER_DESKTOP%" (
    echo [ERROR] Docker Desktop executable was not found.
    goto :failed
)

echo Docker Desktop is not running. Starting it now...
start "" "%MARKETCOUNCIL_DOCKER_DESKTOP%"

set /a MARKETCOUNCIL_TRIES=0
:wait_for_docker
timeout /t 2 /nobreak >nul
docker info >nul 2>&1
if not errorlevel 1 goto :docker_ready

set /a MARKETCOUNCIL_TRIES+=1
if !MARKETCOUNCIL_TRIES! LSS 60 goto :wait_for_docker

echo [ERROR] Docker engine did not become ready within 120 seconds.
goto :failed

:docker_ready
echo [2/4] Starting local SearXNG...
docker compose -f "%MARKETCOUNCIL_COMPOSE%" up -d
if errorlevel 1 (
    echo [ERROR] Failed to start the SearXNG container.
    goto :failed
)

echo [3/4] Waiting for the SearXNG search API...
set /a MARKETCOUNCIL_SEARCH_TRIES=0
:wait_for_search
curl.exe --silent --fail --max-time 2 http://127.0.0.1:8080/ >nul 2>&1
if not errorlevel 1 goto :search_ready

set /a MARKETCOUNCIL_SEARCH_TRIES+=1
if !MARKETCOUNCIL_SEARCH_TRIES! GEQ 30 (
    echo [ERROR] SearXNG did not become ready within 60 seconds.
    goto :failed
)
timeout /t 2 /nobreak >nul
goto :wait_for_search

:search_ready
if /I "%~1"=="--check" goto :check_complete

echo [4/4] Starting MarketCouncil...
echo.
"%MARKETCOUNCIL_PYTHON%" -m app.debate_main
if errorlevel 1 goto :failed

popd
endlocal
exit /b 0

:check_complete
echo [4/4] Docker and SearXNG are ready.
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
