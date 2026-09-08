@echo off
REM Easy-Books - rebuild and pack the catalog advertisement explorer.
REM Double-click this file from the project folder.
REM Required files live under docs\marketing and frontend\public\catalog.
title Easy-Books Catalog Ad
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ship-catalog-ad.ps1" %*
echo.
echo Catalog ad ship finished. Press any key to close.
pause >nul
