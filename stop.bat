@echo off
chcp 65001 >nul
title Chimera v5.0 — Остановка
color 0E

echo.
echo  ╔══════════════════════════════════════╗
echo  ║      CHIMERA v5.0 — ОСТАНОВКА       ║
echo  ╚══════════════════════════════════════╝
echo.

cd /d "C:\chimera project"

echo  Останавливаю контейнеры...
docker compose down

if %errorlevel% equ 0 (
    color 0A
    echo.
    echo  Все сервисы остановлены.
) else (
    color 0C
    echo.
    echo  Ошибка при остановке.
)

echo.
pause
