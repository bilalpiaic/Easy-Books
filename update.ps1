# Easy-Books — update to the latest version.
# Your data lives in %EB_DATA_DIR% (default %USERPROFILE%\.easy-books), OUTSIDE
# this folder, so it is never touched. install-and-run.ps1 runs Alembic on
# launch to migrate your data forward safely.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host "Updating Easy-Books - your data is left untouched." -ForegroundColor Yellow
git pull --ff-only
& "$PSScriptRoot\install-and-run.ps1" -Rebuild
