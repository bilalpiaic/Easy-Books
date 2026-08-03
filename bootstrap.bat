@echo off
REM Easy-Books bootstrap (Windows) - double-click this file on a PC with nothing
REM installed. It fetches the latest bootstrap and runs it: clones the repo to
REM %USERPROFILE%\Easy-Books, installs uv/Python + a local Node if needed,
REM builds, and launches the app at http://127.0.0.1:3000.
title Easy-Books Setup
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/bilalpiaic/Easy-Books/main/bootstrap.ps1 | iex"
echo.
echo Easy-Books setup finished. Press any key to close.
pause >nul
