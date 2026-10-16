@echo off
setlocal
title Easy-Books - Issue License (staff)
REM STAFF ONLY — generate an EB1 license token for one client.
REM Run this on the field-staff laptop / office checkout, NOT on the client's
REM Easy-Books folder. The signing seed is NOT stored in this file.
REM Repeat for any other client with that client's install ID + owner email.

echo ============================================================
echo              EASY BOOKS - ISSUE LICENSE (staff)
echo ============================================================
echo.
echo Generate a token on THIS machine for one client.
echo Do not run this inside a customer's Easy-Books copy.
echo You need that client's Install ID (UUID) and owner email.
echo.

set "REPO_ROOT=%~dp0.."
pushd "%REPO_ROOT%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot open the Easy-Books folder above this script.
    echo         Keep Issue_License.bat in staff's docs folder.
    echo.
    pause
    exit /b 1
)
set "REPO_ROOT=%CD%"
popd

if not exist "%REPO_ROOT%\backend\scripts\issue_license.py" (
    echo [ERROR] backend\scripts\issue_license.py not found.
    echo         This .bat must live in staff's ^<Easy-Books^>\docs\
    echo         Current folder: %~dp0
    echo.
    pause
    exit /b 1
)

set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"

if not defined EB_LICENSE_SIGNING_SEED (
    echo [ERROR] Set EB_LICENSE_SIGNING_SEED on this staff machine first.
    echo         The seed is not stored in this script.
    echo.
    pause
    exit /b 1
)

set "INSTALL_ID="
set "OWNER_EMAIL="
set /p INSTALL_ID=Client install ID (UUID from their lock screen): 
set /p OWNER_EMAIL=Owner email on that install: 

if not defined INSTALL_ID (
    echo.
    echo [ERROR] Install ID and owner email are required.
    echo.
    pause
    exit /b 1
)
if not defined OWNER_EMAIL (
    echo.
    echo [ERROR] Install ID and owner email are required.
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
call uv run python -m scripts.issue_license --install-id "%INSTALL_ID%" --email "%OWNER_EMAIL%" %*
goto AFTER_RUN

:RUN_VENV
call ".venv\Scripts\python.exe" -m scripts.issue_license --install-id "%INSTALL_ID%" --email "%OWNER_EMAIL%" %*
goto AFTER_RUN

:RUN_PY
call python -m scripts.issue_license --install-id "%INSTALL_ID%" --email "%OWNER_EMAIL%" %*

:AFTER_RUN
set "ISSUE_RC=%ERRORLEVEL%"
echo.
if not "%ISSUE_RC%"=="0" (
    echo [ERROR] Token was not issued. Check the seed, install ID, and email.
    echo.
    pause
    exit /b 1
)

echo Send that EB1. line to the client (or paste it on their lock screen).
echo It only unlocks the install ID you typed. Repeat for the next client.
echo.
pause
endlocal
exit /b 0
