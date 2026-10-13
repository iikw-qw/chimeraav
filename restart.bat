@echo off
chcp 65001 >nul
title Chimera v5.0 — Перезапуск
color 0B

echo.
echo  ╔══════════════════════════════════════╗
echo  ║     CHIMERA v5.0 — ПЕРЕЗАПУСК       ║
echo  ╚══════════════════════════════════════╝
echo.

cd /d "C:\chimera project"

echo  Останавливаю контейнеры...
docker compose down

echo  Пересобираю и запускаю...
docker compose up -d --build

echo  Ожидание готовности...
timeout /t 15 /nobreak >nul

:healthcheck
for /f "delims=" %%i in ('powershell -Command "(Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 5).Content" 2^>nul') do set HEALTH=%%i
echo %HEALTH% | findstr "healthy" >nul 2>&1
if %errorlevel% neq 0 (
    echo        Сервисы загружаются...
    timeout /t 5 /nobreak >nul
    goto healthcheck
)

color 0A
echo.
echo  Chimera v5.0 перезапущена!
echo  Web UI: http://localhost:3000
echo.

start "" "http://localhost:3000"
pause
