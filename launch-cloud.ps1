# Easy-Books - cloud-folder / portable launcher (Windows).
#
# Cloud drives do not execute a backend. This script runs FastAPI + Next.js
# on THIS PC and stores SQLite under EB_DATA_DIR (default .\data in this folder).
#
# Double-click launch-cloud.bat, or:
#   powershell -ExecutionPolicy Bypass -File launch-cloud.ps1
#   powershell -ExecutionPolicy Bypass -File launch-cloud.ps1 -Open
#   powershell -ExecutionPolicy Bypass -File launch-cloud.ps1 -Backend
#   powershell -ExecutionPolicy Bypass -File launch-cloud.ps1 -Stop
#
# ASCII ONLY below this line (PowerShell 5.1 / system codepage).
param(
  [switch]$Open,
  [switch]$Backend,
  [switch]$Stop
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
. (Join-Path $Root 'portable\apply-env.ps1')

if (-not $env:EB_PORTABLE) { $env:EB_PORTABLE = '1' }
if (-not $env:EB_CLOUD_SAFE_SQLITE) { $env:EB_CLOUD_SAFE_SQLITE = 'true' }
if (-not $env:EB_INSTANCE_LOCK) { $env:EB_INSTANCE_LOCK = 'true' }
if (-not $env:EB_DATA_DIR) { $env:EB_DATA_DIR = Join-Path $Root 'data' }
if (-not $env:FRONTEND_ORIGIN) { $env:FRONTEND_ORIGIN = 'http://localhost:3000,http://127.0.0.1:3000' }
if (-not $env:APP_ENV) { $env:APP_ENV = 'local' }
if (-not $env:SEED_DEMO) { $env:SEED_DEMO = 'false' }
$env:Path = "$env:USERPROFILE\.local\bin;$Root\.node;$env:Path"

$RunDir = Join-Path $Root '.run'
New-Item -ItemType Directory -Force -Path $env:EB_DATA_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Test-Api {
  try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/version' -UseBasicParsing -TimeoutSec 2
    return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
  } catch { return $false }
}

function Test-Ui {
  try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:3000/login' -UseBasicParsing -TimeoutSec 2
    return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
  } catch { return $false }
}

function Open-Ui {
  Start-Process 'http://127.0.0.1:3000/login'
}

function Stop-PidFile($file) {
  if (Test-Path $file) {
    $pidVal = (Get-Content $file -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($pidVal) {
      try { Stop-Process -Id ([int]$pidVal) -Force -ErrorAction SilentlyContinue } catch {}
    }
    Remove-Item $file -Force -ErrorAction SilentlyContinue
  }
}

if ($Stop) {
  Stop-PidFile (Join-Path $RunDir 'backend.pid')
  Stop-PidFile (Join-Path $RunDir 'frontend.pid')
  Write-Host "Stopped Easy-Books local servers (data folder left untouched: $env:EB_DATA_DIR)"
  exit 0
}

if ($Open) {
  if (-not (Test-Api)) {
    Write-Host 'Backend is not running on http://127.0.0.1:8000.' -ForegroundColor Red
    Write-Host 'Start it with:  powershell -ExecutionPolicy Bypass -File launch-cloud.ps1 -Backend'
    exit 1
  }
  if (-not (Test-Ui)) {
    Write-Host 'Frontend is not running. Starting it...'
  } else {
    Open-Ui
    Write-Host "Opened http://127.0.0.1:3000  (API already running; data: $env:EB_DATA_DIR)"
    exit 0
  }
}

function Start-EbBackend {
  if (Test-Api) {
    Write-Host 'Backend already running on :8000'
    return
  }
  Write-Host "Starting backend (data: $env:EB_DATA_DIR)..."
  $env:PYTHONPATH = (Join-Path $Root 'backend')
  $log = Join-Path $RunDir 'backend.log'
  $p = Start-Process -FilePath 'uv' -ArgumentList @('run','python','-m','uvicorn','main:app','--host','127.0.0.1','--port','8000') `
    -WorkingDirectory (Join-Path $Root 'backend') `
    -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError (Join-Path $RunDir 'backend.err.log')
  Set-Content -Path (Join-Path $RunDir 'backend.pid') -Value $p.Id
  $env:PYTHONPATH = (Join-Path $Root 'backend')
  $ready = $false
  for ($i = 0; $i -lt 60; $i++) {
    if (Test-Api) { $ready = $true; break }
    Start-Sleep -Seconds 1
  }
  if (-not $ready) {
    Write-Host 'Backend failed to start. See .run\backend.err.log' -ForegroundColor Red
    exit 1
  }
}

function Start-EbFrontend {
  if (Test-Ui) {
    Write-Host 'Frontend already running on :3000'
    return
  }
  $node = Get-Command node -ErrorAction SilentlyContinue
  if (-not $node) {
    Write-Host 'Node.js not found. Run install-and-run.bat once first.' -ForegroundColor Red
    exit 1
  }
  $server = Join-Path $Root 'frontend\.next\standalone\server.js'
  if (-not (Test-Path $server)) {
    Write-Host 'Frontend is not built. Run install-and-run.bat once first.' -ForegroundColor Red
    exit 1
  }
  Write-Host 'Starting frontend...'
  $env:PORT = '3000'
  $env:HOSTNAME = '127.0.0.1'
  $p = Start-Process -FilePath $node.Source -ArgumentList @($server) `
    -WorkingDirectory (Join-Path $Root 'frontend') `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $RunDir 'frontend.log') `
    -RedirectStandardError (Join-Path $RunDir 'frontend.err.log')
  Set-Content -Path (Join-Path $RunDir 'frontend.pid') -Value $p.Id
  for ($i = 0; $i -lt 30; $i++) {
    if (Test-Ui) { break }
    Start-Sleep -Seconds 1
  }
}

# uv on Windows needs PYTHONPATH for uvicorn main:app
$env:PYTHONPATH = (Join-Path $Root 'backend')

if ($Backend) {
  Start-EbBackend
  Write-Host 'API is running at http://127.0.0.1:8000 - leave this machine on.'
  Write-Host 'Open the UI with launch-cloud.ps1 -Open'
  exit 0
}

Start-EbBackend
Start-EbFrontend
Open-Ui
Write-Host 'Easy-Books is running at http://127.0.0.1:3000'
Write-Host "Data folder: $env:EB_DATA_DIR"
Write-Host 'Stop with: powershell -ExecutionPolicy Bypass -File launch-cloud.ps1 -Stop'
