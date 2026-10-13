<#
.SYNOPSIS
    Provision an embedded Python 3.11 runtime for Chimera.

.DESCRIPTION
    1. Download the Python 3.11 embedded zip and extract it into %LOCALAPPDATA%\Chimera\python\
    2. Patch python311._pth to enable site-packages (uncomment "import site")
    3. Bootstrap pip via get-pip.py
    4. pip install -r <InstallDir>\resources\backend\requirements.txt
    5. Create per-user data dirs (datasets, cleaned, exports, backups) under %APPDATA%\Chimera

.PARAMETER InstallDir
    NSIS install root. The installer passes $INSTDIR here; the backend lives at
    $InstallDir\resources\backend (electron-builder extraResources).
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$InstallDir
)

$ErrorActionPreference = 'Stop'
$ProgressPreference   = 'SilentlyContinue'

$PythonVersion    = '3.11.9'
$PythonZipName    = "python-$PythonVersion-embed-amd64.zip"
$PythonUrl        = "https://www.python.org/ftp/python/$PythonVersion/$PythonZipName"
$GetPipUrl        = 'https://bootstrap.pypa.io/get-pip.py'

$PythonDir        = Join-Path $env:LOCALAPPDATA 'Chimera\python'
$BackendDir       = Join-Path $InstallDir 'resources\backend'
$RequirementsPath = Join-Path $BackendDir 'requirements.txt'

Write-Host "==> Installing embedded Python $PythonVersion to $PythonDir"
New-Item -ItemType Directory -Force -Path $PythonDir | Out-Null

$tmpZip = Join-Path $env:TEMP $PythonZipName
Invoke-WebRequest -Uri $PythonUrl -OutFile $tmpZip
Expand-Archive -Path $tmpZip -DestinationPath $PythonDir -Force
Remove-Item $tmpZip -Force

Write-Host "==> Patching python._pth to enable site-packages"
$pthFile = Get-ChildItem -Path $PythonDir -Filter 'python*._pth' | Select-Object -First 1
if ($pthFile) {
    $lines = Get-Content $pthFile.FullName
    $patched = @()
    $hasImportSite = $false
    foreach ($line in $lines) {
        if ($line -match '^\s*#\s*import\s+site\s*$') {
            $patched += 'import site'
            $hasImportSite = $true
        } elseif ($line -match '^\s*import\s+site\s*$') {
            $patched += $line
            $hasImportSite = $true
        } else {
            $patched += $line
        }
    }
    if (-not $hasImportSite) { $patched += 'import site' }
    Set-Content -Path $pthFile.FullName -Value $patched -Encoding ASCII
} else {
    Write-Warning "Could not find python._pth in $PythonDir"
}

$pythonExe = Join-Path $PythonDir 'python.exe'

Write-Host "==> Bootstrapping pip"
$getPipPath = Join-Path $env:TEMP 'get-pip.py'
Invoke-WebRequest -Uri $GetPipUrl -OutFile $getPipPath
& $pythonExe $getPipPath --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "get-pip.py failed (exit $LASTEXITCODE)" }
Remove-Item $getPipPath -Force

if (Test-Path $RequirementsPath) {
    Write-Host "==> Installing Python dependencies from $RequirementsPath"
    & $pythonExe -m pip install --no-warn-script-location -r $RequirementsPath
    if ($LASTEXITCODE -ne 0) { throw "pip install failed (exit $LASTEXITCODE)" }
} else {
    Write-Warning "requirements.txt not found at $RequirementsPath - skipping pip install"
}

Write-Host "==> Creating data directories under %APPDATA%\Chimera"
$dataRoot = Join-Path $env:APPDATA 'Chimera'
foreach ($sub in @('datasets', 'cleaned', 'exports', 'backups')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $dataRoot $sub) | Out-Null
}

Write-Host "==> Done."
