# Easy-Books bootstrap (Windows) - clone (or update) the repo, then install
# everything and run. The only manual step a new user takes.
#
# One-liner (nothing pre-downloaded), in PowerShell:
#   irm https://raw.githubusercontent.com/bilalpiaic/Easy-Books/main/bootstrap.ps1 | iex
#
# Or:  powershell -ExecutionPolicy Bypass -File bootstrap.ps1 [-Dest <folder>]
# Install location: -Dest, else %EB_INSTALL_DIR%, else %USERPROFILE%\Easy-Books.
param([string]$Dest = $(if ($env:EB_INSTALL_DIR) { $env:EB_INSTALL_DIR } else { Join-Path $env:USERPROFILE 'Easy-Books' }))

$ErrorActionPreference = 'Stop'
$Repo = 'https://github.com/bilalpiaic/Easy-Books.git'
$Zip  = 'https://github.com/bilalpiaic/Easy-Books/archive/refs/heads/main.zip'

function Log($m) { Write-Host "`n> $m" -ForegroundColor Yellow }

Log "Easy-Books will be installed in: $Dest"

if (Get-Command git -ErrorAction SilentlyContinue) {
  if (Test-Path (Join-Path $Dest '.git')) {
    Log 'Updating existing copy (git pull)...'
    git -C $Dest pull --ff-only
  } elseif (Test-Path $Dest) {
    Log 'Folder already exists and is not a git repo - using it as-is.'
  } else {
    Log "Cloning $Repo ..."
    git clone --depth 1 $Repo $Dest
  }
} else {
  # No git - download the source archive instead.
  if (-not (Test-Path $Dest)) {
    Log 'git not found - downloading source archive...'
    $tmp = Join-Path $env:TEMP ('eb_' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    Invoke-WebRequest $Zip -OutFile (Join-Path $tmp 'eb.zip')
    Expand-Archive (Join-Path $tmp 'eb.zip') -DestinationPath $tmp -Force
    Move-Item (Join-Path $tmp 'Easy-Books-main') $Dest -Force
    Remove-Item $tmp -Recurse -Force
  }
}

$runner = Join-Path $Dest 'install-and-run.ps1'
if (-not (Test-Path $runner)) { throw "install-and-run.ps1 not found in $Dest." }
Set-Location $Dest
Log 'Launching the installer...'
powershell -NoProfile -ExecutionPolicy Bypass -File $runner
