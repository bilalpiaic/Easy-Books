$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot/../..").Path
$Res = Join-Path $Root "desktop/resources"
$NodeVersion = "20.18.1"
Remove-Item -Recurse -Force $Res -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Res | Out-Null

# Ensure Node/npm is on PATH for the frontend build below. Prefer system node;
# else reuse the portable .\.node that install-and-run.bat sets up; else fetch
# it. (A plain shell does NOT inherit install-and-run's in-process PATH.)
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  $NodeDir = Join-Path $Root ".node"
  if (-not (Test-Path (Join-Path $NodeDir "node.exe"))) {
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
    $pkg  = "node-v$NodeVersion-win-$arch"
    Invoke-WebRequest "https://nodejs.org/dist/v$NodeVersion/$pkg.zip" -OutFile "$Root\node-build.zip"
    if (Test-Path "$Root\.nodetmp") { Remove-Item "$Root\.nodetmp" -Recurse -Force }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory(
        "$Root\node-build.zip", "$Root\.nodetmp")
    Move-Item (Join-Path "$Root\.nodetmp" $pkg) $NodeDir -Force
    Remove-Item "$Root\node-build.zip","$Root\.nodetmp" -Recurse -Force
  }
  $env:Path = "$NodeDir;$env:Path"
}

# Read version from desktop/package.json and write VERSION for run_packaged._app_version()
$AppVersion = (Get-Content (Join-Path $Root "desktop/package.json") | ConvertFrom-Json).version
[System.IO.File]::WriteAllText((Join-Path $Root "backend/VERSION"), $AppVersion)
Write-Host "App version: $AppVersion"

# Backend binary (PyInstaller emits easybooks-backend\ containing easybooks-backend.exe)
Push-Location (Join-Path $Root "backend")
uv run pyinstaller easybooks-backend.spec
Pop-Location
Copy-Item -Recurse (Join-Path $Root "backend/dist/easybooks-backend") (Join-Path $Res "backend")

# Stop any running Easy-Books instance first — its frontend server (port 3000)
# keeps frontend\.next\standalone open, so `next build` fails with EBUSY trying
# to overwrite it. (Also free 8000 in case the backend is running.)
foreach ($port in 8000, 3000) {
  try {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
      ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  } catch { }
}
# Belt-and-suspenders: drop a stale standalone dir if it lingers after the kill.
Remove-Item -Recurse -Force (Join-Path $Root "frontend/.next/standalone") -ErrorAction SilentlyContinue

# Frontend standalone
Push-Location (Join-Path $Root "frontend")
npm install
$env:NEXT_PUBLIC_APP_VERSION = $AppVersion
npx next build
$env:NEXT_PUBLIC_APP_VERSION = $null
Pop-Location
Copy-Item -Recurse (Join-Path $Root "frontend/.next/static")  (Join-Path $Root "frontend/.next/standalone/.next/static")
Copy-Item -Recurse (Join-Path $Root "frontend/public")        (Join-Path $Root "frontend/.next/standalone/public")
New-Item -ItemType Directory -Force -Path (Join-Path $Res "frontend") | Out-Null
Copy-Item -Recurse (Join-Path $Root "frontend/.next/standalone/*") (Join-Path $Res "frontend")

# Portable Node (win-x64 zip extracts to node-v<ver>-win-x64\node.exe)
$Zip = "node-v$NodeVersion-win-x64"
Invoke-WebRequest "https://nodejs.org/dist/v$NodeVersion/$Zip.zip" -OutFile "$Res/node.zip"
Expand-Archive "$Res/node.zip" -DestinationPath $Res
Move-Item (Join-Path $Res $Zip) (Join-Path $Res "node")
Remove-Item "$Res/node.zip"

echo "Staged -> $Res"
