@echo off
setlocal EnableExtensions
chcp 65001 >nul

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "PYTHON_EXE=C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "DOCKER_EXE=C:\Program Files\Docker\Docker\resources\bin\docker.exe"
set "DOCKER_DESKTOP=C:\Program Files\Docker\Docker\Docker Desktop.exe"
set "SITE_PORT=4173"
set "SITE_URL=http://127.0.0.1:%SITE_PORT%/"
set "CHECK_ONLY=0"
if /I "%~1"=="--check" set "CHECK_ONLY=1"

title Site Workflow MVP Launcher
echo [1/5] Checking local project...
if not exist "%PROJECT_ROOT%\workflow.json" (
  echo ERROR: Project root is missing: %PROJECT_ROOT%
  goto :failed
)
if not exist "%PROJECT_ROOT%\artifacts\04-implementation\site\index.html" (
  echo ERROR: Generated website is missing.
  goto :failed
)
if not exist "%PYTHON_EXE%" (
  echo ERROR: Bundled Python is missing: %PYTHON_EXE%
  goto :failed
)
if not exist "%DOCKER_EXE%" (
  echo ERROR: Docker CLI is missing: %DOCKER_EXE%
  goto :failed
)

if "%CHECK_ONLY%"=="1" (
  "%PYTHON_EXE%" --version
  "%DOCKER_EXE%" --version
  echo CHECK PASSED: launcher prerequisites are available.
  exit /b 0
)

echo [2/5] Checking Docker Desktop...
"%DOCKER_EXE%" info >nul 2>&1
if errorlevel 1 (
  if not exist "%DOCKER_DESKTOP%" (
    echo ERROR: Docker Desktop is not running and its executable was not found.
    goto :failed
  )
  echo Starting Docker Desktop. This can take up to 90 seconds...
  start "" "%DOCKER_DESKTOP%"
  for /l %%I in (1,1,45) do (
    timeout /t 2 /nobreak >nul
    "%DOCKER_EXE%" info >nul 2>&1 && goto :docker_ready
  )
  echo ERROR: Docker Desktop did not become ready in time.
  goto :failed
)

:docker_ready
echo [3/5] Starting PostgreSQL and pgvector...
"%DOCKER_EXE%" compose -f "%PROJECT_ROOT%\rag\docker-compose.yml" up -d
if errorlevel 1 goto :failed

echo [4/5] Initializing the isolated RAG schema...
"%PYTHON_EXE%" -c "import psycopg" >nul 2>&1
if errorlevel 1 (
  echo Installing the local PostgreSQL driver...
  "%PYTHON_EXE%" -m pip install -r "%PROJECT_ROOT%\rag\requirements.txt"
  if errorlevel 1 goto :failed
)
pushd "%PROJECT_ROOT%"
"%PYTHON_EXE%" -m rag.cli init-db
if errorlevel 1 (
  popd
  goto :failed
)
"%PYTHON_EXE%" -m rag.cli health
if errorlevel 1 (
  popd
  goto :failed
)
popd

echo [5/5] Starting the desktop website...
set "SITE_LISTENING=False"
for /f %%P in ('powershell -NoProfile -Command "[bool](Get-NetTCPConnection -State Listen -LocalPort %SITE_PORT% -ErrorAction SilentlyContinue)"') do set "SITE_LISTENING=%%P"
if /I "%SITE_LISTENING%"=="False" (
  start "Site Workflow Website" /min "%PYTHON_EXE%" -m http.server %SITE_PORT% --bind 127.0.0.1 --directory "%PROJECT_ROOT%\artifacts\04-implementation\site"
  timeout /t 2 /nobreak >nul
) else (
  echo Port %SITE_PORT% is already listening; reusing the existing local server.
)

start "" "%SITE_URL%"
echo.
echo Startup complete: %SITE_URL%
echo PostgreSQL/pgvector: 127.0.0.1:55433
echo You may close this launcher window. The website server remains open separately.
pause
exit /b 0

:failed
echo.
echo Startup failed. Review the error above; no success result was fabricated.
pause
exit /b 1
