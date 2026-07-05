# Easy-Books — update to the latest version.
# Your data lives in %EB_DATA_DIR% (default %USERPROFILE%\.easy-books), OUTSIDE
# this folder, so it is never touched. install-and-run.ps1 runs Alembic on
# launch to migrate your data forward safely.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host "Updating Easy-Books - your data is left untouched." -ForegroundColor Yellow
# uv sync (run by install-and-run.ps1 on every launch) can rewrite backend/uv.lock
# even with no dependency changes; discard that drift before pulling so a fresh
# upstream lockfile bump can't block the fast-forward (#138).
git checkout -- backend/uv.lock 2>$null
git pull --ff-only
& "$PSScriptRoot\install-and-run.ps1" -Rebuild
