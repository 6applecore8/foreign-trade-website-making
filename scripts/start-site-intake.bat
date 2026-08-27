@echo off
setlocal EnableExtensions
chcp 65001 >nul

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "PYTHON_EXE=C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "INTAKE_PORT=4180"
set "INTAKE_URL=http://127.0.0.1:%INTAKE_PORT%/"
set "HEALTH_URL=http://127.0.0.1:%INTAKE_PORT%/api/health"
set "CHECK_ONLY=0"
set "NO_PAUSE=0"
if /I "%~1"=="--check" set "CHECK_ONLY=1"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
if /I "%~2"=="--no-pause" set "NO_PAUSE=1"

title Independent Site Requirement Intake
echo [1/3] Checking the requirement intake application...
if not exist "%PROJECT_ROOT%\intake\server.py" (
  echo ERROR: Intake server is missing: %PROJECT_ROOT%\intake\server.py
  goto :failed
)
if not exist "%PROJECT_ROOT%\intake\dist\index.html" (
  echo ERROR: Intake production page is missing.
  echo Run npm run build from %PROJECT_ROOT%\intake first.
  goto :failed
)
if not exist "%PYTHON_EXE%" (
  echo ERROR: Bundled Python is missing: %PYTHON_EXE%
  goto :failed
)

"%PYTHON_EXE%" -c "import jsonschema" >nul 2>&1
if errorlevel 1 (
  if "%CHECK_ONLY%"=="1" (
    echo ERROR: Intake Python dependencies are not installed.
    echo Run: "%PYTHON_EXE%" -m pip install -r "%PROJECT_ROOT%\intake\requirements.txt"
    goto :failed
  )
  echo Installing the local Intake dependency...
  "%PYTHON_EXE%" -m pip install -r "%PROJECT_ROOT%\intake\requirements.txt"
  if errorlevel 1 goto :failed
)

if "%CHECK_ONLY%"=="1" (
  "%PYTHON_EXE%" --version
  "%PYTHON_EXE%" "%PROJECT_ROOT%\intake\server.py" --help >nul
  if errorlevel 1 goto :failed
  echo CHECK PASSED: requirement intake prerequisites are available.
  exit /b 0
)

echo [2/3] Starting the local intake server...
set "INTAKE_HEALTHY=False"
for /f %%H in ('powershell -NoProfile -Command "try { $r=Invoke-RestMethod -Uri '%HEALTH_URL%' -TimeoutSec 2; [bool]($r.status -eq 'ok' -and $r.service -eq 'local-site-intake') } catch { $false }"') do set "INTAKE_HEALTHY=%%H"
if /I "%INTAKE_HEALTHY%"=="True" goto :open_intake

set "PORT_LISTENING=False"
for /f %%P in ('powershell -NoProfile -Command "[bool](Get-NetTCPConnection -State Listen -LocalPort %INTAKE_PORT% -ErrorAction SilentlyContinue)"') do set "PORT_LISTENING=%%P"
if /I "%PORT_LISTENING%"=="True" (
  echo ERROR: Port %INTAKE_PORT% is occupied by another service.
  goto :failed
)

start "Site Requirement Intake" /min "%PYTHON_EXE%" "%PROJECT_ROOT%\intake\server.py" --port %INTAKE_PORT%
for /l %%I in (1,1,20) do (
  timeout /t 1 /nobreak >nul
  powershell -NoProfile -Command "try { $r=Invoke-RestMethod -Uri '%HEALTH_URL%' -TimeoutSec 2; if($r.status -eq 'ok' -and $r.service -eq 'local-site-intake'){exit 0}; exit 1 } catch { exit 1 }" >nul 2>&1 && goto :open_intake
)
echo ERROR: Requirement intake server did not become healthy in time.
goto :failed

:open_intake
echo [3/3] Opening the independent-site requirement page...
start "" "%INTAKE_URL%"
echo.
echo Requirement intake is ready: %INTAKE_URL%
echo Submitted requests are appended under intake\requests\ and do not overwrite active config.
echo You may close this launcher window. The intake server remains open separately.
if "%NO_PAUSE%"=="0" pause
exit /b 0

:failed
echo.
echo Startup failed. Review the error above.
if "%NO_PAUSE%"=="0" pause
exit /b 1
