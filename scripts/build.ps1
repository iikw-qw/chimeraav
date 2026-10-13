$ErrorActionPreference = 'Stop'

Write-Host "Building Chimera..." -ForegroundColor Cyan

npm run build
if ($LASTEXITCODE -ne 0) { throw "vite/electron build failed (exit $LASTEXITCODE)" }

npm run dist:win
if ($LASTEXITCODE -ne 0) { throw "electron-builder failed (exit $LASTEXITCODE)" }

Write-Host "Done! Installer: build/Chimera-Setup.exe" -ForegroundColor Green
