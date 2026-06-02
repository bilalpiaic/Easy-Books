# Build the Easy-Books desktop installer on WINDOWS.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File desktop\build-all.ps1
#   powershell -ExecutionPolicy Bypass -File desktop\build-all.ps1 -SkipStaging
#
#   -SkipStaging  Reuse the already-staged desktop\resources and just repackage
#                 (fast — for a main.js / electron-builder.yml-only change). Skips
#                 the ~minutes-long PyInstaller backend + Next.js rebuild.
#
# Produces:  desktop\dist\Easy-Books Setup <version>.exe  (and dist\win-unpacked\)
#
# Prereqs (present after running install-and-run.bat): uv (+Python) and Node —
# this script finds Node itself (system → portable .\.node → download), so you do
# NOT need npm on your PATH. Signing: unsigned unless CSC_LINK/CSC_KEY_PASSWORD set.
param([switch]$SkipStaging, [switch]$Publish)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $Root "..")).Path
Set-Location $Root

# --- Ensure Node/npm is on PATH (system → portable .\.node → download) --------
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  $NodeDir = Join-Path $RepoRoot ".node"
  if (-not (Test-Path (Join-Path $NodeDir "node.exe"))) {
    $nv = "20.18.1"
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
    $pkg = "node-v$nv-win-$arch"
    Write-Host "Downloading a local Node $nv..." -ForegroundColor Yellow
    Invoke-WebRequest "https://nodejs.org/dist/v$nv/$pkg.zip" -OutFile "$RepoRoot\node-build.zip"
    if (Test-Path "$RepoRoot\.nodetmp") { Remove-Item "$RepoRoot\.nodetmp" -Recurse -Force }
    Expand-Archive "$RepoRoot\node-build.zip" -DestinationPath "$RepoRoot\.nodetmp" -Force
    Move-Item (Join-Path "$RepoRoot\.nodetmp" $pkg) $NodeDir -Force
    Remove-Item "$RepoRoot\node-build.zip","$RepoRoot\.nodetmp" -Recurse -Force
  }
  $env:Path = "$NodeDir;$env:Path"
}

# --- Stop any running instance so the build can overwrite its output ----------
Get-Process -Name "Easy-Books" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
foreach ($port in 8000, 3000) {
  try {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
      ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  } catch { }
}

# --- 1/3  Stage resources (skippable) -----------------------------------------
if (-not $SkipStaging) {
  Write-Host "`n[1/3] Staging resources (PyInstaller backend + Next.js build + portable Node)..." -ForegroundColor Yellow
  & "$Root\scripts\prepare-resources.ps1"
  Set-Location $Root
} else {
  if (-not (Test-Path (Join-Path $Root "resources\frontend\server.js"))) {
    throw "-SkipStaging given but desktop\resources isn't staged yet. Run without -SkipStaging once."
  }
  Write-Host "`n[1/3] -SkipStaging: reusing existing desktop\resources." -ForegroundColor Yellow
}

# --- 2/3  Desktop (Electron) deps ---------------------------------------------
Write-Host "`n[2/3] Installing desktop (Electron) dependencies..." -ForegroundColor Yellow
npm install

# --- 3/3  Package (and optionally publish) the installer ----------------------
if ($Publish) {
  if (-not $env:GH_TOKEN) {
    throw "Set GH_TOKEN before -Publish, e.g.  `$env:GH_TOKEN = (gh auth token)"
  }
  Write-Host "`n[3/3] Building + PUBLISHING to GitHub Releases (electron-builder --publish always)..." -ForegroundColor Yellow
  npx electron-builder --config electron-builder.yml --publish always
} else {
  Write-Host "`n[3/3] Building the installer (electron-builder)..." -ForegroundColor Yellow
  npm run dist
}

Write-Host "`nDone. Output in $Root\dist:" -ForegroundColor Green
Get-ChildItem "$Root\dist" -Filter *.exe -ErrorAction SilentlyContinue |
  ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Green }
Write-Host "  win-unpacked\Easy-Books.exe  (run directly to test)" -ForegroundColor Green
