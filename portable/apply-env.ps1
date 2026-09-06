# Shared portable / cloud-folder env for install-and-run.ps1 and launch-cloud.ps1.
# Dot-source this file. Expects $Root to be the repo root.

$portableEnv = Join-Path $Root 'easy-books-portable.env'
if (Test-Path $portableEnv) {
  Get-Content $portableEnv | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $eq = $line.IndexOf('=')
    if ($eq -lt 1) { return }
    $k = $line.Substring(0, $eq).Trim()
    $v = $line.Substring($eq + 1).Trim().Trim('"').Trim("'")
    if (-not [Environment]::GetEnvironmentVariable($k)) {
      Set-Item -Path "Env:$k" -Value $v
    }
  }
}

$portable = $false
if ($env:EB_PORTABLE -match '^(1|true|yes|on)$') { $portable = $true }
if (Test-Path (Join-Path $Root '.easy-books-portable')) { $portable = $true }

if ($portable) {
  $env:EB_PORTABLE = '1'
  if (-not $env:EB_CLOUD_SAFE_SQLITE) { $env:EB_CLOUD_SAFE_SQLITE = 'true' }
  if (-not $env:EB_INSTANCE_LOCK) { $env:EB_INSTANCE_LOCK = 'true' }
  if (-not $env:EB_DATA_DIR) {
    if ($env:EB_CLOUD_DATA_DIR) {
      $env:EB_DATA_DIR = $env:EB_CLOUD_DATA_DIR
    } else {
      $env:EB_DATA_DIR = Join-Path $Root 'data'
    }
  }
}
