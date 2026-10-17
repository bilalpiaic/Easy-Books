@echo off
setlocal
title Easy-Books - Deactivate License
REM Field / staff: remove the signed license from this client PC.
REM Double-click from the Easy-Books docs folder. Deletes
REM %USERPROFILE%\.easy-books\.easy-books-license (or %EB_DATA_DIR%).
REM Type DEACTIVATE to confirm. Books and source are not deleted.

echo ============================================================
echo             EASY BOOKS - DEACTIVATE LICENSE
echo ============================================================
echo.
echo This removes the signed license from THIS PC.
echo Your source folder and books are not deleted.
echo If the 15-day trial has already ended, the copy will lock again.
echo.

set "REPO_ROOT=%~dp0.."
pushd "%REPO_ROOT%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot open the Easy-Books folder above this script.
    echo         Keep Deactivate_License.bat in the docs folder of the install.
    echo.
    pause
    exit /b 1
)
set "REPO_ROOT=%CD%"
popd

if not exist "%REPO_ROOT%\backend\scripts\deactivate_license.py" (
    echo [ERROR] backend\scripts\deactivate_license.py not found.
    echo         This .bat must live in ^<Easy-Books^>\docs\
    echo         Current folder: %~dp0
    echo.
    pause
    exit /b 1
)

set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"

if exist "%REPO_ROOT%\.easy-books-portable" (
    if not defined EB_DATA_DIR set "EB_DATA_DIR=%REPO_ROOT%\data"
)
if not defined EB_DATA_DIR set "EB_DATA_DIR=%USERPROFILE%\.easy-books"

set "CONFIRM="
set /p CONFIRM=Type DEACTIVATE to continue: 
if not "%CONFIRM%"=="DEACTIVATE" (
    echo.
    echo [ERROR] Not deactivated (type DEACTIVATE exactly).
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
call uv run python -m scripts.deactivate_license --yes %*
goto AFTER_RUN

:RUN_VENV
call ".venv\Scripts\python.exe" -m scripts.deactivate_license --yes %*
goto AFTER_RUN

:RUN_PY
call python -m scripts.deactivate_license --yes %*

:AFTER_RUN
set "DEACT_RC=%ERRORLEVEL%"
echo.
if not "%DEACT_RC%"=="0" (
    echo [ERROR] License was not deactivated.
    echo.
    pause
    exit /b 1
)

echo Restart Easy-Books. If the trial has ended you will see Trial ended.
echo.
pause
endlocal
exit /b 0
