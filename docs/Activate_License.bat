@echo off
setlocal
title Easy-Books - Activate License
REM Field tool: activate a signed Easy-Books install license.
REM Paste the EB1. token issued by Easy-Books. The private signing seed is
REM NOT in this file. Double-click this file from the Easy-Books docs folder.
REM Writes %USERPROFILE%\.easy-books\.easy-books-license (or %EB_DATA_DIR%).
REM Source folder and books are never deleted.

echo ============================================================
echo              EASY BOOKS - ACTIVATE LICENSE
echo ============================================================
echo.
echo This unlocks this installation with a signed license token.
echo Stop Easy-Books first. Your source folder and books are not deleted.
echo.

set "REPO_ROOT=%~dp0.."
pushd "%REPO_ROOT%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot open the Easy-Books folder above this script.
    echo         Keep Activate_License.bat in the docs folder of the install.
    echo.
    pause
    exit /b 1
)
set "REPO_ROOT=%CD%"
popd

if not exist "%REPO_ROOT%\backend\scripts\activate_license.py" (
    echo [ERROR] backend\scripts\activate_license.py not found.
    echo         This .bat must live in ^<Easy-Books^>\docs\
    echo         Current folder: %~dp0
    echo.
    pause
    exit /b 1
)

REM uv is installed to %%USERPROFILE%%\.local\bin by install-and-run.bat
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"

REM Same data dir as install-and-run.bat. Without this, Python defaults to
REM backend\ and the running copy (%%USERPROFILE%%\.easy-books) stays locked.
if exist "%REPO_ROOT%\.easy-books-portable" (
    if not defined EB_DATA_DIR set "EB_DATA_DIR=%REPO_ROOT%\data"
)
if not defined EB_DATA_DIR set "EB_DATA_DIR=%USERPROFILE%\.easy-books"

echo Paste the license token ^(EB1.…^):
echo.

set "EB_LICENSE_TOKEN="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $t = Read-Host 'License token'; if ([string]::IsNullOrEmpty($t)) { exit 2 }; [Console]::Out.Write($t)"`) do set "EB_LICENSE_TOKEN=%%P"

if not defined EB_LICENSE_TOKEN (
    echo.
    echo [ERROR] License token is required.
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
call uv run python -m scripts.activate_license %*
goto AFTER_RUN

:RUN_VENV
call ".venv\Scripts\python.exe" -m scripts.activate_license %*
goto AFTER_RUN

:RUN_PY
call python -m scripts.activate_license %*

:AFTER_RUN
set "ACTIVATE_RC=%ERRORLEVEL%"
set "EB_LICENSE_TOKEN="
echo.
if not "%ACTIVATE_RC%"=="0" (
    echo [ERROR] License was not activated. Check the token and that
    echo         Easy-Books is installed ^(uv / Python in backend^).
    echo.
    pause
    exit /b 1
)

echo Restart Easy-Books ^(install-and-run.bat or the desktop app^)
echo for the license to take effect.
echo.
pause
endlocal
exit /b 0
