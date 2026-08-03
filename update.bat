@echo off
REM Easy-Books - update to the latest version. Double-click this file.
REM Always refresh update.ps1 from origin first so a broken/old local copy
REM cannot block the update (Windows PowerShell UTF-8 em-dash parse bug).
title Easy-Books Update
cd /d "%~dp0"

if exist ".git" (
  echo Fetching latest updater script...
  git fetch --quiet origin 2>nul
  if not errorlevel 1 (
    git checkout origin/main -- update.ps1 2>nul
    git checkout origin/main -- install-and-run.ps1 2>nul
  )
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1" %*
echo.
echo Update finished. Press any key to close.
pause >nul
