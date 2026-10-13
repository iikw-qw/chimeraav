# Chimera v9.0 — Windows Installer
# Usage: powershell -ExecutionPolicy Bypass -File install_chimera.ps1

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host ""
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host "    CHIMERA v9.0 — Windows Installer    " -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host ""

# --- Check OS ---
Write-Host "[1/7] Checking system..." -ForegroundColor Yellow
$os = [System.Environment]::OSVersion
if ($os.Platform -ne "Win32NT") {
    Write-Host "  ERROR: This script is for Windows only" -ForegroundColor Red
    exit 1
}
Write-Host "  Windows $($os.Version) OK" -ForegroundColor Green

# --- Check/Install Python ---
Write-Host "[2/7] Checking Python 3.11+..." -ForegroundColor Yellow
$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) {
    $py = Get-Command python -ErrorAction SilentlyContinue
}
if ($py) {
    $version = & $py.Source --version 2>&1
    Write-Host "  $version OK" -ForegroundColor Green
} else {
    Write-Host "  Python not found. Install from https://python.org" -ForegroundColor Red
    Write-Host "  Download: https://www.python.org/downloads/" -ForegroundColor Yellow
    Start-Process "https://www.python.org/downloads/"
    exit 1
}

# --- Check/Install Node.js ---
Write-Host "[3/7] Checking Node.js 20+..." -ForegroundColor Yellow
$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    $nodeVersion = & node --version 2>&1
    Write-Host "  Node.js $nodeVersion OK" -ForegroundColor Green
} else {
    Write-Host "  Node.js not found. Install from https://nodejs.org" -ForegroundColor Red
    Start-Process "https://nodejs.org"
    exit 1
}

# --- Check ADB ---
Write-Host "[4/7] Checking ADB..." -ForegroundColor Yellow
$adb = Get-Command adb -ErrorAction SilentlyContinue
if ($adb) {
    Write-Host "  ADB found OK" -ForegroundColor Green
} else {
    Write-Host "  ADB not found (optional for Android device management)" -ForegroundColor Yellow
}

# --- Install dependencies ---
Write-Host "[5/7] Installing dependencies..." -ForegroundColor Yellow

$projectDir = Split-Path -Parent $PSScriptRoot
Push-Location $projectDir

try {
    Write-Host "  npm install..." -ForegroundColor Gray
    & npm install 2>&1 | Out-Null

    $reqFile = Join-Path $projectDir "python-backend\requirements.txt"
    if (Test-Path $reqFile) {
        Write-Host "  pip install..." -ForegroundColor Gray
        & py -m pip install -r $reqFile 2>&1 | Out-Null
    }
    Write-Host "  Dependencies installed" -ForegroundColor Green
} finally {
    Pop-Location
}

# --- Create desktop shortcut ---
Write-Host "[6/7] Creating desktop shortcut..." -ForegroundColor Yellow

$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Chimera Desktop.lnk"
$targetPath = Join-Path $projectDir "run-desktop.bat"
$iconPath = Join-Path $projectDir "resources\icon.ico"

$WshShell = New-Object -ComObject WScript.Shell
$shortcut = $WshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $projectDir
if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}
$shortcut.Description = "Chimera Desktop v9.0"
$shortcut.Save()
Write-Host "  Shortcut created at: $shortcutPath" -ForegroundColor Green

# --- Done ---
Write-Host "[7/7] Installation complete!" -ForegroundColor Yellow
Write-Host ""
Write-Host "  To launch Chimera:" -ForegroundColor Cyan
Write-Host "    1. Double-click 'Chimera Desktop' on your desktop" -ForegroundColor White
Write-Host "    2. Or run: cd '$projectDir' && npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "  Chimera v9.0 ready!" -ForegroundColor Green
