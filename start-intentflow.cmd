@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "SETUP_ARGS=-AllowEnvironmentRepair -AllowDependencyInstall -AllowWebBuild -AllowRepositoryPathRepair -AllowStopExisting"

rem Check-only mode must remain read-only, so it skips automatic setup.
for %%A in (%*) do (
    if /I "%%~A"=="-CheckOnly" set "SETUP_ARGS="
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-intentflow.ps1" %SETUP_ARGS% %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo IntentFlow startup failed with exit code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
