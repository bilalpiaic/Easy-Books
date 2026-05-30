# Easy-Books - one-click install & run (Windows).
#
# Auto-installs everything it needs (no pre-installed Python or Node required):
#   * uv      - self-installs; also provisions Python 3.12 automatically
#   * Node.js - uses system Node if present, else downloads a local portable
#               copy into .\.node (no system install, no admin rights)
# Then builds the app and launches it at http://127.0.0.1:3000.
#
# Double-click install-and-run.bat, or:  powershell -ExecutionPolicy Bypass -File install-and-run.ps1
# Pass -Rebuild to force a fresh frontend build.
# Data lives in %EB_DATA_DIR% (default %USERPROFILE%\.easy-books).
param([switch]$Rebuild)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$NodeVersion = '20.18.1'

function Log($m) { Write-Host "`n> $m" -ForegroundColor Yellow }

# --- 1. uv (provides Python 3.12 too) ----------------------------------------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Log 'Installing uv (Python toolchain manager)...'
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
}
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw 'uv install failed - see https://docs.astral.sh/uv/'
}

# --- 2. Node.js (system, else local portable download) -----------------------
if (Get-Command node -ErrorAction SilentlyContinue) {
  $NodeExe = (Get-Command node).Source
} else {
  $NodeDir = Join-Path $Root '.node'
  $NodeExe = Join-Path $NodeDir 'node.exe'
  if (-not (Test-Path $NodeExe)) {
    Log "Downloading a local Node.js $NodeVersion (no system install)..."
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'x64' }
    $url  = "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-win-$arch.zip"
    Invoke-WebRequest -Uri $url -OutFile 'node.zip'
    if (Test-Path '.nodetmp') { Remove-Item '.nodetmp' -Recurse -Force }
    Expand-Archive 'node.zip' -DestinationPath '.nodetmp' -Force
    Move-Item (Join-Path '.nodetmp' "node-v$NodeVersion-win-$arch") $NodeDir -Force
    Remove-Item 'node.zip' -Force
    Remove-Item '.nodetmp' -Recurse -Force
  }
  $env:Path = "$NodeDir;$env:Path"
}

# --- 3. Backend dependencies (uv fetches Python 3.12 if missing) -------------
Log 'Installing backend dependencies...'
Push-Location backend; uv sync; Pop-Location

# --- 4. Frontend build (skipped if already built; -Rebuild forces it) --------
$server = 'frontend\.next\standalone\server.js'
if ($Rebuild -or -not (Test-Path $server)) {
  Log 'Building the app (first run can take a few minutes)...'
  Push-Location frontend; npm install; npx next build; Pop-Location
  # Next 'standalone' does not copy these - required for the server to serve them.
  Copy-Item 'frontend\.next\static' 'frontend\.next\standalone\.next\static' -Recurse -Force
  Copy-Item 'frontend\public'       'frontend\.next\standalone\public'       -Recurse -Force
}

# --- 5. Launch (both servers, localhost only) --------------------------------
if (-not $env:EB_DATA_DIR) { $env:EB_DATA_DIR = Join-Path $env:USERPROFILE '.easy-books' }
if (-not $env:SEED_DEMO)   { $env:SEED_DEMO   = 'true' }    # seed demo tenants so the advertised demo logins work (override with SEED_DEMO=false for an empty start)
if (-not $env:FRONTEND_ORIGIN) { $env:FRONTEND_ORIGIN = 'http://localhost:3000,http://127.0.0.1:3000' }  # allow both hosts so the browser is not CORS-blocked
if (-not $env:APP_ENV)     { $env:APP_ENV     = 'local' }
New-Item -ItemType Directory -Force -Path $env:EB_DATA_DIR | Out-Null

# Free ports from any previous run so the fresh backend (with seeding) actually binds.
foreach ($port in 8000, 3000) {
  try {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
      ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  } catch { }
}

Log "Starting Easy-Books - data folder: $env:EB_DATA_DIR"
$backLog = Join-Path $env:EB_DATA_DIR 'backend.log'
$backErr = Join-Path $env:EB_DATA_DIR 'backend.err.log'
$back = Start-Process -PassThru -WindowStyle Hidden -WorkingDirectory (Join-Path $Root 'backend') `
  -FilePath 'cmd.exe' -ArgumentList '/c','set "PYTHONPATH=." && uv run uvicorn main:app --host 127.0.0.1 --port 8000' `
  -RedirectStandardOutput $backLog -RedirectStandardError $backErr

# Child inherits these (PowerShell 5.1 has no Start-Process -Environment).
$env:PORT = '3000'; $env:HOSTNAME = '127.0.0.1'
$front = Start-Process -PassThru -WindowStyle Hidden -WorkingDirectory (Join-Path $Root 'frontend') `
  -FilePath $NodeExe -ArgumentList '.next\standalone\server.js'

Start-Sleep -Seconds 6
foreach ($f in $backLog, $backErr) {
  if (Test-Path $f) {
    Get-Content $f | Select-String -SimpleMatch '[seed]' | Select-Object -Last 1 |
      ForEach-Object { Write-Host $_.Line -ForegroundColor Cyan }
  }
}
Start-Process 'http://127.0.0.1:3000'
Write-Host "`nEasy-Books is running at  http://127.0.0.1:3000   (close this window to stop)" -ForegroundColor Green
try { Wait-Process -Id $back.Id, $front.Id }
finally { Stop-Process -Id $back.Id, $front.Id -ErrorAction SilentlyContinue }
