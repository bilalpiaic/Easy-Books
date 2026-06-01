# Build the Easy-Books desktop installer on WINDOWS.
#
# Produces:  desktop\dist\Easy-Books Setup <version>.exe   (NSIS)
#
# Prereqs (already present if you've run install-and-run.bat): uv (+Python 3.12)
# and Node.js. The FIRST run also downloads a portable Node + Electron and can
# take several minutes.
#
# Signing: the installer is UNSIGNED unless you set CSC_LINK (path/base64 of your
# .pfx) and CSC_KEY_PASSWORD before running. Unsigned installs trigger a Windows
# SmartScreen "unknown publisher" prompt (the app still installs/runs).
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "`n[1/3] Staging resources (PyInstaller backend + Next.js build + portable Node)..." -ForegroundColor Yellow
& "$Root\scripts\prepare-resources.ps1"
Set-Location $Root   # prepare-resources may change the location; reset it

Write-Host "`n[2/3] Installing desktop (Electron) dependencies..." -ForegroundColor Yellow
npm install

Write-Host "`n[3/3] Building the installer (electron-builder)..." -ForegroundColor Yellow
npm run dist

Write-Host "`nDone. Installer(s) in $Root\dist:" -ForegroundColor Green
Get-ChildItem "$Root\dist" -Filter *.exe -ErrorAction SilentlyContinue |
  ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Green }
