# Easy-Books - update to the latest version.
# Your data lives in %EB_DATA_DIR% (default %USERPROFILE%\.easy-books), OUTSIDE
# this folder, so it is never touched. install-and-run.ps1 runs Alembic on
# launch to migrate your data forward safely.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host "Updating Easy-Books - your data is left untouched." -ForegroundColor Yellow

if (-not (Test-Path (Join-Path $PSScriptRoot '.git'))) {
  Write-Host "This folder is not a git checkout (no .git). Clone from GitHub to use update.ps1." -ForegroundColor Red
  exit 1
}

function Discard-InstallerDrift {
  # uv sync can rewrite backend/uv.lock; older installers dirtied
  # frontend/public/version.json — both block git pull --ff-only (#138).
  git checkout -- backend/uv.lock frontend/public/version.json 2>$null
}

Discard-InstallerDrift

# Local-only FloatingStack experiment never shipped upstream and breaks next build.
$mobileDir = Join-Path $PSScriptRoot 'frontend\src\components\mobile'
$floatingStack = Join-Path $mobileDir 'FloatingStack.tsx'
if (Test-Path $floatingStack) {
  Write-Host "Removing local-only frontend/src/components/mobile (breaks next build)." -ForegroundColor Yellow
  Remove-Item -Recurse -Force $mobileDir
}
$layout = Join-Path $PSScriptRoot 'frontend\src\app\(dashboard)\layout.tsx'
if ((Test-Path $layout) -and (Select-String -Path $layout -Pattern 'FloatingStack' -Quiet)) {
  Write-Host "Restoring layout.tsx (local FloatingStack import)." -ForegroundColor Yellow
  git checkout -- 'frontend/src/app/(dashboard)/layout.tsx' 2>$null
}

git fetch --quiet origin 2>$null
$pull = git pull --ff-only 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "git pull --ff-only failed — local files are blocking the update:" -ForegroundColor Red
  git status -sb
  Write-Host ""
  Write-Host "Safe fix for a script install (discards local commits in this folder only):" -ForegroundColor Yellow
  Write-Host "  git checkout -- backend/uv.lock frontend/public/version.json"
  Write-Host "  git fetch origin; git reset --hard origin/main"
  Write-Host "  .\update.bat"
  Write-Host "Your data under %USERPROFILE%\.easy-books is never touched." -ForegroundColor Yellow
  exit 1
}

Discard-InstallerDrift
& "$PSScriptRoot\install-and-run.ps1" -Rebuild
