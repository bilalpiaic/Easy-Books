@echo off
REM Easy-Books - one-click install & run (Windows). Double-click this file.
REM It auto-installs uv (+Python) and a local Node if needed, builds, and launches
REM the app at http://127.0.0.1:3000. First run downloads dependencies.
title Easy-Books
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-and-run.ps1" %*
echo.
echo Easy-Books has stopped. Press any key to close this window.
pause >nul
