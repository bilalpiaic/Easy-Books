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
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory(
        (Join-Path $Root 'node.zip'), (Join-Path $Root '.nodetmp'))
    Move-Item (Join-Path '.nodetmp' "node-v$NodeVersion-win-$arch") $NodeDir -Force
    Remove-Item 'node.zip' -Force
    Remove-Item '.nodetmp' -Recurse -Force
  }
  $env:Path = "$NodeDir;$env:Path"
}

# --- 3. Backend dependencies (uv fetches Python 3.12 if missing) -------------
Log 'Installing backend dependencies...'
Push-Location backend; uv sync; Pop-Location

# --- 4. Stop any running instance so the build can replace locked files ------
foreach ($port in 8000, 3000) {
  try {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
      ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  } catch { }
}

# --- 4b. Frontend build (skipped if already built; -Rebuild forces it) -------
$server = 'frontend\.next\standalone\server.js'
# Rebuild when forced, when there's no build yet, OR when the code has moved on
# since the last build (so a git pull / update always recompiles the UI — a
# stale bundle must never hide new features).
$builtMarker = 'frontend\.next\.built-commit'
$headCommit  = (git rev-parse HEAD 2>$null)
$builtCommit = if (Test-Path $builtMarker) { (Get-Content $builtMarker -ErrorAction SilentlyContinue) } else { '' }
$stale = $headCommit -and ($headCommit -ne $builtCommit)
$appVersion = (uv run python -c "import json; print(json.load(open('frontend/package.json'))['version'],end='')" 2>$null)
if (-not $appVersion) { $appVersion = 'dev' }
if ($Rebuild -or -not (Test-Path $server) -or $stale) {
  Log 'Building the app (first run or update can take a few minutes)...'
  $buildDate = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  $env:NEXT_PUBLIC_APP_VERSION = $appVersion
  $env:NEXT_PUBLIC_GIT_COMMIT  = if ($headCommit) { $headCommit } else { 'dev' }
  $env:NEXT_PUBLIC_BUILD_DATE  = $buildDate
  Push-Location frontend; npm install; npx next build; Pop-Location
  Remove-Item Env:NEXT_PUBLIC_APP_VERSION -ErrorAction SilentlyContinue
  Remove-Item Env:NEXT_PUBLIC_GIT_COMMIT  -ErrorAction SilentlyContinue
  Remove-Item Env:NEXT_PUBLIC_BUILD_DATE  -ErrorAction SilentlyContinue
  # Write version.json so UpdateModal can detect when update.ps1 has already
  # rebuilt the server (page's baked-in commit differs from server's commit).
  $commitVal = if ($headCommit) { $headCommit } else { 'dev' }
  $vj = '{"version":"' + $appVersion + '","commit":"' + $commitVal + '","built":"' + $buildDate + '"}'
  Set-Content -Path 'frontend\public\version.json' -Value $vj -Encoding UTF8
  # Next 'standalone' does not copy these - required for the server to serve them.
  Copy-Item 'frontend\.next\static' 'frontend\.next\standalone\.next\static' -Recurse -Force
  Copy-Item 'frontend\public'       'frontend\.next\standalone\public'       -Recurse -Force
  if ($headCommit) { Set-Content -Path $builtMarker -Value $headCommit }
}

# --- 5. Launch (both servers, localhost only) --------------------------------
if (-not $env:EB_DATA_DIR) { $env:EB_DATA_DIR = Join-Path $env:USERPROFILE '.easy-books' }
if (-not $env:SEED_DEMO)   { $env:SEED_DEMO   = 'true' }    # auto-load full demo data on first install; set SEED_DEMO=false for a clean install
if (-not $env:FRONTEND_ORIGIN) { $env:FRONTEND_ORIGIN = 'http://localhost:3000,http://127.0.0.1:3000' }  # allow both hosts so the browser is not CORS-blocked
if (-not $env:APP_ENV)     { $env:APP_ENV     = 'local' }
New-Item -ItemType Directory -Force -Path $env:EB_DATA_DIR | Out-Null

# Migrate the user's DB forward so updates apply new columns (not just tables).
# Fail loud rather than start the app on a half-migrated schema.
# Auto-backup before any migration so users can roll back by restoring the file.
Log 'Checking for pending database migrations...'
Push-Location backend
$pendingOut = cmd /c 'set "PYTHONPATH=." && uv run alembic check 2>&1'
$hasPending = $LASTEXITCODE -ne 0
Pop-Location
if ($hasPending) {
  $backupDir = Join-Path $env:EB_DATA_DIR 'backups'
  New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
  $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
  Get-ChildItem -Path $env:EB_DATA_DIR -Filter '*.db' -File | ForEach-Object {
    $dest = Join-Path $backupDir ($_.BaseName + "_$stamp.bak")
    Copy-Item $_.FullName $dest
    Log "  Backed up $($_.Name) → backups\$($_.BaseName)_$stamp.bak"
  }
}
Log 'Applying database migrations...'
Push-Location backend
cmd /c 'set "PYTHONPATH=." && uv run alembic upgrade head'
$migrateCode = $LASTEXITCODE
Pop-Location
if ($migrateCode -ne 0) { throw "Database migration failed - restore from $env:EB_DATA_DIR\backups\ if needed. See the error above." }

# First-run demo data: load the 5 fully-populated demo companies so the demo
# logins work immediately. Idempotent (skips once present); skipped entirely
# when SEED_DEMO=false. ~20-30s on first install only.
Log 'Loading demo data (first run only; set SEED_DEMO=false to skip)...'
Push-Location backend
cmd /c 'set "PYTHONPATH=." && uv run python -m scripts.autoseed_demo'
Pop-Location

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
try { Wait-Process -Id $back.Id, $front.Id -ErrorAction SilentlyContinue }
finally { Stop-Process -Id $back.Id, $front.Id -ErrorAction SilentlyContinue }
