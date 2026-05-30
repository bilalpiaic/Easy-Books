$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot/../..").Path
$Res = Join-Path $Root "desktop/resources"
$NodeVersion = "20.18.1"
Remove-Item -Recurse -Force $Res -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Res | Out-Null

# Backend binary (PyInstaller emits easybooks-backend\ containing easybooks-backend.exe)
Push-Location (Join-Path $Root "backend")
uv run pyinstaller easybooks-backend.spec
Pop-Location
Copy-Item -Recurse (Join-Path $Root "backend/dist/easybooks-backend") (Join-Path $Res "backend")

# Frontend standalone
Push-Location (Join-Path $Root "frontend")
npm install
npx next build
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
