@echo off
REM Double-click launcher for a OneDrive / Google Drive checkout.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch-cloud.ps1" %*
