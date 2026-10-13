@echo off
setlocal
title Easy-Books - Extend Trial
REM Field tool: grant another 15-day standalone trial window.
REM The password is NOT stored in this file. It is checked (SHA-256) by
REM backend\scripts\extend_trial.py. Double-click this file from the
REM Easy-Books docs folder, or run it from an already-installed checkout.
REM Source folder and %USERPROFILE%\.easy-books books are never deleted.

echo ============================================================
echo              EASY BOOKS - EXTEND TRIAL (15 days)
echo ============================================================
echo.
echo This restarts the trial clock from today. Stop Easy-Books first.
echo Your source folder and books are not deleted.
echo A field password is required (typing is hidden).
echo.

set "REPO_ROOT=%~dp0.."
pushd "%REPO_ROOT%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot open the Easy-Books folder above this script.
    echo         Keep Extend_Trial.bat in the docs folder of the install.
    echo.
    pause
    exit /b 1
)
set "REPO_ROOT=%CD%"
popd

if not exist "%REPO_ROOT%\backend\scripts\extend_trial.py" (
    echo [ERROR] backend\scripts\extend_trial.py not found.
    echo         This .bat must live in ^<Easy-Books^>\docs\
    echo         Current folder: %~dp0
    echo.
    pause
    exit /b 1
)

REM uv is installed to %%USERPROFILE%%\.local\bin by install-and-run.bat
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"

echo Enter the extend-trial password:
echo.

set "EB_EXTEND_TRIAL_PASSWORD="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $p = Read-Host 'Password' -AsSecureString; $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($p); $t = [Runtime.InteropServices.Marshal]::PtrToStringAuto($b); [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b); if ([string]::IsNullOrEmpty($t)) { exit 2 }; [Console]::Out.Write($t)"`) do set "EB_EXTEND_TRIAL_PASSWORD=%%P"

if not defined EB_EXTEND_TRIAL_PASSWORD (
    echo.
    echo [ERROR] Password is required.
    echo.
    pause
    exit /b 1
)

cd /d "%REPO_ROOT%\backend" || (
    echo [ERROR] Cannot open "%REPO_ROOT%\backend".
    pause
    exit /b 1
)
set "PYTHONPATH=."

where uv >nul 2>&1
if %errorlevel% equ 0 goto RUN_UV
if exist ".venv\Scripts\python.exe" goto RUN_VENV
goto RUN_PY

:RUN_UV
call uv run python -m scripts.extend_trial %*
goto AFTER_RUN

:RUN_VENV
call ".venv\Scripts\python.exe" -m scripts.extend_trial %*
goto AFTER_RUN

:RUN_PY
call python -m scripts.extend_trial %*

:AFTER_RUN
set "EXTEND_RC=%ERRORLEVEL%"
set "EB_EXTEND_TRIAL_PASSWORD="
echo.
if not "%EXTEND_RC%"=="0" (
    echo [ERROR] Trial was not extended. Check the password and that
    echo         Easy-Books is installed ^(uv / Python in backend^).
    echo.
    pause
    exit /b 1
)

echo Restart Easy-Books ^(install-and-run.bat or the desktop app^)
echo for the new 15-day window to take effect.
echo.
pause
endlocal
exit /b 0
