# Easy-Books - rebuild and pack the catalog advertisement explorer.
#
# Double-click ship-catalog-ad.bat, or:
#   powershell -ExecutionPolicy Bypass -File ship-catalog-ad.ps1
#   powershell -ExecutionPolicy Bypass -File ship-catalog-ad.ps1 -Refresh
#   powershell -ExecutionPolicy Bypass -File ship-catalog-ad.ps1 -Open
#   powershell -ExecutionPolicy Bypass -File ship-catalog-ad.ps1 -PrintPaths
#
# Override the project folder with $env:EB_ROOT if this script is copied elsewhere.
#
# ASCII ONLY below this line. Windows PowerShell 5.1 does not reliably read
# UTF-8 em-dashes; use "-" in string literals (same rule as install-and-run.ps1).
param(
  [switch]$Refresh,
  [switch]$Open,
  [switch]$SkipPack,
  [switch]$PrintPaths
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($env:EB_ROOT) {
  $Root = (Resolve-Path $env:EB_ROOT).Path
} else {
  $Root = $ScriptDir
}
Set-Location $Root

# --- Project + required file locations (all relative to Root) ----------------
$Marketing   = Join-Path $Root 'docs\marketing'
$Frontend    = Join-Path $Root 'frontend'
$Public      = Join-Path $Frontend 'public'
$Shots       = Join-Path $Public 'catalog'

$BuildPy     = Join-Path $Marketing 'build_catalog_ad.py'
$PackPy      = Join-Path $Marketing 'pack_catalog_ad.py'
$ShipDoc     = Join-Path $Marketing 'CATALOG_AD_SHIP.md'
$IndexDocs   = Join-Path $Marketing 'catalog-index.json'
$IndexPublic = Join-Path $Shots 'index.json'
$HtmlDocs    = Join-Path $Marketing 'catalog-advertisement.html'
$HtmlPublic  = Join-Path $Public 'catalog-advertisement.html'
$ZipOut      = Join-Path $Marketing 'dist\easy-books-catalog-explorer.zip'
$Creative    = Join-Path $Marketing 'slides\12-cta.png'
$VitestSpec  = Join-Path $Frontend 'src\lib\__tests__\workflowCatalog.test.ts'

$Origin = if ($env:FRONTEND_ORIGIN) { $env:FRONTEND_ORIGIN.TrimEnd('/') } else { 'http://127.0.0.1:3000' }
$Hosted = "$Origin/catalog-advertisement.html"

function Write-Paths {
  Write-Host ""
  Write-Host "Easy-Books catalog advertisement - locations"
  Write-Host "============================================"
  Write-Host "Project root (EB_ROOT)     $Root"
  Write-Host "Shipping spec              $ShipDoc"
  Write-Host "Build HTML                 $BuildPy"
  Write-Host "Pack zip                   $PackPy"
  Write-Host "Catalog JSON (preferred)   $IndexDocs"
  Write-Host "Catalog JSON (fallback)    $IndexPublic"
  Write-Host "Explorer HTML (docs)       $HtmlDocs"
  Write-Host "Explorer HTML (public)     $HtmlPublic"
  Write-Host "Snapshots (JPEGs)          $Shots"
  Write-Host "Ad creative (slide)        $Creative"
  Write-Host "Offline zip (gitignored)   $ZipOut"
  Write-Host "Hosted click-out URL       $Hosted"
  Write-Host "Vitest (refresh index)     $VitestSpec"
  Write-Host ""
  Write-Host "Ads / email / chat: send the hosted URL, not the HTML file."
  Write-Host "Booth / USB: unzip the zip and double-click catalog-advertisement.html."
}

function Log($m) { Write-Host "`n> $m" -ForegroundColor Yellow }
function Ok($m)  { Write-Host "OK $m" -ForegroundColor Green }

Write-Paths

if (-not (Test-Path (Join-Path $Root 'frontend')) -or -not (Test-Path $Marketing)) {
  throw "Not an Easy-Books checkout. Expected frontend\ and docs\marketing\ under $Root (set EB_ROOT)."
}
if (-not (Test-Path $BuildPy)) { throw "missing $BuildPy" }
if (-not (Test-Path $PackPy))  { throw "missing $PackPy" }
if (-not (Test-Path $Shots))   { throw "missing snapshot folder $Shots" }

$JpgCount = @(Get-ChildItem -Path $Shots -Filter '*.jpg' -File -ErrorAction SilentlyContinue).Count
if ($JpgCount -lt 50) { throw "expected catalog JPEGs in $Shots, found $JpgCount" }

if ($PrintPaths) {
  Ok "$JpgCount snapshots on disk"
  exit 0
}

function Invoke-Python([string]$ScriptPath) {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $ScriptPath
  } elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $ScriptPath
  } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    & python3 $ScriptPath
  } else {
    throw 'python3 is required (stdlib only - json, pathlib, zipfile). Install Python 3 or the py launcher.'
  }
  if ($LASTEXITCODE -ne 0) { throw "python failed: $ScriptPath" }
}

function Refresh-Index {
  if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'npm is required for -Refresh (catalog-index.json).'
  }
  $nm = Join-Path $Frontend 'node_modules'
  if (-not (Test-Path $nm)) { throw 'frontend\node_modules missing - run npm install in frontend\ first.' }
  Log 'Refreshing catalog-index.json (vitest)...'
  Push-Location $Frontend
  try {
    npm test -- src/lib/__tests__/workflowCatalog.test.ts
    if ($LASTEXITCODE -ne 0) { throw 'vitest failed' }
  } finally {
    Pop-Location
  }
}

if ($Refresh) { Refresh-Index }

if (-not (Test-Path $IndexDocs) -and -not (Test-Path $IndexPublic)) {
  Log 'catalog-index.json missing - generating it...'
  Refresh-Index
}

if (-not (Test-Path $IndexDocs) -and -not (Test-Path $IndexPublic)) {
  throw "no catalog JSON at $IndexDocs or $IndexPublic"
}

Log 'Building explorer HTML...'
Invoke-Python $BuildPy
if (-not (Test-Path $HtmlDocs) -or -not (Test-Path $HtmlPublic)) {
  throw "build did not write $HtmlDocs and $HtmlPublic"
}
Ok "HTML -> $HtmlDocs"
Ok "HTML -> $HtmlPublic  (served as /catalog-advertisement.html)"

if (-not $SkipPack) {
  Log 'Packing offline zip (USB / booth)...'
  Invoke-Python $PackPy
  if (-not (Test-Path $ZipOut)) { throw "packer did not write $ZipOut" }
  Ok "zip  -> $ZipOut"
}

Write-Host ""
Write-Host "Ship for ads:  $Hosted"
Write-Host "Do not attach the HTML. Spec: $ShipDoc"

if ($Open) {
  Start-Process $HtmlPublic
}
