@echo off
setlocal
title Easy-Books - Force Expire Trial
REM QA / staff: force-expire the standalone trial clock.
REM Double-click from the Easy-Books docs folder. Charges
REM %USERPROFILE%\.easy-books (or %EB_DATA_DIR%), never backend\.
REM Type EXPIRE to confirm. Books and source are not deleted.

echo ============================================================
echo              EASY BOOKS - FORCE EXPIRE TRIAL
echo ============================================================
echo.
echo This locks the copy as if the 15-day trial had already ended.
echo Your source folder and books are not deleted.
echo If a license file is present the copy stays unlocked.
echo.

set "REPO_ROOT=%~dp0.."
pushd "%REPO_ROOT%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot open the Easy-Books folder above this script.
    echo         Keep Expire_Trial.bat in the docs folder of the install.
    echo.
    pause
    exit /b 1
)
set "REPO_ROOT=%CD%"
popd

if not exist "%REPO_ROOT%\backend\scripts\expire_trial.py" (
    echo [ERROR] backend\scripts\expire_trial.py not found.
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
set /p CONFIRM=Type EXPIRE to continue: 
if not "%CONFIRM%"=="EXPIRE" (
    echo.
    echo [ERROR] Not expired (type EXPIRE exactly).
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
call uv run python -m scripts.expire_trial --yes %*
goto AFTER_RUN

:RUN_VENV
call ".venv\Scripts\python.exe" -m scripts.expire_trial --yes %*
goto AFTER_RUN

:RUN_PY
call python -m scripts.expire_trial --yes %*

:AFTER_RUN
set "EXPIRE_RC=%ERRORLEVEL%"
echo.
if not "%EXPIRE_RC%"=="0" (
    echo [ERROR] Trial was not force-expired.
    echo.
    pause
    exit /b 1
)

echo Refresh the login page (or restart Easy-Books) to see Trial ended.
echo.
pause
endlocal
exit /b 0
