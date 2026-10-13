@echo off
chcp 65001 >nul
title Chimera v5.0 — Запуск
color 0A

echo.
echo  ╔══════════════════════════════════════╗
echo  ║       CHIMERA v5.0 — ЗАПУСК         ║
echo  ╚══════════════════════════════════════╝
echo.

cd /d "C:\chimera project"

echo  [1/3] Проверка Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo  ОШИБКА: Docker не запущен!
    echo  Запустите Docker Desktop и попробуйте снова.
    echo.
    pause
    exit /b 1
)
echo        Docker OK

echo  [2/3] Запуск контейнеров...
docker compose up -d
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo  ОШИБКА при запуске контейнеров!
    echo.
    pause
    exit /b 1
)

echo  [3/3] Ожидание готовности сервисов...
timeout /t 10 /nobreak >nul

:healthcheck
for /f "delims=" %%i in ('powershell -Command "(Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 5).Content" 2^>nul') do set HEALTH=%%i
echo %HEALTH% | findstr "healthy" >nul 2>&1
if %errorlevel% neq 0 (
    echo        Сервисы загружаются, подождите...
    timeout /t 5 /nobreak >nul
    goto healthcheck
)

color 0A
echo.
echo  ╔══════════════════════════════════════╗
echo  ║      CHIMERA v5.0 ЗАПУЩЕНА!         ║
echo  ╠══════════════════════════════════════╣
echo  ║                                      ║
echo  ║  Web UI:     http://localhost:3000   ║
echo  ║  API:        http://localhost:8000   ║
echo  ║  Grafana:    http://localhost:3001   ║
echo  ║  Prometheus: http://localhost:9090   ║
echo  ║                                      ║
echo  ╚══════════════════════════════════════╝
echo.

echo  Открываю браузер...
start "" "http://localhost:3000"

echo.
echo  Для остановки запустите stop.bat
echo  или нажмите любую клавишу для выхода из этого окна.
echo.
pause >nul
