<#
.SYNOPSIS
    Download platform tools required by Chimera: Android platform-tools (ADB)
    and imobiledevice-net (libimobiledevice for Windows).

.DESCRIPTION
    Both archives are extracted into %LOCALAPPDATA%\Chimera\tools\ so the backend
    can locate them without touching system PATH.

.PARAMETER Only
    Optional: "adb" or "ios" to install only one of them. Default: both.
#>

param(
    [ValidateSet('all','adb','ios')]
    [string]$Only = 'all'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

$ToolsRoot  = Join-Path $env:LOCALAPPDATA 'Chimera\tools'
$AdbDir     = Join-Path $ToolsRoot 'platform-tools'
$IosDir     = Join-Path $ToolsRoot 'imobiledevice'

$AdbUrl     = 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip'
$IosUrl     = 'https://github.com/libimobiledevice-win32/imobiledevice-net/releases/download/v1.3.17/libimobiledevice.1.2.1-r1122-win-x64.zip'

New-Item -ItemType Directory -Force -Path $ToolsRoot | Out-Null

function Install-Zip {
    param(
        [string]$Url,
        [string]$Dest,
        [string]$MarkerFile
    )
    $marker = Join-Path $Dest $MarkerFile
    if (Test-Path $marker) {
        Write-Host "==> Already installed: $Dest"
        return
    }
    Write-Host "==> Downloading $Url"
    $tmp = Join-Path $env:TEMP ([System.IO.Path]::GetRandomFileName() + '.zip')
    Invoke-WebRequest -Uri $Url -OutFile $tmp
    Write-Host "==> Extracting to $Dest"
    if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    Expand-Archive -Path $tmp -DestinationPath $Dest -Force
    Remove-Item $tmp -Force
}

if ($Only -eq 'all' -or $Only -eq 'adb') {
    Install-Zip -Url $AdbUrl -Dest $ToolsRoot -MarkerFile 'platform-tools\adb.exe'
    # Google ships the zip as "platform-tools/..." so $ToolsRoot already contains the dir.
    if (-not (Test-Path (Join-Path $AdbDir 'adb.exe'))) {
        throw "adb.exe was not found after extraction at $AdbDir"
    }
    Write-Host "==> ADB installed at $AdbDir"
}

if ($Only -eq 'all' -or $Only -eq 'ios') {
    Install-Zip -Url $IosUrl -Dest $IosDir -MarkerFile 'idevice_id.exe'
    if (-not (Test-Path (Join-Path $IosDir 'idevice_id.exe'))) {
        Write-Warning "idevice_id.exe not found in $IosDir - iOS detection may not work."
    } else {
        Write-Host "==> libimobiledevice installed at $IosDir"
    }
}

Write-Host "==> Done."
