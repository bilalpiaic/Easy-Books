@echo off
setlocal enabledelayedexpansion
title Easy Books - Installer
REM Easy-Books first-time Windows installer.
REM Download this file and double-click it. Installs Git if needed, clones
REM https://github.com/bilalpiaic/Easy-Books, creates a Desktop launcher,
REM then runs install-and-run.bat (uv, Node, build, alembic, launch).
REM Data lives in %USERPROFILE%\.easy-books and is never deleted.

echo ============================================================
echo                  EASY BOOKS - INSTALLER
echo ============================================================
echo.

REM ------------------------------------------------------------
REM  STEP 1 : Check if Git is installed, install it if missing
REM ------------------------------------------------------------
echo [1/5] Checking for Git...
git --version >nul 2>&1
if !errorlevel! equ 0 (
    echo        Git is already installed.
) else (
    echo        Git not found. Attempting installation...
    echo.

    REM --- Try winget first (built into modern Windows) ---
    winget --version >nul 2>&1
    if !errorlevel! equ 0 (
        echo        Installing Git via winget...
        winget install --id Git.Git -e --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity
    ) else (
        echo        winget not available. Falling back to PowerShell download...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $r=Invoke-RestMethod 'https://api.github.com/repos/git-for-windows/git/releases/latest' -Headers @{'User-Agent'='EasyBooksInstaller'}; $a=$r.assets ^| Where-Object {$_.name -match '64-bit\.exe$'} ^| Select-Object -First 1; $o=Join-Path $env:TEMP $a.name; Write-Host ('Downloading ' + $a.name); Invoke-WebRequest $a.browser_download_url -OutFile $o; Write-Host 'Installing Git silently...'; Start-Process $o -ArgumentList '/VERYSILENT','/NORESTART','/o:PathOption=Cmd' -Wait"
    )

    REM --- Make Git usable in THIS session without a restart ---
    set "PATH=%PATH%;%ProgramFiles%\Git\cmd;%ProgramFiles%\Git\bin;%LOCALAPPDATA%\Programs\Git\cmd"

    git --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo.
        echo        [ERROR] Git installation could not be verified.
        echo        Please install Git manually from:
        echo            https://git-scm.com/download/win
        echo        then run this installer again.
        echo.
        pause
        exit /b 1
    )
    echo        Git installed successfully.
)
echo.

REM ------------------------------------------------------------
REM  STEP 2 : Ask the user where to install the app
REM ------------------------------------------------------------
echo [2/5] Choose installation location
echo        The repo is cloned as Easy-Books inside this folder.
echo        Example: C:\Apps  -^>  C:\Apps\Easy-Books
echo.
:ASKDIR
set "INSTALL_DIR="
set /p "INSTALL_DIR=Enter the full folder path to install Easy Books (e.g. C:\Apps): "
if not defined INSTALL_DIR (
    echo        Path cannot be empty. Please try again.
    echo.
    goto ASKDIR
)
REM Strip surrounding quotes and any trailing backslash
set "INSTALL_DIR=%INSTALL_DIR:"=%"
if "%INSTALL_DIR:~-1%"=="\" set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"

if not exist "%INSTALL_DIR%" (
    echo        Creating folder: %INSTALL_DIR%
    mkdir "%INSTALL_DIR%"
)
cd /d "%INSTALL_DIR%" || (
    echo        [ERROR] Cannot access "%INSTALL_DIR%".
    pause
    exit /b 1
)
echo        Installing into: %INSTALL_DIR%
echo.

set "REPO_DIR=%INSTALL_DIR%\Easy-Books"

REM ------------------------------------------------------------
REM  STEP 3 : Clone the repository (or update if it exists)
REM ------------------------------------------------------------
echo [3/5] Getting Easy-Books source code...
if exist "%REPO_DIR%\.git" (
    echo        Existing copy found. Pulling latest changes...
    cd /d "%REPO_DIR%"
    REM Installer drift must not block git pull --ff-only (same list as update.ps1).
    REM Per-path: a missing file must not abort the rest of the list.
    git checkout -- backend/uv.lock 2>nul
    git checkout -- frontend/public/version.json 2>nul
    git checkout -- frontend/package-lock.json 2>nul
    git checkout -- package-lock.json 2>nul
    git checkout -- mobile/package-lock.json 2>nul
    git pull --ff-only
    if !errorlevel! neq 0 (
        echo        [ERROR] git pull --ff-only failed.
        echo        Safe reset of this code folder only (data in %%USERPROFILE%%\.easy-books is untouched):
        echo            git fetch origin
        echo            git reset --hard origin/main
        echo        then run this installer again, or double-click update.bat in the Easy-Books folder.
        pause
        exit /b 1
    )
) else (
    git clone https://github.com/bilalpiaic/Easy-Books.git
    if !errorlevel! neq 0 (
        echo        [ERROR] git clone failed.
        pause
        exit /b 1
    )
    cd /d "%REPO_DIR%"
)
echo.

REM ------------------------------------------------------------
REM  STEP 4 : Create the "Easy-Books" launcher on the Desktop
REM           (done before running, so it always gets created)
REM ------------------------------------------------------------
echo [4/5] Creating desktop launcher...
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%D"

set "LAUNCHER=%DESKTOP%\Easy-Books.bat"
(
    echo @echo off
    echo title Easy Books Launcher
    echo cd /d "%REPO_DIR%"
    echo call "%REPO_DIR%\install-and-run.bat"
    echo pause
) > "%LAUNCHER%"

if exist "%LAUNCHER%" (
    echo        Launcher created at: %LAUNCHER%
) else (
    echo        [WARNING] Could not create launcher on the Desktop.
)
echo.

REM ------------------------------------------------------------
REM  STEP 5 : Run the project's install-and-run script
REM ------------------------------------------------------------
echo [5/5] Running install-and-run.bat...
echo ------------------------------------------------------------
call "%REPO_DIR%\install-and-run.bat"

echo.
echo ============================================================
echo  Done. From now on just double-click "Easy-Books" on your
echo  Desktop to launch the app.
echo  To update later: double-click update.bat in the Easy-Books
echo  folder, or run this installer again on the same path.
echo ============================================================
pause
endlocal
