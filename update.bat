@echo off
REM Easy-Books - update to the latest version. Double-click this file.
title Easy-Books Update
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1" %*
echo.
echo Update finished. Press any key to close.
pause >nul
